import unittest
from pathlib import Path

from Templates.TemplateGenerator import TemplateGenerator


REPO_ROOT = Path(__file__).resolve().parents[1]


class TemplateGeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.definitions = TemplateGenerator(REPO_ROOT / "Templates" / "archive").definitions()
        cls.by_name = {definition.name: definition for definition in cls.definitions}

    def test_generates_the_complete_archived_catalogue(self):
        self.assertEqual(len(self.definitions), 29)
        self.assertIn("tmpl_train_8", self.by_name)
        self.assertIn("tmpl_tram_5_tall", self.by_name)
        self.assertIn("tmpl_train_8_old_reversed", self.by_name)

    def test_applies_corrected_modern_train_offsets(self):
        boxes = self.by_name["tmpl_train_8"].bounding_boxes
        self.assertEqual(
            [(box.offset_x, box.offset_y) for box in boxes],
            [(-3, -13), (-15, -11), (-15, -9), (-5, -11),
             (-3, -13), (-15, -11), (-16, -9), (-5, -11)],
        )

    def test_preserves_tall_tram_geometry(self):
        boxes = self.by_name["tmpl_tram_5_tall"].bounding_boxes
        self.assertEqual([box.height for box in boxes], [25, 22, 19, 22, 25, 22, 19, 22])
        self.assertEqual([(box.offset_x, box.offset_y) for box in boxes], [
            (-3, -19), (0, -17), (-8, -15), (-8, -14),
            (-3, -19), (-12, -13), (-15, -15), (-8, -16),
        ])

    def test_does_not_adjust_legacy_train_offsets(self):
        boxes = self.by_name["tmpl_train_8_old"].bounding_boxes
        self.assertEqual((boxes[0].offset_x, boxes[0].offset_y), (-3, -11))
        self.assertEqual((boxes[7].offset_x, boxes[7].offset_y), (-4, -10))


if __name__ == "__main__":
    unittest.main()
