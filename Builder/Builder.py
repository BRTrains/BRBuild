import time
import logging
from pathlib import Path

from Lang.StringRegistry import _registry
from Lang.StringWriter import StringWriter
from NmlWriter import NmlGrfWriter, NmlVariantWriter, NmlCollator, NmlCompiler
from Project import Project
from Vehicle import VariantIterator
from YamlHandler import VehicleLoader, GrfLoader
from .BuildContext import BuildContext
from .CandidateFinder import CandidateFinder

logger = logging.getLogger(__name__)


class Builder:

    def __init__(self):
        self.nmlCollator = NmlCollator()
        self.nmlCompiler = NmlCompiler()
        return

    def build(self, project_data, log_nml_output=False):
        # Clear the global string registry so each project build starts fresh
        _registry.clear()
        context = BuildContext(project_data=project_data, log_nml_output=log_nml_output)

        stages = [
            self._load_project,
            self._validate_project_path,
            self._load_grf,
            self._discover_candidates,
            self._process_candidates,
            self._collate_nml,
            self._write_language,
            self._compile_newgrf,
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

        ctx.nml_output_folder = f"WorkingData/{ctx.project.name}/"
        ctx.lang_folder = str(Path(ctx.nml_output_folder) / "lang")

        if not ctx.project.build:
            raise RuntimeError(f"Skipping project '{ctx.project.name}' because build is disabled.")

        logger.info(f"BRBuild is attempting to build project '{ctx.project.name}' in {ctx.project.path}.")

    def _validate_project_path(self, ctx: BuildContext):
        if not ctx.project.path.is_dir():
            raise FileNotFoundError(f"Project folder '{ctx.project.path}' does not exist.")

    def _load_grf(self, ctx: BuildContext):
        loader = GrfLoader(ctx.project.path / ctx.project.grfFolder / "GRF.yaml")
        grf = loader.load()
        writer = NmlGrfWriter(grf)
        ctx.nml_files.append(writer.write_grf_gnml(ctx.nml_output_folder + "GRF.gnml"))

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

        for pnml in candidate.get("pnml_files", []):
            logger.debug(f"\tFound manual PNML file: {pnml}")
            ctx.nml_files.append(pnml)

        for file in candidate.get("files", []):
            logger.debug(f"\tParsing YAML file: {file}")
            vehicle = VehicleLoader.load(file)
            logger.debug(
                f"\tLoaded vehicle: {vehicle.name} with identifier {vehicle.identifier}, "
                f"{len(vehicle.profiles)} profiles, and {len(vehicle.liveries)} liveries."
            )

            for variant in VariantIterator(vehicle):
                logger.debug(
                    f"\tGenerated variant: {variant.vehicle.name}, using livery {variant.livery.name} "
                    f"and profile {variant.profile.identifier}"
                )
                try:
                    variant.process()
                except Exception as exc:
                    logger.exception(f"Error processing variant {variant}: {exc}")
                    ctx.failed_variants.append(repr(variant))
                    return

                try:
                    variant_writer = NmlVariantWriter(variant, ctx.nml_output_folder)
                    nml_file = variant_writer.write()
                    ctx.nml_files.append(nml_file)
                except Exception as exc:
                    logger.exception(f"Unable to write NML for variant {variant}: {exc}")
                    ctx.failed_variants.append(repr(variant))
                    return

                ctx.successful_variants.append(variant)

    def _collate_nml(self, ctx: BuildContext):
        if len(ctx.nml_files) == 0:
            raise RuntimeError("No NML files available for collation.")

        ctx.nml_filepath = self.nmlCollator.collate(ctx.nml_files, ctx.project.name)
        logger.info(f"NML collation complete: {ctx.nml_filepath}")

    def _write_language(self, ctx: BuildContext):
        ctx.lang_folder = str(Path(ctx.nml_output_folder) / "lang")
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
