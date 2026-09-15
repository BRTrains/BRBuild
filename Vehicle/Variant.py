import re
import logging
from Badge import BadgeRegistry
from Lang.StringRegistry import nml_str
from PropertyCalculation import CostCalculator, FuelType, Physics, PowerTypeClassifier, TrainType, VehicleType

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
            self.handleBasicProperties, # Things that don't need any complicated transformations or calculations
            self.handleSpeed,
            self.handleCapacity,
            self.handlePhysics,
            self.handleFuelType,
            self.handleCosts,
            self.handleSpecialTags,
            self.handleAdditionalText
        ]

        for stage in stages:
            try:
                stage()
            except Exception as exc:
                logger.exception(f"Error in variant {self} during stage {stage.__name__}: {exc}")
                raise

    # Clamp ranges
    def clamp(n, smallest, largest):
        return max(smallest, min(n, largest))

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

        # Formatted NML header properties
        name_ref = nml_str(self.name, f"{self.identifier}_name")
        self.properties["name"] = name_ref

        # Sprite ID based on vehicle feature
        v_type = self.vehicle_type
        sprite_id = "SPRITE_ID_NEW_TRAIN"
        if isinstance(v_type, VehicleType):
            if v_type in (VehicleType.TRAM, VehicleType.ROADVEH):
                sprite_id = "SPRITE_ID_NEW_ROADVEH"
            elif v_type == VehicleType.SHIP:
                sprite_id = "SPRITE_ID_NEW_SHIP"
            elif v_type == VehicleType.PLANE:
                sprite_id = "SPRITE_ID_NEW_AIRCRAFT"
        elif hasattr(v_type, "name"):
            v_name = v_type.name.upper()
            if v_name in ("TRAM", "ROADVEH"):
                sprite_id = "SPRITE_ID_NEW_ROADVEH"

        self.properties["sprite_id"] = sprite_id

    ''' Handle some fairly simple properties that don't need complex calculations'''
    def handleBasicProperties(self):
        intro_date = self.get_attr("introduction_date")
        if intro_date is not None:
            if isinstance(intro_date, int) or (isinstance(intro_date, str) and intro_date.isdigit()):
                self.properties["introduction_date"] = f"date({intro_date}, 1, 1)"
            else:
                self.properties["introduction_date"] = str(intro_date)

        model_life = self.get_attr("model_life")
        if model_life is None or int(model_life) == 0:
            model_life = "VEHICLE_NEVER_EXPIRES"
        else:
            model_life = self.clamp(int(model_life), 1, 254) # Clamp to NML range
        self.properties["model_life"] = str(model_life)

        self.properties["climates_available"] = "ALL_CLIMATES"

        vehicle_life = self.get_attr("vehicle_life")
        if vehicle_life is not None:
            vehicle_life = self.clamp(int(vehicle_life), 1, 255) # Clamp to NML range
        else:
            vehicle_life = 30 # Default
        self.properties["vehicle_life"] = str(vehicle_life)

        length = self.get_attr("length")
        if length is not None:
            self.properties["length"] = str(length)

    def handleSpeed(self):
        speed = self.get_attr("speed")
        self.speed = speed
        if speed is not None:
            if isinstance(speed, float):
                self.properties["speed"] = f"{speed:.1f} mph"
            else:
                self.properties["speed"] = f"{speed} mph"

    def handleCapacity(self):
        capacity = self.get_attr("capacity")
        if capacity is None:
            capacity = 0
        self.callbacks["cargo_capacity"] = f"{int(capacity)} * param_passenger_multiplier"
        self.properties["cargo_capacity"] = 1 # Needed for NML to allow the callback override

    def handlePhysics(self):
        PhysicsRules().apply_rules(self)

        power = self.get_attr("power")
        if power is not None:
            self.power = power
            self.properties["power"] = f"{power} hp"
        else:
            self.power = 0

        weight = self.get_attr("weight")
        if weight is not None:
            self.properties["weight"] = f"{weight} ton"

        if hasattr(self, "te_coefficient") and self.te_coefficient is not None:
            self.properties["tractive_effort_coefficient"] = str(self.te_coefficient)

        if hasattr(self, "ad_coefficient") and self.ad_coefficient is not None:
            self.properties["air_drag_coefficient"] = str(self.ad_coefficient)

    def handleCosts(self):
        calculator = CostCalculator(self)

        purchase_cost = calculator.purchase_cost(False)
        running_cost = calculator.running_cost(False)

        self.callbacks["cost_factor"] = purchase_cost
        self.callbacks["running_cost_factor"] = running_cost
    
    #todo: this doesn't need to be per variant, can be done per vehicle instead
    def handleAdditionalText(self):
        additional_text = self.get_attr("additional_text")
        if additional_text:
            if isinstance(additional_text, list):
                additional_text = "{}".join(additional_text)
            self.callbacks["additional_text"] = nml_str(additional_text,f"{self.identifier}_additional_text")

    def handleSpecialTags(self):
        if self.vehicle.special_tags:
            for tag in self.vehicle.special_tags:
                badge = BadgeRegistry().add_badge(tag)
                self.badges.append(badge)

        operator = self.get_attr("operator")
        if operator is not None:
            self.badges.append(f"Operator/{operator}")

        if self.badges:
            badges_formatted = ", ".join(f'"{b}"' for b in self.badges)
            self.properties["badges"] = f"[{badges_formatted}]"

    def handleFuelType(self):
        PowerTypeClassifier(self).process()