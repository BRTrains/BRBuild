from dataclasses import dataclass
from typing import List, Optional, Union


@dataclass
class Livery:
    name: str
    size: Optional[int] = None
    num_vehicles: Optional[int] = None
    sprite_override: Optional[List[int]] = None
    sprite_exclude: Optional[List[int]] = None
    profiles: Optional[List[str]] = None
    power: Optional[int] = None
    design_speed: Optional[int] = None
    weight: Optional[float] = None
    tilt: Optional[Union[str, float]] = None
    sound_effect: Optional[str] = None
    visual_effect: Optional[str] = None
    nml_override: Optional[dict] = None
    special_tags: Optional[List[str]] = None