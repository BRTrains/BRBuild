import hashlib
import json
import time
import logging
import shutil
from pathlib import Path

from Badge import BadgeRegistry
from Grf.RailTypeTable import RailTypeTable
from Lang.StringRegistry import _registry
from NmlWriter import NmlGrfWriter, NmlVariantWriter, NmlCollator, NmlCompiler
from Project import Project
from Sprites.LightingOverlay import (
    LIGHTING_AUTO,
    LIGHTING_EXACT,
    LIGHTING_NONE,
    Part,
    VehicleLighting,
    boxes_of,
    pattern_of,
)
from Sprites.PalettedImage import PalettedImage
from Templates.SpritesheetLegacyConverter import SpritesheetLegacyConverter
from Templates.TemplateGenerator import TemplateGenerator
from Templates.TemplateLoaderNML import TemplateLoaderNML
from Vehicle import Variant, VariantIterator, VehicleSpriteAllocator
from Vehicle.UsageVisibility import disable_condition
from YamlHandler import VehicleLoader, GrfLoader
from .BuildContext import BuildContext
from .CandidateFinder import CandidateFinder
from .SpriteIDRegistry import SpriteIDRegistry
from .ManifestWriter import ManifestWriter
from .GrfParameterInjector import GrfParameterInjector
from .PurchaseListBuilder import PurchaseListBuilder
from .NmlOutput import NmlOutput
from .SpriteIngestManager import SpriteIngestManager

logger = logging.getLogger(__name__)

#: The layout of the palette-stage cache files. Bumped whenever the staged sheets' own
#: content changes for an unchanged source, so existing caches are not reused across it.
PALETTE_STAGE_CACHE_VERSION = 2


