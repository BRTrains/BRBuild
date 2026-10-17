from dataclasses import dataclass
from typing import List, Optional, Union

from PropertyCalculation.VehicleType import VehicleType


@dataclass
class Profile:
    identifier: str
    name: Optional[str] = None
    sub_name: Optional[str] = None
    size: Optional[int] = None
    num_vehicles: Optional[int] = None
    formation: Optional[str] = None
    sprite_override: Optional[List[int]] = None
    sprite_exclude: Optional[List[int]] = None
    sprite_group: Optional[str] = None
    capacity: Optional[int] = None
    power: Optional[int] = None
    speed: Optional[int] = None
    design_speed: Optional[int] = None
    weight: Optional[float] = None
    introduction_date: Optional[Union[str, int]] = None
    years_available: Optional[int] = None
    vehicle_life: Optional[int] = None
    effect_vehicles: Optional[List[int]] = None
    effect_vehicles_by_power: Optional[dict] = None
    pantograph_car: Optional[Union[int, List[int]]] = None
    effect_x_offset: Optional[int] = None
    effect_y_offset: Optional[int] = None
    effect_z_offset: Optional[int] = None
    effect_offsets_by_power: Optional[dict] = None
    effect_sprite: Optional[str] = None
    effect_sprites_by_power: Optional[dict] = None
    tilt: Optional[Union[str, float]] = None
    track_type: Optional[List[str]] = None
    has_cab: Optional[bool] = None
    #: `auto` (default), `exact` or `none`; see Vehicle.lighting.
    lighting: Optional[str] = None
    #: Draw this profile's rows from a spritesheet of its own, instead of the candidate's
    #: own `<Vehicle>.png`. Keeps the drawings of one profile out of the shared sheet.
    spritesheet: Optional[str] = None
    sound_effect: Optional[str] = None
    visual_effect: Optional[str] = None
    types: Optional[List[VehicleType]] = None
    cargo_classes: Optional[List[str]] = None
    nml_override: Optional[dict] = None
    special_tags: Optional[List[str]] = None