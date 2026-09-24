"""Lighting overlays: work out which pixels of a train drawing carry its lamps, and emit the
overlay sprite that shows them in the opposite running state.

A lamp is a bright pixel (white or a pale yellow) that is *not* bright in the same place on the
counterpart view or drawing: the artist draws a headlight on the drawing whose end leads, and the
matching tail lamp on the drawing of the other end. The overlay paints the counterpart's own value
there, so the shade is reciprocated rather than replaced, and it is drawn as a second sprite layer on
top of the vehicle (see `NmlWriter.NmlVariantWriter`).

Rules in force (agreed with Jon, 2026-09-24):

- candidates are searched brightest first, and only a cluster's brightest shade counts as a lamp;
- at most `MAX_LAMPS_PER_VIEW` lamp pixels are automated in one view — a double headlight is two
  pixels a side plus a centre repeater pair;
- a multiple unit pairs the drawing at its first consist position with the one at its last (its rear
  unit); a single-unit vehicle pairs a view with the view four along inside its own drawing;
- end-on views (N and S) must be mirror-symmetric about the centreline apart from a lone centre
  pixel, otherwise the unit needs manual work;
- anything not clearly identified is flagged and left alone.

Detection is cached beside the sheet in `<sheet>.lightcache.json`, keyed by the sheet bytes, the
palette, the template geometry, the rules version and the pairings it was asked about, so a rebuild
with unchanged inputs does no pixel work at all.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

#: Lamp shades, brightest first. A lamp uses a lighter shade than the livery around it.
LIT_ORDER = (0x0F, 0xA1, 0x45, 0x34, 0x44)
LIT = frozenset(LIT_ORDER)

#: Everything the sheets use for lit lamps, including the dimmer whites and pale yellows. A pixel
#: whose counterpart is any of these has not changed state and is therefore not a lamp.
WHITE = frozenset({0x0F, 0x0E, 0x0D, 0x45, 0x44, 0x34, 0xA1})

TRANSPARENT = 0x00

#: A double headlight is two pixels a side and a centre repeater adds a pair.
MAX_LAMPS_PER_VIEW = 6

#: The brightest reds a tail lamp is drawn in. Deliberately not a shade *search*: the trailing-only
#: rule below looks for these in the end-on views only, where a livery's own red runs in strokes.
TRAILING_LAMP_RED = frozenset({0xB6, 0xB7})

#: The shade a tail lamp takes when the train drives backwards, which is what the trailing-only
#: overlay paints: the same lamp, in the state the ordinary pair-based rule would have found.
TRAILING_LAMP_LIT = 0x0F

#: Bump when the rules above change, so every cache is re-derived.
RULES_VERSION = 3

#: End-on views, where lamps are mirror-symmetric about the box centreline.
END_ON_VIEWS = (0, 4)

#: A variant's `lighting` setting, accepted at vehicle, profile and livery level (livery wins):
#: `auto` detects and fills an unreadable livery in from its siblings, `exact` trusts only what the
#: artwork itself shows (the manual override for a wrong guess), `none` emits no layer at all.
LIGHTING_AUTO = "auto"
LIGHTING_EXACT = "exact"
LIGHTING_NONE = "none"
LIGHTING_SETTINGS = (LIGHTING_AUTO, LIGHTING_EXACT, LIGHTING_NONE)

#: Overlay and transparency sheets are generated build data, written next to the purchase icons.
OVERLAY_SUFFIX = "_lights.png"
TRANSPARENT_SUFFIX = "_transparent.png"


@dataclass(frozen=True)
class Part:
	"""One articulated part of a variant: the sheet row it draws, and its view boxes."""

	row_y: int
	template_name: str
	boxes: tuple[tuple[int, int, int, int], ...]


@dataclass
class Detection:
	"""Lamp pixels found for one set of pairings, plus whatever could not be automated."""

	pixels: dict[tuple[int, int], int] = field(default_factory=dict)
	rows: set[int] = field(default_factory=set)
	flags: list[str] = field(default_factory=list)
	pairs: int = 0
	rejected: int = 0
	view_mapping: str | None = None
	#: The variant identifier whose lamps these were assumed from, when the drawing itself told us
	#: nothing and a sibling livery on the same sheet and template was taken as the pattern.
	assumed_from: str | None = None

	def add(self, other: "Detection") -> None:
		for key, value in other.pixels.items():
			self.pixels.setdefault(key, value)
		self.rows |= other.rows
		self.flags.extend(flag for flag in other.flags if flag not in self.flags)
		self.pairs += other.pairs
		self.rejected += other.rejected
		self.view_mapping = self.view_mapping or other.view_mapping
		self.assumed_from = self.assumed_from or other.assumed_from

	def serialise(self) -> dict:
		return {
			"pixels": [[x, y, value] for (x, y), value in sorted(self.pixels.items())],
			"rows": sorted(self.rows),
			"flags": sorted(self.flags),
			"pairs": self.pairs,
			"rejected": self.rejected,
			"view_mapping": self.view_mapping,
			"assumed_from": self.assumed_from,
		}

	@classmethod
	def deserialise(cls, payload: dict) -> "Detection":
		return cls(
			pixels={(int(x), int(y)): int(value) for x, y, value in payload.get("pixels", [])},
			rows={int(row) for row in payload.get("rows", [])},
			flags=list(payload.get("flags", [])),
			pairs=int(payload.get("pairs", 0)),
			rejected=int(payload.get("rejected", 0)),
			view_mapping=payload.get("view_mapping"),
			assumed_from=payload.get("assumed_from"),
		)


def boxes_of(spriteset) -> tuple[tuple[int, int, int, int], ...]:
	"""The view boxes of a spriteset, as (left, top, width, height) relative to its own origin."""
	return tuple(
		(sprite.left_x, sprite.upper_y, sprite.width, sprite.height) for sprite in spriteset.template.sprites
	)


def pattern_of(detection: Detection, part: Part) -> frozenset[tuple[int, int, int, int]]:
	"""One drawing's lamps as a pattern: (view, x, y, value) per lamp, box-relative.

	The coordinates are relative to the view boxes rather than the sheet, because that is what two
	liveries of one unit share: they draw their lamps in the same places on different rows. Comparing
	these patterns is how the builder decides whether a unit's identified liveries agree.
	"""
	pattern = set()
	for (abs_x, abs_y), value in detection.pixels.items():
		for view, (left, top, width, height) in enumerate(part.boxes):
			x, y = abs_x - left, abs_y - part.row_y - top
			if 0 <= x < width and 0 <= y < height:
				pattern.add((view, x, y, value))
				break
	return frozenset(pattern)


def apply_pattern(part: Part, pattern, source: str) -> Detection:
	"""A detection holding `pattern`'s lamps on this drawing, labelled as assumed from `source`."""
	detection = Detection()
	for view, x, y, value in sorted(pattern):
		left, top, width, height = part.boxes[view]
		detection.pixels[(left + x, part.row_y + top + y)] = value
	if not detection.pixels:
		return detection
	detection.rows.add(part.row_y)
	detection.pairs = len(detection.pixels)
	detection.view_mapping = "assumed"
	detection.assumed_from = source
	return detection


