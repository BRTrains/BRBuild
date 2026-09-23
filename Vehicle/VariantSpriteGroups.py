from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from PIL import Image

from PropertyCalculation.PowerTypeClassifier import PowerTypeClassifier
from Sprites.SheetDetectionCache import SheetDetectionCache
from Sprites.Sprite import Sprite
from Sprites.Spriteset import Spriteset
from Sprites.SpritesheetExtractor import SpritesheetExtractor
from Templates.Template import Template
from Templates.TemplateDefinition import TemplateDefinition
from Templates.TemplateMatcher import classify_row
from Templates.TemplateType import TemplateType

from .Livery import Livery
from .Profile import Profile
from .SpriteSizeTemplate import standard_pattern
from .Vehicle import Vehicle


@dataclass
class SpriteGroup:
	"""The ordered spriteset pattern needed for one profile/livery combination."""

	profile: Profile
	livery: Livery
	pattern: list[int]
	group_size: int

	@property
	def key(self) -> tuple[str, str]:
		"""Identifies this group independently of vehicle type, which doesn't affect sprites."""
		return (str(self.profile.identifier), str(self.livery.name))



def _resolve(attr: str, livery: Livery, profile: Profile, vehicle: Vehicle):
	"""Resolve a sprite-layout attribute, preferring livery, then profile, then vehicle."""
	for obj in (livery, profile, vehicle):
		value = getattr(obj, attr, None)
		if value is not None:
			return value
	return None


def _resolve_pattern(livery: Livery, profile: Profile, vehicle: Vehicle) -> list[int] | None:
	"""Resolve an explicit sprite pattern, falling back to the vehicle count."""
	for obj in (livery, profile, vehicle):
		override = getattr(obj, "sprite_override", None)
		if override:
			return list(override)

		num_vehicles = getattr(obj, "num_vehicles", None)
		if num_vehicles is not None:
			return list(range(1, int(num_vehicles) + 1))

	return None


def _liveries_for_profile(profile: Profile, liveries: list[Livery]) -> list[Livery]:
	"""Return liveries that apply to a profile, in their configured order.

	A livery with no `profiles` restriction applies to every profile.
	"""
	matching = []
	for livery in liveries:
		allowed = livery.profiles
		if not allowed or str(profile.identifier).lower() in (str(p).lower() for p in allowed):
			matching.append(livery)
	return matching


def _build_group(profile: Profile, livery: Livery, vehicle: Vehicle, is_ohle: bool) -> SpriteGroup:
	"""Resolve a single profile/livery combination's pattern and raw spriteset requirement."""
	size = _resolve("size", livery, profile, vehicle)
	pattern = _resolve_pattern(livery, profile, vehicle)
	exclude = _resolve("sprite_exclude", livery, profile, vehicle) or []

	if isinstance(exclude, int):
		exclude = [exclude]

	if pattern is None:
		pattern = standard_pattern(int(size) if size is not None else 1, is_ohle)

	used = set(pattern) | set(exclude)
	group_size = max(used) if used else 0

	return SpriteGroup(profile=profile, livery=livery, pattern=pattern, group_size=group_size)


def build_sprite_groups(vehicle: Vehicle) -> list[SpriteGroup]:
	"""Build the ordered list of sprite groups for a vehicle's profile/livery combinations.

	Mirrors the profile-outer, livery-inner order `VariantIterator` produces variants in,
	but collapses vehicle type since the sprite layout doesn't vary by feature target.
	"""
	is_ohle = PowerTypeClassifier.is_ohle(vehicle.power_type)
	return [
		_build_group(profile, livery, vehicle, is_ohle)
		for profile in vehicle.profiles
		for livery in _liveries_for_profile(profile, vehicle.liveries)
	]


