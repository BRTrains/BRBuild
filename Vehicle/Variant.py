import re
import logging
from Badge import BadgeRegistry
from PropertyCalculation import CostCalculator, Physics, TrainType

from Vehicle.Translator.PhysicsRules import PhysicsRules

logger = logging.getLogger(__name__)


class Variant:
    def __init__(self, vehicle, livery, profile, vehicleType=None):
        self.vehicle = vehicle
        self.livery = livery
        self.profile = profile
        self.vehicle_type = vehicleType if vehicleType is not None else vehicle.vehicle_type

        self.badges = list()
        self.properties = dict()
        self.callbacks = dict()

        self.identifier = None
        self.nml_filename = None

    def process(self):
        """Executes the processing pipeline stages for this variant."""
        stages = [
            self.generate_identifiers,
            self.handleSpeed,
            self.handleCapacity,
            self.handlePhysics,
            self.handleCosts,
            self.handleSpecialTags,
        ]

        for stage in stages:
            try:
                stage()
            except Exception as exc:
                logger.exception(f"Error in variant {self} during stage {stage.__name__}: {exc}")
                raise

    def get_attr(self, attr):
        # Check profile first, then livery, then vehicle, returning the first non-None value
        for obj in (self.profile, self.livery, self.vehicle):
            val = getattr(obj, attr, None)
            if val is not None:
                return val
        return None

    @property
    def name(self):
        """Constructs the variant display name in the format:
        'Vehicle Name - Profile Name - Livery Name'
        Skipping Profile Name if the profile identifier is DEFAULT (case-insensitive).
        """
        vehicle_name = self.vehicle.name

        profile_id = str(self.profile.identifier).strip() if self.profile and self.profile.identifier else ""
        profile_name = (self.profile.name or profile_id) if self.profile else ""

        livery_name = self.livery.name if self.livery and self.livery.name else ""

        parts = [vehicle_name]

        if profile_id and profile_id.upper() != "DEFAULT" and profile_name:
            parts.append(profile_name)

        if livery_name:
            parts.append(livery_name)

        return " - ".join(parts)

    def __repr__(self):
        return f"Variant(vehicle={self.vehicle.name}, livery={self.livery.name}, profile={self.profile.identifier})"

    def __str__(self):
        return self.name

    def generate_identifiers(self):
        # Generate unique identifiers for the variant based on the vehicle, livery, and profile
        raw_id = (
            f"{self.vehicle.identifier}_"
            f"{self.profile.identifier}_"
            f"{self.livery.name}_"
            f"{self.vehicle_type.name}"
        ).lower()
        self.identifier = re.sub(r"[^a-z0-9_]", "_", raw_id)
        self.nml_filename = f"{self.identifier}.gnml"

        # {self.vehicle.classification}/{self.vehicle.identifier}/
        self.nml_filename = f"{self.identifier}.gnml"

    def handleSpeed(self):
        # Placeholder for handling speed-related logic based on the profile
        pass

    def handleCapacity(self):
        # Placeholder for handling capacity-related logic based on the profile
        pass

    def handlePhysics(self):
        PhysicsRules().apply_rules(self)

    def handleCosts(self):
        # Compute costs using CostCalculator when needed
        # Example usage (uncomment and adapt):
        # calculator = CostCalculator()
        # purchase_cost = calculator.purchase_cost(speed, power, numvehs, capacity, fuelType, wagonType)
        # running_cost = calculator.running_cost(speed, power, numvehs, capacity, fuelType, wagonType)
        pass

    def handleSpecialTags(self):
        if self.vehicle.special_tags:
            for tag in self.vehicle.special_tags:
                badge = BadgeRegistry().add_badge(tag)
                self.badges.append(badge)

        operator = self.get_attr("operator")
        if operator is not None:
            self.badges.append(f"Operator/{operator}")