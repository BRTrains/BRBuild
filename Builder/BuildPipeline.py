"""Run the ordered BRBuild lifecycle."""

import logging
import time

from Badge import BadgeRegistry
from Lang.StringRegistry import _registry
from .BuildContext import BuildContext
from .ManifestWriter import ManifestWriter

logger = logging.getLogger(__name__)


class BuildPipeline:
    """Execute the existing build stages without owning their implementations."""

    def __init__(self, builder):
        self.builder = builder

    def run(self, project_data, log_nml_output=False, release=False, docs=False):
        # Clear global registries so each project build starts fresh
        _registry.clear()
        BadgeRegistry().clear()
        context = BuildContext(
            project_data=project_data,
            log_nml_output=log_nml_output,
            release=release,
        )

        stages = [
            self.builder._load_project,
            self.builder._validate_project_path,
            self.builder._load_sprite_id_registry,
            self.builder._load_grf,
            self.builder._load_railtypes,
            self.builder._load_palette,
            self.builder._write_templates,
            self.builder._discover_candidates,
            self.builder._prepare_sprite_ids,
            self.builder._process_candidates,
            self.builder._write_errors,
            self.builder._finalize_sprite_ids,
            self.builder._collate_nml,
            self.builder._write_language,
            self.builder._compile_newgrf,
            self.builder._finalize_sprite_ingests,
            self.builder._copy_newgrf,
        ]

        start_time = time.time()
        for stage in stages:
            try:
                stage(context)
            except Exception as exc:
                logger.exception(f"Build stage {stage.__name__} failed: {exc}")
                if docs:
                    self.builder._write_manifest_failure(context, exc)
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

