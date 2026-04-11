from __future__ import annotations

import unittest

from scripts.probe_phase8_transfer_recognition import (
    evaluate_phase8_transfer_recognition_probe,
)


class TestPhase8TransferRecognitionProbe(unittest.TestCase):
    def test_transfer_probe_reports_warm_variants_and_recognition_stats(self) -> None:
        result = evaluate_phase8_transfer_recognition_probe(seed=13)

        enabled = result["warm_transfer_with_recognition_bias"]
        disabled = result["warm_transfer_without_recognition_bias"]

        self.assertTrue(enabled["recognition_bias_enabled"])
        self.assertFalse(disabled["recognition_bias_enabled"])
        self.assertGreaterEqual(enabled["recognition"]["route_entry_count"], 0)
        self.assertGreaterEqual(disabled["recognition"]["route_entry_count"], 0)
        self.assertGreater(enabled["recognition"]["recognized_route_entry_count"], 0)
        self.assertGreater(disabled["recognition"]["recognized_route_entry_count"], 0)
        self.assertIn("best_rolling_exact_rate", enabled["transfer_metrics"])
        self.assertIn("best_rolling_exact_rate", disabled["transfer_metrics"])
        self.assertIn("first_wrong_delivery_cycle", enabled["recognition"])
        self.assertIn("first_recognized_route_cycle", enabled["recognition"])
        self.assertIsNotNone(enabled["recognition"]["first_recognized_route_cycle"])
        self.assertIn("first_source_route_cycle", enabled["recognition"])
        self.assertIn(
            "recognized_source_transform_entry_count",
            enabled["recognition"],
        )
        self.assertIn(
            "first_recognized_source_transform_cycle",
            enabled["recognition"],
        )
        self.assertIn(
            "recognized_source_transform_on_first_source_route",
            enabled["recognition"],
        )
        self.assertIn("mean_route_cost", result["delta_enabled_minus_disabled"])


if __name__ == "__main__":
    unittest.main()
