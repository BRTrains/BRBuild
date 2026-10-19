import tempfile
import unittest
from pathlib import Path

from Grf import Grf
from NmlWriter.NmlGrfWriter import NmlGrfWriter
from YamlHandler.GrfLoader import GrfLoader


class GlobalActionsTests(unittest.TestCase):
    def test_loader_reads_global_actions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "GRF.yaml"
            path.write_text(
                """grf:\n  grfid: TEST\n  short_name: Test\n  name: Test\n  description: Test\nversioning:\n  version: 1\n  compatible_version: 1\nglobal_actions:\n  - condition: param_hide == 1\n    action: disable_item(FEAT_TRAINS)\n""",
                encoding="utf-8",
            )
            grf = GrfLoader(path).load()

        self.assertEqual(
            grf.global_properties,
            {"traininfo_y_offset": 2, "train_width_32_px": 1},
        )
        self.assertEqual(
            grf.global_actions,
            [{"condition": "param_hide == 1", "action": "disable_item(FEAT_TRAINS)"}],
        )

    def test_loader_reads_cost_scale(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "GRF.yaml"
            path.write_text(
                """grf:\n  grfid: TEST\n  short_name: Test\n  name: Test\n  description: Test\nversioning:\n  version: 1\n  compatible_version: 1\ncost_scale: 0.8\n""",
                encoding="utf-8",
            )
            grf = GrfLoader(path).load()

        self.assertEqual(grf.cost_scale, 0.8)

    def test_loader_rejects_cost_scale_that_can_overflow_a_four_x_callback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "GRF.yaml"
            path.write_text(
                """grf:\n  grfid: TEST\n  short_name: Test\n  name: Test\n  description: Test\nversioning:\n  version: 1\n  compatible_version: 1\ncost_scale: 2\n""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "65535"):
                GrfLoader(path).load()

    def test_writer_emits_conditional_global_action(self):
        grf = Grf(
            grfid="TEST",
            short_name="Test",
            name="Test",
            description="Test",
            version="1",
            compatible_version="1",
            global_actions=[
                {"condition": "param_hide == 1", "action": "disable_item(FEAT_TRAINS)"}
            ],
        )
        with tempfile.TemporaryDirectory() as folder:
            output = NmlGrfWriter(grf).write_grf_gnml(Path(folder) / "GRF.gnml")
            text = output.read_text(encoding="utf-8")

        self.assertIn("traininfo_y_offset = 2;\ntrain_width_32_px = 1;", text)
        self.assertIn(
            "if (param_hide == 1)\n{\n\tdisable_item(FEAT_TRAINS);\n}",
            text,
        )


if __name__ == "__main__":
    unittest.main()
