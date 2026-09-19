import tempfile
import unittest
from pathlib import Path

from Builder.BuildContext import BuildContext
from Builder.Builder import Builder
from NmlWriter.NmlCollator import NmlCollator
from NmlWriter.NmlSpritesetWriter import NmlSpritesetWriter
from NmlWriter.NmlVariantWriter import NmlVariantWriter
from PropertyCalculation.VehicleType import VehicleType
from Project.Project import Project
from Sprites.Sprite import Sprite
from Sprites.Spriteset import Spriteset
from Templates.Template import Template


class BuildPathTests(unittest.TestCase):
    def test_working_data_root_is_project_relative(self):
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            project = Project({"path": str(project_root), "name": "Example", "build": True})
            context = BuildContext(project_data=project)

            Builder()._load_project(context)

            self.assertEqual(
                Path(context.nml_output_folder),
                (project_root / "WorkingData" / "Example").resolve(),
            )
            self.assertTrue(Path(context.nml_output_folder).is_absolute())

    def test_collated_nml_is_written_under_project_root(self):
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)

            output = NmlCollator().collate([], "Example", project_path=project_root)

            self.assertEqual(Path(output), (project_root / "Build" / "Example.nml").resolve())
            self.assertTrue(Path(output).is_file())
            self.assertFalse((Path.cwd() / "Build" / "Example.nml").is_file())

    def test_generated_spriteset_references_existing_png(self):
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            image_path = project_root / "source.png"
            image_path.write_bytes(b"png placeholder")
            spriteset = Spriteset(
                name="source_spriteset",
                file=str(image_path),
                template=Template(name="source", sprites=[Sprite(0, 0, 1, 1, 0, 0)]),
                x=0,
                y=0,
            )
            nml_path = project_root / "variant.gnml"

            with nml_path.open("w", encoding="utf-8") as output:
                NmlSpritesetWriter().write(output, spriteset, "tmpl_purchase")

            emitted_path = Path(nml_path.read_text(encoding="utf-8").split('"')[1])
            self.assertTrue(emitted_path.is_file())

    def test_item_with_sprite_id_declares_new_graphics_property(self):
        from io import StringIO

        class Variant:
            identifier = "example_train"
            nml_filename = "example_train.gnml"
            vehicle_type = VehicleType.TRAIN
            sprite_id = 1234
            properties = {}
            callbacks = {}

        output = StringIO()
        writer = NmlVariantWriter(Variant(), "/tmp")
        writer.write_item(output, Variant())

        self.assertIn("sprite_id: SPRITE_ID_NEW_TRAIN;", output.getvalue())

    def test_variant_groups_liveries_under_profile(self):
        class Profile:
            def __init__(self, identifier):
                self.identifier = identifier

        class Variant:
            vehicle_type = VehicleType.TRAIN

            def __init__(self, sprite_id, profile_id):
                self.sprite_id = sprite_id
                self.profile = Profile(profile_id)
                self.properties = {}

        groups = {}
        first_livery = Variant(100, "default")
        second_livery = Variant(101, "default")
        first_livery_other_profile = Variant(102, "express")

        Builder._assign_variant_group(first_livery, groups)
        Builder._assign_variant_group(second_livery, groups)
        Builder._assign_variant_group(first_livery_other_profile, groups)

        self.assertNotIn("variant_group", first_livery.properties)
        self.assertEqual(second_livery.properties["variant_group"], 100)
        self.assertNotIn("variant_group", first_livery_other_profile.properties)


if __name__ == "__main__":
    unittest.main()
