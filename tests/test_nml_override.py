"""Tests for `nml_override`: letting a candidate supply its own NML for a callback.

A candidate may point one of its graphics callbacks at a switch that its own custom
`.pnml` declares, instead of the auto-generated spriteset switch. BRBuild must then
stop generating that callback's own switch and emit the override verbatim.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Builder.CandidateFinder import CandidateFinder
from NmlWriter.NmlCollator import NmlCollator
from NmlWriter.NmlVariantWriter import NmlVariantWriter
from PropertyCalculation.VehicleType import VehicleType
from Sprites.Sprite import Sprite
from Sprites.Spriteset import Spriteset
from Templates.Template import Template
from Vehicle.Profile import Profile
from Vehicle.Variant import Variant
from Vehicle.Vehicle import Vehicle
from YamlHandler.VehicleLoader import VehicleLoader


VEHICLE_YAML = """
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
nml_override:
  default: sw_example_custom
profiles:
  - identifier: DEFAULT
    num_vehicles: 1
    capacity: 30
liveries:
  - name: Default
"""


class NmlOverrideTests(unittest.TestCase):
    def _load_vehicle(self, folder, document=VEHICLE_YAML):
        path = Path(folder) / "Example.yaml"
        path.write_text(document, encoding="utf-8")
        return VehicleLoader.load(str(path))

    def _processed_variant(self, vehicle, with_sprites=True):
        variant = Variant(vehicle, vehicle.liveries[0], vehicle.profiles[0], VehicleType.TRAIN)
        variant.sprite_id = 1001
        if with_sprites:
            spriteset = Spriteset(
                name="source",
                file="source.png",
                template=Template("tmpl_train_8", [Sprite(0, 0, 8, 25, -3, -12, [])]),
                x=0,
                y=13,
            )
            variant.spritesets = [spriteset]
            variant.sprite_template_names = ["tmpl_train_8"]
            variant.sprite_lengths = [8]
        variant.process()
        return variant

    def _written_item(self, variant, folder):
        return Path(NmlVariantWriter(variant, folder).write()).read_text(encoding="utf-8")

    def test_nml_override_replaces_the_generated_default_callback(self):
        """An overridden `default` is emitted verbatim, with no generated sprite switch."""
        with tempfile.TemporaryDirectory() as folder:
            vehicle = self._load_vehicle(folder)
            variant = self._processed_variant(vehicle)
            written = self._written_item(variant, folder)

        self.assertIn("default: sw_example_custom;", written)
        self.assertNotIn(f"default: sw_{variant.identifier};", written)
        self.assertNotIn(f"switch (FEAT_TRAINS, SELF, sw_{variant.identifier},", written)

    def test_nml_override_leaves_other_callbacks_generated(self):
        """An override for one callback must not disturb the others."""
        with tempfile.TemporaryDirectory() as folder:
            vehicle = self._load_vehicle(folder)
            variant = self._processed_variant(vehicle)
            written = self._written_item(variant, folder)

        self.assertIn("default: sw_example_custom;", written)
        self.assertIn("length: ", written)

    def test_nml_override_is_read_from_the_vehicle_level(self):
        with tempfile.TemporaryDirectory() as folder:
            vehicle = self._load_vehicle(folder)

        self.assertEqual(vehicle.nml_override, {"default": "sw_example_custom"})

    def test_nml_override_rejects_an_unknown_callback_name(self):
        """A typo must fail the load rather than silently doing nothing."""
        document = VEHICLE_YAML.replace("default: sw_example_custom", "defualt: sw_example_custom")
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                self._load_vehicle(folder, document)

    def test_project_custom_nml_is_collated_before_the_generated_item(self):
        """A project's `custom_nml` files must reach the collated NML ahead of the items.

        This is what `docs/project.md` promises, and it is what lets a candidate's own
        switch be in scope when `nml_override` points a callback at it.
        """
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            custom_nml = project_root / "src" / "grf" / "custom_nml"
            custom_nml.mkdir(parents=True)
            (custom_nml / "Container.pnml").write_text(
                "switch (FEAT_TRAINS, SELF, sw_example_custom, cargo_count) {\n}\n",
                encoding="utf-8",
            )

            item_file = project_root / "WorkingData" / "Example" / "item.gnml"
            item_file.parent.mkdir(parents=True, exist_ok=True)
            item_file.write_text("item (FEAT_TRAINS, example) {\n}\n", encoding="utf-8")

            collated = NmlCollator().collate(
                [str(item_file)],
                "Example",
                custom_nml,
                project_root,
            )
            text = Path(collated).read_text(encoding="utf-8")

        # Locate each declaration, past the collator's "// File: ..." banner lines.
        custom_switch = text.index("switch (FEAT_TRAINS, SELF, sw_example_custom,")
        item_block = text.index("item (FEAT_TRAINS, example) {\n")
        self.assertLess(
            custom_switch,
            item_block,
            "a project's custom NML must be collated before the generated item blocks",
        )

    def test_candidate_pnml_is_collated_next_to_its_own_vehicle_only(self):
        """A candidate's `.pnml` goes immediately before that vehicle's blocks.

        It must not be hoisted above the badge table: a switch holds a concurrent
        spritegroup slot while in scope, and OpenTTD only allows 255 of those.
        """
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            candidate = project_root / "Example"
            candidate.mkdir()
            (candidate / "Example.yaml").write_text(VEHICLE_YAML, encoding="utf-8")
            (candidate / "Example.pnml").write_text(
                "switch (FEAT_TRAINS, SELF, sw_example_custom, cargo_count) {\n}\n",
                encoding="utf-8",
            )
            other = project_root / "Other"
            other.mkdir()
            (other / "Other.yaml").write_text(VEHICLE_YAML, encoding="utf-8")

            found = CandidateFinder(project_root).find_candidates()
            self.assertEqual(len(found), 2)
            by_name = {c["name"]: c for c in found}
            self.assertEqual(
                [Path(p).name for p in by_name["Example"]["pnml_files"]], ["Example.pnml"]
            )

            working = project_root / "WorkingData" / "Example"
            working.mkdir(parents=True, exist_ok=True)
            example_item = working / "example_default_default_train.gnml"
            example_item.write_text("item (FEAT_TRAINS, example) {\n}\n", encoding="utf-8")
            other_item = working / "other_default_default_train.gnml"
            other_item.write_text("item (FEAT_TRAINS, other) {\n}\n", encoding="utf-8")

            # The builder stages a candidate's own NML into the working folder with its
            # quoted paths made absolute, so it is never compiled in place.
            staged = NmlCollator().copy_supplied_nml(
                Path(by_name["Example"]["pnml_files"][0]),
                working / "candidate_nml" / "Example.pnml",
                project_root,
            )

            collated = NmlCollator().collate(
                [str(example_item), str(other_item)],
                "Example",
                None,
                project_root,
                candidates_root=project_root,
                staged_candidate_nml=working / "candidate_nml",
                vehicle_nml_files={"example": [staged]},
                variant_owners={str(example_item.resolve()): "example", str(other_item.resolve()): "other"},
            )
            text = Path(collated).read_text(encoding="utf-8")

        badge_table = text.index("badgetable {")
        custom_switch = text.index("switch (FEAT_TRAINS, SELF, sw_example_custom,")
        example_item_block = text.index("item (FEAT_TRAINS, example) {")
        other_item_block = text.index("item (FEAT_TRAINS, other) {")

        self.assertLess(badge_table, custom_switch, "the badge table stays before all vehicles")
        self.assertLess(custom_switch, example_item_block, "vehicle NML precedes its own item")
        self.assertLess(example_item_block, other_item_block, "variant order is preserved")
        self.assertEqual(
            text.count("switch (FEAT_TRAINS, SELF, sw_example_custom,"),
            1,
            "the custom switch is written once, not once per variant",
        )


if __name__ == "__main__":
    unittest.main()
