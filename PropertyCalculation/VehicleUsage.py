from enum import Enum


class VehicleUsage(Enum):
    """Operational usage category used by project-specific feature filters."""

    TRAM = "TRAM"
    TRAM_TRAIN = "TRAM_TRAIN"
    LIGHT_RAIL = "LIGHT_RAIL"
    UNDERGROUND = "UNDERGROUND"
    METRO = "METRO"
    SUBURBAN = "SUBURBAN"
    COMMUTER = "COMMUTER"
    LOCAL = "LOCAL"
    REGIONAL = "REGIONAL"
    INTERCITY = "INTERCITY"
    HIGH_SPEED = "HIGH_SPEED"

    @classmethod
    def from_identifier(cls, raw: str) -> "VehicleUsage":
        try:
            return cls[str(raw).strip().upper()]
        except (KeyError, AttributeError):
            raise ValueError(f"Invalid vehicle usage '{raw}'.")
