import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from Sprites.SheetDetectionCache import SheetDetectionCache
from Sprites.Sprite import Sprite
from Sprites.Spriteset import Spriteset
from Templates.BoundingBox import BoundingBox
from Templates.Template import Template
from Templates.TemplateDefinition import TemplateDefinition
from Templates.TemplateLoaderNML import TemplateLoaderNML
from Templates.TemplateType import TemplateType

#: Root of the BRBuild checkout, so tests never depend on a machine-specific absolute path.
REPO_ROOT = Path(__file__).resolve().parents[1]

PALETTE = [index % 256 for index in range(768)]


def _definition(name="tmpl_train_7", length=7, height=13):
    return TemplateDefinition(
        name=name,
        template_type=TemplateType.VEHICLE,
        vehicle_type="train",
        length=length,
        bounding_boxes=[BoundingBox(0, 0, 8, height, -3, -12, [])],
    )


def _rows(definition=None, y=13, views=((0, 0, 8, 13), (9, 0, 20, 12))):
    definition = definition or _definition()
    sprites = [
        Sprite(left_x=left, upper_y=top, width=width, height=height, offset_x=0, offset_y=0)
        for left, top, width, height in views
    ]
    spriteset = Spriteset(
        name=f"spriteset_y{y}",
        file="sheet.png",
        template=Template(name="row_0", sprites=sprites),
        x=0,
        y=y,
    )
    return [(spriteset, definition)]


