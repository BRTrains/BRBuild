from .FuelType import FuelType
from .TrainType import TrainType
from .WagonType import WagonType
from Grf import COST_SCORE_MAX


CALLBACK_MAX = 65535

# Reference values for the normalised cost model. Values above a reference saturate
# that component at 1.0; COST_SCORE_MAX is the shared callback-score scale.
SPEED_REFERENCE_MPH = 250.0
POWER_REFERENCE_HP = 21000.0
MU_CAPACITY_REFERENCE = 1500.0
STOCK_CAPACITY_REFERENCE = 250.0
FORMATION_REFERENCE = 16.0

LOCOMOTIVE_WEIGHTS = (0.65, 0.35)  # power, speed
MU_WEIGHTS = (0.40, 0.30, 0.25, 0.05)  # power, capacity, speed, unit overhead
COACH_WEIGHTS = (0.65, 0.35)  # capacity, speed
WAGON_WEIGHTS = (0.65, 0.35)  # capacity, speed


class CostCalculator:
    def __init__(self, variant):
        raw_speed = getattr(variant, "speed", None) or variant.get_attr("speed")
        self.speed: float = float(raw_speed) if raw_speed is not None else 100.0

        raw_power = getattr(variant, "power", None) or variant.get_attr("power")
        self.power: float = float(raw_power) if raw_power is not None else 0.0

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
        """Return the normalised, unscaled callback score for one vehicle."""
        speed = self._proportion(self.speed, SPEED_REFERENCE_MPH)
        power = self._proportion(self.power, POWER_REFERENCE_HP)

        if self._train_type_name == TrainType.WAGON.name:
            capacity = self._proportion(self.capacity, STOCK_CAPACITY_REFERENCE)
            index = WAGON_WEIGHTS[0] * capacity + WAGON_WEIGHTS[1] * speed
        elif self._train_type_name == TrainType.COACH.name:
            capacity = self._proportion(self.capacity, STOCK_CAPACITY_REFERENCE)
            index = COACH_WEIGHTS[0] * capacity + COACH_WEIGHTS[1] * speed
        elif self._train_type_name == TrainType.MULTIPLE_UNIT.name:
            capacity = self._proportion(self.capacity, MU_CAPACITY_REFERENCE)
            overhead = 1.0 / min(self.num_vehicles, FORMATION_REFERENCE)
            index = (
                MU_WEIGHTS[0] * power
                + MU_WEIGHTS[1] * capacity
                + MU_WEIGHTS[2] * speed
                + MU_WEIGHTS[3] * overhead
            )
        else:
            index = LOCOMOTIVE_WEIGHTS[0] * power + LOCOMOTIVE_WEIGHTS[1] * speed

        return COST_SCORE_MAX * index

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
