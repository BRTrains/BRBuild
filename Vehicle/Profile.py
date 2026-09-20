from dataclasses import dataclass
from typing import List, Optional, Union

from PropertyCalculation.VehicleType import VehicleType


@dataclass
class Profile:
    identifier: str
    name: Optional[str] = None
    size: Optional[int] = None
    num_vehicles: Optional[int] = None
    sprite_override: Optional[List[int]] = None
    sprite_exclude: Optional[List[int]] = None
    capacity: Optional[int] = None
    power: Optional[int] = None
    design_speed: Optional[int] = None
    weight: Optional[float] = None
    tilt: Optional[Union[str, float]] = None
    sound_effect: Optional[str] = None
    visual_effect: Optional[str] = None
    types: Optional[List[VehicleType]] = None
    cargo_classes: Optional[List[str]] = None
    nml_override: Optional[dict] = None
    special_tags: Optional[List[str]] = None