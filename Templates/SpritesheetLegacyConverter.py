from __future__ import annotations

import logging
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

	Pipeline: force the game palette, extract raw rows, keep only the rows that match a
	known template (dropping doodles/notes/labels), then rewrite the sheet containing just
	those rows in a clean canonical layout. The builder only ever points this at a staging
	copy of a sheet ingested from `new/`, and publishes the result after a successful build.
	"""

	def __init__(self, definitions: list[TemplateDefinition], palette: list[int]):
		self.palette = palette
		self.definitions = definitions

	def process(self, png_path: str, vehicle_type: str) -> list[Spriteset]:
		"""Convert a spritesheet in place, returning the rows recognised as real spritesets."""
		path = Path(png_path)
		if not path.is_file():
			raise FileNotFoundError(path)

		extractor = SpritesheetExtractor(str(path), self.palette)
		raw_rows = extractor.extract_spritesets()

		kept_rows = []
		kept = []
		for row in raw_rows:
			definition = classify_row(row.template.sprites, vehicle_type, self.definitions)
			if definition is not None and definition.template_type.value == "vehicle":
				kept_rows.append(row)
				kept.append((row, definition))
			else:
				logger.debug(f"Dropping unrecognised row at y={row.y} in '{path}' (no matching template)")

		if not kept_rows:
			logger.warning(f"No recognised template rows found in '{path}'; leaving the file unchanged.")
			return kept_rows

		cleaned = self._rebuild_clean_sheet(extractor, kept)
		cleaned.save(path)

		logger.info(f"Converted '{path}': kept {len(kept_rows)}/{len(raw_rows)} row(s)")
		return kept_rows

	def _rebuild_clean_sheet(self, extractor: SpritesheetExtractor, rows) -> Image.Image:
		"""Paste the recognised rows into the layout their templates describe.

		Each view is placed at *its template's own column and row height*, not at a cursor
		derived from the widths measured off the artist's sheet. The template is what the
		game reads, so a view that is 1px narrower or wider than its box (or drawn 1px off
		the box's column) would otherwise shift every later view in that row, and the boxes
		then read the 1px white separators as extra columns - which the player sees as a
		white line down one edge of those sprites.

		The art is cropped from wherever it actually sits and pasted at its box's top-left,
		so it fills the box rather than leaving a blank margin; the rest of the box is
		filled with the transparent blue, because white inside a box is opaque and would be
		drawn. The 1px gaps *between* boxes stay white, which is what keeps the sheet
		segmentable if it is ever ingested again.
		"""
		if not rows:
			blank = Image.new("P", (1, 1))
			blank.putpalette(self.palette)
			return blank

		row_heights = [
			max(box.height for box in definition.bounding_boxes) for _, definition in rows
		]
		row_widths = [
			max(box.left_x + box.width for box in definition.bounding_boxes)
			for _, definition in rows
		]

		out_width = max(row_widths)
		out_height = sum(row_heights) + (len(row_heights) - 1)

		out = Image.new("P", (out_width, out_height))
		out.putpalette(self.palette)

		white_index = self._white_index()
		out.paste(white_index, (0, 0, out_width, out_height))
		transparent_index = self._transparent_index()

		y_cursor = 0
		for (row, definition), row_height in zip(rows, row_heights):
			for index, box in enumerate(definition.bounding_boxes):
				# The box is the region the game reads; anything else inside it would be
				# drawn, so it starts transparent.
				out.paste(
					transparent_index,
					(box.left_x, y_cursor, box.left_x + box.width, y_cursor + box.height),
				)

				if index >= len(row.template.sprites):
					continue

				measured = row.template.sprites[index]
				left = row.x + measured.left_x
				top = row.y + measured.upper_y
				width = min(measured.width, box.width)
				height = min(measured.height, box.height)
				if width <= 0 or height <= 0:
					continue

				crop = extractor.image.crop((left, top, left + width, top + height))
				out.paste(crop, (box.left_x, y_cursor))
			y_cursor += row_height + 1

		return out

	def _white_index(self) -> int:
		"""Find the palette index that renders as white, falling back to 255 if absent."""
		for index in range(256):
			r, g, b = self.palette[index * 3:index * 3 + 3]
			if (r, g, b) == (255, 255, 255):
				return index
		return FALLBACK_WHITE_INDEX

	def _transparent_index(self) -> int:
		"""Find the palette index the sheets use for "nothing here".

		The family's sheets fill their backgrounds with pure blue and the game draws that
		as transparent, so it is what an unfilled part of a view box must be.
		"""
		for index in range(256):
			r, g, b = self.palette[index * 3:index * 3 + 3]
			if (r, g, b) == (0, 0, 255):
				return index
		return 0
