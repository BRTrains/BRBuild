"""Tests for the cargo configuration: `cargo:` presets, classes, and the writer.

`cargo:` names a preset (`passenger`, `parcels`, `containerised`, …), an explicit NML
class (`CC_PASSENGERS`, `piece_goods`), a list of either, or `none`. It resolves per
variant, so one candidate can carry both passenger and parcels formations.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PropertyCalculation.VehicleType import VehicleType
from Vehicle.Variant import Variant
from YamlHandler.VehicleLoader import VehicleLoader


BASE_YAML = """
info:
  identifier: example
  name: Class Example
stats:
  vehicle_type: train
  train_type: wagon
  power: 0
  speed: 0
  weight: 20
  length: 8
profiles:
  - identifier: DEFAULT
    num_vehicles: 1
    capacity: 30
liveries:
  - name: Default
"""


def yaml_with(body: str) -> str:
    return BASE_YAML + body


class CargoPresetTests(unittest.TestCase):
    def _variant(self, folder, document, profile_index=0):
        path = Path(folder) / "Example.yaml"
        path.write_text(document, encoding="utf-8")
        vehicle = VehicleLoader.load(str(path))
        variant = Variant(
            vehicle, vehicle.liveries[0], vehicle.profiles[profile_index], VehicleType.TRAIN
        )
        variant.sprite_id = 1001
        variant.process()
        return variant

    def _refittable(self, folder, document, profile_index=0):
        return self._variant(folder, document, profile_index).properties.get(
            "refittable_cargo_classes"
        )

    def test_a_preset_name_resolves_to_its_classes(self):
        with tempfile.TemporaryDirectory() as folder:
            refittable = self._refittable(folder, yaml_with("cargo: passenger\n"))

        self.assertEqual(refittable, "bitmask(CC_PASSENGERS)")

    def test_parcels_preset_covers_mail_express_and_armoured(self):
        with tempfile.TemporaryDirectory() as folder:
            refittable = self._refittable(folder, yaml_with("cargo: parcels\n"))

        self.assertEqual(refittable, "bitmask(CC_MAIL, CC_EXPRESS, CC_ARMOURED)")

    def test_containerised_preset_matches_the_legacy_wagon_list(self):
        with tempfile.TemporaryDirectory() as folder:
            refittable = self._refittable(folder, yaml_with("cargo: containerised\n"))

        self.assertEqual(
            refittable,
            "bitmask(CC_PIECE_GOODS, CC_EXPRESS, CC_HAZARDOUS, CC_REFRIGERATED, "
            "CC_NON_POURABLE, CC_NEO_BULK, CC_OVERSIZED)",
        )

    def test_bulk_and_tank_presets(self):
        with tempfile.TemporaryDirectory() as folder:
            bulk = self._refittable(folder, yaml_with("cargo: bulk\n"))
        with tempfile.TemporaryDirectory() as folder:
            tank = self._refittable(folder, yaml_with("cargo: tank\n"))

        self.assertEqual(
            bulk,
            "bitmask(CC_BULK, CC_COVERED, CC_POWDERIZED, CC_NON_POURABLE, CC_NEO_BULK)",
        )
        self.assertEqual(tank, "bitmask(CC_LIQUID)")

    def test_explicit_nml_classes_are_accepted_as_an_escape_hatch(self):
        with tempfile.TemporaryDirectory() as folder:
            refittable = self._refittable(
                folder, yaml_with("cargo: [CC_PASSENGERS, CC_ARMOURED]\n")
            )

        self.assertEqual(refittable, "bitmask(CC_PASSENGERS, CC_ARMOURED)")

    def test_presets_and_explicit_classes_mix(self):
        with tempfile.TemporaryDirectory() as folder:
            refittable = self._refittable(folder, yaml_with("cargo: [mail, CC_ARMOURED]\n"))

        self.assertEqual(refittable, "bitmask(CC_MAIL, CC_ARMOURED)")

    def test_a_cc_prefixed_name_means_that_one_class_not_the_preset(self):
        """`bulk` is both a preset and a class; the prefix picks the single class."""
        with tempfile.TemporaryDirectory() as folder:
            preset = self._refittable(folder, yaml_with("cargo: bulk\n"))
        with tempfile.TemporaryDirectory() as folder:
            single = self._refittable(folder, yaml_with("cargo: CC_BULK\n"))

        self.assertEqual(
            preset,
            "bitmask(CC_BULK, CC_COVERED, CC_POWDERIZED, CC_NON_POURABLE, CC_NEO_BULK)",
        )
        self.assertEqual(single, "bitmask(CC_BULK)")

    def test_unknown_cargo_name_is_rejected_and_lists_the_presets(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError) as raised:
                self._refittable(folder, yaml_with("cargo: freight\n"))

        self.assertIn("containerised", str(raised.exception))

    def test_the_old_nested_form_is_rejected_with_a_pointer(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError) as raised:
                self._refittable(
                    folder, yaml_with("cargo:\n  cargo_classes: [passengers]\n")
                )

        self.assertIn("cargo:", str(raised.exception))

    def test_none_emits_an_explicit_empty_class_list(self):
        """A vehicle that carries nothing still declares that, rather than staying silent."""
        with tempfile.TemporaryDirectory() as folder:
            variant = self._variant(folder, yaml_with("cargo: none\n"))

        self.assertEqual(variant.properties["refittable_cargo_classes"], "0")

    def test_none_keeps_the_capacity_property_and_its_callback(self):
        """Capacity stays 1 in the property and is overridden in the callback, as before."""
        with tempfile.TemporaryDirectory() as folder:
            variant = self._variant(folder, yaml_with("cargo: none\n"))

        self.assertEqual(variant.properties["cargo_capacity"], 1)
        self.assertIn("cargo_capacity", variant.callbacks)

    def test_an_unset_cargo_emits_no_refittable_property(self):
        with tempfile.TemporaryDirectory() as folder:
            variant = self._variant(folder, yaml_with(""))

        self.assertNotIn("refittable_cargo_classes", variant.properties)


class CargoResolutionTests(unittest.TestCase):
    def _vehicle(self, folder, document):
        path = Path(folder) / "Example.yaml"
        path.write_text(document, encoding="utf-8")
        return VehicleLoader.load(str(path))

    def _process(self, vehicle, profile_index=0):
        variant = Variant(
            vehicle, vehicle.liveries[0], vehicle.profiles[profile_index], VehicleType.TRAIN
        )
        variant.sprite_id = 1001
        variant.process()
        return variant

    def test_a_profile_cargo_overrides_the_vehicle_default(self):
        document = """
