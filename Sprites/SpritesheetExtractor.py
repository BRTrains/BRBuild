import logging

from Templates.Template import Template

from .PalettedImage import PalettedImage
from .Sprite import Sprite
from .Spriteset import Spriteset

logger = logging.getLogger(__name__)

NEAR_WHITE_TOLERANCE = 3  # gutter pixels are white or near-white
MAX_SPRITES_PER_ROW = 8


class SpritesheetExtractor:
	"""Detects spriteset rows and sprite rectangles in an image, purely from pixel geometry.

	Rows and sprites are separated by gutters of white/near-white pixels. This class has
	no knowledge of variants or NML; it only produces raw `Spriteset`/`Sprite` geometry
	that the caller assigns to variants afterwards (see `Spritesheet.add_spriteset`).
	"""

	def __init__(self, filename: str, palette: list[int]):
		self.filename = filename

		image = PalettedImage.load(filename, palette)

		if image.image.mode == "PA":
			raise ValueError(
				f"Unsupported paletted+alpha mode 'PA' in {filename}. "
				"8bpp OpenTTD sprites must not contain alpha."
			)

		if image.image.mode not in ("P", "RGB", "RGBA"):
			raise ValueError(f"Unsupported image mode {image.image.mode!r} for {filename}")

		if image.image.mode == "RGBA":
			image.image = image.image.convert("RGB")

		if not image.is_using_palette():
			image.set_palette()

		self.image = image.image
		self.width, self.height = self.image.size
		self.pixels = self.image.load()

		raw_palette = self.image.getpalette() or []
		self._palette_rgb = [
			tuple(raw_palette[i:i + 3]) for i in range(0, len(raw_palette), 3)
		]

	def _get_rgb(self, x: int, y: int) -> tuple[int, int, int]:
		"""Return the pixel at (x, y) as an RGB tuple via the enforced palette table."""
		idx = self.pixels[x, y]
		if idx >= len(self._palette_rgb):
			return (0, 0, 0)
		return self._palette_rgb[idx]

	def is_gutter(self, x: int, y: int) -> bool:
		"""A gutter pixel is white or near-white, marking gaps between sprites/rows."""
		r, g, b = self._get_rgb(x, y)
		return max(abs(r - 255), abs(g - 255), abs(b - 255)) <= NEAR_WHITE_TOLERANCE

	# -- row (spriteset) detection -----------------------------------------

	def _detect_rows(self) -> list[int]:
		rows = []
		y = 0

		while y < self.height:
			if not self.is_gutter(0, y):
				rows.append(y)
				y += max(1, self._estimate_row_height(y))
			else:
				y += 1

		return rows

	def _estimate_row_height(self, y_start: int) -> int:
		y = y_start
		while y < self.height:
			if self._is_full_gutter_row(y):
				return y - y_start + 1
			y += 1
		return self.height - y_start

	def _is_full_gutter_row(self, y: int) -> bool:
		return all(self.is_gutter(x, y) for x in range(self.width))

	# -- sprite detection within a row --------------------------------------

	def _find_sprites_in_row(self, y_start: int) -> list[tuple[int, int, int, int]]:
		"""Return (x, y, width, height) bounding boxes for sprites in this row."""
		bboxes = []
		x = 0

		while x < self.width:
			while x < self.width and self.is_gutter(x, y_start):
				x += 1
			if x >= self.width:
				break

			x0 = x
			width = self._estimate_sprite_width(x0, y_start)
			height = self._estimate_sprite_height(x0, y_start, width)
			bboxes.append((x0, y_start, width, height))

			x = x0 + width + 1

			if len(bboxes) >= MAX_SPRITES_PER_ROW:
				break

		return bboxes

	def _estimate_sprite_width(self, x_start: int, y_start: int) -> int:
		y_end = min(self.height, y_start + self._estimate_row_height(y_start))

		x = x_start
		while x < self.width and not self._is_full_gutter_col(x, y_start, y_end):
			x += 1

		return max(1, x - x_start)

	def _estimate_sprite_height(self, x_start: int, y_start: int, width: int) -> int:
		y = y_start
		while y < self.height:
			if self._is_full_gutter_row_segment(y, x_start, x_start + width):
				return max(1, y - y_start)
			y += 1
		return max(1, self.height - y_start)

	def _is_full_gutter_col(self, x: int, y_start: int, y_end: int) -> bool:
		return all(self.is_gutter(x, y) for y in range(y_start, y_end))

	def _is_full_gutter_row_segment(self, y: int, x_start: int, x_end: int) -> bool:
		return all(self.is_gutter(x, y) for x in range(x_start, x_end))

	# -- spriteset construction ----------------------------------------------

	def extract_spritesets(self) -> list[Spriteset]:
		"""Detect rows and the sprites within them, returning one `Spriteset` per row.

		TODO: rows are expected to have 4 or 8 views; a single-view row is likely a legacy
		purchase-sprite remnant and other counts may be doodles/notes, not real content.
		This isn't filtered yet - legacy template detection is a separate future task.
		"""
		spritesets = []

		for row_index, row_y in enumerate(self._detect_rows()):
			bboxes = self._find_sprites_in_row(row_y)
			if not bboxes or len(bboxes) > MAX_SPRITES_PER_ROW:
				continue

			row_x = bboxes[0][0]
			sprites = [
				Sprite(
					left_x=x - row_x,
					upper_y=y - row_y,
					width=width,
					height=height,
					offset_x=0,
					offset_y=0,
				)
				for x, y, width, height in bboxes
			]

			template = Template(name=f"row_{row_index}", sprites=sprites)
			spritesets.append(
				Spriteset(
					name=f"spriteset_y{row_y}",
					file=self.filename,
					template=template,
					x=row_x,
					y=row_y,
				)
			)

		logger.debug(f"Extracted {len(spritesets)} spriteset row(s) from {self.filename}")
		return spritesets
