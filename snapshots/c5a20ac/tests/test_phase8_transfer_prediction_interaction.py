from __future__ import annotations

import unittest

from scripts.diagnose_phase8_transfer_prediction_interaction import (
    evaluate_phase8_transfer_prediction_interaction,
)


class TestPhase8TransferPredictionInteraction(unittest.TestCase):
    def test_prediction_interaction_probe_reports_prediction_terms(self) -> None:
        result = evaluate_phase8_transfer_prediction_interaction(seed=13)

        enabled = result["prediction_enabled"]
        disabled = result["prediction_disabled"]

        self.assertTrue(enabled["prediction_enabled"])
        self.assertFalse(disabled["prediction_enabled"])
        self.assertGreater(int(enabled["source_route_decision_count"]), 0)
        self.assertGreater(int(disabled["source_route_decision_count"]), 0)

        first_enabled = enabled["source_route_decisions"][0]
        self.assertIn("chosen_breakdown", first_enabled)
        self.assertIn("prediction_delta_term", first_enabled["chosen_breakdown"])
        self.assertIn("prediction_coherence_term", first_enabled["chosen_breakdown"])
        self.assertIn(
            "prediction_effective_confidence_term",
            first_enabled["chosen_breakdown"],
        )
        self.assertIn(
            "prediction_stale_family_penalty_term",
            first_enabled["chosen_breakdown"],
        )
        self.assertIn("decision_deltas", result)
        self.assertIn("divergence_cycles", result["decision_deltas"])


if __name__ == "__main__":
    unittest.main()
