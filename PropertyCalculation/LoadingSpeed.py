from PropertyCalculation.DoorType import DoorType


# These values stay within the loading_speed range used by BRTrains2 passenger stock:
# intercity examples commonly used 10, while commuter stock used 20-30.
DOOR_LOADING_SPEEDS = {
    DoorType.INTERCITY: 10,
    DoorType.COMMUTER_DOUBLE: 20,
    DoorType.COMMUTER_TRIPLE: 25,
    DoorType.MULTIPLE: 30,
}

COMMUTER_USAGES = {
    "TRAM",
    "TRAM_TRAIN",
    "LIGHT_RAIL",
    "UNDERGROUND",
    "METRO",
    "SUBURBAN",
    "COMMUTER",
    "LOCAL",
}


def _usage_names(usage):
    values = usage if isinstance(usage, (list, tuple)) else [usage]
    return {
        getattr(value, "name", str(value)).strip().upper()
        for value in values
        if value is not None
    }


def _inferred_base_door(usage, speed, train_type, cargo_classes):
    names = _usage_names(usage)
    if names:
        return (
            DoorType.COMMUTER_DOUBLE
            if names & COMMUTER_USAGES
            else DoorType.INTERCITY
        )

    train_type_name = getattr(train_type, "name", str(train_type)).upper()
    is_passenger = "CC_PASSENGERS" in (cargo_classes or [])
    if speed is None:
        if train_type_name == "COACH" or is_passenger:
            return DoorType.INTERCITY
        return None
    return DoorType.INTERCITY if float(speed) > 100 else DoorType.COMMUTER_DOUBLE


def loading_speed_for(
    *, doors=None, usage=None, speed=None, train_type=None, cargo_classes=None
):
    """Return the inferred loading speed, or None for non-passenger stock without a signal."""
    explicit_slam = doors is DoorType.SLAM
    base_door = (
        None
        if explicit_slam
        else doors
    ) or _inferred_base_door(usage, speed, train_type, cargo_classes)
    if base_door is None:
        return None

    base_speed = DOOR_LOADING_SPEEDS[base_door]
    return (base_speed * 2) // 3 if explicit_slam else base_speed
