from enum import Enum


class DoorType(Enum):
    """Passenger-door arrangement used by loading-speed calculations."""

    INTERCITY = "intercity"
    COMMUTER_DOUBLE = "commuter_double"
    COMMUTER_TRIPLE = "commuter_triple"
    MULTIPLE = "multiple"
    SLAM = "slam"

    @classmethod
    def from_identifier(cls, raw: str) -> "DoorType":
        try:
            return cls[str(raw).strip().upper()]
        except (KeyError, AttributeError):
            raise ValueError(f"Invalid doors '{raw}'.")
