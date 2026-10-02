from typing import List, Set, Any
from Badge import BadgeRegistry
from PropertyCalculation.FuelDefaults import FuelDefaults
from PropertyCalculation.FuelType import FuelType
from PropertyCalculation.VehicleType import VehicleType


class PowerTypeClassifier:
    """Parses power and fuel types for a Variant, assigning NML engine classes,
    badges, multi-mode classifications, and FuelType enums.
    """

    #: Tokens that name a self-powered traction mode: these run on any rail.
    SELF_POWERED_TOKENS = frozenset(
        {
            "STEAM",
            "DIESEL",
            "DIESEL_HYDRAULIC",
            "DIESEL_ELECTRIC",
            "DIESEL_MECHANICAL",
            "HYDRAULIC",
            "MECHANICAL",
            "HYDROGEN",
            "BATTERY",
            "GAS_TURBINE",
            "GAS_TURBINE_ELECTRIC",
            "TURBINE",
        }
    )

    #: Tokens naming an overhead (catenary) supply.
    OHLE_TOKENS = frozenset({"OHLE", "OHLE_25KV", "OVERHEAD", "CATENARY", "DUAL", "DUAL_VOLTAGE"})

    #: Tokens naming a third-rail supply.
    THIRD_RAIL_TOKENS = frozenset(
        {"THIRD_RAIL", "THIRD", "3RD_RAIL", "3RD", "BR_3RDR", "3RDR", "BR_3RDC", "3RDC", "DUAL", "DUAL_VOLTAGE"}
    )

    #: Tokens naming a fourth-rail supply.
    FOURTH_RAIL_TOKENS = frozenset(
        {"FOURTH_RAIL", "FOURTH", "4TH_RAIL", "4TH", "4RDR"}
    )

    #: Any token that implies an externally electrified supply.
    ELECTRIC_TOKENS = frozenset(
        {"ELECTRIC", "OHLE", "OVERHEAD", "CATENARY", "3RD_RAIL", "THIRD_RAIL", "4TH_RAIL", "FOURTH_RAIL"}
    )

    def __init__(self, variant: Any):
        self.variant = variant

    def process(self) -> FuelType:
        raw_power = self.variant.get_attr("power_type") or self.variant.get_attr("fuel_type")
        tokens = self._extract_tokens(raw_power)

        # Initialize variant flags
        self.variant.is_electric = False
        self.variant.is_ohle = False
        self.variant.is_third_rail = False
        self.variant.is_fourth_rail = False
        self.variant.is_dual_voltage = False
        self.variant.is_multi_mode = False

        # Check for unpowered condition
        is_explicit_unpowered = any(t in ("NONE", "UNPOWERED") for t in tokens)
        has_no_power = (getattr(self.variant, "power", None) == 0) and not tokens

        if is_explicit_unpowered or has_no_power or not tokens:
            self.variant.fuel_type = FuelType.UNPOWERED
            self._add_badge("Power/Unpowered")
            self._apply_tram_rule()
            return FuelType.UNPOWERED

        # A traction mode is a distinct way the vehicle makes power: steam, diesel,
        # hydrogen, battery, gas turbine or an electric supply. Two or more modes make
        # the vehicle bi-/tri-mode. Electric-only supply distinctions (OHLE, third rail)
        # are not separate modes.
        modes = 0
        detected_fuels: Set[FuelType] = set()
        # Preferred engine class. An explicit `engine_class` from the YAML always wins, so
        # it is tracked separately from the per-fuel defaults explored below. It is
        # emitted only if the vehicle has one traction mode; multi-mode traction relies on
        # the per-fuel presentation defaults instead.
        engine_class = self.variant.get_attr("engine_class")
        explicit_engine_class = engine_class is not None

        # 1. STEAM
        if "STEAM" in tokens:
            modes += 1
            detected_fuels.add(FuelType.STEAM)
            engine_class = engine_class or FuelDefaults.engine_class(FuelType.STEAM)
            self._add_badge("Power/Steam")

        # 2. DIESEL
        has_diesel = any(t in tokens for t in ("DIESEL", "DIESEL_HYDRAULIC", "DIESEL_ELECTRIC", "DIESEL_MECHANICAL"))
        if has_diesel:
            modes += 1
            detected_fuels.add(FuelType.DIESEL)
            if engine_class is None:
                engine_class = "ENGINE_CLASS_DIESEL"
            self._add_badge("Power/diesel")

            if any(t in ("HYDRAULIC", "DIESEL_HYDRAULIC") for t in tokens):
                self._add_badge("Power/diesel_hydraulic")
            if any(t in ("DIESEL_ELECTRIC",) for t in tokens) or ("ELECTRIC" in tokens and "DIESEL" in tokens):
                self._add_badge("Power/diesel_electric")

        # 3. HYDROGEN
        if "HYDROGEN" in tokens:
            modes += 1
            detected_fuels.add(FuelType.HYDROGEN)
            engine_class = engine_class or FuelDefaults.engine_class(FuelType.HYDROGEN)
            self._add_badge("Power/Hydrogen")

        # 4. BATTERY
        if "BATTERY" in tokens:
            modes += 1
            detected_fuels.add(FuelType.BATTERY)
            engine_class = engine_class or FuelDefaults.engine_class(FuelType.BATTERY)
            self._add_badge("Power/Battery")

        # 5. GAS TURBINE
        # Not an OpenTTD concept. Approximated as self-powered with no catenary
        # requirement, which is what the diesel engine class gives.
        if any(t in ("GAS_TURBINE", "GAS_TURBINE_ELECTRIC", "TURBINE") for t in tokens):
            modes += 1
            detected_fuels.add(FuelType.GAS_TURBINE)
            engine_class = engine_class or FuelDefaults.engine_class(FuelType.GAS_TURBINE)
            self._add_badge("Power/Gas_turbine")

        # 6. ELECTRIC
        electric_tokens = self.ELECTRIC_TOKENS
        has_electric = any(t in tokens for t in electric_tokens) or any(t.startswith("OHLE") or "RAIL" in t for t in tokens)

        if has_electric:
            if "ELECTRIC" not in [f.name for f in detected_fuels]:
                modes += 1
                detected_fuels.add(FuelType.ELECTRIC)

            self.variant.is_electric = True
            if engine_class is None:
                engine_class = "ENGINE_CLASS_ELECTRIC"
            self._add_badge("Power/Electric")

            voltages = 0
            if any(t in self.OHLE_TOKENS for t in tokens):
                self.variant.is_ohle = True
                self._add_badge("Power/delivery/OHLE")
                self._add_badge("Power/current/AC")
                voltages += 1

            if any(t in self.THIRD_RAIL_TOKENS for t in tokens):
                self.variant.is_third_rail = True
                self._add_badge("Power/delivery/3rd_Rail")
                self._add_badge("Power/voltage/750V")
                self._add_badge("Power/current/DC")
                voltages += 1

            if any(t in self.FOURTH_RAIL_TOKENS for t in tokens):
                self.variant.is_fourth_rail = True
                self._add_badge("Power/delivery/4th_Rail")
                self._add_badge("Power/voltage/650V")
                self._add_badge("Power/current/DC")
                voltages += 1

            if voltages > 1 or "DUAL" in tokens or "DUAL_VOLTAGE" in tokens:
                self.variant.is_dual_voltage = True
                self._add_badge("Power/dual_voltage")

        # Multi-mode handling
        if modes >= 2:
            self.variant.is_multi_mode = True
            self._add_badge("Power/multi_mode")

        if modes == 2:
            self._add_badge("Power/bi_mode")
            fuel_enum = FuelType.BI_MODE
        elif modes == 3:
            self._add_badge("Power/tri_mode")
            fuel_enum = FuelType.TRI_MODE
        elif modes > 3:
            fuel_enum = FuelType.TRI_MODE
        elif modes == 1:
            fuel_enum = next(iter(detected_fuels)) if detected_fuels else FuelType.DIESEL
        else:
            fuel_enum = FuelType.UNPOWERED

        # An explicit engine class is always emitted verbatim. A per-fuel default is used
        # for single-mode traction, and for a multi-mode unit that has a diesel engine:
        # leaving the class unset is not neutral, because OpenTTD defaults a train's class
        # to steam, which gives steam particles, the steam departure sound and the steam
        # livery scheme. Diesel is the right class for such a unit — ENGINE_CLASS_ELECTRIC
        # would give overhead-wire effects on stock that also runs on plain rail, which is
        # what the legacy project recorded when it gave its bi-modes ENGINE_CLASS_DIESEL.
        if engine_class and (explicit_engine_class or modes == 1 or has_diesel):
            self.variant.properties["engine_class"] = engine_class

        self.variant.fuel_type = fuel_enum
        self.variant.default_track_types = self.track_types(tokens)
        self._apply_tram_rule()
        return fuel_enum

    def track_types(self, tokens: List[str]) -> List[str]:
        """The project track types this traction implies, in preference order.

        Used only when the variant itself names no `track_type`, so the mapping is a
        default rather than a decision: an explicit value always wins. Self-powered
        traction runs on any rail, so it asks for `RAIL`; each electric supply asks for
        the track type that supplies it, and a multi-system unit gets the union, best
        first (fourth rail, third rail, overhead).
        """
        track_types: List[str] = []
        self_powered = any(t in self.SELF_POWERED_TOKENS for t in tokens)
        # "ELECTRIC" alone means "an electric unit, supply unspecified", which is the
        # overhead case: third and fourth rail both have tokens of their own.
        overhead = any(t in self.OHLE_TOKENS for t in tokens) or "ELECTRIC" in tokens
        third = any(t in self.THIRD_RAIL_TOKENS for t in tokens)
        fourth = any(t in self.FOURTH_RAIL_TOKENS for t in tokens)

        if self_powered:
            track_types.append("RAIL")
        if fourth:
            track_types.append("FOURTH")
        if third:
            track_types.append("THIRD")
        if overhead and not (third or fourth):
            # An AC-only unit has no DC supply to fall back on, so it asks for overhead
            # electric in its own right. A unit that also has third or fourth rail
            # already reaches overhead track through that railtype's own fallback list.
            track_types.append("ELRL")

        return track_types or ["RAIL"]

    def _extract_tokens(self, raw: Any) -> List[str]:
        return self._tokenize(raw)

    @staticmethod
    def _tokenize(raw: Any) -> List[str]:
        if raw is None:
            return []

        tokens: List[str] = []
        if isinstance(raw, FuelType):
            tokens.append(raw.name)
        elif isinstance(raw, str):
            for part in raw.replace(",", " ").split():
                clean = part.strip().upper()
                if clean:
                    tokens.append(clean)
        elif isinstance(raw, (list, tuple, set)):
            for item in raw:
                tokens.extend(PowerTypeClassifier._tokenize(item))

        return tokens

    @staticmethod
    def is_ohle(power_type: Any) -> bool:
        """Return True if the given power/fuel type tokens indicate OHLE (overhead catenary)."""
        tokens = PowerTypeClassifier._tokenize(power_type)
        ohle_types = {"OHLE", "OHLE_25KV", "OVERHEAD", "CATENARY", "DUAL", "DUAL_VOLTAGE"}
        return any(t in ohle_types for t in tokens)

    def _add_badge(self, badge: str):
        registered = BadgeRegistry().add_badge(badge)
        if registered not in self.variant.badges:
            self.variant.badges.append(registered)

    def _apply_tram_rule(self):
        v_type = getattr(self.variant, "vehicle_type", None)
        is_tram = False
        if isinstance(v_type, VehicleType) and v_type == VehicleType.TRAM:
            is_tram = True
        elif hasattr(v_type, "name") and str(v_type.name).upper() == "TRAM":
            is_tram = True

        if is_tram:
            self.variant.properties.pop("engine_class", None)
