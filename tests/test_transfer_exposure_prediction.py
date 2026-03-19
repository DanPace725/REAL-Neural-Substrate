from __future__ import annotations

import unittest

from scripts.probe_transfer_exposure_prediction import (
    evaluate_transfer_exposure_prediction,
)


class TestTransferExposurePrediction(unittest.TestCase):
    def test_probe_reports_per_pass_transfer_and_prediction_fields(self) -> None:
        result = evaluate_transfer_exposure_prediction(
            train_scenario="cvt1_task_a_stage1",
            transfer_scenario="cvt1_task_b_stage1",
            seeds=(13,),
            repeat_counts=(1, 2),
            carryover_mode="full",
        )

        self.assertEqual(result["train_scenario"], "cvt1_task_a_stage1")
        self.assertEqual(result["repeat_counts"], [1, 2])
        self.assertEqual(result["aggregate"]["case_count"], 1)
        case = result["results"][0]
        self.assertEqual(case["carryover_mode"], "full")
        self.assertEqual([run["repeat_count"] for run in case["runs"]], [1, 2])
        self.assertIn("transfer_metrics", case["runs"][1])
        self.assertIn("anticipation", case["runs"][1])
        self.assertIn(
            "predicted_source_route_entry_count",
            case["runs"][1]["anticipation"],
        )
        self.assertIn("per_pass", case["runs"][1])
        self.assertEqual(len(case["runs"][1]["per_pass"]), 2)
        self.assertIn("anticipation", case["runs"][1]["per_pass"][0])
        self.assertIn("delta_final_pass_exact_match_rate", case["runs"][1])


if __name__ == "__main__":
    unittest.main()
