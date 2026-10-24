import tempfile
import unittest
from pathlib import Path

from Vehicle.Vehicle import resolve_case_insensitive_file


class CaseInsensitivePathTests(unittest.TestCase):
    def test_resolves_existing_file_with_different_case(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            actual = root / "sheet.PNG"
            actual.write_bytes(b"png")
            self.assertEqual(resolve_case_insensitive_file(root / "sheet.png"), str(actual))

    def test_rejects_two_case_variants(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "sheet.PNG").write_bytes(b"one")
            (root / "SHEET.png").write_bytes(b"two")
            with self.assertRaisesRegex(ValueError, "Ambiguous case-insensitive file name"):
                resolve_case_insensitive_file(root / "sheet.png")

    def test_keeps_missing_path_for_new_sheet_ingest(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sheet.png"
            self.assertEqual(resolve_case_insensitive_file(path), str(path))


if __name__ == "__main__":
    unittest.main()
