from __future__ import annotations

import unittest

from scripts.diagnose_phase8_transfer_selector_interaction import (
    evaluate_phase8_transfer_selector_interaction,
)


class TestPhase8TransferSelectorInteraction(unittest.TestCase):
    def test_selector_interaction_probe_reports_source_breakdowns(self) -> None:
        result = evaluate_phase8_transfer_selector_interaction(seed=13)

        enabled = result["recognition_bias_enabled"]
        disabled = result["recognition_bias_disabled"]

        self.assertTrue(enabled["recognition_bias_enabled"])
        self.assertFalse(disabled["recognition_bias_enabled"])
        self.assertGreater(int(enabled["source_route_decision_count"]), 0)
        self.assertGreater(int(disabled["source_route_decision_count"]), 0)

        first_enabled = enabled["source_route_decisions"][0]
        self.assertIn("chosen_breakdown", first_enabled)
        self.assertIn("recognition_transform_term", first_enabled["chosen_breakdown"])
        self.assertIn("task_transform_bonus_term", first_enabled["chosen_breakdown"])
        self.assertIn("top_competitor_breakdown", first_enabled)


if __name__ == "__main__":
    unittest.main()
