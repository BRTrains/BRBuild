import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from Sprites.Sprite import Sprite
from Sprites.Spriteset import Spriteset
from Templates.BoundingBox import BoundingBox
from Templates.SpritesheetLegacyConverter import SpritesheetLegacyConverter
from Templates.Template import Template
from Templates.TemplateDefinition import TemplateDefinition
from Templates.TemplateType import TemplateType


PALETTE = [index % 256 for index in range(768)]


class SpritesheetConverterTests(unittest.TestCase):
    def test_unchanged_normalized_sheet_skips_extraction(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sheet.png"
            source = Image.new("P", (8, 8), color=3)
            source.putpalette(PALETTE)
            source.save(path)

            definition = TemplateDefinition(
                name="tmpl_train_7",
                template_type=TemplateType.VEHICLE,
                vehicle_type="train",
                length=7,
                bounding_boxes=[BoundingBox(0, 0, 8, 8, 0, 0, [])],
            )
            row = Spriteset(
                name="spriteset_y0",
                file=str(path),
                template=Template(
                    name="detected",
                    sprites=[Sprite(0, 0, 8, 8, 0, 0)],
                ),
                x=0,
                y=0,
            )
            fake_extractor = SimpleNamespace(
                image=source,
                extract_spritesets=lambda: [row],
            )
            converter = SpritesheetLegacyConverter([definition], PALETTE)

            with patch(
                "Templates.SpritesheetLegacyConverter.SpritesheetExtractor",
                return_value=fake_extractor,
            ) as extractor, patch(
                "Templates.SpritesheetLegacyConverter.classify_row",
                return_value=definition,
            ):
                converter.process(str(path), "train")
                extractor.reset_mock()
                reused = converter.process(str(path), "train")

            extractor.assert_not_called()
            self.assertIsNone(reused)


if __name__ == "__main__":
    unittest.main()
