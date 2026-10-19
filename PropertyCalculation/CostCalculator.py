from .FuelType import FuelType
from .TrainType import TrainType
from .WagonType import WagonType
from Grf import COST_SCORE_MAX


CALLBACK_MAX = 65535

# OpenTTD's train and wagon purchase bases differ by 200x. These factors are in
# callback units, not percentages: a wagon/coach must use a larger factor to reach
# a sensible absolute price than a powered train vehicle.
WAGON_BASE_FACTOR = 4200.0
COACH_BASE_FACTOR = 3300.0


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

        raw_num_vehicles = variant.get_attr("num_vehicles") or getattr(variant, "num_vehicles", None)
        self.num_vehicles: float = max(1.0, float(raw_num_vehicles or 1))

        self.train_type = getattr(variant, "train_type", None) or variant.get_attr("train_type")
        self.cost_scale = float(
            getattr(variant, "cost_scale", None)
            or getattr(getattr(variant, "vehicle", None), "cost_scale", None)
            or 1.0
        )

        if getattr(variant, "fuel_type", None) is not None:
            self.fuel_type = variant.fuel_type
        elif variant.get_attr("fuel_type") is not None:
            self.fuel_type = variant.get_attr("fuel_type")
        else:
            self.fuel_type = FuelType.DIESEL

        if variant.get_attr("wagon_type") is not None:
            self.wagon_type = variant.wagon_type
        elif self.power == 0:
            self.wagon_type = WagonType.COACH if self._is_coach else WagonType.FREIGHT_WAGON
        else:
            self.wagon_type = None

    @property
    def _train_type_name(self) -> str:
        value = self.train_type
        return str(getattr(value, "name", value or "")).upper().replace(" ", "_")

    @property
    def _is_coach(self) -> bool:
        return self._train_type_name == TrainType.COACH.name

    @staticmethod
    def _proportion(value: float, maximum: float) -> float:
        return max(0.0, min(1.0, value / maximum))

    def base_performance_cost(self) -> float:
        """Return the unscaled callback factor for one vehicle.

        Wagon and coach factors are deliberately much larger than powered-train
        factors because OpenTTD uses a £2,000 purchase base for both, versus
        £400,000 for locomotives and powered MU parts.
        """
        speed = self._proportion(self.speed, 200.0)
        power = self._proportion(self.power, 21000.0)
        capacity = self._proportion(self.capacity, 120.0)
        size = self._proportion(self.size, 8.0)

        if self._train_type_name == TrainType.WAGON.name:
            # Freight stock stays below passenger stock despite capacity.
            return WAGON_BASE_FACTOR * (1.0 + 0.25 * speed + 0.50 * capacity + 0.15 * size)

        if self._train_type_name == TrainType.COACH.name:
            return COACH_BASE_FACTOR * (1.0 + 0.25 * speed + 0.50 * capacity + 0.10 * size)

        if self._train_type_name == TrainType.MULTIPLE_UNIT.name:
            # The fixed unit overhead is spread across its cars: two short
            # coupled MUs therefore cost more than one long MU with the same
            # car count.
            return 20.0 / self.num_vehicles + 90.0 + 15.0 * speed + 35.0 * power + 10.0 * capacity

        # Locomotives carry the strongest power weighting and a modest speed/size
        # contribution. The result is a per-locomotive factor.
        return 180.0 + 80.0 * power + 40.0 * speed + 10.0 * size

    def _apply_scale(self, value: float) -> int:
        return self.clean_value(min(COST_SCORE_MAX, value) * self.cost_scale, allow_zero=False)

    def clean_value(self, value: float, allow_zero: bool = False) -> int:
        min_val = 0 if allow_zero else 1
        return int(max(min_val, min(CALLBACK_MAX, round(value))))

    def runtime_expression(self, value: int, parameter: str) -> str:
        """Return the callback expression for one runtime cost parameter."""
        values = [
            max(1, round(value / 4)),
            max(1, round(value / 3)),
            max(1, round(value / 2)),
            value,
            value * 2,
            value * 3,
            value * 4,
        ]
        expression = str(values[-1])
        for index in range(len(values) - 2, -1, -1):
            expression = f"{parameter} == {index} ? {values[index]} : {expression}"
        return expression

    def running_cost(self, allow_zero: bool = False) -> int:
        base = self.base_performance_cost()
        modifier = 1.0

        if self.fuel_type is not None:
            modifier *= self.fuel_type.running_multiplier

        if self.wagon_type is not None:
            modifier *= self.wagon_type.running_multiplier

        return self._apply_scale(base * modifier)

    def purchase_cost(self, allow_zero: bool = False) -> int:
        base = self.base_performance_cost()
        modifier = 1.0

        if self.fuel_type is not None:
            modifier *= self.fuel_type.purchase_multiplier

        if self.wagon_type is not None:
            modifier *= self.wagon_type.purchase_multiplier

        return self._apply_scale(base * modifier)
