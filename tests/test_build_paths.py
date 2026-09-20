import sys
import tempfile
import unittest
from io import StringIO
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

    def test_operator_badge_is_declared_in_the_badge_table(self):
        """info.operator must register its badge string, not just reference it.

        NML only accepts badge literals declared in the badge table, so appending the
        operator badge without registering it aborts the whole GRF compile.
        """
        from Badge import BadgeRegistry
        from Lang.StringRegistry import _registry
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        BadgeRegistry().clear()
        vehicle = Vehicle(
            folder_path=".",
            identifier="example",
            name="Class Example",
            operator="Avanti West Coast",
        )
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle,
            Livery("Blue"),
            Profile("Passenger", name="Passenger"),
            VehicleType.TRAIN,
        )
        variant.process()

        self.assertIn("Operator/Avanti West Coast", BadgeRegistry().badges())
        self.assertIn("STR_BADGE_OPERATOR_AVANTI_WEST_COAST", _registry)
        self.assertIn('"Operator/Avanti West Coast"', variant.properties["badges"])

    def test_profile_and_livery_physics_override_vehicle_defaults(self):
        """Profile wins over livery, and livery wins over vehicle defaults."""
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(
            folder_path=".",
            identifier="example",
            name="Class Example",
            weight=100,
            power=1000,
        )
        livery = Livery("Heavy", power=2000, weight=200)
        profile = Profile("Long", power=3000, weight=300)
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle, livery, profile, VehicleType.TRAIN
        )
        variant.process()

        self.assertEqual(variant.power, 3000)
        self.assertEqual(variant.properties["power"], "3000 hp")
        self.assertEqual(variant.properties["weight"], "300 ton")

        livery_only = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle, livery, Profile("Default"), VehicleType.TRAIN
        )
        livery_only.process()
        self.assertEqual(livery_only.power, 2000)
        self.assertEqual(livery_only.properties["weight"], "200 ton")

    def test_tilt_level_sets_curve_speed_mod_and_flag(self):
        """A named tilt level drives both curve_speed_mod and TRAIN_FLAG_TILT."""
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(folder_path=".", identifier="example", name="Class Example")

        for level, expected in (("modest", "0.2"), ("strong", "0.3"), ("extreme", "0.35")):
            variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
                vehicle, Livery("Blue", tilt=level), Profile("Default"), VehicleType.TRAIN
            )
            variant.process()
            self.assertEqual(variant.properties["curve_speed_mod"], expected)
            self.assertEqual(variant.properties["misc_flags"], "bitmask(TRAIN_FLAG_TILT)")

    def test_tilt_none_omits_curve_speed_mod(self):
        """'none' is a deliberate zero: no modifier, no flag."""
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(folder_path=".", identifier="example", name="Class Example")
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle, Livery("Blue", tilt="none"), Profile("Default"), VehicleType.TRAIN
        )
        variant.process()

        self.assertEqual(variant.properties["curve_speed_mod"], "0")
        self.assertNotIn("misc_flags", variant.properties)

    def test_tilt_accepts_a_numeric_curve_speed_mod(self):
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(folder_path=".", identifier="example", name="Class Example")
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle, Livery("Blue", tilt=0.25), Profile("Default"), VehicleType.TRAIN
        )
        variant.process()

        self.assertEqual(variant.properties["curve_speed_mod"], "0.25")
        self.assertEqual(variant.properties["misc_flags"], "bitmask(TRAIN_FLAG_TILT)")

    def test_tilt_is_resolved_profile_first_like_other_statistics(self):
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(folder_path=".", identifier="example", name="Class Example", tilt="basic")
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle,
            Livery("Blue", tilt="strong"),
            Profile("Default", tilt="modest"),
            VehicleType.TRAIN,
        )
        variant.process()

        self.assertEqual(variant.properties["curve_speed_mod"], "0.2")

    def test_unknown_tilt_level_is_rejected(self):
        from Vehicle.Translator.Tilt import resolve_tilt

        with self.assertRaises(ValueError):
            resolve_tilt("very tilty")

    def test_tram_flag_is_kept_when_a_tram_tilts(self):
        """The tilt handler must not overwrite the tram flag handleBasicProperties set."""
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(folder_path=".", identifier="example", name="Example Tram")
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle, Livery("Blue", tilt="modest"), Profile("Default"), VehicleType.TRAM
        )
        variant.process()

        self.assertEqual(
            variant.properties["misc_flags"],
            "bitmask(ROADVEH_FLAG_TRAM, TRAIN_FLAG_TILT)",
        )

    def _variant(self, power_type=None, **kwargs):
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(folder_path=".", identifier="example", name="Class Example", **kwargs)
        if power_type is not None:
            vehicle.power_type = power_type
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle, Livery("Blue"), Profile("Default"), VehicleType.TRAIN
        )
        variant.process()
        return variant

    def test_gas_turbine_is_self_powered_and_quiet(self):
        """Gas turbine does not exist in OpenTTD: approximated as self-powered diesel."""
        from Badge import BadgeRegistry
        from PropertyCalculation.FuelType import FuelType
        from PropertyCalculation.PowerTypeClassifier import PowerTypeClassifier

        BadgeRegistry().clear()
        variant = self._variant(power_type=["gas_turbine"], power=2700, speed=152)

        self.assertEqual(variant.fuel_type, FuelType.GAS_TURBINE)
        self.assertEqual(variant.properties["engine_class"], "ENGINE_CLASS_DIESEL")
        self.assertEqual(
            variant.properties["visual_effect_and_powered"],
            "visual_effect_and_powered(VISUAL_EFFECT_DISABLE, 0, DISABLE_WAGON_POWER)",
        )
        self.assertIn("Power/Gas_turbine", BadgeRegistry().badges())
        # A self-powered unit needs no catenary.
        self.assertFalse(PowerTypeClassifier.is_ohle(["gas_turbine"]))

    def test_hydrogen_keeps_electric_traction_but_no_particles(self):
        from PropertyCalculation.FuelType import FuelType

        variant = self._variant(power_type=["hydrogen"], power=1438, speed=75)

        self.assertEqual(variant.fuel_type, FuelType.HYDROGEN)
        self.assertEqual(variant.properties["engine_class"], "ENGINE_CLASS_ELECTRIC")
        self.assertEqual(
            variant.properties["visual_effect_and_powered"],
            "visual_effect_and_powered(VISUAL_EFFECT_DISABLE, 0, DISABLE_WAGON_POWER)",
        )

    def test_battery_matches_hydrogen_presentation(self):
        from PropertyCalculation.FuelType import FuelType

        variant = self._variant(power_type=["battery"], power=1000, speed=75)

        self.assertEqual(variant.fuel_type, FuelType.BATTERY)
        self.assertEqual(variant.properties["engine_class"], "ENGINE_CLASS_ELECTRIC")
        self.assertEqual(
            variant.properties["visual_effect_and_powered"],
            "visual_effect_and_powered(VISUAL_EFFECT_DISABLE, 0, DISABLE_WAGON_POWER)",
        )

    def test_ordinary_fuels_get_no_visual_effect_override(self):
        """Diesel and electric already match their engine class default."""
        for power_type in (["diesel"], ["electric"], ["steam"]):
            variant = self._variant(power_type=power_type, power=1000, speed=100)
            self.assertNotIn(
                "visual_effect_and_powered",
                variant.properties,
                f"{power_type} should not need an override",
            )

    def test_gas_turbine_costs_more_to_run_than_diesel(self):
        diesel = self._variant(power_type=["diesel"], power=2700, speed=152)
        turbine = self._variant(power_type=["gas_turbine"], power=2700, speed=152)

        self.assertGreater(
            turbine.callbacks["running_cost_factor"], diesel.callbacks["running_cost_factor"]
        )
        self.assertGreater(
            turbine.callbacks["cost_factor"], diesel.callbacks["cost_factor"]
        )

    def test_explicit_engine_class_wins_over_the_fuel_default(self):
        variant = self._variant(
            power_type=["hydrogen"], power=1438, speed=75, engine_class="ENGINE_CLASS_DIESEL"
        )

        self.assertEqual(variant.properties["engine_class"], "ENGINE_CLASS_DIESEL")

    def test_explicit_sound_and_visual_effect_are_emitted(self):
        variant = self._variant(
            power_type=["hydrogen"],
            power=1438,
            speed=75,
            sound_effect="SOUND_DEPARTURE_TRAIN",
            visual_effect="VISUAL_EFFECT_ELECTRIC",
        )

        self.assertEqual(variant.callbacks["sound_effect"], "SOUND_DEPARTURE_TRAIN")
        self.assertEqual(
            variant.properties["visual_effect_and_powered"],
            "visual_effect_and_powered(VISUAL_EFFECT_ELECTRIC, 0, DISABLE_WAGON_POWER)",
        )

    def test_road_vehicle_uses_the_plain_visual_effect_property(self):
        """Only trains use the _and_powered form of the property."""
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(
            folder_path=".",
            identifier="example",
            name="Example Tram",
            power_type=["hydrogen"],
            power=500,
            speed=45,
        )
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle, Livery("Blue"), Profile("Default"), VehicleType.TRAM
        )
        variant.process()

        self.assertEqual(
            variant.properties["visual_effect"], "visual_effect(VISUAL_EFFECT_DISABLE, 0)"
        )
        self.assertNotIn("visual_effect_and_powered", variant.properties)

    def test_sound_and_effect_are_read_from_the_stats_block_too(self):
        """Authoring sound_effect under `stats` must still give a vehicle-level value."""
        import tempfile
        import textwrap
        from YamlHandler.VehicleLoader import VehicleLoader

        document = textwrap.dedent(
            """
            info:
              identifier: example
              name: Class Example
            stats:
              vehicle_type: train
              train_type: multiple_unit
              sound_effect: SOUND_DEPARTURE_TRAIN
              visual_effect: VISUAL_EFFECT_DISABLE
            """
        )
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "Example.yaml"
            path.write_text(document, encoding="utf-8")
            vehicle = VehicleLoader.load(str(path))

        self.assertEqual(vehicle.sound_effect, "SOUND_DEPARTURE_TRAIN")
        self.assertEqual(vehicle.visual_effect, "VISUAL_EFFECT_DISABLE")

    def test_profile_types_are_loaded_as_vehicle_type_enums(self):
        """Profile type variants must reach the iterator as VehicleType values."""
        import textwrap
        from YamlHandler.VehicleLoader import VehicleLoader
        from Vehicle.VariantIterator import VariantIterator

        document = textwrap.dedent(
            """
            info:
              identifier: example
              name: Class Example
            stats:
              vehicle_type: train
              train_type: multiple_unit
            profiles:
              - identifier: default
                types: [train, tram]
            liveries:
              - name: Blue
            """
        )
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "Example.yaml"
            path.write_text(document, encoding="utf-8")
            vehicle = VehicleLoader.load(str(path))

        variants = list(VariantIterator(vehicle))
        self.assertEqual(
            [variant.vehicle_type for variant in variants],
            [VehicleType.TRAIN, VehicleType.TRAM],
        )

    def test_unusable_sound_effect_is_rejected(self):
        with self.assertRaises(ValueError):
            self._variant(
                power_type=["diesel"], power=1000, speed=100, sound_effect="sw_sound steam!"
            )

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

    def test_variant_names_use_property_and_group_callback_labels(self):
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(folder_path=".", identifier="example", name="Class Example")
        livery = Livery("Blue")
        vehicle.liveries = [livery]
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle,
            livery,
            Profile("Passenger", name="Passenger"),
            VehicleType.TRAIN,
        )
        variant.process()

        self.assertEqual(variant.name, "Passenger - Blue")
        self.assertEqual(variant.grouped_name, "Class Example - Passenger")
        self.assertEqual(variant.properties["name"], "string(str_example_passenger_blue_train_name)")
        self.assertEqual(variant.callbacks["name"], "sw_example_passenger_blue_train_name")

        output = StringIO()
        NmlVariantWriter(variant, "/tmp").write_sprites(output, variant)
        switch = output.getvalue()
        self.assertIn("switch (FEAT_TRAINS, SELF, sw_example_passenger_blue_train_name, extra_callback_info1 & 0xFF)", switch)
        self.assertIn("0x20 : sw_example_passenger_blue_train_name_purchase;", switch)
        self.assertIn("switch (FEAT_TRAINS, SELF, sw_example_passenger_blue_train_name_purchase, getbits(extra_callback_info1, 0, 16))", switch)
        self.assertIn("0x20 : string(str_example_passenger_blue_train_single_livery_name);", switch)
        self.assertIn("0x120 : string(str_example_passenger_blue_train_name);", switch)
        self.assertIn("\tstring(str_example_passenger_blue_train_name);", switch)
        self.assertIn("CB_FAILED;", switch)

    def test_variant_name_callback_uses_group_name_for_multiple_liveries(self):
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(folder_path=".", identifier="example", name="Class Example")
        first = Livery("Blue")
        second = Livery("Green")
        vehicle.liveries = [first, second]
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle,
            first,
            Profile("Passenger", name="Passenger"),
            VehicleType.TRAIN,
        )
        variant.process()

        output = StringIO()
        NmlVariantWriter(variant, "/tmp").write_sprites(output, variant)
        switch = output.getvalue()
        self.assertIn("switch (FEAT_TRAINS, SELF, sw_example_passenger_blue_train_name_purchase, getbits(extra_callback_info1, 0, 16))", switch)
        self.assertIn("0x20 : string(str_example_passenger_blue_train_group_name);", switch)
        self.assertIn("0x120 : string(str_example_passenger_blue_train_name);", switch)

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

    def test_each_compile_runs_with_fresh_nml_state(self):
        """Building more than one project used to fail on the second compile.

        nmlc keeps loaded language strings in module-level globals, so a second
        in-process compile saw the first project's strings and aborted with
        'String name "str_grf_name" is used multiple times'. The compiler now runs
        each project in its own interpreter. This test uses a stand-in nml package
        that is only importable in the child process, so it fails the old way if the
        compiler ever runs nmlc in the process that invoked it.
        """
        import importlib
        import os
        from NmlWriter.NmlCompiler import NmlCompiler

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fake_nml = root / "fakepkg" / "nml"
            fake_nml.mkdir(parents=True)
            # Importable only when the compiler has put the package on the child's
            # PYTHONPATH: an in-process import still sees the real installed nml.
            (fake_nml / "__init__.py").write_text(
                "import os\n"
                "if os.environ.get('NML_TEST_CHILD') != '1':\n"
                "    raise ImportError('the stand-in nml package is for subprocesses only')\n"
                "from . import main\n",
                encoding="utf-8",
            )
            (fake_nml / "main.py").write_text(
                "import os\n"
                "from pathlib import Path\n"
                "def main(argv):\n"
                "    Path(argv[-1]).write_text(str(os.getpid()))\n"
                "    return 0\n",
                encoding="utf-8",
            )

            nml_file = root / "Example.nml"
            nml_file.write_text("// example\n", encoding="utf-8")
            lang_folder = root / "lang"
            lang_folder.mkdir()
            (lang_folder / "english.lng").write_text("##grflangid 0x01\n", encoding="utf-8")
            caller_file = root / "caller.txt"

            # The compiler resolves nml from the running interpreter's sys.path, so
            # the stand-in is found by making the test directory current and putting
            # it first. A real local ../nml checkout would take priority instead.
            previous_cwd = os.getcwd()
            previous_environment = os.environ.get("NML_TEST_CHILD")
            os.environ["NML_TEST_CHILD"] = "1"
            sys.path.insert(0, str(root / "fakepkg"))
            # sys.path was already searched for nml earlier in the suite, so the
            # import system's directory cache has to be dropped for the new entry.
            importlib.invalidate_caches()
            os.chdir(root)
            try:
                compiler = NmlCompiler()
                resolved = compiler._resolve_nml()
                first = compiler.compile(str(nml_file), str(caller_file))
                first_caller = caller_file.read_text()
                second = compiler.compile(str(nml_file), str(caller_file))
                second_caller = caller_file.read_text()
            finally:
                os.chdir(previous_cwd)
                sys.path.remove(str(root / "fakepkg"))
                if previous_environment is None:
                    os.environ.pop("NML_TEST_CHILD", None)
                else:
                    os.environ["NML_TEST_CHILD"] = previous_environment

            self.assertEqual(resolved, root / "fakepkg")
            self.assertEqual(first, str(nml_file).replace(".nml", ".grf"))
            self.assertEqual(second, first)
            # Each compile must run in its own process, never in the process that
            # tried to import nml itself (whose globals are what leaks).
            self.assertNotEqual(first_caller, str(os.getpid()))
            self.assertNotEqual(second_caller, str(os.getpid()))
            self.assertNotEqual(first_caller, second_caller)
            self.assertNotIn("nml", sys.modules)


if __name__ == "__main__":
    unittest.main()