class Builder:

    def __init__(self):
        self.nmlCollator = NmlCollator()
        self.nmlCompiler = NmlCompiler()
        self.nmlOutput = NmlOutput(self.nmlCollator, self.nmlCompiler)
        self.spriteIngest = SpriteIngestManager()
        return

    def build(self, project_data, log_nml_output=False, release=False, docs=False):
        # Clear global registries so each project build starts fresh
        _registry.clear()
        BadgeRegistry().clear()
        context = BuildContext(
            project_data=project_data,
            log_nml_output=log_nml_output,
            release=release,
        )

        stages = [
            self._load_project,
            self._validate_project_path,
            self._load_sprite_id_registry,
            self._load_grf,
            self._load_railtypes,
            self._load_palette,
            self._write_templates,
            self._discover_candidates,
            self._prepare_sprite_ids,
            self._process_candidates,
            self._write_errors,
            self._finalize_sprite_ids,
            self._collate_nml,
            self._write_language,
            self._compile_newgrf,
            self._finalize_sprite_ingests,
            self._copy_newgrf,
        ]

        start_time = time.time()
        for stage in stages:
            try:
                stage(context)
            except Exception as exc:
                logger.exception(f"Build stage {stage.__name__} failed: {exc}")
                if docs:
                    self._write_manifest_failure(context, exc)
                return

        if docs:
            # Documentation is deliberately outside the build-stage list: it is written only
            # after the compiled GRF has been copied, and a documentation failure must not
            # turn an otherwise successful build into a failed build.
            try:
                ManifestWriter(context.project, context.successful_variants).write()
            except Exception as exc:
                logger.exception(f"Unable to write build manifest: {exc}")
                try:
                    ManifestWriter(context.project, context.successful_variants).write_failure_report(exc)
                except Exception:
                    logger.exception("Unable to write manifest failure report.")

        elapsed = round(time.time() - start_time, 2)
        logger.info(f"BRBuild build process for project '{context.project.name}' completed successfully.")
        logger.info(f"Successful variants: {len(context.successful_variants)}. Failed variants: {len(context.failed_variants)}.")
        logger.info(f"BRBuild project '{context.project.name}' build complete after {elapsed} seconds.")

    @staticmethod
    def _write_manifest_failure(ctx: BuildContext, error: Exception):
        """Record a failed build without allowing diagnostics to change its result."""
        if ctx.project is None:
            return
        try:
            ManifestWriter(ctx.project, ctx.successful_variants).write_failure_report(error)
        except Exception:
            logger.exception("Unable to write manifest failure report.")

    def _load_project(self, ctx: BuildContext):
        if isinstance(ctx.project_data, Project):
            logger.debug(f"Received project data is already a Project instance: {ctx.project_data}")
            ctx.project = ctx.project_data
        else:
            logger.debug(f"Received project data is not a Project instance, attempting to create one: {ctx.project_data}")
            ctx.project = Project(ctx.project_data)

        ctx.nml_output_folder = str(ctx.project.path / "WorkingData" / ctx.project.name)
        ctx.lang_folder = str(Path(ctx.nml_output_folder) / "lang")

        if not ctx.project.build:
            raise RuntimeError(f"Skipping project '{ctx.project.name}' because build is disabled.")

        logger.info(f"BRBuild is attempting to build project '{ctx.project.name}' in {ctx.project.path}.")

    def _validate_project_path(self, ctx: BuildContext):
        if not ctx.project.path.is_dir():
            raise FileNotFoundError(f"Project folder '{ctx.project.path}' does not exist.")

    def _load_sprite_id_registry(self, ctx: BuildContext):
        registry_folder = ctx.project.path / ctx.project.grfFolder
        ctx.sprite_id_registry = SpriteIDRegistry(
            registry_folder / "VehicleIDData.yaml",
            registry_folder / "generated_variants",
            release=ctx.release,
        )

    def _load_grf(self, ctx: BuildContext):
        loader = GrfLoader(ctx.project.path / ctx.project.grfFolder / "GRF.yaml")
        grf = loader.load()
        self._ensure_cost_parameters(grf)
        self._ensure_general_parameters(grf)
        if self._is_default_template_folder(self._resolve_template_folder(ctx)):
            ctx.template_alignment_param_index = self._ensure_template_alignment_param(grf)
        ctx.grf = grf
        writer = NmlGrfWriter(grf)
        output_path = Path(ctx.nml_output_folder) / "GRF.gnml"
        ctx.nml_files.append(writer.write_grf_gnml(output_path))

    @staticmethod
    def _ensure_cost_parameters(grf):
        return GrfParameterInjector.ensure_cost_parameters(grf)

    @staticmethod
    def _ensure_general_parameters(grf):
        return GrfParameterInjector.ensure_general_parameters(grf)

    @staticmethod
    def _ensure_template_alignment_param(grf):
        return GrfParameterInjector.ensure_template_alignment_param(grf)

    def _load_railtypes(self, ctx: BuildContext):
        """Load the project's `RailTypes.yaml`, if it has one, and emit it as NML.

        The table maps each logical track type a vehicle can name onto the real
        railtype labels it resolves to. Its NML is collated before every vehicle block,
        because the constants it declares are what a `track_type` property references.

        A project without the file keeps NML's default table and ordinary rail.
        """
        path = ctx.project.path / ctx.project.grfFolder / "RailTypes.yaml"
        if path.is_file():
            ctx.rail_type_table = RailTypeTable.load(path)
            logger.info(
                f"Loaded railtype table with {len(ctx.rail_type_table.keys())} track type(s) "
                f"from {path}."
            )
        else:
            ctx.rail_type_table = Variant.DEFAULT_RAILTYPE_TABLE
            logger.debug(
                f"No RailTypes.yaml in '{ctx.project.path / ctx.project.grfFolder}'; "
                f"using the default railtype table."
            )

        output_path = Path(ctx.nml_output_folder) / "RailTypes.gnml"
        NmlGrfWriter(None).write_railtype_table(ctx.rail_type_table, output_path)
        ctx.nml_files.append(str(output_path))

    def _load_palette(self, ctx: BuildContext):
        ctx.palette = PalettedImage.load_palette(ctx.project.palette)
        logger.debug(f"Loaded palette from {ctx.project.palette}")

    def _write_templates(self, ctx: BuildContext):
        """Generate the template catalogue before vehicle candidates are processed."""
        template_dir = self._resolve_template_folder(ctx)
        if template_dir is None:
            logger.debug("No template folder found; skipping template pre-write.")
            return

        output_path = Path(ctx.nml_output_folder) / "Templates.gnml"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if self._is_default_template_folder(template_dir):
            archive_dir = template_dir / "archive"
            if not archive_dir.is_dir():
                raise FileNotFoundError(f"BRBuild template archive is missing: {archive_dir}")
            output_path.write_text(
                TemplateGenerator(archive_dir).render(),
                encoding="utf-8",
            )
            logger.info(f"Generated BRBuild templates from '{archive_dir}' to {output_path}")
        else:
            template_files = sorted(template_dir.glob("*.pnml"))
            if not template_files:
                logger.debug(f"No .pnml template files found in '{template_dir}'.")
                return
            with open(output_path, "w", encoding="utf-8") as out:
                out.write("// !!!!! Warning, auto generated file. Do not edit this file. !!!!!\n")
                out.write("// Collated NML `template` definitions, written before any vehicle candidates.\n")
                for template_file in template_files:
                    out.write(f"\n\n// File: {template_file}\n")
                    out.write(template_file.read_text(encoding="utf-8"))

        ctx.nml_files.append(str(output_path))

    @staticmethod
    def _is_default_template_folder(template_dir: Path | None) -> bool:
        return template_dir is not None and template_dir.resolve() == (Path(__file__).resolve().parent.parent / "Templates").resolve()

    def _resolve_template_folder(self, ctx: BuildContext) -> Path | None:
        if ctx.project is not None and ctx.project.templateFolder:
            candidate = ctx.project.path / ctx.project.templateFolder
            if candidate.is_dir():
                return candidate
            logger.warning(f"Configured template_folder '{candidate}' does not exist; falling back to BRBuild's default templates.")

        default_dir = Path(__file__).resolve().parent.parent / "Templates"
        return default_dir if default_dir.is_dir() else None

    def _get_template_definitions(self, ctx: BuildContext) -> list:
        """Load the generated default templates or a project's custom templates."""
        if ctx.template_definitions is None:
            template_dir = self._resolve_template_folder(ctx)
            if template_dir and self._is_default_template_folder(template_dir):
                ctx.template_definitions = TemplateGenerator(template_dir / "archive").definitions()
            else:
                ctx.template_definitions = TemplateLoaderNML().read_folder(str(template_dir)) if template_dir else []

        return ctx.template_definitions

    def _discover_candidates(self, ctx: BuildContext):
        if ctx.project.targetFolders:
            logger.debug(f"Scanning specified target folders for candidates: {ctx.project.targetFolders}")
            scan_paths = [ctx.project.path / target for target in ctx.project.targetFolders]
        else:
            logger.debug("No target folders specified; scanning project root.")
            scan_paths = [ctx.project.path]

        ctx.candidates = self.find_candidates(scan_paths)
        if len(ctx.candidates) == 0:
            raise RuntimeError(f"No candidates found for project '{ctx.project.name}'. Halting build process.")

        elapsed_candidates = len(ctx.candidates)
        logger.info(f"Candidate finding complete. Found {elapsed_candidates} candidates.")

    def _prepare_sprite_ids(self, ctx: BuildContext):
        keys = set()
        for candidate in ctx.candidates:
            for file in candidate.get("files", []):
                vehicle = VehicleLoader.load(file)
                for variant in VariantIterator(vehicle):
                    keys.add(
                        (
                            str(vehicle.identifier).strip().lower(),
                            str(variant.profile.identifier).strip().lower(),
                            str(variant.livery.name).strip().lower(),
                            self._vehicle_type_name(variant.vehicle_type),
                        )
                    )
        ctx.sprite_id_registry.prepare(keys)

    def find_candidates(self, scan_paths):
        candidates = []
        for scan_path in scan_paths:
            if not scan_path.exists():
                logger.warning(f"Target folder '{scan_path}' does not exist; skipping.")
                continue
            if not scan_path.is_dir():
                logger.warning(f"Target path '{scan_path}' is not a directory; skipping.")
                continue

            logger.debug(f"Finding candidates in folder: {scan_path}")

            finder = CandidateFinder(scan_path)
            found = finder.find_candidates()
            candidates.extend(found)

        logger.info(f"Found {len(candidates)} candidates.")
        return candidates

    def _process_candidates(self, ctx: BuildContext):
        if not ctx.candidates:
            raise RuntimeError("No candidates found")

        for candidate in ctx.candidates:
            self._process_candidate(candidate, ctx)

        if len(ctx.successful_variants) == 0:
            raise RuntimeError(f"No successful variants were generated for project '{ctx.project.name}'. Halting build process.")
        if ctx.failed_variants:
            logger.warning(
                f"{len(ctx.failed_variants)} variant(s) failed for project "
                f"'{ctx.project.name}'; continuing with successful variants."
            )

    def _process_candidate(self, candidate, ctx: BuildContext):
        logger.info(f"Processing candidate: {candidate.get('name')}")

        for file in candidate.get("files", []):
            logger.debug(f"\tParsing YAML file: {file}")
            vehicle = VehicleLoader.load(file)
            vehicle.rail_type_table = ctx.rail_type_table
            logger.debug(
                f"\tLoaded vehicle: {vehicle.name} with identifier {vehicle.identifier}, "
                f"{len(vehicle.profiles)} profiles, and {len(vehicle.liveries)} liveries."
            )

            # A candidate folder's own NML is keyed by its loaded vehicle identifier (not the
            # folder name, which need not match it) so the collator can place it immediately
            # before the blocks of the vehicle that uses it.
            for pnml in candidate.get("pnml_files", []):
                logger.debug(f"\tFound manual PNML file: {pnml}")
                staged = self._stage_candidate_nml(pnml, ctx)
                files_for_vehicle = ctx.vehicle_nml_files.setdefault(vehicle.identifier, [])
                if staged not in files_for_vehicle:
                    files_for_vehicle.append(staged)

            ingested_new_spritesheet = self._ingest_new_spritesheet(vehicle, ctx)
            has_spritesheet = self._has_any_sheet(vehicle)
            # A unit without any usable PNG is necessarily unfinished (or a utility/debug
            # definition whose artwork has not landed yet). Keep it in the GRF for development
            # mode, but hide it by default just like an explicitly flagged unit.
            vehicle.development = bool(vehicle.development) or not has_spritesheet
            if not has_spritesheet:
                self._record_failure(
                    ctx,
                    vehicle,
                    None,
                    "development mode",
                    f"No {vehicle.identifier}.png spritesheet found",
                )
            allocator = None
            variant_groups = {}

            if has_spritesheet:
                allocator = self._load_sprite_allocator(vehicle, ctx, normalize=ingested_new_spritesheet)
                if allocator is None:
                    logger.error(
                        f"Skipping vehicle '{vehicle.identifier}': unable to confidently identify spritesets "
                        f"in '{vehicle.spritesheet_path}'."
                    )
                    ctx.failed_variants.append(f"{vehicle.identifier} (spritesheet)")
                    ctx.failed_units.add(vehicle.identifier)
                    self._record_failure(
                        ctx,
                        vehicle,
                        None,
                        "sprite allocation",
                        "Unable to resolve required spritesets from spritesheet",
                    )
                    continue

            # Materialised so the lighting overlays for every variant can be resolved before any of
            # them is written: one overlay sheet per published sheet holds the union of their lamps.
            # A candidate whose profiles name spritesheets of their own gets one detector per sheet.
            # Cost scale is a GRF-level setting, but variants are the calculation boundary.
            # Keep it on the candidate so direct Variant/CostCalculator callers retain the
            # same default when no project context is present.
            vehicle.cost_scale = ctx.grf.cost_scale
            variants = list(VariantIterator(vehicle))
            failed_variant_ids = set()
            lightings: dict[str, VehicleLighting] = {}
            if allocator is not None and variants:
                for sheet in self._declared_sheets(vehicle, resolved=True):
                    if not Path(sheet).is_file():
                        # A candidate can declare a sheet nothing draws from yet.
                        continue
                    lightings[str(sheet)] = VehicleLighting(
                        vehicle,
                        ctx.palette,
                        self._get_template_definitions(ctx),
                        ctx.nml_output_folder,
                        sheet_path=sheet,
                    )

            for variant in variants:
                logger.debug(
                    f"\tGenerated variant: {variant.vehicle.name}, using livery {variant.livery.name} "
                    f"and profile {variant.profile.identifier}"
                )

                refit_liveries = []
                if allocator is not None:
                    try:
                        if getattr(variant, "is_livery_refit", False):
                            variant.refit_groups = []
                            refit_liveries = [
                                livery for livery in vehicle.liveries
                                if not livery.profiles
                                or str(variant.profile.identifier).lower() in {
                                    str(item).lower() for item in livery.profiles
                                }
                            ]
                            for livery in refit_liveries:
                                group = allocator.get(variant.profile, livery, variant.vehicle_type)
                                variant.refit_groups.append((livery.name, *group))
                            if not variant.refit_groups:
                                raise ValueError(f"No livery refits apply to profile {variant.profile.identifier}")
                            first = variant.refit_groups[0]
                            variant.spritesets, variant.sprite_template_names, variant.sprite_lengths = first[1:]
                            variant.sprite_pattern = allocator.pattern_for(variant.profile, refit_liveries[0])
                        else:
                            variant.spritesets, variant.sprite_template_names, variant.sprite_lengths = allocator.get(
                                variant.profile, variant.livery, variant.vehicle_type
                            )
                            variant.sprite_pattern = allocator.pattern_for(variant.profile, variant.livery)
                        purchase_livery = (
                            refit_liveries[0] if getattr(variant, "is_livery_refit", False) else variant.livery
                        )
                        purchase = allocator.get_purchase(
                            variant.profile, purchase_livery, ctx.nml_output_folder
                        )
                        variant.purchase_spriteset, variant.purchase_template_name = purchase if purchase else (None, None)
                    except Exception as exc:
                        logger.exception(f"Unable to assign sprites for variant {variant}: {exc}")
                        ctx.failed_variants.append(repr(variant))
                        failed_variant_ids.add(id(variant))
                        self._record_failure(ctx, vehicle, variant, "sprite allocation", exc)
                        continue

                if (
                    allocator is not None
                    and not getattr(variant, "is_livery_refit", False)
                    and variant.spritesets
                ):
                    lighting = lightings.get(str(allocator.sheet_for(variant.profile, variant.livery)))
                    if lighting is not None:
                        variant.lighting_detection = lighting.detection_for(
                            self._variant_parts(variant),
                            trailing_only=bool(variant.get_attr("has_cab")),
                        )

            if allocator is not None:
                self._assume_lighting_patterns(variants, allocator, lightings)

            for lighting in lightings.values():
                lighting.write_images()

            for variant in variants:
                if id(variant) in failed_variant_ids:
                    continue
                lighting = (
                    lightings.get(str(allocator.sheet_for(variant.profile, variant.livery)))
                    if allocator is not None
                    else None
                )
                if (
                    lighting is not None
                    and variant.lighting_detection is not None
                    and variant.lighting_detection.pixels
                ):
                    variant.lighting_overlay_path = lighting.overlay_path
                    variant.lighting_transparent_path = lighting.transparent_path
                assignment = ctx.sprite_id_registry.resolve(
                    vehicle.identifier,
                    variant.profile.identifier,
                    variant.livery.name,
                    self._vehicle_type_name(variant.vehicle_type),
                    self._compatibility_snapshot(variant),
                )
                variant.sprite_id = assignment["id"]
                variant.sprite_id_generation = assignment["generation"]
                variant.disable_item_condition = disable_condition(
                    vehicle.vehicle_type,
                    variant.vehicle_type,
                    vehicle.usage,
                    getattr(ctx.grf, "usage_filters", None),
                )
                variant.disable_item_conditions = []
                if variant.disable_item_condition:
                    variant.disable_item_conditions.append(variant.disable_item_condition)
                if vehicle.development:
                    variant.disable_item_conditions.append(
                        (variant.vehicle_type.nml_feature, "param_development_mode == 0")
                    )
                if getattr(variant, "is_livery_refit", False):
                    variant.disable_item_conditions.append(
                        (variant.vehicle_type.nml_feature, "param_livery_mode == 0")
                    )
                else:
                    variant.disable_item_conditions.append(
                        (variant.vehicle_type.nml_feature, "param_livery_mode == 1")
                    )

                try:
                    variant.process()
                except Exception as exc:
                    logger.exception(f"Error processing variant {variant}: {exc}")
                    ctx.failed_variants.append(repr(variant))
                    failed_variant_ids.add(id(variant))
                    self._record_failure(ctx, vehicle, variant, "variant processing", exc)
                    continue

                if getattr(variant, "is_livery_refit", False):
                    variant.refit_switches = []
                    applicable_liveries = [
                        livery for livery in vehicle.liveries
                        if not livery.profiles
                        or str(variant.profile.identifier).lower() in {
                            str(item).lower() for item in livery.profiles
                        }
                    ]
                    for livery in applicable_liveries:
                        source = next(
                            (
                                candidate for candidate in variants
                                if not getattr(candidate, "is_livery_refit", False)
                                and candidate.profile is variant.profile
                                and candidate.livery is livery
                                and candidate.vehicle_type == variant.vehicle_type
                                and candidate.callbacks.get("default")
                            ),
                            None,
                        )
                        if source is not None:
                            variant.refit_switches.append(
                                (livery.name, source.callbacks["default"])
                            )

                self._assign_variant_group(variant, variant_groups)

                try:
                    variant_writer = NmlVariantWriter(
                        variant, ctx.nml_output_folder,
                        ctx.template_alignment_param_index if ctx.template_alignment_param_index is not None else 4,
                    )
                    nml_file = variant_writer.write()
                    ctx.nml_files.append(nml_file)
                    ctx.variant_owners[str(nml_file)] = vehicle.identifier
                    ctx.sprite_id_registry.mark_written(assignment)
                    ctx.sprite_id_registry.archive_variant(
                        assignment,
                        nml_file,
                        dict(_registry.items()),
                        variant.identifier,
                    )
                except Exception as exc:
                    logger.exception(f"Unable to write NML for variant {variant}: {exc}")
                    ctx.failed_variants.append(repr(variant))
                    failed_variant_ids.add(id(variant))
                    self._record_failure(ctx, vehicle, variant, "NML writing", exc)
                    continue

                ctx.successful_variants.append(variant)

            if failed_variant_ids:
                ctx.failed_units.add(vehicle.identifier)
                failed_nml = {
                    path for path, owner in ctx.variant_owners.items() if owner == vehicle.identifier
                }
                ctx.nml_files = [path for path in ctx.nml_files if str(path) not in failed_nml]
                for path in failed_nml:
                    ctx.variant_owners.pop(path, None)
                ctx.successful_variants = [
                    variant for variant in ctx.successful_variants
                    if getattr(getattr(variant, "vehicle", None), "identifier", None) != vehicle.identifier
                ]

    @staticmethod
    def _record_failure(ctx, vehicle, variant, stage: str, error) -> None:
        ctx.failed_errors.append(
            {
                "unit": str(getattr(vehicle, "identifier", "unknown")),
                "name": str(getattr(vehicle, "name", "unknown")),
                "variant": (
                    str(getattr(variant, "identifier", None) or (
                        f"{getattr(getattr(variant, 'profile', None), 'identifier', 'unknown')}"
                        f"/{getattr(getattr(variant, 'livery', None), 'name', 'unknown')}"
                    ))
                    if variant is not None
                    else "unit"
                ),
                "stage": stage,
                "error": str(error),
            }
        )

    @staticmethod
    def _write_errors(ctx):
        """Write a readable vehicle-failure report before later build stages run."""
        path = ctx.project.path / "Errors.md"
        lines = [
            f"# BRBuild Errors — {ctx.project.name}",
            "",
            "This file is generated by BRBuild and is overwritten on each build.",
            "",
        ]
        if not ctx.failed_errors:
            lines.append("No vehicle errors were recorded.")
        else:
            lines += [
                f"**Failed units:** {len(ctx.failed_units)}  ",
                f"**Errors/attention items:** {len(ctx.failed_errors)}",
                "",
                "## Build issues and development units",
                "",
            ]
            for failure in ctx.failed_errors:
                lines += [
                    f"### `{failure['unit']}` — {failure['name']}",
                    f"- **Variant:** `{failure['variant']}`",
                    f"- **Stage:** {failure['stage']}",
                    f"- **Error:** `{failure['error']}`",
                    "",
                ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info(f"Wrote vehicle error report to {path}")

    @staticmethod
    def _stage_candidate_nml(pnml_path: str, ctx: BuildContext) -> str:
        """Copy a candidate's own `.pnml` into the build's working NML folder.

        Hand-written NML refers to images (and other files) relative to itself, so the
        source file is never compiled in place: a copy is staged beside the generated
        files with its quoted paths rewritten, exactly as project-level custom NML is.
        """
        source = Path(pnml_path)
        destination = Path(ctx.nml_output_folder) / "candidate_nml" / source.name
        return NmlCollator().copy_supplied_nml(source, destination, ctx.project.path)

    @staticmethod
    def _declared_sheets(vehicle, resolved: bool = False) -> list[str]:
        return SpriteIngestManager._declared_sheets(vehicle, resolved)

    @staticmethod
    def _has_any_sheet(vehicle) -> bool:
        return SpriteIngestManager._has_any_sheet(vehicle)

    @staticmethod
    def _ingest_targets(vehicle, drops: list[Path]) -> list[tuple[Path, str]]:
        return SpriteIngestManager._ingest_targets(vehicle, drops)

    @staticmethod
    def _ingest_new_spritesheet(vehicle, ctx: BuildContext) -> bool:
        return SpriteIngestManager._ingest_new_spritesheet(vehicle, ctx)

    def _finalize_sprite_ingests(self, ctx: BuildContext):
        return self.spriteIngest._finalize_sprite_ingests(ctx)

    @staticmethod
    def _built_vehicle_identifiers(ctx: BuildContext) -> set[str] | None:
        return SpriteIngestManager._built_vehicle_identifiers(ctx)

    @staticmethod
    def _vehicle_type_name(vehicle_type) -> str:
        return getattr(vehicle_type, "name", str(vehicle_type)).lower()

    @staticmethod
    def _assign_variant_group(variant, variant_groups):
        if getattr(variant, "is_livery_refit", False):
            return
        feature = NmlVariantWriter._feature(variant)
        profile_key = str(variant.profile.identifier).strip().lower()
        feature_groups = variant_groups.setdefault(feature, {})
        profile_id = feature_groups.get(profile_key)

        if profile_id is None:
            feature_groups[profile_key] = variant.sprite_id
        else:
            variant.properties["variant_group"] = profile_id

    @staticmethod
    def _compatibility_snapshot(variant) -> dict:
        capacity = variant.get_attr("capacity")
        articulated_count = variant.get_attr("num_vehicles")
        if articulated_count is None:
            articulated_count = variant.get_attr("size")

        lengths = list(getattr(variant, "sprite_lengths", None) or [])
        if not lengths:
            vehicle_length = variant.get_attr("length")
            if vehicle_length is not None:
                lengths = [vehicle_length]

        return {
            "capacity": capacity or 0,
            "articulated_count": articulated_count or 1,
            "lengths": lengths,
        }

    def _load_sprite_allocator(self, vehicle, ctx: BuildContext, *, normalize: bool = False):
        """Build a sprite allocator for a vehicle's spritesheet.

        Returns None if the sheet can't be confidently classified against the known
        templates - the caller treats that as a fatal error for this vehicle.
        """
        self._migrate_vehicle_metadata(vehicle)
        self._stage_palette_normalized_sheets(vehicle, ctx)
        # Canonicalise the staged copy as well: palette correction can expose row gutters
        # that were hidden by alpha, and NML must read the template-sized result.
        self._convert_spritesheet(vehicle, ctx)

        try:
            return VehicleSpriteAllocator(vehicle, ctx.palette, self._get_template_definitions(ctx))
        except Exception as exc:
            logger.exception(f"Unable to load sprite allocator for vehicle '{vehicle.identifier}': {exc}")
            return None

    @staticmethod
    def _migrate_vehicle_metadata(vehicle):
        """Move legacy BRBuild sidecars from a vehicle root into its ``meta`` folder."""
        sheet_path = getattr(vehicle, "spritesheet_path", None)
        if not sheet_path:
            return
        root = Path(sheet_path).parent
        if not root.is_dir():
            return
        suffixes = (
            ".sheetcache.json",
            ".lightcache.json",
            ".normalization.json",
            ".stagecache.json",
            ".purchase.json",
        )
        metadata = root / "meta"
        for legacy in root.iterdir():
            if not legacy.is_file() or not legacy.name.endswith(suffixes):
                continue
            destination = metadata / legacy.name
            try:
                metadata.mkdir(parents=True, exist_ok=True)
                if destination.is_file():
                    legacy.unlink()
                else:
                    legacy.replace(destination)
            except OSError as exc:
                logger.warning(f"Could not move legacy BRBuild metadata '{legacy}': {exc}")

    def _stage_palette_normalized_sheets(self, vehicle, ctx: BuildContext):
        """Give NML palette-valid staging copies of every sheet used by a candidate."""
        staging_root = Path(ctx.nml_output_folder) / "palette" / vehicle.identifier
        for declared in self._declared_sheets(vehicle):
            source = Path((getattr(vehicle, "spritesheet_overrides", None) or {}).get(declared, declared))
            if not source.is_file():
                continue
            destination = staging_root / Path(declared).name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if self._palette_stage_cache_valid(source, destination, ctx.palette):
                if declared == vehicle.spritesheet_path:
                    vehicle.spritesheet_override = str(destination)
                else:
                    vehicle.spritesheet_overrides[declared] = str(destination)
                continue

            image = PalettedImage.load(source, ctx.palette)
            if image.is_using_palette():
                if not destination.is_file() or destination.read_bytes() != source.read_bytes():
                    shutil.copy2(source, destination)
            else:
                image.set_palette()
                from io import BytesIO

                buffer = BytesIO()
                image.image.save(buffer, format="PNG")
                data = buffer.getvalue()
                if not destination.is_file() or destination.read_bytes() != data:
                    destination.write_bytes(data)
            self._write_palette_stage_cache(source, destination, ctx.palette)
            if declared == vehicle.spritesheet_path:
                vehicle.spritesheet_override = str(destination)
            else:
                vehicle.spritesheet_overrides[declared] = str(destination)
            logger.info(
                f"Staged palette-normalized spritesheet '{source.name}' for '{vehicle.identifier}'."
            )

    @staticmethod
    def _palette_digest(palette):
        return hashlib.sha256(bytes(bytearray(palette))).hexdigest()

    @staticmethod
    def _file_digest(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    @staticmethod
    def _palette_stage_cache_path(destination):
        destination = Path(destination)
        return destination.parent / "meta" / (destination.name + ".stagecache.json")

    def _palette_stage_cache_valid(self, source, destination, palette):
        if not Path(destination).is_file():
            return False
        try:
            payload = json.loads(self._palette_stage_cache_path(destination).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return payload == {
            "format": "brbuild-palette-stage",
            "version": PALETTE_STAGE_CACHE_VERSION,
            "source_sha256": self._file_digest(source),
            "palette_sha256": self._palette_digest(palette),
        }

    def _write_palette_stage_cache(self, source, destination, palette):
        payload = {
            "format": "brbuild-palette-stage",
            "version": PALETTE_STAGE_CACHE_VERSION,
            "source_sha256": self._file_digest(source),
            "palette_sha256": self._palette_digest(palette),
        }
        cache_path = self._palette_stage_cache_path(destination)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(payload, indent=1) + "\n", encoding="utf-8"
        )

    def _convert_spritesheet(self, vehicle, ctx: BuildContext):
        """Normalise the vehicle's spritesheets in place to only their recognised template rows.

        One sheet per drop: the candidate's own `<Vehicle>.png`, plus any sheet a profile or
        livery names for itself, each held to the same contract.
        """
        definitions = self._get_template_definitions(ctx)
        if not definitions:
            logger.debug(f"No template definitions found; skipping spritesheet conversion for '{vehicle.identifier}'.")
            return

        v_type = vehicle.vehicle_type
        v_type_str = v_type.name.lower() if hasattr(v_type, "name") else str(v_type).lower()

        sheets = [vehicle.spritesheet_path]
        sheets.extend(
            str(staged)
            for staged in (getattr(vehicle, "spritesheet_overrides", None) or {}).values()
        )

        for sheet in sheets:
            if not Path(sheet).is_file():
                # A candidate whose own sheet is absent builds from its profiles' sheets alone.
                continue
            try:
                converter = SpritesheetLegacyConverter(definitions, ctx.palette)
                kept = converter.process(sheet, v_type_str)
                if kept is None:
                    logger.info(
                        f"Reused cached normalized spritesheet '{Path(sheet).name}' for "
                        f"'{vehicle.identifier}'."
                    )
                else:
                    logger.info(
                        f"Converted spritesheet '{Path(sheet).name}' for '{vehicle.identifier}': "
                        f"kept {len(kept)} recognised row(s)."
                    )
            except Exception as exc:
                logger.exception(f"Unable to convert spritesheet '{sheet}' for '{vehicle.identifier}': {exc}")

    @staticmethod
    def _variant_parts(variant) -> list[Part]:
        """One `Part` per drawing of a variant, in consist order."""
        return [
            Part(row_y=sprite.y, template_name=template_name, boxes=boxes_of(sprite))
            for sprite, template_name in zip(variant.spritesets, variant.sprite_template_names)
        ]

    @staticmethod
    def _lighting_setting(variant) -> str:
        """A variant's `lighting` setting, resolved livery -> profile -> vehicle."""
        return str(variant.get_attr("lighting") or LIGHTING_AUTO).strip().lower()

    @staticmethod
    def _variant_label(variant) -> str:
        """A readable, greppable name for a variant, before its identifier is generated.

        The assumption pass runs before `Variant.process()`, so `variant.identifier` is still unset;
        the label is what the log and the cache record as the source of an assumption.
        """
        return f"{variant.vehicle.identifier} {variant.profile.identifier}/{variant.livery.name}"

    def _assume_lighting_patterns(self, variants, allocator, lightings) -> None:
        """Fill an unreadable livery's lamps from a sibling livery that draws the same pattern.

        Jon's rule (2026-09-25): where a unit's own artwork identifies lamps on at least one livery
        and says nothing about another, the silent one is assumed to match — one livery of a class
        shows the class's lamp geometry. A guess is worth making because a player who does not like
        it has to hand-author that vehicle's lamps anyway, so it costs nobody anything when it is
        right and is one override away when it is wrong.

        Deliberately narrow, on Jon's conditions:

        - only where **exactly one** trustworthy pattern was identified; two or more is ambiguity about which to
          use, so nothing is assumed and the rows keep their flags;
        - only within one spritesheet **and** one template, because a pattern is box-relative;
        - only from a pattern the detector did not flag, and only for a drawing it said *nothing*
          about: a row it actively rejected (over
          the cap, asymmetric, both end-on faces lit) keeps its flag for a human;
        - never for a variant set to `lighting: exact`, which is the manual override.

        Every assumption is labelled three ways so it is easy to find and confirm: the detection
        records the identifier it came from (`assumed_from`, which lands in the sheet's
        `.lightcache.json` with `"view_mapping": "assumed"`), the build logs a warning naming source
        and target, and the variant is marked in game by the lamps themselves being the guess.
        """
        identified: dict[tuple, dict[frozenset, str]] = {}
        waiting: dict[tuple, list] = {}

        for variant in variants:
            if getattr(variant, "is_livery_refit", False):
                continue
            if not variant.spritesets or self._lighting_setting(variant) == LIGHTING_NONE:
                continue
            if self._lighting_setting(variant) == LIGHTING_EXACT:
                continue  # the manual override: trust only what this vehicle's art shows

            sheet = str(allocator.sheet_for(variant.profile, variant.livery))
            parts = self._variant_parts(variant)
            if len({part.row_y for part in parts}) != len(parts):
                continue  # drawings sharing a row cannot be told apart per part

            detection = variant.lighting_detection
            for index, part in enumerate(parts):
                key = (sheet, part.template_name, index)
                if detection is not None and detection.pixels:
                    pattern = pattern_of(detection, part)
                    if detection.assumed_from or detection.flags or not pattern:
                        # An assumption is not evidence for the next one; a row the detector flagged
                        # (over the cap, asymmetric) is too unreliable to set the pattern; and a part
                        # this drawing said nothing about must not register an empty pattern.
                        continue
                    identified.setdefault(key, {}).setdefault(pattern, self._variant_label(variant))
                elif detection is None or not detection.flags:
                    waiting.setdefault(key, []).append((variant, index, parts))

        for key, targets in waiting.items():
            patterns = identified.get(key) or {}
            if len(patterns) != 1:
                continue
            pattern, source = next(iter(patterns.items()))
            sheet = key[0]
            lighting = lightings.get(sheet)
            if lighting is None:
                continue

            for variant, part_index, parts in targets:
                detection = lighting.assume_for(parts, part_index, pattern, source)
                if not detection.pixels:
                    continue
                flag = f"lamps assumed from '{source}' (same sheet and template): verify in game"
                if flag not in detection.flags:
                    detection.flags.append(flag)
                variant.lighting_detection = detection
                logger.warning(
                    f"Assumed the lighting pattern of '{source}' for "
                    f"'{self._variant_label(variant)}': its own drawing showed no lamps. The sidecar "
                    f"beside the sheet records it as \"view_mapping\": \"assumed\"; set "
                    f"`lighting: exact` on that livery (or its profile or vehicle) to keep the "
                    f"artwork as drawn instead."
                )

    def _collate_nml(self, ctx: BuildContext):
        return self.nmlOutput.collate(ctx)

    @staticmethod
    def _purchase_list_nml(ctx: BuildContext) -> tuple[list, list]:
        """Compatibility wrapper for purchase-list generation."""
        return PurchaseListBuilder.build(ctx)

    def _finalize_sprite_ids(self, ctx: BuildContext):
        deprecated_files = ctx.sprite_id_registry.finalize(ctx.nml_output_folder)
        ctx.nml_files.extend(deprecated_files)

    def _write_language(self, ctx: BuildContext):
        return self.nmlOutput.write_language(ctx)

    def _compile_newgrf(self, ctx: BuildContext):
        return self.nmlOutput.compile(ctx)

    def _copy_newgrf(self, ctx: BuildContext):
        return self.nmlOutput.copy(ctx)
