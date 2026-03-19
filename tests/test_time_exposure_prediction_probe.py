from __future__ import annotations

import unittest

from scripts.probe_time_exposure_prediction import (
    evaluate_time_exposure_prediction_probe,
)


class TestTimeExposurePredictionProbe(unittest.TestCase):
    def test_probe_reports_runtime_and_exposure_prediction_fields(self) -> None:
        result = evaluate_time_exposure_prediction_probe(
            benchmark_ids=("A1",),
            task_keys=("task_a",),
            method_ids=("self-selected",),
            seeds=(13,),
            cycle_multipliers=(1.0, 1.5),
            repeat_counts=(1, 2),
        )

        self.assertEqual(result["benchmark_ids"], ["A1"])
        self.assertIn("runtime_slack", result)
        self.assertIn("experience_extension", result)

        runtime_case = result["runtime_slack"]["cases"][0]
        self.assertEqual(runtime_case["benchmark_id"], "A1")
        self.assertEqual(len(runtime_case["runs"]), 2)
        self.assertIn("anticipation", runtime_case["runs"][0])
        self.assertIn(
            "predicted_source_route_entry_rate",
            runtime_case["runs"][0]["anticipation"],
        )

        exposure_case = result["experience_extension"]["cases"][0]
        self.assertEqual(exposure_case["benchmark_id"], "A1")
        self.assertEqual(len(exposure_case["runs"]), 2)
        self.assertIn("anticipation", exposure_case["runs"][1])
        self.assertEqual(len(exposure_case["runs"][1]["per_pass"]), 2)
        self.assertIn(
            "mean_source_prediction_confidence",
            exposure_case["runs"][1]["per_pass"][0]["anticipation"],
        )


if __name__ == "__main__":
    unittest.main()
