import logging
from pathlib import Path

from Grf.RailTypeTable import RailTypeTable
from NmlWriter import NmlGrfWriter, NmlVariantWriter, NmlCollator, NmlCompiler
from Project import Project
from Sprites.LightingOverlay import Part
from Sprites.PalettedImage import PalettedImage
from Templates.TemplateGenerator import TemplateGenerator
from Templates.TemplateLoaderNML import TemplateLoaderNML
from Vehicle import Variant, VariantIterator, VehicleSpriteAllocator
from YamlHandler import VehicleLoader, GrfLoader
from .BuildContext import BuildContext
from .CandidateFinder import CandidateFinder
from .SpriteIDRegistry import SpriteIDRegistry
from .ManifestWriter import ManifestWriter
from .GrfParameterInjector import GrfParameterInjector
from .PurchaseListBuilder import PurchaseListBuilder
from .NmlOutput import NmlOutput
from .SpriteIngestManager import SpriteIngestManager
from .CandidateProcessor import CandidateProcessor
from .SpritePreparation import SpritePreparation
from .LightingResolver import LightingResolver
from .BuildPipeline import BuildPipeline

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
        self.candidateProcessor = CandidateProcessor(self)
        self.spritePreparation = SpritePreparation(self)
        self.lightingResolver = LightingResolver()
        self.pipeline = BuildPipeline(self)
        return

    def build(self, project_data, log_nml_output=False, release=False, docs=False):
        return self.pipeline.run(project_data, log_nml_output, release, docs)

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
        return self.candidateProcessor.process_candidates(ctx)

    def _process_candidate(self, candidate, ctx: BuildContext):
        return self.candidateProcessor.process_candidate(candidate, ctx)

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
        return SpritePreparation._migrate_vehicle_metadata(vehicle)

    def _stage_palette_normalized_sheets(self, vehicle, ctx: BuildContext):
        return self.spritePreparation._stage_palette_normalized_sheets(vehicle, ctx)

    @staticmethod
    def _palette_digest(palette):
        return SpritePreparation._palette_digest(palette)

    @staticmethod
    def _file_digest(path):
        return SpritePreparation._file_digest(path)

    @staticmethod
    def _palette_stage_cache_path(destination):
        return SpritePreparation._palette_stage_cache_path(destination)

    def _palette_stage_cache_valid(self, source, destination, palette):
        return self.spritePreparation._palette_stage_cache_valid(source, destination, palette)

    def _write_palette_stage_cache(self, source, destination, palette):
        return self.spritePreparation._write_palette_stage_cache(source, destination, palette)

    def _convert_spritesheet(self, vehicle, ctx: BuildContext):
        return self.spritePreparation._convert_spritesheet(vehicle, ctx)

    @staticmethod
    def _variant_parts(variant) -> list[Part]:
        return LightingResolver._variant_parts(variant)

    @staticmethod
    def _lighting_setting(variant) -> str:
        return LightingResolver._lighting_setting(variant)

    @staticmethod
    def _variant_label(variant) -> str:
        return LightingResolver._variant_label(variant)

    def _assume_lighting_patterns(self, variants, allocator, lightings) -> None:
        return LightingResolver._assume_lighting_patterns(variants, allocator, lightings)

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
