from dataclasses import dataclass, field


@dataclass
class Sprite:
	"""One real-sprite rectangle in a template."""

	left_x: int
	upper_y: int
	width: int
	height: int
	offset_x: int
	offset_y: int
	flags: list[str] = field(default_factory=list)
