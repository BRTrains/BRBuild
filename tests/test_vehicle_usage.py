import pytest

from PropertyCalculation.VehicleType import VehicleType
from PropertyCalculation.VehicleUsage import VehicleUsage
from Vehicle.UsageVisibility import disable_condition
from YamlHandler.VehicleLoader import VehicleLoader


def test_vehicle_usage_enum_accepts_yaml_identifier():
    assert VehicleUsage.from_identifier("UNDERGROUND") is VehicleUsage.UNDERGROUND


def test_vehicle_loader_reads_optional_usage_identifier(tmp_path):
    path = tmp_path / "vehicle.yaml"
    path.write_text(
        """info:\n  identifier: test\n  name: Test\nstats:\n  vehicle_type: train\n  train_type: multiple_unit\n  power_type: electric\nusage: METRO\ncargo: passenger\ndates:\n  introduction_date: 2000\nprofiles:\n  - identifier: default\n    num_vehicles: 1\n    capacity: 1\n    types: [train]\nliveries:\n  - name: Default\n"""
    )
    vehicle = VehicleLoader.load(str(path))
    assert vehicle.usage is VehicleUsage.METRO


def test_invalid_vehicle_usage_identifier_is_rejected(tmp_path):
    path = tmp_path / "vehicle.yaml"
    path.write_text(
        """info:\n  identifier: test\n  name: Test\nstats:\n  vehicle_type: train\n  train_type: multiple_unit\nusage: NOT_A_USAGE\nprofiles: []\nliveries: []\n"""
    )
    with pytest.raises(ValueError, match="Invalid vehicle usage"):
        VehicleLoader.load(str(path))


def test_tram_train_visibility_uses_configured_threshold():
    filters = [{"feature": "FEAT_TRAINS", "parameter": "show", "minimum": {"TRAM_TRAIN": 1}}]
    assert disable_condition(VehicleType.TRAM, VehicleType.TRAIN, VehicleUsage.TRAM_TRAIN, filters) == (
        "FEAT_TRAINS", "show < 1"
    )


def test_same_feature_has_no_visibility_condition():
    filters = [{"feature": "FEAT_TRAINS", "parameter": "show", "minimum": {"TRAM": 2}}]
    assert disable_condition(VehicleType.TRAIN, VehicleType.TRAIN, VehicleUsage.TRAM, filters) is None


def test_unmapped_tram_usage_uses_filter_default():
    filters = [{"feature": "FEAT_TRAINS", "parameter": "show", "default_minimum": 2}]
    assert disable_condition(VehicleType.TRAM, VehicleType.TRAIN, VehicleUsage.METRO, filters) == (
        "FEAT_TRAINS", "show < 2"
    )
