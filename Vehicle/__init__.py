"""Vehicle package public API

Export the core classes used by other packages. Keep imports lightweight.
"""

from .Livery import Livery
from .Profile import Profile
from .SpriteSizeTemplate import standard_pattern
from .Variant import Variant
from .VariantIterator import VariantIterator
from .VariantNmlModel import VariantNmlModel
from .VariantSpriteGroups import (
	SpriteGroup,
	VehicleSpriteAllocator,
	build_sprite_groups,
)
from .Vehicle import Vehicle

__all__ = [
	"Vehicle",
	"Variant",
	"VariantIterator",
	"Profile",
	"Livery",
	"VariantNmlModel",
	"SpriteGroup",
	"VehicleSpriteAllocator",
	"build_sprite_groups",
	"standard_pattern",
]
