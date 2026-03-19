from __future__ import annotations

import unittest

from phase8 import NativeSubstrateSystem


class TestPhase8ContextUncertainty(unittest.TestCase):
    def _system_with_hidden_source_packet(self, task_id: str) -> NativeSubstrateSystem:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=91,
            capability_policy="self-selected",
        )
        system.environment.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            task_id=task_id,
        )
        return system

    def test_multistate_sequence_disagreement_softens_effective_context(self) -> None:
        system = self._system_with_hidden_source_packet("ceiling_c3_task_a")
        system.environment._latent_snapshot = lambda *args, **kwargs: {
            "available": True,
            "estimate": 0,
            "confidence": 0.82,
            "context_count": 4,
            "promotion_ready": True,
            "growth_ready": False,
            "sequence_available": True,
            "sequence_context_estimate": 1,
            "sequence_context_confidence": 0.95,
            "channel_context_estimate": {},
            "channel_context_confidence": {},
        }

        observation = system.environment.observe_local("n0")

        self.assertAlmostEqual(observation["latent_context_confidence"], 0.82, places=6)
        self.assertLess(observation["latent_resolution_weight"], 0.5)
        self.assertEqual(observation["effective_has_context"], 0.0)

    def test_multistate_sequence_agreement_preserves_effective_context(self) -> None:
        system = self._system_with_hidden_source_packet("ceiling_c3_task_a")
        system.environment._latent_snapshot = lambda *args, **kwargs: {
            "available": True,
            "estimate": 0,
            "confidence": 0.82,
            "context_count": 4,
            "promotion_ready": True,
            "growth_ready": False,
            "sequence_available": True,
            "sequence_context_estimate": 0,
            "sequence_context_confidence": 0.95,
            "channel_context_estimate": {},
            "channel_context_confidence": {},
        }

        observation = system.environment.observe_local("n0")

        self.assertAlmostEqual(observation["latent_resolution_weight"], 0.9925, places=4)
        self.assertEqual(observation["effective_has_context"], 1.0)
        self.assertEqual(observation["effective_context_bit"], 0.0)

    def test_binary_task_ignores_multistate_uncertainty_discount(self) -> None:
        system = self._system_with_hidden_source_packet("task_b")
        system.environment._latent_snapshot = lambda *args, **kwargs: {
            "available": True,
            "estimate": 1,
            "confidence": 0.82,
            "context_count": 2,
            "promotion_ready": True,
            "growth_ready": False,
            "sequence_available": True,
            "sequence_context_estimate": 0,
            "sequence_context_confidence": 0.95,
            "channel_context_estimate": {},
            "channel_context_confidence": {},
        }

        observation = system.environment.observe_local("n0")

        self.assertEqual(observation["latent_resolution_weight"], 1.0)
        self.assertEqual(observation["effective_has_context"], 1.0)
        self.assertEqual(observation["effective_context_bit"], 1.0)


if __name__ == "__main__":
    unittest.main()
