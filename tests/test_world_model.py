from __future__ import annotations

import unittest
from dataclasses import replace

from real_core import (
    HeuristicSliceRegulator,
    LaminatedController,
    REALWorldModel,
    RegulatorySignal,
    SettlementDecision,
    SliceExecutionPlan,
    SliceSummary,
    WorldModelObservationAdapter,
)


def _c_summary(
    slice_id: int,
    *,
    floor_accuracy: float = 0.30,
    final_accuracy: float = 0.48,
    ambiguity: float = 0.62,
    commitment: float = 0.22,
    seq_estimate: float = -1.0,
    seq_confidence: float = 0.0,
    route_estimate: float = -1.0,
    route_confidence: float = 0.0,
    feedback_estimate: float = -1.0,
    feedback_confidence: float = 0.0,
    revisit_marker: float = 0.0,
    dead_end_marker: float = 0.0,
    teacher_hypothesis: str | float | None = None,
    teacher_confidence: float = 0.0,
    mode_used: str = "visible",
    world_model_summary: dict[str, object] | None = None,
) -> SliceSummary:
    context_0 = floor_accuracy
    context_1 = min(1.0, max(context_0, final_accuracy + 0.18))
    metadata = {
        "final_accuracy": final_accuracy,
        "mean_bit_accuracy": final_accuracy,
        "floor_accuracy": floor_accuracy,
        "mean_provisional_context_ambiguity": ambiguity,
        "mean_transform_commitment_margin": commitment,
        "source_sequence_context_estimate": seq_estimate,
        "source_sequence_context_confidence": seq_confidence,
        "source_sequence_channel_context_confidence": seq_confidence,
        "source_route_context_estimate": route_estimate,
        "source_route_context_confidence": route_confidence,
        "source_feedback_context_estimate": feedback_estimate,
        "source_feedback_context_confidence": feedback_confidence,
        "forecast_metrics": {
            "forecast_regime_accuracy": {
                "stable": max(0.0, min(1.0, final_accuracy)),
            }
        },
        "growth_request": {
            "authorization": "authorize",
            "requesting_nodes": 1,
            "active_growth_nodes": 0,
            "pending_proposals": 0,
            "max_pressure": 0.52,
            "max_readiness": 0.42,
        },
        "world_model_revisit_marker": revisit_marker,
        "world_model_dead_end_marker": dead_end_marker,
    }
    if teacher_hypothesis is not None:
        metadata["world_model_teacher_hypothesis"] = teacher_hypothesis
        metadata["world_model_teacher_confidence"] = teacher_confidence
    if world_model_summary is not None:
        metadata["world_model_summary"] = dict(world_model_summary)
    return SliceSummary(
        slice_id=slice_id,
        slice_budget=4,
        cycles_used=4,
        examples_seen=4,
        benchmark_family="C",
        task_key="task_a",
        coherence_delta=0.0,
        mean_uncertainty=max(0.0, min(1.0, 1.0 - final_accuracy)),
        ambiguity_level=ambiguity,
        conflict_level=max(0.0, min(1.0, ambiguity * 0.7)),
        context_accuracy={"context_0": context_0, "context_1": context_1},
        metadata=metadata,
        mode_used=mode_used,
    )


