import pytest

from PropertyCalculation.DoorType import DoorType
from PropertyCalculation.VehicleType import VehicleType
from Vehicle.Livery import Livery
from Vehicle.Profile import Profile
from Vehicle.Variant import Variant
from Vehicle.Vehicle import Vehicle
from YamlHandler.VehicleLoader import VehicleLoader


def test_doors_accepts_all_identifiers():
    assert [DoorType.from_identifier(value).value for value in (
        "intercity",
        "commuter_single",
        "commuter_double",
        "commuter_triple",
        "multiple",
        "slam",
    )] == ["intercity", "commuter_single", "commuter_double", "commuter_triple", "multiple", "slam"]


def test_doors_resolve_livery_then_profile_then_vehicle():
    vehicle = Vehicle(".", "test", "Test", doors=DoorType.INTERCITY)
    profile = Profile("default", doors=DoorType.COMMUTER_DOUBLE)
    livery = Livery("Default", doors=DoorType.MULTIPLE)
    variant = Variant(vehicle, livery, profile, VehicleType.TRAIN)

    assert variant.get_attr("doors") is DoorType.MULTIPLE
    assert Variant(vehicle, Livery("Other"), profile, VehicleType.TRAIN).get_attr("doors") is DoorType.COMMUTER_DOUBLE
    assert Variant(vehicle, Livery("Plain"), Profile("plain"), VehicleType.TRAIN).get_attr("doors") is DoorType.INTERCITY


def test_vehicle_loader_parses_doors_at_all_scopes(tmp_path):
    path = tmp_path / "vehicle.yaml"
    path.write_text(
        """info:\n  identifier: test\n  name: Test\nstats:\n  vehicle_type: train\n  train_type: multiple_unit\ndoors: intercity\nprofiles:\n  - identifier: default\n    doors: commuter_double\nliveries:\n  - name: Default\n    doors: commuter_triple\n"""
    )

    vehicle = VehicleLoader.load(str(path))

    assert vehicle.doors is DoorType.INTERCITY
    assert vehicle.profiles[0].doors is DoorType.COMMUTER_DOUBLE
    assert vehicle.liveries[0].doors is DoorType.COMMUTER_TRIPLE


def test_invalid_doors_identifier_is_rejected(tmp_path):
    path = tmp_path / "vehicle.yaml"
    path.write_text(
        """info:\n  identifier: test\n  name: Test\nstats:\n  vehicle_type: train\n  train_type: multiple_unit\ndoors: single\nprofiles: []\nliveries: []\n"""
    )

    with pytest.raises(ValueError, match="Invalid doors"):
        VehicleLoader.load(str(path))
