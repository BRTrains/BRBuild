import tempfile
import unittest
from pathlib import Path

from PIL import Image

from Sprites.PalettedImage import PURE_WHITE, PalettedImage

REPO_ROOT = Path(__file__).resolve().parent.parent
PALETTE = PalettedImage.load_palette(str(REPO_ROOT / "Sprites" / "ttd-newgrf-dos.gpl"))


class WithoutTransparencyTests(unittest.TestCase):
    """Transparency is removed at load, taking the sheet's own lightest white."""

    def test_transparent_pixels_take_the_sheets_lightest_white(self):
        image = Image.new("RGBA", (3, 1))
        # Art in a near-white (an artist's own white) beside a lamp and a black outline,
        # with transparent pixels stored in two different colours.
        image.putdata(
            [
                (254, 254, 254, 255),
                (0, 0, 255, 0),
                (16, 16, 16, 0),
            ]
        )

        flattened = PalettedImage.without_transparency(image)

        self.assertEqual(flattened.mode, "RGB")
        self.assertNotIn("A", flattened.getbands())
        self.assertEqual(flattened.getpixel((1, 0)), (254, 254, 254))
        self.assertEqual(flattened.getpixel((2, 0)), (254, 254, 254))
        self.assertEqual(flattened.getpixel((0, 0)), (254, 254, 254))

    def test_takes_the_lightest_white_when_the_sheet_has_several(self):
        image = Image.new("RGBA", (3, 1))
        image.putdata([(252, 252, 252, 255), (255, 255, 255, 255), (0, 0, 255, 0)])

        flattened = PalettedImage.without_transparency(image)

        self.assertEqual(flattened.getpixel((2, 0)), (255, 255, 255))

    def test_a_sheet_without_any_white_falls_back_to_pure_white(self):
        image = Image.new("RGBA", (2, 1))
        image.putdata([(168, 168, 168, 255), (0, 0, 255, 0)])

        flattened = PalettedImage.without_transparency(image)

        self.assertEqual(flattened.getpixel((1, 0)), PURE_WHITE)

    def test_a_sheet_without_transparency_is_untouched(self):
        image = Image.new("P", (2, 1))
        image.putpalette(PALETTE)
        image.putdata([1, 2])

        self.assertIs(PalettedImage.without_transparency(image), image)

    def test_palette_transparency_is_removed_too(self):
        image = Image.new("P", (2, 1))
        image.putpalette(PALETTE)
        image.putdata([255, 0])
        image.info["transparency"] = 0

        flattened = PalettedImage.without_transparency(image)

        self.assertEqual(flattened.mode, "RGB")

    def test_load_removes_transparency_from_a_file(self):
        image = Image.new("RGBA", (2, 1))
        image.putdata([(255, 255, 255, 255), (0, 0, 255, 0)])

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sheet.png"
            image.save(path)

            loaded = PalettedImage.load(str(path), PALETTE)

        self.assertEqual(loaded.image.mode, "RGB")
        self.assertEqual(loaded.image.getpixel((1, 0)), PURE_WHITE)


class IsWhiteTests(unittest.TestCase):
    def test_accepts_white_within_the_gutter_tolerance(self):
        self.assertTrue(PalettedImage.is_white((255, 255, 255)))
        self.assertTrue(PalettedImage.is_white((252, 252, 252)))

    def test_rejects_colours_that_are_not_white(self):
        self.assertFalse(PalettedImage.is_white((251, 251, 251)))
        self.assertFalse(PalettedImage.is_white((255, 255, 200)))
        self.assertFalse(PalettedImage.is_white((0, 0, 255)))


if __name__ == "__main__":
    unittest.main()