class PortfolioWorldModelRunner:
    def __init__(self) -> None:
        self.state = "initial"
        self.world_model_state: dict[str, object] = {}

    def run_slice_plan(
        self,
        *,
        slice_id: int,
        execution_plan: SliceExecutionPlan,
        regulatory_signal=None,
    ) -> SliceSummary:
        hard_cap = int(execution_plan.hard_cap)
        if slice_id == 1:
            self.state = "after-initial"
            return _c_summary(
                1,
                floor_accuracy=0.24,
                final_accuracy=0.45,
                ambiguity=0.74,
                commitment=0.18,
                seq_estimate=0.0,
                seq_confidence=0.62,
                route_estimate=0.0,
                route_confidence=0.55,
            )
        if hard_cap <= 3:
            self.state = "after-short"
            return _c_summary(
                slice_id,
                floor_accuracy=0.82,
                final_accuracy=0.88,
                ambiguity=0.18,
                commitment=0.70,
                seq_estimate=0.0,
                seq_confidence=0.78,
                route_estimate=0.0,
                route_confidence=0.68,
                feedback_estimate=0.0,
                feedback_confidence=0.65,
            )
        if hard_cap <= 5:
            self.state = "after-base"
            return _c_summary(
                slice_id,
                floor_accuracy=0.52,
                final_accuracy=0.66,
                ambiguity=0.30,
                commitment=0.50,
                seq_estimate=1.0,
                seq_confidence=0.66,
                route_estimate=1.0,
                route_confidence=0.62,
                feedback_estimate=1.0,
                feedback_confidence=0.48,
            )
        self.state = "after-long"
        return _c_summary(
            slice_id,
            floor_accuracy=0.40,
            final_accuracy=0.58,
            ambiguity=0.38,
            commitment=0.44,
            seq_estimate=2.0,
            seq_confidence=0.68,
            route_estimate=2.0,
            route_confidence=0.54,
            feedback_estimate=2.0,
            feedback_confidence=0.42,
        )

    def snapshot_fast_state(self) -> dict[str, object]:
        return {"state": self.state, "world_model_state": dict(self.world_model_state)}

    def restore_fast_state(self, snapshot: dict[str, object]) -> None:
        self.state = str(snapshot.get("state", self.state))
        self.world_model_state = dict(snapshot.get("world_model_state", {}) or {})


class PortfolioWorldModelRegulator:
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
        )


