import logging

from Templates.Template import Template

from .PalettedImage import PalettedImage
from .Sprite import Sprite
from .Spriteset import Spriteset

logger = logging.getLogger(__name__)

MAX_SPRITES_PER_ROW = 8
MAX_NON_WHITE_ROW_GUTTER_PIXELS = 10
LEGACY_PURCHASE_MARKER_WIDTH = 36
LEGACY_PURCHASE_MARKER_RED = (255, 0, 0)
LEGACY_PURCHASE_MARKER_YELLOW = (255, 255, 0)
#: How far a marker pixel may sit from the marker's own colour and still count as one. A sheet
#: that is not already paletted reaches this through the palette stage's quantisation, which
#: lands the marker's exact red and yellow on the palette's nearest shades ((252,0,0) and
#: (252,252,0)), so an exact comparison never sees a marker at all. The same reach as the
#: gutters' white, which is what that staging does to a sheet's whites.
LEGACY_PURCHASE_MARKER_TOLERANCE = 3


class SpritesheetExtractor:
	"""Detects spriteset rows and sprite rectangles in an image, purely from pixel geometry.

	Rows and sprites are separated by gutters of white/near-white pixels. This class has
	no knowledge of variants or NML; it only produces raw `Spriteset`/`Sprite` geometry
	that the caller assigns to variants afterwards (see `Spritesheet.add_spriteset`).
	"""

	def __init__(self, filename: str, palette: list[int]):
		self.filename = filename

		image = PalettedImage.load(filename, palette)

		if image.image.mode not in ("P", "RGB"):
			raise ValueError(f"Unsupported image mode {image.image.mode!r} for {filename}")

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
		return PalettedImage.is_white(self._get_rgb(x, y))

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
		row_width = self._estimate_row_width(y_start)
		y = y_start
		while y < self.height:
			if self._is_legacy_purchase_marker(y, row_width):
				return y - y_start + 1
			if self._is_row_gutter(y, row_width):
				return y - y_start + 1
			y += 1
		return self.height - y_start

	def _estimate_row_width(self, y_start: int) -> int:
		"""Estimate the row's sprite width from its first scanline.

		Content outside this width may be notes or working art and must not prevent
		rows from being separated.
		"""
		for x in range(self.width - 1, -1, -1):
			if not self.is_gutter(x, y_start):
				return x + 1
		return self.width

	def _is_row_gutter(self, y: int, row_width: int) -> bool:
		non_white_pixels = sum(
			not self.is_gutter(x, y) for x in range(min(self.width, row_width))
		)
		return non_white_pixels <= MAX_NON_WHITE_ROW_GUTTER_PIXELS

	def _is_legacy_purchase_marker(self, y: int, row_width: int) -> bool:
		non_white = [
			x for x in range(min(self.width, row_width)) if not self.is_gutter(x, y)
		]
		if len(non_white) != LEGACY_PURCHASE_MARKER_WIDTH:
			return False

		if any(right != left + 1 for left, right in zip(non_white, non_white[1:])):
			return False

		colours = [self._get_rgb(x, y) for x in non_white]
		return (
			all(self._is_marker_colour(colour, LEGACY_PURCHASE_MARKER_RED) for colour in colours[:4])
			and all(self._is_marker_colour(colour, LEGACY_PURCHASE_MARKER_YELLOW) for colour in colours[4:24])
			and all(self._is_marker_colour(colour, LEGACY_PURCHASE_MARKER_RED) for colour in colours[24:])
		)

	@staticmethod
	def _is_marker_colour(colour: tuple[int, int, int], expected: tuple[int, int, int]) -> bool:
		"""True if a pixel is the marker's colour, or as near to it as the palette allows."""
		return all(
			abs(channel - target) <= LEGACY_PURCHASE_MARKER_TOLERANCE
			for channel, target in zip(colour, expected)
		)

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
			if self._is_legacy_purchase_marker(y, x_start + width):
				return max(1, y - y_start)
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
