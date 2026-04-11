from __future__ import annotations

import unittest

from phase8 import NativeSubstrateSystem


class TestLatentRouteTransformGate(unittest.TestCase):
    def _system(self) -> NativeSubstrateSystem:
        return NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=13,
        )

    def test_downstream_ambiguous_latent_packet_hides_non_identity_route_transforms(self) -> None:
        system = self._system()
        backend = system.agents["n1"].engine.actions
        system.environment.inboxes["n1"] = [object()]
        system.environment.route_available = lambda node_id, neighbor_id, cost: True
        system.environment.observe_local = lambda node_id: {
            "effective_has_context": 0.0,
            "effective_context_bit": 0.0,
            "head_has_task": 1.0,
            "head_has_context": 0.0,
            "latent_context_available": 1.0,
            "context_promotion_ready": 0.0,
        }

        actions = backend.available_actions(history_size=0)

        self.assertIn("route:sink", actions)
        self.assertIn("route_transform:sink:identity", actions)
        self.assertNotIn("route_transform:sink:rotate_left_1", actions)
        self.assertNotIn("route_transform:sink:xor_mask_1010", actions)
        self.assertNotIn("route_transform:sink:xor_mask_0101", actions)

    def test_source_pre_promotion_latent_packet_keeps_route_transform_variants(self) -> None:
        system = self._system()
        backend = system.agents["n0"].engine.actions
        system.environment.inboxes["n0"] = [object()]
        system.environment.route_available = lambda node_id, neighbor_id, cost: True
        system.environment.observe_local = lambda node_id: {
            "effective_has_context": 0.0,
            "effective_context_bit": 0.0,
            "head_has_task": 1.0,
            "head_has_context": 0.0,
            "latent_context_available": 1.0,
            "context_promotion_ready": 0.0,
        }

        actions = backend.available_actions(history_size=0)

        self.assertIn("route_transform:n1:identity", actions)
        self.assertIn("route_transform:n1:rotate_left_1", actions)
        self.assertIn("route_transform:n1:xor_mask_1010", actions)
        self.assertIn("route_transform:n1:xor_mask_0101", actions)


if __name__ == "__main__":
    unittest.main()
