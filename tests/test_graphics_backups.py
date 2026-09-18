import tempfile
import unittest
from pathlib import Path

from Run import reset_project_graphics
from Templates.SpritesheetLegacyConverter import SpritesheetLegacyConverter


class GraphicsBackupTests(unittest.TestCase):
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