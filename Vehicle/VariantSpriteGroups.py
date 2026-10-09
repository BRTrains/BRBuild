from __future__ import annotations

import io
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


def _same_path(one: str | Path | None, other: str | Path | None) -> bool:
	"""Whether two sheet paths name the same file."""
	if one is None or other is None:
		return False
	return Path(one).resolve() == Path(other).resolve()


def declared_sheet_path(livery: Livery, profile: Profile, vehicle: Vehicle) -> str | None:
	"""The spritesheet a group draws from, if it does not use the candidate's own sheet.

	`spritesheet` on a livery or profile keeps that group's drawings in a sheet of its own, so
	one profile of a candidate can be maintained without intermingling its rows with the rest.
	Resolution is livery, then profile, then vehicle like every other per-variant field; unset
	means the candidate's own `<Vehicle>.png`, which is the case for every existing project.

	During an ingest the published sheet is remapped to the copy staged out of `new/`, exactly
	as the vehicle's own sheet is, so the build reads and normalises one picture per sheet.
	"""
	declared = _resolve("spritesheet", livery, profile, vehicle)
	if declared is None:
		return None
	overrides = getattr(vehicle, "spritesheet_overrides", None) or {}
	return str(overrides.get(str(declared), declared))


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


#: A vehicle template is named `tmpl_<vehicle_type>_<length>[_<tags>]`, so a counterpart for
#: another feature carries the same length and tags under that feature's vehicle type.
TRAM_VEHICLE_TYPE = "tram"
ROAD_VEHICLE_FEATURE = "FEAT_ROADVEHS"


def tram_template_index(definitions: list[TemplateDefinition]) -> dict[tuple, str]:
	"""Index the tram templates by (length, tags), the key a train template is looked up with.

	The two sets are deliberately the same shape — same columns, same view boxes — and differ
	only in the offsets, so a train template's counterpart is the tram template with the same
	length and the same tags (`_old`, `_reversed`, `_tall`, ...).
	"""
	return {
		(definition.length, tuple(definition.variant_tags)): definition.name
		for definition in definitions
		if definition.template_type == TemplateType.VEHICLE
		and definition.vehicle_type == TRAM_VEHICLE_TYPE
	}


