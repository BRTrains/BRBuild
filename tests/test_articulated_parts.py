import tempfile
import unittest
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from Builder.ItemCatalog import ItemCatalog
from Builder.Builder import Builder
from Builder.CandidateProcessor import CandidateProcessor
from Builder.SpriteIDRegistry import SpriteIDRegistry
from NmlWriter.NmlVariantWriter import NmlVariantWriter
from NmlWriter.NmlSwitchWriter import NmlSwitchWriter
from PropertyCalculation import TrainType, VehicleType
from PropertyCalculation.VehicleUsage import VehicleUsage
from Vehicle import Livery, Profile, Variant, Vehicle
from YamlHandler import VehicleLoader


class ArticulatedPartsLoaderTests(unittest.TestCase):
    def _load(self, articulated_parts):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "unit.yaml"
            path.write_text(
                "info:\n  identifier: root\n  name: Root\n"
                "stats:\n  vehicle_type: TRAIN\n  train_type: LOCOMOTIVE\n"
                "liveries:\n  - name: Blue\n"
                f"articulated_parts: {articulated_parts}\n"
            )
            return VehicleLoader.load(str(path))

    def test_loads_vehicle_profile_and_livery_scoped_parts(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "unit.yaml"
            path.write_text(
                "info:\n  identifier: root\n  name: Root\n"
                "stats:\n  vehicle_type: TRAIN\n  train_type: LOCOMOTIVE\n"
                "articulated_parts:\n  - vehicle: coach\n"
                "profiles:\n  - identifier: LONG\n    articulated_parts:\n    - vehicle: coach\n      livery: Blue\n"
                "liveries:\n  - name: Red\n    articulated_parts:\n    - vehicle: coach\n      profile: DEFAULT\n"
            )
            vehicle = VehicleLoader.load(str(path))

        self.assertEqual(vehicle.articulated_parts, [{"vehicle": "coach"}])
        self.assertEqual(vehicle.profiles[0].articulated_parts[0]["livery"], "Blue")
        self.assertEqual(vehicle.liveries[0].articulated_parts[0]["profile"], "DEFAULT")

    def test_rejects_non_list_and_missing_vehicle(self):
        with self.assertRaisesRegex(ValueError, "articulated_parts.*list"):
            self._load("coach")
        with self.assertRaisesRegex(ValueError, "articulated_parts.*requires.*vehicle"):
            self._load("[{profile: DEFAULT}]")


class ItemCatalogTests(unittest.TestCase):
    @staticmethod
    def _vehicle(identifier, *, count=1, parts=None, vehicle_type=VehicleType.TRAIN):
        return Vehicle(
            folder_path=".", identifier=identifier, name=identifier,
            vehicle_type=vehicle_type, train_type=TrainType.COACH,
            num_vehicles=count, articulated_parts=parts,
            profiles=[Profile("DEFAULT")], liveries=[Livery("Default")],
        )

    def test_resolves_targets_independent_of_source_order_and_projects_each_position(self):
        root = self._vehicle("toby", parts=[{"vehicle": "annie"}], vehicle_type=VehicleType.TRAIN)
        root.profiles[0].types = [VehicleType.TRAM]
        target = self._vehicle("annie", count=2)

        catalog = ItemCatalog.from_vehicles([root, target])
        parent = catalog.variants_for(root)[0]
        hidden = catalog.hidden_variants_for(target)

        self.assertEqual(len(hidden), 2)
        self.assertEqual(parent.articulated_part_variants, hidden)
        self.assertEqual([part.target_part_position for part in hidden], [0, 1])
        self.assertTrue(all(part.vehicle_type == VehicleType.TRAM for part in hidden))
        self.assertTrue(all(part.hidden_articulated_part for part in hidden))

    def test_reuses_the_same_position_safe_hidden_target_for_multiple_parents(self):
        first = self._vehicle("first", parts=[{"vehicle": "coach"}], vehicle_type=VehicleType.TRAM)
        second = self._vehicle("second", parts=[{"vehicle": "coach"}], vehicle_type=VehicleType.TRAM)
        target = self._vehicle("coach")

        catalog = ItemCatalog.from_vehicles([first, second, target])

        self.assertEqual(len(catalog.hidden_variants_for(target)), 1)
        self.assertEqual(
            catalog.variants_for(first)[0].articulated_part_variants,
            catalog.variants_for(second)[0].articulated_part_variants,
        )

    def test_livery_refit_inherits_vehicle_articulated_parts(self):
        root = self._vehicle("root", parts=[{"vehicle": "coach"}], vehicle_type=VehicleType.TRAM)
        root.liveries.append(Livery("Blue"))
        target = self._vehicle("coach")

        catalog = ItemCatalog.from_vehicles([root, target])
        refit = next(
            variant for variant in catalog.variants_for(root) if variant.is_livery_refit
        )

        self.assertEqual(refit.articulated_part_variants, catalog.hidden_variants_for(target))
        refit.process()
        self.assertEqual(refit.callbacks["articulated_part"], refit.articulated_switch_name)

    def test_livery_refit_inherits_identical_livery_scoped_articulated_parts(self):
        root = self._vehicle("root", vehicle_type=VehicleType.TRAM)
        root.liveries = [
            Livery("Red", articulated_parts=[{"vehicle": "coach"}]),
            Livery("Blue", articulated_parts=[{"vehicle": "COA_CH"}]),
        ]
        target = self._vehicle("coach")

        catalog = ItemCatalog.from_vehicles([root, target])
        refit = next(
            variant for variant in catalog.variants_for(root) if variant.is_livery_refit
        )

        self.assertEqual(refit.articulated_part_variants, catalog.hidden_variants_for(target))

    def test_livery_refit_accepts_equivalent_explicit_and_implicit_targets(self):
        root = self._vehicle("root", vehicle_type=VehicleType.TRAM)
        root.liveries = [
            Livery("Red", articulated_parts=[{"vehicle": "coach"}]),
            Livery(
                "Blue",
                articulated_parts=[{
                    "vehicle": "COA_CH",
                    "profile": "DEFAULT",
                    "livery": "Default",
                }],
            ),
        ]
        target = self._vehicle("coach")

        catalog = ItemCatalog.from_vehicles([root, target])
        refit = next(
            variant for variant in catalog.variants_for(root) if variant.is_livery_refit
        )

        self.assertEqual(refit.articulated_part_variants, catalog.hidden_variants_for(target))

    def test_livery_refit_rejects_differing_livery_scoped_articulated_parts(self):
        root = self._vehicle("root", vehicle_type=VehicleType.TRAM)
        root.liveries = [
            Livery("Red", articulated_parts=[{"vehicle": "coach"}]),
            Livery("Blue", articulated_parts=[{"vehicle": "van"}]),
        ]

        with self.assertRaisesRegex(
            ValueError,
            "Livery Refits.*profile 'DEFAULT'.*different articulated_parts",
        ):
            ItemCatalog.from_vehicles([
                root,
                self._vehicle("coach"),
                self._vehicle("van"),
            ])

    def test_selected_target_livery_must_apply_to_selected_profile(self):
        root = self._vehicle(
            "root",
            parts=[{"vehicle": "target", "profile": "LONG_FORM", "livery": "Blue"}],
        )
        target = self._vehicle("target")
        target.profiles = [Profile("LONG_FORM"), Profile("OTHER")]
        target.liveries = [Livery("Blue", profiles=["OTHER"])]

        with self.assertRaisesRegex(
            ValueError, "livery 'Blue'.*does not apply.*profile 'LONG_FORM'"
        ):
            ItemCatalog.from_vehicles([root, target])

    def test_missing_ambiguous_and_cyclic_references_fail_clearly(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            ItemCatalog.from_vehicles([self._vehicle("root", parts=[{"vehicle": "missing"}])])

        target = self._vehicle("target")
        target.profiles.append(Profile("OTHER"))
        with self.assertRaisesRegex(ValueError, "ambiguous.*profile"):
            ItemCatalog.from_vehicles([
                self._vehicle("root", parts=[{"vehicle": "target"}]), target
            ])

        first = self._vehicle("first", parts=[{"vehicle": "second"}])
        second = self._vehicle("second", parts=[{"vehicle": "first"}])
        with self.assertRaisesRegex(ValueError, "[Cc]ycle"):
            ItemCatalog.from_vehicles([first, second])

    def test_hidden_variant_is_not_purchasable_and_is_a_tram(self):
        root = self._vehicle("root", parts=[{"vehicle": "coach"}], vehicle_type=VehicleType.TRAM)
        target = self._vehicle("coach")
        hidden = ItemCatalog.from_vehicles([root, target]).hidden_variants_for(target)[0]

        hidden.process()

        self.assertEqual(hidden.properties["climates_available"], "NO_CLIMATE")
        self.assertIn("ROADVEH_FLAG_TRAM", hidden.properties["misc_flags"])
        self.assertNotIn("articulated_part", hidden.callbacks)

    def test_hidden_identifier_uses_registry_generation_suffix(self):
        root = self._vehicle("root", parts=[{"vehicle": "coach"}], vehicle_type=VehicleType.TRAM)
        target = self._vehicle("coach")
        catalog = ItemCatalog.from_vehicles([root, target])
        parent = catalog.variants_for(root)[0]
        hidden = catalog.hidden_variants_for(target)[0]
        hidden.sprite_id_generation = 2

        hidden.process()

        self.assertIs(parent.articulated_part_variants[0], hidden)
        self.assertEqual(hidden.identifier, "hidden_part_coach_default_default_tram_pos1_v2")

    def test_writer_emits_distinct_final_symbols_at_each_position(self):
        root = self._vehicle("toby", parts=[{"vehicle": "annie_clarabel"}], vehicle_type=VehicleType.TRAM)
        target = self._vehicle("annie_clarabel", count=2)
        catalog = ItemCatalog.from_vehicles([root, target])
        parent = catalog.variants_for(root)[0]
        hidden = catalog.hidden_variants_for(target)
        parent.process()
        hidden[0].process()
        hidden[1].sprite_id_generation = 2
        hidden[1].process()
        output = StringIO()

        writer = NmlVariantWriter.__new__(NmlVariantWriter)
        writer.switch_writer = NmlSwitchWriter()
        writer._write_articulated_switch(output, parent)
        text = output.getvalue()

        annie = "1 : hidden_part_annie_clarabel_default_default_tram_pos1"
        clarabel = "2 : hidden_part_annie_clarabel_default_default_tram_pos2_v2"
        self.assertIn(annie, text)
        self.assertIn(clarabel, text)
        self.assertLess(text.index(annie), text.index(clarabel))
        self.assertIn("CB_RESULT_NO_MORE_ARTICULATED_PARTS", text)

    def test_hidden_part_has_no_purchase_or_name_callback_chain(self):
        root = self._vehicle("root", parts=[{"vehicle": "coach"}], vehicle_type=VehicleType.TRAM)
        target = self._vehicle("coach")
        hidden = ItemCatalog.from_vehicles([root, target]).hidden_variants_for(target)[0]
        hidden.purchase_spriteset = object()
        hidden.purchase_template_name = "tmpl_purchase"
        hidden.spritesets = [object()]
        hidden.sprite_template_names = ["tmpl_tram_8"]
        hidden.sprite_lengths = [8]

        hidden.process()

        self.assertIsNone(hidden.purchase_spriteset)
        self.assertNotIn("purchase", hidden.callbacks)
        self.assertNotIn("name", hidden.callbacks)
        self.assertFalse(getattr(hidden, "name_callback_name", None))

    def test_hidden_part_ignores_target_nml_overrides(self):
        root = self._vehicle("root", parts=[{"vehicle": "coach"}], vehicle_type=VehicleType.TRAM)
        target = self._vehicle("coach")
        target.nml_override = {
            "default": "sw_target_default",
            "purchase": "sw_target_purchase",
            "name": "sw_target_name",
            "articulated_part": "sw_target_parts",
            "cargo_capacity": "sw_target_capacity",
        }
        hidden = ItemCatalog.from_vehicles([root, target]).hidden_variants_for(target)[0]
        hidden.spritesets = [object()]
        hidden.sprite_template_names = ["tmpl_tram_8"]
        hidden.sprite_lengths = [8]

        hidden.process()

        self.assertEqual(hidden.resolve_nml_override(), {})
        self.assertEqual(hidden.nml_override, {})
        self.assertEqual(hidden.callbacks["default"], hidden.sprite_switch_name)
        for callback in ("purchase", "name", "articulated_part"):
            self.assertNotIn(callback, hidden.callbacks)
        self.assertNotEqual(hidden.callbacks["cargo_capacity"], "sw_target_capacity")

    def test_hidden_part_has_no_independent_disable_conditions(self):
        root = self._vehicle("root", parts=[{"vehicle": "coach"}], vehicle_type=VehicleType.TRAM)
        target = self._vehicle("coach")
        target.development = True
        target.usage = VehicleUsage.METRO
        hidden = ItemCatalog.from_vehicles([root, target]).hidden_variants_for(target)[0]
        grf = SimpleNamespace(usage_filters=[{
            "feature": VehicleType.TRAM.nml_feature,
            "parameter": "param_tram_mode",
            "minimum": {"METRO": 1},
        }])

        CandidateProcessor(Builder())._set_disable_conditions(hidden, target, grf)

        self.assertIsNone(hidden.disable_item_condition)
        self.assertEqual(hidden.disable_item_conditions, [])

    def test_annie_and_clarabel_are_pinned_to_distinct_source_rows(self):
        root = self._vehicle("toby", parts=[{"vehicle": "annie_clarabel"}], vehicle_type=VehicleType.TRAM)
        target = self._vehicle("annie_clarabel", count=2)
        hidden = ItemCatalog.from_vehicles([root, target]).hidden_variants_for(target)
        annie_row, clarabel_row = object(), object()
        rows = [annie_row, clarabel_row]
        templates = ["tmpl_tram_6", "tmpl_tram_8"]
        lengths = [6, 8]

        for part in hidden:
            part.pin_articulated_position(rows, templates, lengths, [1, 2])

        self.assertEqual(hidden[0].spritesets, [annie_row])
        self.assertEqual(hidden[0].sprite_template_names, [templates[0]])
        self.assertEqual(hidden[0].sprite_lengths, [6])
        self.assertEqual(hidden[1].spritesets, [clarabel_row])
        self.assertEqual(hidden[1].sprite_template_names, [templates[1]])
        self.assertEqual(hidden[1].sprite_lengths, [8])

    def test_repeated_source_pattern_pins_each_physical_position(self):
        root = self._vehicle("root", parts=[{"vehicle": "unit"}], vehicle_type=VehicleType.TRAM)
        target = self._vehicle("unit", count=4)
        hidden = ItemCatalog.from_vehicles([root, target]).hidden_variants_for(target)
        front, middle, rear = object(), object(), object()
        expanded_rows = [front, middle, middle, rear]
        expanded_templates = ["front", "middle", "middle", "rear"]
        expanded_lengths = [8, 6, 6, 8]

        for part in hidden:
            part.pin_articulated_position(
                expanded_rows,
                expanded_templates,
                expanded_lengths,
                [1, 2, 2, 3],
            )

        self.assertEqual([part.spritesets[0] for part in hidden], expanded_rows)
        self.assertEqual(
            [part.sprite_template_names[0] for part in hidden], expanded_templates
        )
        self.assertEqual([part.sprite_lengths[0] for part in hidden], expanded_lengths)

    def test_parent_compatibility_uses_root_plus_resolved_appended_parts(self):
        root = self._vehicle("toby", parts=[{"vehicle": "coach"}], vehicle_type=VehicleType.TRAM)
        target = self._vehicle("coach", count=2)
        parent = ItemCatalog.from_vehicles([root, target]).variants_for(root)[0]

        snapshot = Builder._compatibility_snapshot(parent)

        self.assertEqual(snapshot["articulated_count"], 3)

    def test_missing_hidden_dependency_fails_parent_and_prunes_orphans(self):
        parent_vehicle = self._vehicle("parent", vehicle_type=VehicleType.TRAM)
        target_vehicle = self._vehicle("target")
        unrelated_vehicle = self._vehicle("unrelated")
        catalog = ItemCatalog.from_vehicles([parent_vehicle, target_vehicle, unrelated_vehicle])
        parent = catalog.variants_for(parent_vehicle)[0]
        hidden = Variant(
            target_vehicle,
            target_vehicle.liveries[0],
            target_vehicle.profiles[0],
            vehicleType=VehicleType.TRAM,
        )
        hidden.hidden_articulated_part = True
        parent.articulated_part_variants = [hidden]
        unrelated = catalog.variants_for(unrelated_vehicle)[0]
        orphan = Variant(
            target_vehicle,
            target_vehicle.liveries[0],
            target_vehicle.profiles[0],
            vehicleType=VehicleType.TRAM,
        )
        orphan.hidden_articulated_part = True
        processor = CandidateProcessor(Builder())
        processor._pending_variants = [
            (parent_vehicle, parent, object()),
            (unrelated_vehicle, unrelated, object()),
            (target_vehicle, orphan, object()),
        ]
        ctx = SimpleNamespace(
            failed_variants=[], failed_units=set(), failed_errors=[]
        )

        processor._prune_failed_dependencies(ctx)

        self.assertEqual(
            [record[1] for record in processor._pending_variants], [unrelated]
        )
        self.assertEqual(ctx.failed_variants, [repr(parent)])
        self.assertEqual(ctx.failed_units, {"parent"})
        self.assertIn("hidden articulated part", ctx.failed_errors[0]["error"])

    def test_deferred_writes_are_globally_atomic_on_writer_failure(self):
        first_vehicle = self._vehicle("first")
        second_vehicle = self._vehicle("second")
        first = ItemCatalog.from_vehicles([first_vehicle]).variants_for(first_vehicle)[0]
        second = ItemCatalog.from_vehicles([second_vehicle]).variants_for(second_vehicle)[0]
        first.nml_filename = "first.gnml"
        second.nml_filename = "second.gnml"
        registry = SimpleNamespace(marked=[], archived=[])
        registry.mark_written = registry.marked.append
        registry.archive_variant = lambda *args: registry.archived.append(args)

        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "first.gnml").write_text("previous first", encoding="utf-8")
            (Path(folder) / "second.gnml").write_text("previous second", encoding="utf-8")
            ctx = SimpleNamespace(
                nml_output_folder=folder,
                template_alignment_param_index=4,
                nml_files=[],
                variant_owners={},
                successful_variants=[],
                failed_variants=[],
                failed_units=set(),
                failed_errors=[],
                sprite_id_registry=registry,
            )
            processor = CandidateProcessor(Builder())
            processor._pending_variants = [
                (first_vehicle, first, {"entry": object()}),
                (second_vehicle, second, {"entry": object()}),
            ]

            class FailingWriter:
                def __init__(self, variant, output_path, alignment_param_index):
                    self.variant = variant
                    self.filepath = str(Path(output_path) / variant.nml_filename)

                def write(self):
                    Path(self.filepath).write_text("partial", encoding="utf-8")
                    if self.variant is second:
                        raise RuntimeError("injected writer failure")
                    return self.filepath

            with patch("Builder.CandidateProcessor.NmlVariantWriter", FailingWriter):
                with self.assertRaisesRegex(RuntimeError, "injected writer failure"):
                    processor._write_variants(ctx)

            self.assertEqual(
                (Path(folder) / "first.gnml").read_text(encoding="utf-8"),
                "previous first",
            )
            self.assertEqual(
                (Path(folder) / "second.gnml").read_text(encoding="utf-8"),
                "previous second",
            )

        self.assertEqual(ctx.nml_files, [])
        self.assertEqual(ctx.variant_owners, {})
        self.assertEqual(ctx.successful_variants, [])
        self.assertEqual(registry.marked, [])
        self.assertEqual(registry.archived, [])

    def test_deferred_parent_nml_uses_later_targets_final_generation_symbol(self):
        root = self._vehicle("toby", parts=[{"vehicle": "coach"}], vehicle_type=VehicleType.TRAM)
        target = self._vehicle("coach")
        catalog = ItemCatalog.from_vehicles([root, target])
        parent = catalog.variants_for(root)[0]
        hidden = catalog.hidden_variants_for(target)[0]

        with tempfile.TemporaryDirectory() as folder:
            registry_path = Path(folder) / "VehicleIDData.yaml"
            archive = Path(folder) / "archive"
            previous = SpriteIDRegistry(registry_path, archive, release=True)
            old_assignment = previous.resolve(
                "coach", hidden.registry_profile_identifier, "Default", "tram",
                {"capacity": 0, "articulated_count": 1, "lengths": [6]},
            )
            previous.mark_written(old_assignment)
            previous.finalize(Path(folder) / "old")

            registry = SpriteIDRegistry(registry_path, archive, release=True)
            parent_assignment = registry.resolve(
                "toby", "DEFAULT", "Default", "tram",
                Builder._compatibility_snapshot(parent),
            )
            target_assignment = registry.resolve(
                "coach", hidden.registry_profile_identifier, "Default", "tram",
                {"capacity": 0, "articulated_count": 1, "lengths": [8]},
            )
            self.assertEqual(target_assignment["generation"], 2)

            parent.sprite_id = parent_assignment["id"]
            parent.sprite_id_generation = parent_assignment["generation"]
            parent.process()
            hidden.sprite_id = target_assignment["id"]
            hidden.sprite_id_generation = target_assignment["generation"]
            hidden.process()

            ctx = type("Context", (), {
                "nml_output_folder": folder,
                "template_alignment_param_index": 4,
                "nml_files": [],
                "variant_owners": {},
                "successful_variants": [],
                "failed_variants": [],
                "failed_units": set(),
                "sprite_id_registry": registry,
            })()
            processor = CandidateProcessor(Builder())
            processor._pending_variants = [
                (root, parent, parent_assignment),
                (target, hidden, target_assignment),
            ]

            processor._write_variants(ctx)

            parent_nml = Path(ctx.nml_files[0]).read_text()

        self.assertIn("hidden_part_coach_default_default_tram_pos1_v2", parent_nml)
        self.assertEqual(ctx.successful_variants, [parent, hidden])


if __name__ == "__main__":
    unittest.main()
