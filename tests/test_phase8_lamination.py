from __future__ import annotations

import unittest

from phase8 import (
    FeedbackPulse,
    Phase8SliceRunner,
    SignalPacket,
    build_system_for_scenario,
)
from phase8.environment import _apply_transform, _expected_transform_for_task
from real_core import RegulatorySignal, SliceExecutionPlan
from scripts.compare_a_scale_suite import a_scale_suite_by_id
from scripts.compare_b_scale_suite import b_scale_suite_by_id
from scripts.compare_c_scale_suite import c_scale_suite_by_id
from scripts.evaluate_laminated_phase8 import evaluate_laminated_benchmark


class TestPhase8Lamination(unittest.TestCase):
    def test_source_sequence_context_can_be_disabled_for_a_family_runs(self) -> None:
        case = a_scale_suite_by_id()["A1"]
        scenario = case.tasks["task_a"].visible_scenario
        system = build_system_for_scenario(
            scenario,
            seed=13,
            capability_policy="self-selected",
            source_sequence_context_enabled=False,
        )
        env = system.environment
        packet = SignalPacket(
            packet_id="a1-seq-off",
            origin=env.source_id,
            target=env.sink_id,
            created_cycle=0,
            input_bits=[1, 0, 0, 1],
            payload_bits=[1, 0, 0, 1],
            context_bit=0,
            task_id="task_a",
        )
        env.inboxes[env.source_id].append(packet)

        observation = env.observe_local(env.source_id)

        self.assertEqual(observation["source_sequence_available"], 0.0)
        self.assertEqual(observation["source_sequence_context_confidence"], 0.0)

    def test_c_task_layer1_requires_explicit_family_enablement(self) -> None:
        case = c_scale_suite_by_id()["C3S1"]
        scenario = case.tasks["task_a"].visible_scenario
        system = build_system_for_scenario(
            scenario,
            seed=13,
            capability_policy="self-selected",
            c_task_layer1_enabled=False,
            c_task_layer1_mode="communicative",
        )
        env = system.environment
        packet = SignalPacket(
            packet_id="c-disabled",
            origin=env.source_id,
            target=env.sink_id,
            created_cycle=0,
            input_bits=[1, 0, 0, 1],
            payload_bits=[1, 0, 0, 1],
            context_bit=0,
            task_id="task_a",
        )
        env.inboxes[env.source_id].append(packet)

        observation = env.observe_local(env.source_id)

        self.assertEqual(observation["c_task_layer1_active"], 0.0)

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
        self.assertIn("exact_match_rate", summary.metadata)
        self.assertIn("mean_bit_accuracy", summary.metadata)
        self.assertIn("floor_accuracy", summary.metadata)
        self.assertIn("worst_context_accuracy", summary.metadata)
        self.assertIn("context_exact_accuracy", summary.metadata)
        self.assertIn("context_bit_accuracy", summary.metadata)
        self.assertIn("mean_provisional_context_ambiguity", summary.metadata)
        self.assertIn("max_provisional_context_ambiguity", summary.metadata)
        self.assertIn("mean_transform_commitment_margin", summary.metadata)
        self.assertIn("source_sequence_context_estimate", summary.metadata)
        self.assertIn("source_sequence_context_confidence", summary.metadata)
        self.assertIn("source_route_context_estimate", summary.metadata)
        self.assertIn("source_route_context_confidence", summary.metadata)
        self.assertIn("source_feedback_context_estimate", summary.metadata)
        self.assertIn("source_feedback_context_confidence", summary.metadata)
        self.assertIn("hidden_packet_mean_provisional_context_ambiguity", summary.metadata)
        self.assertIn("hidden_packet_min_transform_commitment_margin", summary.metadata)
        self.assertIn("source_route_breakdown", summary.metadata)
        self.assertIsInstance(summary.metadata["source_route_breakdown"], dict)
        self.assertIn("forecast_metrics", summary.metadata)
        self.assertIn("intervention_payoff_trend", summary.metadata)
        self.assertIn("forecast_entry_count", summary.metadata["forecast_metrics"])
        self.assertIn("growth_request", summary.metadata)
        self.assertNotIn("capability_states", summary.metadata["growth_request"])
        self.assertIn("blocked_reason_counts", summary.metadata["growth_request"])
        self.assertIn("authorized_stall_slices", summary.metadata["growth_request"])
        expected_exact_rate = (
            float(summary.cost_summary["exact_matches"])
            / max(int(summary.metadata["packets_evaluated"]), 1)
        )
        self.assertAlmostEqual(summary.metadata["final_accuracy"], expected_exact_rate, places=4)
        self.assertAlmostEqual(summary.metadata["exact_match_rate"], expected_exact_rate, places=4)
        self.assertEqual(summary.context_accuracy, summary.metadata["context_exact_accuracy"])

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
                max_atp=2.0,
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
        self.assertEqual(runner.system.environment.max_atp, 2.0)
        self.assertEqual(runner.system.max_atp, 2.0)
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

    def test_force_expected_transform_at_sink_overrides_final_transform_but_keeps_trace(self) -> None:
        case = b_scale_suite_by_id()["B2S1"]
        scenario = case.tasks["task_a"].visible_scenario
        system = build_system_for_scenario(
            scenario,
            seed=13,
            capability_policy="self-selected",
            force_expected_transform_at_sink=True,
        )
        env = system.environment
        pre_sink = next(
            node_id
            for node_id, neighbors in env.adjacency.items()
            if env.sink_id in neighbors and node_id != env.source_id
        )
        input_bits = [1, 0, 0, 0]
        expected_transform = _expected_transform_for_task("task_a", 0)
        self.assertIsNotNone(expected_transform)
        target_bits = _apply_transform(input_bits, expected_transform)
        packet = env.create_packet(
            cycle=0,
            input_bits=input_bits,
            context_bit=0,
            task_id="task_a",
            target_bits=target_bits,
        )
        env.inboxes[pre_sink].append(packet)

        result = env.route_signal(pre_sink, env.sink_id, 0.01, transform_name="identity")

        delivered = env.delivered_packets[-1]
        self.assertTrue(result["forced_transform_applied"])
        self.assertEqual(result["chosen_transform"], "identity")
        self.assertEqual(result["expected_transform"], expected_transform)
        self.assertEqual(delivered.selected_transform_trace[-1], "identity")
        self.assertEqual(delivered.transform_trace[-1], expected_transform)
        self.assertTrue(delivered.forced_transform_applied)
        self.assertEqual(delivered.forced_from_transform, "identity")
        self.assertEqual(delivered.expected_transform_at_delivery, expected_transform)
        self.assertEqual(delivered.substrate_matched_target, False)
        self.assertLess(float(delivered.substrate_bit_match_ratio or 0.0), 1.0)
        self.assertTrue(delivered.matched_target)

    def test_teacher_trace_observe_records_expected_vs_actual_hop(self) -> None:
        case = b_scale_suite_by_id()["B2S1"]
        scenario = case.tasks["task_a"].visible_scenario
        system = build_system_for_scenario(
            scenario,
            seed=13,
            capability_policy="self-selected",
            teacher_trace_mode="observe",
        )
        env = system.environment
        pre_sink = next(
            node_id
            for node_id, neighbors in env.adjacency.items()
            if env.sink_id in neighbors and node_id != env.source_id
        )
        input_bits = [1, 0, 0, 0]
        expected_transform = _expected_transform_for_task("task_a", 0)
        target_bits = _apply_transform(input_bits, expected_transform)
        packet = env.create_packet(
            cycle=0,
            input_bits=input_bits,
            context_bit=0,
            task_id="task_a",
            target_bits=target_bits,
        )
        env.inboxes[pre_sink].append(packet)

        env.route_signal(pre_sink, env.sink_id, 0.01, transform_name="xor_mask_1010")

        delivered = env.delivered_packets[-1]
        self.assertEqual(len(delivered.teacher_trace), 1)
        step = delivered.teacher_trace[0]
        self.assertEqual(step["node_id"], pre_sink)
        self.assertEqual(step["neighbor_id"], env.sink_id)
        self.assertEqual(step["chosen_transform"], "xor_mask_1010")
        self.assertEqual(step["expected_transform"], "identity")
        self.assertFalse(step["forced"])
        self.assertFalse(step["payload_matches_expected"])

    def test_teacher_trace_force_on_source_uses_answer_key_transform(self) -> None:
        case = b_scale_suite_by_id()["B2S1"]
        scenario = case.tasks["task_a"].visible_scenario
        system = build_system_for_scenario(
            scenario,
            seed=13,
            capability_policy="self-selected",
            teacher_trace_mode="force",
            teacher_transform_policy="source_then_identity",
            teacher_force_nodes=["n0"],
        )
        env = system.environment
        next_node = env.adjacency[env.source_id][0]
        input_bits = [1, 0, 0, 0]
        expected_transform = _expected_transform_for_task("task_a", 0)
        packet = env.create_packet(
            cycle=0,
            input_bits=input_bits,
            context_bit=0,
            task_id="task_a",
        )
        env.inboxes[env.source_id].append(packet)

        result = env.route_signal(env.source_id, next_node, 0.01, transform_name="identity")

        forwarded = env.inboxes[next_node][-1]
        self.assertEqual(result["chosen_transform"], "identity")
        self.assertEqual(result["transform"], expected_transform)
        self.assertEqual(forwarded.selected_transform_trace[-1], "identity")
        self.assertEqual(forwarded.transform_trace[-1], expected_transform)
        self.assertEqual(len(forwarded.teacher_trace), 1)
        self.assertTrue(forwarded.teacher_trace[-1]["forced"])
        self.assertEqual(forwarded.teacher_trace[-1]["expected_transform"], expected_transform)

    def test_c_task_layer1_source_prunes_wrong_transforms(self) -> None:
        case = c_scale_suite_by_id()["C3S1"]
        scenario = case.tasks["task_a"].visible_scenario
        system = build_system_for_scenario(
            scenario,
            seed=13,
            capability_policy="self-selected",
            c_task_layer1_enabled=True,
            c_task_layer1_mode="stabilized",
        )
        env = system.environment
        packet = env.create_packet(
            cycle=0,
            input_bits=[1, 0, 0, 0],
            context_bit=0,
            task_id="task_a",
        )
        env.inboxes[env.source_id].append(packet)

        available = system.agents[env.source_id].engine.actions.available_actions(history_size=0)
        expected_transform = _expected_transform_for_task("task_a", 0)

        self.assertIn(
            f"route_transform:{env.adjacency[env.source_id][0]}:{expected_transform}",
            available,
        )
        self.assertFalse(any(action.endswith(":xor_mask_0101") for action in available))
        if expected_transform != "identity":
            self.assertFalse(any(action.startswith("route:") for action in available if ":" in action))

    def test_c_task_layer1_sets_preserve_mode_after_expected_transform(self) -> None:
        case = c_scale_suite_by_id()["C3S1"]
        scenario = case.tasks["task_a"].visible_scenario
        system = build_system_for_scenario(
            scenario,
            seed=13,
            capability_policy="self-selected",
            c_task_layer1_enabled=True,
            c_task_layer1_mode="stabilized",
        )
        env = system.environment
        next_node = env.adjacency[env.source_id][0]
        expected_transform = _expected_transform_for_task("task_a", 0)
        packet = env.create_packet(
            cycle=0,
            input_bits=[1, 0, 0, 0],
            context_bit=0,
            task_id="task_a",
        )
        env.inboxes[env.source_id].append(packet)

        env.route_signal(env.source_id, next_node, 0.01, transform_name=expected_transform)

        forwarded = env.inboxes[next_node][-1]
        self.assertTrue(forwarded.c_task_preserve_mode)
        self.assertEqual(forwarded.c_task_resolved_transform, expected_transform)
        self.assertEqual(forwarded.c_task_resolution_source, env.source_id)

    def test_c_task_layer1_downstream_preserve_mode_prefers_identity_only(self) -> None:
        case = c_scale_suite_by_id()["C3S1"]
        scenario = case.tasks["task_a"].visible_scenario
        system = build_system_for_scenario(
            scenario,
            seed=13,
            capability_policy="self-selected",
            c_task_layer1_enabled=True,
            c_task_layer1_mode="stabilized",
        )
        env = system.environment
        downstream_node = next(
            node_id
            for node_id, neighbors in env.adjacency.items()
            if node_id not in {env.source_id, env.sink_id} and neighbors
        )
        packet = SignalPacket(
            packet_id="p1",
            origin=env.source_id,
            target=env.sink_id,
            created_cycle=0,
            input_bits=[1, 0, 0, 0],
            payload_bits=[0, 0, 0, 1],
            context_bit=0,
            task_id="task_a",
            c_task_resolved_transform="rotate_left_1",
            c_task_resolution_confidence=1.0,
            c_task_preserve_mode=True,
            c_task_resolution_source=env.source_id,
            c_task_resolution_depth=1,
        )
        env.inboxes[downstream_node].append(packet)

        available = system.agents[downstream_node].engine.actions.available_actions(history_size=0)

        self.assertTrue(any(action.startswith("route:") for action in available))
        self.assertFalse(any(":rotate_left_1" in action for action in available))
        self.assertFalse(any(":xor_mask_1010" in action for action in available))
        self.assertFalse(any(":xor_mask_0101" in action for action in available))

    def test_c_task_layer1_communicative_keeps_actions_but_writes_pressures(self) -> None:
        case = c_scale_suite_by_id()["C3S1"]
        scenario = case.tasks["task_a"].visible_scenario
        system = build_system_for_scenario(
            scenario,
            seed=13,
            capability_policy="self-selected",
            c_task_layer1_enabled=True,
            c_task_layer1_mode="communicative",
        )
        env = system.environment
        next_node = env.adjacency[env.source_id][0]
        expected_transform = _expected_transform_for_task("task_a", 0)
        packet = env.create_packet(
            cycle=0,
            input_bits=[1, 0, 0, 0],
            context_bit=0,
            task_id="task_a",
        )
        env.inboxes[env.source_id].append(packet)

        available = system.agents[env.source_id].engine.actions.available_actions(history_size=0)
        self.assertIn(
            f"route_transform:{next_node}:{expected_transform}",
            available,
        )

        env.route_signal(env.source_id, next_node, 0.01, transform_name=expected_transform)

        forwarded = env.inboxes[next_node][-1]
        self.assertGreater(forwarded.c_task_preserve_pressure, 0.0)
        self.assertGreaterEqual(forwarded.c_task_resolution_confidence, 0.0)
        self.assertLessEqual(forwarded.c_task_reopen_pressure, forwarded.c_task_preserve_pressure)
        self.assertEqual(forwarded.c_task_hypothesis_transform, expected_transform)
        self.assertGreater(forwarded.c_task_hypothesis_confidence, 0.0)
        self.assertGreater(
            forwarded.c_task_transform_belief.get(expected_transform, 0.0),
            0.0,
        )
        source_context = env.local_unit_state_for(env.source_id).context
        self.assertEqual(source_context.dominant_transform, expected_transform)
        self.assertGreater(source_context.preserve_pressure, 0.0)
        self.assertGreater(source_context.transform_confidence, 0.0)
        self.assertEqual(source_context.hypothesis_transform, expected_transform)
        self.assertGreater(source_context.hypothesis_confidence, 0.0)
        source_observation = env.observe_local(env.source_id)
        self.assertGreater(source_observation["c_task_node_preserve_pressure"], 0.0)
        self.assertGreater(source_observation["c_task_node_resolution_confidence"], 0.0)
        self.assertEqual(
            source_observation[f"c_task_node_hypothesis_transform_{expected_transform}"],
            1.0,
        )
        next_observation = env.observe_local(next_node)
        self.assertGreater(next_observation["c_task_hypothesis_confidence"], 0.0)
        self.assertEqual(
            next_observation[f"c_task_hypothesis_transform_{expected_transform}"],
            1.0,
        )
        self.assertGreater(
            next_observation[f"c_task_transform_belief_{expected_transform}"],
            0.0,
        )

    def test_c_task_observation_reports_zero_transform_belief_without_evidence(self) -> None:
        case = c_scale_suite_by_id()["C3S1"]
        scenario = case.tasks["task_a"].visible_scenario
        system = build_system_for_scenario(
            scenario,
            seed=13,
            capability_policy="self-selected",
            c_task_layer1_enabled=True,
            c_task_layer1_mode="communicative",
        )
        env = system.environment
        packet = env.create_packet(
            cycle=0,
            input_bits=[1, 0, 0, 0],
            context_bit=0,
            task_id="task_a",
        )
        env.inboxes[env.source_id].append(packet)

        observation = env.observe_local(env.source_id)

        for transform_name in ("identity", "rotate_left_1", "xor_mask_1010", "xor_mask_0101"):
            self.assertEqual(observation[f"c_task_transform_belief_{transform_name}"], 0.0)
            self.assertEqual(
                observation[f"c_task_node_transform_belief_{transform_name}"],
                0.0,
            )

    def test_c_task_layer1_communicative_self_hardens_on_high_preserve_pressure(self) -> None:
        case = c_scale_suite_by_id()["C3S1"]
        scenario = case.tasks["task_a"].visible_scenario
        system = build_system_for_scenario(
            scenario,
            seed=13,
            capability_policy="self-selected",
            c_task_layer1_enabled=True,
            c_task_layer1_mode="communicative",
        )
        env = system.environment
        downstream_node = next(
            node_id
            for node_id, neighbors in env.adjacency.items()
            if node_id not in {env.source_id, env.sink_id} and neighbors
        )
        packet = SignalPacket(
            packet_id="p2",
            origin=env.source_id,
            target=env.sink_id,
            created_cycle=0,
            input_bits=[1, 0, 0, 0],
            payload_bits=[0, 0, 0, 1],
            context_bit=0,
            task_id="task_a",
            c_task_resolved_transform="rotate_left_1",
            c_task_resolution_confidence=0.8,
            c_task_preserve_mode=False,
            c_task_preserve_pressure=0.8,
            c_task_reopen_pressure=0.1,
            c_task_resolution_source=env.source_id,
            c_task_resolution_depth=1,
        )
        env.inboxes[downstream_node].append(packet)

        available = system.agents[downstream_node].engine.actions.available_actions(history_size=0)

        self.assertTrue(any(action.startswith("route:") for action in available))
        self.assertFalse(any(":rotate_left_1" in action for action in available))
        self.assertFalse(any(":xor_mask_1010" in action for action in available))
        self.assertFalse(any(":xor_mask_0101" in action for action in available))

    def test_c_task_layer1_communicative_exports_node_state_without_packet_pressures(self) -> None:
        case = c_scale_suite_by_id()["C3S1"]
        scenario = case.tasks["task_a"].visible_scenario
        system = build_system_for_scenario(
            scenario,
            seed=13,
            capability_policy="self-selected",
            c_task_layer1_enabled=True,
            c_task_layer1_mode="communicative",
        )
        env = system.environment
        downstream_node = next(
            node_id
            for node_id, neighbors in env.adjacency.items()
            if node_id not in {env.source_id, env.sink_id} and neighbors
        )
        packet = SignalPacket(
            packet_id="p2b",
            origin=env.source_id,
            target=env.sink_id,
            created_cycle=0,
            input_bits=[1, 0, 0, 0],
            payload_bits=[0, 0, 0, 1],
            context_bit=0,
            task_id="task_a",
            c_task_resolved_transform="rotate_left_1",
            c_task_resolution_confidence=0.0,
            c_task_preserve_mode=False,
            c_task_preserve_pressure=0.0,
            c_task_reopen_pressure=0.0,
            c_task_resolution_source=env.source_id,
            c_task_resolution_depth=1,
        )
        env.inboxes[downstream_node].append(packet)
        local_context = env.local_unit_state_for(downstream_node).context
        local_context.dominant_transform = "rotate_left_1"
        local_context.transform_confidence = 0.82
        local_context.preserve_pressure = 0.84
        local_context.reopen_pressure = 0.08
        local_context.preserve_mode = True
        local_context.commitment_age = 2

        observation = env.observe_local(downstream_node)

        self.assertEqual(observation["c_task_preserve_pressure"], 0.0)
        self.assertEqual(observation["c_task_reopen_pressure"], 0.0)
        self.assertEqual(observation["c_task_resolution_confidence"], 0.0)
        self.assertGreater(observation["c_task_node_preserve_pressure"], 0.8)
        self.assertGreater(observation["c_task_node_resolution_confidence"], 0.8)
        self.assertEqual(observation["c_task_node_preserve_mode"], 1.0)

    def test_c_task_layer1_communicative_does_not_self_harden_when_confidence_is_low(self) -> None:
        case = c_scale_suite_by_id()["C3S1"]
        scenario = case.tasks["task_a"].visible_scenario
        system = build_system_for_scenario(
            scenario,
            seed=13,
            capability_policy="self-selected",
            c_task_layer1_enabled=True,
            c_task_layer1_mode="communicative",
        )
        env = system.environment
        downstream_node = next(
            node_id
            for node_id, neighbors in env.adjacency.items()
            if node_id not in {env.source_id, env.sink_id} and neighbors
        )
        packet = SignalPacket(
            packet_id="p3",
            origin=env.source_id,
            target=env.sink_id,
            created_cycle=0,
            input_bits=[1, 0, 0, 0],
            payload_bits=[0, 0, 0, 1],
            context_bit=0,
            task_id="task_a",
            c_task_resolved_transform="rotate_left_1",
            c_task_resolution_confidence=0.2,
            c_task_preserve_mode=False,
            c_task_preserve_pressure=0.55,
            c_task_reopen_pressure=0.18,
            c_task_resolution_source=env.source_id,
            c_task_resolution_depth=1,
        )
        env.inboxes[downstream_node].append(packet)

        available = system.agents[downstream_node].engine.actions.available_actions(history_size=0)

        self.assertTrue(any(":rotate_left_1" in action for action in available))
        self.assertTrue(any(":xor_mask_1010" in action for action in available))

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

    def test_authorize_signal_latches_growth_intent_for_requesting_node(self) -> None:
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
        capability = runner.system.environment.capability_states[source_id]
        capability.growth_recruitment_pressure = 0.62
        capability.growth_stabilization_readiness = 0.48

        runner._apply_regulatory_signal(RegulatorySignal(growth_authorization="authorize"))

        intent = runner.system.environment.growth_intent_state_for(source_id)
        self.assertEqual(intent.authorization_state, "authorize")
        self.assertTrue(intent.requested)

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

    def test_regulatory_signal_sets_c_task_regulatory_profile_on_environment(self) -> None:
        case = c_scale_suite_by_id()["C3S1"]
        scenario = case.tasks["task_a"].visible_scenario
        runner = Phase8SliceRunner(
            build_system_for_scenario(
                scenario,
                seed=13,
                capability_policy="self-selected",
                c_task_layer1_enabled=True,
                c_task_layer1_mode="communicative",
            ),
            scenario,
            benchmark_family="C",
            task_key="task_a",
        )

        runner._apply_regulatory_signal(
            RegulatorySignal(
                metadata={
                    "c_task_regulatory_profile": {
                        "source_hardening_shift": -0.14,
                        "preserve_hardening_shift": 0.12,
                        "preserve_bonus_scale": 1.35,
                        "reopen_penalty_scale": 1.55,
                        "weak_context_boost": 0.28,
                        "atp_conservation_bias": 0.18,
                        "route_cost_scale": 0.91,
                        "recovery_scale": 1.12,
                    },
                },
            )
        )

        env = runner.system.environment
        self.assertAlmostEqual(env.slow_c_task_source_hardening_shift, -0.14)
        self.assertAlmostEqual(env.slow_c_task_preserve_hardening_shift, 0.12)
        self.assertAlmostEqual(env.slow_c_task_preserve_bonus_scale, 1.35)
        self.assertAlmostEqual(env.slow_c_task_reopen_penalty_scale, 1.55)
        self.assertAlmostEqual(env.slow_c_task_weak_context_boost, 0.28)
        self.assertAlmostEqual(env.slow_c_task_atp_conservation_bias, 0.18)
        self.assertAlmostEqual(env.slow_c_task_route_cost_scale, 0.91)
        self.assertAlmostEqual(env.slow_c_task_recovery_scale, 1.12)
        self.assertEqual(
            runner._applied_signal_meta["applied_c_task_regulatory_profile"],
            {
                "source_hardening_shift": -0.14,
                "preserve_hardening_shift": 0.12,
                "preserve_bonus_scale": 1.35,
                "reopen_penalty_scale": 1.55,
                "weak_context_boost": 0.28,
                "atp_conservation_bias": 0.18,
                "route_cost_scale": 0.91,
                "recovery_scale": 1.12,
            },
        )

    def test_regulatory_signal_applies_c_task_node_support_profile_and_atp_credit(self) -> None:
        case = c_scale_suite_by_id()["C3S1"]
        scenario = case.tasks["task_a"].visible_scenario
        runner = Phase8SliceRunner(
            build_system_for_scenario(
                scenario,
                seed=13,
                capability_policy="self-selected",
                c_task_layer1_enabled=True,
                c_task_layer1_mode="communicative",
            ),
            scenario,
            benchmark_family="C",
            task_key="task_a",
        )

        source_state = runner.system.environment.state_for(runner.system.environment.source_id)
        source_state.atp = 0.4
        source_state.reward_buffer = 0.0

        runner._apply_regulatory_signal(
            RegulatorySignal(
                metadata={
                    "c_task_node_support_profile": {
                        runner.system.environment.source_id: {
                            "atp_credit": 0.08,
                            "recovery_scale": 1.1,
                            "route_cost_scale": 0.92,
                            "source_hardening_shift": -0.05,
                            "weak_context_boost": 0.1,
                        }
                    }
                },
            )
        )

        env = runner.system.environment
        source_id = env.source_id
        self.assertIn(source_id, env.slow_c_task_node_support_profiles)
        self.assertAlmostEqual(env.state_for(source_id).atp, 0.48)
        self.assertAlmostEqual(env.state_for(source_id).reward_buffer, 0.04)
        applied = runner._applied_signal_meta["applied_c_task_node_support_profile"]
        self.assertIn(source_id, applied)
        self.assertAlmostEqual(
            float(applied[source_id]["atp_credit"]),
            0.08,
        )

    def test_c_slice_summary_exports_c_task_regime_summary(self) -> None:
        case = c_scale_suite_by_id()["C3S1"]
        scenario = case.tasks["task_a"].visible_scenario
        runner = Phase8SliceRunner(
            build_system_for_scenario(
                scenario,
                seed=13,
                capability_policy="self-selected",
                c_task_layer1_enabled=True,
                c_task_layer1_mode="communicative",
            ),
            scenario,
            benchmark_family="C",
            task_key="task_a",
        )

        summary = runner.run_slice(slice_id=1, cycle_budget=3)

        regime = summary.metadata.get("c_task_regime_summary", {})
        self.assertIsInstance(regime, dict)
        self.assertIn("packets_evaluated", regime)
        self.assertIn("context_gap", regime)
        self.assertIn("weak_context_key", regime)
        self.assertIn("source_self_hardening_ready_ratio", regime)
        self.assertIn("preserve_hardening_ready_ratio", regime)
        self.assertIn("preserve_identity_action_ratio", regime)
        self.assertIn("low_atp_route_ratio", regime)
        self.assertIn("mean_preserve_pressure", regime)
        self.assertIn("mean_reopen_pressure", regime)
        self.assertIn("preserve_mode_packet_ratio", regime)
        self.assertIn("mean_hypothesis_confidence", regime)
        self.assertIn("mean_node_hypothesis_confidence", regime)
        self.assertIn("mean_hypothesis_margin", regime)
        self.assertIn("hypothesis_alignment_ratio", regime)
        self.assertIn("node_evidence", regime)

    def test_c_slice_summary_does_not_let_applied_signal_meta_overwrite_regime_summary(self) -> None:
        case = c_scale_suite_by_id()["C3S1"]
        scenario = case.tasks["task_a"].visible_scenario
        runner = Phase8SliceRunner(
            build_system_for_scenario(
                scenario,
                seed=13,
                capability_policy="self-selected",
                c_task_layer1_enabled=True,
                c_task_layer1_mode="communicative",
            ),
            scenario,
            benchmark_family="C",
            task_key="task_a",
        )
        runner._applied_signal_meta["c_task_regime_summary"] = {
            "weak_context_key": "context_1",
            "weak_context_accuracy": 1.0,
            "strong_context_key": "context_1",
            "strong_context_accuracy": 1.0,
        }

        summary = runner.run_slice(slice_id=1, cycle_budget=3)

        regime = summary.metadata.get("c_task_regime_summary", {})
        if summary.context_accuracy:
            expected_weak = min(float(value) for value in summary.context_accuracy.values())
            expected_strong = max(float(value) for value in summary.context_accuracy.values())
            self.assertAlmostEqual(float(regime.get("weak_context_accuracy", -1.0)), expected_weak)
            self.assertAlmostEqual(float(regime.get("strong_context_accuracy", -1.0)), expected_strong)

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

    def test_snapshot_restore_preserves_world_model_state(self) -> None:
        case = b_scale_suite_by_id()["B2S1"]
        scenario = case.tasks["task_a"].visible_scenario
        runner = Phase8SliceRunner(
            build_system_for_scenario(
                scenario,
                seed=13,
                capability_policy="self-selected",
            ),
            scenario,
            benchmark_family="C",
            task_key="task_a",
        )
        runner.system.world_model_state = {
            "last_top_hypothesis": "h1",
            "last_action": "hold_open",
        }
        base_snapshot = runner.snapshot_fast_state()

        runner.system.world_model_state = {
            "last_top_hypothesis": "h3",
            "last_action": "handoff_commit",
        }
        runner.restore_fast_state(base_snapshot)
        restored_snapshot = runner.snapshot_fast_state()

        self.assertEqual(restored_snapshot["world_model_state"]["last_top_hypothesis"], "h1")

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

    def test_evaluate_laminated_benchmark_records_world_model_assistance(self) -> None:
        result = evaluate_laminated_benchmark(
            benchmark_id="C3S1",
            task_key="task_a",
            mode="visible",
            seed=13,
            capability_policy="self-selected",
            initial_cycle_budget=2,
            safety_limit=2,
            regulator_type="heuristic",
            topology_mode="bounded_overlap_13715",
            local_unit_mode="pulse_local_unit",
            local_unit_preset="c_hr_overlap_tuned_v1",
            world_model_assistance_mode="guided",
            world_model_assistance_confidence_threshold=0.20,
        )

        self.assertTrue(result["world_model_enabled"])
        self.assertEqual(result["world_model_assistance_mode"], "guided")
        first_summary = result["laminated_run"]["slice_summaries"][0]
        self.assertIn("world_model_teacher_hypothesis", first_summary["metadata"])
        self.assertIn("world_model_teacher_confidence", first_summary["metadata"])
        world_model_summary = first_summary["metadata"].get("world_model_summary", {})
        self.assertEqual(world_model_summary.get("assistance_mode"), "guided")
        self.assertIn("assistance", world_model_summary)

    def test_evaluate_laminated_benchmark_records_force_expected_transform_flag(self) -> None:
        result = evaluate_laminated_benchmark(
            benchmark_id="C3S1",
            task_key="task_a",
            mode="visible",
            seed=13,
            capability_policy="self-selected",
            initial_cycle_budget=2,
            safety_limit=1,
            regulator_type="heuristic",
            topology_mode="bounded_overlap_13715",
            local_unit_mode="pulse_local_unit",
            local_unit_preset="c_hr_overlap_tuned_v1",
            force_expected_transform_at_sink=True,
            world_model_enabled=False,
        )

        self.assertTrue(result["force_expected_transform_at_sink"])
        self.assertTrue(result["laminated_summary"]["force_expected_transform_at_sink"])
        first_summary = result["laminated_run"]["slice_summaries"][0]
        self.assertTrue(first_summary["metadata"]["force_expected_transform_at_sink"])

    def test_evaluate_laminated_benchmark_records_teacher_trace_settings(self) -> None:
        result = evaluate_laminated_benchmark(
            benchmark_id="C3S1",
            task_key="task_a",
            mode="visible",
            seed=13,
            capability_policy="self-selected",
            initial_cycle_budget=2,
            safety_limit=1,
            regulator_type="heuristic",
            topology_mode="bounded_overlap_13715",
            local_unit_mode="pulse_local_unit",
            local_unit_preset="c_hr_overlap_tuned_v1",
            teacher_trace_mode="observe",
            teacher_transform_policy="source_then_identity",
            teacher_force_nodes=["n0"],
            c_task_layer1_mode="stabilized",
            world_model_enabled=False,
        )

        self.assertEqual(result["teacher_trace_mode"], "observe")
        self.assertEqual(result["teacher_transform_policy"], "source_then_identity")
        self.assertEqual(result["teacher_force_nodes"], ["n0"])
        self.assertEqual(result["c_task_layer1_mode"], "stabilized")
        self.assertEqual(result["laminated_summary"]["teacher_trace_mode"], "observe")
        self.assertEqual(result["laminated_summary"]["c_task_layer1_mode"], "stabilized")
        first_summary = result["laminated_run"]["slice_summaries"][0]
        self.assertEqual(first_summary["metadata"]["teacher_trace_mode"], "observe")
