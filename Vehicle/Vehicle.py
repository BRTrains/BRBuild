from PropertyCalculation.VehicleType import VehicleType
from PropertyCalculation.TrainType import TrainType
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

from Grf.RailTypeTable import RailTypeTable
from Vehicle.Livery import Livery
from Vehicle.Profile import Profile


@dataclass
class Vehicle:
    folder_path: str
    identifier: str
    name: str
    nickname: Optional[str] = None
    sub_name: Optional[str] = None

    yaml_path: Optional[str] = None
    spritesheet_override: Optional[str] = None
    #: Staged copies of this vehicle's spritesheets during an ingest, keyed by published path.
    #: A standalone sheet declared on a profile/livery is staged the same way the vehicle's own
    #: sheet is, so the build reads (and normalises) the staged copy and publishes it afterwards.
    spritesheet_overrides: dict = field(default_factory=dict)

    based_on: Optional[str] = None
    operator: Optional[str] = None
    classification: Optional[str] = None
    additional_text: Optional[str] = None

    vehicle_type: Optional[VehicleType] = None
    train_type: Optional[TrainType] = None

    weight: Optional[float] = None
    length: Optional[int] = None
    tilt: Optional[Union[str, float]] = None

    #: `auto` (default) detects the lamps and fills an unreadable livery in from its siblings,
    #: `exact` trusts only what this vehicle's own artwork shows, `none` emits no layer at all.
    lighting: Optional[str] = None

    #: A driving vehicle — an unpowered cab car such as a DVT or DBSO, which OpenTTD lets lead a
    #: rake so the train backs up instead of magic-flipping. Emits `extra_flags`' HAS_CAB bit.
    has_cab: Optional[bool] = None

    power: Optional[int] = None
    speed: Optional[int] = None
    design_speed: Optional[int] = None
    tractive_effort: Optional[int] = None

    cargo_classes: Optional[List[str]] = None
    non_cargo_classes: Optional[List[str]] = None
    default_cargo_type: Optional[str] = None
    autorefit: Optional[bool] = None
    power_type: Optional[List[str]] = None
    track_type: Optional[List[str]] = None
    capacity: Optional[int] = None

    size: Optional[int] = None
    num_vehicles: Optional[int] = None
    formation: Optional[str] = None
    sprite_override: Optional[List[int]] = None
    sprite_exclude: Optional[List[int]] = None

    introduction_date: Optional[Union[str, int]] = None

    model_life: Optional[str] = None
    retire_early: Optional[int] = None
    vehicle_life: Optional[int] = None
    cargo_age_period: Optional[int] = None
    loading_speed: Optional[int] = None
    sound_effect: Optional[str] = None
    visual_effect: Optional[str] = None
    engine_class: Optional[str] = None

    special_tags: Optional[list] = None
    nml_override: Optional[dict] = None

    profiles: List[Profile] = field(default_factory=list)
    liveries: List[Livery] = field(default_factory=list)

    #: The project's logical track types; set by the builder so variants can resolve
    #: `track_type` names into railtype indices.
    rail_type_table: Optional[RailTypeTable] = None

    @property
    def spritesheet_path(self) -> Optional[str]:
        """The spritesheet image path: same name as the YAML file, with a .png extension."""
        if self.spritesheet_override:
            return self.spritesheet_override
        if not self.yaml_path:
            return None
        return str(Path(self.yaml_path).with_suffix(".png"))
