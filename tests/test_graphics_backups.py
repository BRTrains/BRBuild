import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from Builder.Builder import Builder
from Builder.BuildContext import BuildContext
from Run import reset_project_graphics
from Templates.SpritesheetLegacyConverter import SpritesheetLegacyConverter
from PropertyCalculation.VehicleType import VehicleType
from Vehicle.Vehicle import Vehicle


def make_vehicle(folder: Path, identifier: str = "Thomas") -> Vehicle:
    """A real Vehicle, so the spritesheet_path property resolves like a build does."""
    return Vehicle(
        folder_path=str(folder),
        identifier=identifier,
        name=identifier,
        yaml_path=str(folder / f"{identifier}.yaml"),
    )


class GraphicsBackupTests(unittest.TestCase):
    def test_existing_spritesheet_is_not_normalized_in_place(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "Thomas.png").write_bytes(b"existing")
            vehicle = SimpleNamespace(identifier="Thomas", yaml_path=str(root / "Thomas.yaml"))
            context = BuildContext(palette=[0] * 768, template_definitions=[])

            with patch.object(Builder, "_convert_spritesheet") as convert:
                with patch(
                    "Builder.Builder.VehicleSpriteAllocator",
                    lambda vehicle, palette, definitions: SimpleNamespace(),
                ):
                    Builder()._load_sprite_allocator(vehicle, context)

            convert.assert_not_called()
            self.assertEqual((root / "Thomas.png").read_bytes(), b"existing")

    def test_ingested_spritesheet_is_normalized_in_place(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "Thomas.png").write_bytes(b"ingested")
            vehicle = SimpleNamespace(
                identifier="Thomas",
                yaml_path=str(root / "Thomas.yaml"),
                vehicle_type=VehicleType.TRAIN,
            )
            context = BuildContext(palette=[0] * 768, template_definitions=[])
            calls = []

            with patch.object(Builder, "_convert_spritesheet", side_effect=lambda v, c: calls.append(v)):
                with patch(
                    "Builder.Builder.VehicleSpriteAllocator",
                    lambda vehicle, palette, definitions: SimpleNamespace(),
                ):
                    Builder()._load_sprite_allocator(vehicle, context, normalize=True)

            self.assertEqual([call.identifier for call in calls], ["Thomas"])

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

    def test_new_spritesheet_is_staged_into_working_before_publishing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / "Thomas.png"
            image.write_bytes(b"old")
            new_image = root / "new" / "thomas_revision.png"
            new_image.parent.mkdir()
            new_image.write_bytes(b"new")
            vehicle = make_vehicle(root)
            context = BuildContext()

            self.assertTrue(Builder._ingest_new_spritesheet(vehicle, context))

            staged = root / "working" / "Thomas.png"
            self.assertEqual(staged.read_bytes(), b"new")
            self.assertEqual(vehicle.spritesheet_override, str(staged))
            self.assertEqual([item["working_path"] for item in context.pending_sprite_ingests], [staged])
            # Nothing is published until the build succeeds.
            self.assertEqual(image.read_bytes(), b"old")
            self.assertTrue(new_image.exists())
            self.assertFalse((root / "original" / "Thomas.png").exists())

    def test_successful_build_publishes_staged_sheet_and_empties_new(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / "Thomas.png"
            image.write_bytes(b"old")
            new_image = root / "new" / "thomas_revision.png"
            new_image.parent.mkdir()
            new_image.write_bytes(b"new")
            vehicle = make_vehicle(root)
            context = BuildContext()
            Builder._ingest_new_spritesheet(vehicle, context)

            Builder()._finalize_sprite_ingests(context)

            staged = root / "working" / "Thomas.png"
            self.assertEqual(image.read_bytes(), b"new")
            self.assertEqual((root / "original" / "Thomas.png").read_bytes(), b"new")
            self.assertEqual(staged.read_bytes(), b"new")
            self.assertFalse(new_image.exists())
            self.assertEqual(list((root / "new").iterdir()), [])
            self.assertEqual(context.pending_sprite_ingests, [])

    def test_only_latest_ingestion_is_retained(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "Thomas.png").write_bytes(b"published")
            new_folder = root / "new"
            new_folder.mkdir()
            first = new_folder / "first.png"
            first.write_bytes(b"first")
            vehicle = make_vehicle(root)
            context = BuildContext()
            Builder._ingest_new_spritesheet(vehicle, context)
            first.unlink()
            (new_folder / "second.png").write_bytes(b"second")

            vehicle.spritesheet_override = None
            context.pending_sprite_ingests.clear()
            Builder._ingest_new_spritesheet(vehicle, context)

            self.assertEqual(sorted(path.name for path in (root / "working").iterdir()), ["Thomas.png"])
            self.assertEqual((root / "working" / "Thomas.png").read_bytes(), b"second")

    def test_publishing_archives_the_raw_ingested_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "Thomas.png").write_bytes(b"published")
            new_image = root / "new" / "thomas_revision.png"
            new_image.parent.mkdir()
            new_image.write_bytes(b"raw source with artist notes")
            vehicle = make_vehicle(root)
            context = BuildContext()
            Builder._ingest_new_spritesheet(vehicle, context)
            # Simulate the normalizer rewriting the staged working copy.
            (root / "working" / "Thomas.png").write_bytes(b"normalised")
            (root / "working" / "Thomas.png.cache").write_bytes(b"cache")
            (root / "working" / "original").mkdir()
            (root / "working" / "original" / "Thomas.png").write_bytes(b"pre-normalisation")

            Builder()._finalize_sprite_ingests(context)

            self.assertEqual((root / "Thomas.png").read_bytes(), b"normalised")
            self.assertEqual(
                (root / "original" / "Thomas.png").read_bytes(),
                b"raw source with artist notes",
            )
            self.assertEqual([path.name for path in (root / "working").iterdir()], ["Thomas.png"])

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