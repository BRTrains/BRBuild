from .FuelType import FuelType
from .WagonType import WagonType


class CostCalculator:
    def __init__(self, variant): 
        if variant.speed is not None:
            self.speed = variant.speed
        else:
            self.speed = 100
        
        if variant.power is not None:
            self.power = variant.power
        else:
            self.power = 0

        if variant.get_attr("size") is not None:
            self.size = variant.get_attr("size")
        else:
            self.size = 1

        if variant.get_attr("capacity") is not None:
            self.capacity = variant.get_attr("capacity")
        else:
            self.capacity = 0

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
        if self.speed == 0 or self.speed is None:
            self.speed = 1

        self.size = max(1, self.size)

        if self.power > 0:
            # Powered vehicles (locomotives / power units)
            return (
                (self.speed / 250.0) * 0.5 +
                (self.power / self.size / 3000.0) * 0.5
            )
        else:
            # Unpowered vehicles (coaches / wagons)
            return (
                (self.speed / 250.0) * 0.4 +
                (self.capacity / 100.0) * 0.4 +
                (self.size / 8.0) * 0.2
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