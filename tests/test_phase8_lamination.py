from __future__ import annotations

import unittest

from phase8 import (
    Phase8SliceRunner,
    build_system_for_scenario,
)
from real_core import RegulatorySignal
from scripts.compare_b_scale_suite import b_scale_suite_by_id
from scripts.evaluate_laminated_phase8 import evaluate_laminated_benchmark


class TestPhase8Lamination(unittest.TestCase):
    def test_phase8_slice_runner_produces_compact_b2_summary(self) -> None:
        case = b_scale_suite_by_id()["B2S1"]
        scenario = case.tasks["task_a"].visible_scenario
        system = build_system_for_scenario(
            scenario,
            seed=13,
            capability_policy="self-selected",
        )
        runner = Phase8SliceRunner(
            system,
            scenario,
            benchmark_family="B",
            task_key="task_a",
        )

        summary = runner.run_slice(slice_id=1, cycle_budget=4)

        self.assertEqual(summary.benchmark_family, "B")
        self.assertEqual(summary.task_key, "task_a")
        self.assertEqual(summary.slice_id, 1)
        self.assertEqual(summary.slice_budget, 4)
        self.assertLessEqual(summary.mean_uncertainty, 1.0)
        self.assertGreaterEqual(summary.ambiguity_level, 0.0)
        self.assertGreaterEqual(summary.conflict_level, 0.0)
        self.assertIn("total_action_cost", summary.cost_summary)
        self.assertNotIn("episodic_entries", summary.metadata)

    def test_carryover_filter_drop_clears_prior_episodic_entries_before_next_slice(self) -> None:
        case = b_scale_suite_by_id()["B2S1"]
        scenario = case.tasks["task_a"].visible_scenario
        system = build_system_for_scenario(
            scenario,
            seed=13,
            capability_policy="self-selected",
        )
        runner = Phase8SliceRunner(
            system,
            scenario,
            benchmark_family="B",
            task_key="task_a",
        )

        first = runner.run_slice(slice_id=1, cycle_budget=4)
        self.assertEqual(first.cycles_used, 4)

        runner.run_slice(
            slice_id=2,
            cycle_budget=4,
            regulatory_signal=RegulatorySignal(carryover_filter_mode="drop"),
        )

        for agent in system.agents.values():
            self.assertTrue(all(entry.cycle > 4 for entry in agent.engine.memory.entries))

    def test_evaluate_laminated_benchmark_returns_baseline_and_slice_history(self) -> None:
        result = evaluate_laminated_benchmark(
            benchmark_id="B2S1",
            task_key="task_a",
            mode="visible",
            seed=13,
            capability_policy="self-selected",
            max_slices=3,
            initial_cycle_budget=4,
        )

        self.assertEqual(result["benchmark_id"], "B2S1")
        self.assertIn("baseline_summary", result)
        self.assertIn("laminated_summary", result)
        self.assertIn("laminated_run", result)
        self.assertGreaterEqual(len(result["laminated_run"]["slice_summaries"]), 1)
        self.assertIn(
            result["laminated_run"]["final_decision"],
            {"continue", "settle", "branch", "escalate"},
        )
