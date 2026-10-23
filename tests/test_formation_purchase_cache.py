import json
from io import StringIO
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from NmlWriter.NmlVariantWriter import NmlVariantWriter
from NmlWriter.NmlSwitchWriter import NmlSwitchWriter
from PropertyCalculation.VehicleType import VehicleType

from Sprites.Sprite import Sprite
from Sprites.Spriteset import Spriteset
from Templates.Template import Template
from Vehicle.Variant import Variant
from Vehicle.VariantSpriteGroups import VehicleSpriteAllocator


class FormationPurchaseTests(unittest.TestCase):
    def test_articulation_matches_override_including_repeated_sprites(self):
        vehicle = SimpleNamespace(vehicle_type=None, size=5, sprite_override=[1, 2])
        profile = SimpleNamespace(num_vehicles=3)
        livery = SimpleNamespace(sprite_override=[1, 3, 7, 5, 6, 4, 2])
        variant = Variant(vehicle, livery, profile)
        variant.identifier = "edinburgh"
        variant.handleArticulated()
        self.assertEqual(variant.articulated_count, 7)
        self.assertIn("articulated_part", variant.callbacks)
        vehicle.power = 800
        vehicle.cargo_classes = ["PASSENGERS"]
        self.assertEqual(variant._formation_tag(), "formation/7-car")
        self.assertEqual(variant._formation_display_name(), "7-car")
        variant.handleSpecialTags()
        self.assertIn("formation/7-car", variant.badges)
        variant.vehicle_type = VehicleType.TRAIN
        output = StringIO()
        writer = object.__new__(NmlVariantWriter)
        writer.switch_writer = NmlSwitchWriter()
        writer._write_articulated_switch(output, variant)
        self.assertIn("1..6 : edinburgh", output.getvalue())

        # A narrower explicit count beats a broader sprite override.
        variant = Variant(vehicle, SimpleNamespace(), profile)
        variant.handleArticulated()
        self.assertEqual(variant.articulated_count, 3)

        variant = Variant(vehicle, SimpleNamespace(sprite_override=[1] * 7), profile)
        variant.handleArticulated()
        self.assertEqual(variant.articulated_count, 7)

    def test_purchase_cache_tracks_source_lengths_order_and_output(self):
        allocator = object.__new__(VehicleSpriteAllocator)
        allocator.vehicle = SimpleNamespace(identifier="example", spritesheet_path="source.png")
        allocator._palette = [0, 0, 255, 255, 0, 0] + [0] * 762
        allocator._image = Image.new("P", (16, 13), 1)
        allocator._image.putpalette(allocator._palette)
        profile = SimpleNamespace(identifier="single")
        livery = SimpleNamespace(name="Default")
        key = ("single", "Default")
        template = Template("car", [Sprite(0, 0, 8, 13, 0, 0)] * 8)
        allocator._spritesets = {key: [Spriteset("car", "source.png", template, 0, 0)]}
        allocator._definitions = {key: []}
        allocator._lengths = {key: [3]}
        allocator._patterns = {key: [1]}

        with tempfile.TemporaryDirectory() as folder:
            allocator.vehicle.spritesheet_path = str(Path(folder) / "source.png")
            purchase, _ = allocator.get_purchase(profile, livery, folder)
            path = Path(purchase.file)
            metadata = Path(folder) / "meta" / (path.name + ".purchase.json")
            self.assertTrue(metadata.is_file())
            with patch.object(allocator._image, "crop", wraps=allocator._image.crop) as crop:
                allocator.get_purchase(profile, livery, folder)
                crop.assert_not_called()

                for change in (
                    lambda: allocator._lengths[key].__setitem__(0, 4),
                    lambda: allocator._patterns[key].__setitem__(0, 2),
                    lambda: allocator._image.putpixel((0, 0), 0),
                    lambda: path.write_bytes(b"broken"),
                    lambda: metadata.write_text("broken"),
                ):
                    crop.reset_mock()
                    change()
                    allocator.get_purchase(profile, livery, folder)
                    self.assertTrue(crop.called)

            stored = json.loads(metadata.read_text())
            self.assertEqual(stored["inputs"]["lengths"], [4])
            self.assertEqual(stored["inputs"]["sprite_order"], [2])


if __name__ == "__main__":
    unittest.main()
