"""Manage spritesheet ingestion and publication across a build."""

import logging
import shutil
from pathlib import Path

from .BuildContext import BuildContext

logger = logging.getLogger(__name__)


class SpriteIngestManager:
    """Stage dropped artwork and publish it only after a successful build."""

    @staticmethod
    def _declared_sheets(vehicle, resolved: bool = False) -> list[str]:
        """Every spritesheet a candidate draws from, in declaration order.

        The candidate's own sheet first, then any sheet a profile or livery names for itself,
        de-duplicated by resolved path. A candidate with no standalone sheets — which is
        every candidate in both projects but the new Mk families — reports one path.

        `resolved` returns the paths the build reads, with an ingest's staged copy substituted
        for the published sheet (used for existence checks and for the per-sheet lighting
        detectors); the default returns the published paths, which is what a drop in `new/` is
        matched against.
        """
        sheets: list[str] = []
        overrides = getattr(vehicle, "spritesheet_overrides", None) or {}
        own = getattr(vehicle, "spritesheet_path", None)
        if own:
            sheets.append(str(own))

        for collection in (
            getattr(vehicle, "profiles", None) or [],
            getattr(vehicle, "liveries", None) or [],
        ):
            for entry in collection:
                declared = getattr(entry, "spritesheet", None)
                if not declared:
                    continue
                if any(Path(existing).resolve() == Path(declared).resolve() for existing in sheets):
                    continue
                if resolved:
                    declared = overrides.get(str(declared), declared)
                sheets.append(str(declared))

        return sheets


    @classmethod
    def _has_any_sheet(cls, vehicle) -> bool:
        """Whether any sheet this build will read exists on disk.

        A candidate whose only profiles name sheets of their own needs no `<Vehicle>.png`, so the
        check is over every declared sheet rather than the candidate's own alone.
        """
        return any(Path(sheet).is_file() for sheet in cls._declared_sheets(vehicle, resolved=True))


    @classmethod
    def _ingest_targets(cls, vehicle, drops: list[Path]) -> list[tuple[Path, str]]:
        """Pair each PNG dropped in `new/` with the spritesheet it replaces.

        A drop is matched to a sheet by file name. A single unclaimed drop is paired with the one
        unclaimed sheet, which keeps the long-standing convenience of dropping a sheet under any
        name; anything ambiguous is refused with the names the candidate expects, because a drop
        silently ingested into the wrong sheet rewrites the wrong artwork.
        """
        sheets = cls._declared_sheets(vehicle)
        by_name = {Path(sheet).name.lower(): sheet for sheet in sheets}

        pairs: list[tuple[Path, str]] = []
        claimed: set[str] = set()
        unmatched_sheets = list(sheets)
        unmatched_drops: list[Path] = []

        for drop in drops:
            sheet = by_name.get(drop.name.lower())
            if sheet is not None and sheet not in claimed:
                pairs.append((drop, sheet))
                claimed.add(sheet)
                unmatched_sheets = [item for item in unmatched_sheets if item != sheet]
            elif sheet is not None:
                raise ValueError(
                    f"Two drops in '{drop.parent}' both name the sheet '{Path(sheet).name}'."
                )
            else:
                unmatched_drops.append(drop)

        if len(unmatched_drops) == 1 and len(unmatched_sheets) == 1:
            pairs.append((unmatched_drops[0], unmatched_sheets[0]))
            unmatched_drops = []
            unmatched_sheets = []

        if unmatched_drops:
            expected = ", ".join(Path(sheet).name for sheet in unmatched_sheets) or "none"
            raise ValueError(
                f"Cannot tell which spritesheet the drop(s) "
                f"{', '.join(drop.name for drop in unmatched_drops)} in '{drops[0].parent}' belong "
                f"to for '{vehicle.identifier}': name a drop after the sheet it replaces. "
                f"Still unclaimed: {expected}."
            )

        return pairs


    @classmethod
    def _ingest_new_spritesheet(cls, vehicle, ctx: BuildContext) -> bool:
        """Stage the PNGs in the vehicle's ``new/`` drop folder for this build.

        One drop per spritesheet the candidate uses: its own `<Vehicle>.png`, plus any sheet a
        profile or livery names for itself. The published sheets stay untouched until the build
        succeeds: the staged copies become the sheets this build reads and normalises, and
        `_finalize_sprite_ingests` publishes them only after the GRF has been compiled.
        """
        if not vehicle.spritesheet_path:
            return False

        base_path = Path(vehicle.spritesheet_path)
        vehicle_folder = base_path.parent
        new_folder = vehicle_folder / "new"
        if not new_folder.is_dir():
            return False

        drops = sorted(
            path for path in new_folder.iterdir() if path.is_file() and path.suffix.lower() == ".png"
        )
        if not drops:
            return False

        targets = cls._ingest_targets(vehicle, drops)

        staging_folder = Path(ctx.nml_output_folder) / "ingest" / vehicle.identifier
        if staging_folder.exists():
            shutil.rmtree(staging_folder)
        staging_folder.mkdir(parents=True, exist_ok=True)

        for drop, sheet in targets:
            sheet_path = Path(sheet)
            staging_path = staging_folder / sheet_path.name
            shutil.copy2(drop, staging_path)

            if Path(sheet).resolve() == base_path.resolve():
                vehicle.spritesheet_override = str(staging_path)
            else:
                vehicle.spritesheet_overrides[str(sheet)] = str(staging_path)

            ctx.pending_sprite_ingests.append(
                {
                    "vehicle": vehicle,
                    "new_path": drop,
                    "staging_path": staging_path,
                    "ingested_path": vehicle_folder / "ingested" / sheet_path.name,
                    "base_path": sheet_path,
                }
            )
            logger.info(
                f"Staged new spritesheet '{drop}' as '{staging_path}' for "
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
        # A candidate can drop several sheets at once, so each folder is cleared once for the
        # whole candidate rather than once per sheet: clearing it per sheet would delete the
        # previous sheet's raw source.
        cleared_ingested: set[Path] = set()
        cleared_error: set[Path] = set()

        for ingest in ctx.pending_sprite_ingests:
            vehicle = ingest["vehicle"]
            if built_vehicles is not None and vehicle.identifier not in built_vehicles:
                error_folder = ingest["base_path"].parent / "error"
                error_folder.mkdir(parents=True, exist_ok=True)
                if error_folder not in cleared_error:
                    for stale in error_folder.glob("*.png"):
                        stale.unlink()
                    cleared_error.add(error_folder)
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
            if ingested_folder not in cleared_ingested:
                for stale in ingested_folder.glob("*.png"):
                    stale.unlink()
                cleared_ingested.add(ingested_folder)

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

        return successful - failed - set(getattr(ctx, "failed_units", set()))

