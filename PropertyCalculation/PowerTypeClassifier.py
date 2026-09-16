from typing import List, Set, Any
from Badge import BadgeRegistry
from PropertyCalculation.FuelType import FuelType
from PropertyCalculation.VehicleType import VehicleType


class PowerTypeClassifier:
    """Parses power and fuel types for a Variant, assigning NML engine classes,
    badges, multi-mode classifications, and FuelType enums.
    """

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

        modes = 0
        detected_fuels: Set[FuelType] = set()
        engine_class = None

        # 1. STEAM
        if "STEAM" in tokens:
            modes += 1
            detected_fuels.add(FuelType.STEAM)
            engine_class = "ENGINE_CLASS_STEAM"
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
            if engine_class is None:
                engine_class = "ENGINE_CLASS_ELECTRIC"
            self._add_badge("Power/Hydrogen")

        # 4. BATTERY
        if "BATTERY" in tokens:
            modes += 1
            detected_fuels.add(FuelType.BATTERY)
            if engine_class is None:
                engine_class = "ENGINE_CLASS_ELECTRIC"
            self._add_badge("Power/Battery")

        # 5. ELECTRIC
        electric_tokens = {"ELECTRIC", "OHLE", "OVERHEAD", "CATENARY", "3RD_RAIL", "THIRD_RAIL", "4TH_RAIL", "FOURTH_RAIL"}
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
            ohle_types = {"OHLE", "OHLE_25KV", "OVERHEAD", "CATENARY", "DUAL", "DUAL_VOLTAGE"}
            if any(t in ohle_types for t in tokens):
                self.variant.is_ohle = True
                self._add_badge("Power/delivery/OHLE")
                self._add_badge("Power/current/AC")
                voltages += 1

            third_rail_types = {"THIRD_RAIL", "THIRD", "3RD_RAIL", "3RD", "BR_3RDR", "3RDR", "BR_3RDC", "3RDC", "DUAL", "DUAL_VOLTAGE"}
            if any(t in third_rail_types for t in tokens):
                self.variant.is_third_rail = True
                self._add_badge("Power/delivery/3rd_Rail")
                self._add_badge("Power/voltage/750V")
                self._add_badge("Power/current/DC")
                voltages += 1

            fourth_rail_types = {"FOURTH_RAIL", "FOURTH", "4TH_RAIL", "4TH", "4RDR"}
            if any(t in fourth_rail_types for t in tokens):
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

        if engine_class:
            self.variant.properties["engine_class"] = engine_class

        self.variant.fuel_type = fuel_enum
        self._apply_tram_rule()
        return fuel_enum

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
        elif hasattr(v_type, "name") and str(v_type.name).upper() in ("TRAM", "ROADVEH"):
            is_tram = True

        if is_tram:
            self.variant.properties.pop("engine_class", None)
