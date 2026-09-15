from .FuelType import FuelType
from .WagonType import WagonType


class CostCalculator:
    def __init__(self, variant):
        raw_speed = getattr(variant, "speed", None) or variant.get_attr("speed")
        self.speed: float = float(raw_speed) if raw_speed is not None else 100.0

        raw_power = getattr(variant, "power", None) or variant.get_attr("power")
        self.power: float = float(raw_power) if raw_power is not None else 0.0

        raw_size = variant.get_attr("size") or getattr(variant, "size", None)
        self.size: float = float(raw_size) if raw_size is not None else 1.0

        raw_capacity = variant.get_attr("capacity") or getattr(variant, "capacity", None)
        self.capacity: float = float(raw_capacity) if raw_capacity is not None else 0.0

        if getattr(variant, "fuel_type", None) is not None:
            self.fuel_type = variant.fuel_type
        elif variant.get_attr("fuel_type") is not None:
            self.fuel_type = variant.get_attr("fuel_type")
        else:
            self.fuel_type = FuelType.DIESEL

        if variant.get_attr("wagon_type") is not None:
            self.wagon_type = variant.wagon_type
        elif self.power == 0:
            self.wagon_type = WagonType.COACH
        else:
            self.wagon_type = None

    def base_performance_cost(self) -> float:
        speed = max(1.0, self.speed)
        size = max(1.0, self.size)
        power = max(0.0, self.power)
        capacity = max(0.0, self.capacity)

        if power > 0:
            # Powered vehicles (locomotives / power units)
            return (
                (speed / 250.0) * 0.5 +
                (power / size / 3000.0) * 0.5
            )
        else:
            # Unpowered vehicles (coaches / wagons)
            return (
                (speed / 250.0) * 0.4 +
                (capacity / 100.0) * 0.4 +
                (size / 8.0) * 0.2
            )

    # Ensure the final cost value is an integer between 0 and 255, as required by NML.
    def clean_value(self, value: float, allow_zero: bool = False) -> int:
        min_val = 0 if allow_zero else 1
        return int(max(min_val, min(255, value)))

    def running_cost(
        self,
        allow_zero: bool = False,
    ) -> int:
        base = self.base_performance_cost()
        modifier = 1.0

        if self.fuel_type is not None:
            modifier *= self.fuel_type.running_multiplier

        if self.wagon_type is not None:
            modifier *= self.wagon_type.running_multiplier

        value = base * modifier * 254 + (0 if allow_zero else 1)
        return self.clean_value(value, allow_zero=allow_zero)

    def purchase_cost(
        self,
        allow_zero: bool = False,
    ) -> int:
        base = self.base_performance_cost()
        modifier = 1.0

        if self.fuel_type is not None:
            modifier *= self.fuel_type.purchase_multiplier

        if self.wagon_type is not None:
            modifier *= self.wagon_type.purchase_multiplier

        value = base * modifier * 254 + (0 if allow_zero else 1)
        return self.clean_value(value, allow_zero=allow_zero)