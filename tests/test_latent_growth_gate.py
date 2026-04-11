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

    def test_growth_gate_blocks_idle_recent_latent_task_growth(self) -> None:
        system = self._growth_system()

        blocked_observation = {
            "atp_ratio": 1.0,
            "contradiction_pressure": 0.8,
            "queue_pressure": 0.0,
            "oldest_packet_age": 0.0,
            "ingress_backlog": 0.0,
            "energy_surplus": 0.3,
            "head_has_task": 0.0,
            "head_has_context": 0.0,
            "effective_context_confidence": 0.0,
            "context_promotion_ready": 0.0,
            "context_growth_ready": 0.0,
            "recent_latent_task_active": 1.0,
            "recent_latent_task_age": 0.0,
            "recent_latent_has_context": 1.0,
            "recent_latent_context_confidence": 0.95,
            "recent_latent_promotion_ready": 1.0,
            "recent_latent_growth_ready": 1.0,
        }
        allowed_observation = dict(blocked_observation)
        allowed_observation["recent_latent_task_active"] = 0.0

        system.environment.observe_local = lambda node_id: dict(blocked_observation)
        blocked = system.environment.growth_action_specs("n0")

        system.environment.observe_local = lambda node_id: dict(allowed_observation)
        allowed = system.environment.growth_action_specs("n0")

        self.assertFalse(any(action["action"].startswith("bud_") for action in blocked))
        self.assertTrue(any(action["action"].startswith("bud_") for action in allowed))

    def test_initiate_authorization_opens_growth_without_high_request_pressure(self) -> None:
        system = self._growth_system()
        capability = system.environment.capability_states["n0"]
        capability.growth_enabled = False
        capability.growth_support = 0.12
        capability.growth_recruitment_pressure = 0.04
        capability.growth_stabilization_readiness = 0.52
        system.environment.slow_growth_authorization = "initiate"

        observation = {
            "atp_ratio": 1.0,
            "contradiction_pressure": 0.8,
            "queue_pressure": 0.0,
            "oldest_packet_age": 0.0,
            "ingress_backlog": 0.0,
            "energy_surplus": 0.3,
            "head_has_task": 1.0,
            "head_has_context": 1.0,
            "effective_context_confidence": 0.9,
            "context_promotion_ready": 1.0,
            "context_growth_ready": 1.0,
        }

        system.environment.observe_local = lambda node_id: dict(observation)
        actions = system.environment.growth_action_specs("n0")

        self.assertTrue(any(action["action"].startswith("bud_") for action in actions))

    def test_authorize_honors_bottom_up_request_without_stricter_second_gate(self) -> None:
        system = self._growth_system()
        capability = system.environment.capability_states["n0"]
        capability.growth_enabled = False
        capability.growth_support = 0.12
        capability.growth_recruitment_pressure = 0.38
        capability.growth_stabilization_readiness = 0.20
        system.environment.slow_growth_authorization = "authorize"

        observation = {
            "atp_ratio": 1.0,
            "contradiction_pressure": 0.8,
            "queue_pressure": 0.0,
            "oldest_packet_age": 0.0,
            "ingress_backlog": 0.0,
            "energy_surplus": 0.3,
            "head_has_task": 1.0,
            "head_has_context": 1.0,
            "effective_context_confidence": 0.9,
            "context_promotion_ready": 1.0,
            "context_growth_ready": 1.0,
        }

        system.environment.observe_local = lambda node_id: dict(observation)
        actions = system.environment.growth_action_specs("n0")

        self.assertTrue(any(action["action"].startswith("bud_") for action in actions))

    def test_growth_intent_pressure_persists_across_short_dips(self) -> None:
        system = self._growth_system()
        capability = system.environment.capability_states["n0"]
        capability.growth_enabled = False
        capability.growth_support = 0.12
        capability.growth_recruitment_pressure = 0.40
        capability.growth_stabilization_readiness = 0.36

        observation = {
            "atp_ratio": 1.0,
            "contradiction_pressure": 0.55,
            "queue_pressure": 0.15,
            "oldest_packet_age": 0.0,
            "ingress_backlog": 0.0,
            "energy_surplus": 0.2,
            "head_has_task": 1.0,
            "head_has_context": 1.0,
            "effective_context_confidence": 0.8,
            "context_promotion_ready": 1.0,
            "context_growth_ready": 1.0,
        }

        system.environment.observe_local = lambda node_id: dict(observation)
        first = system.environment._refresh_growth_intent("n0")
        self.assertTrue(first.requested)
        first_cycle = first.request_cycle

        capability.growth_recruitment_pressure = 0.18
        capability.growth_stabilization_readiness = 0.18
        system.environment.current_cycle += 3
        second = system.environment._refresh_growth_intent("n0")

        self.assertTrue(second.requested)
        self.assertGreaterEqual(second.request_cycle, first_cycle)
        self.assertGreaterEqual(second.request_pressure, 0.35)

    def test_authorize_latches_request_and_bypasses_context_gate_for_requesting_node(self) -> None:
        system = self._growth_system()
        capability = system.environment.capability_states["n0"]
        capability.growth_enabled = False
        capability.growth_support = 0.12
        capability.growth_recruitment_pressure = 0.52
        capability.growth_stabilization_readiness = 0.42
        system.environment.slow_growth_authorization = "authorize"

        blocked_observation = {
            "atp_ratio": 1.0,
            "contradiction_pressure": 0.8,
            "queue_pressure": 0.0,
            "oldest_packet_age": 0.0,
            "ingress_backlog": 0.0,
            "energy_surplus": 0.3,
            "head_has_task": 1.0,
            "head_has_context": 0.0,
            "effective_context_confidence": 0.0,
            "context_promotion_ready": 0.0,
            "context_growth_ready": 0.0,
        }

        system.environment.observe_local = lambda node_id: dict(blocked_observation)
        system.environment._apply_growth_authorization_to_intents("authorize")
        actions = system.environment.growth_action_specs("n0")

        self.assertTrue(any(action["action"].startswith("bud_") for action in actions))


if __name__ == "__main__":
    unittest.main()
