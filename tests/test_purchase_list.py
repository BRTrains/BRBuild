"""Tests for the purchase-list `sort` blocks BRBuild derives from vehicle data.

A project opts in with `purchase_list: {order: grouped}` (or `date`) in its `GRF.yaml`;
`none` is the default and emits nothing, so a project that does not ask for this keeps
the vehicle-ID order it had.
"""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from Builder import Builder
from Grf import Grf
from NmlWriter.NmlCollator import NmlCollator
from PropertyCalculation.TrainType import TrainType
from Vehicle.PurchaseList import (
    DATE,
    GROUPED,
    NONE,
    VehicleFacts,
    build_blocks,
    entry_for,
    group_of,
    parse_order,
)
from YamlHandler.GrfLoader import GrfLoader


def facts(identifier, name, date, train_type, feature="FEAT_TRAINS", position=0):
    return VehicleFacts(
        identifier=identifier,
        name=name,
        feature=feature,
        introduction_date=date,
        train_type=train_type,
        position=position,
    )


def identifiers(block):
    return [
        line.strip().rstrip(",")
        for line in block.splitlines()
        if line.startswith("  ") and not line.strip().startswith("//") and line.strip()
    ]


class PurchaseListOrderTests(unittest.TestCase):
    def test_standard_class_stock_is_not_a_class_grouping(self):
        """`Standard Class 9F` is not `Class 9F`, so it takes the date group."""
        standard = facts("br_standard_9f", "Standard Class 9F", "date(1954, 2, 4)", TrainType.LOCOMOTIVE)
        self.assertEqual(group_of(standard), 1)

    def test_class_named_stock_is_grouped_by_class_then_subclass(self):
        self.assertEqual(group_of(facts("a", "Class 375/4", "date(1999, 4, 21)", TrainType.MULTIPLE_UNIT)), 2)
        self.assertEqual(entry_for(facts("a", "Class 375/4", "date(1999, 4, 21)", TrainType.MULTIPLE_UNIT)).subclass, 4)
        self.assertEqual(entry_for(facts("a", "Class 08", "date(1952, 4, 21)", TrainType.LOCOMOTIVE)).class_number, 8)

    def test_coaches_and_wagons_take_their_own_groups(self):
        self.assertEqual(group_of(facts("c", "Mk3 Sleeper", "date(1982, 1, 1)", TrainType.COACH)), 3)
        self.assertEqual(group_of(facts("w", "Conflat A", "date(1950, 1, 1)", TrainType.WAGON)), 4)

    def test_trains_are_grouped_then_dated_within_each_group(self):
        variants = [
            _Stub("cls_88", "Class 88", "date(2017, 6, 11)", TrainType.LOCOMOTIVE),
            _Stub("std_9f", "Standard Class 9F", "date(1954, 2, 4)", TrainType.LOCOMOTIVE),
            _Stub("cls_375_4", "Class 375/4", "date(1999, 4, 21)", TrainType.MULTIPLE_UNIT),
            _Stub("kestrel", "Kestrel", "date(1967, 1, 1)", TrainType.LOCOMOTIVE),
            _Stub("cls_375_3", "Class 375/3", "date(1999, 4, 21)", TrainType.MULTIPLE_UNIT),
            _Stub("sleeper", "Mk3 Sleeper", "date(1982, 1, 1)", TrainType.COACH),
            _Stub("conflat", "Conflat A", "date(1950, 1, 1)", TrainType.WAGON),
        ]

        blocks = build_blocks(variants, GROUPED)

        self.assertEqual(len(blocks), 1)
        self.assertEqual(
            identifiers(blocks[0]),
            ["std_9f", "kestrel", "cls_88", "cls_375_3", "cls_375_4", "sleeper", "conflat"],
        )

    def test_a_units_variants_stay_contiguous_in_generation_order(self):
        variants = [
            _Stub("unit_a_1", "Class 375/4", "date(1999, 4, 21)", TrainType.MULTIPLE_UNIT),
            _Stub("unit_a_2", "Class 375/4", "date(1999, 4, 21)", TrainType.MULTIPLE_UNIT),
            _Stub("unit_b_1", "Class 375/3", "date(1999, 4, 21)", TrainType.MULTIPLE_UNIT),
        ]

        blocks = build_blocks(variants, GROUPED)

        self.assertEqual(identifiers(blocks[0]), ["unit_b_1", "unit_a_1", "unit_a_2"])

    def test_trams_are_dated_whatever_the_order_setting(self):
        variants = [
            _Stub("tram_555", "Class 555 Metro", "date(2024, 5, 1)", TrainType.MULTIPLE_UNIT, feature="FEAT_ROADVEHS"),
            _Stub("tram_777", "Class 777 METRO", "date(2023, 1, 23)", TrainType.MULTIPLE_UNIT, feature="FEAT_ROADVEHS"),
        ]

        blocks = build_blocks(variants, GROUPED)

        self.assertEqual(identifiers(blocks[0]), ["tram_777", "tram_555"])
        self.assertIn("sort(FEAT_ROADVEHS, [", blocks[0])

    def test_date_order_ignores_the_groups(self):
        variants = [
            _Stub("cls_88", "Class 88", "date(2017, 6, 11)", TrainType.LOCOMOTIVE),
            _Stub("conflat", "Conflat A", "date(1950, 1, 1)", TrainType.WAGON),
            _Stub("std_9f", "Standard Class 9F", "date(1954, 2, 4)", TrainType.LOCOMOTIVE),
        ]

        blocks = build_blocks(variants, DATE)

        self.assertEqual(identifiers(blocks[0]), ["conflat", "std_9f", "cls_88"])

    def test_none_emits_nothing(self):
        variants = [
            _Stub("a", "Class 88", "date(2017, 6, 11)", TrainType.LOCOMOTIVE),
            _Stub("b", "Class 90", "date(2017, 6, 11)", TrainType.LOCOMOTIVE),
        ]

        self.assertEqual(build_blocks(variants, NONE), [])

    def test_a_single_item_needs_no_sort_block(self):
        variants = [_Stub("a", "Class 88", "date(2017, 6, 11)", TrainType.LOCOMOTIVE)]

        self.assertEqual(build_blocks(variants, GROUPED), [])

    def test_an_undated_vehicle_sorts_last_within_its_group(self):
        variants = [
            _Stub("undated", "Kestrel", None, TrainType.LOCOMOTIVE),
            _Stub("dated", "APT-E", "date(1972, 4, 21)", TrainType.MULTIPLE_UNIT),
        ]

        blocks = build_blocks(variants, GROUPED)

        self.assertEqual(identifiers(blocks[0]), ["dated", "undated"])