def _clusters(pixels: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
	remaining, out = set(pixels), []
	while remaining:
		seed = remaining.pop()
		component, stack = {seed}, [seed]
		while stack:
			x, y = stack.pop()
			for dx in (-1, 0, 1):
				for dy in (-1, 0, 1):
					candidate = (x + dx, y + dy)
					if candidate in remaining:
						remaining.discard(candidate)
						component.add(candidate)
						stack.append(candidate)
		out.append(component)
	return out


def lamp_pixels(image, box: tuple[int, int, int, int], row_y: int) -> tuple[set, set]:
	"""Lit pixels in one view box of one row: (all candidates, the ones accepted as lamps).

	Within a cluster only the brightest shade counts, so a dimmer glow around a lamp does not widen it
	and an oversized bright blob is rejected rather than truncated.
	"""
	left, top, width, height = box
	candidates = {
		(x, y)
		for x in range(width)
		for y in range(height)
		if image.getpixel((left + x, row_y + top + y)) in LIT
	}
	kept: set[tuple[int, int]] = set()
	for component in _clusters(candidates):
		brightest = min(LIT_ORDER.index(image.getpixel((left + x, row_y + top + y))) for x, y in component)
		top_shade = {
			p for p in component
			if LIT_ORDER.index(image.getpixel((left + p[0], row_y + top + p[1]))) == brightest
		}
		if len(component) <= 2 or len(top_shade) == len(component):
			kept |= top_shade
	return candidates, kept


def mirror_symmetric(lamps: list[tuple[int, int, int, int]], width: int) -> bool:
	"""True when every lamp pixel in an end-on view has its x-mirror partner or is a centre pixel."""
	positions = {(x, y) for (x, y, *_) in lamps}
	for x, y in positions:
		if (width - 1 - x, y) in positions:
			continue
		if x in (width // 2 - 1, width // 2):  # a lone centre repeater, either side of dead centre
			continue
		return False
	return True


def _pair_view(
	image,
	detection: Detection,
	this_row: int,
	this_box: tuple[int, int, int, int],
	other_row: int,
	other_box: tuple[int, int, int, int],
	view: int,
	mirror_x: bool = False,
) -> None:
	"""Pair one view's lamp pixels with the counterpart view four along, storing absolute pixels."""
	_, kept = lamp_pixels(image, this_box, this_row)
	positions = sorted(kept)
	if mirror_x:
		positions = sorted((this_box[2] - 1 - x, y) for x, y in positions)
	found: list[tuple[int, int, int, int]] = []
	for (x, y) in positions:
		if x >= other_box[2]:
			continue
		value = image.getpixel((this_box[0] + x, this_row + this_box[1] + y))
		other = image.getpixel((other_box[0] + x, other_row + other_box[1] + y))
		if other in WHITE or other == value:
			detection.rejected += 1
			continue
		if other == TRANSPARENT:
			detection.flags.append(f"transparent counterpart at row y={this_row} view {view} ({x},{y})")
			continue
		found.append((x, y, other, value))
	if len(found) > MAX_LAMPS_PER_VIEW:
		detection.flags.append(
			f"view {view} of row y={this_row} found {len(found)} lamp pixels "
			f"(cap {MAX_LAMPS_PER_VIEW}): not automated"
		)
		return
	if view in END_ON_VIEWS and not mirror_symmetric(found, this_box[2]):
		detection.flags.append(
			f"end-on lamps at view {view} of row y={this_row} are not mirror-symmetric: not automated"
		)
		return
	if found:
		detection.rows.add(this_row)
		detection.rows.add(other_row)
	for (x, y, other, value) in found:
		detection.pixels[(this_box[0] + x, this_row + this_box[1] + y)] = other
		detection.pixels[(other_box[0] + x, other_row + other_box[1] + y)] = value
		detection.pairs += 1


def detect_in_row(image, row_y: int, boxes) -> Detection:
	"""Pair a single-unit drawing's own views: its row holds the nose views and the rear views."""
	best: Detection | None = None
	for mirror_x in (False, True):
		detection = Detection()
		for view in range(8):
			_pair_view(image, detection, row_y, boxes[view], row_y, boxes[(view + 4) % 8], view, mirror_x)
		if best is None or detection.pairs > best.pairs:
			best = detection
			best.view_mapping = "mirrored x" if mirror_x else "same x"
	return best


def detect_between_rows(image, row_a: int, boxes_a, row_b: int, boxes_b) -> Detection:
	"""Pair two drawings: the leading end's lamp pixel is the trailing end's counterpart."""
	detection = Detection()
	end_on = 0
	for this_row, this_boxes, other_row, other_boxes in (
		(row_a, boxes_a, row_b, boxes_b),
		(row_b, boxes_b, row_a, boxes_a),
	):
		for view in range(8):
			before = detection.pairs
			_pair_view(image, detection, this_row, this_boxes[view], other_row, other_boxes[(view + 4) % 8], view)
			if detection.pairs > before and view in END_ON_VIEWS:
				end_on += 1
	if not end_on:
		detection.flags.append("no end-on (N/S) lamp pair found: ends may not be two cabs of one unit")
	return detection


def _end_on_lamp_count(image, box: tuple[int, int, int, int], row_y: int) -> int:
	_, kept = lamp_pixels(image, box, row_y)
	return len(kept)


def _detect_unpaired_rows(image, row_a: int, boxes_a, row_b: int, boxes_b) -> Detection:
	"""A loco and its tender: only the end that is the whole vehicle can be paired, within its own row."""
	detection = Detection()
	count_a = sum(_end_on_lamp_count(image, boxes_a[view], row_a) for view in END_ON_VIEWS)
	count_b = sum(_end_on_lamp_count(image, boxes_b[view], row_b) for view in END_ON_VIEWS)
	if not count_a and not count_b:
		detection.flags.append("no lamp pixels in the head set on either end's own drawing")
		return detection
	if count_a and count_b:
		detection.flags.append("the two ends use different templates and both carry lamps: needs review")
		return detection
	detection.add(detect_in_row(image, row_a if count_a else row_b, boxes_a if count_a else boxes_b))
	if not detection.pairs:
		detection.flags.append("the drawing has no pairable lamp pixels in the head set")
	return detection


def detect_for_parts(image, parts: list[Part], trailing_only_fallback: bool = False) -> Detection:
	"""Run the rules over one variant's parts, in consist order.

	`trailing_only_fallback` admits the trailing-lamp rule for a vehicle the caller knows is a
	driving car (`has_cab`): such a vehicle draws its lamps red on the end-on face because its cab
	points away from the train in the normal state, so there is no white counterpart to pair with.
	It stays off everywhere else — a locomotive or multiple unit that already pairs must not have
	livery red read as lamps.
	"""
	if not parts:
		return Detection()

	detection = _paired_detection(image, parts)
	if detection.pixels or not trailing_only_fallback:
		return detection

	rows: list[tuple[int, tuple]] = []
	for part in parts:
		if not any(row_y == part.row_y for row_y, _ in rows):
			rows.append((part.row_y, part.boxes))

	trailing = detect_trailing_only(image, rows)
	if trailing.pixels:
		return trailing

	detection.flags.extend(flag for flag in trailing.flags if flag not in detection.flags)
	return detection


def _paired_detection(image, parts: list[Part]) -> Detection:
	"""The original rule: pair each drawing's lamps with the counterpart that shows them lit."""
	if len({part.row_y for part in parts}) == 1:
		# a single-unit vehicle: locomotive, tank engine, single-unit stock
		return detect_in_row(image, parts[0].row_y, parts[0].boxes)

	first, last = parts[0], parts[-1]
	if first.row_y == last.row_y:
		return detect_in_row(image, first.row_y, first.boxes)
	if len(first.boxes) != len(last.boxes):
		detection = Detection()
		detection.flags.append("the two ends expose a different number of views: needs review")
		return detection
	if first.template_name != last.template_name:
		return _detect_unpaired_rows(image, first.row_y, first.boxes, last.row_y, last.boxes)
	return detect_between_rows(image, first.row_y, first.boxes, last.row_y, last.boxes)


def detect_trailing_only(image, rows: list[tuple[int, tuple]]) -> Detection:
	"""Lamps drawn only in their trailing state: a red pair on an end-on face, no white anywhere.

	Driving vehicles draw their lamps red, because a DVT's cab faces away from the train in the
	normal state (that is what `has_cab` marks), and their art carries no white counterpart to pair
	with — so the ordinary rule finds nothing and the lamps never flip while the train drives
	backwards. This rule accepts the red pair instead, and paints it white.

	Searching only the end-on views is what keeps a livery's own red out: the Royal Mail PCV and the
	TPO body are drawn mostly in red, as is a Class 60's livery, and a livery red runs in strokes of
	a dozen pixels or more while a lamp is one or two isolated pixels mirrored about the centreline.
	The caller decides *whether* to ask (it passes `has_cab`); this function decides whether what it
	finds is a lamp.
	"""
	detection = Detection()
	for row_y, boxes in rows:
		found: dict[tuple[int, int], int] = {}
		ends_with_lamps = 0
		for view in END_ON_VIEWS:
			left, top, width, height = boxes[view]
			reds = {
				(x, y)
				for x in range(width)
				for y in range(height)
				if image.getpixel((left + x, row_y + top + y)) in TRAILING_LAMP_RED
			}
			# A lamp is one or two pixels; anything larger is a stroke of livery.
			lamps = {pixel for cluster in _clusters(reds) if len(cluster) <= 2 for pixel in cluster}
			if not lamps:
				continue
			if len(lamps) > MAX_LAMPS_PER_VIEW:
				detection.flags.append(
					f"view {view} of row y={row_y} has {len(lamps)} red pixels "
					f"(cap {MAX_LAMPS_PER_VIEW}): not automated"
				)
				continue
			if not mirror_symmetric([(x, y, 0, 0) for x, y in lamps], width):
				detection.flags.append(
					f"red pixels at view {view} of row y={row_y} are not mirror-symmetric: not automated"
				)
				continue
			ends_with_lamps += 1
			for x, y in lamps:
				found[(left + x, row_y + top + y)] = TRAILING_LAMP_LIT

		if not found:
			continue
		if ends_with_lamps > 1:
			# Both end-on faces carry a red pair: the drawing is not a single-cab vehicle, so which
			# end trails is ambiguous. Leave it to a human rather than guess.
			detection.flags.append(
				f"red lamp pairs on both end-on views of row y={row_y}: not automated"
			)
			continue

		if detection.pixels:
			detection.flags.append(
				f"trailing lamps found on more than one drawing (rows {sorted(detection.rows)} and "
				f"y={row_y}): not automated"
			)
			return detection

		detection.pixels.update(found)
		detection.rows.add(row_y)
		detection.pairs += len(found)
		detection.view_mapping = "trailing only"

	return detection


class LightingOverlayCache:
	"""Reads and writes a sheet's lamp pixels as `<sheet>.lightcache.json`, beside the sheet.

	Keyed by everything detection depends on: the sheet bytes, the palette, the template geometry, the
	rules version, and the pairings asked about. Derived data, not a build input.
	"""

	FORMAT_NAME = "brbuild-lighting-overlay"
	FORMAT_VERSION = 1
	SUFFIX = ".lightcache.json"

	def __init__(self, sheet_path: str | Path, palette: list[int], definitions: list):
		self.sheet_path = Path(sheet_path)
		self.palette = palette
		self.definitions = definitions

	@property
	def path(self) -> Path:
		return self.sheet_path.with_name(self.sheet_path.name + self.SUFFIX)

	def load(self) -> dict[str, Detection]:
		"""Return the cached detections by pairing signature, or {} when there is no usable cache."""
		if not self.path.is_file():
			return {}
		try:
			payload = json.loads(self.path.read_text(encoding="utf-8"))
		except (OSError, json.JSONDecodeError) as exc:
			logger.warning(f"Ignoring unreadable lighting cache '{self.path}': {exc}")
			return {}
		if not isinstance(payload, dict) or not self._matches(payload):
			return {}
		logger.debug(f"Reused {len(payload.get('detections', {}))} lighting detection(s) from '{self.path}'.")
		return {key: Detection.deserialise(value) for key, value in payload.get("detections", {}).items()}

	def store(self, detections: dict[str, Detection]) -> None:
		if not detections:
			return
		payload = {
			"format": self.FORMAT_NAME,
			"version": self.FORMAT_VERSION,
			"rules": RULES_VERSION,
			"limits": {"max_lamps_per_view": MAX_LAMPS_PER_VIEW, "lamp_order": list(LIT_ORDER)},
			"sheet": {"name": self.sheet_path.name, "sha256": self._file_digest(self.sheet_path)},
			"palette_sha256": _digest(bytes(bytearray(self.palette))),
			"templates_sha256": _templates_digest(self.definitions),
			"detections": {key: value.serialise() for key, value in sorted(detections.items())},
		}
		try:
			self.path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
		except OSError as exc:
			logger.warning(f"Could not write lighting cache '{self.path}': {exc}")
			return
		logger.debug(f"Cached {len(detections)} lighting detection(s) to '{self.path}'.")

	def _matches(self, payload: dict) -> bool:
		if payload.get("format") != self.FORMAT_NAME or payload.get("version") != self.FORMAT_VERSION:
			return False
		if payload.get("rules") != RULES_VERSION:
			return False
		if payload.get("palette_sha256") != _digest(bytes(bytearray(self.palette))):
			return False
		if payload.get("templates_sha256") != _templates_digest(self.definitions):
			return False
		sheet = payload.get("sheet") or {}
		if sheet.get("name") != self.sheet_path.name:
			return False
		if sheet.get("sha256") != self._file_digest(self.sheet_path):
			return False
		return isinstance(payload.get("detections"), dict)

	@staticmethod
	def _file_digest(path: Path) -> str | None:
		try:
			return _digest(path.read_bytes())
		except OSError:
			return None


def _digest(data: bytes) -> str:
	return hashlib.sha256(data).hexdigest()


def _templates_digest(definitions: list) -> str:
	"""Everything about the template geometry that detection depends on."""
	described = [
		{
			"name": definition.name,
			"vehicle_type": definition.vehicle_type,
			"length": definition.length,
			"boxes": [[box.left_x, box.upper_y, box.width, box.height] for box in definition.bounding_boxes],
		}
		for definition in definitions
	]
	return _digest(json.dumps(described, sort_keys=True).encode("utf-8"))


def signature(parts: list[Part]) -> str:
	"""A stable description of the pairings a detection was made for, used as the cache key."""
	described = [
		{"row": part.row_y, "template": part.template_name, "boxes": [list(box) for box in part.boxes]}
		for part in parts
	]
	return _digest(json.dumps(described, sort_keys=True).encode("utf-8"))[:16]


def overlay_image(sheet_path: str | Path, detection: Detection):
	"""The overlay sheet: same geometry as the base sheet, transparent apart from the lamp pixels,
	which take the counterpart's value. Returns None when nothing was detected."""
	if not detection.pixels:
		return None
	base = Image.open(sheet_path).convert("P")
	overlay = Image.new("P", base.size, TRANSPARENT)
	overlay.putpalette(base.getpalette())
	for (x, y), value in detection.pixels.items():
		overlay.putpixel((x, y), value)
	return overlay


class VehicleLighting:
	"""Per-vehicle lighting work: detect (with caching), then write the overlay and transparency sheets.

	One overlay sheet per published sheet, holding the union of every variant's lamp pixels, mirroring
	how the purchase icons are written into the build's working folder.
	"""

	def __init__(
		self,
		vehicle,
		palette: list[int],
		definitions: list,
		output_folder: str,
		sheet_path: str | None = None,
	):
		self.vehicle = vehicle
		#: One instance per spritesheet: a candidate whose profiles name their own sheets gets a
		#: detector (and an overlay sheet) per sheet it draws from.
		self.sheet_path = Path(sheet_path or vehicle.spritesheet_path)
		self.output_folder = Path(output_folder)
		self.cache = LightingOverlayCache(self.sheet_path, palette, definitions)
		self._detections: dict[str, Detection] = self.cache.load()
		self._image = None
		self._combined = Detection()
		self.overlay_path: Path | None = None
		self.transparent_path: Path | None = None
		self.unwritten = False

	@property
	def image(self):
		if self._image is None:
			self._image = Image.open(self.sheet_path).convert("P")
		return self._image

	def detection_for(self, parts: list[Part], trailing_only: bool = False) -> Detection:
		"""The detection for one variant's pairings, from the cache or freshly made.

		`trailing_only` admits the trailing-lamp rule for a driving car (`has_cab`); it is part of the
		cache key because the same pairings answer differently with and without it.
		"""
		key = signature(parts) + ("|trailing" if trailing_only else "")
		if key not in self._detections:
			self._detections[key] = detect_for_parts(self.image, parts, trailing_only_fallback=trailing_only)
			self.unwritten = True
		detection = self._detections[key]
		self._combined.add(detection)
		return detection

	def assume_for(self, parts: list[Part], part_index: int, pattern, source: str) -> Detection:
		"""Register a detection whose lamps were assumed from a sibling drawing.

		Cached like any other detection so a rebuild reuses the assumption instead of re-deriving
		it, under a key that names the source: if a later build picks a different sibling (because
		that one stopped being readable, say) the entry is re-derived rather than carrying a stale
		label. `<sheet>.lightcache.json` therefore names what every guess came from.
		"""
		key = signature(parts) + f"|assumed:{part_index}|{source}"
		detection = self._detections.get(key)
		if detection is None:
			detection = apply_pattern(parts[part_index], pattern, source)
			self._detections[key] = detection
			self.unwritten = True
		detection.assumed_from = source
		self._combined.add(detection)
		return detection

	def write_images(self) -> None:
		"""Write the overlay and transparency sheets, only when their contents changed."""
		if self.unwritten:
			self.cache.store(self._detections)

		if not self._combined.pixels:
			return

		overlay = overlay_image(self.sheet_path, self._combined)
		if overlay is None:
			return
		path = self.output_folder / (self.sheet_path.stem + OVERLAY_SUFFIX)
		_write_if_changed(path, overlay)
		self.overlay_path = path

		transparent = Image.new("P", overlay.size, TRANSPARENT)
		transparent.putpalette(overlay.getpalette())
		transparent_path = self.output_folder / (self.sheet_path.stem + TRANSPARENT_SUFFIX)
		_write_if_changed(transparent_path, transparent)
		self.transparent_path = transparent_path


def _write_if_changed(path: Path, image) -> None:
	"""Write an image only when its bytes differ, so an unchanged build does not invalidate caches."""
	buffer = _encode(image)
	if path.is_file() and path.read_bytes() == buffer:
		return
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_bytes(buffer)


def _encode(image) -> bytes:
	import io

	stream = io.BytesIO()
	image.save(stream, format="PNG", optimize=True)
	return stream.getvalue()
