from __future__ import annotations

import unittest
from dataclasses import replace

from real_core import (
    GradientSliceRegulator,
    HeuristicSliceRegulator,
    LaminatedController,
    LearningSliceRegulator,
    RegulatorySignal,
    SliceAccuracyCoherenceModel,
    SliceExecutionPlan,
    SliceSummaryObservationAdapter,
    REALSliceRegulator,
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


class AdaptiveScriptedRunner:
    def __init__(self) -> None:
        self.state = "initial"
        self.plan_budgets: list[int] = []

    def run_slice_plan(
        self,
        *,
        slice_id: int,
        execution_plan: SliceExecutionPlan,
        regulatory_signal=None,
    ) -> SliceSummary:
        hard_cap = int(execution_plan.hard_cap)
        self.plan_budgets.append(hard_cap)
        if slice_id == 1:
            self.state = "after-initial"
            return SliceSummary(
                slice_id=1,
                slice_budget=hard_cap,
                cycles_used=min(hard_cap, 4),
                examples_seen=4,
                conflict_level=0.45,
                ambiguity_level=0.35,
                coherence_delta=0.0,
                mean_uncertainty=0.55,
                context_accuracy={"context_0": 0.15, "context_1": 0.85},
                metadata={
                    "final_accuracy": 0.50,
                    "floor_accuracy": 0.15,
                    "mean_provisional_context_ambiguity": 0.08,
                    "mean_transform_commitment_margin": 0.62,
                },
            )
        if hard_cap <= 3:
            floor = 0.45
            final = 0.98
            self.state = "after-short"
        elif hard_cap <= 5:
            floor = 0.40
            final = 0.72
            self.state = "after-base"
        else:
            floor = 1.00
            final = 1.00
            self.state = "after-long"
        return SliceSummary(
            slice_id=slice_id,
            slice_budget=hard_cap,
            cycles_used=hard_cap,
            examples_seen=hard_cap,
            conflict_level=0.18,
            ambiguity_level=0.10,
            coherence_delta=0.04,
            mean_uncertainty=0.22,
            context_accuracy={"context_0": floor, "context_1": final},
            metadata={
                "final_accuracy": final,
                "floor_accuracy": floor,
                "mean_provisional_context_ambiguity": 0.07,
                "mean_transform_commitment_margin": 0.44,
                "total_context_debt": max(0.0, 1.0 - floor),
            },
        )

    def snapshot_fast_state(self) -> dict[str, object]:
        return {"state": self.state}

    def restore_fast_state(self, snapshot: dict[str, object]) -> None:
        self.state = str(snapshot["state"])


class PortfolioRegulator:
    def regulate(self, history: list[SliceSummary]) -> RegulatorySignal:
        if len(history) >= 2:
            return RegulatorySignal(decision_hint=SettlementDecision.SETTLE)
        return RegulatorySignal(
            decision_hint=SettlementDecision.CONTINUE,
            budget_target=4.0,
            pressure_level=0.72,
            hygiene_level=0.58,
            growth_drive=0.35,
            portfolio_drive=0.95,
            settlement_confidence=0.20,
            execution_plan=SliceExecutionPlan(
                initial_budget=4,
                extend_step=2,
                soft_cap=4,
                hard_cap=6,
                early_stop_patience=1,
                metadata={"target_budget": 4},
            ),
            metadata={"regulator_mode": "gradient"},
        )


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

    def test_learning_regulator_reports_positive_intervention_payoff(self) -> None:
        regulator = LearningSliceRegulator(accuracy_threshold=0.8)
        first = SliceSummary(
            slice_id=1,
            slice_budget=6,
            cycles_used=6,
            examples_seen=4,
            conflict_level=0.2,
            ambiguity_level=0.3,
            coherence_delta=0.05,
            mean_uncertainty=0.5,
            context_accuracy={"context_0": 0.50, "context_1": 0.55},
            mode_used="visible",
            metadata={"mean_bit_accuracy": 0.525},
        )
        second = SliceSummary(
            slice_id=2,
            slice_budget=6,
            cycles_used=6,
            examples_seen=4,
            conflict_level=0.2,
            ambiguity_level=0.25,
            coherence_delta=0.06,
            mean_uncertainty=0.45,
            context_accuracy={"context_0": 0.68, "context_1": 0.70},
            mode_used="visible",
            metadata={"mean_bit_accuracy": 0.69},
        )

        regulator.regulate([first])
        signal = regulator.regulate([first, second])

        self.assertEqual(signal.metadata.get("intervention_status"), "improved")
        self.assertGreater(float(signal.metadata.get("intervention_payoff", 0.0)), 0.0)
        self.assertEqual(signal.metadata.get("intervention_target_metric"), "min_ctx_acc")

    def test_heuristic_regulator_authorizes_growth_from_compact_request_summary(self) -> None:
        regulator = HeuristicSliceRegulator(accuracy_threshold=0.8)
        summary = SliceSummary(
            slice_id=1,
            slice_budget=6,
            cycles_used=6,
            examples_seen=4,
            conflict_level=0.15,
            ambiguity_level=0.2,
            coherence_delta=0.01,
            mean_uncertainty=0.45,
            context_accuracy={"context_0": 0.52, "context_1": 0.58},
            metadata={
                "mean_bit_accuracy": 0.55,
                "growth_request": {
                    "authorization": "auto",
                    "requesting_nodes": 2,
                    "active_growth_nodes": 0,
                    "pending_proposals": 1,
                    "max_pressure": 0.72,
                    "max_readiness": 0.63,
                },
            },
        )

        signal = regulator.regulate([summary])

        self.assertEqual(signal.growth_authorization, "authorize")

    def test_heuristic_regulator_can_initiate_growth_without_fast_request(self) -> None:
        regulator = HeuristicSliceRegulator(accuracy_threshold=0.8)
        summaries = [
            SliceSummary(
                slice_id=1,
                slice_budget=6,
                cycles_used=6,
                examples_seen=4,
                conflict_level=0.52,
                ambiguity_level=0.38,
                coherence_delta=0.0,
                mean_uncertainty=0.46,
                context_accuracy={"context_0": 0.34, "context_1": 0.82},
                metadata={
                    "final_accuracy": 0.58,
                    "mean_bit_accuracy": 0.58,
                    "growth_request": {
                        "authorization": "auto",
                        "requesting_nodes": 0,
                        "active_growth_nodes": 0,
                        "pending_proposals": 0,
                        "max_pressure": 0.05,
                        "max_readiness": 0.52,
                    },
                    "applied_carryover_filter_mode": "drop",
                    "mean_provisional_context_ambiguity": 0.04,
                    "mean_transform_commitment_margin": 0.64,
                },
            ),
            SliceSummary(
                slice_id=2,
                slice_budget=6,
                cycles_used=6,
                examples_seen=4,
                conflict_level=0.50,
                ambiguity_level=0.36,
                coherence_delta=0.0,
                mean_uncertainty=0.48,
                context_accuracy={"context_0": 0.32, "context_1": 0.84},
                metadata={
                    "final_accuracy": 0.57,
                    "mean_bit_accuracy": 0.57,
                    "growth_request": {
                        "authorization": "auto",
                        "requesting_nodes": 0,
                        "active_growth_nodes": 0,
                        "pending_proposals": 0,
                        "max_pressure": 0.04,
                        "max_readiness": 0.5,
                    },
                    "applied_carryover_filter_mode": "drop",
                    "mean_provisional_context_ambiguity": 0.03,
                    "mean_transform_commitment_margin": 0.66,
                },
            ),
            SliceSummary(
                slice_id=3,
                slice_budget=6,
                cycles_used=6,
                examples_seen=4,
                conflict_level=0.53,
                ambiguity_level=0.35,
                coherence_delta=0.0,
                mean_uncertainty=0.47,
                context_accuracy={"context_0": 0.30, "context_1": 0.83},
                metadata={
                    "final_accuracy": 0.56,
                    "mean_bit_accuracy": 0.56,
                    "growth_request": {
                        "authorization": "auto",
                        "requesting_nodes": 0,
                        "active_growth_nodes": 0,
                        "pending_proposals": 0,
                        "max_pressure": 0.03,
                        "max_readiness": 0.49,
                    },
                    "applied_carryover_filter_mode": "drop",
                    "mean_provisional_context_ambiguity": 0.02,
                    "mean_transform_commitment_margin": 0.68,
                },
            ),
        ]

        signal = regulator.regulate(summaries)

        self.assertEqual(signal.growth_authorization, "initiate")

    def test_observation_adapter_surfaces_context_asymmetry_features(self) -> None:
        adapter = SliceSummaryObservationAdapter()
        summary = SliceSummary(
            slice_id=1,
            slice_budget=6,
            cycles_used=6,
            examples_seen=4,
            context_accuracy={"context_0": 0.0, "context_1": 1.0},
            metadata={"final_accuracy": 0.5, "mean_bit_accuracy": 0.5},
        )

        adapter.update(
            summary,
            context_debt_summary={
                "max_context_debt": 1.4,
                "total_context_debt": 1.4,
                "open_context_count": 1.0,
                "max_context_credit": 0.2,
            },
        )
        observed = adapter.observe(1)

        self.assertEqual(observed["best_ctx_acc"], 1.0)
        self.assertEqual(observed["worst_ctx_acc"], 0.0)
        self.assertEqual(observed["context_accuracy_spread"], 1.0)
        self.assertEqual(observed["asymmetric_context_collapse"], 1.0)
        self.assertEqual(observed["floor_accuracy"], 0.0)
        self.assertEqual(observed["max_context_debt"], 1.4)
        self.assertEqual(observed["open_context_count"], 1.0)

    def test_coherence_model_penalizes_asymmetric_context_collapse(self) -> None:
        model = SliceAccuracyCoherenceModel(accuracy_threshold=0.8)

        balanced = model.score(
            {
                "min_ctx_acc": 0.5,
                "delta_min_ctx_acc": 0.0,
                "conflict": 0.1,
                "ambiguity": 0.1,
                "context_accuracy_spread": 0.1,
                "asymmetric_context_collapse": 0.0,
            },
            [],
        )
        collapsed = model.score(
            {
                "min_ctx_acc": 0.0,
                "delta_min_ctx_acc": 0.0,
                "conflict": 0.1,
                "ambiguity": 0.1,
                "context_accuracy_spread": 1.0,
                "asymmetric_context_collapse": 1.0,
            },
            [],
        )

        self.assertGreater(balanced["context_balance"], collapsed["context_balance"])

    def test_controller_does_not_settle_on_aggregate_threshold_when_floor_fails(self) -> None:
        runner = ScriptedRunner(
            [
                SliceSummary(
                    slice_id=1,
                    slice_budget=6,
                    cycles_used=6,
                    examples_seen=4,
                    mean_coherence=0.7,
                    final_coherence=0.72,
                    coherence_delta=0.01,
                    mean_uncertainty=0.35,
                    ambiguity_level=0.2,
                    conflict_level=0.2,
                    context_accuracy={"context_0": 0.55, "context_1": 1.0},
                    metadata={"final_accuracy": 0.81, "mean_bit_accuracy": 0.81},
                ),
                SliceSummary(
                    slice_id=2,
                    slice_budget=6,
                    cycles_used=6,
                    examples_seen=4,
                    mean_coherence=0.72,
                    final_coherence=0.74,
                    coherence_delta=0.01,
                    mean_uncertainty=0.3,
                    ambiguity_level=0.18,
                    conflict_level=0.18,
                    context_accuracy={"context_0": 0.57, "context_1": 1.0},
                    metadata={"final_accuracy": 0.83, "mean_bit_accuracy": 0.83},
                ),
            ]
        )
        controller = LaminatedController(
            runner,
            regulator=HeuristicSliceRegulator(accuracy_threshold=0.8),
            initial_cycle_budget=6,
            safety_limit=2,
        )

        result = controller.run()

        self.assertEqual(result.final_decision, SettlementDecision.CONTINUE)

    def test_controller_settles_only_when_floor_and_aggregate_thresholds_pass(self) -> None:
        runner = ScriptedRunner(
            [
                SliceSummary(
                    slice_id=1,
                    slice_budget=6,
                    cycles_used=6,
                    examples_seen=4,
                    mean_coherence=0.7,
                    final_coherence=0.72,
                    coherence_delta=0.01,
                    mean_uncertainty=0.35,
                    ambiguity_level=0.2,
                    conflict_level=0.2,
                    context_accuracy={"context_0": 0.81, "context_1": 0.9},
                    metadata={"final_accuracy": 0.86, "mean_bit_accuracy": 0.86},
                ),
                SliceSummary(
                    slice_id=2,
                    slice_budget=6,
                    cycles_used=6,
                    examples_seen=4,
                    mean_coherence=0.72,
                    final_coherence=0.74,
                    coherence_delta=0.01,
                    mean_uncertainty=0.3,
                    ambiguity_level=0.18,
                    conflict_level=0.18,
                    context_accuracy={"context_0": 0.83, "context_1": 0.91},
                    metadata={"final_accuracy": 0.87, "mean_bit_accuracy": 0.87},
                ),
            ]
        )
        controller = LaminatedController(
            runner,
            regulator=HeuristicSliceRegulator(accuracy_threshold=0.8),
            initial_cycle_budget=6,
        )

        result = controller.run()

        self.assertEqual(result.final_decision, SettlementDecision.SETTLE)

    def test_heuristic_regulator_triggers_differentiation_reframe_on_persistent_asymmetry(self) -> None:
        regulator = HeuristicSliceRegulator(accuracy_threshold=0.8)
        first = SliceSummary(
            slice_id=1,
            slice_budget=8,
            cycles_used=8,
            examples_seen=4,
            conflict_level=0.2,
            ambiguity_level=0.4,
            coherence_delta=0.01,
            mean_uncertainty=0.45,
            context_accuracy={"context_0": 0.0, "context_1": 1.0},
            metadata={"final_accuracy": 0.5, "mean_bit_accuracy": 0.5},
        )
        second = SliceSummary(
            slice_id=2,
            slice_budget=10,
            cycles_used=10,
            examples_seen=4,
            conflict_level=0.18,
            ambiguity_level=0.35,
            coherence_delta=0.0,
            mean_uncertainty=0.48,
            context_accuracy={"context_0": 0.05, "context_1": 0.95},
            metadata={"final_accuracy": 0.5, "mean_bit_accuracy": 0.5},
        )

        signal = regulator.regulate([first, second])

        self.assertEqual(signal.reframe_flags.get("context_differentiation"), 1.0)
        self.assertEqual(signal.reset_flags.get("episodic"), 1.0)
        self.assertEqual(signal.carryover_filter_mode, "drop")
        self.assertEqual(signal.context_pressure, "high")
        self.assertEqual(signal.growth_authorization, "hold")
        self.assertGreater(float(signal.bias_updates.get("max_context_debt", 0.0)), 1.0)
        self.assertEqual(float(signal.bias_updates.get("open_context_count", 0.0)), 1.0)

    def test_heuristic_regulator_escalates_after_repeated_failed_hygiene(self) -> None:
        regulator = HeuristicSliceRegulator(accuracy_threshold=0.8)
        summaries = [
            SliceSummary(
                slice_id=1,
                slice_budget=8,
                cycles_used=8,
                examples_seen=4,
                conflict_level=0.55,
                ambiguity_level=0.45,
                coherence_delta=0.0,
                mean_uncertainty=0.4,
                context_accuracy={"context_0": 0.15, "context_1": 0.82},
                metadata={
                    "final_accuracy": 0.485,
                    "mean_bit_accuracy": 0.485,
                    "applied_carryover_filter_mode": "drop",
                    "mean_provisional_context_ambiguity": 0.03,
                    "mean_transform_commitment_margin": 0.63,
                },
            ),
            SliceSummary(
                slice_id=2,
                slice_budget=8,
                cycles_used=8,
                examples_seen=4,
                conflict_level=0.52,
                ambiguity_level=0.42,
                coherence_delta=0.0,
                mean_uncertainty=0.42,
                context_accuracy={"context_0": 0.12, "context_1": 0.85},
                metadata={
                    "final_accuracy": 0.485,
                    "mean_bit_accuracy": 0.485,
                    "applied_carryover_filter_mode": "drop",
                    "mean_provisional_context_ambiguity": 0.02,
                    "mean_transform_commitment_margin": 0.68,
                },
            ),
            SliceSummary(
                slice_id=3,
                slice_budget=8,
                cycles_used=8,
                examples_seen=4,
                conflict_level=0.50,
                ambiguity_level=0.40,
                coherence_delta=0.0,
                mean_uncertainty=0.43,
                context_accuracy={"context_0": 0.10, "context_1": 0.84},
                metadata={
                    "final_accuracy": 0.47,
                    "mean_bit_accuracy": 0.47,
                    "applied_carryover_filter_mode": "soften",
                    "mean_provisional_context_ambiguity": 0.01,
                    "mean_transform_commitment_margin": 0.71,
                },
            ),
        ]

        signal = regulator.regulate(summaries)

        self.assertEqual(signal.reframe_flags.get("context_differentiation"), 1.0)
        self.assertEqual(signal.reset_flags.get("episodic"), 1.0)
        self.assertEqual(signal.carryover_filter_mode, "drop")
        self.assertEqual(signal.context_pressure, "high")
        self.assertEqual(signal.growth_authorization, "hold")
        self.assertEqual(signal.stop_reason, "failed_hygiene_recovery")
        self.assertEqual(signal.bias_updates.get("failed_hygiene_reframe"), 1.0)

    def test_real_slice_regulator_reports_negative_intervention_payoff(self) -> None:
        regulator = REALSliceRegulator(accuracy_threshold=0.8)
        first = SliceSummary(
            slice_id=1,
            slice_budget=6,
            cycles_used=6,
            examples_seen=4,
            conflict_level=0.2,
            ambiguity_level=0.3,
            coherence_delta=0.05,
            mean_uncertainty=0.5,
            context_accuracy={"context_0": 0.72, "context_1": 0.68},
            mode_used="visible",
            metadata={"mean_bit_accuracy": 0.70},
        )
        second = SliceSummary(
            slice_id=2,
            slice_budget=6,
            cycles_used=6,
            examples_seen=4,
            conflict_level=0.3,
            ambiguity_level=0.35,
            coherence_delta=-0.02,
            mean_uncertainty=0.6,
            context_accuracy={"context_0": 0.60, "context_1": 0.58},
            mode_used="visible",
            metadata={"mean_bit_accuracy": 0.59},
        )

        regulator.regulate([first])
        signal = regulator.regulate([first, second])

        self.assertEqual(signal.metadata.get("intervention_status"), "worsened")
        self.assertLess(float(signal.metadata.get("intervention_payoff", 0.0)), 0.0)
        self.assertIsInstance(signal.metadata.get("intervention_policy"), str)

    def test_real_slice_regulator_requires_floor_and_aggregate_thresholds_to_settle(self) -> None:
        regulator = REALSliceRegulator(accuracy_threshold=0.8)
        first = SliceSummary(
            slice_id=1,
            slice_budget=6,
            cycles_used=6,
            examples_seen=4,
            conflict_level=0.2,
            ambiguity_level=0.2,
            coherence_delta=0.04,
            mean_uncertainty=0.35,
            context_accuracy={"context_0": 0.56, "context_1": 1.0},
            mode_used="visible",
            metadata={"final_accuracy": 0.81, "mean_bit_accuracy": 0.81},
        )
        second = SliceSummary(
            slice_id=2,
            slice_budget=6,
            cycles_used=6,
            examples_seen=4,
            conflict_level=0.18,
            ambiguity_level=0.18,
            coherence_delta=0.03,
            mean_uncertainty=0.3,
            context_accuracy={"context_0": 0.58, "context_1": 1.0},
            mode_used="visible",
            metadata={"final_accuracy": 0.84, "mean_bit_accuracy": 0.84},
        )

        first_signal = regulator.regulate([first])
        second_signal = regulator.regulate([first, second])

        self.assertEqual(first_signal.decision_hint, SettlementDecision.CONTINUE)
        self.assertEqual(second_signal.decision_hint, SettlementDecision.CONTINUE)

    def test_real_slice_regulator_settles_when_floor_and_aggregate_thresholds_pass(self) -> None:
        regulator = REALSliceRegulator(accuracy_threshold=0.8)
        first = SliceSummary(
            slice_id=1,
            slice_budget=6,
            cycles_used=6,
            examples_seen=4,
            conflict_level=0.2,
            ambiguity_level=0.2,
            coherence_delta=0.04,
            mean_uncertainty=0.35,
            context_accuracy={"context_0": 0.82, "context_1": 0.9},
            mode_used="visible",
            metadata={"final_accuracy": 0.86, "mean_bit_accuracy": 0.86},
        )
        second = SliceSummary(
            slice_id=2,
            slice_budget=6,
            cycles_used=6,
            examples_seen=4,
            conflict_level=0.18,
            ambiguity_level=0.18,
            coherence_delta=0.03,
            mean_uncertainty=0.3,
            context_accuracy={"context_0": 0.84, "context_1": 0.91},
            mode_used="visible",
            metadata={"final_accuracy": 0.88, "mean_bit_accuracy": 0.88},
        )

        first_signal = regulator.regulate([first])
        second_signal = regulator.regulate([first, second])

        self.assertEqual(first_signal.decision_hint, SettlementDecision.CONTINUE)
        self.assertEqual(second_signal.decision_hint, SettlementDecision.SETTLE)

    def test_real_slice_regulator_propagates_differentiation_reframe(self) -> None:
        regulator = REALSliceRegulator(accuracy_threshold=0.8)
        first = SliceSummary(
            slice_id=1,
            slice_budget=8,
            cycles_used=8,
            examples_seen=4,
            conflict_level=0.2,
            ambiguity_level=0.4,
            coherence_delta=0.01,
            mean_uncertainty=0.45,
            context_accuracy={"context_0": 0.0, "context_1": 1.0},
            mode_used="visible",
            metadata={"final_accuracy": 0.5, "mean_bit_accuracy": 0.5},
        )
        second = SliceSummary(
            slice_id=2,
            slice_budget=10,
            cycles_used=10,
            examples_seen=4,
            conflict_level=0.18,
            ambiguity_level=0.35,
            coherence_delta=0.0,
            mean_uncertainty=0.48,
            context_accuracy={"context_0": 0.05, "context_1": 0.95},
            mode_used="visible",
            metadata={"final_accuracy": 0.5, "mean_bit_accuracy": 0.5},
        )

        regulator.regulate([first])
        signal = regulator.regulate([first, second])

        self.assertEqual(signal.reframe_flags.get("context_differentiation"), 1.0)
        self.assertEqual(signal.reset_flags.get("episodic"), 1.0)
        self.assertEqual(signal.carryover_filter_mode, "drop")
        self.assertEqual(signal.context_pressure, "high")
        self.assertEqual(signal.growth_authorization, "hold")
        self.assertEqual(signal.metadata.get("best_debt_context"), "context_0")
        self.assertGreater(float(signal.metadata.get("max_context_debt", 0.0)), 1.0)

    def test_real_slice_regulator_propagates_failed_hygiene_reframe(self) -> None:
        regulator = REALSliceRegulator(accuracy_threshold=0.8)
        summaries = [
            SliceSummary(
                slice_id=1,
                slice_budget=8,
                cycles_used=8,
                examples_seen=4,
                conflict_level=0.55,
                ambiguity_level=0.45,
                coherence_delta=0.0,
                mean_uncertainty=0.4,
                context_accuracy={"context_0": 0.15, "context_1": 0.82},
                mode_used="visible",
                metadata={
                    "final_accuracy": 0.485,
                    "mean_bit_accuracy": 0.485,
                    "applied_carryover_filter_mode": "drop",
                    "mean_provisional_context_ambiguity": 0.03,
                    "mean_transform_commitment_margin": 0.63,
                },
            ),
            SliceSummary(
                slice_id=2,
                slice_budget=8,
                cycles_used=8,
                examples_seen=4,
                conflict_level=0.52,
                ambiguity_level=0.42,
                coherence_delta=0.0,
                mean_uncertainty=0.42,
                context_accuracy={"context_0": 0.12, "context_1": 0.85},
                mode_used="visible",
                metadata={
                    "final_accuracy": 0.485,
                    "mean_bit_accuracy": 0.485,
                    "applied_carryover_filter_mode": "drop",
                    "mean_provisional_context_ambiguity": 0.02,
                    "mean_transform_commitment_margin": 0.68,
                },
            ),
            SliceSummary(
                slice_id=3,
                slice_budget=8,
                cycles_used=8,
                examples_seen=4,
                conflict_level=0.50,
                ambiguity_level=0.40,
                coherence_delta=0.0,
                mean_uncertainty=0.43,
                context_accuracy={"context_0": 0.10, "context_1": 0.84},
                mode_used="visible",
                metadata={
                    "final_accuracy": 0.47,
                    "mean_bit_accuracy": 0.47,
                    "applied_carryover_filter_mode": "soften",
                    "mean_provisional_context_ambiguity": 0.01,
                    "mean_transform_commitment_margin": 0.71,
                },
            ),
        ]

        regulator.regulate(summaries[:1])
        regulator.regulate(summaries[:2])
        signal = regulator.regulate(summaries)

        self.assertEqual(signal.reframe_flags.get("context_differentiation"), 1.0)
        self.assertEqual(signal.reset_flags.get("episodic"), 1.0)
        self.assertEqual(signal.carryover_filter_mode, "drop")
        self.assertEqual(signal.context_pressure, "high")
        self.assertEqual(signal.growth_authorization, "hold")
        self.assertEqual(signal.stop_reason, "failed_hygiene_recovery")

    def test_real_slice_regulator_preserves_heuristic_growth_initiation(self) -> None:
        regulator = REALSliceRegulator(accuracy_threshold=0.8)
        summaries = [
            SliceSummary(
                slice_id=1,
                slice_budget=6,
                cycles_used=6,
                examples_seen=4,
                conflict_level=0.52,
                ambiguity_level=0.38,
                coherence_delta=0.0,
                mean_uncertainty=0.46,
                context_accuracy={"context_0": 0.34, "context_1": 0.82},
                metadata={
                    "final_accuracy": 0.58,
                    "mean_bit_accuracy": 0.58,
                    "growth_request": {
                        "authorization": "auto",
                        "requesting_nodes": 0,
                        "active_growth_nodes": 0,
                        "pending_proposals": 0,
                        "max_pressure": 0.05,
                        "max_readiness": 0.52,
                    },
                    "applied_carryover_filter_mode": "drop",
                    "mean_provisional_context_ambiguity": 0.04,
                    "mean_transform_commitment_margin": 0.64,
                },
            ),
            SliceSummary(
                slice_id=2,
                slice_budget=6,
                cycles_used=6,
                examples_seen=4,
                conflict_level=0.50,
                ambiguity_level=0.36,
                coherence_delta=0.0,
                mean_uncertainty=0.48,
                context_accuracy={"context_0": 0.32, "context_1": 0.84},
                metadata={
                    "final_accuracy": 0.57,
                    "mean_bit_accuracy": 0.57,
                    "growth_request": {
                        "authorization": "auto",
                        "requesting_nodes": 0,
                        "active_growth_nodes": 0,
                        "pending_proposals": 0,
                        "max_pressure": 0.04,
                        "max_readiness": 0.5,
                    },
                    "applied_carryover_filter_mode": "drop",
                    "mean_provisional_context_ambiguity": 0.03,
                    "mean_transform_commitment_margin": 0.66,
                },
            ),
            SliceSummary(
                slice_id=3,
                slice_budget=6,
                cycles_used=6,
                examples_seen=4,
                conflict_level=0.53,
                ambiguity_level=0.35,
                coherence_delta=0.0,
                mean_uncertainty=0.47,
                context_accuracy={"context_0": 0.30, "context_1": 0.83},
                metadata={
                    "final_accuracy": 0.56,
                    "mean_bit_accuracy": 0.56,
                    "growth_request": {
                        "authorization": "auto",
                        "requesting_nodes": 0,
                        "active_growth_nodes": 0,
                        "pending_proposals": 0,
                        "max_pressure": 0.03,
                        "max_readiness": 0.49,
                    },
                    "applied_carryover_filter_mode": "drop",
                    "mean_provisional_context_ambiguity": 0.02,
                    "mean_transform_commitment_margin": 0.68,
                },
            ),
        ]

        signal = regulator.regulate(summaries)

        self.assertGreater(signal.growth_drive, 0.0)
        self.assertIn(signal.growth_authorization, {"hold", "authorize", "initiate"})

    def test_real_slice_regulator_keeps_high_context_pressure_under_open_context_debt(self) -> None:
        regulator = REALSliceRegulator(accuracy_threshold=0.8)
        first = SliceSummary(
            slice_id=1,
            slice_budget=8,
            cycles_used=8,
            examples_seen=4,
            conflict_level=0.15,
            ambiguity_level=0.25,
            coherence_delta=0.02,
            mean_uncertainty=0.35,
            context_accuracy={"context_0": 0.0, "context_1": 0.95},
            mode_used="visible",
            metadata={"final_accuracy": 0.475, "mean_bit_accuracy": 0.475},
        )
        second = SliceSummary(
            slice_id=2,
            slice_budget=8,
            cycles_used=8,
            examples_seen=4,
            conflict_level=0.15,
            ambiguity_level=0.25,
            coherence_delta=0.01,
            mean_uncertainty=0.34,
            context_accuracy={"context_0": 0.3, "context_1": 1.0},
            mode_used="visible",
            metadata={"final_accuracy": 0.65, "mean_bit_accuracy": 0.65},
        )

        regulator.regulate([first])
        signal = regulator.regulate([first, second])

        self.assertIn(signal.context_pressure, {"medium", "high"})
        self.assertGreater(signal.pressure_level, 0.0)
        self.assertEqual(signal.metadata.get("best_debt_context"), "context_0")
        self.assertGreater(float(signal.metadata.get("max_context_debt", 0.0)), 0.0)

    def test_real_slice_regulator_does_not_settle_below_final_accuracy_threshold(self) -> None:
        regulator = REALSliceRegulator(accuracy_threshold=0.8)
        first = SliceSummary(
            slice_id=1,
            slice_budget=6,
            cycles_used=6,
            examples_seen=4,
            conflict_level=0.12,
            ambiguity_level=0.12,
            coherence_delta=0.03,
            mean_uncertainty=0.28,
            context_accuracy={"context_0": 0.78, "context_1": 0.79},
            mode_used="visible",
            metadata={"final_accuracy": 0.786, "mean_bit_accuracy": 0.786},
        )
        second = SliceSummary(
            slice_id=2,
            slice_budget=6,
            cycles_used=6,
            examples_seen=4,
            conflict_level=0.1,
            ambiguity_level=0.1,
            coherence_delta=0.02,
            mean_uncertainty=0.25,
            context_accuracy={"context_0": 0.78, "context_1": 0.79},
            mode_used="visible",
            metadata={"final_accuracy": 0.786, "mean_bit_accuracy": 0.786},
        )

        regulator.regulate([first])
        signal = regulator.regulate([first, second])

        self.assertEqual(signal.decision_hint, SettlementDecision.CONTINUE)

    def test_learning_regulator_keeps_growth_control_compact(self) -> None:
        regulator = LearningSliceRegulator(accuracy_threshold=0.8)
        summary = SliceSummary(
            slice_id=1,
            slice_budget=6,
            cycles_used=6,
            examples_seen=4,
            conflict_level=0.2,
            ambiguity_level=0.25,
            coherence_delta=0.02,
            mean_uncertainty=0.4,
            context_accuracy={"context_0": 0.48, "context_1": 0.5},
            mode_used="visible",
            metadata={
                "mean_bit_accuracy": 0.49,
                "growth_request": {
                    "authorization": "auto",
                    "requesting_nodes": 1,
                    "active_growth_nodes": 0,
                    "pending_proposals": 1,
                    "max_pressure": 0.68,
                    "max_readiness": 0.61,
                },
            },
        )

        signal = regulator.regulate([summary])

        self.assertIsNone(signal.capability_mode)
        self.assertIn(signal.growth_authorization, {"authorize", "hold", "initiate", None})

    def test_gradient_regulator_emits_continuous_control_vector(self) -> None:
        regulator = GradientSliceRegulator(accuracy_threshold=0.8)
        history = [
            SliceSummary(
                slice_id=1,
                slice_budget=6,
                cycles_used=6,
                examples_seen=4,
                conflict_level=0.4,
                ambiguity_level=0.3,
                coherence_delta=0.0,
                mean_uncertainty=0.5,
                context_accuracy={"context_0": 0.20, "context_1": 0.72},
                metadata={
                    "final_accuracy": 0.46,
                    "floor_accuracy": 0.20,
                    "mean_provisional_context_ambiguity": 0.04,
                    "mean_transform_commitment_margin": 0.71,
                    "growth_request": {
                        "authorization": "auto",
                        "requesting_nodes": 0,
                        "active_growth_nodes": 0,
                        "pending_proposals": 0,
                        "max_pressure": 0.08,
                        "max_readiness": 0.40,
                    },
                    "applied_carryover_filter_mode": "drop",
                },
            ),
            SliceSummary(
                slice_id=2,
                slice_budget=6,
                cycles_used=6,
                examples_seen=4,
                conflict_level=0.42,
                ambiguity_level=0.28,
                coherence_delta=0.0,
                mean_uncertainty=0.48,
                context_accuracy={"context_0": 0.24, "context_1": 0.75},
                metadata={
                    "final_accuracy": 0.50,
                    "floor_accuracy": 0.24,
                    "mean_provisional_context_ambiguity": 0.03,
                    "mean_transform_commitment_margin": 0.73,
                    "growth_request": {
                        "authorization": "auto",
                        "requesting_nodes": 0,
                        "active_growth_nodes": 0,
                        "pending_proposals": 0,
                        "max_pressure": 0.05,
                        "max_readiness": 0.42,
                    },
                    "applied_carryover_filter_mode": "drop",
                },
            ),
        ]

        signal = regulator.regulate(history)

        self.assertGreater(signal.budget_target or 0.0, 0.0)
        self.assertGreaterEqual(signal.pressure_level, 0.0)
        self.assertLessEqual(signal.pressure_level, 1.0)
        self.assertGreaterEqual(signal.hygiene_level, 0.0)
        self.assertLessEqual(signal.hygiene_level, 1.0)
        self.assertGreaterEqual(signal.portfolio_drive, 0.0)
        self.assertLessEqual(signal.portfolio_drive, 1.0)
        self.assertIsNotNone(signal.execution_plan)
        self.assertEqual(signal.metadata.get("regulator_mode"), "gradient")

    def test_controller_portfolio_prefers_floor_recovery_and_commits_winner_state(self) -> None:
        runner = AdaptiveScriptedRunner()
        controller = LaminatedController(
            runner,
            regulator=PortfolioRegulator(),
            initial_cycle_budget=4,
            safety_limit=3,
        )

        result = controller.run()

        self.assertEqual(result.final_decision, SettlementDecision.SETTLE)
        self.assertEqual(runner.state, "after-long")
        self.assertEqual(result.summaries[-1].metadata.get("portfolio_selected"), "long")
        scores = result.summaries[-1].metadata.get("portfolio_candidate_scores", {})
        self.assertGreater(scores.get("long", 0.0), scores.get("short", 0.0))
