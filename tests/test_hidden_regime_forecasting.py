from __future__ import annotations

import unittest

from phase8.environment import _expected_transform_for_task, _sequence_context_estimate_for_task
from phase8.hidden_regime import hidden_regime_suite_by_id
from scripts.evaluate_hidden_regime_forecasting import _auto_output_path, evaluate_hidden_regime_benchmark


class TestHiddenRegimeForecasting(unittest.TestCase):
    def test_hidden_regime_suite_builds_hidden_and_visible_scenarios(self) -> None:
        suite = hidden_regime_suite_by_id()
        self.assertIn("HR1", suite)
        self.assertIn("HR3", suite)
        self.assertIn("HR4", suite)

        hr2 = suite["HR2"]
        self.assertEqual(hr2.sequence_memory_window, 3)
        task = hr2.tasks["task_a"]
        self.assertTrue(task.task_id.startswith("hidden_regime_hr2_"))
        self.assertEqual(task.visible_scenario.initial_signal_specs[0].context_bit, 0)
        self.assertIsNone(task.hidden_scenario.initial_signal_specs[0].context_bit)

        hr4 = suite["HR4"].tasks["task_a"]
        visible_schedule = hr4.visible_scenario.signal_schedule_specs or {}
        task_ids = {spec[0].task_id for spec in visible_schedule.values() if spec}
        self.assertTrue(any("phase1" in str(task_id) for task_id in task_ids))
        self.assertTrue(any("phase2" in str(task_id) for task_id in task_ids))

    def test_hidden_regime_task_ids_bind_sequence_context_and_expected_transform(self) -> None:
        estimate, confidence = _sequence_context_estimate_for_task(
            "hidden_regime_hr2_task_a",
            prior_parities=[1, 0, 1],
        )
        self.assertEqual(estimate, 0)
        self.assertGreater(confidence, 0.9)
        self.assertEqual(
            _expected_transform_for_task("hidden_regime_hr2_task_a", estimate),
            "rotate_left_1",
        )

        quad_estimate, quad_confidence = _sequence_context_estimate_for_task(
            "hidden_regime_hr3_task_c",
            prior_parities=[0, 1],
        )
        self.assertEqual(quad_estimate, 1)
        self.assertGreater(quad_confidence, 0.9)
        self.assertEqual(
            _expected_transform_for_task("hidden_regime_hr3_task_c", 3),
            "identity",
        )

    def test_evaluate_hidden_regime_benchmark_returns_forecast_metrics(self) -> None:
        result = evaluate_hidden_regime_benchmark(
            benchmark_id="HR1",
            task_key="task_a",
            observable="hidden",
            seed=13,
            capability_policy="self-selected",
            initial_cycle_budget=4,
            safety_limit=8,
            regulator_type="real",
        )

        self.assertEqual(result["benchmark_id"], "HR1")
        self.assertEqual(result["observable"], "hidden")
        self.assertEqual(result["capability_policy"], "self-selected")
        self.assertIn("case", result)
        self.assertIn("laminated_run", result)
        self.assertGreaterEqual(len(result["laminated_run"]["slice_summaries"]), 1)

        first_summary = result["laminated_run"]["slice_summaries"][0]
        self.assertIn("forecast_metrics", first_summary["metadata"])
        self.assertIn("intervention_payoff_trend", first_summary["metadata"])
        self.assertIn(
            result["laminated_run"]["final_decision"],
            {"continue", "settle", "branch", "escalate"},
        )

    def test_evaluate_hidden_regime_shift_benchmark_returns_case_metadata(self) -> None:
        result = evaluate_hidden_regime_benchmark(
            benchmark_id="HR4",
            task_key="task_b",
            observable="hidden",
            seed=13,
            capability_policy="self-selected",
            initial_cycle_budget=4,
            safety_limit=8,
            regulator_type="real",
        )

        self.assertEqual(result["benchmark_id"], "HR4")
        self.assertEqual(result["case"]["sequence_memory_window"], 3)
        self.assertEqual(result["case"]["regime_cardinality"], 2)
        self.assertGreaterEqual(len(result["laminated_run"]["slice_summaries"]), 1)

    def test_hidden_regime_output_path_uses_unique_run_stamp(self) -> None:
        path = _auto_output_path(
            benchmark_id="HR2",
            task_key="task_c",
            observable="hidden",
            capability_policy="self-selected",
            seed=13,
            initial_cycle_budget=8,
            safety_limit=30,
            accuracy_threshold=0.0,
            regulator_type="real",
            run_stamp="20260326_133015_123456",
        )

        self.assertIn("20260326_133015_123456_hidden_regime_hr2_task_c_hidden", path.name)
        self.assertIn("_b8_s30", path.name)
        self.assertTrue(path.name.endswith("_seed13.json"))


if __name__ == "__main__":
    unittest.main()
