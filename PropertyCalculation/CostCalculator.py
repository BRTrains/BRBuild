from .FuelType import FuelType
from .WagonType import WagonType


class CostCalculator:
    def __init__(self):
        pass

    def base_performance_cost(self, speed: float, power: float, num_vehs: int, capacity: float) -> float:
        num_vehs = max(1, num_vehs)
        return (
            (speed / 250.0) * 0.4 +
            (power / num_vehs / 3000.0) * 0.4 +
            (capacity / 1000.0) * 0.2
        )

    # Ensure the final cost value is an integer between 0 and 255, as required by NML.
    def clean_value(self, value: float, allow_zero: bool = False) -> int:
        min_val = 0 if allow_zero else 1
        return int(max(min_val, min(255, value)))

    def running_cost(
        self,
        speed: float,
        power: float,
        num_vehs: int,
        capacity: float,
        fuel_type: FuelType | None = None,
        wagon_type: WagonType | None = None,
        allow_zero: bool = False,
    ) -> int:
        base = self.base_performance_cost(speed, power, num_vehs, capacity)
        modifier = 1.0

        if fuel_type is not None:
            modifier *= fuel_type.running_multiplier

        if wagon_type is not None:
            modifier *= wagon_type.running_multiplier

        value = base * modifier * 254 + (0 if allow_zero else 1)
        return self.clean_value(value, allow_zero=allow_zero)

    def purchase_cost(
        self,
        speed: float,
        power: float,
        num_vehs: int,
        capacity: float,
        fuel_type: FuelType | None = None,
        wagon_type: WagonType | None = None,
        allow_zero: bool = False,
    ) -> int:
        base = self.base_performance_cost(speed, power, num_vehs, capacity)
        modifier = 1.0

        if fuel_type is not None:
            modifier *= fuel_type.purchase_multiplier

        if wagon_type is not None:
            modifier *= wagon_type.purchase_multiplier

        value = base * modifier * 254 + (0 if allow_zero else 1)
        return self.clean_value(value, allow_zero=allow_zero)


if __name__ == "__main__":
    calculator = CostCalculator()

    print("Example calculation for a steam locomotive with speed=100, power=3000, num_vehs=1, capacity=500:")
    print(f"Purchase cost: {calculator.purchase_cost(100, 3000, 1, 500, fuel_type=FuelType.DIESEL)}")
    print(f"Running cost: {calculator.running_cost(100, 3000, 1, 500, fuel_type=FuelType.DIESEL)}")