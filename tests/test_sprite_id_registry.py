import tempfile
import unittest
from pathlib import Path

from Builder.SpriteIDRegistry import SpriteIDRegistry


class SpriteIDRegistryTests(unittest.TestCase):
    def test_unlocked_ids_are_reused_in_development(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            registry = SpriteIDRegistry(root / "VehicleIDData.yaml", root / "generated_variants")
            first = registry.resolve("train", "default", "blue", "train", self._compatibility())
            registry.mark_written(first)
            registry.finalize(root / "output")

            registry = SpriteIDRegistry(root / "VehicleIDData.yaml", root / "generated_variants")
            registry.prepare({("train", "default", "red", "train")})
            replacement = registry.resolve("train", "default", "red", "train", self._compatibility())

            self.assertEqual(replacement["id"], 1001)

    def test_release_breaking_change_creates_deprecated_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            yaml_path = root / "VehicleIDData.yaml"
            archive = root / "generated_variants"
            source = root / "variant.gnml"
            source.write_text(
                "item (FEAT_TRAINS, train_default_blue, 1001) {\n"
                "\tproperty {\n"
                "\t\tname: string(str_train_default_blue_name);\n"
                "\t\tclimates_available: ALL_CLIMATES;\n"
                "\t}\n"
                "}\n",
                encoding="utf-8",
            )

            registry = SpriteIDRegistry(yaml_path, archive, release=True)
            first = registry.resolve("train", "default", "blue", "train", self._compatibility())
            registry.mark_written(first)
            registry.archive_variant(
                first,
                source,
                {
                    "str_train_default_blue_name": "Blue train",
                    "str_unrelated_parameter": "Ignored",
                },
                "train_default_blue",
            )
            registry.finalize(root / "output")

            registry = SpriteIDRegistry(yaml_path, archive, release=True)
            changed = registry.resolve(
                "train",
                "default",
                "blue",
                "train",
                {**self._compatibility(), "capacity": 10},
            )
            self.assertNotIn("str_unrelated_parameter", registry.entries[0]["strings"])
            registry.mark_written(changed)
            registry.archive_variant(
                changed,
                source,
                {"str_train_default_blue_v2_name": "Blue train"},
                "train_default_blue_v2",
            )
            deprecated = registry.finalize(root / "output")

            self.assertEqual(changed["id"], 1002)
            self.assertEqual(changed["generation"], 2)
            self.assertEqual(len(deprecated), 1)
            self.assertEqual(len(list(archive.glob("*.gnml"))), 2)
            deprecated_text = Path(deprecated[0]).read_text(encoding="utf-8")
            self.assertIn("NO_CLIMATE", deprecated_text)
            self.assertNotIn("ALL_CLIMATES", deprecated_text)

            strings = {}
            registry.register_deprecated_strings(
                lambda text, name: strings.setdefault(name, text)
            )
            self.assertEqual(strings["str_train_default_blue_name"], "(DEPRECATED) Blue train")
            self.assertNotIn("str_unrelated_parameter", registry.entries[0]["strings"])

            registry = SpriteIDRegistry(yaml_path, archive, release=True)
            unchanged = registry.resolve(
                "train",
                "default",
                "blue",
                "train",
                {**self._compatibility(), "capacity": 10},
            )
            registry.mark_written(unchanged)
            registry.archive_variant(
                unchanged,
                source,
                {"str_train_default_blue_v2_name": "Blue train"},
                "train_default_blue_v2",
            )
            self.assertEqual(len(registry.finalize(root / "output")), 1)

    @staticmethod
    def _compatibility():
        return {"capacity": 0, "articulated_count": 1, "lengths": [4]}


if __name__ == "__main__":
    unittest.main()