from __future__ import annotations

import unittest

from phase8 import FeedbackPulse, NativeSubstrateSystem
from phase8.environment import _context_credit_key


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

    def test_downstream_packet_context_keeps_expected_non_identity_route_transforms(self) -> None:
        system = self._system()
        backend = system.agents["n1"].engine.actions
        system.environment.inboxes["n1"] = [object()]
        system.environment.route_available = lambda node_id, neighbor_id, cost: True
        system.environment.observe_local = lambda node_id: {
            "effective_has_context": 0.0,
            "effective_context_bit": 0.0,
            "packet_has_context": 1.0,
            "packet_context_bit": 1.0,
            "packet_context_confidence": 0.25,
            "head_has_task": 1.0,
            "head_has_context": 0.0,
            "latent_context_available": 1.0,
            "context_promotion_ready": 0.0,
            "expected_transform_identity": 0.0,
            "expected_transform_rotate_left_1": 0.0,
            "expected_transform_xor_mask_1010": 0.0,
            "expected_transform_xor_mask_0101": 1.0,
            "task_transform_affinity_identity": 0.0,
            "task_transform_affinity_rotate_left_1": -1.0,
            "task_transform_affinity_xor_mask_1010": 1.0,
            "task_transform_affinity_xor_mask_0101": 1.0,
            "source_sequence_transform_hint_identity": 0.0,
            "source_sequence_transform_hint_rotate_left_1": 0.0,
            "source_sequence_transform_hint_xor_mask_1010": 0.0,
            "source_sequence_transform_hint_xor_mask_0101": 0.0,
        }

        actions = backend.available_actions(history_size=0)

        self.assertIn("route:sink", actions)
        self.assertIn("route_transform:sink:identity", actions)
        self.assertIn("route_transform:sink:xor_mask_0101", actions)
        self.assertIn("route_transform:sink:xor_mask_1010", actions)
        self.assertNotIn("route_transform:sink:rotate_left_1", actions)

    def test_hidden_packet_context_exposes_context_feedback_credit(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=13,
            capability_policy="self-selected",
        )
        state = system.environment.state_for("n1")
        state.context_transform_credit[_context_credit_key("xor_mask_0101", 1)] = 0.7
        packet = system.environment.create_packet(
            cycle=0,
            input_bits=[1, 1, 0, 0],
            payload_bits=[1, 1, 0, 0],
            context_bit=1,
            task_id="task_b",
            target_bits=[1, 0, 0, 1],
        )
        system.environment.inboxes["n1"] = [packet]
        system.environment.capability_states["n1"].visible_context_trust = 0.10

        observed = system.environment.observe_local("n1")

        self.assertEqual(observed["head_has_context"], 0.0)
        self.assertEqual(observed["packet_has_context"], 1.0)
        self.assertEqual(observed["packet_context_bit"], 1.0)
        self.assertGreater(observed["context_feedback_credit_xor_mask_0101"], 0.0)

    def test_hidden_packet_context_surfaces_provisional_ambiguity(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=13,
            capability_policy="self-selected",
        )
        state = system.environment.state_for("n1")
        state.provisional_transform_credit["xor_mask_1010"] = 0.60
        state.provisional_transform_credit["xor_mask_0101"] = 0.58
        state.provisional_context_transform_credit[_context_credit_key("xor_mask_1010", 0)] = 0.62
        state.provisional_context_transform_credit[_context_credit_key("xor_mask_0101", 0)] = 0.57
        packet = system.environment.create_packet(
            cycle=0,
            input_bits=[1, 0, 1, 0],
            payload_bits=[1, 0, 1, 0],
            context_bit=0,
            task_id="task_c",
            target_bits=[0, 0, 0, 0],
        )
        system.environment.inboxes["n1"] = [packet]
        system.environment.capability_states["n1"].visible_context_trust = 0.10

        observed = system.environment.observe_local("n1")

        self.assertGreater(observed["provisional_feedback_credit_xor_mask_1010"], 0.0)
        self.assertGreater(observed["provisional_context_feedback_credit_xor_mask_1010"], 0.0)
        self.assertGreater(observed["provisional_context_ambiguity"], 0.75)
        self.assertLess(observed["transform_commitment_margin"], 0.10)

    def test_feedback_promotes_provisional_credit_faster_than_generic_credit(self) -> None:
        system = self._system()
        state = system.environment.state_for("n0")
        state.context_transform_credit[_context_credit_key("xor_mask_1010", 1)] = 0.90
        system.environment.pending_feedback = [
            FeedbackPulse(
                packet_id="p0",
                edge_path=["n0->n1"],
                amount=system.environment.feedback_amount,
                transform_path=["xor_mask_1010"],
                context_bit=0,
                task_id="task_c",
                bit_match_ratio=1.0,
                matched_target=True,
            )
        ]

        delivered = system.environment.advance_feedback()

        self.assertEqual(len(delivered), 1)
        self.assertGreater(
            state.provisional_transform_credit.get("xor_mask_1010", 0.0),
            state.transform_credit.get("xor_mask_1010", 0.0),
        )
        self.assertGreater(
            state.context_transform_credit.get(_context_credit_key("xor_mask_1010", 0), 0.0),
            state.transform_credit.get("xor_mask_1010", 0.0),
        )

    def test_selector_explores_more_when_provisional_ambiguity_is_high(self) -> None:
        system = self._system()
        selector = system.agents["n1"].engine.selector

        low = selector._local_exploration_rate(
            history=[],
            local_inbox=1,
            urgency=0.0,
            observation={
                "provisional_context_ambiguity": 0.0,
                "transform_commitment_margin": 1.0,
            },
        )
        high = selector._local_exploration_rate(
            history=[],
            local_inbox=1,
            urgency=0.0,
            observation={
                "provisional_context_ambiguity": 0.9,
                "transform_commitment_margin": 0.1,
            },
        )

        self.assertGreater(high, low)


if __name__ == "__main__":
    unittest.main()
