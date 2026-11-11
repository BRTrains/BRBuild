import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from Builder.Builder import Builder
from Builder.CandidateProcessor import CandidateProcessor
from PropertyCalculation import TrainType, VehicleType
from Sprites.PalettedImage import PalettedImage
from Sprites.Sprite import Sprite
from Sprites.Spriteset import Spriteset
from Templates.BoundingBox import BoundingBox
from Templates.Template import Template
from Templates.TemplateDefinition import TemplateDefinition
from Templates.TemplateType import TemplateType
from Vehicle import Livery, Profile, Variant, Vehicle
from Vehicle.VariantSpriteGroups import (
    PurchaseSpriteComposer,
    PurchaseSpritePart,
    VehicleSpriteAllocator,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class PurchaseSpriteComposerTests(unittest.TestCase):
    @staticmethod
    def _part(palette, colour_index, name, height=13):
        image = Image.new("P", (4, height), colour_index)
        image.putpalette(palette)
        template = Template(
            name=f"measured_{name}",
            sprites=[Sprite(0, 0, 4, height, 0, 0) for _ in range(8)],
        )
        definition = TemplateDefinition(
            name=f"tmpl_{name}",
            template_type=TemplateType.VEHICLE,
            bounding_boxes=[
                BoundingBox(0, 0, 4, height, 0, -8, []) for _ in range(8)
            ],
        )
        return PurchaseSpritePart(
            image,
            palette,
            Spriteset(name, f"/staged/{name}.png", template, 0, 0),
            definition,
        )

    def test_composes_ordered_parts_from_different_staged_images(self):
        palette = PalettedImage.load_palette(
            str(REPO_ROOT / "Sprites" / "ttd-newgrf-dos.gpl")
        )
        colour_indices = [10, 20, 30]
        colours = [
            tuple(palette[index * 3:index * 3 + 3]) for index in colour_indices
        ]
        parts = [
            self._part(palette, colour_index, f"part_{index}")
            for index, colour_index in enumerate(colour_indices)
        ]

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "purchase_parent_variant.png"
            result = PurchaseSpriteComposer(palette).compose(parts, path)

            self.assertEqual(result[1], "tmpl_purchase")
            icon = Image.open(result[0].file).convert("RGB")
            self.assertEqual(
                [icon.getpixel((x, 12)) for x in (0, 4, 8)], colours
            )

    def test_processor_composes_root_then_exact_flattened_hidden_parts(self):
        palette = PalettedImage.load_palette(
            str(REPO_ROOT / "Sprites" / "ttd-newgrf-dos.gpl")
        )
        profile = Profile("DEFAULT")
        livery = Livery("Default")
        root_vehicle = Vehicle(
            folder_path=".", identifier="root", name="Root",
            vehicle_type=VehicleType.TRAM, train_type=TrainType.COACH,
            profiles=[profile], liveries=[livery],
        )
        hidden_vehicle = Vehicle(
            folder_path=".", identifier="coach", name="Coach",
            vehicle_type=VehicleType.TRAIN, train_type=TrainType.COACH,
            profiles=[profile], liveries=[livery],
        )
        root = Variant(root_vehicle, livery, profile, vehicleType=VehicleType.TRAM)
        hidden = Variant(hidden_vehicle, livery, profile, vehicleType=VehicleType.TRAM)
        nested = Variant(hidden_vehicle, livery, profile, vehicleType=VehicleType.TRAM)
        root.identifier = "root_default_default_tram"
        hidden.hidden_articulated_part = True
        root.purchase_sprite_parts = [self._part(palette, 10, "root")]
        hidden.purchase_sprite_parts = [self._part(palette, 20, "hidden")]
        nested.purchase_sprite_parts = [self._part(palette, 30, "nested")]
        root.articulated_part_variants = [hidden]
        hidden.articulated_part_variants = [nested]
        processor = CandidateProcessor(Builder())
        processor._pending_variants = [
            (root_vehicle, root, object()),
            (hidden_vehicle, hidden, object()),
        ]

        with tempfile.TemporaryDirectory() as folder:
            ctx = type("Context", (), {
                "palette": palette,
                "nml_output_folder": folder,
            })()
            processor._compose_purchase_sprites(ctx)

            icon = Image.open(root.purchase_spriteset.file).convert("RGB")
            expected = [
                tuple(palette[index * 3:index * 3 + 3]) for index in (10, 20)
            ]
            self.assertEqual([icon.getpixel((x, 12)) for x in (0, 4)], expected)
            self.assertEqual(icon.getpixel((8, 12)), (0, 0, 255))
            self.assertEqual(root.purchase_template_name, "tmpl_purchase")

    def test_allocator_exposes_each_physical_part_with_its_staged_image(self):
        palette = PalettedImage.load_palette(
            str(REPO_ROOT / "Sprites" / "ttd-newgrf-dos.gpl")
        )
        profile = Profile("DEFAULT")
        livery = Livery("Default")
        source = self._part(palette, 10, "source")
        key = (str(profile.identifier), str(livery.name))
        allocator = VehicleSpriteAllocator.__new__(VehicleSpriteAllocator)
        allocator._palette = palette
        allocator._image = source.image
        allocator._spritesets = {key: [source.spriteset, source.spriteset]}
        allocator._definitions = {key: [source.definition, source.definition]}
        allocator._sheet_paths = {}

        parts = allocator.get_purchase_parts(profile, livery)

        self.assertEqual(len(parts), 2)
        self.assertTrue(all(part.image is source.image for part in parts))
        self.assertEqual([part.spriteset for part in parts], [source.spriteset] * 2)

    def test_overflow_warns_while_retaining_the_canonical_canvas(self):
        palette = PalettedImage.load_palette(
            str(REPO_ROOT / "Sprites" / "ttd-newgrf-dos.gpl")
        )
        source = self._part(palette, 10, "wide")
        source.spriteset.template.sprites[6].width = 129
        source.definition.bounding_boxes[6].width = 129

        with tempfile.TemporaryDirectory() as folder, self.assertLogs(
            "Vehicle.VariantSpriteGroups", level="WARNING"
        ) as captured:
            result = PurchaseSpriteComposer(palette).compose(
                [source], Path(folder) / "wide.png"
            )

            self.assertIn("overflows the 128px canvas", captured.output[0])
            with Image.open(result[0].file) as image:
                self.assertEqual(image.size, (128, 13))

            with self.assertLogs(
                "Vehicle.VariantSpriteGroups", level="WARNING"
            ) as cached_warning:
                PurchaseSpriteComposer(palette).compose(
                    [source], Path(folder) / "wide.png"
                )
            self.assertIn("overflows the 128px canvas", cached_warning.output[0])

    def test_manual_purchase_override_is_not_replaced(self):
        palette = PalettedImage.load_palette(
            str(REPO_ROOT / "Sprites" / "ttd-newgrf-dos.gpl")
        )
        profile = Profile("DEFAULT")
        livery = Livery("Default")
        vehicle = Vehicle(
            folder_path=".", identifier="root", name="Root",
            vehicle_type=VehicleType.TRAM, train_type=TrainType.COACH,
            profiles=[profile], liveries=[livery],
            nml_override={"purchase": "manual_purchase_switch"},
        )
        variant = Variant(vehicle, livery, profile, vehicleType=VehicleType.TRAM)
        variant.identifier = "root_default_default_tram"
        variant.purchase_sprite_parts = [self._part(palette, 10, "root")]
        variant.articulated_part_variants = [SimpleNamespace(
            purchase_sprite_parts=[self._part(palette, 20, "hidden")]
        )]
        processor = CandidateProcessor(Builder())
        processor._pending_variants = [(vehicle, variant, object())]

        with tempfile.TemporaryDirectory() as folder:
            ctx = type("Context", (), {
                "palette": palette,
                "nml_output_folder": folder,
            })()
            processor._compose_purchase_sprites(ctx)

            self.assertIsNone(variant.purchase_spriteset)
            self.assertEqual(list(Path(folder).glob("purchase_*.png")), [])

    def test_shorter_part_bottom_aligns_and_clips_from_the_top(self):
        """A 12px part shares the 13px baseline with a 13px part, not the top edge."""
        palette = PalettedImage.load_palette(
            str(REPO_ROOT / "Sprites" / "ttd-newgrf-dos.gpl")
        )
        tall = self._part(palette, 10, "tall")
        short = self._part(palette, 20, "short", height=12)

        with tempfile.TemporaryDirectory() as folder:
            result = PurchaseSpriteComposer(palette).compose(
                [tall, short], Path(folder) / "mixed.png"
            )
            with Image.open(result[0].file) as icon:
                icon = icon.convert("RGB")
                self.assertEqual(icon.getpixel((4, 12)), tuple(palette[60:63]))
                self.assertEqual(icon.getpixel((4, 0)), (0, 0, 255))
                self.assertEqual(icon.getpixel((0, 0)), tuple(palette[30:33]))

    def test_composition_failure_keeps_the_existing_icon_and_warns(self):
        palette = PalettedImage.load_palette(
            str(REPO_ROOT / "Sprites" / "ttd-newgrf-dos.gpl")
        )
        profile = Profile("DEFAULT")
        livery = Livery("Default")
        vehicle = Vehicle(
            folder_path=".", identifier="root", name="Root",
            vehicle_type=VehicleType.TRAM, train_type=TrainType.COACH,
            profiles=[profile], liveries=[livery],
        )
        variant = Variant(vehicle, livery, profile, vehicleType=VehicleType.TRAM)
        variant.identifier = "root_default_default_tram"
        existing = self._part(palette, 10, "existing")
        variant.purchase_spriteset = existing.spriteset
        variant.purchase_template_name = "tmpl_purchase"
        variant.purchase_sprite_parts = [self._part(palette, 10, "root")]
        variant.articulated_part_variants = [SimpleNamespace(
            purchase_sprite_parts=[self._part(palette, 20, "hidden")]
        )]
        processor = CandidateProcessor(Builder())
        processor._pending_variants = [(vehicle, variant, object())]

        with tempfile.TemporaryDirectory() as folder, patch.object(
            PurchaseSpriteComposer, "compose", side_effect=OSError("unreadable sheet")
        ), self.assertLogs("Builder.CandidateProcessor", level="WARNING") as captured:
            ctx = type("Context", (), {
                "palette": palette,
                "nml_output_folder": folder,
            })()
            processor._compose_purchase_sprites(ctx)

        self.assertIs(variant.purchase_spriteset, existing.spriteset)
        self.assertIn("Unable to compose the purchase icon", captured.output[0])


if __name__ == "__main__":
    unittest.main()
