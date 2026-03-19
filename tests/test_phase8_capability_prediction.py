from __future__ import annotations

import unittest

from phase8 import NativeSubstrateSystem


class TestPhase8CapabilityPrediction(unittest.TestCase):
    def test_self_selected_prediction_shortfall_can_raise_latent_pressure(self) -> None:
        baseline = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=81,
            capability_policy="self-selected",
        )
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=81,
            capability_policy="self-selected",
        )
        for current in (baseline, system):
            current.environment.inject_signal(
                count=5,
                cycle=0,
                packet_payloads=[[1, 0, 1, 1]] * 5,
                context_bits=[0] * 5,
                task_id="task_a",
            )
            current.environment.capability_states["n0"].visible_context_trust = 0.28
        baseline.environment.tick(1)
        baseline_updated = baseline.environment.capability_states["n0"]
        runtime = system.environment.state_for("n0")
        runtime.last_prediction_confidence = 0.7
        runtime.last_prediction_expected_delta = 0.01
        runtime.last_prediction_expected_match_ratio = 0.42
        runtime.last_prediction_error_magnitude = 0.35

        system.environment.tick(1)
        updated = system.environment.capability_states["n0"]

        self.assertGreater(
            updated.latent_recruitment_pressure,
            baseline_updated.latent_recruitment_pressure,
        )
        self.assertGreaterEqual(updated.latent_support, baseline_updated.latent_support)

    def test_self_selected_strong_visible_prediction_keeps_latent_quiet(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=83,
            capability_policy="self-selected",
        )
        system.environment.inject_signal(
            count=5,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]] * 5,
            context_bits=[0] * 5,
            task_id="task_a",
        )
        runtime = system.environment.state_for("n0")
        runtime.last_prediction_confidence = 0.9
        runtime.last_prediction_expected_delta = 0.24
        runtime.last_prediction_expected_match_ratio = 0.95
        runtime.last_prediction_error_magnitude = 0.02

        system.environment.tick(1)
        updated = system.environment.capability_states["n0"]

        self.assertFalse(updated.latent_enabled)
        self.assertLess(updated.latent_recruitment_pressure, 0.05)
        self.assertEqual(updated.latent_recruitment_cycles, [])


if __name__ == "__main__":
    unittest.main()
