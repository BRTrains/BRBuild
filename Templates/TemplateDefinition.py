from dataclasses import dataclass, field

from .BoundingBox import BoundingBox
from .TemplateType import TemplateType


@dataclass
class TemplateDefinition:
	"""A parsed `template tmpl_...(x, y) { [...] }` block from a project's .pnml files."""

	name: str
	template_type: TemplateType
	vehicle_type: str | None = None
	length: int | None = None
	legacy: bool = False
	tall: bool = False
	is_reversed: bool = False
	purchase_subtype: str | None = None
	variant_tags: list[str] = field(default_factory=list)
	bounding_boxes: list[BoundingBox] = field(default_factory=list)
