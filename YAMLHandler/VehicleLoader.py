from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from PropertyCalculation import TrainType, VehicleType
from Vehicle import Livery, Profile, Vehicle

# assumes Vehicle, Profile, Livery already defined
# from models import Vehicle, Profile, Livery


class VehicleLoader:
    @staticmethod
    def load(path: str) -> Vehicle:
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return VehicleLoader._parse_vehicle(
            data,
            folder_path=str(Path(path).parent),
            path=path
        )

    @staticmethod
    def _parse_vehicle(data: Dict[str, Any], folder_path: str, path: str) -> Vehicle:
        info = data.get("info", {}) or {}
        stats = data.get("stats", {}) or {}
        cargo = data.get("cargo", {}) or {}
        dates = data.get("dates", {}) or {}

        profiles = [
            VehicleLoader._parse_profile(p)
            for p in data.get("profiles", []) or []
        ]

        liveries = [
            VehicleLoader._parse_livery(lv)
            for lv in data.get("liveries", []) or []
        ]

        raw_vehicle_type = stats.get("vehicle_type")

        if raw_vehicle_type is None:
            raise ValueError(f"Missing required stat 'vehicle_type' in {path}")

        try:
            vehicle_type = VehicleType[raw_vehicle_type.upper()]
        except (KeyError, AttributeError):
            raise ValueError(
                f"Invalid value '{raw_vehicle_type}' for 'vehicle_type' in {path}."
            )
        
        raw_train_type = stats.get("train_type", "").upper()
        if raw_train_type == "":
            raise ValueError(f"Missing required stat 'train_type' in {path}")

        try:
            # First try to parse as enum member (e.g., "LOCOMOTIVE" or "FREIGHT_WAGON")
            train_type = TrainType[raw_train_type.upper()]
        except KeyError:
            # If that fails, try to parse as raw value (e.g., "locomotive" or "freight_wagon")
            train_type = TrainType(raw_train_type)

        return Vehicle(
            folder_path=folder_path,
            identifier=info["identifier"],
            name=info.get("name", ""),
            sub_name=info.get("sub_name", ""),
            yaml_path=path,
            based_on=info.get("based_on", ""),
            operator=info.get("operator"),
            classification=data.get("classification"),
            additional_text=data.get("additional_text"),

            vehicle_type=vehicle_type,
            train_type=train_type,
            weight=stats.get("weight"),
            length=stats.get("length"),

            power=stats.get("power"),
            speed=stats.get("speed"),
            tractive_effort=stats.get("tractive_effort"),
            capacity = stats.get("capacity"),

            cargo_classes=cargo.get("cargo_classes"),
            power_type=stats.get("power_type"),

            size=stats.get("size") or data.get("size"),
            num_vehicles=stats.get("num_vehicles") or data.get("num_vehicles"),
            sprite_override=data.get("sprite_override"),
            sprite_exclude=data.get("sprite_exclude"),

            introduction_date=dates.get("introduction_date") or data.get("introduction_date"),

            model_life=data.get("model_life"),
            retire_early=data.get("retire_early"),
            vehicle_life=data.get("vehicle_life"),
            cargo_age_period=data.get("cargo_age_period"),
            loading_speed=data.get("loading_speed"),
            sound_effect=data.get("sound effect"),

            special_tags = data.get("special_tags", {}),

            profiles=profiles,
            liveries=liveries,
        )

    @staticmethod
    def _parse_profile(p: Dict[str, Any]) -> Profile:
        identifier = p.get("identifier")
        if identifier is None:
            raise ValueError(f"Profile configuration missing required 'identifier': {p}")
        return Profile(
            identifier=str(identifier),
            name=p.get("name"),
            size=p.get("size"),
            num_vehicles=p.get("num_vehicles"),
            sprite_override=p.get("sprite_override"),
            sprite_exclude=p.get("sprite_exclude"),
            capacity=p.get("capacity"),
            types=p.get("types"),
        )

    @staticmethod
    def _parse_livery(lv: Dict[str, Any]) -> Livery:
        name = lv.get("name")
        if name is None:
            raise ValueError(f"Livery configuration missing required 'name': {lv}")
        return Livery(
            name=str(name),
            size=lv.get("size"),
            num_vehicles=lv.get("num_vehicles"),
            sprite_override=lv.get("sprite_override"),
            sprite_exclude=lv.get("sprite_exclude"),
            profiles=lv.get("profiles"),
        )