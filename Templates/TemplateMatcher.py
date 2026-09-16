from __future__ import annotations

from Sprites.Sprite import Sprite

from .TemplateDefinition import TemplateDefinition
from .TemplateType import TemplateType

EXPECTED_VIEWS = 8


def classify_row(
	views: list[Sprite], vehicle_type: str, definitions: list[TemplateDefinition]
) -> TemplateDefinition | None:
	"""Identify which known template a detected row's views correspond to, if any.

	A single-view row is treated as a legacy purchase-sprite remnant (`tmpl_purchase`).
	Otherwise, length is derived from the 3rd (index 2) view's width: legacy templates
	use width/4, newer templates use (width-1)/4. The candidate length is confirmed by
	finding a loaded TemplateDefinition of matching vehicle_type/length/flavour.
	Returns None if the row doesn't correspond to any known template (a doodle/note/etc).
	"""
	if len(views) == 1:
		return next(
			(d for d in definitions if d.template_type == TemplateType.PURCHASE and d.purchase_subtype is None),
			None,
		)

	if len(views) != EXPECTED_VIEWS:
		return None

	third_width = views[2].width
	candidate_lengths = []

	if third_width % 4 == 0:
		candidate_lengths.append((third_width // 4, True))  # legacy formula

	if (third_width - 1) % 4 == 0:
		candidate_lengths.append(((third_width - 1) // 4, False))  # newer formula

	for length, legacy in candidate_lengths:
		if not (1 <= length <= 8):
			continue

		match = _find_definition(definitions, vehicle_type, length, legacy, views)
		if match is not None:
			return match

	return None


def _find_definition(
	definitions: list[TemplateDefinition], vehicle_type: str, length: int, legacy: bool, views: list[Sprite]
) -> TemplateDefinition | None:
	options = [
		d for d in definitions
		if d.template_type == TemplateType.VEHICLE
		and d.vehicle_type == vehicle_type
		and d.length == length
		and d.legacy == legacy
		and not d.is_reversed
	]

	if not options:
		return None

	if len(options) == 1:
		return options[0]

	# Multiple matches (e.g. normal vs _tall) - disambiguate by closest overall height.
	tallest_view = max((view.height for view in views), default=0)
	return min(
		options,
		key=lambda d: abs(max((box.height for box in d.bounding_boxes), default=0) - tallest_view),
	)
