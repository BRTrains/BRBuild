from __future__ import annotations

from dataclasses import dataclass

from PropertyCalculation.PowerTypeClassifier import PowerTypeClassifier
from Sprites.Spriteset import Spriteset
from Sprites.SpritesheetExtractor import SpritesheetExtractor
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
	override = _resolve("sprite_override", livery, profile, vehicle)
	exclude = _resolve("sprite_exclude", livery, profile, vehicle) or []

	if isinstance(exclude, int):
		exclude = [exclude]

	if override:
		pattern = list(override)
	else:
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
	only the confidently-identified rows. Doodles/notes/labels and anything else that
	doesn't match a known template are dropped rather than guessed at. Confirmed vehicle
	rows are then consumed from the sheet only as new (profile, livery) combinations are
	first requested, advancing an internal cursor.
	"""

	def __init__(self, vehicle: Vehicle, palette: list[int], definitions: list[TemplateDefinition]):
		if not vehicle.spritesheet_path:
			raise ValueError(f"Vehicle '{vehicle.identifier}' has no yaml_path to derive a spritesheet path from.")

		self.vehicle = vehicle
		self.is_ohle = PowerTypeClassifier.is_ohle(vehicle.power_type)

		v_type = vehicle.vehicle_type
		vehicle_type_str = v_type.name.lower() if hasattr(v_type, "name") else str(v_type).lower()

		raw_rows = SpritesheetExtractor(vehicle.spritesheet_path, palette).extract_spritesets()

		# Rows that match a known VEHICLE template, in sheet order, ready to be consumed per group.
		self.vehicle_rows: list[tuple[Spriteset, TemplateDefinition]] = []
		# The sheet's shared purchase-list icon, if a `tmpl_purchase`-like row was found (first one wins).
		self.purchase_row: tuple[Spriteset, TemplateDefinition] | None = None

		for row in raw_rows:
			match = classify_row(row.template.sprites, vehicle_type_str, definitions)
			if match is None:
				continue  # unrecognised row (doodle/note/label/etc) - ignore, not a spriteset

			if match.template_type == TemplateType.PURCHASE:
				if self.purchase_row is None:
					self.purchase_row = (row, match)
				continue

			self.vehicle_rows.append((row, match))

		if not self.vehicle_rows:
			raise ValueError(
				f"No recognised vehicle spritesets found in '{vehicle.spritesheet_path}' "
				f"(checked {len(raw_rows)} detected row(s))."
			)

		self.cursor = 0
		self._spritesets: dict[tuple[str, str], list[Spriteset]] = {}
		self._template_names: dict[tuple[str, str], list[str]] = {}
		self._lengths: dict[tuple[str, str], list[int]] = {}

	def get(self, profile: Profile, livery: Livery) -> tuple[list[Spriteset], list[str], list[int]]:
		"""Return the (spritesets, template_names, lengths) for a profile/livery combination.

		Consumes new confidently-identified rows from the sheet only the first time this
		combination is seen; `template_names` are the real NML template macro (e.g.
		`tmpl_train_6`) each corresponding spriteset was matched against, for the writer
		to call verbatim instead of guessing one from an articulation role. `lengths` are
		the matched templates' own `length` (1-8), for the per-variant `length` callback.
		"""
		key = (str(profile.identifier), str(livery.name))

		if key not in self._spritesets:
			group = _build_group(profile, livery, self.vehicle, self.is_ohle)
			group_slice = self.vehicle_rows[self.cursor:self.cursor + group.group_size]
			self.cursor += group.group_size

			if len(group_slice) < group.group_size:
				raise ValueError(
					f"Not enough recognised spritesets for group {key} in "
					f"'{self.vehicle.spritesheet_path}': needed {group.group_size}, "
					f"found {len(group_slice)} confidently-identified row(s)."
				)

			self._spritesets[key] = [group_slice[position - 1][0] for position in group.pattern]
			self._template_names[key] = [group_slice[position - 1][1].name for position in group.pattern]
			self._lengths[key] = [group_slice[position - 1][1].length for position in group.pattern]

		return self._spritesets[key], self._template_names[key], self._lengths[key]

	def get_purchase(self) -> tuple[Spriteset, str] | None:
		"""Return the (spriteset, template_name) for the sheet's shared purchase icon, if any.

		Assumes at most one purchase-list row per spritesheet, shared by every variant of
		this vehicle - matches the observed real spritesheet layout (one leading purchase
		row, followed by the vehicle's own content rows).
		"""
		if self.purchase_row is None:
			return None

		spriteset, definition = self.purchase_row
		return spriteset, definition.name
