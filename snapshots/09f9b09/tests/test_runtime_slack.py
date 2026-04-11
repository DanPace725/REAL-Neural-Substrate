from __future__ import annotations

import unittest

from scripts.evaluate_runtime_slack import evaluate_runtime_slack


class TestRuntimeSlack(unittest.TestCase):
    def test_runtime_slack_reports_multiplier_runs(self) -> None:
        result = evaluate_runtime_slack(
            benchmark_ids=("B2",),
            task_keys=("task_a",),
            method_ids=("self-selected",),
            seeds=(13,),
            cycle_multipliers=(1.0, 1.5),
        )

        self.assertEqual(result["benchmark_ids"], ["B2"])
        self.assertEqual(result["task_keys"], ["task_a"])
        self.assertEqual(result["method_ids"], ["self-selected"])
        self.assertEqual(result["cycle_multipliers"], [1.0, 1.5])
        self.assertEqual(result["aggregate"]["case_count"], 1)
        case = result["results"][0]
        self.assertEqual(case["benchmark_id"], "B2")
        self.assertEqual(case["method_id"], "self-selected")
        self.assertEqual([run["cycle_multiplier"] for run in case["runs"]], [1.0, 1.5])
        self.assertEqual(case["runs"][0]["delta_exact_match_rate"], 0.0)
        self.assertIn("best_rolling_exact_rate", case["runs"][1])
        self.assertIn("anticipation", case["runs"][1])
        self.assertIn(
            "predicted_route_entry_count",
            case["runs"][1]["anticipation"],
        )


if __name__ == "__main__":
    unittest.main()
