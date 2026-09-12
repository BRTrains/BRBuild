import logging

logger = logging.getLogger(__name__)


class Physics:
    def __init__(self):
        pass

    def calculate_TE_coefficient(self, tractive_effort, weight, is_road_vehicle: bool = False) -> float:
        if tractive_effort is None or weight is None:
            logger.warning(f"Tractive effort ({tractive_effort}) or weight ({weight}) is None. Defaulting TE coefficient to 0.0.")
            return 0.0

        if weight <= 0 or tractive_effort <= 0:
            return 0.0

        if tractive_effort < 1:
            # Value in YAML already a coefficient
            return max(0.0, min(1.0, float(tractive_effort)))

        gravity = 10.0 if is_road_vehicle else 9.8
        target_TE = float(tractive_effort)

        TE_coefficient = target_TE / weight / gravity

        if TE_coefficient > 1.0:
            logger.warning(
                f"Calculated TE coefficient {TE_coefficient:.5f} is greater than 1. Capping TE coefficient at 1.0."
            )
            TE_coefficient = 1.0

        return round(TE_coefficient, 5)

    def calculate_AD_coefficient(self, speed_mph) -> float:
        if speed_mph is None or speed_mph <= 0:
            return 0.0

        speed_kmh = float(speed_mph) * 1.60934
        if speed_kmh <= 0:
            return 0.0

        # OpenTTD aerodynamic drag formula: 8 / max_speed_kmh
        AD_coefficient = 8.0 / speed_kmh

        # NML Specification: Air drag coefficient is clamped to 0.004..0.75
        clamped_AD = max(0.004, min(0.75, AD_coefficient))

        return round(clamped_AD, 5)