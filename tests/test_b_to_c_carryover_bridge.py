from __future__ import annotations

import unittest

from scripts.diagnose_b_to_c_carryover_bridge import (
    MODE_FULL,
    MODE_FULL_CONTEXT_ACTIONS_SCRUBBED,
    MODE_FULL_CONTEXT_PATTERNS_SCRUBBED,
    MODE_FULL_CONTEXT_SCRUBBED,
    MODE_NONE,
    MODE_SUBSTRATE,
    MODE_SUBSTRATE_CONTEXT_ACTIONS_SCRUBBED,
    MODE_SUBSTRATE_CONTEXT_PATTERNS_SCRUBBED,
    MODE_SUBSTRATE_CONTEXT_SCRUBBED,
    diagnose_b_to_c_carryover_bridge,
)


class TestBToCCarryoverBridge(unittest.TestCase):
    def test_bridge_reports_scrubbed_modes_and_transfer_runs(self) -> None:
        result = diagnose_b_to_c_carryover_bridge(seeds=(13,))

        self.assertEqual(result["train_scenario"], "cvt1_task_b_stage1")
        self.assertEqual(result["transfer_scenario"], "cvt1_task_c_stage1")
        case = result["results"][0]
        self.assertIn("carryover_modes", case)
        for mode_name in (
            MODE_NONE,
            MODE_SUBSTRATE,
            MODE_SUBSTRATE_CONTEXT_ACTIONS_SCRUBBED,
            MODE_SUBSTRATE_CONTEXT_PATTERNS_SCRUBBED,
            MODE_SUBSTRATE_CONTEXT_SCRUBBED,
            MODE_FULL,
            MODE_FULL_CONTEXT_ACTIONS_SCRUBBED,
            MODE_FULL_CONTEXT_PATTERNS_SCRUBBED,
            MODE_FULL_CONTEXT_SCRUBBED,
        ):
            self.assertIn(mode_name, case["carryover_modes"])
            mode_case = case["carryover_modes"][mode_name]
            self.assertIn("bridge_summary", mode_case)
            self.assertIn("first_decisions", mode_case)
            self.assertIn("transfer_run", mode_case)
            self.assertIn("delta_vs_none", mode_case)
            self.assertIn("context_0", mode_case["first_decisions"])
            self.assertEqual(
                mode_case["first_decisions"]["context_0"]["expected_transform"],
                "xor_mask_1010",
            )

        substrate_scrubbed = case["carryover_modes"][MODE_SUBSTRATE_CONTEXT_SCRUBBED]
        self.assertTrue(substrate_scrubbed["bridge_summary"]["scrubbed"])
        self.assertGreater(
            substrate_scrubbed["bridge_summary"]["zeroed_context_action_keys"],
            0,
        )
        self.assertGreaterEqual(
            substrate_scrubbed["bridge_summary"]["removed_context_transform_patterns"],
            0,
        )
        action_only = case["carryover_modes"][MODE_SUBSTRATE_CONTEXT_ACTIONS_SCRUBBED]
        self.assertTrue(action_only["bridge_summary"]["scrubbed"])
        self.assertGreater(
            action_only["bridge_summary"]["zeroed_context_action_keys"],
            0,
        )
        self.assertEqual(
            action_only["bridge_summary"]["removed_context_transform_patterns"],
            0,
        )
        pattern_only = case["carryover_modes"][MODE_SUBSTRATE_CONTEXT_PATTERNS_SCRUBBED]
        self.assertTrue(pattern_only["bridge_summary"]["scrubbed"])
        self.assertEqual(
            pattern_only["bridge_summary"]["zeroed_context_action_keys"],
            0,
        )
        self.assertGreaterEqual(
            pattern_only["bridge_summary"]["removed_context_transform_patterns"],
            0,
        )

        aggregate = result["aggregate"]
        self.assertEqual(
            aggregate["mode_order"],
            [
                MODE_NONE,
                MODE_SUBSTRATE,
                MODE_SUBSTRATE_CONTEXT_ACTIONS_SCRUBBED,
                MODE_SUBSTRATE_CONTEXT_PATTERNS_SCRUBBED,
                MODE_SUBSTRATE_CONTEXT_SCRUBBED,
                MODE_FULL,
                MODE_FULL_CONTEXT_ACTIONS_SCRUBBED,
                MODE_FULL_CONTEXT_PATTERNS_SCRUBBED,
                MODE_FULL_CONTEXT_SCRUBBED,
            ],
        )
        self.assertIn(MODE_FULL_CONTEXT_SCRUBBED, aggregate["modes"])
        self.assertIn(MODE_FULL_CONTEXT_ACTIONS_SCRUBBED, aggregate["modes"])
        self.assertIn(MODE_FULL_CONTEXT_PATTERNS_SCRUBBED, aggregate["modes"])


if __name__ == "__main__":
    unittest.main()
