from dataclasses import dataclass, field

from .PalettedImage import PalettedImage
from .Spriteset import Spriteset
from .SpritesheetExtractor import SpritesheetExtractor


@dataclass
class Spritesheet:
	"""An image file containing the spritesets (and thus sprites) for one or more variants."""

	file: str
	spritesets: dict[str | None, list[Spriteset]] = field(default_factory=dict)

	@classmethod
	def extract(cls, filename: str, palette: list[int]) -> "Spritesheet":
		"""Load an image and detect its spritesets purely from pixel geometry.

		The returned sheet's spritesets are not yet assigned to a variant; use
		`add_spriteset` (or re-key `spritesets`) once the caller knows which
		variant each detected row belongs to.
		"""
		sheet = cls(file=filename)
		for spriteset in SpritesheetExtractor(filename, palette).extract_spritesets():
			sheet.spritesets.setdefault(None, []).append(spriteset)
		return sheet

	def add_spriteset(self, variant_identifier: str | None, spriteset: Spriteset):
		"""Register a spriteset drawn from this spritesheet under its owning variant."""
		if spriteset.file != self.file:
			raise ValueError(
				f"Spriteset '{spriteset.name}' belongs to file '{spriteset.file}', "
				f"not '{self.file}'"
			)

		self.spritesets.setdefault(variant_identifier, []).append(spriteset)

	def spritesets_for_variant(self, variant_identifier: str | None) -> list[Spriteset]:
		"""Return the spritesets registered for a given variant."""
		return self.spritesets.get(variant_identifier, [])

	@property
	def variants(self) -> list[str | None]:
		"""Return the identifiers of every variant with spritesets in this spritesheet."""
		return list(self.spritesets.keys())

	def all_spritesets(self) -> list[Spriteset]:
		"""Return a flat list of every spriteset in this spritesheet, across all variants."""
		return [spriteset for spritesets in self.spritesets.values() for spriteset in spritesets]

	def validate_bounds(self, palette):
		"""Ensure every sprite rectangle of every spriteset fits within the image bounds."""
		image = PalettedImage.load(self.file, palette)
		width, height = image.image.size

		for spriteset in self.all_spritesets():
			for sprite in spriteset.template.sprites:
				left = spriteset.x + sprite.left_x
				upper = spriteset.y + sprite.upper_y
				right = left + sprite.width
				lower = upper + sprite.height

				if left < 0 or upper < 0 or right > width or lower > height:
					raise ValueError(
						f"Sprite in spriteset '{spriteset.name}' ({left}, {upper}, {right}, {lower}) "
						f"exceeds bounds of '{self.file}' ({width}x{height})"
					)

