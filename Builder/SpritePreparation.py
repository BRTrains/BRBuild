"""Prepare spritesheets and sprite allocators for candidate processing."""

import hashlib
import json
import logging
import shutil
from pathlib import Path

from Sprites.PalettedImage import PalettedImage
from Templates.SpritesheetLegacyConverter import SpritesheetLegacyConverter
from Vehicle import VehicleSpriteAllocator
from .BuildContext import BuildContext

PALETTE_STAGE_CACHE_VERSION = 2
logger = logging.getLogger(__name__)


class SpritePreparation:
    """Own palette staging, normalization, and allocator construction."""

    def __init__(self, builder):
        self.builder = builder

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
            return VehicleSpriteAllocator(vehicle, ctx.palette, self.builder._get_template_definitions(ctx))
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
        for declared in self.builder._declared_sheets(vehicle):
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
        definitions = self.builder._get_template_definitions(ctx)
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

