"""Tests for the cargo properties the loader reads but the writer must emit.

`cargo.cargo_classes` was parsed onto the Vehicle and then never written anywhere, so
every BRTrains3 wagon was silently non-refittable and any cargo-driven graphics chain
could never trigger. These cover the emission side.
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


def yaml_with(cargo_block: str, extra: str = "") -> str:
    document = BASE_YAML + cargo_block + extra
    return document


class CargoPropertyTests(unittest.TestCase):
    def _variant(self, folder, document, extra=""):
        path = Path(folder) / "Example.yaml"
        path.write_text(document + extra, encoding="utf-8")
        vehicle = VehicleLoader.load(str(path))
        variant = Variant(vehicle, vehicle.liveries[0], vehicle.profiles[0], VehicleType.TRAIN)
        variant.sprite_id = 1001
        variant.process()
        return variant

    def test_cargo_classes_are_emitted_as_an_nml_bitmask(self):
        with tempfile.TemporaryDirectory() as folder:
            variant = self._variant(
                folder, yaml_with("cargo:\n  cargo_classes: [piece_goods, express]\n")
            )

        self.assertEqual(
            variant.properties["refittable_cargo_classes"],
            "bitmask(CC_PIECE_GOODS, CC_EXPRESS)",
        )

    def test_cargo_class_names_accept_the_cc_prefix_and_any_case(self):
        with tempfile.TemporaryDirectory() as folder:
            variant = self._variant(
                folder, yaml_with("cargo:\n  cargo_classes: [CC_PIECE_GOODS, Express, NON_POURABLE]\n")
            )

        self.assertEqual(
            variant.properties["refittable_cargo_classes"],
            "bitmask(CC_PIECE_GOODS, CC_EXPRESS, CC_NON_POURABLE)",
        )

    def test_a_scalar_class_list_is_accepted(self):
        """Other projects in the family author this as a bare string."""
        with tempfile.TemporaryDirectory() as folder:
            variant = self._variant(
                folder, yaml_with("cargo:\n  cargo_classes: [BULK, PIECE_GOODS]\n")
            )

        self.assertEqual(
            variant.properties["refittable_cargo_classes"], "bitmask(CC_BULK, CC_PIECE_GOODS)"
        )

    def test_unknown_cargo_class_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                self._variant(folder, yaml_with("cargo:\n  cargo_classes: [freight]\n"))

    def test_no_cargo_classes_emits_no_refittable_property(self):
        with tempfile.TemporaryDirectory() as folder:
            variant = self._variant(folder, yaml_with("cargo:\n  cargo_classes: NONE\n"))

        self.assertNotIn("refittable_cargo_classes", variant.properties)

    def test_non_cargo_classes_are_emitted(self):
        with tempfile.TemporaryDirectory() as folder:
            variant = self._variant(
                folder,
                yaml_with(
                    "cargo:\n  cargo_classes: [piece_goods]\n  non_cargo_classes: [bulk]\n"
                ),
            )

        self.assertEqual(
            variant.properties["non_refittable_cargo_classes"], "bitmask(CC_BULK)"
        )

    def test_default_cargo_type_is_emitted(self):
        with tempfile.TemporaryDirectory() as folder:
            variant = self._variant(
                folder,
                yaml_with(
                    "cargo:\n  cargo_classes: [piece_goods]\n"
                    "  default_cargo_type: DEFAULT_CARGO_FIRST_REFITTABLE\n"
                ),
            )

        self.assertEqual(
            variant.properties["default_cargo_type"], "DEFAULT_CARGO_FIRST_REFITTABLE"
        )

    def test_a_cargo_label_is_rejected_while_there_is_no_cargotable(self):
        """`GOOD` is only an identifier when the GRF declares a cargotable."""
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                self._variant(
                    folder,
                    yaml_with("cargo:\n  cargo_classes: [piece_goods]\n  default_cargo_type: GOOD\n"),
                )

    def test_loading_speed_and_cargo_age_period_are_emitted(self):
        with tempfile.TemporaryDirectory() as folder:
            variant = self._variant(
                folder,
                yaml_with("cargo:\n  cargo_classes: [piece_goods]\n"),
                extra="loading_speed: 25\ncargo_age_period: 185\n",
            )

        self.assertEqual(variant.properties["loading_speed"], "25")
        self.assertEqual(variant.properties["cargo_age_period"], "185")

    def test_autorefit_sets_the_train_autorefit_flag(self):
        with tempfile.TemporaryDirectory() as folder:
            variant = self._variant(
                folder,
                yaml_with("cargo:\n  cargo_classes: [piece_goods]\n"),
                extra="autorefit: true\n",
            )

        self.assertIn("TRAIN_FLAG_AUTOREFIT", variant.properties["misc_flags"])

    def test_autorefit_is_absent_by_default(self):
        with tempfile.TemporaryDirectory() as folder:
            variant = self._variant(folder, yaml_with("cargo:\n  cargo_classes: [piece_goods]\n"))

        self.assertNotIn("TRAIN_FLAG_AUTOREFIT", variant.properties.get("misc_flags", ""))


if __name__ == "__main__":
    unittest.main()
