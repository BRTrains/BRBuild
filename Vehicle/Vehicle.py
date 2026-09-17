from PropertyCalculation.VehicleType import VehicleType
from PropertyCalculation.TrainType import TrainType
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

from Vehicle.Livery import Livery
from Vehicle.Profile import Profile


@dataclass
class Vehicle:
    folder_path: str
    identifier: str
    name: str
    sub_name: Optional[str] = None

    yaml_path: Optional[str] = None

    based_on: Optional[str] = None
    operator: Optional[str] = None
    classification: Optional[str] = None
    additional_text: Optional[str] = None

    vehicle_type: Optional[VehicleType] = None
    train_type: Optional[TrainType] = None

    weight: Optional[float] = None
    length: Optional[int] = None

    power: Optional[int] = None
    speed: Optional[int] = None
    tractive_effort: Optional[int] = None

    cargo_classes: Optional[List[str]] = None
    power_type: Optional[List[str]] = None
    capacity: Optional[int] = None

    size: Optional[int] = None
    num_vehicles: Optional[int] = None
    sprite_override: Optional[List[int]] = None
    sprite_exclude: Optional[List[int]] = None

    introduction_date: Optional[Union[str, int]] = None

    model_life: Optional[str] = None
    retire_early: Optional[int] = None
    vehicle_life: Optional[int] = None
    cargo_age_period: Optional[int] = None
    loading_speed: Optional[int] = None
    sound_effect: Optional[str] = None

    special_tags: Optional[list] = None

    profiles: List[Profile] = field(default_factory=list)
    liveries: List[Livery] = field(default_factory=list)

    @property
    def spritesheet_path(self) -> Optional[str]:
        """The spritesheet image path: same name as the YAML file, with a .png extension."""
        if not self.yaml_path:
            return None
        return str(Path(self.yaml_path).with_suffix(".png"))
