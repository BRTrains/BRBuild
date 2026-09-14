from dataclasses import dataclass
from typing import List, Optional, Union

from Vehicle.Livery import Livery
from Vehicle.Profile import Profile


@dataclass
class Vehicle:
    folder_path: str
    identifier: str
    name: str
    sub_name: Optional[str] = None

    based_on: Optional[str] = None
    operator: Optional[str] = None
    classification: Optional[str] = None
    additional_text: Optional[str] = None

    vehicle_type: Optional[str] = None
    train_type: Optional[str] = None

    weight: Optional[float] = None
    length: Optional[int] = None

    power: Optional[int] = None
    speed: Optional[int] = None
    tractive_effort: Optional[int] = None

    cargo_classes: Optional[List[str]] = None
    power_type: Optional[List[str]] = None
    capacity: Optional[int] = None

    introduction_date: Optional[Union[str, int]] = None

    model_life: Optional[str] = None
    retire_early: Optional[int] = None
    vehicle_life: Optional[int] = None
    cargo_age_period: Optional[int] = None
    loading_speed: Optional[int] = None
    sound_effect: Optional[str] = None

    special_tags: Optional[list] = None

    profiles: List[Profile] = None
    liveries: List[Livery] = None
