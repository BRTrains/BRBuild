from __future__ import annotations

import re
from datetime import date as _date, datetime as _datetime
from pathlib import Path
from typing import Any, Dict

import yaml

from PropertyCalculation import TrainType, VehicleType
from PropertyCalculation.CargoClasses import parse_cargo
from Vehicle import Livery, Profile, Vehicle

# assumes Vehicle, Profile, Livery already defined
# from models import Vehicle, Profile, Livery


class VehicleLoader:
    #: `YYYY`, `YYYY-MM` or `YYYY-MM-DD`, the authoring form for `introduction_date`.
    #: A bare year may be shorter (`1` is year 1), which is how the family's other
    #: projects author "available from the start".
    DATE_PATTERN = re.compile(r"^(\d{1,4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?$")

    #: Graphics callback names a candidate may point at its own NML. These are the keys
    #: the collator/`graphics {}` block accepts; an unknown name is a typo that would
    #: otherwise emit an unrecognised callback and abort the GRF compile much later.
    NML_OVERRIDE_CALLBACKS = frozenset(
        {
            "default",
            "purchase",
            "rotor",
            "random_trigger",
            "cargo_subtype_text",
            "additional_text",
            "colour_mapping",
            "start_stop",
            "every_32_days",
            "sound_effect",
            "articulated_part",
            "can_attach_wagon",
            "refit_cost",
            "create_effect",
            "reverse_build_probability",
            "refit",
            "loading_speed",
            "speed",
            "cost_factor",
            "running_cost_factor",
            "cargo_age_period",
            "cargo_capacity",
            "passenger_capacity",
            "mail_capacity",
            "range",
            "visual_effect_and_powered",
            "visual_effect",
        }
    )

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

        vehicle_type = VehicleLoader._parse_vehicle_type(raw_vehicle_type)
        
        raw_train_type = stats.get("train_type", "").upper()
        if raw_train_type == "":
            raise ValueError(f"Missing required stat 'train_type' in {path}")

        try:
            # First try to parse as enum member (e.g., "LOCOMOTIVE" or "FREIGHT_WAGON")
            train_type = TrainType[raw_train_type.upper()]
        except KeyError:
            # If that fails, try to parse as raw value (e.g., "locomotive" or "freight_wagon")
            train_type = TrainType(raw_train_type)

        cargo_classes = parse_cargo(data.get("cargo"), f"'cargo' in {path}")
        non_cargo_classes = parse_cargo(
            data.get("non_cargo_classes"), f"'non_cargo_classes' in {path}", presets=False
        )

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
            tilt=stats.get("tilt"),

            power=stats.get("power"),
            speed=stats.get("speed"),
            design_speed=stats.get("design_speed"),
            tractive_effort=stats.get("tractive_effort"),
            capacity = stats.get("capacity"),

            cargo_classes=cargo_classes,
            non_cargo_classes=non_cargo_classes,
            default_cargo_type=VehicleLoader._parse_default_cargo_type(
                data.get("default_cargo_type"), path
            ),
            autorefit=data.get("autorefit") or stats.get("autorefit"),
            power_type=stats.get("power_type"),

            size=stats.get("size") or data.get("size"),
            num_vehicles=stats.get("num_vehicles") or data.get("num_vehicles"),
            sprite_override=data.get("sprite_override"),
            sprite_exclude=data.get("sprite_exclude"),

            introduction_date=VehicleLoader._parse_introduction_date(
                dates.get("introduction_date") or data.get("introduction_date"), path
            ),

            model_life=data.get("model_life"),
            retire_early=data.get("retire_early"),
            vehicle_life=data.get("vehicle_life"),
            cargo_age_period=data.get("cargo_age_period"),
            loading_speed=data.get("loading_speed"),
            # Accept either the root or `stats` block, since authoring one way and
            # meaning the other is an easy mistake and both are read as vehicle-level.
            sound_effect=data.get("sound_effect") or stats.get("sound_effect"),
            visual_effect=data.get("visual_effect") or stats.get("visual_effect"),
            engine_class=data.get("engine_class") or stats.get("engine_class"),

            special_tags = data.get("special_tags", {}),
            nml_override=VehicleLoader._parse_nml_override(data.get("nml_override"), path),

            profiles=profiles,
            liveries=liveries,
        )

    @staticmethod
    def _parse_introduction_date(raw: Any, where: str) -> str | None:
        """Render `introduction_date` as the NML date expression it has to be.

        A bare `1990-08-01` is *not* a date to NML: it parses as the arithmetic
        expression 1990 - 8 - 1 and compiles to 1981 days, i.e. the year 5, so every
        vehicle authored that way silently becomes available from the start of the
        game instead of on its introduction date. Accept a year (`1952`), `YYYY-MM`
        or `YYYY-MM-DD` and emit `date(year, month, day)`; an explicit `date(...)`
        expression is passed through so a project can still be precise.
        """
        if raw is None:
            return None

        # YAML types a bare `1952-04-21` as a date object, not a string.
        if isinstance(raw, _datetime):
            return f"date({raw.year}, {raw.month}, {raw.day})"
        if isinstance(raw, _date):
            return f"date({raw.year}, {raw.month}, {raw.day})"

        if isinstance(raw, bool) or not isinstance(raw, (int, str)):
            raise ValueError(
                f"'introduction_date: {raw}' in {where} must be a year, "
                f"'YYYY-MM' or 'YYYY-MM-DD'"
            )

        text = str(raw).strip()
        if not text:
            return None

        match = VehicleLoader.DATE_PATTERN.match(text)
        if match:
            year = int(match.group(1))
            month = int(match.group(2) or 1)
            day = int(match.group(3) or 1)
            if not 1 <= month <= 12 or not 1 <= day <= 31:
                raise ValueError(
                    f"'introduction_date: {raw}' in {where} is not a valid date"
                )
            return f"date({year}, {month}, {day})"

        if re.fullmatch(r"date\s*\(.*\)", text):
            return text

        raise ValueError(
            f"'introduction_date: {raw}' in {where} is not understood. Write a year "
            f"('1952'), 'YYYY-MM-DD' ('1952-04-21'), or an explicit date(...) expression."
        )

    @staticmethod
    def _parse_default_cargo_type(raw: Any, where: str) -> str | None:
        """Validate `default_cargo_type`.

        A cargo *label* (such as `GOOD`) is only a known identifier when the GRF declares a
        `cargotable`, which BRBuild does not generate yet, so naming one would abort the
        whole compile with `Unknown identifier 'GOOD'`. Only NML's own label-free constant
        is accepted for now.
        """
        if raw is None:
            return None

        value = str(raw).strip().upper()
        if not value:
            return None
        if value == "DEFAULT_CARGO_FIRST_REFITTABLE":
            return value

        raise ValueError(
            f"'default_cargo_type: {raw}' in {where} names a cargo label, but BRBuild does not "
            f"generate a cargotable, so only 'DEFAULT_CARGO_FIRST_REFITTABLE' can be used. "
            f"Refittability comes from the cargo classes."
        )

    @staticmethod
    def _parse_nml_override(raw: Any, where: str) -> Dict[str, str] | None:
        """Validate an `nml_override` block: graphics callback name -> NML target.

        The value is emitted verbatim as the callback's target, so it is normally the
        name of a switch declared in the candidate's own `.pnml` file. A typo in the
        callback name would otherwise produce a silent no-op, so names are checked here
        and an unknown one fails the load.
        """
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise ValueError(f"'nml_override' in {where} must be a mapping of callback name to NML target")

        parsed: Dict[str, str] = {}
        for name, value in raw.items():
            callback = str(name).strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", callback):
                raise ValueError(f"'nml_override' in {where} has an invalid callback name {name!r}")
            if callback not in VehicleLoader.NML_OVERRIDE_CALLBACKS:
                known = ", ".join(sorted(VehicleLoader.NML_OVERRIDE_CALLBACKS))
                raise ValueError(
                    f"'nml_override' in {where} sets unknown callback '{callback}'. "
                    f"Known callbacks: {known}"
                )
            if isinstance(value, bool) or not isinstance(value, (str, int, float)):
                raise ValueError(
                    f"'nml_override.{callback}' in {where} must be an NML switch or expression, "
                    f"got {value!r}"
                )
            target = str(value).strip()
            if not target:
                raise ValueError(f"'nml_override.{callback}' in {where} must not be empty")
            parsed[callback] = target

        return parsed or None

    @staticmethod
    def _parse_vehicle_type(raw_vehicle_type: Any) -> VehicleType:
        try:
            return VehicleType[str(raw_vehicle_type).upper()]
        except (KeyError, AttributeError):
            raise ValueError(
                f"Invalid value '{raw_vehicle_type}' for vehicle type."
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
            sprite_group=p.get("sprite_group"),
            capacity=p.get("capacity"),
            power=p.get("power"),
            speed=p.get("speed"),
            design_speed=p.get("design_speed"),
            weight=p.get("weight"),
            introduction_date=VehicleLoader._parse_introduction_date(
                p.get("introduction_date"), f"'introduction_date' in profile {identifier}"
            ),
            tilt=p.get("tilt"),
            sound_effect=p.get("sound_effect"),
            visual_effect=p.get("visual_effect"),
            types=[
                VehicleLoader._parse_vehicle_type(vehicle_type)
                for vehicle_type in (p.get("types") or [])
            ] or None,
            cargo_classes=parse_cargo(p.get("cargo"), f"'cargo' in profile {identifier}"),
            nml_override=VehicleLoader._parse_nml_override(p.get("nml_override"), f"profile {identifier}"),
            special_tags=p.get("special_tags"),
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
            power=lv.get("power"),
            speed=lv.get("speed"),
            design_speed=lv.get("design_speed"),
            weight=lv.get("weight"),
            tilt=lv.get("tilt"),
            sound_effect=lv.get("sound_effect"),
            visual_effect=lv.get("visual_effect"),
            nml_override=VehicleLoader._parse_nml_override(lv.get("nml_override"), f"livery {name}"),
            special_tags=lv.get("special_tags"),
        )