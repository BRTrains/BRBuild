"""Per-fuel presentation defaults.

OpenTTD has no hydrogen, battery or gas-turbine traction, so those types are
approximated. `PowerTypeClassifier` decides the physics side (engine class for track
purposes, badges, multi-mode counting); this module decides how the vehicle presents.

`engine_class` is the OpenTTD class used for livery colouring and, unless overridden,
the default sound and visual effect. The self-powered novel fuels approximate to diesel,
so they need no catenary; hydrogen and battery approximate to electric because they
drive electric traction motors.

`visual_effect` is a power unit's exhaust/idle effect. It is deliberately **off** for
hydrogen and battery: OpenTTD has no water-vapour effect and the legacy project disabled
particles on hydrogen for that reason, so showing diesel clag on an electric-drive unit
would be worse than showing nothing. Electric units keep theirs, which OpenTTD only
draws when the rails are actually powered.

Sound is *not* defaulted per fuel: OpenTTD's built-in sound set has no diesel, electric
or turbine entry (only `SOUND_DEPARTURE_*`, most of which are toyland). Anything
sound-like is either a callback switch or a `sound("file")` from the GRF itself, so it
belongs to the vehicle that provides it. Set `sound_effect` on the vehicle, profile or
livery to override the engine class's default.
"""

from __future__ import annotations

from typing import Optional

from .FuelType import FuelType


class FuelDefaults:
    """Engine class and visual-effect defaults for a `FuelType`."""

    # fuel -> (engine_class, visual_effect)
    DEFAULTS: dict[FuelType, tuple[Optional[str], Optional[str]]] = {
        FuelType.STEAM: ("ENGINE_CLASS_STEAM", "VISUAL_EFFECT_STEAM"),
        FuelType.DIESEL: ("ENGINE_CLASS_DIESEL", "VISUAL_EFFECT_DIESEL"),
        FuelType.ELECTRIC: ("ENGINE_CLASS_ELECTRIC", "VISUAL_EFFECT_ELECTRIC"),
        # A gas turbine is self-powered (no catenary) and burns fuel, but it does not
        # clag like a diesel: it is an electric-drive unit with a turbine generator, and
        # the legacy APT-E disabled particles for exactly that reason.
        FuelType.GAS_TURBINE: ("ENGINE_CLASS_DIESEL", "VISUAL_EFFECT_DISABLE"),
        FuelType.HYDROGEN: ("ENGINE_CLASS_ELECTRIC", "VISUAL_EFFECT_DISABLE"),
        FuelType.BATTERY: ("ENGINE_CLASS_ELECTRIC", "VISUAL_EFFECT_DISABLE"),
        # Multi-mode types are decided per consist, not per fuel, so they take the
        # electric defaults where a unit does not override them.
        FuelType.BI_MODE: ("ENGINE_CLASS_ELECTRIC", "VISUAL_EFFECT_ELECTRIC"),
        FuelType.TRI_MODE: ("ENGINE_CLASS_ELECTRIC", "VISUAL_EFFECT_ELECTRIC"),
    }

    @classmethod
    def for_fuel(cls, fuel: Optional[FuelType]) -> tuple[Optional[str], Optional[str]]:
        if fuel is None:
            return (None, None)
        return cls.DEFAULTS.get(fuel, (None, None))

    @classmethod
    def engine_class(cls, fuel: Optional[FuelType]) -> Optional[str]:
        return cls.for_fuel(fuel)[0]

    @classmethod
    def visual_effect(cls, fuel: Optional[FuelType]) -> Optional[str]:
        return cls.for_fuel(fuel)[1]
