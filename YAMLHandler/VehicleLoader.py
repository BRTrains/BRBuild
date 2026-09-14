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
            folder_path=str(Path(path).parent)
        )

    @staticmethod
    def _parse_vehicle(data: Dict[str, Any], folder_path: str) -> Vehicle:
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
        try:
            # First try to parse as enum member (e.g., "TRAIN" or "ROAD_VEHICLE")
            vehicle_type = VehicleType[raw_vehicle_type.upper()]
        except KeyError:
            # If that fails, try to parse as raw value (e.g., "train" or "road_vehicle")
            vehicle_type = VehicleType(raw_vehicle_type)

        raw_train_type = stats.get("train_type")
        try:
            # First try to parse as enum member (e.g., "LOCOMOTIVE" or "FREIGHT_WAGON")
            train_type = TrainType[raw_train_type.upper()]
        except KeyError:
            # If that fails, try to parse as raw value (e.g., "locomotive" or "freight_wagon")
            train_type = TrainType(raw_train_type)

        return Vehicle(
            folder_path=folder_path,
            identifier=info.get("identifier"),
            name=info.get("name"),
            sub_name=info.get("sub_name"),
            based_on=info.get("based_on"),
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
        return Profile(
            identifier=p.get("identifier"),
            name=p.get("name"),
            size=p.get("size"),
            capacity=p.get("capacity"),
            types=p.get("types"),
        )

    @staticmethod
    def _parse_livery(lv: Dict[str, Any]) -> Livery:
        return Livery(
            name=lv.get("name"),
            sprite_override=lv.get("sprite_override"),
            profiles=lv.get("profiles"),
        )