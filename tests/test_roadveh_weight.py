"""A tram's weight and capacity ride in callbacks, and both are guarded.

A road vehicle's `weight` property is one byte of 1/4 tons, so it cannot hold more than
63.75 t, and its `cargo_capacity` property is one byte of units. The real figures therefore
have to reach the game through the get/set-property (CB36) callbacks, written in each
property's *field* unit — nmlc converts a `ton` literal but converts nothing written into an
expression. The property must still be set: OpenTTD falls back to it, and
`Engine::CanCarryCargo()` tests it alone.

The capacity callback is also guarded against the scaling parameter being unset. OpenTTD uses
the stored parameter as-is (`GRFConfig::GetValue`), and a slot that was never written — a
savegame that predates the parameter's current index, for instance — reads as 0, which would
otherwise zero every capacity in the set.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PropertyCalculation.VehicleType import VehicleType
from Vehicle.Variant import (
    ROADVEH_WEIGHT_PROPERTY_MAX_T,
    Variant,
)
from YamlHandler.VehicleLoader import VehicleLoader


BASE_YAML = """
info:
  identifier: example
  name: Class Example
stats:
  vehicle_type: {vehicle_type}
  train_type: multiple_unit
  power: 1000
  speed: 50
  weight: {weight}
  length: 6
profiles:
  - identifier: DEFAULT
    num_vehicles: 4
    capacity: 120
liveries:
  - name: Default
"""


class RoadVehicleWeightTests(unittest.TestCase):
    def _variant(self, folder, weight, vehicle_type="train", variant_type=VehicleType.TRAIN):
        document = BASE_YAML.format(vehicle_type=vehicle_type, weight=weight)
        path = Path(folder) / "Example.yaml"
        path.write_text(document, encoding="utf-8")
        vehicle = VehicleLoader.load(str(path))
        variant = Variant(vehicle, vehicle.liveries[0], vehicle.profiles[0], variant_type)
        variant.sprite_id = 1001
        variant.process()
        return variant

    def test_tram_weight_above_the_property_ceiling_is_clamped_and_called_back(self):
        with tempfile.TemporaryDirectory() as folder:
            variant = self._variant(folder, 98, "tram", VehicleType.TRAM)
        self.assertEqual(f"{ROADVEH_WEIGHT_PROPERTY_MAX_T} ton", variant.properties["weight"])
        self.assertEqual("392", variant.callbacks["weight"])

    def test_tram_weight_below_the_ceiling_keeps_its_authored_figure(self):
        with tempfile.TemporaryDirectory() as folder:
            variant = self._variant(folder, 30.2, "tram", VehicleType.TRAM)
        self.assertEqual("30.2 ton", variant.properties["weight"])
        self.assertEqual("121", variant.callbacks["weight"])

    def test_train_weight_is_a_plain_property_with_no_callback(self):
        with tempfile.TemporaryDirectory() as folder:
            variant = self._variant(folder, 466, "train", VehicleType.TRAIN)
        self.assertEqual("466 ton", variant.properties["weight"])
        self.assertNotIn("weight", variant.callbacks)

    def test_road_is_a_non_tram_road_vehicle(self):
        with tempfile.TemporaryDirectory() as folder:
            variant = self._variant(folder, 98, "road", VehicleType.ROAD)
        self.assertEqual("FEAT_ROADVEHS", variant.vehicle_type.nml_feature)
        self.assertEqual(f"{ROADVEH_WEIGHT_PROPERTY_MAX_T} ton", variant.properties["weight"])
        self.assertEqual("392", variant.callbacks["weight"])
        self.assertNotIn("ROADVEH_FLAG_TRAM", variant.properties.get("misc_flags", ""))
        self.assertNotIn("engine_class", variant.properties)


class CapacityCallbackTests(unittest.TestCase):
    def _variant(self, folder):
        document = BASE_YAML.format(vehicle_type="train", weight=100)
        path = Path(folder) / "Example.yaml"
        path.write_text(document, encoding="utf-8")
        vehicle = VehicleLoader.load(str(path))
        variant = Variant(vehicle, vehicle.liveries[0], vehicle.profiles[0], VehicleType.TRAIN)
        variant.sprite_id = 1001
        variant.process()
        return variant

    def test_capacity_callback_falls_back_when_the_parameter_is_unset(self):
        with tempfile.TemporaryDirectory() as folder:
            variant = self._variant(folder)
        # The placeholder keeps the property set; the real figure is in the callback, and the
        # callback does not simply multiply — a stored 0 must still read 120.
        self.assertEqual("1", str(variant.properties["cargo_capacity"]))
        self.assertEqual(
            "param_capacity_scaling < 1 ? 120 : 120 * param_capacity_scaling",
            variant.callbacks["cargo_capacity"],
        )


if __name__ == "__main__":
    unittest.main()
