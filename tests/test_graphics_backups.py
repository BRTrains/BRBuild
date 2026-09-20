import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from Builder.Builder import Builder
from Builder.BuildContext import BuildContext
from Run import reset_project_graphics
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


def make_context(folder: Path) -> BuildContext:
    return BuildContext(nml_output_folder=str(folder / "WorkingData" / "Project"))


def drop_new_sheet(root: Path, name: str, payload: bytes) -> Path:
    new_image = root / "new" / name
    new_image.parent.mkdir(parents=True, exist_ok=True)
    new_image.write_bytes(payload)
    return new_image


class GraphicsBackupTests(unittest.TestCase):
    def test_existing_spritesheet_is_not_normalized_in_place(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "Thomas.png").write_bytes(b"existing")
            vehicle = SimpleNamespace(identifier="Thomas", yaml_path=str(root / "Thomas.yaml"))
            context = make_context(root)

            with patch.object(Builder, "_convert_spritesheet") as convert:
                with patch(
                    "Builder.Builder.VehicleSpriteAllocator",
                    lambda vehicle, palette, definitions: SimpleNamespace(),
                ):
                    Builder()._load_sprite_allocator(vehicle, context)

            convert.assert_not_called()
            self.assertEqual((root / "Thomas.png").read_bytes(), b"existing")

    def test_ingested_spritesheet_is_normalized(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "Thomas.png").write_bytes(b"ingested")
            vehicle = SimpleNamespace(
                identifier="Thomas",
                yaml_path=str(root / "Thomas.yaml"),
                vehicle_type=VehicleType.TRAIN,
            )
            context = make_context(root)
            calls = []

            with patch.object(Builder, "_convert_spritesheet", side_effect=lambda v, c: calls.append(v)):
                with patch(
                    "Builder.Builder.VehicleSpriteAllocator",
                    lambda vehicle, palette, definitions: SimpleNamespace(),
                ):
                    Builder()._load_sprite_allocator(vehicle, context, normalize=True)

            self.assertEqual([call.identifier for call in calls], ["Thomas"])

    def test_new_spritesheet_is_staged_outside_the_source_tree_before_publishing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / "Thomas.png"
            image.write_bytes(b"old")
            new_image = drop_new_sheet(root, "thomas_revision.png", b"new")
            vehicle = make_vehicle(root)
            context = make_context(root)

            self.assertTrue(Builder._ingest_new_spritesheet(vehicle, context))

            staged = Path(context.nml_output_folder) / "ingest" / "Thomas" / "Thomas.png"
            self.assertEqual(staged.read_bytes(), b"new")
            self.assertEqual(vehicle.spritesheet_override, str(staged))
            self.assertEqual(
                [item["staging_path"] for item in context.pending_sprite_ingests], [staged]
            )
            # Nothing is published until the build succeeds.
            self.assertEqual(image.read_bytes(), b"old")
            self.assertTrue(new_image.exists())
            self.assertFalse((root / "ingested").exists())

    def test_successful_build_publishes_staged_sheet_and_empties_new(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / "Thomas.png"
            image.write_bytes(b"old")
            new_image = drop_new_sheet(root, "thomas_revision.png", b"new")
            vehicle = make_vehicle(root)
            context = make_context(root)
            Builder._ingest_new_spritesheet(vehicle, context)

            Builder()._finalize_sprite_ingests(context)

            self.assertEqual(image.read_bytes(), b"new")
            self.assertEqual((root / "ingested" / "Thomas.png").read_bytes(), b"new")
            self.assertFalse(new_image.exists())
            self.assertEqual(list((root / "new").iterdir()), [])
            self.assertEqual(context.pending_sprite_ingests, [])
            self.assertFalse((Path(context.nml_output_folder) / "ingest").exists())

    def test_only_latest_ingestion_is_retained(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "Thomas.png").write_bytes(b"published")
            first = drop_new_sheet(root, "first.png", b"first")
            vehicle = make_vehicle(root)
            context = make_context(root)
            Builder._ingest_new_spritesheet(vehicle, context)
            Builder()._finalize_sprite_ingests(context)

            drop_new_sheet(root, "second.png", b"second")
            vehicle.spritesheet_override = None
            Builder._ingest_new_spritesheet(vehicle, context)
            Builder()._finalize_sprite_ingests(context)

            self.assertEqual([path.name for path in (root / "ingested").iterdir()], ["Thomas.png"])
            self.assertEqual((root / "ingested" / "Thomas.png").read_bytes(), b"second")
            self.assertEqual(list((root / "new").iterdir()), [])

    def test_publishing_keeps_the_raw_ingested_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "Thomas.png").write_bytes(b"published")
            drop_new_sheet(root, "thomas_revision.png", b"raw source with artist notes")
            vehicle = make_vehicle(root)
            context = make_context(root)
            Builder._ingest_new_spritesheet(vehicle, context)
            # Simulate the normalizer rewriting the staged copy.
            staged = Path(context.nml_output_folder) / "ingest" / "Thomas" / "Thomas.png"
            staged.write_bytes(b"normalised")

            Builder()._finalize_sprite_ingests(context)

            self.assertEqual((root / "Thomas.png").read_bytes(), b"normalised")
            self.assertEqual(
                (root / "ingested" / "Thomas.png").read_bytes(),
                b"raw source with artist notes",
            )

    def test_ingested_source_is_resettable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / "Thomas.png"
            image.write_bytes(b"processed")
            ingested = root / "ingested" / "Thomas.png"
            ingested.parent.mkdir()
            ingested.write_bytes(b"source")

            class Project:
                path = root

            self.assertEqual(reset_project_graphics(Project()), 1)
            self.assertEqual(image.read_bytes(), b"source")

    def test_reset_prefers_new_spritesheet_over_ingested(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            vehicle_folder = root / "Thomas"
            vehicle_folder.mkdir()
            image = vehicle_folder / "Thomas.png"
            image.write_bytes(b"processed")
            ingested = vehicle_folder / "ingested" / "Thomas.png"
            ingested.parent.mkdir()
            ingested.write_bytes(b"old")
            new_image = vehicle_folder / "new" / "revision.png"
            new_image.parent.mkdir()
            new_image.write_bytes(b"new")
            (vehicle_folder / "Thomas.yaml").write_text("vehicle: Thomas")

            class Project:
                path = root

            self.assertEqual(reset_project_graphics(Project()), 1)
            self.assertFalse(new_image.exists())
            self.assertEqual(ingested.read_bytes(), b"new")
            self.assertEqual(image.read_bytes(), b"new")

    def test_legacy_original_folder_is_migrated_to_ingested(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / "Thomas.png"
            image.write_bytes(b"processed")
            legacy = root / "original" / "Thomas.png"
            legacy.parent.mkdir()
            legacy.write_bytes(b"source")

            class Project:
                path = root

            self.assertEqual(reset_project_graphics(Project()), 1)
            self.assertEqual((root / "ingested" / "Thomas.png").read_bytes(), b"source")
            self.assertEqual(image.read_bytes(), b"source")
            self.assertFalse(legacy.exists())

    def test_legacy_original_sibling_is_migrated_to_ingested(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / "Thomas.png"
            image.write_bytes(b"processed")
            legacy = root / "Thomas_original.png"
            legacy.write_bytes(b"source")

            class Project:
                path = root

            self.assertEqual(reset_project_graphics(Project()), 1)
            self.assertEqual((root / "ingested" / "Thomas.png").read_bytes(), b"source")
            self.assertFalse(legacy.exists())


if __name__ == "__main__":
    unittest.main()
