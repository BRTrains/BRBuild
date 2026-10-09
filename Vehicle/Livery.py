from dataclasses import dataclass
from typing import List, Optional, Union


@dataclass
class Livery:
    name: str
    sub_name: Optional[str] = None
    size: Optional[int] = None
    num_vehicles: Optional[int] = None
    formation: Optional[str] = None
    sprite_override: Optional[List[int]] = None
    sprite_exclude: Optional[List[int]] = None
    profiles: Optional[List[str]] = None
    #: Reuse another livery's drawings (of this profile) instead of consuming rows of its own.
    #: The profile field of the same name reuses a profile's rows for the same livery.
    sprite_group: Optional[str] = None
    capacity: Optional[int] = None
    power: Optional[int] = None
    speed: Optional[int] = None
    design_speed: Optional[int] = None
    weight: Optional[float] = None
    #: When this livery's vehicles become available, as a year or `YYYY-MM-DD`.
    introduction_date: Optional[Union[str, int]] = None
    tilt: Optional[Union[str, float]] = None
    track_type: Optional[List[str]] = None
    has_cab: Optional[bool] = None
    #: `auto` (default), `exact` or `none`; see Vehicle.lighting.
    lighting: Optional[str] = None
    #: Draw this livery's rows from a spritesheet of its own; see Profile.spritesheet.
    spritesheet: Optional[str] = None
    sound_effect: Optional[str] = None
    visual_effect: Optional[str] = None
    nml_override: Optional[dict] = None
    special_tags: Optional[List[str]] = None