class VehicleSpriteAllocator:
	"""Lazily resolves and caches sprite groups for a vehicle as variants are iterated.

	Extracts the vehicle's spritesheet once and classifies every detected row against the
	project's known NML templates (see `Templates.TemplateMatcher.classify_row`), keeping
	only the confidently-identified rows. Detection is the expensive part of a build and is
	reused from the sheet's own cache (`Sprites.SheetDetectionCache`) whenever the sheet,
	palette, template definitions and vehicle type are unchanged. Doodles/notes/labels and
	anything else that doesn't match a known template are dropped rather than guessed at.
	Confirmed vehicle rows are then consumed from the sheet only as new (profile, livery)
	combinations are first requested, advancing an internal cursor.
	"""

	def __init__(self, vehicle: Vehicle, palette: list[int], definitions: list[TemplateDefinition]):
		if not vehicle.spritesheet_path:
			raise ValueError(f"Vehicle '{vehicle.identifier}' has no yaml_path to derive a spritesheet path from.")

		self.vehicle = vehicle
		self.is_ohle = PowerTypeClassifier.is_ohle(vehicle.power_type)

		v_type = vehicle.vehicle_type
		vehicle_type_str = v_type.name.lower() if hasattr(v_type, "name") else str(v_type).lower()

		extractor = SpritesheetExtractor(vehicle.spritesheet_path, palette)
		self._image = extractor.image
		self._palette = palette

		# Detecting rows is the build's most expensive step and answers the same question
		# for an unchanged sheet, so the result is cached beside the sheet and reused while
		# the sheet bytes, palette, template definitions and vehicle type all match.
		cache = SheetDetectionCache(vehicle.spritesheet_path, palette, definitions, vehicle_type_str)
		rows = cache.load()
		if rows is None:
			rows = self._match_vehicle_rows(extractor, vehicle_type_str, definitions)
			cache.store(rows)

		self.vehicle_rows: list[tuple[Spriteset, TemplateDefinition]] = rows

		self.cursor = 0
		self._assigned_rows: dict[tuple[str, str], list[tuple[Spriteset, TemplateDefinition]]] = {}
		self._spritesets: dict[tuple[str, str], list[Spriteset]] = {}
		self._template_names: dict[tuple[str, str], list[str]] = {}
		self._lengths: dict[tuple[str, str], list[int]] = {}
		self._definitions: dict[tuple[str, str], list[TemplateDefinition]] = {}

	@staticmethod
	def _match_vehicle_rows(extractor: SpritesheetExtractor, vehicle_type_str: str, definitions: list[TemplateDefinition]):
		"""Detect the sheet's rows and keep the ones that match a known vehicle template.

		Rows that match nothing (doodles, notes, labels) and legacy purchase remnants are
		dropped rather than guessed at. This is the expensive path: its result is what
		`SheetDetectionCache` stores, so an unchanged sheet never reaches it again.
		"""
		raw_rows = extractor.extract_spritesets()

		# Rows that match a known VEHICLE template, in sheet order, ready to be consumed per group.
		vehicle_rows: list[tuple[Spriteset, TemplateDefinition]] = []
		for row in raw_rows:
			match = classify_row(row.template.sprites, vehicle_type_str, definitions)
			if match is None:
				continue  # unrecognised row (doodle/note/label/etc) - ignore, not a spriteset

			if match.template_type == TemplateType.PURCHASE:
				continue

			vehicle_rows.append((row, match))

		if not vehicle_rows:
			raise ValueError(
				f"No recognised vehicle spritesets found in '{extractor.filename}' "
				f"(checked {len(raw_rows)} detected row(s))."
			)

		return vehicle_rows

	def get(self, profile: Profile, livery: Livery) -> tuple[list[Spriteset], list[str], list[int]]:
		"""Return the (spritesets, template_names, lengths) for a profile/livery combination.

		Consumes new confidently-identified rows from the sheet only the first time this
		combination is seen; `template_names` are the real NML template macro (e.g.
		`tmpl_train_6`) each corresponding spriteset was matched against, for the writer
		to call verbatim instead of guessing one from an articulation role. `lengths` are
		the matched templates' own `length` (1-8), for the per-variant `length` callback.

		A profile declaring `sprite_group: <profile identifier>` reuses the rows already
		assigned to that profile's matching livery instead of consuming its own, so two
		profiles that differ only in statistics (e.g. a unit whose service speed changed
		after a modification) need one set of drawings, not two.
		"""
		key = (str(profile.identifier), str(livery.name))

		if key not in self._spritesets:
			group = _build_group(profile, livery, self.vehicle, self.is_ohle)
			source = getattr(profile, "sprite_group", None)
			if source and str(source) != str(profile.identifier):
				group_slice = self._shared_rows(profile, livery, source)
			else:
				group_slice = self.vehicle_rows[self.cursor:self.cursor + group.group_size]
				self.cursor += group.group_size
				self._assigned_rows[key] = group_slice

			if len(group_slice) < group.group_size:
				raise ValueError(
					f"Not enough recognised spritesets for group {key} in "
					f"'{self.vehicle.spritesheet_path}': needed {group.group_size}, "
					f"found {len(group_slice)} confidently-identified row(s)."
				)

			self._spritesets[key] = [group_slice[position - 1][0] for position in group.pattern]
			self._template_names[key] = [group_slice[position - 1][1].name for position in group.pattern]
			self._lengths[key] = [group_slice[position - 1][1].length for position in group.pattern]
			self._definitions[key] = [group_slice[position - 1][1] for position in group.pattern]

		return self._spritesets[key], self._template_names[key], self._lengths[key]

	def _shared_rows(self, profile: Profile, livery: Livery, source: str) -> list:
		"""Return the rows assigned to the profile named by this profile's `sprite_group`."""
		source_key = (str(source), str(livery.name))

		if source_key not in self._assigned_rows:
			base = next(
				(
					other
					for other in self.vehicle.profiles
					if str(other.identifier) == str(source)
				),
				None,
			)
			if base is None:
				raise ValueError(
					f"'{profile.identifier}' declares sprite_group '{source}', which is not a "
					f"profile of {self.vehicle.identifier}."
				)
			# Resolve the source group so its rows exist, whichever order the iterator
			# asks for the two profiles in.
			self.get(base, livery)

		return self._assigned_rows[source_key]

	def get_purchase(
		self,
		profile: Profile,
		livery: Livery,
		output_folder: str,
	) -> tuple[Spriteset, str] | None:
		"""Build a 128x13 purchase sprite from the west view of each vehicle part.

		Each car is cropped to its template's own west-view box, never to the measured
		content box, because the template is what the emitted spriteset tells OpenTTD to
		read. A stray pale line just below a car (a leftover of the artist's row edge,
		which is not near-white and so counts as content) otherwise inflates the measured
		box by a row and the icon gains a visible white line under that car.

		Cars are then placed on a common bottom/baseline, not all at the top of the icon:
		units are bottom-aligned in the game and any extra template height is top padding
		(for example, a pantograph). Pasting every crop at row 0 makes parts drawn against
		different templates (a 13px box whose art sits one row down, against a 12px box
		whose art starts at the top) sit a row apart in the icon while looking aligned in
		the consist.
		"""
		key = (str(profile.identifier), str(livery.name))
		spritesets = self._spritesets.get(key) or []
		definitions = self._definitions.get(key) or []
		if not spritesets:
			return None

		parts = []
		for index, spriteset in enumerate(spritesets):
			views = spriteset.template.sprites
			if len(views) <= 6:
				return None

			box = None
			definition = definitions[index] if index < len(definitions) else None
			if definition is not None and len(definition.bounding_boxes) > 6:
				box = definition.bounding_boxes[6]

			view = views[6]
			left = spriteset.x + view.left_x
			top = spriteset.y + view.upper_y
			right = left + view.width
			bottom = top + view.height

			if box is not None:
				right = min(right, spriteset.x + box.left_x + box.width)
				bottom = min(bottom, spriteset.y + box.upper_y + box.height)

			parts.append(self._image.crop((left, top, right, bottom)))

		# Units are bottom-aligned: the deepest crop sits on the icon's bottom row and
		# the rest keep their extra height as padding above, which is what the game does
		# with a view box that is taller than a neighbour's.
		baseline = max(crop.height for crop in parts)

		blue_index = self._palette_index((0, 0, 255))
		purchase = Image.new("P", (128, 13), color=blue_index)
		purchase.putpalette(self._palette)
		x_cursor = 0

		for crop in parts:
			if x_cursor >= purchase.width:
				break

			paste_y = baseline - crop.height
			visible_width = min(crop.width, purchase.width - x_cursor)
			visible_height = min(crop.height, purchase.height - paste_y)
			if visible_height > 0:
				purchase.paste(
					crop.crop((0, 0, visible_width, visible_height)), (x_cursor, paste_y)
				)
			x_cursor += crop.width

		path = Path(output_folder) / self._purchase_filename(spritesets)
		path.parent.mkdir(parents=True, exist_ok=True)
		purchase.save(path)

		template = Template(
			name="generated_purchase",
			sprites=[Sprite(0, 0, 128, 13, -25, -8)],
		)
		return Spriteset("generated_purchase", str(path.resolve()), template), "tmpl_purchase"

	def _palette_index(self, colour: tuple[int, int, int]) -> int:
		for index in range(256):
			if tuple(self._palette[index * 3:index * 3 + 3]) == colour:
				return index
		raise ValueError(f"Colour {colour} is missing from the configured palette")

	def _purchase_filename(self, spritesets: list[Spriteset]) -> str:
		parts = [self.vehicle.identifier]
		for spriteset in spritesets:
			parts.append(f"{Path(spriteset.file).stem}_{spriteset.y}")
		return "purchase_" + re.sub(r"[^a-zA-Z0-9_.-]+", "_", "_".join(parts)) + ".png"
