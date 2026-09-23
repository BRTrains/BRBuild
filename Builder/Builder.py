import time
import logging
import shutil
from pathlib import Path

from Badge import BadgeRegistry
from Grf.RailTypeTable import RailTypeTable
from Lang.StringRegistry import _registry
from Lang.StringWriter import StringWriter
from NmlWriter import NmlGrfWriter, NmlVariantWriter, NmlCollator, NmlCompiler
from Project import Project
from Sprites.PalettedImage import PalettedImage
from Templates.SpritesheetLegacyConverter import SpritesheetLegacyConverter
from Templates.TemplateLoaderNML import TemplateLoaderNML
from Vehicle import PurchaseList, Variant, VariantIterator, VehicleSpriteAllocator
from YamlHandler import VehicleLoader, GrfLoader
from .BuildContext import BuildContext
from .CandidateFinder import CandidateFinder
from .SpriteIDRegistry import SpriteIDRegistry

logger = logging.getLogger(__name__)


class Builder:

    def __init__(self):
        self.nmlCollator = NmlCollator()
        self.nmlCompiler = NmlCompiler()
        return

    def build(self, project_data, log_nml_output=False, release=False):
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
                return

        elapsed = round(time.time() - start_time, 2)
        logger.info(f"BRBuild build process for project '{context.project.name}' completed successfully.")
        logger.info(f"Successful variants: {len(context.successful_variants)}. Failed variants: {len(context.failed_variants)}.")
        logger.info(f"BRBuild project '{context.project.name}' build complete after {elapsed} seconds.")

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
        ctx.grf = grf
        writer = NmlGrfWriter(grf)
        output_path = Path(ctx.nml_output_folder) / "GRF.gnml"
        ctx.nml_files.append(writer.write_grf_gnml(output_path))

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
        """Pre-write the project's (or BRBuild's default) NML template blocks.

        These must be collated before any vehicle candidates, since vehicles reference
        `tmpl_*` templates by name in their generated spriteset() blocks.
        """
        template_dir = self._resolve_template_folder(ctx)
        if template_dir is None:
            logger.debug("No template folder found; skipping template pre-write.")
            return

        template_files = sorted(template_dir.glob("*.pnml"))
        if not template_files:
            logger.debug(f"No .pnml template files found in '{template_dir}'.")
            return

        output_path = Path(ctx.nml_output_folder) / "Templates.gnml"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as out:
            out.write("// !!!!! Warning, auto generated file. Do not edit this file. !!!!!\n")
            out.write("// Collated NML `template` definitions, written before any vehicle candidates.\n")
            for template_file in template_files:
                out.write(f"\n\n// File: {template_file}\n")
                out.write(template_file.read_text(encoding="utf-8"))

        ctx.nml_files.append(str(output_path))
        logger.info(f"Pre-wrote {len(template_files)} template file(s) from '{template_dir}' to {output_path}")

    def _resolve_template_folder(self, ctx: BuildContext) -> Path | None:
        if ctx.project is not None and ctx.project.templateFolder:
            candidate = ctx.project.path / ctx.project.templateFolder
            if candidate.is_dir():
                return candidate
            logger.warning(f"Configured template_folder '{candidate}' does not exist; falling back to BRBuild's default templates.")

        default_dir = Path(__file__).resolve().parent.parent / "Templates"
        return default_dir if default_dir.is_dir() else None

    def _get_template_definitions(self, ctx: BuildContext) -> list:
        """Load (and cache) the project's or BRBuild's default NML template definitions."""
        if ctx.template_definitions is None:
            template_dir = self._resolve_template_folder(ctx)
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
            has_spritesheet = bool(vehicle.spritesheet_path) and Path(vehicle.spritesheet_path).is_file()
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
                    continue

            for variant in VariantIterator(vehicle):
                logger.debug(
                    f"\tGenerated variant: {variant.vehicle.name}, using livery {variant.livery.name} "
                    f"and profile {variant.profile.identifier}"
                )

                if allocator is not None:
                    try:
                        variant.spritesets, variant.sprite_template_names, variant.sprite_lengths = allocator.get(
                            variant.profile, variant.livery, variant.vehicle_type
                        )
                        purchase = allocator.get_purchase(
                            variant.profile, variant.livery, ctx.nml_output_folder
                        )
                        variant.purchase_spriteset, variant.purchase_template_name = purchase if purchase else (None, None)
                    except Exception as exc:
                        logger.exception(f"Unable to assign sprites for variant {variant}: {exc}")
                        ctx.failed_variants.append(repr(variant))
                        return

                assignment = ctx.sprite_id_registry.resolve(
                    vehicle.identifier,
                    variant.profile.identifier,
                    variant.livery.name,
                    self._vehicle_type_name(variant.vehicle_type),
                    self._compatibility_snapshot(variant),
                )
                variant.sprite_id = assignment["id"]
                variant.sprite_id_generation = assignment["generation"]

                try:
                    variant.process()
                except Exception as exc:
                    logger.exception(f"Error processing variant {variant}: {exc}")
                    ctx.failed_variants.append(repr(variant))
                    return

                self._assign_variant_group(variant, variant_groups)

                try:
                    variant_writer = NmlVariantWriter(variant, ctx.nml_output_folder)
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
                    return

                ctx.successful_variants.append(variant)

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
    def _ingest_new_spritesheet(vehicle, ctx: BuildContext) -> bool:
        """Stage one PNG from the vehicle's ``new/`` drop folder for this build.

        The published spritesheet stays untouched until the build succeeds: the staged
        copy becomes the sheet this build reads and normalises, and
        `_finalize_sprite_ingests` publishes it only after the GRF has been compiled.
        """
        if not vehicle.spritesheet_path:
            return False

        base_path = Path(vehicle.spritesheet_path)
        vehicle_folder = base_path.parent
        new_folder = vehicle_folder / "new"
        if not new_folder.is_dir():
            return False

        candidates = sorted(
            path for path in new_folder.iterdir() if path.is_file() and path.suffix.lower() == ".png"
        )
        if not candidates:
            return False
        if len(candidates) > 1:
            raise ValueError(f"Expected one PNG in '{new_folder}', found {len(candidates)}.")

        staging_folder = Path(ctx.nml_output_folder) / "ingest" / vehicle.identifier
        if staging_folder.exists():
            shutil.rmtree(staging_folder)
        staging_folder.mkdir(parents=True, exist_ok=True)
        staging_path = staging_folder / base_path.name

        shutil.copy2(candidates[0], staging_path)
        vehicle.spritesheet_override = str(staging_path)
        ctx.pending_sprite_ingests.append(
            {
                "vehicle": vehicle,
                "new_path": candidates[0],
                "staging_path": staging_path,
                "ingested_path": vehicle_folder / "ingested" / base_path.name,
                "base_path": base_path,
            }
        )
        logger.info(
            f"Staged new spritesheet '{candidates[0]}' as '{staging_path}' for "
            f"'{vehicle.identifier}'."
        )
        return True

    def _finalize_sprite_ingests(self, ctx: BuildContext):
        """Publish staged spritesheets after a successful build.

        The latest raw ingestion is retained in ``ingested/`` for artists and debugging,
        and the ``new/`` folder is emptied so it is obvious where replacement artwork goes.
        """
        if not ctx.pending_sprite_ingests:
            return

        built_vehicles = self._built_vehicle_identifiers(ctx)
        staging_root = None
        for ingest in ctx.pending_sprite_ingests:
            vehicle = ingest["vehicle"]
            if built_vehicles is not None and vehicle.identifier not in built_vehicles:
                error_folder = ingest["base_path"].parent / "error"
                error_folder.mkdir(parents=True, exist_ok=True)
                for stale in error_folder.glob("*.png"):
                    stale.unlink()
                error_path = error_folder / ingest["base_path"].name
                shutil.move(str(ingest["new_path"]), error_path)
                staging_root = Path(ingest["staging_path"]).parent.parent
                logger.warning(
                    f"Moved errored spritesheet for '{vehicle.identifier}' to '{error_path}': "
                    f"the build produced no successful variant for it."
                )
                continue

            base_path = ingest["base_path"]
            ingested_folder = ingest["ingested_path"].parent
            ingested_folder.mkdir(parents=True, exist_ok=True)
            for stale in ingested_folder.glob("*.png"):
                stale.unlink()

            shutil.copy2(ingest["staging_path"], base_path)
            shutil.move(str(ingest["new_path"]), ingest["ingested_path"])
            staging_root = Path(ingest["staging_path"]).parent.parent
            logger.info(
                f"Ingested spritesheet for '{vehicle.identifier}': "
                f"published '{base_path}' and retained the raw source at "
                f"'{ingest['ingested_path']}'."
            )

        # The staging folder is shared by every vehicle in the build, so it is only
        # safe to remove once every staged sheet has been published.
        if staging_root is not None:
            shutil.rmtree(staging_root, ignore_errors=True)

        ctx.pending_sprite_ingests.clear()

    @staticmethod
    def _built_vehicle_identifiers(ctx: BuildContext) -> set[str] | None:
        """Identifiers of vehicles that produced at least one successful variant.

        Returns None when the evidence is unavailable, in which case every staged sheet is
        published rather than risking a silent no-op.
        """
        def identifier(variant) -> str | None:
            return getattr(getattr(variant, "vehicle", None), "identifier", None)

        successful: set[str] = {name for variant in ctx.successful_variants if (name := identifier(variant))}
        failed: set[str] = {name for variant in ctx.failed_variants if (name := identifier(variant))}

        if not successful and not failed:
            return None

        return successful - failed


    @staticmethod
    def _vehicle_type_name(vehicle_type) -> str:
        return getattr(vehicle_type, "name", str(vehicle_type)).lower()

    @staticmethod
    def _assign_variant_group(variant, variant_groups):
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
        if normalize:
            self._convert_spritesheet(vehicle, ctx)
        else:
            logger.debug(
                f"Using existing spritesheet for '{vehicle.identifier}' without in-place normalization."
            )

        try:
            return VehicleSpriteAllocator(vehicle, ctx.palette, self._get_template_definitions(ctx))
        except Exception as exc:
            logger.exception(f"Unable to load spritesheet for vehicle '{vehicle.identifier}': {exc}")
            return None

    def _convert_spritesheet(self, vehicle, ctx: BuildContext):
        """Normalise a vehicle's spritesheet in place to only its recognised template rows."""
        definitions = self._get_template_definitions(ctx)
        if not definitions:
            logger.debug(f"No template definitions found; skipping spritesheet conversion for '{vehicle.identifier}'.")
            return

        v_type = vehicle.vehicle_type
        v_type_str = v_type.name.lower() if hasattr(v_type, "name") else str(v_type).lower()

        try:
            converter = SpritesheetLegacyConverter(definitions, ctx.palette)
            kept = converter.process(vehicle.spritesheet_path, v_type_str)
            logger.info(f"Converted spritesheet for '{vehicle.identifier}': kept {len(kept)} recognised row(s).")
        except Exception as exc:
            logger.exception(f"Unable to convert spritesheet for vehicle '{vehicle.identifier}': {exc}")

    def _collate_nml(self, ctx: BuildContext):
        if len(ctx.nml_files) == 0:
            raise RuntimeError("No NML files available for collation.")

        custom_nml_folder = ctx.project.path / ctx.project.grfFolder / "custom_nml"
        purchase_list_blocks, skipped_custom_nml = self._purchase_list_nml(ctx)
        ctx.nml_filepath = self.nmlCollator.collate(
            ctx.nml_files,
            ctx.project.name,
            custom_nml_folder,
            ctx.project.path,
            candidates_root=ctx.project.path,
            staged_candidate_nml=Path(ctx.nml_output_folder) / "candidate_nml",
            vehicle_nml_files=ctx.vehicle_nml_files,
            variant_owners=ctx.variant_owners,
            generated_trailing_nml=purchase_list_blocks,
            skip_custom_nml=skipped_custom_nml,
        )
        logger.info(f"NML collation complete: {ctx.nml_filepath}")

    @staticmethod
    def _purchase_list_nml(ctx: BuildContext) -> tuple[list, list]:
        """Return the project's purchase-list NML, and any file it replaces.

        A `sort` block names the generated items, so it can only be written once the
        variants exist; the blocks go after every item and before any hand-written
        `custom_nml/append` file.

        `purchase_list.file` names a manual NML file the project maintains itself
        (relative to the GRF folder). Its contents are returned as a generated block,
        and the path is returned as well so the collator does not compile the same
        file a second time from its `custom_nml` folder.
        """
        grf = getattr(ctx, "grf", None)
        manual_file = getattr(grf, "purchase_list_file", None)
        if manual_file:
            path = (ctx.project.path / ctx.project.grfFolder / manual_file).resolve()
            grf_root = (ctx.project.path / ctx.project.grfFolder).resolve()
            if grf_root not in path.parents:
                raise ValueError(
                    f"'purchase_list.file' must stay inside the GRF folder: {manual_file}"
                )
            if not path.is_file():
                raise FileNotFoundError(f"Purchase-list file not found: {path}")
            logger.info(f"Using manual purchase-list NML file: {path}")
            return [path.read_text(encoding="utf-8")], [path]

        order = getattr(grf, "purchase_list_order", PurchaseList.NONE)
        if order == PurchaseList.NONE:
            return [], []

        blocks = PurchaseList.build_blocks(ctx.successful_variants, order)
        if blocks:
            logger.info(
                f"Purchase-list order '{order}': wrote {len(blocks)} sort block(s) "
                f"for {len(ctx.successful_variants)} variant(s)."
            )
        return blocks, []

    def _finalize_sprite_ids(self, ctx: BuildContext):
        deprecated_files = ctx.sprite_id_registry.finalize(ctx.nml_output_folder)
        ctx.nml_files.extend(deprecated_files)

    def _write_language(self, ctx: BuildContext):
        ctx.lang_folder = str(Path(ctx.nml_output_folder) / "lang")
        ctx.sprite_id_registry.register_deprecated_strings(_registry.write_string)
        string_writer = StringWriter(_registry, ctx.lang_folder)
        string_writer.write_file()
        logger.info(f"Wrote language file to {ctx.lang_folder}")

    def _compile_newgrf(self, ctx: BuildContext):
        if not ctx.nml_filepath:
            raise RuntimeError("NML file path is missing for compilation.")

        ctx.newgrf_filepath = self.nmlCompiler.compile(ctx.nml_filepath, ctx.lang_folder, ctx.log_nml_output)
        logger.info(f"newGRF compilation complete: {ctx.newgrf_filepath}")

    def _copy_newgrf(self, ctx: BuildContext):
        if not getattr(ctx, 'newgrf_filepath', None):
            raise RuntimeError("Compiled GRF path is missing for copying.")

        self.nmlCompiler.copy_newgrf(ctx.newgrf_filepath)
        logger.info(f"newGRF copying complete for {ctx.newgrf_filepath}")
