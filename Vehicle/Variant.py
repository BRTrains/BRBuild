from PropertyCalculation import VehicleType, Physics, CostCalculator, TrainType
from Badge import BadgeRegistry

class Variant:
    def __init__(self, vehicle, livery, profile, vehicleType=None):
        self.vehicle = vehicle
        self.livery = livery
        self.profile = profile
        self.vehicle_type = vehicleType if vehicleType is not None else vehicle.vehicle_type

        self.badges = list()
        self.properties = dict()
        self.callbacks = dict()

        # Identifier must be first, in case it's needed for file naming and other properties
        self.generate_identifiers()

        self.handleSpeed()
        self.handleCapacity()
        self.handlePhysics()
        self.handleCosts()
        self.handleSpecialTags()

    def get_attr(self, attr):
        # Check profile first, then livery, then vehicle
        return getattr(self.profile, attr, None) or getattr(self.livery, attr, None) or getattr(self.vehicle, attr, None)

    def process(self):
        # Placeholder for processing logic, e.g., generating NML files based on the vehicle, livery, and profile
        pass

    def __repr__(self):
        return f"Variant(vehicle={self.vehicle.name}, livery={self.livery.name}, profile={self.profile.identifier})"
    
    def __str__(self):
        return f"{self.vehicle.name} - {self.livery.name} - {self.profile.identifier}"
    
    def handleSpeed(self):
        # Placeholder for handling speed-related logic based on the profile
        pass

    def handleCapacity(self):
        # Placeholder for handling capacity-related logic based on the profile
        pass

    def handlePhysics(self):
        physics = Physics()
        te = self.get_attr("tractive_effort")
        weight = self.get_attr("weight")

        if self.vehicle.train_type in (TrainType.WAGON, TrainType.COACH):
            # No tractive effort or air drag for wagons and coaches, so set coefficients to 0
            self.te_coefficient = 0
            self.ad_coefficient = 0
        else:
            self.te_coefficient = physics.calculate_TE_coefficient(te, weight)
            self.ai_coefficient = physics.calculate_AD_coefficient(self.get_attr("speed"))

    def generate_identifiers(self):
        # Generate unique identifiers for the variant based on the vehicle, livery, and profile
        self.identifier = (
            f"{self.vehicle.identifier}_"
            f"{self.profile.identifier.replace(' ', '-')}_"
            f"{self.livery.name.replace(' ', '-')}_"
            f"{self.vehicle_type.name}" # tram, train etc
        ).lower()
        
        # {self.vehicle.classification}/{self.vehicle.identifier}/
        self.nml_filename = f"{self.identifier}.gnml"
    

    def handleCosts(self):
        vehicle = self.vehicle
        calculator = CostCalculator()
        # purchase_cost = calculator.purchase_cost(speed, power, numvehs, capacity, fuelType, wagonType)
        # running_cost = calculator.running_cost(speed, power, numvehs, capacity, fuelType, wagonType) 

    def handleSpecialTags(self):
        for tag in self.vehicle.special_tags:
            badge = BadgeRegistry().add_badge(tag)
            self.badges.append(badge)

        operator = self.get_attr("operator")
        if operator is not None:
            self.badges.append(f"Operator/{operator}")