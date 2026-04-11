from __future__ import annotations

import unittest

from phase8.adapters import LocalNodeMemoryBinding
from phase8.environment import NativeSubstrateSystem
from real_core.types import CycleEntry, GCOStatus


class TestPhase8Expectation(unittest.TestCase):
    def test_source_node_records_prediction_for_route_cycle(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=7,
        )
        system.environment.inject_signal(count=1)

        entry = system.agents["n0"].step()

        self.assertTrue(str(entry.action).startswith("route"))
        self.assertIsNotNone(entry.prediction)
        assert entry.prediction is not None
        self.assertEqual(entry.prediction.metadata.get("source"), "phase8_expectation")
        self.assertIn("anticipation", entry.state_before)
        self.assertIn("predictions", entry.state_before["anticipation"])
        self.assertIn(entry.action, entry.state_before["anticipation"]["predictions"])

    def test_expectation_model_predicts_available_route_actions(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1", "n2"),
                "n1": ("sink",),
                "n2": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "n2": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=11,
        )
        system.environment.inject_signal(count=1)
        agent = system.agents["n0"]
        available = agent.engine.actions.available_actions(history_size=0)
        observation = agent.engine.observer.observe(1)

        predictions = agent.engine.expectation_model.predict(
            observation,
            available,
            [],
            recognition=None,
            prior_coherence=None,
            substrate=agent.substrate,
        )

        route_actions = [action for action in available if str(action).startswith("route")]
        self.assertTrue(route_actions)
        for action in route_actions:
            self.assertIn(action, predictions)
            self.assertEqual(
                predictions[action].metadata.get("source"),
                "phase8_expectation",
            )

    def test_expectation_model_marks_stale_family_risk_under_hidden_task_mismatch(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=5,
        )
        agent = system.agents["n0"]
        history = [
            CycleEntry(
                cycle=index,
                action="route_transform:n1:xor_mask_1010",
                mode="guided",
                state_before={},
                state_after={},
                dimensions={},
                coherence=0.5,
                delta=0.0,
                gco=GCOStatus.PARTIAL,
                cost_secs=0.05,
            )
            for index in range(1, 5)
        ]
        observation = {
            "head_has_task": 1.0,
            "head_has_context": 0.0,
            "effective_has_context": 0.0,
            "transfer_adaptation_phase": 1.0,
            "task_transform_affinity_rotate_left_1": 1.0,
            "task_transform_affinity_xor_mask_1010": -1.0,
            "source_sequence_transform_hint_rotate_left_1": 0.9,
            "source_sequence_transform_hint_xor_mask_1010": -0.4,
            "feedback_debt_xor_mask_1010": 0.4,
            "context_feedback_debt_xor_mask_1010": 0.3,
            "support_n1": 0.5,
            "action_support_n1_rotate_left_1": 0.5,
            "action_support_n1_xor_mask_1010": 0.5,
            "progress_n1": 0.4,
            "congestion_n1": 0.1,
            "inhibited_n1": 0.0,
        }

        predictions = agent.engine.expectation_model.predict(
            observation,
            ["route_transform:n1:rotate_left_1", "route_transform:n1:xor_mask_1010"],
            history,
            recognition=None,
            prior_coherence=0.5,
            substrate=agent.substrate,
        )

        self.assertLess(
            float(
                predictions["route_transform:n1:rotate_left_1"].metadata.get(
                    "stale_family_risk",
                    0.0,
                )
            ),
            0.2,
        )
        self.assertGreater(
            float(
                predictions["route_transform:n1:xor_mask_1010"].metadata.get(
                    "stale_family_risk",
                    0.0,
                )
            ),
            0.5,
        )

    def test_memory_binding_ignores_unsupported_context_action_key(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=9,
        )
        agent = system.agents["n0"]
        binding = LocalNodeMemoryBinding(
            environment=system.environment,
            node_id="n0",
            neighbor_ids=("n1",),
            substrate=agent.substrate,
        )
        modulated = binding.modulate_observation(
            {
                "effective_has_context": 1.0,
                "effective_context_bit": 3.0,
                "progress_n1": 0.5,
                "congestion_n1": 0.1,
            },
            agent.substrate,
            cycle=1,
        )

        self.assertIn("context_action_support_n1_identity", modulated)


if __name__ == "__main__":
    unittest.main()