def road_vehicle_template_name(definition: TemplateDefinition, tram_templates: dict) -> str:
	"""The template a road vehicle is drawn with, given the one its sheet row matched.

	OpenTTD places a tram from the tram template's offsets, which differ from the train
	template's by up to 9px in the diagonal views, while the view boxes are identical. A row
	that matched a train template therefore needs no re-matching to be drawn as a tram: only
	the template name changes. Anything without a counterpart — a train template with no tram
	twin — keeps the template it matched.
	"""
	key = (definition.length, tuple(definition.variant_tags))
	return tram_templates.get(key, definition.name)


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
		# Road vehicles use the train-template geometry as their source artwork; the
		# allocator maps the matched train template to its tram counterpart when writing
		# the road-vehicle feature.
		if vehicle_type_str in ("road", "roadveh"):
			vehicle_type_str = "train"

		self._palette = palette
		#: The template definitions and vehicle type the detections were made with, needed again
		#: for any sheet a profile or livery names for itself.
		self._template_definitions = definitions
		self._vehicle_type_str = vehicle_type_str
		#: Recognised rows of each extra sheet, keyed by resolved path, with its own cursor.
		self._extra_pools: dict[str, dict] = {}
		#: The sheet each (profile, livery) group actually drew its rows from.
		self._sheet_paths: dict[tuple[str, str], str] = {}

		# The candidate's own sheet is optional: a candidate whose every profile names a
		# `spritesheet` of its own has no rows to detect there, and its coach rows may simply not
		# exist yet. Each sheet is read from the path the build actually uses, which is the copy
		# staged out of `new/` while that sheet is being ingested.
		self._own_sheet = str(vehicle.spritesheet_path)
		if Path(self._own_sheet).is_file():
			# Detecting rows is the build's most expensive step and answers the same question
			# for an unchanged sheet, so the result is cached beside the sheet and reused while
			# the sheet bytes, palette, template definitions and vehicle type all match.
			cache = SheetDetectionCache(
				self._own_sheet, palette, definitions, vehicle_type_str
			)
			rows = cache.load()
			if rows is None:
				extractor = SpritesheetExtractor(self._own_sheet, palette)
				rows = self._match_vehicle_rows(extractor, vehicle_type_str, definitions)
				cache.store(rows)
				self._image = extractor.image
			else:
				self._image = None

			self.vehicle_rows: list[tuple[Spriteset, TemplateDefinition]] = rows
		else:
			self._image = None
			self.vehicle_rows: list[tuple[Spriteset, TemplateDefinition]] = []

		# Rows are matched against the vehicle's own type, so a candidate authored as a train
		# matches train templates even where a profile is also emitted as a road vehicle. The
		# tram counterparts are indexed up front so those variants can be drawn with the right
		# offsets without re-matching anything (see `road_vehicle_template_name`).
		self._tram_templates = tram_template_index(definitions)

		self.cursor = 0
		self._assigned_rows: dict[tuple[str, str], list[tuple[Spriteset, TemplateDefinition]]] = {}
		self._spritesets: dict[tuple[str, str], list[Spriteset]] = {}
		self._template_names: dict[tuple[str, str], list[str]] = {}
		self._lengths: dict[tuple[str, str], list[int]] = {}
		self._definitions: dict[tuple[str, str], list[TemplateDefinition]] = {}
		self._patterns: dict[tuple[str, str], list[int]] = {}

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

	def get(self, profile: Profile, livery: Livery, vehicle_type=None) -> tuple[list[Spriteset], list[str], list[int]]:
		"""Return the (spritesets, template_names, lengths) for a profile/livery combination.

		Consumes new confidently-identified rows from the sheet only the first time this
		combination is seen; `template_names` are the real NML template macro (e.g.
		`tmpl_train_6`) each corresponding spriteset was matched against, for the writer
		to call verbatim instead of guessing one from an articulation role. `lengths` are
		the matched templates' own `length` (1-8), for the per-variant `length` callback.

		`vehicle_type` is the feature the variant is being emitted for. Rows are matched once
		per candidate against the vehicle's own type, so a variant emitted as a road vehicle
		names the tram counterpart of each matched template instead (`road_vehicle_template_name`)
		— same geometry, road placement. The rows themselves, and their positions, are
		unchanged, so both features share one set of sprites.

		A profile declaring `sprite_group: <profile identifier>` reuses the rows already
		assigned to that profile's matching livery instead of consuming its own, so two
		profiles that differ only in statistics (e.g. a unit whose service speed changed
		after a modification) need one set of drawings, not two. A livery declaring
		`sprite_group: <livery name>` does the same across the other axis: it reuses the
		rows of that livery in this profile, so one set of drawings can serve several
		liveries of one formation. The livery's statement wins where both are given.
		"""
		key = (str(profile.identifier), str(livery.name))

		if key not in self._spritesets:
			group = _build_group(profile, livery, self.vehicle, self.is_ohle)
			source = getattr(profile, "sprite_group", None)
			livery_source = getattr(livery, "sprite_group", None)

			if livery_source and str(livery_source).strip().lower() != str(livery.name).strip().lower():
				base_livery = self._source_livery(livery_source)
				group_slice = self._shared_livery_rows(profile, base_livery)
				# The shared rows keep the sheet the source group drew them from.
				self._record_sheet(
					key,
					getattr(self, "_sheet_paths", {}).get(
						(str(profile.identifier), str(base_livery.name)),
						self.vehicle.spritesheet_path,
					),
				)
			elif source and str(source) != str(profile.identifier):
				group_slice = self._shared_rows(profile, livery, source)
				# The shared rows keep the sheet the source group drew them from.
				self._record_sheet(
					key,
					getattr(self, "_sheet_paths", {}).get(
						(str(source), str(livery.name)), self.vehicle.spritesheet_path
					),
				)
			else:
				group_slice = self._take_rows(profile, livery, group.group_size)
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
			if not hasattr(self, "_patterns"):
				self._patterns = {}
			self._patterns[key] = list(group.pattern)

		names = self._template_names[key]
		if getattr(vehicle_type, "nml_feature", None) == ROAD_VEHICLE_FEATURE:
			names = [
				road_vehicle_template_name(definition, self._tram_templates)
				for definition in self._definitions[key]
			]

		return self._spritesets[key], names, self._lengths[key]

	def pattern_for(self, profile: Profile, livery: Livery) -> list[int]:
		"""Return the resolved sprite pattern for an already materialised group."""
		if not hasattr(self, "_patterns"):
			self._patterns = {}
		key = (str(profile.identifier), str(livery.name))
		if key not in self._patterns:
			self.get(profile, livery)
		return list(self._patterns[key])

	def _record_sheet(self, key: tuple[str, str], sheet_path: str) -> None:
		"""Remember which sheet a group's rows came from (see `sheet_for`)."""
		if not hasattr(self, "_sheet_paths"):
			self._sheet_paths = {}
		self._sheet_paths[key] = sheet_path

	def _take_rows(self, profile: Profile, livery: Livery, count: int) -> list:
		"""Take the next `count` recognised rows from the sheet this group draws from.

		A group using the candidate's own sheet consumes rows from it exactly as before; a group
		whose profile (or livery) names a `spritesheet` of its own consumes rows from that sheet,
		which keeps its own cursor. The sheet's identity is remembered per group so the purchase
		icon and the lighting overlays read the picture the rows actually live on.
		"""
		key = (str(profile.identifier), str(livery.name))
		sheet = declared_sheet_path(livery, profile, self.vehicle)

		if sheet is None or _same_path(sheet, self.vehicle.spritesheet_path):
			if not self.vehicle_rows:
				raise ValueError(
					f"'{self.vehicle.identifier}' has no spritesheet of its own at "
					f"'{self.vehicle.spritesheet_path}': give this profile a 'spritesheet' of "
					f"its own, or commit the candidate's own sheet."
				)
			group_slice = self.vehicle_rows[self.cursor:self.cursor + count]
			self.cursor += count
			self._record_sheet(key, self.vehicle.spritesheet_path)
			return group_slice

		pool = self._extra_pool(sheet)
		group_slice = pool["rows"][pool["cursor"]:pool["cursor"] + count]
		pool["cursor"] += count
		self._record_sheet(key, pool["path"])
		return group_slice

	def _extra_pool(self, sheet_path: str) -> dict:
		"""The recognised rows of a sheet a profile or livery names for itself.

		Detected through the same extractor, cache and template matching as the candidate's own
		sheet, so a standalone sheet is held to exactly the same contract and is just as cheap on
		a rebuild. Sheets load once each and are keyed by resolved path.
		"""
		path = Path(sheet_path)
		key = str(path.resolve())
		pool = self._extra_pools.get(key)
		if pool is not None:
			return pool

		if not path.is_file():
			raise ValueError(
				f"Spritesheet '{sheet_path}' does not exist: a profile or livery of "
				f"'{self.vehicle.identifier}' names it, so it must be committed beside the "
				f"candidate's own sheet."
			)

		cache = SheetDetectionCache(
			str(path), self._palette, self._template_definitions, self._vehicle_type_str
		)
		rows = cache.load()
		if rows is None:
			extractor = SpritesheetExtractor(str(path), self._palette)
			rows = self._match_vehicle_rows(
				extractor, self._vehicle_type_str, self._template_definitions
			)
			cache.store(rows)
			image = extractor.image
		else:
			image = None

		pool = {"path": str(path), "image": image, "rows": rows, "cursor": 0}
		self._extra_pools[key] = pool
		return pool

	def image_for(self, sheet_path: str | None):
		"""The image rows drawn from `sheet_path` live on: an extra sheet, or the candidate's own."""
		if sheet_path is None or _same_path(sheet_path, self.vehicle.spritesheet_path):
			if self._image is None:
				self._image = SpritesheetExtractor(self._own_sheet, self._palette).image
			return self._image
		pool = self._extra_pool(sheet_path)
		if pool["image"] is None:
			pool["image"] = SpritesheetExtractor(pool["path"], self._palette).image
		return pool["image"]

	def sheet_for(self, profile: Profile, livery: Livery) -> str:
		"""The sheet a group's rows live on, once the group has been resolved."""
		key = (str(profile.identifier), str(livery.name))
		return getattr(self, "_sheet_paths", {}).get(key, self.vehicle.spritesheet_path)

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

	def _source_livery(self, source: str) -> Livery:
		"""Return the livery a `sprite_group` names, or fail loudly."""
		base = next(
			(
				other
				for other in self.vehicle.liveries
				if str(other.name).strip().lower() == str(source).strip().lower()
			),
			None,
		)

		if base is None:
			raise ValueError(
				f"sprite_group '{source}' is not a livery of {self.vehicle.identifier}."
			)

		return base

	def _shared_livery_rows(self, profile: Profile, base: Livery) -> list:
		"""Return the rows assigned to another livery of this profile."""
		source_key = (str(profile.identifier), str(base.name))

		if source_key not in self._assigned_rows:
			# Resolve the source group so its rows exist, whichever order the iterator
			# asks for the two liveries in.
			self.get(profile, base)

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

		# A group drawing from a sheet of its own crops its cars out of that sheet.
		sheet = getattr(self, "_sheet_paths", {}).get(key)
		image = self._image if sheet is None else self.image_for(sheet)

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

			parts.append(image.crop((left, top, right, bottom)))

		# Units are bottom-aligned in the purchase icon.  The icon is only 13px tall,
		# so a taller west-view crop must be clipped from the top, not from the bottom:
		# pantographs and other less-important top detail may occupy the extra rows.
		blue_index = self._palette_index((0, 0, 255))
		purchase = Image.new("P", (128, 13), color=blue_index)
		purchase.putpalette(self._palette)
		x_cursor = 0

		for crop in parts:
			if x_cursor >= purchase.width:
				break

			visible_width = min(crop.width, purchase.width - x_cursor)
			visible_height = min(crop.height, purchase.height)
			source_top = crop.height - visible_height
			paste_y = purchase.height - visible_height
			purchase.paste(
				crop.crop(
					(0, source_top, visible_width, source_top + visible_height)
				),
				(x_cursor, paste_y),
			)
			x_cursor += crop.width

		path = Path(output_folder) / self._purchase_filename(spritesets)
		path.parent.mkdir(parents=True, exist_ok=True)
		self._write_if_changed(path, purchase)

		template = Template(
			name="generated_purchase",
			sprites=[Sprite(0, 0, 128, 13, -25, -8)],
		)
		return Spriteset("generated_purchase", str(path.resolve()), template), "tmpl_purchase"

	@staticmethod
	def _write_if_changed(path: Path, image: Image.Image) -> None:
		"""Write a generated sprite only when its bytes differ from the file on disk.

		The icon is otherwise rewritten on every build, which gives it a fresh mtime: nmlc
		keeps its encoded sprites in a `.png.cache` beside each image and drops any entry
		whose source file is newer, so rewriting an icon that did not change costs an
		encode for nothing. An identical icon is left completely alone.
		"""
		buffer = io.BytesIO()
		image.save(buffer, format="PNG")
		data = buffer.getvalue()

		try:
			if path.is_file() and path.read_bytes() == data:
				return
		except OSError:
			pass

		path.write_bytes(data)

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
