from dataclasses import dataclass, field

from Sprites.Sprite import Sprite


@dataclass
class Template:
	"""An ordered NML template made up of sprite rectangles."""

	name: str
	sprites: list[Sprite] = field(default_factory=list)
