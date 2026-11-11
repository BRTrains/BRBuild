"""Build purchase-list NML after the candidate items are known."""

import json
import logging
import re
import subprocess
import sys
from pathlib import Path

from Vehicle import PurchaseList
from Vehicle.PublicVariants import public_variants

logger = logging.getLogger(__name__)


class PurchaseListBuilder:
    """Resolve and generate a project's purchase-list configuration."""

    @staticmethod
    def build(ctx) -> tuple[list, list]:
        """Return generated purchase-list NML and any manual file it replaces."""
        grf = getattr(ctx, "grf", None)
        manual_file = getattr(grf, "purchase_list_file", None)
        script = getattr(grf, "purchase_list_script", None)

        if manual_file is not None:
            path = PurchaseListBuilder._resolve_path(
                ctx, manual_file, root=ctx.project.path / ctx.project.grfFolder, setting="purchase_list.file"
            )
            if not path.is_file():
                raise FileNotFoundError(f"Purchase-list file not found: {path}")
            logger.info(f"Using manual purchase-list NML file: {path}")
            return [PurchaseListBuilder._filter_manual(path.read_text(encoding="utf-8"), ctx)], [path]

        if script:
            block = PurchaseListBuilder._run_script(script, ctx)
            if not block.strip():
                logger.warning(
                    f"Purchase-list script '{script}' returned no block: no purchase-list order "
                    "will be emitted."
                )
                return [], []

            stored = PurchaseListBuilder._write(ctx, block)
            logger.info(
                f"Purchase-list script '{script}' returned {len(block.splitlines())} line(s), "
                f"stored at {stored}."
            )
            return [block], []

        order = getattr(grf, "purchase_list_order", PurchaseList.NONE)
        if order == PurchaseList.NONE:
            return [], []

        variants = public_variants(ctx.successful_variants)
        generated = PurchaseList.build_blocks(variants, order)
        if generated:
            logger.info(
                f"Purchase-list order '{order}': wrote {len(generated)} sort block(s) "
                f"for {len(variants)} variant(s)."
            )
        return generated, []

    @staticmethod
    def _write(ctx, block: str) -> Path:
        destination = Path(ctx.nml_output_folder) / "purchase_list.pnml"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(block.rstrip("\n") + "\n", encoding="utf-8")
        return destination

    @staticmethod
    def _resolve_path(ctx, relative: str, *, root, setting: str) -> Path:
        allowed = Path(root).expanduser().resolve()
        path = (allowed / relative).resolve()
        if path != allowed and allowed not in path.parents:
            raise ValueError(f"'{setting}' must stay inside {allowed}: {relative}")
        return path

    @staticmethod
    def _write_items(ctx) -> Path:
        """Write the items this build produced, in feature/build order, for a script."""
        features: dict[str, list[dict]] = {}
        for position, variant in enumerate(public_variants(ctx.successful_variants)):
            facts = PurchaseList.facts_from_variant(variant, position)
            features.setdefault(facts.feature, []).append(
                {
                    "identifier": facts.identifier,
                    "vehicle": facts.unit,
                    "profile": str(getattr(getattr(variant, "profile", None), "identifier", "") or ""),
                    "livery": str(getattr(getattr(variant, "livery", None), "name", "") or ""),
                    "name": facts.name,
                }
            )

        destination = Path(ctx.nml_output_folder) / "purchase_list_items.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps({"project": ctx.project.name, "features": features}, indent=1) + "\n",
            encoding="utf-8",
        )
        return destination

    @staticmethod
    def _run_script(relative: str, ctx) -> str:
        script = PurchaseListBuilder._resolve_path(
            ctx, relative, root=ctx.project.path, setting="purchase_list.script"
        )
        if not script.is_file():
            raise FileNotFoundError(f"Purchase-list script not found: {script}")

        items = PurchaseListBuilder._write_items(ctx)
        completed = subprocess.run(
            [sys.executable, str(script), "--items", str(items)],
            cwd=str(ctx.project.path),
            capture_output=True,
            text=True,
        )
        for line in completed.stdout.splitlines():
            logger.debug(f"purchase-list script: {line}")
        if completed.returncode != 0:
            raise RuntimeError(
                f"Purchase-list script '{script}' failed with exit code {completed.returncode}: "
                f"{completed.stderr.strip() or 'no error output'}"
            )
        logger.info(
            f"Ran purchase-list script '{relative}' for "
            f"{len(public_variants(ctx.successful_variants))} variant(s)."
        )
        return completed.stdout

    @staticmethod
    def _filter_manual(text: str, ctx) -> str:
        """Remove item symbols for variants excluded from this build."""
        available = {variant.identifier for variant in public_variants(ctx.successful_variants)}
        filtered = []
        for line in text.splitlines(keepends=True):
            match = re.match(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*),(\s*(?://.*)?\r?\n?)$", line)
            if match and match.group(2) not in available:
                logger.warning(
                    f"Omitting '{match.group(2)}' from the manual purchase list: "
                    "the corresponding variant did not build successfully."
                )
                newline = "\n" if line.endswith("\n") else ""
                filtered.append(f"{match.group(1)}// omitted unavailable item: {match.group(2)},{newline}")
            else:
                filtered.append(line)
        return "".join(filtered)