class TestWorldModelLayer(unittest.TestCase):
    def test_observation_adapter_reads_slice_features(self) -> None:
        adapter = WorldModelObservationAdapter()
        history = [
            _c_summary(
                1,
                floor_accuracy=0.34,
                final_accuracy=0.50,
                ambiguity=0.66,
                commitment=0.24,
                seq_estimate=0.0,
                seq_confidence=0.58,
                route_estimate=1.0,
                route_confidence=0.44,
                feedback_estimate=1.0,
                feedback_confidence=0.32,
            )
        ]

        observation = adapter.observe(history)

        self.assertGreater(observation["slice_ambiguity"], 0.6)
        self.assertAlmostEqual(observation["source_sequence_confidence"], 0.58, places=4)
        self.assertAlmostEqual(observation["source_route_confidence"], 0.44, places=4)
        self.assertGreaterEqual(observation["forecast_regime_accuracy"], 0.49)

    def test_competing_hypotheses_remain_alive_under_ambiguity(self) -> None:
        world_model = REALWorldModel(update_stride=1)
        history = [
            _c_summary(
                1,
                floor_accuracy=0.28,
                final_accuracy=0.46,
                ambiguity=0.72,
                commitment=0.18,
                seq_estimate=0.0,
                seq_confidence=0.62,
                route_estimate=1.0,
                route_confidence=0.56,
            ),
            _c_summary(
                2,
                floor_accuracy=0.30,
                final_accuracy=0.48,
                ambiguity=0.70,
                commitment=0.20,
                seq_estimate=0.0,
                seq_confidence=0.60,
                route_estimate=1.0,
                route_confidence=0.58,
                feedback_estimate=0.0,
                feedback_confidence=0.22,
            ),
        ]

        result = world_model.process(history)

        self.assertIsNotNone(result)
        self.assertEqual(result.action, "hold_open")
        hypotheses = result.summary["hypotheses"]
        self.assertGreater(hypotheses["h0"]["support"], 0.0)
        self.assertGreater(hypotheses["h1"]["support"], 0.0)
        self.assertGreater(result.summary["unresolved_mass"], 0.2)

    def test_mark_dead_end_reduces_failed_top_hypothesis(self) -> None:
        world_model = REALWorldModel(update_stride=1)
        first = _c_summary(
            1,
            floor_accuracy=0.52,
            final_accuracy=0.64,
            ambiguity=0.30,
            commitment=0.56,
            seq_estimate=0.0,
            seq_confidence=0.74,
            route_estimate=0.0,
            route_confidence=0.62,
        )
        second = _c_summary(
            2,
            floor_accuracy=0.40,
            final_accuracy=0.50,
            ambiguity=0.72,
            commitment=0.20,
            seq_estimate=0.0,
            seq_confidence=0.70,
            route_estimate=0.0,
            route_confidence=0.58,
            dead_end_marker=1.0,
        )

        world_model.process([first])
        result = world_model.process([first, second])

        self.assertEqual(result.action, "mark_dead_end")
        self.assertGreater(result.summary["dead_end_hit_count"], 0)
        self.assertGreater(
            result.summary["hypotheses"]["h0"]["dead_end_penalty"],
            0.2,
        )

    def test_hinted_assistance_biases_target_without_collapsing_ambiguity(self) -> None:
        world_model = REALWorldModel(
            update_stride=1,
            assistance_mode="hinted",
            assistance_confidence_threshold=0.30,
        )
        history = [
            _c_summary(
                1,
                floor_accuracy=0.30,
                final_accuracy=0.46,
                ambiguity=0.70,
                commitment=0.22,
                seq_estimate=0.0,
                seq_confidence=0.72,
                route_estimate=1.0,
                route_confidence=0.54,
            )
        ]

        result = world_model.process(history)

        self.assertIsNotNone(result)
        self.assertEqual(result.summary["assistance"]["mode"], "hinted")
        self.assertTrue(result.summary["assistance"]["active"])
        self.assertEqual(result.summary["assistance"]["target"], "h0")
        self.assertEqual(result.action, "hold_open")
        self.assertGreater(result.summary["hypotheses"]["h0"]["support"], 0.0)
        self.assertGreater(result.summary["hypotheses"]["h1"]["support"], 0.0)
        self.assertGreater(result.summary["unresolved_mass"], 0.1)

    def test_reopen_alternative_restores_plausible_branch(self) -> None:
        world_model = REALWorldModel(update_stride=1)
        first = _c_summary(
            1,
            floor_accuracy=0.50,
            final_accuracy=0.62,
            ambiguity=0.28,
            commitment=0.58,
            seq_estimate=0.0,
            seq_confidence=0.72,
            route_estimate=0.0,
            route_confidence=0.60,
        )
        dead_end = _c_summary(
            2,
            floor_accuracy=0.42,
            final_accuracy=0.50,
            ambiguity=0.68,
            commitment=0.22,
            seq_estimate=0.0,
            seq_confidence=0.68,
            route_estimate=0.0,
            route_confidence=0.58,
            dead_end_marker=1.0,
        )
        reopen = _c_summary(
            3,
            floor_accuracy=0.44,
            final_accuracy=0.54,
            ambiguity=0.50,
            commitment=0.34,
            seq_estimate=1.0,
            seq_confidence=0.70,
            route_estimate=1.0,
            route_confidence=0.60,
            feedback_estimate=1.0,
            feedback_confidence=0.44,
            revisit_marker=1.0,
        )

        world_model.process([first])
        world_model.process([first, dead_end])
        result = world_model.process([first, dead_end, reopen])

        self.assertEqual(result.action, "reopen_alternative")
        self.assertGreater(result.summary["revisit_hit_count"], 0)
        self.assertGreater(result.summary["hypotheses"]["h1"]["support"], 0.0)
        self.assertGreater(result.summary["hypotheses"]["h1"]["revisit_credit"], 0.0)

    def test_teacher_assistance_holds_open_instead_of_forcing_commit(self) -> None:
        world_model = REALWorldModel(
            update_stride=1,
            assistance_mode="teacher",
            assistance_confidence_threshold=0.20,
        )
        result = world_model.process(
            [
                _c_summary(
                    1,
                    floor_accuracy=0.62,
                    final_accuracy=0.70,
                    ambiguity=0.24,
                    commitment=0.44,
                    seq_estimate=1.0,
                    seq_confidence=0.34,
                    teacher_hypothesis="h2",
                    teacher_confidence=0.98,
                )
            ]
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.summary["assistance"]["mode"], "teacher")
        self.assertTrue(result.summary["assistance"]["active"])
        self.assertEqual(result.summary["assistance"]["target"], "h2")
        self.assertEqual(result.action, "hold_open")
        self.assertGreater(result.summary["hypotheses"]["h2"]["support"], 0.0)
        self.assertGreater(result.summary["unresolved_mass"], 0.2)

    def test_load_state_restores_exported_runtime_config(self) -> None:
        original = REALWorldModel(
            update_stride=5,
            ambiguity_threshold=0.63,
            ambiguity_streak=4,
            accuracy_threshold=0.82,
            assistance_mode="guided",
            assistance_confidence_threshold=0.27,
        )
        payload = original.export_state()
        restored = REALWorldModel(
            update_stride=1,
            ambiguity_threshold=0.2,
            ambiguity_streak=1,
            accuracy_threshold=0.5,
            assistance_mode="off",
            assistance_confidence_threshold=0.9,
        )

        restored.load_state(payload)

        self.assertEqual(restored.update_stride, 5)
        self.assertAlmostEqual(restored.ambiguity_threshold, 0.63, places=4)
        self.assertEqual(restored.ambiguity_streak, 4)
        self.assertAlmostEqual(restored.accuracy_threshold, 0.82, places=4)
        self.assertAlmostEqual(restored.adapter.accuracy_threshold, 0.82, places=4)
        self.assertEqual(restored.assistance_mode, "guided")
        self.assertAlmostEqual(restored.assistance_confidence_threshold, 0.27, places=4)

    def test_regulator_changes_policy_from_world_model_summary(self) -> None:
        regulator = HeuristicSliceRegulator(accuracy_threshold=0.8)
        unresolved = _c_summary(
            1,
            world_model_summary={
                "top_hypothesis": "h0",
                "top_margin": 0.08,
                "unresolved_mass": 0.68,
                "contradiction_load": 0.34,
                "last_action": "hold_open",
                "hypotheses": {
                    "h0": {"dead_end_penalty": 0.0},
                },
            },
        )
        confident = replace(
            unresolved,
            mode_used="visible",
            metadata={
                **dict(unresolved.metadata),
                "world_model_summary": {
                    "top_hypothesis": "h2",
                    "top_margin": 0.34,
                    "unresolved_mass": 0.18,
                    "contradiction_load": 0.08,
                    "last_action": "handoff_commit",
                    "hypotheses": {
                        "h2": {"dead_end_penalty": 0.0},
                    },
                },
            },
        )

        unresolved_signal = regulator.regulate([unresolved])
        confident_signal = regulator.regulate([confident])

        self.assertEqual(unresolved_signal.carryover_filter_mode, "keep")
        self.assertEqual(unresolved_signal.growth_authorization, "hold")
        self.assertEqual(unresolved_signal.context_pressure, "high")
        self.assertEqual(confident_signal.capability_mode, "latent")

    def test_controller_portfolio_restores_winning_world_model_state(self) -> None:
        runner = PortfolioWorldModelRunner()
        controller = LaminatedController(
            runner,
            regulator=PortfolioWorldModelRegulator(),
            initial_cycle_budget=4,
            safety_limit=3,
            world_model=REALWorldModel(update_stride=1),
        )

        result = controller.run()

        self.assertEqual(result.final_decision, SettlementDecision.SETTLE)
        self.assertEqual(result.summaries[-1].metadata.get("portfolio_selected"), "short")
        candidate_world_models = result.summaries[-1].metadata.get(
            "portfolio_candidate_world_models",
            {},
        )
        self.assertNotEqual(
            result.summaries[-1].metadata.get("world_model_summary"),
            candidate_world_models.get("long"),
        )
        self.assertIn("short", candidate_world_models)
        self.assertIn("long", candidate_world_models)
        self.assertEqual(
            runner.world_model_state.get("last_update_slice_id"),
            controller.world_model.summary()["last_update_slice_id"],
        )
        final_signal = result.final_signal
        self.assertIsNotNone(final_signal)
        self.assertIn("world_model_summary", final_signal.metadata)
