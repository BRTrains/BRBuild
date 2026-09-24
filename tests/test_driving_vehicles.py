"""Driving vehicles (`has_cab`) and standalone spritesheets (`spritesheet`).

Two related fields landed together for the DVT/DBSO work:

* `has_cab` marks an unpowered cab car, which OpenTTD lets lead a rake so the train backs up
  instead of magic-flipping — it emits the train `extra_flags` HAS_CAB bit;
* `spritesheet` lets one profile or livery of a candidate keep its drawings in a sheet of its
  own, so rows of different vehicles held in one candidate (a coach family and its DVT, say)
  are maintained separately instead of intermingled.

Both are no-ops when unset, which is what keeps every existing candidate's output identical.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from PropertyCalculation.VehicleType import VehicleType
from Vehicle.Livery import Livery
from Vehicle.Profile import Profile
from Vehicle.Vehicle import Vehicle
import Vehicle.VariantSpriteGroups as sprite_groups
from Vehicle.VariantSpriteGroups import (
    VehicleSpriteAllocator,
    declared_sheet_path,
)
from YamlHandler.VehicleLoader import VehicleLoader


def make_variant(vehicle, profile=None, livery=None, vehicle_type=VehicleType.TRAIN):
    from Vehicle.Variant import Variant

    return Variant(
        vehicle,
        livery if livery is not None else Livery("Default"),
        profile if profile is not None else Profile("Default"),
        vehicle_type,
    )


class HasCabTests(unittest.TestCase):
    def test_a_vehicle_with_a_cab_emits_the_train_extra_flag(self):
        vehicle = Vehicle(folder_path=".", identifier="br_mk3_dvt", name="Mk3 DVT", has_cab=True)

        variant = make_variant(vehicle)
        variant.process()

        self.assertEqual(
            variant.properties["extra_flags"], "bitmask(VEHICLE_FLAG_TRAIN_HAS_CAB)"
        )

    def test_the_flag_resolves_livery_then_profile_then_vehicle(self):
        vehicle = Vehicle(folder_path=".", identifier="dvt", name="DVT")

        # unset everywhere: nothing is emitted
        self.assertNotIn("extra_flags", make_variant(vehicle).properties)

        profiled = make_variant(vehicle, profile=Profile("dvt", has_cab=True))
        profiled.process()
        self.assertEqual(
            profiled.properties["extra_flags"], "bitmask(VEHICLE_FLAG_TRAIN_HAS_CAB)"
        )

        # A livery that says no wins over a profile that says yes, and takes the property
        # back out rather than leaving a stale bitmask behind.
        overridden = make_variant(
            vehicle, profile=Profile("dvt", has_cab=True), livery=Livery("Ordinary", has_cab=False)
        )
        overridden.process()
        self.assertNotIn("extra_flags", overridden.properties)

        inherited = make_variant(
            vehicle, profile=Profile("dvt", has_cab=True), livery=Livery("Plain", has_cab=None)
        )
        inherited.process()
        self.assertEqual(
            inherited.properties["extra_flags"], "bitmask(VEHICLE_FLAG_TRAIN_HAS_CAB)"
        )

    def test_a_vehicle_level_flag_applies_to_every_variant(self):
        vehicle = Vehicle(folder_path=".", identifier="dvt", name="DVT", has_cab=True)

        for profile in (Profile("one"), Profile("two")):
            variant = make_variant(vehicle, profile=profile)
            variant.process()
            self.assertEqual(
                variant.properties["extra_flags"], "bitmask(VEHICLE_FLAG_TRAIN_HAS_CAB)"
            )

    def test_a_tram_has_no_cab_flag(self):
        # Road vehicles have no back-up state, and the road-vehicle `extra_flags` field numbers
        # its bits differently, so the flag must not be written there.
        vehicle = Vehicle(folder_path=".", identifier="tram", name="Metro tram", has_cab=True)

        variant = make_variant(vehicle, vehicle_type=VehicleType.TRAM)
        variant.process()

        self.assertNotIn("extra_flags", variant.properties)

    def test_the_loader_refuses_a_non_boolean(self):
        self.assertIsNone(VehicleLoader._parse_has_cab(None, "test"))
        self.assertIs(True, VehicleLoader._parse_has_cab(True, "test"))
        self.assertIs(False, VehicleLoader._parse_has_cab(False, "test"))

        for bad in ("yes", "true", 1, 0):
            with self.assertRaises(ValueError):
                VehicleLoader._parse_has_cab(bad, "test")


class StandaloneSheetResolutionTests(unittest.TestCase):
    def test_a_profile_sheet_resolves_beside_the_candidate_yaml(self):
        self.assertEqual(
            VehicleLoader._parse_spritesheet("BRMk3DVT.png", "test", "/tmp/mk3"),
            "/tmp/mk3/BRMk3DVT.png",
        )
        self.assertEqual(
            VehicleLoader._parse_spritesheet("sheets/dvt.png", "test", "/tmp/mk3"),
            "/tmp/mk3/sheets/dvt.png",
        )
        self.assertEqual(
            VehicleLoader._parse_spritesheet("/elsewhere/dvt.png", "test", "/tmp/mk3"),
            "/elsewhere/dvt.png",
        )
        self.assertIsNone(VehicleLoader._parse_spritesheet(None, "test", "/tmp/mk3"))

        for bad in ("", "   ", 7):
            with self.assertRaises(ValueError):
                VehicleLoader._parse_spritesheet(bad, "test", "/tmp/mk3")

    def test_the_narrowest_declaration_wins_and_an_ingest_remaps_it(self):
        vehicle = Vehicle(folder_path=".", identifier="mk3", name="Mk3")
        profile = Profile("dvt", spritesheet="/published/BRMk3DVT.png")
        plain = Livery("Default")

        self.assertEqual(
            declared_sheet_path(plain, profile, vehicle), "/published/BRMk3DVT.png"
        )
        self.assertIsNone(declared_sheet_path(plain, Profile("coach"), vehicle))

        # A livery's own sheet beats the profile's.
        self.assertEqual(
            declared_sheet_path(
                Livery("NSE", spritesheet="/published/BRMk3DVT_nse.png"), profile, vehicle
            ),
            "/published/BRMk3DVT_nse.png",
        )

        # While a sheet is being ingested, the staged copy is what the build reads.
        vehicle.spritesheet_overrides = {
            "/published/BRMk3DVT.png": "/staging/BRMk3DVT.png"
        }
        self.assertEqual(
            declared_sheet_path(plain, profile, vehicle), "/staging/BRMk3DVT.png"
        )
        self.assertEqual(
            declared_sheet_path(
                Livery("NSE", spritesheet="/published/BRMk3DVT_nse.png"), profile, vehicle
            ),
            "/published/BRMk3DVT_nse.png",
        )


class IngestTargetTests(unittest.TestCase):
    def _vehicle(self, sheets):
        profiles = [Profile(f"p{index}", spritesheet=sheet) for index, sheet in enumerate(sheets)]
        return SimpleNamespace(
            identifier="mk3",
            spritesheet_path="/candidate/BRMk3.png",
            profiles=profiles,
            liveries=[],
        )

    def test_declared_sheets_lists_the_candidates_own_sheet_first(self):
        from Builder.Builder import Builder

        vehicle = SimpleNamespace(
            identifier="mk3",
            spritesheet_path="/candidate/BRMk3.png",
            profiles=[
                Profile("dvt", spritesheet="/candidate/BRMk3DVT.png"),
                Profile("coach", spritesheet="/candidate/BRMk3DVT.png"),
            ],
            liveries=[Livery("NSE", spritesheet="/candidate/BRMk3NSE.png")],
        )

        self.assertEqual(
            Builder._declared_sheets(vehicle),
            ["/candidate/BRMk3.png", "/candidate/BRMk3DVT.png", "/candidate/BRMk3NSE.png"],
        )

    def test_drops_are_matched_to_sheets_by_name(self):
        from Builder.Builder import Builder

        vehicle = self._vehicle(["/candidate/BRMk3DVT.png"])
        drops = [Path("/candidate/new/BRMk3DVT.png"), Path("/candidate/new/BRMk3.png")]

        pairs = Builder._ingest_targets(vehicle, drops)

        self.assertEqual(
            [(drop.name, sheet) for drop, sheet in pairs],
            [("BRMk3DVT.png", "/candidate/BRMk3DVT.png"), ("BRMk3.png", "/candidate/BRMk3.png")],
        )

    def test_one_unnamed_drop_still_reaches_the_candidates_own_sheet(self):
        from Builder.Builder import Builder

        vehicle = self._vehicle([])
        pairs = Builder._ingest_targets(vehicle, [Path("/candidate/new/revision.png")])

        self.assertEqual(pairs, [(Path("/candidate/new/revision.png"), "/candidate/BRMk3.png")])

    def test_an_ambiguous_drop_is_refused_rather_than_guessed(self):
        from Builder.Builder import Builder

        vehicle = self._vehicle(["/candidate/BRMk3DVT.png"])

        with self.assertRaises(ValueError) as caught:
            Builder._ingest_targets(
                vehicle,
                [Path("/candidate/new/drop_a.png"), Path("/candidate/new/drop_b.png")],
            )

        message = str(caught.exception)
        self.assertIn("drop_a.png", message)
        self.assertIn("drop_b.png", message)
        self.assertIn("BRMk3DVT.png", message)


class FakeExtractor:
    """Stands in for the real detector: the sheet's path is all the test needs from it."""

    def __init__(self, filename, palette):
        self.filename = str(filename)
        self.image = None


