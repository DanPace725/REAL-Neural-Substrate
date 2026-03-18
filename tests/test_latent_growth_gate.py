from __future__ import annotations

import unittest

from phase8 import MorphogenesisConfig, NativeSubstrateSystem


class TestLatentGrowthGate(unittest.TestCase):
    def _growth_system(self) -> NativeSubstrateSystem:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
                "n2": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "n2": 2, "sink": 3},
            source_id="n0",
            sink_id="sink",
            selector_seed=13,
            morphogenesis_config=MorphogenesisConfig(
                enabled=True,
                checkpoint_interval=6,
                max_dynamic_nodes=2,
                surplus_window=2,
                contradiction_threshold=0.2,
                overload_threshold=0.2,
                atp_surplus_threshold=0.4,
                context_resolution_growth_gate=0.55,
                routing_feedback_gate=0.0,
            ),
        )
        node_spec = system.topology_state.node_specs["n0"]
        node_spec.surplus_streak = 3
        node_spec.positive_energy_streak = 3
        node_spec.net_energy_recent = 0.20
        node_spec.value_recent = 0.28
        system.environment.current_cycle = 6
        system.global_cycle = 6
        return system

    def test_growth_gate_uses_context_growth_ready_not_promotion_ready(self) -> None:
        system = self._growth_system()

        blocked_observation = {
            "atp_ratio": 1.0,
            "contradiction_pressure": 0.8,
            "queue_pressure": 0.0,
            "oldest_packet_age": 0.0,
            "ingress_backlog": 0.0,
            "energy_surplus": 0.3,
            "head_has_task": 1.0,
            "head_has_context": 0.0,
            "effective_context_confidence": 0.70,
            "context_promotion_ready": 1.0,
            "context_growth_ready": 0.0,
        }
        allowed_observation = dict(blocked_observation)
        allowed_observation["context_growth_ready"] = 1.0

        system.environment.observe_local = lambda node_id: dict(blocked_observation)
        blocked = system.environment.growth_action_specs("n0")

        system.environment.observe_local = lambda node_id: dict(allowed_observation)
        allowed = system.environment.growth_action_specs("n0")

        self.assertFalse(any(action["action"].startswith("bud_") for action in blocked))
        self.assertTrue(any(action["action"].startswith("bud_") for action in allowed))


if __name__ == "__main__":
    unittest.main()
