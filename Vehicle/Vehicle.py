from dataclasses import dataclass
from typing import Optional, List, Union

from Vehicle.Profile import Profile
from Vehicle.Livery import Livery

@dataclass
class Vehicle:
    identifier: str
    name: str
    sub_name: Optional[str] = None

    based_on: Optional[str] = None
    operator: Optional[str] = None
    classification: Optional[str] = None

    vehicle_type: Optional[str] = None

    weight: Optional[float] = None
    length: Optional[int] = None

    power: Optional[int] = None
    speed: Optional[int] = None
    tractive_effort: Optional[int] = None

    cargo_classes: Optional[List[str]] = None
    power_type: Optional[List[str]] = None

    introduction_date: Optional[Union[str, int]] = None

    model_life: Optional[str] = None
    retire_early: Optional[int] = None
    vehicle_life: Optional[int] = None
    cargo_age_period: Optional[int] = None
    loading_speed: Optional[int] = None
    sound_effect: Optional[str] = None

    profiles: List[Profile] = None
    liveries: List[Livery] = None
