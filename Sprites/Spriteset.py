from dataclasses import dataclass

from .Template import Template


@dataclass
class Spriteset:
	"""A template rendered from a spritesheet at a given origin."""

	name: str
	file: str
	template: Template
	x: int = 0
	y: int = 0
