"""A road-vehicle variant is drawn with the tram template, not the train one.

A tram is placed by OpenTTD from its template's offsets, and the tram templates differ from
the train templates of the same length in exactly those offsets — the view boxes are the same
shape on purpose, which is what lets a row matched as a train carry over to the tram side
unchanged. These tests pin both halves: the twin lookup, and that a road-vehicle variant names
the twin while the train variant keeps what it matched.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from PropertyCalculation.VehicleType import VehicleType
from Sprites.Sprite import Sprite
from Sprites.Spriteset import Spriteset
from Templates.Template import Template
from Templates.TemplateLoaderNML import TemplateLoaderNML
from Templates.TemplateType import TemplateType
from Vehicle.Profile import Profile
from Vehicle.Livery import Livery
from Vehicle.VariantSpriteGroups import (
    VehicleSpriteAllocator,
    road_vehicle_template_name,
    tram_template_index,
)
from Vehicle.Vehicle import Vehicle

#: Root of the BRBuild checkout, so tests never depend on a machine-specific absolute path.
REPO_ROOT = Path(__file__).resolve().parents[1]

PALETTE = [index % 256 for index in range(768)]


def _definitions():
    return TemplateLoaderNML().read_folder(str(REPO_ROOT / "Templates"))


def _box_tuple(box):
    return (box.left_x, box.upper_y, box.width, box.height)


class TramTemplateTests(unittest.TestCase):
    def test_a_train_template_maps_to_the_tram_template_of_the_same_shape(self):
        definitions = _definitions()
        index = tram_template_index(definitions)

        self.assertIn((4, ()), index)
        self.assertEqual(index[(4, ())], "tmpl_tram_4")

        train = next(d for d in definitions if d.name == "tmpl_train_4")
        self.assertEqual(road_vehicle_template_name(train, index), "tmpl_tram_4")

    def test_a_train_template_with_no_tram_twin_keeps_its_own_name(self):
        definitions = _definitions()
        index = tram_template_index(definitions)

        twins = {}
        for definition in definitions:
            if definition.template_type is not TemplateType.VEHICLE:
                continue
            if definition.vehicle_type != "train":
                continue
            if (definition.length, tuple(definition.variant_tags)) in index:
                twins[definition.name] = index[(definition.length, tuple(definition.variant_tags))]

        self.assertTrue(twins, "expected at least one train template with a tram twin")
        self.assertNotIn("tmpl_train_8_old_reversed", twins)

        unmatched = next(d for d in definitions if d.name == "tmpl_train_8_old_reversed")
        self.assertEqual(road_vehicle_template_name(unmatched, index), "tmpl_train_8_old_reversed")

    def test_every_twin_pair_has_identical_view_boxes_and_different_offsets(self):
        """The premise of the swap: same geometry, so only the offsets change."""
        definitions = _definitions()
        index = tram_template_index(definitions)
        by_name = {d.name: d for d in definitions}

        pairs = 0
        offsets_differ = 0
        for definition in definitions:
            if definition.template_type is not TemplateType.VEHICLE:
                continue
            if definition.vehicle_type != "train":
                continue
            key = (definition.length, tuple(definition.variant_tags))
            if key not in index:
                continue

            twin = by_name[index[key]]
            pairs += 1
            self.assertEqual(
                [_box_tuple(box) for box in definition.bounding_boxes],
                [_box_tuple(box) for box in twin.bounding_boxes],
                f"{definition.name} and {twin.name} must cover the same view boxes",
            )
            if [(b.offset_x, b.offset_y) for b in definition.bounding_boxes] != [
                (b.offset_x, b.offset_y) for b in twin.bounding_boxes
            ]:
                offsets_differ += 1

        self.assertGreater(pairs, 0)
        self.assertGreater(offsets_differ, 0, "the tram templates must place sprites differently")

    def test_a_road_vehicle_variant_names_the_tram_template(self):
        definitions = _definitions()
        train_four = next(d for d in definitions if d.name == "tmpl_train_4")

        with tempfile.TemporaryDirectory() as folder:
            sheet = Path(folder) / "unit.png"
            image = Image.new("P", (60, 60))
            image.putpalette(PALETTE)
            image.save(sheet)

            vehicle = Vehicle(
                folder_path=folder,
                identifier="unit",
                name="Unit",
                yaml_path=str(Path(folder) / "unit.yaml"),
                vehicle_type=VehicleType.TRAIN,
                profiles=[Profile("Default")],
                liveries=[Livery("Default")],
            )

            row = Spriteset(
                name="spriteset_row",
                file=str(sheet),
                template=Template(
                    name="row",
                    sprites=[Sprite(0, 0, 8, 17, -3, -13), Sprite(9, 0, 14, 15, -5, -12)],
                ),
                x=0,
                y=13,
            )

            with patch.object(
                VehicleSpriteAllocator, "_match_vehicle_rows", return_value=[(row, train_four)]
            ):
                allocator = VehicleSpriteAllocator(vehicle, PALETTE, definitions)

            _, train_names, train_lengths = allocator.get(
                vehicle.profiles[0], vehicle.liveries[0], VehicleType.TRAIN
            )
            _, tram_names, tram_lengths = allocator.get(
                vehicle.profiles[0], vehicle.liveries[0], VehicleType.TRAM
            )

        # Same rows and same lengths either way; only the template the writer calls changes.
        self.assertEqual(train_names, ["tmpl_train_4"])
        self.assertEqual(tram_names, ["tmpl_tram_4"])
        self.assertEqual(train_lengths, tram_lengths)
        self.assertEqual(train_lengths, [4])

    def test_no_traffic_type_leaves_the_matched_template_alone(self):
        definitions = _definitions()
        train_four = next(d for d in definitions if d.name == "tmpl_train_4")

        with tempfile.TemporaryDirectory() as folder:
            sheet = Path(folder) / "unit.png"
            image = Image.new("P", (60, 60))
            image.putpalette(PALETTE)
            image.save(sheet)

            vehicle = Vehicle(
                folder_path=folder,
                identifier="unit",
                name="Unit",
                yaml_path=str(Path(folder) / "unit.yaml"),
                vehicle_type=VehicleType.TRAIN,
                profiles=[Profile("Default")],
                liveries=[Livery("Default")],
            )
            row = Spriteset(
                name="spriteset_row",
                file=str(sheet),
                template=Template(name="row", sprites=[Sprite(0, 0, 8, 17, -3, -13)]),
                x=0,
                y=13,
            )

            with patch.object(
                VehicleSpriteAllocator, "_match_vehicle_rows", return_value=[(row, train_four)]
            ):
                allocator = VehicleSpriteAllocator(vehicle, PALETTE, definitions)

            _, names, _ = allocator.get(vehicle.profiles[0], vehicle.liveries[0])

        self.assertEqual(names, ["tmpl_train_4"])


if __name__ == "__main__":
    unittest.main()
