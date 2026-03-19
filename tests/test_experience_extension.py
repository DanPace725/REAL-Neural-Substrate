from __future__ import annotations

import unittest

from scripts.evaluate_experience_extension import evaluate_experience_extension


class TestExperienceExtension(unittest.TestCase):
    def test_experience_extension_reports_per_pass_metrics(self) -> None:
        result = evaluate_experience_extension(
            benchmark_ids=("B2",),
            task_keys=("task_a",),
            method_ids=("self-selected",),
            seeds=(13,),
            repeat_counts=(1, 2),
        )

        self.assertEqual(result["benchmark_ids"], ["B2"])
        self.assertEqual(result["repeat_counts"], [1, 2])
        self.assertEqual(result["aggregate"]["case_count"], 1)
        case = result["results"][0]
        self.assertEqual(case["benchmark_id"], "B2")
        self.assertEqual(case["method_id"], "self-selected")
        self.assertEqual([run["repeat_count"] for run in case["runs"]], [1, 2])
        self.assertEqual(case["runs"][0]["delta_exact_match_rate"], 0.0)
        self.assertEqual(len(case["runs"][1]["per_pass"]), 2)
        self.assertIn("delta_final_pass_exact_match_rate", case["runs"][1])
        self.assertIn("anticipation", case["runs"][1])
        self.assertIn(
            "predicted_source_route_entry_count",
            case["runs"][1]["anticipation"],
        )
        self.assertIn("anticipation", case["runs"][1]["per_pass"][0])


if __name__ == "__main__":
    unittest.main()