class FakeDetectionCache:
    def __init__(self, path, palette, definitions, vehicle_type):
        self.path = str(path)

    def load(self):
        return None

    def store(self, rows):
        return None


class StandaloneSheetRowTests(unittest.TestCase):
    """A profile naming its own sheet draws its rows from that sheet, not the candidate's."""

    def test_rows_come_from_the_sheet_the_profile_names(self):
        with tempfile.TemporaryDirectory() as folder:
            main = Path(folder) / "BRMk3.png"
            dvt = Path(folder) / "BRMk3DVT.png"
            for sheet in (main, dvt):
                sheet.write_bytes(b"\x89PNG\r\n\x1a\n")

            vehicle = Vehicle(folder_path=folder, identifier="br_mk3", name="Mk3 Coach")
            vehicle.yaml_path = str(Path(folder) / "BRMk3.yaml")
            vehicle.profiles = [
                Profile("dvt", spritesheet=str(dvt), num_vehicles=1),
                Profile("coach", num_vehicles=1),
            ]
            livery = Livery("Default")
            vehicle.liveries = [livery]

            rows = {
                str(main): [("main-row", SimpleNamespace(name="tmpl_train_8", length=8))],
                str(dvt): [("dvt-row", SimpleNamespace(name="tmpl_train_8", length=8))],
            }

            with patch.object(sprite_groups, "SpritesheetExtractor", FakeExtractor), patch.object(
                sprite_groups, "SheetDetectionCache", FakeDetectionCache
            ), patch.object(
                VehicleSpriteAllocator,
                "_match_vehicle_rows",
                staticmethod(lambda extractor, vehicle_type, definitions: rows[extractor.filename]),
            ):
                allocator = VehicleSpriteAllocator(vehicle, [], [])

                dvt_sets, _, _ = allocator.get(vehicle.profiles[0], livery)
                coach_sets, _, _ = allocator.get(vehicle.profiles[1], livery)

            self.assertEqual(dvt_sets, ["dvt-row"])
            self.assertEqual(coach_sets, ["main-row"])

            # Each sheet is consumed on its own cursor, and the group remembers where it drew.
            self.assertEqual(allocator.cursor, 1)
            self.assertEqual(allocator.sheet_for(vehicle.profiles[0], livery), str(dvt))
            self.assertEqual(allocator.sheet_for(vehicle.profiles[1], livery), str(main))

    def test_a_profile_naming_a_missing_sheet_fails_with_its_path(self):
        with tempfile.TemporaryDirectory() as folder:
            main = Path(folder) / "BRMk3.png"
            main.write_bytes(b"\x89PNG\r\n\x1a\n")

            vehicle = Vehicle(folder_path=folder, identifier="br_mk3", name="Mk3 Coach")
            vehicle.yaml_path = str(Path(folder) / "BRMk3.yaml")
            dvt_profile = Profile(
                "dvt", spritesheet=str(Path(folder) / "BRMk3DVT.png"), num_vehicles=1
            )
            vehicle.profiles = [dvt_profile]
            livery = Livery("Default")
            vehicle.liveries = [livery]

            with patch.object(sprite_groups, "SpritesheetExtractor", FakeExtractor), patch.object(
                sprite_groups, "SheetDetectionCache", FakeDetectionCache
            ), patch.object(
                VehicleSpriteAllocator,
                "_match_vehicle_rows",
                staticmethod(lambda extractor, vehicle_type, definitions: [("row", SimpleNamespace(name="tmpl_train_8", length=8))]),
            ):
                allocator = VehicleSpriteAllocator(vehicle, [], [])

                with self.assertRaises(ValueError) as caught:
                    allocator.get(dvt_profile, livery)

            self.assertIn("BRMk3DVT.png", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
