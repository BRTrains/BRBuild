from __future__ import annotations

import yaml
from typing import Any, Dict, List, Optional, Union

from Vehicle.Vehicle import Vehicle, Profile, Livery

# assumes Vehicle, Profile, Livery already defined
# from models import Vehicle, Profile, Livery


class VehicleLoader:
    @staticmethod
    def load(path: str) -> Vehicle:
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return VehicleLoader._parse_vehicle(data)

    @staticmethod
    def _parse_vehicle(data: Dict[str, Any]) -> Vehicle:
        info = data.get("info", {}) or {}
        stats = data.get("stats", {}) or {}
        cargo = data.get("cargo", {}) or {}
        dates = data.get("dates", {}) or {}

        profiles = [
            VehicleLoader._parse_profile(p)
            for p in data.get("profiles", []) or []
        ]

        liveries = [
            VehicleLoader._parse_livery(l)
            for l in data.get("liveries", []) or []
        ]

        return Vehicle(
            identifier=info.get("identifier"),
            name=info.get("name"),
            sub_name=info.get("sub_name"),
            based_on=info.get("based_on"),
            operator=info.get("operator"),
            classification=data.get("classification"),

            vehicle_type=stats.get("type"),

            weight=stats.get("weight"),
            length=data.get("length"),

            power=data.get("power"),
            speed=data.get("speed"),
            tractive_effort=data.get("tractive_effort"),

            cargo_classes=cargo.get("cargo_classes"),
            power_type=data.get("power_type"),

            introduction_date=dates.get("introduction_date") or data.get("introduction_date"),

            model_life=data.get("model_life"),
            retire_early=data.get("retire_early"),
            vehicle_life=data.get("vehicle_life"),
            cargo_age_period=data.get("cargo_age_period"),
            loading_speed=data.get("loading_speed"),
            sound_effect=data.get("sound effect"),

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
    def _parse_livery(l: Dict[str, Any]) -> Livery:
        return Livery(
            name=l.get("name"),
            sprite_override=l.get("sprite_override"),
            profiles=l.get("profiles"),
        )