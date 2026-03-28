from __future__ import annotations

import unittest

from phase8 import (
    FeedbackPulse,
    Phase8SliceRunner,
    SignalPacket,
    build_system_for_scenario,
)
from real_core import RegulatorySignal, SliceExecutionPlan
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
        self.assertIn("final_accuracy", summary.metadata)
        self.assertIn("floor_accuracy", summary.metadata)
        self.assertIn("worst_context_accuracy", summary.metadata)
        self.assertIn("mean_provisional_context_ambiguity", summary.metadata)
        self.assertIn("max_provisional_context_ambiguity", summary.metadata)
        self.assertIn("mean_transform_commitment_margin", summary.metadata)
        self.assertIn("hidden_packet_mean_provisional_context_ambiguity", summary.metadata)
        self.assertIn("hidden_packet_min_transform_commitment_margin", summary.metadata)
        self.assertIn("forecast_metrics", summary.metadata)
        self.assertIn("intervention_payoff_trend", summary.metadata)
        self.assertIn("forecast_entry_count", summary.metadata["forecast_metrics"])
        self.assertIn("growth_request", summary.metadata)
        self.assertNotIn("capability_states", summary.metadata["growth_request"])

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

        second_summary = runner.run_slice(
            slice_id=3,
            cycle_budget=4,
            regulatory_signal=RegulatorySignal(
                carryover_filter_mode="keep",
                metadata={"chosen_policy": "visible_explore", "chosen_mode": "visible"},
            ),
        )

        for agent in system.agents.values():
            self.assertTrue(all(entry.cycle > 4 for entry in agent.engine.memory.entries))
        self.assertIn(
            second_summary.metadata["intervention_payoff_trend"]["status"],
            {"improved", "worsened", "flat", "unavailable"},
        )

    def test_mode_switch_preserves_fast_layer_runtime_continuity(self) -> None:
        case = b_scale_suite_by_id()["B2S1"]
        scenario = case.tasks["task_a"].visible_scenario
        runner = Phase8SliceRunner(
            build_system_for_scenario(
                scenario,
                seed=13,
                capability_policy="self-selected",
            ),
            scenario,
            benchmark_family="B",
            task_key="task_a",
            initial_capability_mode="visible",
        )

        runner.run_slice(slice_id=1, cycle_budget=4)
        source_id = runner.system.environment.source_id
        runner.system.environment.queue_growth_proposal(
            source_id,
            "bud_edge:n1",
            score=0.8,
            cost=0.1,
        )
        capability = runner.system.environment.capability_states[source_id]
        capability.growth_support = 0.42
        capability.growth_enabled = True
        capability.growth_recruitment_cycles.append(runner.system.global_cycle)
        prior_cycle = runner.system.global_cycle
        prior_env_cycle = runner.system.environment.current_cycle
        prior_pending = len(runner.system.environment.pending_growth_proposals)
        prior_capability_state = runner.system.environment.export_capability_state()
        prior_entry_count = len(runner.system.agents[source_id].engine.memory.entries)

        runner._switch_mode("growth-visible")

        self.assertEqual(runner.system.capability_policy, "growth-visible")
        self.assertEqual(runner.system.environment.capability_policy, "growth-visible")
        self.assertEqual(runner.system.global_cycle, prior_cycle)
        self.assertEqual(runner.system.environment.current_cycle, prior_env_cycle)
        self.assertEqual(
            len(runner.system.environment.pending_growth_proposals),
            prior_pending,
        )
        self.assertEqual(
            runner.system.environment.export_capability_state(),
            prior_capability_state,
        )
        self.assertGreaterEqual(
            len(runner.system.agents[source_id].engine.memory.entries),
            prior_entry_count,
        )

    def test_growth_hold_preserves_pending_growth_but_stops_new_authorized_growth(self) -> None:
        case = b_scale_suite_by_id()["B2S1"]
        scenario = case.tasks["task_a"].visible_scenario
        runner = Phase8SliceRunner(
            build_system_for_scenario(
                scenario,
                seed=13,
                capability_policy="self-selected",
            ),
            scenario,
            benchmark_family="B",
            task_key="task_a",
        )

        runner.run_slice(slice_id=1, cycle_budget=4)
        source_id = runner.system.environment.source_id
        runner.system.environment.queue_growth_proposal(
            source_id,
            "bud_edge:n1",
            score=0.7,
            cost=0.1,
        )
        capability = runner.system.environment.capability_states[source_id]
        capability.growth_enabled = True
        capability.growth_recruitment_pressure = 0.78
        capability.growth_stabilization_readiness = 0.65
        prior_pending = len(runner.system.environment.pending_growth_proposals)

        runner._apply_regulatory_signal(RegulatorySignal(growth_authorization="hold"))

        self.assertEqual(runner.system.environment.slow_growth_authorization, "hold")
        self.assertEqual(
            len(runner.system.environment.pending_growth_proposals),
            prior_pending,
        )
        self.assertEqual(
            runner.system.environment.growth_action_specs(source_id),
            [],
        )

    def test_gradient_signal_honors_explicit_growth_authorization(self) -> None:
        case = b_scale_suite_by_id()["B2S1"]
        scenario = case.tasks["task_a"].visible_scenario
        runner = Phase8SliceRunner(
            build_system_for_scenario(
                scenario,
                seed=13,
                capability_policy="self-selected",
            ),
            scenario,
            benchmark_family="B",
            task_key="task_a",
        )

        runner._apply_regulatory_signal(
            RegulatorySignal(
                growth_authorization="hold",
                growth_drive=0.9,
                metadata={"regulator_mode": "gradient"},
            ),
        )

        self.assertEqual(runner.system.environment.slow_growth_authorization, "hold")

    def test_slice_summary_records_applied_reset_and_reframe_flags(self) -> None:
        case = b_scale_suite_by_id()["B2S1"]
        scenario = case.tasks["task_a"].visible_scenario
        runner = Phase8SliceRunner(
            build_system_for_scenario(
                scenario,
                seed=13,
                capability_policy="self-selected",
            ),
            scenario,
            benchmark_family="B",
            task_key="task_a",
        )

        summary = runner.run_slice(
            slice_id=1,
            cycle_budget=4,
            regulatory_signal=RegulatorySignal(
                carryover_filter_mode="drop",
                context_pressure="high",
                growth_authorization="hold",
                reset_flags={"episodic": 1.0},
                reframe_flags={"context_differentiation": 1.0},
            ),
        )

        self.assertEqual(summary.metadata["applied_growth_authorization"], "hold")
        self.assertEqual(summary.metadata["applied_carryover_filter_mode"], "drop")
        self.assertEqual(summary.metadata["applied_context_pressure"], "high")
        self.assertEqual(summary.metadata["applied_reset_flags"], {"episodic": 1.0})
        self.assertEqual(
            summary.metadata["applied_reframe_flags"],
            {"context_differentiation": 1.0},
        )
        self.assertFalse(summary.metadata["applied_slice_end_consolidation"])
        self.assertTrue(summary.metadata["applied_guidance_bias_skipped"])

    def test_regulatory_signal_sets_weak_context_bias_on_environment(self) -> None:
        case = b_scale_suite_by_id()["B2S1"]
        scenario = case.tasks["task_a"].visible_scenario
        runner = Phase8SliceRunner(
            build_system_for_scenario(
                scenario,
                seed=13,
                capability_policy="self-selected",
            ),
            scenario,
            benchmark_family="B",
            task_key="task_a",
        )

        runner.run_slice(
            slice_id=1,
            cycle_budget=2,
            regulatory_signal=RegulatorySignal(
                bias_updates={"weak_context_bit": 0, "weak_context_gap": 0.6},
            ),
        )

        self.assertEqual(runner.system.environment.slow_weak_context_bit, 0)
        self.assertAlmostEqual(runner.system.environment.slow_weak_context_gap, 0.6)

    def test_drop_reset_scrubs_context_poison_beyond_episodic_entries(self) -> None:
        case = b_scale_suite_by_id()["B2S1"]
        scenario = case.tasks["task_a"].visible_scenario
        runner = Phase8SliceRunner(
            build_system_for_scenario(
                scenario,
                seed=13,
                capability_policy="self-selected",
            ),
            scenario,
            benchmark_family="B",
            task_key="task_a",
        )

        source_id = runner.system.environment.source_id
        source_state = runner.system.environment.state_for(source_id)
        context_key = "xor_mask_1010:context_0"
        branch_key = "n2:context_0"
        source_state.provisional_transform_credit["xor_mask_1010"] = 0.9
        source_state.context_transform_credit[context_key] = 0.8
        source_state.provisional_context_transform_credit[context_key] = 0.7
        source_state.context_transform_debt[context_key] = 0.6
        source_state.branch_context_credit[branch_key] = 0.5
        source_state.branch_context_debt[branch_key] = 0.4
        capability = runner.system.environment.capability_states[source_id]
        capability.latent_recruitment_pressure = 0.7
        capability.latent_confidence_estimate = 0.8
        capability.latent_support = 0.9
        capability.latent_enabled = True
        capability.visible_context_trust = 0.1
        capability.growth_recruitment_pressure = 0.75
        capability.growth_stabilization_readiness = 0.8
        capability.growth_support = 0.85
        capability.growth_enabled = True
        runner.system.agents[source_id].substrate.seed_action_support(
            "n2",
            "xor_mask_1010",
            value=0.9,
            context_bit=0,
        )
        runner.system.environment.queue_growth_proposal(
            source_id,
            "bud_edge:n1",
            score=0.7,
            cost=0.1,
        )
        runner.system.environment.pending_feedback.append(
            FeedbackPulse(
                packet_id="p1",
                edge_path=["n0->n2"],
                amount=0.5,
                transform_path=["xor_mask_1010"],
                context_bit=0,
                task_id="task_a",
            )
        )
        runner.system.environment.inboxes[source_id].append(
            SignalPacket(
                packet_id="queued",
                origin=source_id,
                target="n2",
                created_cycle=runner.system.environment.current_cycle,
                input_bits=[1, 0, 1, 0],
                payload_bits=[1, 0, 1, 0],
                context_bit=0,
                task_id="task_a",
            )
        )

        runner.run_slice(
            slice_id=1,
            cycle_budget=0,
            regulatory_signal=RegulatorySignal(
                carryover_filter_mode="drop",
                reset_flags={"episodic": 1.0},
                bias_updates={"weak_context_bit": 0, "weak_context_gap": 0.8},
            ),
        )

        self.assertEqual(
            len(runner.system.agents[source_id].engine.memory.entries),
            0,
        )
        self.assertLess(
            source_state.provisional_transform_credit.get("xor_mask_1010", 0.0),
            0.9,
        )
        self.assertLess(
            source_state.context_transform_credit.get(context_key, 0.0),
            0.8,
        )
        self.assertLess(
            source_state.provisional_context_transform_credit.get(context_key, 0.0),
            0.7,
        )
        self.assertLess(
            source_state.context_transform_debt.get(context_key, 0.0),
            0.6,
        )
        self.assertLess(
            source_state.branch_context_credit.get(branch_key, 0.0),
            0.5,
        )
        self.assertLess(
            source_state.branch_context_debt.get(branch_key, 0.0),
            0.4,
        )
        self.assertEqual(len(runner.system.environment.pending_feedback), 0)
        self.assertNotIn(
            "queued",
            [
                packet.packet_id
                for queue in runner.system.environment.inboxes.values()
                for packet in queue
            ],
        )
        self.assertLess(
            runner.system.agents[source_id].substrate.contextual_action_support(
                "n2",
                "xor_mask_1010",
                0,
            ),
            0.9,
        )
        self.assertEqual(len(runner.system.environment.pending_growth_proposals), 1)
        self.assertLess(capability.latent_support, 0.9)
        self.assertAlmostEqual(capability.growth_recruitment_pressure, 0.75)
        self.assertAlmostEqual(capability.growth_stabilization_readiness, 0.8)
        self.assertAlmostEqual(capability.growth_support, 0.85)
        self.assertTrue(capability.growth_enabled)
        self.assertGreaterEqual(capability.visible_context_trust, 0.55)

    def test_run_slice_plan_records_adaptive_execution_metadata(self) -> None:
        case = b_scale_suite_by_id()["B2S1"]
        scenario = case.tasks["task_a"].visible_scenario
        runner = Phase8SliceRunner(
            build_system_for_scenario(
                scenario,
                seed=13,
                capability_policy="self-selected",
            ),
            scenario,
            benchmark_family="B",
            task_key="task_a",
        )

        summary = runner.run_slice_plan(
            slice_id=1,
            execution_plan=SliceExecutionPlan(
                initial_budget=2,
                extend_step=1,
                soft_cap=3,
                hard_cap=4,
                early_stop_patience=1,
                metadata={"target_budget": 3},
            ),
            regulatory_signal=RegulatorySignal(
                budget_target=3.0,
                pressure_level=0.5,
                hygiene_level=0.3,
                growth_drive=0.2,
                settlement_confidence=0.1,
                metadata={"regulator_mode": "gradient"},
            ),
        )

        self.assertIn("execution_plan", summary.metadata)
        self.assertIn("adaptive_cycles_used", summary.metadata)
        self.assertLessEqual(
            int(summary.metadata["adaptive_cycles_used"]),
            int(summary.metadata["adaptive_hard_cap"]),
        )

    def test_snapshot_restore_discards_loser_branch_state(self) -> None:
        case = b_scale_suite_by_id()["B2S1"]
        scenario = case.tasks["task_a"].visible_scenario
        runner = Phase8SliceRunner(
            build_system_for_scenario(
                scenario,
                seed=13,
                capability_policy="self-selected",
            ),
            scenario,
            benchmark_family="B",
            task_key="task_a",
        )

        runner.run_slice(slice_id=1, cycle_budget=2)
        base_snapshot = runner.snapshot_fast_state()
        source_id = runner.system.environment.source_id

        runner.system.environment.queue_growth_proposal(
            source_id,
            "bud_edge:n1",
            score=0.8,
            cost=0.1,
        )
        runner.system.environment.pending_feedback.append(
            FeedbackPulse(
                packet_id="portfolio-branch",
                edge_path=["n0->n1"],
                amount=0.4,
                transform_path=["identity"],
                context_bit=0,
                task_id="task_a",
            )
        )
        mutated_snapshot = runner.snapshot_fast_state()
        self.assertGreater(len(mutated_snapshot["runtime_state"]["pending_feedback"]), 0)
        self.assertGreater(len(mutated_snapshot["runtime_state"]["pending_growth_proposals"]), 0)

        runner.restore_fast_state(base_snapshot)
        restored_snapshot = runner.snapshot_fast_state()

        self.assertEqual(
            len(restored_snapshot["runtime_state"]["pending_feedback"]),
            len(base_snapshot["runtime_state"]["pending_feedback"]),
        )
        self.assertEqual(
            len(restored_snapshot["runtime_state"]["pending_growth_proposals"]),
            len(base_snapshot["runtime_state"]["pending_growth_proposals"]),
        )

    def test_evaluate_laminated_benchmark_returns_baseline_and_slice_history(self) -> None:
        result = evaluate_laminated_benchmark(
            benchmark_id="B2S1",
            task_key="task_a",
            mode="visible",
            seed=13,
            capability_policy="self-selected",
            initial_cycle_budget=4,
            safety_limit=10,
        )

        self.assertEqual(result["benchmark_id"], "B2S1")
        self.assertIn("laminated_summary", result)
        self.assertIn("laminated_run", result)
        self.assertGreaterEqual(len(result["laminated_run"]["slice_summaries"]), 1)
        self.assertIn(
            result["laminated_run"]["final_decision"],
            {"continue", "settle", "branch", "escalate"},
        )
        final_signal = result["laminated_run"]["final_signal"]
        self.assertIsNotNone(final_signal)
        self.assertIn("growth_authorization", final_signal)
        self.assertIn("reset_flags", final_signal)
        self.assertIn("reframe_flags", final_signal)
        first_summary = result["laminated_run"]["slice_summaries"][0]
        self.assertIn("forecast_metrics", first_summary["metadata"])
        self.assertIn("intervention_payoff_trend", first_summary["metadata"])

    def test_evaluate_laminated_benchmark_gradient_surfaces_continuous_signal(self) -> None:
        result = evaluate_laminated_benchmark(
            benchmark_id="B2S1",
            task_key="task_a",
            mode="visible",
            seed=13,
            capability_policy="self-selected",
            initial_cycle_budget=4,
            safety_limit=6,
            regulator_type="gradient",
            accuracy_threshold=0.8,
        )

        final_signal = result["laminated_run"]["final_signal"]
        self.assertIsNotNone(final_signal)
        self.assertIn("budget_target", final_signal)
        self.assertIn("pressure_level", final_signal)
        self.assertIn("execution_plan", final_signal)