info:
  identifier: example
  name: Class Example
stats:
  vehicle_type: train
  train_type: multiple_unit
  power: 1000
  speed: 100
  weight: 40
  length: 8
cargo: passenger
profiles:
  - identifier: passenger
    num_vehicles: 2
    capacity: 100
  - identifier: parcels
    num_vehicles: 2
    capacity: 60
    cargo: parcels
liveries:
  - name: Default
"""
        with tempfile.TemporaryDirectory() as folder:
            vehicle = self._vehicle(folder, document)
            first = self._process(vehicle, 0)
            second = self._process(vehicle, 1)

        self.assertEqual(
            first.properties["refittable_cargo_classes"], "bitmask(CC_PASSENGERS)"
        )
        self.assertEqual(
            second.properties["refittable_cargo_classes"],
            "bitmask(CC_MAIL, CC_EXPRESS, CC_ARMOURED)",
        )

    def test_a_profile_can_opt_out_of_a_vehicle_cargo_with_none(self):
        document = """
info:
  identifier: example
  name: Class Example
stats:
  vehicle_type: train
  train_type: locomotive
  power: 1000
  speed: 100
  weight: 40
  length: 8
cargo: passenger
profiles:
  - identifier: deadweight
    num_vehicles: 1
    capacity: 0
    cargo: none
liveries:
  - name: Default
"""
        with tempfile.TemporaryDirectory() as folder:
            vehicle = self._vehicle(folder, document)
            variant = self._process(vehicle, 0)

        self.assertEqual(variant.properties["refittable_cargo_classes"], "0")

    def test_non_cargo_classes_and_default_cargo_type_work_at_root(self):
        document = """
info:
  identifier: example
  name: Class Example
stats:
  vehicle_type: train
  train_type: wagon
  power: 0
  speed: 0
  weight: 20
  length: 8
cargo: containerised
non_cargo_classes: [bulk]
default_cargo_type: DEFAULT_CARGO_FIRST_REFITTABLE
profiles:
  - identifier: DEFAULT
    num_vehicles: 1
    capacity: 30
liveries:
  - name: Default
"""
        with tempfile.TemporaryDirectory() as folder:
            vehicle = self._vehicle(folder, document)
            variant = self._process(vehicle, 0)

        self.assertEqual(variant.properties["non_refittable_cargo_classes"], "bitmask(CC_BULK)")
        self.assertEqual(
            variant.properties["default_cargo_type"], "DEFAULT_CARGO_FIRST_REFITTABLE"
        )

    def test_a_cargo_label_is_rejected_while_there_is_no_cargotable(self):
        """`GOOD` is only an identifier when the GRF declares a cargotable."""
        document = BASE_YAML + "cargo: containerised\ndefault_cargo_type: GOOD\n"
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                self._vehicle(folder, document)

    def test_loading_speed_and_cargo_age_period_are_emitted(self):
        document = BASE_YAML + "cargo: passenger\nloading_speed: 25\ncargo_age_period: 185\n"
        with tempfile.TemporaryDirectory() as folder:
            vehicle = self._vehicle(folder, document)
            variant = self._process(vehicle, 0)

        self.assertEqual(variant.properties["loading_speed"], "25")
        self.assertEqual(variant.properties["cargo_age_period"], "185")

    def test_autorefit_sets_the_train_autorefit_flag(self):
        document = BASE_YAML + "cargo: containerised\nautorefit: true\n"
        with tempfile.TemporaryDirectory() as folder:
            vehicle = self._vehicle(folder, document)
            variant = self._process(vehicle, 0)

        self.assertIn("TRAIN_FLAG_AUTOREFIT", variant.properties["misc_flags"])

    def test_autorefit_is_absent_by_default(self):
        document = BASE_YAML + "cargo: containerised\n"
        with tempfile.TemporaryDirectory() as folder:
            vehicle = self._vehicle(folder, document)
            variant = self._process(vehicle, 0)

        self.assertNotIn("TRAIN_FLAG_AUTOREFIT", variant.properties.get("misc_flags", ""))


if __name__ == "__main__":
    unittest.main()
