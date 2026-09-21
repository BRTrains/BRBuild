from Vehicle.Variant import Variant


class VariantIterator:
    def __init__(self, vehicle):
        self.vehicle = vehicle
        self.liveries = vehicle.liveries
        self.profiles = vehicle.profiles

        self.current_livery_index = 0
        self.current_profile_index = 0
        self.current_type_index = 0

    def __iter__(self):
        # Reset state to allow reuse
        self.current_livery_index = 0
        self.current_profile_index = 0
        self.current_type_index = 0
        return self

    def __next__(self):
        while True:
            if self.current_profile_index >= len(self.profiles):
                raise StopIteration

            livery = self.liveries[self.current_livery_index]
            profile = self.profiles[self.current_profile_index]

            vehicle_types = getattr(profile, "types", None)
            if not vehicle_types:
                vehicle_types = [None]

            vehicle_type = vehicle_types[self.current_type_index]

            self.current_type_index += 1

            if self.current_type_index >= len(vehicle_types):
                self.current_type_index = 0
                self.current_livery_index += 1

                if self.current_livery_index >= len(self.liveries):
                    self.current_livery_index = 0
                    self.current_profile_index += 1

            profile_id = str(profile.identifier).replace("_", "").strip().lower()
            livery_profiles = getattr(livery, "profiles", None)
            if livery_profiles and not any(
                str(livery_profile).replace("_", "").strip().lower() == profile_id
                for livery_profile in livery_profiles
            ):
                continue

            return Variant(
                self.vehicle,
                livery,
                profile,
                vehicleType=vehicle_type,
                rail_type_table=getattr(self.vehicle, "rail_type_table", None),
            )
