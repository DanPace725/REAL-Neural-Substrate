from __future__ import annotations

import unittest

from phase8 import (
    FeedbackPulse,
    NativeSubstrateSystem,
    Phase8SliceRunner,
    build_system_for_scenario,
)
from scripts.compare_c_scale_suite import c_scale_suite_by_id
from scripts.evaluate_hidden_regime_forecasting import evaluate_hidden_regime_benchmark


class TestPhase8PulseLocalUnit(unittest.TestCase):
    def _build_small_system(self) -> NativeSubstrateSystem:
        return NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("n2",),
                "n2": ("sink",),
                "sink": (),
            },
            positions={"n0": 0, "n1": 1, "n2": 2, "sink": 3},
            source_id="n0",
            sink_id="sink",
            capability_policy="fixed-visible",
            local_unit_mode="pulse_local_unit",
        )

    def _prime_middle_packet(self, system: NativeSubstrateSystem) -> None:
        env = system.environment
        env.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[0],
            task_id="task_a",
        )
        cost = system.agents["n0"].substrate.use_cost("n1")
        routed = env.route_signal("n0", "n1", cost)
        self.assertTrue(routed["success"])

    def test_accumulator_crosses_threshold_and_cooldown_blocks_refire(self) -> None:
        system = self._build_small_system()
        self._prime_middle_packet(system)
        env = system.environment
        backend = system.agents["n1"].engine.actions

        first = backend.execute("route_transform:n2:rotate_left_1")
        self.assertFalse(first.success)
        self.assertTrue(first.result["suppressed"])
        self.assertEqual(first.result["reason"], "threshold")
        self.assertEqual(len(env.inboxes["n1"]), 1)

        second = backend.execute("route_transform:n2:rotate_left_1")
        self.assertTrue(second.success)
        self.assertEqual(len(env.inboxes["n2"]), 1)

        env.inboxes["n1"].append(
            env.create_packet(
                cycle=env.current_cycle,
                input_bits=[1, 0, 1, 1],
                payload_bits=[1, 0, 1, 1],
                context_bit=0,
                task_id="task_a",
                origin="n1",
            )
        )
        third = backend.execute("route_transform:n2:rotate_left_1")
        self.assertFalse(third.success)
        self.assertTrue(third.result["suppressed"])
        self.assertEqual(third.result["reason"], "cooldown")

        local_unit_state = env.local_unit_state_for("n1")
        self.assertEqual(local_unit_state.signal.fired_route_count, 1)
        self.assertGreaterEqual(local_unit_state.signal.suppressed_route_attempts, 2)
        self.assertEqual(local_unit_state.signal.last_fired_channel, "n2:rotate_left_1")

    def test_repeated_threshold_delays_eventually_release_route_trial(self) -> None:
        system = self._build_small_system()
        self._prime_middle_packet(system)
        env = system.environment
        backend = system.agents["n1"].engine.actions
        env.local_unit_state_for("n1").signal.base_threshold = 1.20

        release = None
        delayed_attempts = 0
        for _ in range(5):
            attempt = backend.execute("route_transform:n2:rotate_left_1")
            if not attempt.success:
                delayed_attempts += 1
            if attempt.success:
                release = attempt
                break

        self.assertIsNotNone(release)
        self.assertGreaterEqual(delayed_attempts, 1)
        self.assertEqual(len(env.inboxes["n2"]), 1)
        self.assertIn(release.result["pulse_reason"], {"ok", "delayed_release"})

    def test_ambiguous_attempt_keeps_plasticity_closed_and_raises_growth_request(self) -> None:
        system = self._build_small_system()
        self._prime_middle_packet(system)
        env = system.environment
        state = env.state_for("n1")
        state.provisional_transform_credit["rotate_left_1"] = 0.80
        state.provisional_transform_credit["xor_mask_1010"] = 0.76

        result = system.agents["n1"].engine.actions.execute("route_transform:n2:rotate_left_1")
        self.assertFalse(result.success)

        local_unit_state = env.local_unit_state_for("n1")
        self.assertLess(local_unit_state.plasticity.plasticity_gate, 0.30)
        self.assertFalse(local_unit_state.plasticity.promotion_ready)
        self.assertGreater(local_unit_state.plasticity.growth_request_pressure, 0.20)
        self.assertGreaterEqual(local_unit_state.context.unresolved_streak, 1)

    def test_plasticity_gate_damps_durable_feedback_promotion(self) -> None:
        low_gate_system = self._build_small_system()
        low_env = low_gate_system.environment
        low_env.local_unit_state_for("n1").plasticity.plasticity_gate = 0.0
        low_env.pending_feedback.append(
            FeedbackPulse(
                packet_id="low",
                edge_path=["n1->n2"],
                amount=low_env.feedback_amount,
                transform_path=["rotate_left_1"],
                context_bit=0,
                task_id="task_a",
                bit_match_ratio=1.0,
                matched_target=True,
            )
        )
        low_env.advance_feedback()
        low_transform_credit = low_env.state_for("n1").transform_credit.get("rotate_left_1", 0.0)
        low_context_credit = low_env.state_for("n1").context_transform_credit.get(
            "rotate_left_1:context_0",
            0.0,
        )

        high_gate_system = self._build_small_system()
        high_env = high_gate_system.environment
        high_env.local_unit_state_for("n1").plasticity.plasticity_gate = 1.0
        high_env.pending_feedback.append(
            FeedbackPulse(
                packet_id="high",
                edge_path=["n1->n2"],
                amount=high_env.feedback_amount,
                transform_path=["rotate_left_1"],
                context_bit=0,
                task_id="task_a",
                bit_match_ratio=1.0,
                matched_target=True,
            )
        )
        high_env.advance_feedback()
        high_transform_credit = high_env.state_for("n1").transform_credit.get("rotate_left_1", 0.0)
        high_context_credit = high_env.state_for("n1").context_transform_credit.get(
            "rotate_left_1:context_0",
            0.0,
        )

        self.assertGreater(high_transform_credit, low_transform_credit)
        self.assertGreater(high_context_credit, low_context_credit)

    def test_named_pulse_preset_applies_initial_local_unit_state(self) -> None:
        system = build_system_for_scenario(
            c_scale_suite_by_id()["C3S1"].tasks["task_a"].visible_scenario,
            seed=13,
            capability_policy="self-selected",
            local_unit_mode="pulse_local_unit",
            local_unit_preset="c_hr_overlap_tuned_v1",
        )
        local_unit_state = system.environment.local_unit_state_for("n1")
        self.assertAlmostEqual(local_unit_state.signal.base_threshold, 0.45)
        self.assertAlmostEqual(local_unit_state.signal.accumulator_decay, 0.92)
        self.assertAlmostEqual(local_unit_state.plasticity.plasticity_gate, 0.05)
        self.assertEqual(system.environment.local_unit_preset, "c_hr_overlap_tuned_v1")

    def test_c_family_slice_summary_emits_pulse_metadata_with_legacy_fallback(self) -> None:
        case = c_scale_suite_by_id()["C3S1"]
        scenario = case.tasks["task_a"].visible_scenario

        legacy_runner = Phase8SliceRunner(
            build_system_for_scenario(
                scenario,
                seed=13,
                capability_policy="self-selected",
            ),
            scenario,
            benchmark_family="C",
            task_key="task_a",
        )
        legacy_summary = legacy_runner.run_slice(slice_id=1, cycle_budget=2)
        self.assertEqual(legacy_summary.metadata["local_unit_mode"], "legacy")
        self.assertIn("pulse_fire_count", legacy_summary.metadata)
        self.assertIn("max_growth_request_pressure", legacy_summary.metadata)

        pulse_runner = Phase8SliceRunner(
            build_system_for_scenario(
                scenario,
                seed=13,
                capability_policy="self-selected",
                local_unit_mode="pulse_local_unit",
            ),
            scenario,
            benchmark_family="C",
            task_key="task_a",
        )
        pulse_summary = pulse_runner.run_slice(slice_id=1, cycle_budget=2)
        self.assertEqual(pulse_summary.metadata["local_unit_mode"], "pulse_local_unit")
        self.assertIn("pulse_fire_count", pulse_summary.metadata)
        self.assertIn("suppressed_route_attempts", pulse_summary.metadata)
        self.assertIn("mean_accumulator_level", pulse_summary.metadata)
        self.assertIn("refractory_occupancy", pulse_summary.metadata)
        self.assertIn("mean_plasticity_gate", pulse_summary.metadata)
        self.assertIn("growth_request", pulse_summary.metadata)

        tuned_runner = Phase8SliceRunner(
            build_system_for_scenario(
                scenario,
                seed=13,
                capability_policy="self-selected",
                local_unit_mode="pulse_local_unit",
                local_unit_preset="c_hr_overlap_tuned_v1",
            ),
            scenario,
            benchmark_family="C",
            task_key="task_a",
        )
        tuned_summary = tuned_runner.run_slice(slice_id=1, cycle_budget=2)
        self.assertEqual(tuned_summary.metadata["local_unit_mode"], "pulse_local_unit")
        self.assertEqual(tuned_summary.metadata["local_unit_preset"], "c_hr_overlap_tuned_v1")

    def test_hidden_regime_runner_records_local_unit_mode(self) -> None:
        result = evaluate_hidden_regime_benchmark(
            benchmark_id="HR1",
            task_key="task_a",
            observable="hidden",
            seed=13,
            capability_policy="self-selected",
            local_unit_mode="pulse_local_unit",
            local_unit_preset="c_hr_overlap_tuned_v1",
            initial_cycle_budget=2,
            safety_limit=1,
            regulator_type="heuristic",
        )

        self.assertEqual(result["local_unit_mode"], "pulse_local_unit")
        self.assertEqual(result["local_unit_preset"], "c_hr_overlap_tuned_v1")
        self.assertEqual(
            result["laminated_summary"]["local_unit_summary"]["local_unit_mode"],
            "pulse_local_unit",
        )
        self.assertEqual(
            result["laminated_summary"]["local_unit_summary"]["local_unit_preset"],
            "c_hr_overlap_tuned_v1",
        )
        slice_summary = result["laminated_run"]["slice_summaries"][-1]
        self.assertEqual(slice_summary["metadata"]["local_unit_mode"], "pulse_local_unit")
        self.assertEqual(slice_summary["metadata"]["local_unit_preset"], "c_hr_overlap_tuned_v1")
        self.assertIn("pulse_fire_count", slice_summary["metadata"])


if __name__ == "__main__":
    unittest.main()
