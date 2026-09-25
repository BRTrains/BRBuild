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

#: Root of the BRBuild checkout, so tests never depend on a machine-specific absolute path.
REPO_ROOT = Path(__file__).resolve().parents[1]


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

    def test_livery_and_profile_physics_override_vehicle_defaults(self):
        """Livery wins over profile, and profile wins over vehicle defaults."""
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

        self.assertEqual(variant.power, 2000)
        self.assertEqual(variant.properties["power"], "2000 hp")
        self.assertEqual(variant.properties["weight"], "200 ton")

        profile_only = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle, Livery("Default"), profile, VehicleType.TRAIN
        )
        profile_only.process()
        self.assertEqual(profile_only.power, 3000)
        self.assertEqual(profile_only.properties["weight"], "300 ton")

    def test_railtype_table_loads_ordered_fallbacks_and_writes_nml(self):
        """The project's logical track types resolve to ordered real railtype labels."""
        import textwrap
        from Grf.RailTypeTable import RailTypeTable
        from NmlWriter.NmlGrfWriter import NmlGrfWriter

        document = textwrap.dedent(
            """
            RAIL: [RAIL]
            ELRL: [SAAA, SAAE, ELRL]
            THIRD: [SAA3, 3RDR, ELRL]
            FOURTH: [SAA4, SAA3, 4RDR, ELRL]
            """
        )
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "RailTypes.yaml"
            path.write_text(document, encoding="utf-8")
            table = RailTypeTable.load(path)

            self.assertEqual(table.lookup_order("THIRD"), ["SAA3", "3RDR", "ELRL"])
            self.assertEqual(table.lookup_order("FOURTH"), ["SAA4", "SAA3", "4RDR", "ELRL"])
            # A type with no fallbacks of its own still resolves to itself.
            self.assertEqual(table.lookup_order("RAIL"), ["RAIL"])

            output = Path(folder) / "RailTypes.gnml"
            NmlGrfWriter(None).write_railtype_table(table, output)
            written = output.read_text(encoding="utf-8")

        self.assertIn("railtypetable {", written)
        # The list form is used even for one label: `RAIL: RAIL` is a syntax error.
        self.assertIn("RAIL: [RAIL]", written)
        # A label starting with a digit is not a bare identifier to nmlc.
        self.assertIn('THIRD: [SAA3, "3RDR", ELRL]', written)
        self.assertIn('FOURTH: [SAA4, SAA3, "4RDR", ELRL]', written)
        # Vehicles name a constant, not a table entry, so the property is an index.
        self.assertIn("const railtype_THIRD = THIRD;", written)

    def test_a_railtype_table_entry_without_fallbacks_is_still_declared(self):
        """A single-label entry assigns directly; nmlc rejects an empty list."""
        import textwrap
        from Grf.RailTypeTable import RailTypeTable
        from NmlWriter.NmlGrfWriter import NmlGrfWriter

        document = textwrap.dedent(
            """
            RAIL: []
            THIRD: [SAA3]
            """
        )
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "RailTypes.yaml"
            path.write_text(document, encoding="utf-8")
            table = RailTypeTable.load(path)
            output = Path(folder) / "RailTypes.gnml"
            NmlGrfWriter(None).write_railtype_table(table, output)
            written = output.read_text(encoding="utf-8")

        # An empty fallback list means "this is the label", so emit the label itself
        # in the list form nmlc requires.
        self.assertIn("RAIL: [RAIL]", written)
        self.assertNotIn("[]", written)

    def test_unknown_railtype_key_is_rejected(self):
        """A vehicle naming a track type the project does not define must fail loudly."""
        import textwrap
        from Grf.RailTypeTable import RailTypeTable

        document = textwrap.dedent(
            """
            RAIL: [RAIL]
            THIRD: [SAA3, ELRL]
            """
        )
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "RailTypes.yaml"
            path.write_text(document, encoding="utf-8")
            table = RailTypeTable.load(path)

        self.assertEqual(table.lookup("THIRD"), "railtype_THIRD")
        with self.assertRaises(ValueError):
            table.lookup("FIFTH")

    def test_a_train_emits_its_resolved_track_types(self):
        """`track_type` is a list of logical project keys, written as railtype indices."""
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(
            folder_path=".", identifier="example", name="Class Example", track_type=["RAIL"]
        )
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle,
            Livery("Blue"),
            Profile("Dual", track_type=["THIRD", "ELRL"]),
            VehicleType.TRAIN,
            rail_type_table=self._railtype_table(),
        )
        variant.process()

        self.assertEqual(
            variant.properties["track_type"], "railtype_THIRD + railtype_ELRL"
        )

    def _railtype_table(self):
        """A stand-in project table: the four logical types BRTrains uses."""
        from Grf.RailTypeTable import RailTypeTable

        return RailTypeTable(
            entries={
                "RAIL": ["RAIL"],
                "ELRL": ["SAAA", "SAAE", "ELRL"],
                "THIRD": ["SAA3", "3RDR", "ELRL"],
                "FOURTH": ["SAA4", "SAA3", "4RDR", "ELRL"],
            }
        )

    def test_track_type_uses_livery_then_profile_then_vehicle(self):
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(
            folder_path=".", identifier="example", name="Class Example", track_type=["FOURTH"]
        )
        # Ordinary resolution: the profile and livery override, livery first.
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle,
            Livery("Blue", track_type=["ELRL"]),
            Profile("Dual", track_type=["THIRD", "ELRL"]),
            VehicleType.TRAIN,
            rail_type_table=self._railtype_table(),
        )
        variant.process()
        self.assertEqual(variant.properties["track_type"], "railtype_ELRL")

        profile_only = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle,
            Livery("Default"),
            Profile("Dual", track_type=["THIRD", "ELRL"]),
            VehicleType.TRAIN,
            rail_type_table=self._railtype_table(),
        )
        profile_only.process()
        self.assertEqual(
            profile_only.properties["track_type"], "railtype_THIRD + railtype_ELRL"
        )

        # The vehicle's own value is the fallback for both.
        vehicle_only = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle,
            Livery("Default"),
            Profile("Default"),
            VehicleType.TRAIN,
            rail_type_table=self._railtype_table(),
        )
        vehicle_only.process()
        self.assertEqual(vehicle_only.properties["track_type"], "railtype_FOURTH")

    def test_track_type_defaults_to_rail(self):
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(folder_path=".", identifier="example", name="Class Example")
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle, Livery("Default"), Profile("Default"), VehicleType.TRAIN
        )
        variant.process()
        self.assertEqual(variant.properties["track_type"], "railtype_RAIL")

    def test_power_type_selects_the_track_types_by_default(self):
        """Traction decides the track types when the vehicle does not name any."""
        cases = (
            (["diesel"], "railtype_RAIL"),
            (["steam"], "railtype_RAIL"),
            (["hydrogen"], "railtype_RAIL"),
            (["battery"], "railtype_RAIL"),
            (["gas_turbine"], "railtype_RAIL"),
            (["electric"], "railtype_ELRL"),
            (["electric", "ohle"], "railtype_ELRL"),
            (["electric", "third_rail"], "railtype_THIRD"),
            (["electric", "fourth_rail"], "railtype_FOURTH"),
            # A dual-voltage unit keeps overhead reach through THIRD's own fallbacks.
            (["electric", "third_rail", "ohle"], "railtype_THIRD"),
            (["diesel", "electric"], "railtype_RAIL + railtype_ELRL"),
            (["diesel", "electric", "third_rail"], "railtype_RAIL + railtype_THIRD"),
        )
        for power_type, expected in cases:
            variant = self._variant(
                power_type=power_type, power=1000, speed=100,
                rail_type_table=self._railtype_table(),
            )
            self.assertEqual(
                variant.properties["track_type"], expected, f"power_type {power_type}"
            )

    def test_explicit_track_type_overrides_what_traction_implies(self):
        """A vehicle that names its own track type is never second-guessed."""
        variant = self._variant(
            power_type=["diesel", "electric"],
            power=1000,
            speed=100,
            track_type=["THIRD"],
            rail_type_table=self._railtype_table(),
        )
        self.assertEqual(variant.properties["track_type"], "railtype_THIRD")

    def test_track_type_is_read_from_yaml_and_defaults_absent(self):
        """`track_type` is authored as project track types, from `stats` or the root."""
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
              track_type: [THIRD, ELRL]
            """
        )
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "Example.yaml"
            path.write_text(document, encoding="utf-8")
            vehicle = VehicleLoader.load(str(path))

            self.assertEqual(vehicle.track_type, ["THIRD", "ELRL"])
            self.assertEqual(vehicle.profiles, [])

            # A railtype *label* is the RailTypes.yaml's business, not the vehicle's:
            # the loader only guards the name's shape, and the table rejects what it
            # does not define.
            document = document.replace("[THIRD, ELRL]", '"4RDR"')
            path.write_text(document, encoding="utf-8")
            with self.assertRaises(ValueError):
                VehicleLoader.load(str(path))

    def test_road_vehicles_keep_their_own_track_property(self):
        """A tram's running gear is `tram_type`, not `track_type`."""
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(folder_path=".", identifier="example", name="Example Tram")
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle, Livery("Default"), Profile("Default"), VehicleType.TRAM
        )
        variant.process()
        self.assertNotIn("track_type", variant.properties)

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

    def test_tilt_is_resolved_livery_first_like_other_statistics(self):
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

        self.assertEqual(variant.properties["curve_speed_mod"], "0.3")

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

    def _variant(self, power_type=None, rail_type_table=None, **kwargs):
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(folder_path=".", identifier="example", name="Class Example", **kwargs)
        if power_type is not None:
            vehicle.power_type = power_type
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle,
            Livery("Blue"),
            Profile("Default"),
            VehicleType.TRAIN,
            rail_type_table=rail_type_table,
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

    def test_a_diesel_bi_mode_takes_the_diesel_engine_class(self):
        """Leaving the class unset is not neutral: OpenTTD defaults a train to steam."""
        from PropertyCalculation.FuelType import FuelType

        variant = self._variant(power_type=["diesel", "electric"], power=5400, speed=100)

        self.assertEqual(variant.fuel_type, FuelType.BI_MODE)
        self.assertEqual(variant.properties["engine_class"], "ENGINE_CLASS_DIESEL")
        # The diesel class already supplies diesel particles and the train departure sound,
        # so no visual-effect override is needed.
        self.assertNotIn("visual_effect_and_powered", variant.properties)

    def test_a_diesel_tri_mode_takes_the_diesel_engine_class_too(self):
        variant = self._variant(
            power_type=["diesel", "electric", "battery"], power=1000, speed=100
        )

        self.assertEqual(variant.properties["engine_class"], "ENGINE_CLASS_DIESEL")

    def test_explicit_engine_class_still_wins_on_a_bi_mode(self):
        variant = self._variant(
            power_type=["diesel", "electric"],
            power=5400,
            speed=100,
            engine_class="ENGINE_CLASS_ELECTRIC",
        )

        self.assertEqual(variant.properties["engine_class"], "ENGINE_CLASS_ELECTRIC")

    def test_a_multi_mode_with_no_diesel_engine_still_names_no_class(self):
        """Known gap, not a decision: only the diesel rule avoids the steam fallback.

        A hydrogen or battery multi-mode has no rule of its own, so it inherits OpenTTD's
        steam default for particles, departure sound and livery scheme. Change this test
        when that is addressed rather than leaving it to fail silently.
        """
        variant = self._variant(power_type=["hydrogen", "battery"], power=1000, speed=100)

        self.assertNotIn("engine_class", variant.properties)

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

        self.assertEqual(variant.name, "Class Example - Passenger - Blue")
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

    def test_default_profile_and_livery_names_are_omitted(self):
        """A `Default` profile/livery is a placeholder, so the name is the vehicle's."""
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(folder_path=".", identifier="example", name="Class Example")
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle,
            Livery("Default"),
            Profile("Default", name="Default"),
            VehicleType.TRAIN,
        )
        variant.process()

        self.assertEqual(variant.name, "Class Example")
        self.assertEqual(variant.grouped_name, "Class Example")

        named_livery = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle,
            Livery("Blue"),
            Profile("Default", name="Default"),
            VehicleType.TRAIN,
        )
        named_livery.process()

        self.assertEqual(named_livery.name, "Class Example - Blue")

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

    def test_service_speed_alone_writes_the_property_and_no_callback(self):
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(folder_path=".", identifier="example", name="Class Example")
        vehicle.speed = 100
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle, Livery("Default"), Profile("Default"), VehicleType.TRAIN
        )
        variant.process()

        self.assertEqual(variant.speed, 100)
        self.assertEqual(variant.properties["speed"], "100 mph")
        self.assertNotIn("speed", variant.callbacks)

    def test_design_and_service_speeds_become_a_parameter_selector(self):
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(folder_path=".", identifier="example", name="Class Example")
        vehicle.speed = 125
        vehicle.design_speed = 140
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle, Livery("Default"), Profile("Default"), VehicleType.TRAIN
        )
        variant.process()

        # The property stays the service figure so the unit is usable without the parameter.
        self.assertEqual(variant.speed, 125)
        self.assertEqual(variant.properties["speed"], "125 mph")
        # The callback carries speed field values, not mph: 140 mph is 224 there.
        self.assertEqual(
            variant.callbacks["speed"],
            "param_speed_mode == 1 ? 224 : 200",
        )

    def test_speed_field_conversion_matches_nmls_own_mph_handling(self):
        """A callback value has to equal what nmlc compiles `speed: N mph` to."""
        from Vehicle.Translator.Speed import displayed_mph, speed_field

        self.assertEqual(speed_field(125), 200)
        self.assertEqual(speed_field(140), 224)
        self.assertEqual(speed_field(155), 248)
        # 62 mph is 100, not the 99 that 62 * 1.6 rounds to: 99 reads back as 61 mph.
        self.assertEqual(speed_field(62), 100)
        self.assertEqual(displayed_mph(99), 61)

    def test_every_authored_mph_figure_reads_back_unchanged(self):
        from Vehicle.Translator.Speed import displayed_mph, speed_field

        for mph in range(1, 501):
            self.assertEqual(displayed_mph(speed_field(mph)), mph)

    def test_design_speed_alone_is_written_as_the_speed(self):
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(folder_path=".", identifier="example", name="Class Example")
        vehicle.design_speed = 140
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle, Livery("Default"), Profile("Default"), VehicleType.TRAIN
        )
        variant.process()

        self.assertEqual(variant.speed, 140)
        self.assertEqual(variant.properties["speed"], "140 mph")
        self.assertNotIn("speed", variant.callbacks)

    def test_a_profile_can_share_another_profiles_sprite_rows(self):
        """`sprite_group` lets two profiles use one set of drawings, not two."""
        from types import SimpleNamespace
        from unittest.mock import patch
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        from Vehicle.VariantSpriteGroups import VehicleSpriteAllocator

        vehicle = Vehicle(folder_path=".", identifier="example", name="Class Example")
        vehicle.yaml_path = "/tmp/example/example.yaml"
        livery = Livery("Default")
        before = Profile("before", num_vehicles=3)
        after = Profile("after", num_vehicles=3, sprite_group="before")
        vehicle.profiles = [before, after]
        vehicle.liveries = [livery]

        rows = [(SimpleNamespace(name=f"row{index}"), SimpleNamespace(name=f"tmpl_train_6", length=4))
                for index in range(1, 4)]

        def fake_init(self, vehicle, palette, definitions):
            self.vehicle = vehicle
            self.is_ohle = False
            self._image = None
            self._palette = palette
            self.vehicle_rows = rows
            self.cursor = 0
            self._assigned_rows = {}
            self._spritesets = {}
            self._template_names = {}
            self._lengths = {}
            self._definitions = {}

        with patch.object(VehicleSpriteAllocator, "__init__", fake_init):
            allocator = VehicleSpriteAllocator(vehicle, [], [])

        before_sets, _, _ = allocator.get(before, livery)
        after_sets, _, _ = allocator.get(after, livery)

        # Same drawings for both, and the sheet was only consumed once.
        self.assertEqual(before_sets, after_sets)
        self.assertEqual(allocator.cursor, 3)

    def test_a_profile_can_override_the_introduction_date(self):
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(folder_path=".", identifier="example", name="Class Example")
        vehicle.speed = 75
        vehicle.introduction_date = "date(1990, 8, 1)"
        profile = Profile("late", introduction_date="date(2010, 1, 1)", speed=90, design_speed=75)
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle, Livery("Default"), profile, VehicleType.TRAIN
        )
        variant.process()

        self.assertEqual(variant.properties["introduction_date"], "date(2010, 1, 1)")
        self.assertEqual(variant.properties["speed"], "90 mph")
        self.assertEqual(variant.callbacks["speed"], "param_speed_mode == 1 ? 120 : 144")

    def test_introduction_date_forms_are_emitted_as_nml_dates(self):
        from YamlHandler.VehicleLoader import VehicleLoader

        parse = VehicleLoader._parse_introduction_date
        self.assertEqual(parse(1952, "test"), "date(1952, 1, 1)")
        self.assertEqual(parse("1952", "test"), "date(1952, 1, 1)")
        self.assertEqual(parse("1952-04", "test"), "date(1952, 4, 1)")
        self.assertEqual(parse("1952-04-21", "test"), "date(1952, 4, 21)")
        self.assertEqual(parse("date(1952, 4, 21)", "test"), "date(1952, 4, 21)")
        self.assertIsNone(parse(None, "test"))

        # YAML types a bare `1952-04-21` as a date object, which is the common case.
        from datetime import date

        self.assertEqual(parse(date(1952, 4, 21), "test"), "date(1952, 4, 21)")

        # A bare `1952-04-21` reaching nmlc as an expression was the bug: 1952-4-21.
        self.assertNotEqual(parse("1952-04-21", "test"), "1952-04-21")

        for bad in ("1952-13-01", "1952-04-45", "not a date", [1952]):
            with self.assertRaises(ValueError):
                parse(bad, "test")

    def test_a_document_yaml_date_reaches_the_variant_as_a_date(self):
        """The loader resolves the authored form, so the variant only writes it."""
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(folder_path=".", identifier="example", name="Class Example")
        vehicle.speed = 100
        vehicle.introduction_date = "1952-04-21"
        profile = Profile("Default")
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle, Livery("Default"), profile, VehicleType.TRAIN
        )
        # The loader is what resolves the YAML form; a raw value would be arithmetic.
        from YamlHandler.VehicleLoader import VehicleLoader

        vehicle.introduction_date = VehicleLoader._parse_introduction_date(
            "1952-04-21", "test"
        )
        variant.process()

        self.assertEqual(variant.properties["introduction_date"], "date(1952, 4, 21)")

    def test_a_design_speed_below_the_service_speed_is_logged(self):
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle

        vehicle = Vehicle(folder_path=".", identifier="example", name="Class Example")
        vehicle.speed = 75
        profile = Profile("late", speed=90, design_speed=75)
        variant = __import__("Vehicle.Variant", fromlist=["Variant"]).Variant(
            vehicle, Livery("Default"), profile, VehicleType.TRAIN
        )

        with self.assertLogs("Vehicle.Variant", level="WARNING") as captured:
            variant.process()

        self.assertTrue(
            any("design speed lower than its service speed" in line for line in captured.output)
        )

    def test_purchase_sprite_crops_to_the_template_box_not_the_measured_content(self):
        """A pale line below a car must not become a white row in the purchase icon.

        The measured content box can be a row taller than the template when the artist's
        row edge leaves a non-near-white line below the car; the emitted spriteset tells
        OpenTTD to read the template box, so the icon has to use the same box.
        """
        from unittest.mock import patch
        from PIL import Image
        from Sprites.Sprite import Sprite
        from Sprites.Spriteset import Spriteset
        from Templates.BoundingBox import BoundingBox
        from Templates.Template import Template
        from Templates.TemplateDefinition import TemplateDefinition
        from Templates.TemplateType import TemplateType
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle
        from Vehicle.VariantSpriteGroups import VehicleSpriteAllocator

        vehicle = Vehicle(folder_path=".", identifier="example", name="Class Example")
        vehicle.yaml_path = "/tmp/example/example.yaml"
        livery = Livery("Default")
        profile = Profile("Default", num_vehicles=1)

        # The sheet: a car whose content fills rows 0..11 and a pale row at 12.
        sheet = Image.new("RGB", (64, 40), (255, 255, 255))
        for y in range(12):
            for x in range(32):
                sheet.putpixel((x, y), (0, 0, 255))
        for x in range(32):
            sheet.putpixel((x, 12), (224, 244, 252))

        measured = Template(
            name="measured",
            sprites=[Sprite(0, 0, 32, 12, 0, 0)] * 6 + [Sprite(0, 0, 32, 13, 0, 0)] + [Sprite(0, 0, 32, 12, 0, 0)],
        )
        spriteset = Spriteset("car", "/tmp/example/example.png", measured, 0, 0)

        boxes = [BoundingBox(0, 0, 32, 12, 0, 0, []) for _ in range(8)]
        definition = TemplateDefinition(
            name="tmpl_train_8_old",
            template_type=TemplateType.VEHICLE,
            bounding_boxes=boxes,
        )

        from Sprites.PalettedImage import PalettedImage

        palette = PalettedImage.load_palette(str(REPO_ROOT / "Sprites" / "ttd-newgrf-dos.gpl"))

        def fake_init(self, vehicle, palette_arg, definitions):
            self.vehicle = vehicle
            self.is_ohle = False
            self._image = sheet
            self._palette = palette
            self.vehicle_rows = []
            self.cursor = 0
            self._assigned_rows = {}
            self._spritesets = {(str(profile.identifier), str(livery.name)): [spriteset]}
            self._template_names = {(str(profile.identifier), str(livery.name)): ["tmpl_train_8_old"]}
            self._lengths = {(str(profile.identifier), str(livery.name)): [8]}
            self._definitions = {(str(profile.identifier), str(livery.name)): [definition]}

        with tempfile.TemporaryDirectory() as folder, patch.object(
            VehicleSpriteAllocator, "__init__", fake_init
        ):
            allocator = VehicleSpriteAllocator(vehicle, palette, [])
            result = allocator.get_purchase(profile, livery, folder)

            self.assertIsNotNone(result)
            purchase, template_name = result
            self.assertEqual(template_name, "tmpl_purchase")

            icon = Image.open(purchase.file).convert("RGB")
            bottom_row = [icon.getpixel((x, 12)) for x in range(icon.width)]
            self.assertNotIn(
                (255, 255, 255),
                bottom_row,
                "the pale line below the car must not be cropped into the purchase icon",
            )
            self.assertNotIn((224, 244, 252), bottom_row)

    def test_purchase_sprite_aligns_parts_by_their_template_offsets(self):
        """Parts drawn against different templates must not sit a row apart in the icon.

        The game aligns each part with its template's `offset_y`; a 13px west-view box
        whose art starts one row down and a 12px box whose art starts at the top are
        aligned in the consist but land a row apart if every crop is pasted at row 0.
        """
        from unittest.mock import patch
        from PIL import Image
        from Sprites.PalettedImage import PalettedImage
        from Sprites.Sprite import Sprite
        from Sprites.Spriteset import Spriteset
        from Templates.BoundingBox import BoundingBox
        from Templates.Template import Template
        from Templates.TemplateDefinition import TemplateDefinition
        from Templates.TemplateType import TemplateType
        from Vehicle.Livery import Livery
        from Vehicle.Profile import Profile
        from Vehicle.Vehicle import Vehicle
        from Vehicle.VariantSpriteGroups import VehicleSpriteAllocator

        vehicle = Vehicle(folder_path=".", identifier="example", name="Class Example")
        vehicle.yaml_path = "/tmp/example/example.yaml"
        livery = Livery("Default")
        profile = Profile("Default", num_vehicles=2)

        def west_box(width, height, offset_y):
            return BoundingBox(0, 0, width, height, 0, offset_y, [])

        def definition(name, width, height, offset_y):
            return TemplateDefinition(
                name=name,
                template_type=TemplateType.VEHICLE,
                bounding_boxes=[west_box(width, height, offset_y) for _ in range(8)],
            )

        # Part one: 12px box, art flush to its top, template offset -8.
        # Part two: 13px box, art one row down (as artists place it for that box),
        # template offset -9 - so the two are aligned in the consist.
        palette = PalettedImage.load_palette(str(REPO_ROOT / "Sprites" / "ttd-newgrf-dos.gpl"))

        def palette_index(colour):
            for index in range(256):
                if tuple(palette[index * 3:index * 3 + 3]) == colour:
                    return index
            raise AssertionError(f"{colour} is not in the palette")

        blue_index = palette_index((0, 0, 255))
        art_index = next(
            index
            for index in range(256)
            if tuple(palette[index * 3:index * 3 + 3]) not in ((0, 0, 255), (255, 255, 255), (252, 252, 252))
        )

        sheet = Image.new("P", (64, 60))
        sheet.putpalette(palette)
        sheet.paste(palette_index((255, 255, 255)), (0, 0, 64, 60))
        for y in range(0, 12):
            for x in range(0, 32):
                sheet.putpixel((x, y), art_index)
        for y in range(1, 13):
            for x in range(32, 64):
                sheet.putpixel((x, y), art_index)

        measured_12 = Template(
            name="measured12",
            sprites=[Sprite(0, 0, 32, 12, 0, 0)] * 8,
        )
        measured_13 = Template(
            name="measured13",
            sprites=[Sprite(0, 0, 32, 13, 0, 0)] * 8,
        )
        parts = [
            Spriteset("a", "/tmp/example/example.png", measured_12, 0, 0),
            Spriteset("b", "/tmp/example/example.png", measured_13, 32, 0),
        ]
        definitions = [definition("tmpl_12", 32, 12, -8), definition("tmpl_13", 32, 13, -9)]

        key = (str(profile.identifier), str(livery.name))

        def fake_init(self, vehicle, palette_arg, definitions_arg):
            self.vehicle = vehicle
            self.is_ohle = False
            self._image = sheet
            self._palette = palette
            self.vehicle_rows = []
            self.cursor = 0
            self._assigned_rows = {}
            self._spritesets = {key: parts}
            self._template_names = {key: ["tmpl_12", "tmpl_13"]}
            self._lengths = {key: [8, 8]}
            self._definitions = {key: definitions}

        with tempfile.TemporaryDirectory() as folder, patch.object(
            VehicleSpriteAllocator, "__init__", fake_init
        ):
            allocator = VehicleSpriteAllocator(vehicle, palette, [])
            purchase, _ = allocator.get_purchase(profile, livery, folder)

            icon = Image.open(purchase.file)
            icon.load()

            def first_art_row(x_range):
                return next(
                    (y for y in range(icon.height) if any(icon.getpixel((x, y)) == art_index for x in x_range)),
                    None,
                )

            first_top = first_art_row(range(0, 32))
            second_top = first_art_row(range(32, 64))

            self.assertNotEqual(first_top, None)
            self.assertEqual(
                first_top,
                second_top,
                "a 13px-box car whose art starts one row down must not sit lower than a "
                "12px-box car drawn flush to its box",
            )

    def test_normaliser_lays_views_out_on_the_template_columns(self):
        """The published sheet must match the template the game reads, not the artist's drift.

        A view drawn 1px off its box, or 1px narrower than it, must not shift the later
        views in the row: the boxes would then read the 1px white separators and the
        player sees a white line down one edge.
        """
        from types import SimpleNamespace
        from PIL import Image
        from Sprites.PalettedImage import PalettedImage
        from Sprites.Sprite import Sprite
        from Templates.BoundingBox import BoundingBox
        from Templates.SpritesheetLegacyConverter import SpritesheetLegacyConverter
        from Templates.Template import Template
        from Templates.TemplateDefinition import TemplateDefinition
        from Templates.TemplateType import TemplateType

        palette = PalettedImage.load_palette(str(REPO_ROOT / "Sprites" / "ttd-newgrf-dos.gpl"))

        def index_of(colour):
            for index in range(256):
                if tuple(palette[index * 3:index * 3 + 3]) == colour:
                    return index
            raise AssertionError(f"{colour} missing from the palette")

        blue = index_of((0, 0, 255))
        white = index_of((255, 255, 255))

        # Two views: box 0 is 8 wide, box 1 is 6 wide starting at x=9.
        boxes = [
            BoundingBox(0, 0, 8, 10, 0, 0, []),
            BoundingBox(9, 0, 6, 10, 0, 0, []),
        ]
        definition = TemplateDefinition(
            name="tmpl_two", template_type=TemplateType.VEHICLE, bounding_boxes=boxes
        )

        # The artist's row: view 0 drawn 1px right of its box and 2px too wide; view 1
        # 1px narrower than its box.
        source = Image.new("P", (40, 20))
        source.putpalette(palette)
        source.paste(white, (0, 0, 40, 20))
        for y in range(0, 10):
            for x in range(1, 10):        # art for view 0, at x=1..9
                source.putpixel((x, y), index_of((16, 16, 16)))
            for x in range(11, 16):       # art for view 1, at x=11..15
                source.putpixel((x, y), index_of((160, 0, 0)))

        row = SimpleNamespace(
            x=0,
            y=0,
            template=Template(
                name="measured",
                sprites=[Sprite(1, 0, 9, 10, 0, 0), Sprite(11, 0, 5, 10, 0, 0)],
            ),
        )
        extractor = SimpleNamespace(image=source)

        converted = SpritesheetLegacyConverter([definition], palette)._rebuild_clean_sheet(
            extractor, [(row, definition)]
        )

        self.assertEqual(converted.width, 15, "the sheet must be the template's own extent")
        self.assertEqual(converted.height, 10)

        def is_white(x, y):
            return all(channel >= 250 for channel in converted.convert("RGB").getpixel((x, y)))

        # No blank column inside either box: the art fills its box from the left edge.
        for x in (0, 7, 9, 14):
            self.assertFalse(
                all(is_white(x, y) for y in range(10)),
                f"box column x={x} is blank, so the game would draw a white line there",
            )
        # The box's trailing column, past the shorter art, is transparent rather than white.
        self.assertEqual(converted.getpixel((14, 0)), blue)

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