class PurchaseListOrderValidationTests(unittest.TestCase):
    def test_parse_order_accepts_the_named_orders(self):
        self.assertEqual(parse_order(None), NONE)
        self.assertEqual(parse_order("grouped"), GROUPED)
        self.assertEqual(parse_order(" DATE "), DATE)

    def test_parse_order_rejects_an_unknown_value(self):
        with self.assertRaises(ValueError):
            parse_order("class-grouped")

    def test_loader_reads_the_order_from_grf_yaml(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "GRF.yaml"
            path.write_text(
                "grf:\n  grfid: TEST\n  short_name: Test\n  name: Test\n  description: Test\n"
                "versioning:\n  version: 1\n  compatible_version: 1\n"
                "purchase_list:\n  order: grouped\n",
                encoding="utf-8",
            )
            grf = GrfLoader(path).load()

        self.assertEqual(grf.purchase_list_order, GROUPED)

    def test_loader_reads_a_manual_purchase_list_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "GRF.yaml"
            path.write_text(
                "grf:\n  grfid: TEST\n  short_name: Test\n  name: Test\n  description: Test\n"
                "versioning:\n  version: 1\n  compatible_version: 1\n"
                "purchase_list:\n  file: custom_nml/append/sortpurchase.pnml\n",
                encoding="utf-8",
            )
            grf = GrfLoader(path).load()

        self.assertEqual(grf.purchase_list_file, "custom_nml/append/sortpurchase.pnml")

    def test_loader_reads_a_purchase_list_script(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "GRF.yaml"
            path.write_text(
                "grf:\n  grfid: TEST\n  short_name: Test\n  name: Test\n  description: Test\n"
                "versioning:\n  version: 1\n  compatible_version: 1\n"
                "purchase_list:\n  script: tools/generate_sortpurchase.py\n",
                encoding="utf-8",
            )
            grf = GrfLoader(path).load()

        self.assertEqual(grf.purchase_list_script, "tools/generate_sortpurchase.py")

    def test_loader_rejects_naming_both_a_file_and_a_script(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "GRF.yaml"
            path.write_text(
                "grf:\n  grfid: TEST\n  short_name: Test\n  name: Test\n  description: Test\n"
                "versioning:\n  version: 1\n  compatible_version: 1\n"
                "purchase_list:\n  script: tools/generate_sortpurchase.py\n"
                "  file: custom_nml/append/sortpurchase.pnml\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                GrfLoader(path).load()

    def test_loader_rejects_an_absolute_purchase_list_script(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "GRF.yaml"
            path.write_text(
                "grf:\n  grfid: TEST\n  short_name: Test\n  name: Test\n  description: Test\n"
                "versioning:\n  version: 1\n  compatible_version: 1\n"
                "purchase_list:\n  script: /tmp/generate_sortpurchase.py\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                GrfLoader(path).load()

    def test_loader_defaults_to_no_sorting(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "GRF.yaml"
            path.write_text(
                "grf:\n  grfid: TEST\n  short_name: Test\n  name: Test\n  description: Test\n"
                "versioning:\n  version: 1\n  compatible_version: 1\n",
                encoding="utf-8",
            )
            grf = GrfLoader(path).load()

        self.assertEqual(grf.purchase_list_order, NONE)

    def test_loader_rejects_an_unknown_order(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "GRF.yaml"
            path.write_text(
                "grf:\n  grfid: TEST\n  short_name: Test\n  name: Test\n  description: Test\n"
                "versioning:\n  version: 1\n  compatible_version: 1\n"
                "purchase_list:\n  order: alphabetical\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                GrfLoader(path).load()


class PurchaseListCollationTests(unittest.TestCase):
    def test_generated_block_lands_after_the_last_item(self):
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            item_file = project_root / "WorkingData" / "Example" / "example.gnml"
            item_file.parent.mkdir(parents=True, exist_ok=True)
            item_file.write_text("item (FEAT_TRAINS, example) {\n}\n", encoding="utf-8")

            generated = "sort(FEAT_TRAINS, [\n  example\n]);"
            collated = NmlCollator().collate(
                [str(item_file)],
                "Example",
                None,
                project_root,
                generated_trailing_nml=[generated],
            )
            text = Path(collated).read_text(encoding="utf-8")

        self.assertLess(text.index("item (FEAT_TRAINS, example)"), text.index("sort(FEAT_TRAINS"))
        self.assertIn("// File: generated/purchase_list_feat_trains.pnml", text)

    def test_generated_block_precedes_a_custom_append_file(self):
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            custom_nml = project_root / "src" / "grf" / "custom_nml"
            (custom_nml / "append").mkdir(parents=True)
            (custom_nml / "append" / "extra.pnml").write_text(
                "// hand written last word\n", encoding="utf-8"
            )
            item_file = project_root / "WorkingData" / "Example" / "example.gnml"
            item_file.parent.mkdir(parents=True, exist_ok=True)
            item_file.write_text("item (FEAT_TRAINS, example) {\n}\n", encoding="utf-8")

            collated = NmlCollator().collate(
                [str(item_file)],
                "Example",
                custom_nml,
                project_root,
                generated_trailing_nml=["sort(FEAT_TRAINS, [\n  example\n]);"],
            )
            text = Path(collated).read_text(encoding="utf-8")

        self.assertLess(text.index("sort(FEAT_TRAINS"), text.index("hand written last word"))

    def test_named_manual_append_file_is_not_compiled_twice(self):
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            custom_nml = project_root / "src" / "grf" / "custom_nml"
            (custom_nml / "append").mkdir(parents=True)
            manual = "sort(FEAT_TRAINS, [example]);\n"
            manual_path = custom_nml / "append" / "sortpurchase.pnml"
            manual_path.write_text(manual, encoding="utf-8")
            item_file = project_root / "WorkingData" / "Example" / "example.gnml"
            item_file.parent.mkdir(parents=True, exist_ok=True)
            item_file.write_text("item (FEAT_TRAINS, example) {\n}\n", encoding="utf-8")

            collated = NmlCollator().collate(
                [str(item_file)],
                "Example",
                custom_nml,
                project_root,
                generated_trailing_nml=[manual],
                skip_custom_nml=[manual_path],
            )
            text = Path(collated).read_text(encoding="utf-8")

        self.assertEqual(text.count("sort(FEAT_TRAINS, [example]);"), 1)


class PurchaseListScriptTests(unittest.TestCase):
    """`purchase_list.script` runs the project's own generator before the block is read.

    It is handed the items this build produced, so a list that names their symbols cannot
    go stale. With a `file` named, the script is expected to bring that file up to date and
    the file is what the build reads; without one, what the script prints is the block.
    """

    def context(self, folder) -> SimpleNamespace:
        grf = Grf(grfid="TEST", short_name="Test", name="Test", description="Test", version="1", compatible_version="1")

        return SimpleNamespace(
            grf=grf,
            project=SimpleNamespace(path=Path(folder), name="Example", grfFolder="src/grf"),
            successful_variants=[
                _Stub("thomas_default_blue_train", "Thomas", "date(1920, 1, 1)", TrainType.LOCOMOTIVE),
                _Stub(
                    "toby_default_brown_tram",
                    "Toby",
                    "date(1920, 1, 1)",
                    TrainType.LOCOMOTIVE,
                    feature="FEAT_ROADVEHS",
                ),
            ],
            nml_output_folder=str(Path(folder) / "WorkingData" / "Example"),
        )

    def write_script(self, folder, body: str) -> Path:
        script = Path(folder) / "tools" / "generate_sortpurchase.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(body, encoding="utf-8")

        return script

    def test_script_is_handed_the_items_and_its_returned_block_is_stored(self):
        # The script builds the block from the items it is given, so this also proves the
        # items handover; it reports its own progress on stdout as well as the block, and
        # nothing is written into the project.
        script_body = (
            "import argparse, json\n"
            "from pathlib import Path\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--items', required=True)\n"
            "args = parser.parse_args()\n"
            "payload = json.loads(Path(args.items).read_text())\n"
            "trains = [item['identifier'] for item in payload['features']['FEAT_TRAINS']]\n"
            "print('sort(FEAT_TRAINS, [')\n"
            "for identifier in trains:\n"
            "    print('  ' + identifier + ',')\n"
            "print(']);')\n"
        )

        with tempfile.TemporaryDirectory() as folder:
            context = self.context(folder)
            context.grf.purchase_list_script = "tools/generate_sortpurchase.py"
            self.write_script(folder, script_body)

            blocks, replaced = Builder._purchase_list_nml(context)

            stored = (Path(context.nml_output_folder) / "purchase_list.pnml").read_text()
            items = json.loads((Path(context.nml_output_folder) / "purchase_list_items.json").read_text())
            project_files = sorted(path.name for path in Path(folder).glob("src/**/*.pnml"))

        self.assertEqual(blocks, [stored])
        self.assertIn("thomas_default_blue_train", stored)
        self.assertEqual(replaced, [])
        self.assertEqual(project_files, [], "the list must not be written into the project")
        self.assertEqual(
            [item["identifier"] for item in items["features"]["FEAT_TRAINS"]],
            ["thomas_default_blue_train"],
        )
        self.assertEqual(
            [item["identifier"] for item in items["features"]["FEAT_ROADVEHS"]],
            ["toby_default_brown_tram"],
        )

    def test_a_static_file_is_used_when_no_script_is_named(self):
        with tempfile.TemporaryDirectory() as folder:
            context = self.context(folder)
            context.grf.purchase_list_file = "custom_nml/append/sortpurchase.pnml"
            block = Path(folder) / "src" / "grf" / "custom_nml" / "append" / "sortpurchase.pnml"
            block.parent.mkdir(parents=True)
            block.write_text("sort(FEAT_TRAINS, [\n  thomas_default_blue_train\n]);\n", encoding="utf-8")

            blocks, replaced = Builder._purchase_list_nml(context)

            expected = block.read_text(encoding="utf-8")

        self.assertEqual(blocks, [expected])
        self.assertEqual(replaced, [block])

    def test_a_script_that_returns_nothing_emits_no_order(self):
        with tempfile.TemporaryDirectory() as folder:
            context = self.context(folder)
            context.grf.purchase_list_script = "tools/generate_sortpurchase.py"
            self.write_script(folder, "pass\n")

            blocks, replaced = Builder._purchase_list_nml(context)

            stored = Path(context.nml_output_folder) / "purchase_list.pnml"

        self.assertEqual(blocks, [])
        self.assertEqual(replaced, [])
        self.assertFalse(stored.exists())

    def test_a_failing_script_fails_the_build(self):
        with tempfile.TemporaryDirectory() as folder:
            context = self.context(folder)
            context.grf.purchase_list_script = "tools/generate_sortpurchase.py"
            self.write_script(folder, "import sys\nsys.stderr.write('no items\\n')\nsys.exit(3)\n")

            with self.assertRaises(RuntimeError) as caught:
                Builder._purchase_list_nml(context)

        self.assertIn("no items", str(caught.exception))

    def test_a_missing_script_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            context = self.context(folder)
            context.grf.purchase_list_script = "tools/generate_sortpurchase.py"

            with self.assertRaises(FileNotFoundError):
                Builder._purchase_list_nml(context)

    def test_a_script_must_stay_inside_the_project(self):
        with tempfile.TemporaryDirectory() as folder:
            context = self.context(folder)
            context.grf.purchase_list_script = "../elsewhere/generate.py"

            with self.assertRaises(ValueError):
                Builder._purchase_list_nml(context)


class _Stub:
    """The minimum of a processed `Variant` the purchase-list order reads."""

    def __init__(self, identifier, name, introduction_date, train_type, feature="FEAT_TRAINS"):
        self.identifier = identifier
        self.vehicle = _StubVehicle(name, introduction_date, train_type)
        self.vehicle_type = _StubVehicleType(feature)

    def get_attr(self, attr):
        return None


class _StubVehicle:
    def __init__(self, name, introduction_date, train_type):
        self.name = name
        self.identifier = name.lower().replace(" ", "_")
        self.introduction_date = introduction_date
        self.train_type = train_type


class _StubVehicleType:
    def __init__(self, nml_feature):
        self.nml_feature = nml_feature


if __name__ == "__main__":
    unittest.main()
