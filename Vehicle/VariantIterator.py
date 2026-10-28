from Vehicle.Variant import Variant
from Vehicle.Livery import Livery


class VariantIterator:
    def __init__(self, vehicle):
        self.vehicle = vehicle
        self.liveries = vehicle.liveries
        self.profiles = vehicle.profiles
        self.refit_livery = Livery("Livery Refits")
        self.current_livery_index = 0
        self.current_profile_index = 0
        self.current_type_index = 0
        self.current_refit_index = 0

    def __iter__(self):
        self.current_livery_index = 0
        self.current_profile_index = 0
        self.current_type_index = 0
        self.current_refit_index = 0
        return self

    def __next__(self):
        while True:
            if self.current_profile_index >= len(self.profiles):
                if len(self.liveries) > 1 and self.current_refit_index < len(self.profiles):
                    profile = self.profiles[self.current_refit_index]
                    self.current_refit_index += 1
                    applicable = [
                        livery for livery in self.liveries
                        if not getattr(livery, "profiles", None)
                        or str(profile.identifier).lower() in {
                            str(item).lower() for item in livery.profiles
                        }
                    ]
                    if not applicable:
                        continue
                    variant = Variant(
                        self.vehicle,
                        self.refit_livery,
                        profile,
                        vehicleType=(getattr(profile, "types", None) or [None])[0],
                        rail_type_table=getattr(self.vehicle, "rail_type_table", None),
                    )
                    variant.is_livery_refit = True
                    return variant
                raise StopIteration

            livery = self.liveries[self.current_livery_index]
            profile = self.profiles[self.current_profile_index]
            vehicle_types = getattr(profile, "types", None) or [None]
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
