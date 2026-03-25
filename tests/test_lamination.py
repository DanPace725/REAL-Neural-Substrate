from __future__ import annotations

import unittest
from dataclasses import replace

from real_core import (
    HeuristicSliceRegulator,
    LaminatedController,
    SessionCarryover,
    SettlementDecision,
    SliceSummary,
)


class ScriptedRunner:
    def __init__(self, summaries: list[SliceSummary]) -> None:
        self._summaries = list(summaries)
        self.budgets: list[int] = []

    def run_slice(self, *, slice_id: int, cycle_budget: int, regulatory_signal=None) -> SliceSummary:
        self.budgets.append(cycle_budget)
        template = self._summaries.pop(0)
        return replace(template, slice_id=slice_id, slice_budget=cycle_budget)


class TestLaminationContracts(unittest.TestCase):
    def test_slice_summary_rejects_raw_session_carryover(self) -> None:
        with self.assertRaises(TypeError):
            SliceSummary(
                slice_id=1,
                slice_budget=4,
                cycles_used=4,
                examples_seen=2,
                metadata={"carryover": SessionCarryover()},
            )

    def test_controller_settles_on_flat_low_conflict_history(self) -> None:
        runner = ScriptedRunner(
            [
                SliceSummary(
                    slice_id=1,
                    slice_budget=4,
                    cycles_used=4,
                    examples_seen=2,
                    mean_coherence=0.62,
                    final_coherence=0.64,
                    coherence_delta=0.01,
                    mean_uncertainty=0.22,
                    ambiguity_level=0.1,
                    conflict_level=0.1,
                ),
                SliceSummary(
                    slice_id=2,
                    slice_budget=4,
                    cycles_used=4,
                    examples_seen=2,
                    mean_coherence=0.63,
                    final_coherence=0.64,
                    coherence_delta=0.01,
                    mean_uncertainty=0.2,
                    ambiguity_level=0.1,
                    conflict_level=0.1,
                ),
            ]
        )
        controller = LaminatedController(
            runner,
            regulator=HeuristicSliceRegulator(),
            initial_cycle_budget=4,
        )

        result = controller.run()

        self.assertEqual(result.final_decision, SettlementDecision.SETTLE)
        self.assertEqual(len(result.summaries), 2)

    def test_controller_escalates_on_flat_high_conflict_history(self) -> None:
        runner = ScriptedRunner(
            [
                SliceSummary(
                    slice_id=1,
                    slice_budget=4,
                    cycles_used=4,
                    examples_seen=2,
                    mean_coherence=0.5,
                    final_coherence=0.5,
                    coherence_delta=0.0,
                    mean_uncertainty=0.8,
                    ambiguity_level=0.7,
                    conflict_level=0.6,
                ),
                SliceSummary(
                    slice_id=2,
                    slice_budget=4,
                    cycles_used=4,
                    examples_seen=2,
                    mean_coherence=0.5,
                    final_coherence=0.5,
                    coherence_delta=0.0,
                    mean_uncertainty=0.82,
                    ambiguity_level=0.7,
                    conflict_level=0.6,
                ),
            ]
        )
        controller = LaminatedController(
            runner,
            regulator=HeuristicSliceRegulator(),
            initial_cycle_budget=4,
        )

        result = controller.run()

        self.assertEqual(result.final_decision, SettlementDecision.ESCALATE)
        self.assertEqual(len(result.summaries), 2)

    def test_controller_settles_on_productive_tapering_history(self) -> None:
        runner = ScriptedRunner(
            [
                SliceSummary(
                    slice_id=1,
                    slice_budget=6,
                    cycles_used=6,
                    examples_seen=6,
                    mean_coherence=0.66,
                    final_coherence=0.7,
                    coherence_delta=0.015,
                    mean_uncertainty=0.71,
                    ambiguity_level=1.0,
                    conflict_level=0.48,
                    guidance_alignment=0.75,
                    cost_summary={
                        "exact_matches": 3.0,
                        "partial_matches": 4.0,
                        "bit_accuracy_per_cost": 0.26,
                    },
                    metadata={"mean_bit_accuracy": 0.625},
                ),
                SliceSummary(
                    slice_id=2,
                    slice_budget=8,
                    cycles_used=8,
                    examples_seen=4,
                    mean_coherence=0.7,
                    final_coherence=0.72,
                    coherence_delta=0.003,
                    mean_uncertainty=0.74,
                    ambiguity_level=1.0,
                    conflict_level=0.55,
                    guidance_alignment=0.0,
                    cost_summary={
                        "exact_matches": 1.0,
                        "partial_matches": 3.0,
                        "bit_accuracy_per_cost": 0.35,
                    },
                    metadata={"mean_bit_accuracy": 0.625},
                ),
            ]
        )
        controller = LaminatedController(
            runner,
            regulator=HeuristicSliceRegulator(),
            initial_cycle_budget=6,
        )

        result = controller.run()

        self.assertEqual(result.final_decision, SettlementDecision.SETTLE)
        self.assertEqual(len(result.summaries), 2)
