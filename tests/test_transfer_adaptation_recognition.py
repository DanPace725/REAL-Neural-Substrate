from __future__ import annotations

import unittest

from scripts.probe_transfer_adaptation_recognition import (
    evaluate_transfer_adaptation_recognition,
)


class TestTransferAdaptationRecognition(unittest.TestCase):
    def test_probe_reports_early_adaptation_and_anticipation_fields(self) -> None:
        result = evaluate_transfer_adaptation_recognition(
            train_scenario="cvt1_task_a_stage1",
            transfer_scenario="cvt1_task_b_stage1",
            seeds=(13,),
        )

        self.assertEqual(result["train_scenario"], "cvt1_task_a_stage1")
        self.assertEqual(result["transfer_scenario"], "cvt1_task_b_stage1")
        self.assertEqual(result["seeds"], [13])
        self.assertEqual(len(result["results"]), 1)
        case = result["results"][0]
        self.assertEqual(case["seed"], 13)
        self.assertIn("early_window_exact_rate", case["delta"])
        self.assertIn("first_expected_transform_example", case["delta"])
        enabled_metrics = case["recognition_bias_enabled"]["transfer_metrics"]
        self.assertIn("first_expected_transform_example", enabled_metrics)
        self.assertIn("early_window_wrong_transform_family_rate", enabled_metrics)
        self.assertIn("anticipation", enabled_metrics)
        self.assertIn(
            "recognized_source_transform_entry_count",
            enabled_metrics["anticipation"],
        )
        self.assertIn("predicted_route_entry_count", enabled_metrics["anticipation"])
        self.assertGreater(
            int(enabled_metrics["anticipation"]["predicted_route_entry_count"]),
            0,
        )


if __name__ == "__main__":
    unittest.main()
