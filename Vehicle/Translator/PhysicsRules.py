import logging
from PropertyCalculation import Physics, TrainType, VehicleType

logger = logging.getLogger(__name__)


class PhysicsRules:
    """Translates raw vehicle physics attributes (tractive effort, weight, speed, power)
    into OpenTTD/NML compliant physics coefficients and properties for a Variant.
    """

    def __init__(self, physics_calculator: Physics = None):
        self.physics = physics_calculator or Physics()

    def apply_rules(self, variant):
        """Applies physics rules to the given variant object.

        Calculates:
        - Tractive Effort (TE) coefficient (`variant.te_coefficient`)
        - Air Drag (AD) coefficient (`variant.ad_coefficient`)
        """
        weight = variant.get_attr("weight")
        speed = variant.get_attr("speed")
        tractive_effort = variant.get_attr("tractive_effort")
        train_type = getattr(variant.vehicle, "train_type", None)
        vehicle_type = getattr(variant, "vehicle_type", None) or getattr(variant.vehicle, "vehicle_type", None)

        is_rv = False
        if vehicle_type is not None:
            v_name = getattr(vehicle_type, "name", str(vehicle_type)).upper()
            is_rv = v_name in ("TRAM", "ROADVEH")

        # Unpowered rolling stock (wagons and coaches) have zero TE and AD coefficients in OpenTTD
        if train_type in (TrainType.WAGON, TrainType.COACH):
            variant.te_coefficient = 0.0
            variant.ad_coefficient = 0.0
            logger.debug(f"Applied unpowered physics rules for variant '{variant}'")
            return

        # Powered stock: Calculate TE coefficient
        if tractive_effort is not None and weight is not None and weight > 0:
            try:
                variant.te_coefficient = self.physics.calculate_TE_coefficient(
                    tractive_effort, weight, is_road_vehicle=is_rv
                )
            except Exception as exc:
                logger.warning(f"Could not calculate TE coefficient for variant '{variant}': {exc}")
                variant.te_coefficient = 0.0
        else:
            variant.te_coefficient = 0.0

        # Powered stock: Calculate Air Drag coefficient
        if speed is not None and speed > 0:
            try:
                variant.ad_coefficient = self.physics.calculate_AD_coefficient(speed)
            except Exception as exc:
                logger.warning(f"Could not calculate AD coefficient for variant '{variant}': {exc}")
                variant.ad_coefficient = 0.0
        else:
            variant.ad_coefficient = 0.0

        logger.debug(
            f"Applied physics rules for variant '{variant}': "
            f"TE={variant.te_coefficient}, AD={variant.ad_coefficient}"
        )
