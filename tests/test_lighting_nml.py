import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from NmlWriter.NmlVariantWriter import NmlVariantWriter
from PropertyCalculation import VehicleType
from Sprites.LightingOverlay import Detection
from Sprites.Sprite import Sprite
from Sprites.Spriteset import Spriteset
from Templates.Template import Template

BOXES = ((0, 0, 8, 24), (86, 0, 8, 24))


def _spriteset(name, file, x, y):
    sprites = [
        Sprite(left_x=left, upper_y=top, width=width, height=height, offset_x=0, offset_y=0)
        for left, top, width, height in BOXES
    ]
    return Spriteset(name=name, file=file, template=Template(name="row_0", sprites=sprites), x=x, y=y)


def _variant(*, lighting):
    identifier = "br_test_1_car_train"
    variant = SimpleNamespace(
        identifier=identifier,
        vehicle=SimpleNamespace(identifier="br_test"),
        nml_filename=f"{identifier}.nml",
        vehicle_type=VehicleType.TRAIN,
        properties={"name": "string(str_br_test_1_car_train_name)"},
        callbacks={"default": f"sw_{identifier}"},
        spritesets=[_spriteset(f"spriteset_{identifier}_0", "sheet.png", 0, 0)],
        spriteset_names=[f"spriteset_{identifier}_0"],
        sprite_template_names=["tmpl_train_8_old"],
        sprite_switch_name=f"sw_{identifier}",
        purchase_spriteset=None,
        purchase_template_name=None,
        articulated_switch_name=None,
        articulated_count=None,
        length_switch_name=None,
        sprite_lengths=None,
        nml_override={},
        lighting_switch_name=None,
        lighting_overlay_path=None,
        lighting_transparent_path=None,
        lighting_detection=None,
    )
    if lighting:
        variant.lighting_switch_name = f"sw_{identifier}_layers"
        variant.lighting_overlay_path = Path("/tmp/lights.png")
        variant.lighting_transparent_path = Path("/tmp/transparent.png")
        variant.lighting_detection = Detection(pixels={(86, 20): 0xB7}, rows={0}, pairs=1)
        variant.callbacks["default"] = variant.lighting_switch_name
    return variant


class LightingNmlTests(unittest.TestCase):
    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.output = Path(self._folder.name)

    def tearDown(self):
        self._folder.cleanup()

    def _write(self, variant) -> str:
        path = NmlVariantWriter(variant, str(self.output)).write()
        return Path(path).read_text()

    def test_layered_chain_is_emitted_for_a_variant_with_lamps(self):
        text = self._write(_variant(lighting=True))
        identifier = "br_test_1_car_train"
        # layer 0 draws the published spriteset and asks for a second layer
        self.assertIn(f"sw_{identifier}_layers_l0_0, STORE_TEMP(CB_FLAG_MORE_SPRITES", text)
        # layer 1 draws the overlay and clears the "more sprites" flag
        self.assertIn(f"sw_{identifier}_layers_l1_0, STORE_TEMP(PALETTE_IDENTITY, 0x100)", text)
        self.assertIn("/tmp/lights.png", text)
        self.assertIn("/tmp/transparent.png", text)
        # the state switch pairs the flip flag with the backing-up flag
        self.assertIn("vehicle_is_flipped != train_is_driving_backwards", text)
        # the stack root reads the iteration number of variable 10
        self.assertIn(f"sw_{identifier}_layers, getbits(extra_callback_info1, 8, 8)", text)
        # and the item's graphics chain points at the layered root
        self.assertIn(f"default: sw_{identifier}_layers;", text)

    def test_no_lighting_emits_the_plain_chain(self):
        text = self._write(_variant(lighting=False))
        identifier = "br_test_1_car_train"
        self.assertNotIn("STORE_TEMP", text)
        self.assertNotIn("vehicle_is_flipped", text)
        self.assertIn(f"default: sw_{identifier};", text)

    def test_overlay_image_is_the_size_of_the_base_sheet(self):
        # only the geometry matters here: the overlay is written at the base sheet's coordinates
        sheet = self.output / "sheet.png"
        image = Image.new("P", (171, 25), 0)
        image.putpalette([index % 256 for index in range(768)])
        image.save(sheet)
        from Sprites.LightingOverlay import overlay_image

        overlay = overlay_image(sheet, Detection(pixels={(86, 20): 0xB7}))
        self.assertEqual(overlay.size, (171, 25))
        self.assertEqual(overlay.getpixel((86, 20)), 0xB7)
        self.assertEqual(overlay.getpixel((0, 0)), 0)


if __name__ == "__main__":
    unittest.main()
