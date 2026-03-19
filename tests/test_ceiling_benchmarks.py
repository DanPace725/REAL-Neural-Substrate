from __future__ import annotations

import unittest

from scripts.ceiling_benchmark_metrics import collapse_flag, frontier_summary
from scripts.ceiling_benchmark_suite import benchmark_point_ids, benchmark_suite_by_id, build_ceiling_benchmark_suite
from scripts.compare_ceiling_benchmarks import _run_nn_method, _run_real_method, evaluate_ceiling_benchmarks
from scripts.compare_self_selected_smoke import evaluate_self_selected_smoke
from scripts.neural_baseline import cvt1_stage1_examples, run_mlp_explicit
from scripts.neural_baseline_torch import torch_available


class TestCeilingBenchmarkSuite(unittest.TestCase):
    def test_suite_is_monotonic_and_deterministic(self) -> None:
        first = build_ceiling_benchmark_suite()
        second = build_ceiling_benchmark_suite()

        self.assertEqual(benchmark_point_ids(first), benchmark_point_ids(second))
        self.assertEqual(benchmark_point_ids(first), ("A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4", "C1", "C2", "C3", "C4"))

        by_family: dict[str, list[int]] = {}
        for point in first:
            by_family.setdefault(point.family_id, []).append(point.difficulty_index)
            self.assertEqual(tuple(point.tasks.keys()), ("task_a", "task_b", "task_c"))
            self.assertGreater(point.expected_examples, 0)
        self.assertEqual(by_family["A"], [1, 2, 3, 4])
        self.assertEqual(by_family["B"], [1, 2, 3, 4])
        self.assertEqual(by_family["C"], [1, 2, 3, 4])

    def test_manifest_aggregates_include_schema_fields(self) -> None:
        result = evaluate_ceiling_benchmarks(
            seeds=(13,),
            benchmark_ids=("A1",),
            include_transfer=False,
            allow_missing_torch=True,
        )

        aggregates = result["cold_start"]["aggregates"]
        self.assertTrue(aggregates)
        for aggregate in aggregates:
            self.assertIn("benchmark_id", aggregate)
            self.assertIn("family_id", aggregate)
            self.assertIn("difficulty_index", aggregate)
            self.assertIn("method_id", aggregate)
            self.assertIn("collapse_flag", aggregate)
            self.assertIn("in_transfer_slice", aggregate)
            if aggregate["method_id"] in ("fixed-visible", "fixed-latent", "growth-visible", "growth-latent", "self-selected"):
                self.assertIn("oracle_exact_gap", aggregate)
                self.assertIn("oracle_method_id", aggregate)
        self.assertIn("self_selected_oracle_gap", result["cold_start"])

    def test_collapse_detection_and_frontier_summary(self) -> None:
        real = {
            "criterion_rate": 0.0,
            "mean_bit_accuracy": 0.53,
            "mean_exact_match_rate": 0.08,
        }
        nn = {
            "method_id": "gru",
            "mean_bit_accuracy": 0.67,
            "mean_exact_match_rate": 0.26,
        }
        self.assertTrue(collapse_flag(real, [nn]))

        frontier = frontier_summary(
            [
                {
                    "benchmark_id": "A1",
                    "family_id": "A",
                    "family_order": 0,
                    "difficulty_index": 1,
                    "best_nn_method_id": "mlp-explicit",
                    "all_real_collapsed": False,
                },
                {
                    "benchmark_id": "A2",
                    "family_id": "A",
                    "family_order": 0,
                    "difficulty_index": 2,
                    "best_nn_method_id": "gru",
                    "all_real_collapsed": True,
                },
                {
                    "benchmark_id": "A3",
                    "family_id": "A",
                    "family_order": 0,
                    "difficulty_index": 3,
                    "best_nn_method_id": "gru",
                    "all_real_collapsed": True,
                },
            ]
        )
        self.assertEqual(frontier["earliest_global_ceiling"], "A2")
        self.assertEqual(frontier["families"]["A"]["ceiling_band"], "A2")
        self.assertEqual(frontier["families"]["A"]["last_pre_collapse"], "A1")

    def test_real_smoke_easy_and_hard_points(self) -> None:
        suite = benchmark_suite_by_id()

        easy = _run_real_method(point=suite["A1"], task_key="task_a", method_id="fixed-visible", seed=13)
        hard = _run_real_method(point=suite["C4"], task_key="task_a", method_id="fixed-visible", seed=13)

        self.assertEqual(easy["method_id"], "fixed-visible")
        self.assertEqual(easy["benchmark_id"], "A1")
        self.assertGreaterEqual(easy["expected_examples"], 18)
        self.assertEqual(hard["benchmark_id"], "C4")
        self.assertGreaterEqual(hard["expected_examples"], 216)

    def test_growth_visible_scale_smoke_does_not_crash(self) -> None:
        suite = benchmark_suite_by_id()

        result = _run_real_method(point=suite["A3"], task_key="task_a", method_id="growth-visible", seed=13)

        self.assertEqual(result["benchmark_id"], "A3")
        self.assertEqual(result["method_id"], "growth-visible")
        self.assertGreaterEqual(result["expected_examples"], 108)

    def test_self_selected_smoke_reports_policy(self) -> None:
        suite = benchmark_suite_by_id()

        result = _run_real_method(point=suite["A1"], task_key="task_a", method_id="self-selected", seed=13)

        self.assertEqual(result["benchmark_id"], "A1")
        self.assertEqual(result["method_id"], "self-selected")
        self.assertEqual(result["capability_policy"], "self-selected")

    def test_self_selected_lightweight_harness_returns_oracle_gap(self) -> None:
        result = evaluate_self_selected_smoke(
            benchmark_ids=("A1",),
            task_keys=("task_a",),
            seeds=(13,),
        )

        self.assertEqual(result["benchmark_ids"], ["A1"])
        self.assertEqual(result["task_keys"], ["task_a"])
        self.assertEqual(result["aggregate"]["point_count"], 1)
        self.assertIn("mean_self_selected_oracle_gap", result["aggregate"])
        self.assertEqual(result["results"][0]["benchmark_id"], "A1")
        method_ids = [item["method_id"] for item in result["results"][0]["methods"]]
        self.assertIn("self-selected", method_ids)

    @unittest.skipUnless(torch_available(), "PyTorch is not installed")
    def test_torch_smoke_easy_and_hard_points(self) -> None:
        suite = benchmark_suite_by_id()

        easy = _run_nn_method(point=suite["A1"], task_key="task_a", method_id="gru", seed=13)
        hard = _run_nn_method(point=suite["C4"], task_key="task_a", method_id="gru", seed=13)

        self.assertEqual(easy["method_id"], "gru")
        self.assertEqual(easy["benchmark_id"], "A1")
        self.assertEqual(hard["benchmark_id"], "C4")

    def test_neural_baseline_regression_surface_still_runs(self) -> None:
        examples = cvt1_stage1_examples("task_b")
        result = run_mlp_explicit(examples, seed=13, hidden=8)

        self.assertEqual(result.variant, "mlp-explicit")
        self.assertEqual(result.task_id, "task_b")
        self.assertEqual(len(result.per_example_exact), len(examples))


if __name__ == "__main__":
    unittest.main()
