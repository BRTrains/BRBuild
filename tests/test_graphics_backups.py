import tempfile
import unittest
from pathlib import Path

from Builder.Builder import Builder
from Run import reset_project_graphics
from Templates.SpritesheetLegacyConverter import SpritesheetLegacyConverter


class GraphicsBackupTests(unittest.TestCase):
    def test_reset_prefers_new_spritesheet_over_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            vehicle_folder = root / "Thomas"
            vehicle_folder.mkdir()
            image = vehicle_folder / "Thomas.png"
            image.write_bytes(b"processed")
            original = vehicle_folder / "original" / "Thomas.png"
            original.parent.mkdir()
            original.write_bytes(b"old")
            new_image = vehicle_folder / "new" / "revision.png"
            new_image.parent.mkdir()
            new_image.write_bytes(b"new")
            (vehicle_folder / "Thomas.yaml").write_text("vehicle: Thomas")

            class Project:
                path = root

            self.assertEqual(reset_project_graphics(Project()), 1)
            self.assertFalse(new_image.exists())
            self.assertEqual(original.read_bytes(), b"new")
            self.assertEqual(image.read_bytes(), b"new")

    def test_new_spritesheet_is_moved_to_original_and_promoted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / "Thomas.png"
            image.write_bytes(b"old")
            new_image = root / "new" / "thomas_revision.png"
            new_image.parent.mkdir()
            new_image.write_bytes(b"new")

            class Vehicle:
                yaml_path = str(root / "Thomas.yaml")

                @property
                def spritesheet_path(self):
                    return str(Path(self.yaml_path).with_suffix(".png"))

            self.assertTrue(Builder._ingest_new_spritesheet(Vehicle()))
            self.assertFalse(new_image.exists())
            self.assertEqual((root / "original" / "Thomas.png").read_bytes(), b"new")
            self.assertEqual(image.read_bytes(), b"new")

    def test_original_folder_backup_is_immutable_and_resettable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / "Thomas.png"
            image.write_bytes(b"original")
            converter = SpritesheetLegacyConverter([], [0] * 768)

            converter._archive(image)
            image.write_bytes(b"processed")
            converter._archive(image)

            original = root / "original" / "Thomas.png"
            (root / "Thomas_working.png").write_bytes(b"obsolete")
            self.assertEqual(original.read_bytes(), b"original")

            class Project:
                path = root

            self.assertEqual(reset_project_graphics(Project()), 1)
            self.assertEqual(image.read_bytes(), b"original")
            self.assertFalse((root / "Thomas_working.png").exists())

    def test_legacy_backup_is_migrated(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / "Thomas.png"
            image.write_bytes(b"processed")
            legacy = root / "Thomas_original.png"
            legacy.write_bytes(b"original")

            SpritesheetLegacyConverter([], [0] * 768)._archive(image)

            self.assertEqual((root / "original" / "Thomas.png").read_bytes(), b"original")
            self.assertFalse(legacy.exists())


if __name__ == "__main__":
    unittest.main()