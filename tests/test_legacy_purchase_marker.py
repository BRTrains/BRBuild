import tempfile
import unittest
from pathlib import Path

from PIL import Image

from Sprites.PalettedImage import PalettedImage
from Sprites.SpritesheetExtractor import SpritesheetExtractor

REPO_ROOT = Path(__file__).resolve().parent.parent
PALETTE = PalettedImage.load_palette(str(REPO_ROOT / "Sprites" / "ttd-newgrf-dos.gpl"))

ART = (16, 16, 16)
MARKER_RED = (255, 0, 0)
MARKER_YELLOW = (255, 255, 0)
QUANTISED_RED = (252, 0, 0)
QUANTISED_YELLOW = (252, 252, 0)

#: The legacy layout: an 87x12 purchase block, the 36px marker row, then the first vehicle
#: row of eight views, with a gutter below it.
SHEET_SIZE = (113, 33)
PURCHASE_HEIGHT = 12
MARKER_Y = 12
VEHICLE_Y = 13
VEHICLE_VIEW_PITCH = 14
VEHICLE_VIEW_WIDTH = 8
VEHICLE_HEIGHT = 18
MARKER_START = 51


def build_sheet(red, yellow) -> Image.Image:
    """An artist sheet in the legacy layout, with the marker drawn in the given colours."""
    sheet = Image.new("RGB", SHEET_SIZE, (255, 255, 255))

    for y in range(PURCHASE_HEIGHT):
        for x in range(87):
            sheet.putpixel((x, y), ART)

    marker = [(MARKER_START, 4, red), (MARKER_START + 4, 20, yellow), (MARKER_START + 24, 12, red)]
    for start, length, colour in marker:
        for x in range(start, start + length):
            sheet.putpixel((x, MARKER_Y), colour)

    for y in range(VEHICLE_Y, VEHICLE_Y + VEHICLE_HEIGHT):
        for view in range(8):
            for x in range(view * VEHICLE_VIEW_PITCH, view * VEHICLE_VIEW_PITCH + VEHICLE_VIEW_WIDTH):
                sheet.putpixel((x, y), ART)

    return sheet


class LegacyPurchaseMarkerTests(unittest.TestCase):
    """The legacy 36px red/yellow marker row ends the row holding the purchase block.

    A sheet that is not already paletted only reaches the detector through the palette
    stage's quantisation, which lands the marker's exact red and yellow on the palette's
    nearest shades. An exact colour comparison never sees a marker, so the purchase block
    merged with the first vehicle row and the unit built with no graphics at all.
    """

    def extract(self, sheet: Image.Image):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sheet.png"
            sheet.save(path)

            return SpritesheetExtractor(str(path), PALETTE).extract_spritesets()

    def test_exact_marker_separates_the_purchase_block_from_the_vehicle_row(self):
        rows = self.extract(build_sheet(MARKER_RED, MARKER_YELLOW))

        self.assertEqual([row.y for row in rows], [0, VEHICLE_Y])
        self.assertEqual([len(row.template.sprites) for row in rows], [1, 8])
        self.assertEqual(rows[0].template.sprites[0].width, 87)
        self.assertEqual(rows[0].template.sprites[0].height, PURCHASE_HEIGHT)

    def test_marker_quantised_onto_the_palettes_own_shades_is_still_a_marker(self):
        rows = self.extract(build_sheet(QUANTISED_RED, QUANTISED_YELLOW))

        self.assertEqual([row.y for row in rows], [0, VEHICLE_Y])
        self.assertEqual([len(row.template.sprites) for row in rows], [1, 8])

    def test_a_row_of_other_colours_is_not_a_marker(self):
        rows = self.extract(build_sheet((0, 0, 255), (0, 0, 255)))

        self.assertEqual([row.y for row in rows], [0], "a non-marker row must not end the purchase row")
        self.assertEqual(len(rows[0].template.sprites), 1)


if __name__ == "__main__":
    unittest.main()
