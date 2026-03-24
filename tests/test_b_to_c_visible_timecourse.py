from __future__ import annotations

import unittest

from scripts.analyze_b_to_c_visible_timecourse import (
    MODE_FULL,
    MODE_FULL_CONTEXT_ACTIONS_SCRUBBED,
    MODE_FULL_CONTEXT_SCRUBBED,
    MODE_NONE,
    analyze_b_to_c_visible_timecourse,
)


class TestBToCVisibleTimecourse(unittest.TestCase):
    def test_visible_timecourse_reports_cycle_records_and_focused_nodes(self) -> None:
        result = analyze_b_to_c_visible_timecourse(
            seeds=(13,),
            modes=(
                MODE_NONE,
                MODE_FULL,
                MODE_FULL_CONTEXT_ACTIONS_SCRUBBED,
                MODE_FULL_CONTEXT_SCRUBBED,
            ),
        )

        self.assertEqual(result["train_scenario"], "cvt1_task_b_stage1")
        self.assertEqual(result["transfer_scenario"], "cvt1_task_c_stage1")
        self.assertEqual(
            result["mode_order"],
            [
                MODE_NONE,
                MODE_FULL,
                MODE_FULL_CONTEXT_ACTIONS_SCRUBBED,
                MODE_FULL_CONTEXT_SCRUBBED,
            ],
        )
        case = result["results"][0]
        mode_case = case["carryover_modes"][MODE_FULL]
        self.assertIn("timeline", mode_case)
        self.assertIn("summary", mode_case)
        self.assertGreater(len(mode_case["timeline"]), 0)
        first_cycle = mode_case["timeline"][0]
        self.assertIn("source_selector", first_cycle)
        self.assertIn("focused_selector_snapshots", first_cycle)
        self.assertIn("focused_node_snapshots", first_cycle)
        self.assertIn("selector_cycle", first_cycle)
        self.assertIn("context_1_branch_counts", first_cycle)
        self.assertIn("wrong_transform_family", first_cycle)
        self.assertIn("delta_wrong_transform_family", first_cycle)
        focused_nodes = first_cycle["focused_node_snapshots"]
        self.assertEqual(sorted(focused_nodes.keys()), ["n0", "n1", "n2"])
        focused_selectors = first_cycle["focused_selector_snapshots"]
        self.assertEqual(sorted(focused_selectors.keys()), ["n0", "n1", "n2"])
        self.assertEqual(
            first_cycle["expected_context_1_transform"],
            "xor_mask_0101",
        )

        summary = mode_case["summary"]
        self.assertIn("early_selector_window", summary)
        self.assertIn("full_selector_window", summary)
        self.assertIn("peak_wrong_transform_family", summary)
        self.assertIn("final_context_1_mean_bit_accuracy", summary)

        aggregate = result["aggregate"]
        self.assertIn(MODE_FULL_CONTEXT_SCRUBBED, aggregate["modes"])
        self.assertIn(MODE_FULL_CONTEXT_ACTIONS_SCRUBBED, aggregate["delta_vs_full"])


if __name__ == "__main__":
    unittest.main()