class SheetDetectionCacheTests(unittest.TestCase):
    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.root = Path(self._folder.name)
        self.sheet = self.root / "sheet.png"
        self.sheet.write_bytes(b"not really a png, but the cache only hashes it")

    def tearDown(self):
        self._folder.cleanup()

    def _cache(self, **overrides):
        arguments = {
            "sheet_path": self.sheet,
            "palette": PALETTE,
            "definitions": [_definition()],
            "vehicle_type": "train",
        }
        arguments.update(overrides)
        return SheetDetectionCache(**arguments)

    def test_rows_round_trip(self):
        cache = self._cache()
        cache.store(_rows())

        self.assertTrue(cache.path.is_file())
        self.assertEqual(cache.path.name, "sheet.png.sheetcache.json")

        loaded = cache.load()

        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded), 1)
        spriteset, definition = loaded[0]
        self.assertEqual(definition.name, "tmpl_train_7")
        self.assertEqual((spriteset.x, spriteset.y), (0, 13))
        self.assertEqual(spriteset.file, "sheet.png")
        self.assertEqual(
            [(sprite.left_x, sprite.upper_y, sprite.width, sprite.height, sprite.offset_x, sprite.offset_y)
             for sprite in spriteset.template.sprites],
            [(0, 0, 8, 13, 0, 0), (9, 0, 20, 12, 0, 0)],
        )

    def test_no_cache_file_is_a_miss(self):
        self.assertIsNone(self._cache().load())

    def test_changed_sheet_is_a_miss(self):
        cache = self._cache()
        cache.store(_rows())

        self.sheet.write_bytes(b"different art")

        self.assertIsNone(cache.load())

    def test_changed_palette_is_a_miss(self):
        cache = self._cache()
        cache.store(_rows())

        other_palette = list(PALETTE)
        other_palette[0] = 255

        self.assertIsNone(self._cache(palette=other_palette).load())

    def test_changed_template_geometry_is_a_miss(self):
        cache = self._cache()
        cache.store(_rows())

        moved = _definition()
        moved.bounding_boxes[0].height = 20

        self.assertIsNone(self._cache(definitions=[moved]).load())

    def test_changed_vehicle_type_is_a_miss(self):
        cache = self._cache()
        cache.store(_rows())

        self.assertIsNone(self._cache(vehicle_type="tram").load())

    def test_unknown_definition_is_a_miss(self):
        self._cache().store(_rows())

        self.assertIsNone(self._cache(definitions=[_definition(name="tmpl_train_6", length=6)]).load())

    def test_corrupt_cache_file_is_ignored(self):
        cache = self._cache()
        cache.path.write_text("{ not json", encoding="utf-8")

        with self.assertLogs("Sprites.SheetDetectionCache", level="WARNING"):
            self.assertIsNone(cache.load())

    def test_empty_rows_are_not_stored(self):
        self._cache().store([])

        self.assertFalse(self._cache().path.is_file())

    def test_allocator_reuses_the_cache_instead_of_detecting_again(self):
        """A second build must not re-detect an unchanged sheet at all."""
        definitions = TemplateLoaderNML().read_folder(str(REPO_ROOT / "Templates"))
        template = next(d for d in definitions if d.name == "tmpl_train_7")

        sheet = Image.new("P", (200, 30), color=0)
        sheet.putpalette(PALETTE)
        sheet.save(self.sheet)

        views = [
            Sprite(left_x=box.left_x, upper_y=box.upper_y, width=box.width, height=box.height, offset_x=0, offset_y=0)
            for box in template.bounding_boxes
        ]
        detected = [
            Spriteset(
                name="spriteset_y0",
                file=str(self.sheet),
                template=Template(name="row_0", sprites=views),
                x=0,
                y=0,
            )
        ]

        from Vehicle.VariantSpriteGroups import VehicleSpriteAllocator
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(folder_path=str(self.root), identifier="example", name="Example")
        vehicle.yaml_path = str(self.root / "sheet.yaml")
        vehicle.vehicle_type = "train"
        vehicle.power_type = ["diesel"]

        with patch("Sprites.SpritesheetExtractor.SpritesheetExtractor.extract_spritesets", return_value=detected):
            first = VehicleSpriteAllocator(vehicle, PALETTE, definitions)

        self.assertTrue(self._cache(definitions=definitions).path.is_file())
        self.assertEqual(len(first.vehicle_rows), 1)

        def fail_detection(*args, **kwargs):
            raise AssertionError("the build detected rows for a sheet it had already cached")

        with patch("Sprites.SpritesheetExtractor.SpritesheetExtractor.extract_spritesets", fail_detection):
            second = VehicleSpriteAllocator(vehicle, PALETTE, definitions)

        self.assertEqual(
            [(spriteset.y, definition.name) for spriteset, definition in second.vehicle_rows],
            [(spriteset.y, definition.name) for spriteset, definition in first.vehicle_rows],
        )

    def test_allocator_does_not_load_image_when_detection_is_cached(self):
        """A warm detection-cache hit must avoid opening the sheet image."""
        definitions = TemplateLoaderNML().read_folder(str(REPO_ROOT / "Templates"))
        template = next(d for d in definitions if d.name == "tmpl_train_7")
        sheet = Image.new("P", (200, 30), color=0)
        sheet.putpalette(PALETTE)
        sheet.save(self.sheet)

        views = [
            Sprite(left_x=box.left_x, upper_y=box.upper_y, width=box.width, height=box.height, offset_x=0, offset_y=0)
            for box in template.bounding_boxes
        ]
        detected = [Spriteset("spriteset_y0", str(self.sheet), Template("row_0", sprites=views), 0, 0)]

        from Vehicle.VariantSpriteGroups import VehicleSpriteAllocator
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(folder_path=str(self.root), identifier="example", name="Example")
        vehicle.yaml_path = str(self.root / "sheet.yaml")
        vehicle.vehicle_type = "train"
        vehicle.power_type = ["diesel"]

        with patch("Sprites.SpritesheetExtractor.SpritesheetExtractor.extract_spritesets", return_value=detected):
            VehicleSpriteAllocator(vehicle, PALETTE, definitions)

        with patch("Sprites.SpritesheetExtractor.SpritesheetExtractor.__init__", side_effect=AssertionError("warm cache loaded the image")):
            VehicleSpriteAllocator(vehicle, PALETTE, definitions)

    def test_generated_sprites_are_only_rewritten_when_they_change(self):
        from Vehicle.VariantSpriteGroups import VehicleSpriteAllocator

        target = self.root / "purchase.png"
        first = Image.new("P", (128, 13), color=3)
        first.putpalette(PALETTE)
        VehicleSpriteAllocator._write_if_changed(target, first)

        stat = target.stat()
        original = target.read_bytes()

        same = Image.new("P", (128, 13), color=3)
        same.putpalette(PALETTE)
        VehicleSpriteAllocator._write_if_changed(target, same)

        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(target.stat().st_mtime_ns, stat.st_mtime_ns, "an unchanged sprite was rewritten")

        changed = Image.new("P", (128, 13), color=7)
        changed.putpalette(PALETTE)
        VehicleSpriteAllocator._write_if_changed(target, changed)

        self.assertNotEqual(target.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
