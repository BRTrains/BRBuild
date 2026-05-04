from Vehicle.Variant import Variant


class VariantIterator:
    def __init__(self, vehicle):
        self.vehicle = vehicle
        self.liveries = vehicle.liveries
        self.profiles = vehicle.profiles
        self.current_livery_index = 0
        self.current_profile_index = 0

    def __iter__(self):
        # Reset state to allow reuse
        self.current_livery_index = 0
        self.current_profile_index = 0
        return self

    def __next__(self):
        if self.current_profile_index >= len(self.profiles):
            raise StopIteration

        livery = self.liveries[self.current_livery_index]
        profile = self.profiles[self.current_profile_index]

        variant = Variant(self.vehicle, livery, profile)

        self.current_livery_index += 1

        if self.current_livery_index >= len(self.liveries):
            self.current_livery_index = 0
            self.current_profile_index += 1

        return variant