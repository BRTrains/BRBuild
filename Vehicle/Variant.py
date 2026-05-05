from PropertyCalculation.Physics import Physics
from PropertyCalculation.CostCalculator import CostCalculator
from Badge.BadgeRegistry import BadgeRegistry

class Variant:
    def __init__(self, vehicle, livery, profile):
        self.vehicle = vehicle
        self.livery = livery
        self.profile = profile

        self.badges = list()
        self.handleSpecialTags()
        self.handleSpeed()
        self.handleCapacity()
        self.handlePhysics()
        self.handleCosts()

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

        self.te_coefficient = physics.calculate_TE_coefficient(te, weight)
        self.ai_coefficient = physics.calculate_AD_coefficient(self.get_attr("speed"))


    def handleCosts(self):
        vehicle = self.vehicle
        calculator = CostCalculator()
        # purchase_cost = calculator.purchase_cost(speed, power, numvehs, capacity, fuelType, wagonType)
        # running_cost = calculator.running_cost(speed, power, numvehs, capacity, fuelType, wagonType) 

    def handleSpecialTags(self):
        for tag in self.vehicle.special_tags:
            badge = BadgeRegistry().add_badge(tag)
            self.badges.append(badge)