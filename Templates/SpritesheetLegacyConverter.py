from __future__ import annotations

import logging
import shutil
from pathlib import Path

from PIL import Image

from Sprites.Spriteset import Spriteset
from Sprites.SpritesheetExtractor import SpritesheetExtractor

from .TemplateDefinition import TemplateDefinition
from .TemplateMatcher import classify_row

logger = logging.getLogger(__name__)

FALLBACK_WHITE_INDEX = 255


class SpritesheetLegacyConverter:
	"""Normalises a vehicle's spritesheet down to only its recognised template rows.

	Pipeline: archive the pristine original in an `original/` subfolder (once), force the game palette, extract raw
	rows, keep only the rows that match a known template (dropping doodles/notes/labels),
	then rewrite the sheet containing just those rows in a clean canonical layout.
	"""

	def __init__(self, definitions: list[TemplateDefinition], palette: list[int]):
		self.palette = palette
		self.definitions = definitions

	def process(self, png_path: str, vehicle_type: str) -> list[Spriteset]:
		"""Convert a spritesheet in place, returning the rows recognised as real spritesets."""
		path = Path(png_path)
		if not path.is_file():
			raise FileNotFoundError(path)

		self._archive(path)

		extractor = SpritesheetExtractor(str(path), self.palette)
		raw_rows = extractor.extract_spritesets()

		kept_rows = []
		for row in raw_rows:
			definition = classify_row(row.template.sprites, vehicle_type, self.definitions)
			if definition is not None and definition.template_type.value == "vehicle":
				kept_rows.append(row)
			else:
				logger.debug(f"Dropping unrecognised row at y={row.y} in '{path}' (no matching template)")

		if not kept_rows:
			logger.warning(f"No recognised template rows found in '{path}'; leaving the file unchanged.")
			return kept_rows

		cleaned = self._rebuild_clean_sheet(extractor, kept_rows)
		cleaned.save(path)

		logger.info(f"Converted '{path}': kept {len(kept_rows)}/{len(raw_rows)} row(s)")
		return kept_rows

	def _archive(self, path: Path):
		"""Archive the pristine original once in a sibling `original/` folder."""
		original_folder = path.parent / "original"
		original_path = original_folder / path.name
		legacy_path = path.with_name(f"{path.stem}_original.png")

		if original_path.exists():
			if legacy_path.exists():
				legacy_path.unlink()
			return

		original_folder.mkdir(parents=True, exist_ok=True)
		if legacy_path.exists():
			shutil.move(legacy_path, original_path)
			logger.debug(f"Migrated legacy original backup to '{original_path}'")
		else:
			shutil.copy2(path, original_path)
			logger.debug(f"Archived pristine original to '{original_path}'")

	def _rebuild_clean_sheet(self, extractor: SpritesheetExtractor, rows: list[Spriteset]) -> Image.Image:
		"""Paste only the recognised rows into a new sheet: one row per spriteset,
		1px white gaps between sprites and between rows."""
		if not rows:
			blank = Image.new("P", (1, 1))
			blank.putpalette(self.palette)
			return blank

		row_heights = [max(view.height for view in row.template.sprites) for row in rows]
		row_widths = [
			sum(view.width for view in row.template.sprites) + (len(row.template.sprites) - 1)
			for row in rows
		]

		out_width = max(row_widths)
		out_height = sum(row_heights) + (len(row_heights) - 1)

		out = Image.new("P", (out_width, out_height))
		out.putpalette(self.palette)

		white_index = self._white_index()
		out.paste(white_index, (0, 0, out_width, out_height))

		y_cursor = 0
		for row, row_height in zip(rows, row_heights):
			x_cursor = 0
			for view in row.template.sprites:
				left = row.x + view.left_x
				upper = row.y + view.upper_y
				crop = extractor.image.crop((left, upper, left + view.width, upper + view.height))
				out.paste(crop, (x_cursor, y_cursor))
				x_cursor += view.width + 1
			y_cursor += row_height + 1

		return out

	def _white_index(self) -> int:
		"""Find the palette index that renders as white, falling back to 255 if absent."""
		for index in range(256):
			r, g, b = self.palette[index * 3:index * 3 + 3]
			if (r, g, b) == (255, 255, 255):
				return index
		return FALLBACK_WHITE_INDEX
