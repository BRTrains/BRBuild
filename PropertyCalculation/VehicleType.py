from enum import Enum

'''
Usage

VehicleType.TRAIN.nml_feature --> "FEAT_TRAINS"
VehicleType.TRAIN.display_name  --> "Train"

Note:
VehicleType.TRAM.nml_feature == VehicleType.ROAD.nml_feature --> True, because both map to "FEAT_ROADVEHS"
'''

class VehicleType(Enum):
    TRAIN = ("FEAT_TRAINS", "Train")
    TRAM = ("FEAT_ROADVEHS", "Tram")
    ROAD = ("FEAT_ROADVEHS", "Road Vehicle")
    # Backwards-compatible spelling for existing project data.
    ROADVEH = ROAD
    SHIP = ("FEAT_SHIPS", "Ship")
    PLANE = ("FEAT_AIRCRAFT", "Plane")

    def __init__(self, nml_feature, display_name):
        self.nml_feature = nml_feature
        self.display_name = display_name