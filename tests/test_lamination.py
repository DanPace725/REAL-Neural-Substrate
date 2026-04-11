from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

import real_core.lamination as lamination_module
from real_core import (
    GradientSliceRegulator,
    HeuristicSliceRegulator,
    LaminatedController,
    LearningSliceRegulator,
    RegulatoryObservation,
    RegulatoryPrimitive,
    RegulatorySubstrate,
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

    def test_heuristic_regulator_settles_on_communicative_preserve_window(self) -> None:
        regulator = HeuristicSliceRegulator()
        history = [
            SliceSummary(
                slice_id=1,
                slice_budget=8,
                cycles_used=8,
                examples_seen=8,
                mean_coherence=0.62,
                final_coherence=0.64,
                coherence_delta=0.06,
                mean_uncertainty=0.48,
                ambiguity_level=0.42,
                conflict_level=0.30,
                context_accuracy={"context_0": 0.56, "context_1": 0.80},
                metadata={
                    "final_accuracy": 0.76,
                    "floor_accuracy": 0.56,
                    "c_task_layer1_mode": "communicative",
                    "c_task_mean_preserve_pressure": 0.74,
                    "c_task_mean_reopen_pressure": 0.12,
                    "c_task_mean_resolution_confidence": 0.60,
                    "c_task_preserve_mode_packet_ratio": 0.52,
                },
            )
        ]

        signal = regulator.regulate(history)

        self.assertEqual(signal.decision_hint, SettlementDecision.SETTLE)

    def test_heuristic_regulator_emits_c_task_regulatory_profile(self) -> None:
        regulator = HeuristicSliceRegulator(accuracy_threshold=0.8)
        history = [
            SliceSummary(
                slice_id=1,
                slice_budget=8,
                cycles_used=8,
                examples_seen=8,
                benchmark_family="C",
                task_key="task_a",
                mean_coherence=0.58,
                final_coherence=0.6,
                coherence_delta=0.01,
                mean_uncertainty=0.55,
                ambiguity_level=0.42,
                conflict_level=0.32,
                context_accuracy={"context_0": 0.54, "context_1": 0.84},
                metadata={
                    "final_accuracy": 0.69,
                    "floor_accuracy": 0.54,
                    "c_task_layer1_mode": "communicative",
                    "c_task_regime_summary": {
                        "packets_evaluated": 12,
                        "context_gap": 0.30,
                        "weak_context_key": "context_0",
                        "weak_context_accuracy": 0.54,
                        "strong_context_key": "context_1",
                        "strong_context_accuracy": 0.84,
                        "context_coverage_ratio": 0.58,
                        "source_context_balance": 0.42,
                        "source_self_hardening_ready_ratio": 0.36,
                        "preserve_hardening_ready_ratio": 0.18,
                        "preserve_identity_action_ratio": 0.61,
                        "low_atp_route_ratio": 0.24,
                        "mean_preserve_pressure": 0.66,
                        "mean_reopen_pressure": 0.03,
                        "mean_resolution_confidence": 0.52,
                        "preserve_mode_packet_ratio": 0.31,
                        "mean_hypothesis_confidence": 0.34,
                        "mean_node_hypothesis_confidence": 0.38,
                        "mean_hypothesis_margin": 0.22,
                        "hypothesis_alignment_ratio": 0.46,
                    },
                },
            )
        ]

        signal = regulator.regulate(history)

        profile = signal.metadata.get("c_task_regulatory_profile", {})
        self.assertIsInstance(profile, dict)
        self.assertGreater(float(profile.get("weak_context_boost", 0.0)), 0.0)
        self.assertLess(float(profile.get("source_hardening_shift", 0.0)), 0.0)
        self.assertGreater(float(profile.get("preserve_hardening_shift", 0.0)), 0.0)
        self.assertLessEqual(float(profile.get("route_cost_scale", 1.0)), 1.0)
        self.assertGreaterEqual(float(profile.get("recovery_scale", 1.0)), 1.0)

    def test_heuristic_regulator_uses_slice_context_accuracy_when_regime_summary_is_misleading(self) -> None:
        regulator = HeuristicSliceRegulator(accuracy_threshold=0.8)
        history = [
            SliceSummary(
                slice_id=1,
                slice_budget=20,
                cycles_used=20,
                examples_seen=20,
                benchmark_family="C",
                task_key="task_a",
                mean_coherence=0.6,
                final_coherence=0.61,
                coherence_delta=0.0,
                mean_uncertainty=0.72,
                ambiguity_level=0.55,
                conflict_level=0.4,
                context_accuracy={"context_0": 0.60, "context_1": 0.90},
                metadata={
                    "packets_evaluated": 10,
                    "final_accuracy": 0.75,
                    "floor_accuracy": 0.60,
                    "c_task_layer1_mode": "communicative",
                    "c_task_regime_summary": {
                        "packets_evaluated": 3,
                        "context_gap": 0.0,
                        "weak_context_key": "context_1",
                        "weak_context_accuracy": 1.0,
                        "strong_context_key": "context_1",
                        "strong_context_accuracy": 1.0,
                        "context_coverage_ratio": 0.5,
                        "source_context_balance": 0.78,
                        "source_self_hardening_ready_ratio": 1.0,
                        "preserve_hardening_ready_ratio": 1.0,
                        "preserve_identity_action_ratio": 1.0,
                        "low_atp_route_ratio": 0.0,
                        "mean_preserve_pressure": 0.97,
                        "mean_reopen_pressure": 0.0,
                        "mean_resolution_confidence": 0.7,
                        "preserve_mode_packet_ratio": 0.0,
                    },
                },
            )
        ]

        signal = regulator.regulate(history)

        profile = signal.metadata.get("c_task_regulatory_profile", {})
        self.assertGreater(float(profile.get("weak_context_boost", 0.0)), 0.0)
        self.assertLess(float(profile.get("source_hardening_shift", 0.0)), 0.0)
        self.assertGreaterEqual(float(profile.get("budget_scale", 1.0)), 1.0)

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

    def test_learning_regulator_preserves_c_task_regulatory_profile_metadata(self) -> None:
        regulator = LearningSliceRegulator(accuracy_threshold=0.8)
        summary = SliceSummary(
            slice_id=1,
            slice_budget=8,
            cycles_used=8,
            examples_seen=8,
            benchmark_family="C",
            task_key="task_a",
            mean_coherence=0.58,
            final_coherence=0.6,
            coherence_delta=0.01,
            mean_uncertainty=0.55,
            ambiguity_level=0.42,
            conflict_level=0.32,
            context_accuracy={"context_0": 0.54, "context_1": 0.84},
            mode_used="visible",
            metadata={
                "final_accuracy": 0.69,
                "floor_accuracy": 0.54,
                "c_task_layer1_mode": "communicative",
                "c_task_regime_summary": {
                    "packets_evaluated": 12,
                    "context_gap": 0.30,
                    "weak_context_key": "context_0",
                    "weak_context_accuracy": 0.54,
                    "strong_context_key": "context_1",
                    "strong_context_accuracy": 0.84,
                    "context_coverage_ratio": 0.58,
                    "source_context_balance": 0.42,
                    "source_self_hardening_ready_ratio": 0.36,
                    "preserve_hardening_ready_ratio": 0.18,
                    "preserve_identity_action_ratio": 0.61,
                    "low_atp_route_ratio": 0.24,
                    "mean_preserve_pressure": 0.66,
                    "mean_reopen_pressure": 0.03,
                    "mean_resolution_confidence": 0.52,
                    "preserve_mode_packet_ratio": 0.31,
                },
            },
        )

        signal = regulator.regulate([summary])

        self.assertIn("c_task_regulatory_profile", signal.metadata)

    def test_heuristic_regulator_emits_c_task_node_support_profile_after_persistent_debt(self) -> None:
        regulator = HeuristicSliceRegulator(accuracy_threshold=0.8)
        previous = SliceSummary(
            slice_id=1,
            slice_budget=8,
            cycles_used=8,
            examples_seen=8,
            benchmark_family="C",
            task_key="task_a",
            mean_uncertainty=0.6,
            ambiguity_level=0.5,
            conflict_level=0.35,
            context_accuracy={"context_0": 0.62, "context_1": 0.86},
            metadata={
                "final_accuracy": 0.74,
                "floor_accuracy": 0.62,
                "c_task_layer1_mode": "communicative",
                "c_task_regime_summary": {
                    "node_evidence": {
                        "n0": {
                            "c_task_routes": 4.0,
                            "low_atp_routes": 1.0,
                            "low_atp_ratio": 0.25,
                            "preserve_violation_routes": 0.0,
                            "preserve_violation_ratio": 0.0,
                        },
                        "n2": {
                            "c_task_routes": 4.0,
                            "low_atp_routes": 1.0,
                            "low_atp_ratio": 0.25,
                            "preserve_violation_routes": 1.0,
                            "preserve_violation_ratio": 0.25,
                        },
                    },
                },
            },
        )
        current = SliceSummary(
            slice_id=2,
            slice_budget=8,
            cycles_used=8,
            examples_seen=8,
            benchmark_family="C",
            task_key="task_a",
            mean_uncertainty=0.62,
            ambiguity_level=0.52,
            conflict_level=0.36,
            context_accuracy={"context_0": 0.60, "context_1": 0.88},
            metadata={
                "final_accuracy": 0.74,
                "floor_accuracy": 0.60,
                "c_task_layer1_mode": "communicative",
                "growth_request": {"top_requesting_nodes": ["n2", "n3"]},
                "source_route_breakdown": {
                    "context_0": {"routes": {"n2": 5, "n1": 3}},
                    "context_1": {"routes": {"n3": 6, "n1": 2}},
                },
                "c_task_regime_summary": {
                    "packets_evaluated": 12,
                    "context_gap": 0.28,
                    "weak_context_key": "context_0",
                    "weak_context_accuracy": 0.60,
                    "strong_context_key": "context_1",
                    "strong_context_accuracy": 0.88,
                    "context_coverage_ratio": 0.7,
                    "source_context_balance": 0.55,
                    "source_self_hardening_ready_ratio": 0.45,
                    "preserve_hardening_ready_ratio": 0.3,
                    "preserve_identity_action_ratio": 0.7,
                    "low_atp_route_ratio": 0.22,
                    "mean_preserve_pressure": 0.58,
                    "mean_reopen_pressure": 0.03,
                    "mean_resolution_confidence": 0.52,
                    "preserve_mode_packet_ratio": 0.24,
                    "node_evidence": {
                        "n0": {
                            "c_task_routes": 4.0,
                            "low_atp_routes": 1.0,
                            "low_atp_ratio": 0.25,
                            "preserve_violation_routes": 0.0,
                            "preserve_violation_ratio": 0.0,
                        },
                        "n2": {
                            "c_task_routes": 5.0,
                            "low_atp_routes": 2.0,
                            "low_atp_ratio": 0.4,
                            "preserve_violation_routes": 1.0,
                            "preserve_violation_ratio": 0.2,
                        },
                    },
                },
            },
        )

        signal = regulator.regulate([previous, current])

        node_profile = signal.metadata.get("c_task_node_support_profile", {})
        self.assertIn("n0", node_profile)
        self.assertIn("n2", node_profile)
        self.assertGreater(float(node_profile["n0"].get("atp_credit", 0.0)), 0.0)

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

    def test_threshold_settlement_prefers_exact_accuracy_over_bit_accuracy(self) -> None:
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
                    mean_uncertainty=0.3,
                    ambiguity_level=0.18,
                    conflict_level=0.18,
                    context_accuracy={"context_0": 0.9, "context_1": 0.9},
                    metadata={
                        "accuracy_metric": "exact_match_rate",
                        "exact_match_rate": 0.5,
                        "final_accuracy": 0.9,
                        "mean_bit_accuracy": 0.9,
                        "context_exact_accuracy": {"context_0": 0.5, "context_1": 0.5},
                    },
                ),
                SliceSummary(
                    slice_id=2,
                    slice_budget=6,
                    cycles_used=6,
                    examples_seen=4,
                    mean_coherence=0.72,
                    final_coherence=0.74,
                    coherence_delta=0.01,
                    mean_uncertainty=0.28,
                    ambiguity_level=0.16,
                    conflict_level=0.16,
                    context_accuracy={"context_0": 0.92, "context_1": 0.92},
                    metadata={
                        "accuracy_metric": "exact_match_rate",
                        "exact_match_rate": 0.5,
                        "final_accuracy": 0.92,
                        "mean_bit_accuracy": 0.92,
                        "context_exact_accuracy": {"context_0": 0.5, "context_1": 0.5},
                    },
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

    def test_learning_regulator_preserves_control_fields_when_growth_initiates(self) -> None:
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
            metadata={"mean_bit_accuracy": 0.49},
        )
        base_signal = RegulatorySignal(
            next_slice_budget=7,
            budget_target=9.0,
            pressure_level=0.73,
            hygiene_level=0.41,
            growth_drive=0.35,
            portfolio_drive=0.22,
            settlement_confidence=0.18,
            carryover_filter_mode="soften",
            context_pressure="high",
            decision_hint=SettlementDecision.CONTINUE,
            capability_mode="visible",
            growth_authorization="initiate",
            execution_plan=SliceExecutionPlan(
                initial_budget=6,
                extend_step=2,
                soft_cap=8,
                hard_cap=10,
                early_stop_patience=1,
                metadata={"target_budget": 9},
            ),
            bias_updates={"preserve": 0.2},
            gating_updates={"grow": 0.8},
            reset_flags={"reseed": 0.0},
            reframe_flags={"drop": 0.0},
            stop_reason="",
            metadata={"regulator_mode": "heuristic"},
        )

        class _StubHeuristic:
            accuracy_threshold = 0.8

            def regulate(self, history: list[SliceSummary]) -> RegulatorySignal:
                return base_signal

        regulator._heuristic = _StubHeuristic()
        regulator._extract_features = lambda current, debt_summary: {"floor": 0.48}  # type: ignore[assignment]
        regulator._current_authorization = lambda current, signal: "authorize"  # type: ignore[assignment]
        regulator._candidate_authorizations = lambda current, signal: ["authorize", "initiate"]  # type: ignore[assignment]
        regulator._predict_delta = lambda authorization, features: (  # type: ignore[assignment]
            0.11 if authorization == "authorize" else 0.17
        )

        signal = regulator.regulate([summary])

        self.assertEqual(signal.growth_authorization, "initiate")
        self.assertEqual(signal.carryover_filter_mode, "soften")
        self.assertAlmostEqual(signal.budget_target or 0.0, 9.0, places=4)
        self.assertAlmostEqual(signal.pressure_level, 0.73, places=4)
        self.assertAlmostEqual(signal.hygiene_level, 0.41, places=4)
        self.assertAlmostEqual(signal.growth_drive, 0.35, places=4)
        self.assertAlmostEqual(signal.portfolio_drive, 0.22, places=4)
        self.assertAlmostEqual(signal.settlement_confidence, 0.18, places=4)
        self.assertIsNotNone(signal.execution_plan)
        self.assertEqual(signal.execution_plan.hard_cap, 10)
        self.assertEqual(signal.metadata["regulator_mode"], "heuristic")
        self.assertIn("predicted_delta_initiate", signal.metadata)

    def test_heuristic_regulator_threshold_requires_two_slices_to_settle(self) -> None:
        regulator = HeuristicSliceRegulator(accuracy_threshold=0.8)
        summary = SliceSummary(
            slice_id=1,
            slice_budget=12,
            cycles_used=12,
            examples_seen=16,
            conflict_level=0.5,
            ambiguity_level=1.0,
            coherence_delta=0.0139,
            mean_uncertainty=0.7553,
            context_accuracy={"context_0": 1.0, "context_1": 1.0},
            mode_used="visible",
            metadata={
                "final_accuracy": 1.0,
                "mean_bit_accuracy": 1.0,
                "c_task_layer1_mode": "communicative",
                "c_task_mean_preserve_pressure": 0.972,
                "c_task_mean_reopen_pressure": 0.0,
                "c_task_mean_resolution_confidence": 0.7,
                "c_task_preserve_mode_packet_ratio": 0.0,
            },
        )

        signal = regulator.regulate([summary])

        self.assertEqual(signal.decision_hint, SettlementDecision.CONTINUE)

    def test_learning_regulator_threshold_requires_two_slices_to_settle(self) -> None:
        regulator = LearningSliceRegulator(accuracy_threshold=0.8)
        summary = SliceSummary(
            slice_id=1,
            slice_budget=12,
            cycles_used=12,
            examples_seen=16,
            conflict_level=0.5,
            ambiguity_level=1.0,
            coherence_delta=0.0139,
            mean_uncertainty=0.7553,
            context_accuracy={"context_0": 1.0, "context_1": 1.0},
            mode_used="visible",
            metadata={
                "final_accuracy": 1.0,
                "mean_bit_accuracy": 1.0,
                "c_task_layer1_mode": "communicative",
                "c_task_mean_preserve_pressure": 0.972,
                "c_task_mean_reopen_pressure": 0.0,
                "c_task_mean_resolution_confidence": 0.7,
                "c_task_preserve_mode_packet_ratio": 0.0,
            },
        )

        signal = regulator.regulate([summary])

        self.assertEqual(signal.decision_hint, SettlementDecision.CONTINUE)

    def test_heuristic_regulator_caches_context_debt_summary_per_history(self) -> None:
        regulator = HeuristicSliceRegulator(accuracy_threshold=0.8)
        history = [
            SliceSummary(
                slice_id=1,
                slice_budget=8,
                cycles_used=8,
                examples_seen=6,
                conflict_level=0.52,
                ambiguity_level=0.38,
                coherence_delta=0.01,
                mean_uncertainty=0.48,
                context_accuracy={"context_0": 0.42, "context_1": 0.81},
                mode_used="visible",
                metadata={
                    "final_accuracy": 0.61,
                    "floor_accuracy": 0.42,
                    "growth_request": {
                        "authorization": "auto",
                        "requesting_nodes": 1,
                        "active_growth_nodes": 0,
                        "pending_proposals": 0,
                        "max_pressure": 0.20,
                        "max_readiness": 0.18,
                    },
                },
            ),
            SliceSummary(
                slice_id=2,
                slice_budget=8,
                cycles_used=8,
                examples_seen=6,
                conflict_level=0.56,
                ambiguity_level=0.42,
                coherence_delta=0.0,
                mean_uncertainty=0.52,
                context_accuracy={"context_0": 0.40, "context_1": 0.80},
                mode_used="visible",
                metadata={
                    "final_accuracy": 0.60,
                    "floor_accuracy": 0.40,
                    "growth_request": {
                        "authorization": "auto",
                        "requesting_nodes": 1,
                        "active_growth_nodes": 0,
                        "pending_proposals": 0,
                        "max_pressure": 0.18,
                        "max_readiness": 0.16,
                    },
                },
            ),
        ]

        with patch.object(
            lamination_module,
            "_context_debt_summary",
            wraps=lamination_module._context_debt_summary,
        ) as mocked:
            regulator.regulate(history)

        self.assertEqual(mocked.call_count, 1)

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
        self.assertLessEqual(signal.execution_plan.hard_cap, 32)
        self.assertEqual(signal.metadata.get("regulator_mode"), "gradient")
        substrate_meta = signal.metadata.get("regulatory_substrate", {})
        self.assertIn("primitive_drives", substrate_meta)
        self.assertIn("differentiate", substrate_meta.get("primitive_drives", {}))
        self.assertIn("latent_states", substrate_meta)

    def test_gradient_regulator_only_authorizes_growth_from_bottom_up_request(self) -> None:
        regulator = GradientSliceRegulator(accuracy_threshold=0.8)
        requested = [
            SliceSummary(
                slice_id=1,
                slice_budget=6,
                cycles_used=6,
                examples_seen=4,
                conflict_level=0.35,
                ambiguity_level=0.25,
                coherence_delta=0.0,
                mean_uncertainty=0.42,
                context_accuracy={"context_0": 0.36, "context_1": 0.72},
                metadata={
                    "final_accuracy": 0.54,
                    "floor_accuracy": 0.36,
                    "mean_provisional_context_ambiguity": 0.05,
                    "mean_transform_commitment_margin": 0.68,
                    "growth_request": {
                        "authorization": "auto",
                        "requesting_nodes": 1,
                        "active_growth_nodes": 0,
                        "pending_proposals": 0,
                        "max_pressure": 0.46,
                        "max_readiness": 0.20,
                    },
                    "applied_carryover_filter_mode": "soften",
                },
            )
        ]
        no_request = [
            replace(
                requested[0],
                metadata={
                    **requested[0].metadata,
                    "growth_request": {
                        "authorization": "auto",
                        "requesting_nodes": 0,
                        "active_growth_nodes": 0,
                        "pending_proposals": 0,
                        "max_pressure": 0.46,
                        "max_readiness": 0.20,
                    },
                },
            )
        ]

        requested_signal = regulator.regulate(requested)
        no_request_signal = regulator.regulate(no_request)

        self.assertEqual(requested_signal.growth_authorization, "authorize")
        self.assertNotEqual(no_request_signal.growth_authorization, "authorize")

    def test_gradient_regulator_can_initiate_growth_from_chronic_structural_need(self) -> None:
        regulator = GradientSliceRegulator(accuracy_threshold=0.8)
        self.assertTrue(
            regulator._should_initiate_growth_from_structural_need(
                structural_need=0.59,
                expand_drive=0.25,
                explore_drive=0.35,
                pressure_level=0.63,
                settlement_confidence=0.45,
                floor_gap=0.45,
                growth_readiness=0.64,
            )
        )
        self.assertFalse(
            regulator._should_initiate_growth_from_structural_need(
                structural_need=0.45,
                expand_drive=0.18,
                explore_drive=0.20,
                pressure_level=0.34,
                settlement_confidence=0.65,
                floor_gap=0.12,
                growth_readiness=0.18,
            )
        )

    def test_heuristic_regulator_escalates_authorized_growth_stall_to_initiate(self) -> None:
        regulator = HeuristicSliceRegulator(accuracy_threshold=0.8)
        summary = SliceSummary(
            slice_id=4,
            slice_budget=6,
            cycles_used=6,
            examples_seen=4,
            conflict_level=0.28,
            ambiguity_level=0.24,
            coherence_delta=0.0,
            mean_uncertainty=0.44,
            context_accuracy={"context_0": 0.40, "context_1": 0.58},
            metadata={
                "final_accuracy": 0.56,
                "mean_bit_accuracy": 0.56,
                "growth_request": {
                    "authorization": "authorize",
                    "requesting_nodes": 2,
                    "active_growth_nodes": 0,
                    "pending_proposals": 0,
                    "max_pressure": 0.52,
                    "max_readiness": 0.50,
                    "authorized_stall_slices": 3,
                    "authorized_without_proposal_count": 1,
                },
            },
        )

        signal = regulator.regulate([summary])

        self.assertEqual(signal.growth_authorization, "initiate")

    def test_regulatory_substrate_accumulates_primitive_credit_and_support(self) -> None:
        substrate = RegulatorySubstrate()
        first = RegulatoryObservation(
            floor_accuracy=0.20,
            final_accuracy=0.45,
            floor_gap=0.75,
            final_gap=0.4375,
            debt_mass=0.80,
            debt_total=0.85,
            open_context_mass=1.0,
            spread=0.60,
            uncertainty=0.50,
            conflict=0.42,
            ambiguity=0.28,
            provisional_ambiguity=0.04,
            hidden_ambiguity=0.05,
            commitment_hardness=0.72,
            progress_velocity=0.20,
            stall=0.80,
            failed_hygiene_persistence=0.66,
            slice_efficiency=0.32,
            growth_pressure=0.08,
            growth_readiness=0.35,
            active_growth=0.0,
            pending_growth=0.0,
            budget_saturation=0.55,
        )
        second = RegulatoryObservation(
            floor_accuracy=0.42,
            final_accuracy=0.64,
            floor_gap=0.475,
            final_gap=0.20,
            debt_mass=0.38,
            debt_total=0.50,
            open_context_mass=0.50,
            spread=0.24,
            uncertainty=0.35,
            conflict=0.18,
            ambiguity=0.20,
            provisional_ambiguity=0.12,
            hidden_ambiguity=0.18,
            commitment_hardness=0.44,
            progress_velocity=0.72,
            stall=0.28,
            failed_hygiene_persistence=0.20,
            slice_efficiency=0.70,
            growth_pressure=0.10,
            growth_readiness=0.42,
            active_growth=0.0,
            pending_growth=0.0,
            budget_saturation=0.40,
        )

        first_comp = substrate.step(first, current_budget=6)
        second_comp = substrate.step(second, current_budget=6)

        diff_state = substrate.states[RegulatoryPrimitive.DIFFERENTIATE]
        self.assertGreater(first_comp.primitive_drives["differentiate"], 0.0)
        self.assertGreater(diff_state.credit, 0.0)
        self.assertGreater(diff_state.provisional_support, 0.0)
        self.assertGreater(second_comp.settlement_confidence, first_comp.settlement_confidence)
        self.assertIn("recoverable_branch", second_comp.latent_states)
        self.assertGreater(second_comp.latent_states["recoverable_branch"], 0.0)
        self.assertGreater(second_comp.latent_states["confidently_wrong"], 0.0)

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
