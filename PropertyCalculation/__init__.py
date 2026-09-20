"""Property calculation helpers and enums.

Expose small helper classes used across the project.
"""

from .CargoClasses import CARGO_CLASSES, as_bitmask, parse_cargo
from .CostCalculator import CostCalculator
from .FuelDefaults import FuelDefaults
from .FuelType import FuelType
from .Physics import Physics
from .PowerTypeClassifier import PowerTypeClassifier
from .TrainType import TrainType
from .VehicleType import VehicleType
from .WagonType import WagonType

__all__ = [
	"CARGO_CLASSES",
	"CostCalculator",
	"FuelDefaults",
	"FuelType",
	"PowerTypeClassifier",
	"WagonType",
	"TrainType",
	"VehicleType",
	"Physics",
	"as_bitmask",
	"parse_cargo",
]
