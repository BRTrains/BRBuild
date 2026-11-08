"""Collate, localize, compile, and publish build output."""

import logging
from pathlib import Path

from Lang.StringRegistry import _registry
from Lang.StringWriter import StringWriter
from .PurchaseListBuilder import PurchaseListBuilder

logger = logging.getLogger(__name__)


class NmlOutput:
    """Own the final output stages while retaining the existing BuildContext contract."""

    def __init__(self, collator, compiler):
        self.collator = collator
        self.compiler = compiler

    def collate(self, ctx):
        if len(ctx.nml_files) == 0:
            raise RuntimeError("No NML files available for collation.")

        custom_nml_folder = ctx.project.path / ctx.project.grfFolder / "custom_nml"
        purchase_list_blocks, skipped_custom_nml = PurchaseListBuilder.build(ctx)
        ctx.nml_filepath = self.collator.collate(
            ctx.nml_files,
            ctx.project.name,
            custom_nml_folder,
            ctx.project.path,
            candidates_root=ctx.project.path,
            staged_candidate_nml=Path(ctx.nml_output_folder) / "candidate_nml",
            vehicle_nml_files={
                identifier: files
                for identifier, files in ctx.vehicle_nml_files.items()
                if identifier not in ctx.failed_units
            },
            variant_owners=ctx.variant_owners,
            generated_trailing_nml=purchase_list_blocks,
            skip_custom_nml=skipped_custom_nml,
        )
        logger.info(f"NML collation complete: {ctx.nml_filepath}")

    def write_language(self, ctx):
        ctx.lang_folder = str(Path(ctx.nml_output_folder) / "lang")
        ctx.sprite_id_registry.register_deprecated_strings(_registry.write_string)
        string_writer = StringWriter(_registry, ctx.lang_folder)
        string_writer.write_file()
        logger.info(f"Wrote language file to {ctx.lang_folder}")

    def compile(self, ctx):
        if not ctx.nml_filepath:
            raise RuntimeError("NML file path is missing for compilation.")

        ctx.newgrf_filepath = self.compiler.compile(ctx.nml_filepath, ctx.lang_folder, ctx.log_nml_output)
        logger.info(f"newGRF compilation complete: {ctx.newgrf_filepath}")

    def copy(self, ctx):
        if not getattr(ctx, "newgrf_filepath", None):
            raise RuntimeError("Compiled GRF path is missing for copying.")

        self.compiler.copy_newgrf(ctx.newgrf_filepath)
        logger.info(f"newGRF copying complete for {ctx.newgrf_filepath}")
