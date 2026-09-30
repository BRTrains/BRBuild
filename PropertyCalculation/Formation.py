"""Derive formation badges from the authored vehicle facts."""

from PropertyCalculation.TrainType import TrainType


def _is_steam(power_type) -> bool:
    if isinstance(power_type, str):
        values = [power_type]
    else:
        values = power_type or []
    return any(str(value).strip().upper() in {"STEAM", "STEAM_DIESEL"} for value in values)


def formation_tag(train_type, power, cargo_classes, power_type, num_vehicles=None, size=None):
    """Return the automatic formation badge path, or ``None`` when it is undefined.

    Formation is based on the resolved variant facts, not on a hand-authored badge. Coaches
    and wagons are single unpowered vehicles; powered stock carrying cargo is a multiple unit;
    powered stock without cargo is a locomotive.
    """
    count = num_vehicles if num_vehicles is not None else size
    count = int(count) if count is not None else 1
    powered = power is not None and float(power) > 0
    carries_cargo = bool(cargo_classes)

    if train_type in (TrainType.COACH, TrainType.WAGON):
        return f"formation/{count}-car"

    if powered and carries_cargo:
        return f"formation/{count}-car"

    if powered and not carries_cargo:
        if _is_steam(power_type) and count == 1:
            return "formation/tank_engine"
        if _is_steam(power_type) and count == 2:
            return "formation/engine+tender"
        return "formation/locomotive"

    if not powered and carries_cargo and count == 1:
        return "formation/1-car"

    return None
