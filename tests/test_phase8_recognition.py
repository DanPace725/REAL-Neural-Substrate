from __future__ import annotations

import unittest

from phase8.environment import NativeSubstrateSystem
from real_core.patterns import ConstraintPattern
from real_core.types import (
    CycleEntry,
    GCOStatus,
    LocalPrediction,
    RecognitionMatch,
    RecognitionState,
    SelectionContext,
)


class TestPhase8Recognition(unittest.TestCase):
    def test_node_agent_records_pattern_recognition_from_promoted_substrate(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=3,
        )
        agent = system.agents["n0"]
        edge_key = agent.substrate.edge_key("n1")

        for cycle in range(1, 9):
            agent.engine.memory.record(
                CycleEntry(
                    cycle=cycle,
                    action="route:n1",
                    mode="constraint",
                    state_before={"inbox_load": 1.0},
                    state_after={edge_key: 0.8},
                    dimensions={edge_key: 0.8},
                    coherence=0.82,
                    delta=0.05,
                    gco=GCOStatus.PARTIAL,
                    cost_secs=0.04,
                )
            )

        agent.engine._run_consolidation()
        entry = agent.engine.run_cycle(9)

        self.assertIsNotNone(entry.recognition)
        assert entry.recognition is not None
        self.assertTrue(entry.recognition.matches)
        self.assertEqual(entry.recognition.matches[0].source, "route_attractor")
        self.assertEqual(entry.recognition.metadata.get("dims_source"), "history")
        self.assertIn("recognition", entry.state_before)

    def test_phase8_selector_uses_recognized_route_attractor_as_small_route_bias(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1", "n2"),
                "n1": ("sink",),
                "n2": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "n2": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=17,
        )
        system.environment.inject_signal(count=1)
        agent = system.agents["n0"]
        agent.substrate.seed_support(("n1", "n2"), value=0.6)
        agent.substrate.add_pattern(
            ConstraintPattern(
                dim_scores={
                    agent.substrate.edge_key("n1"): 0.25,
                    agent.substrate.edge_key("n2"): 0.85,
                },
                dim_trends={
                    agent.substrate.edge_key("n1"): 0.0,
                    agent.substrate.edge_key("n2"): 0.08,
                },
                valence=0.7,
                strength=0.9,
                coherence_level=0.8,
                source="route_attractor",
            )
        )
        available = agent.engine.actions.available_actions(history_size=0)
        action_without_context, _ = agent.engine.selector.select(available, history=[])
        context = SelectionContext(
            cycle=1,
            recognition=RecognitionState(
                confidence=0.92,
                novelty=0.1,
                matches=[
                    RecognitionMatch(
                        label="route_attractor:0",
                        score=0.94,
                        source="route_attractor",
                        strength=0.9,
                        metadata={"pattern_index": 0},
                    )
                ],
            ),
        )

        action_with_context, mode = agent.engine.selector.select_with_context(
            available,
            history=[],
            context=context,
        )

        self.assertEqual(action_without_context, "route:n1")
        self.assertEqual(action_with_context, "route:n2")
        self.assertEqual(mode, "guided")

    def test_phase8_selector_uses_context_transform_recognition_as_base_transform_bias(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1", "n2"),
                "n1": ("sink",),
                "n2": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "n2": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=17,
        )
        agent = system.agents["n0"]
        agent.substrate.add_pattern(
            ConstraintPattern(
                dim_scores={
                    agent.substrate.action_key("n1", "rotate_left_1"): 0.25,
                    agent.substrate.action_key("n2", "rotate_left_1"): 0.35,
                    agent.substrate.context_action_key("n2", "rotate_left_1", 0): 0.85,
                },
                dim_trends={
                    agent.substrate.action_key("n1", "rotate_left_1"): 0.0,
                    agent.substrate.action_key("n2", "rotate_left_1"): 0.03,
                    agent.substrate.context_action_key("n2", "rotate_left_1", 0): 0.08,
                },
                valence=0.7,
                strength=0.9,
                coherence_level=0.8,
                source="context_transform_attractor",
            )
        )
        context = SelectionContext(
            cycle=1,
            recognition=RecognitionState(
                confidence=0.88,
                novelty=0.08,
                matches=[
                    RecognitionMatch(
                        label="context_transform_attractor:0",
                        score=0.91,
                        source="context_transform_attractor",
                        strength=0.9,
                        metadata={"pattern_index": 0},
                    )
                ],
            ),
        )

        agent.engine.selector._current_selection_context = context
        try:
            bias = agent.engine.selector._recognized_transform_bias(
                "n2",
                "rotate_left_1",
                None,
            )
        finally:
            agent.engine.selector._current_selection_context = None

        self.assertGreater(bias, 0.0)

    def test_phase8_selector_requires_local_evidence_to_activate_transform_recognition(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1", "n2"),
                "n1": ("sink",),
                "n2": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "n2": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=17,
        )
        agent = system.agents["n0"]
        context = SelectionContext(
            cycle=1,
            recognition=RecognitionState(
                confidence=0.88,
                novelty=0.08,
                matches=[
                    RecognitionMatch(
                        label="context_transform_attractor:0",
                        score=0.91,
                        source="context_transform_attractor",
                        strength=0.9,
                        metadata={"pattern_index": 0},
                    )
                ],
            ),
        )
        agent.substrate.add_pattern(
            ConstraintPattern(
                dim_scores={
                    agent.substrate.action_key("n1", "rotate_left_1"): 0.25,
                    agent.substrate.action_key("n2", "rotate_left_1"): 0.35,
                    agent.substrate.context_action_key("n2", "rotate_left_1", 0): 0.85,
                },
                dim_trends={
                    agent.substrate.action_key("n1", "rotate_left_1"): 0.0,
                    agent.substrate.action_key("n2", "rotate_left_1"): 0.03,
                    agent.substrate.context_action_key("n2", "rotate_left_1", 0): 0.08,
                },
                valence=0.7,
                strength=0.9,
                coherence_level=0.8,
                source="context_transform_attractor",
            )
        )

        original_observe = system.environment.observe_local
        try:
            agent.engine.selector._current_selection_context = context
            system.environment.observe_local = lambda node_id: {
                "effective_has_context": 1.0,
                "effective_context_bit": 0.0,
                "effective_context_confidence": 1.0,
                "feedback_credit_rotate_left_1": 0.0,
                "context_feedback_credit_rotate_left_1": 0.0,
                "history_transform_evidence_rotate_left_1": 0.0,
            }
            without_evidence = agent.engine.selector.debug_route_score_breakdown(
                "route_transform:n2:rotate_left_1",
                history=[],
            )
            system.environment.observe_local = lambda node_id: {
                "effective_has_context": 1.0,
                "effective_context_bit": 0.0,
                "effective_context_confidence": 1.0,
                "feedback_credit_rotate_left_1": 0.45,
                "context_feedback_credit_rotate_left_1": 0.35,
                "history_transform_evidence_rotate_left_1": 0.2,
            }
            with_evidence = agent.engine.selector.debug_route_score_breakdown(
                "route_transform:n2:rotate_left_1",
                history=[],
            )
        finally:
            system.environment.observe_local = original_observe
            agent.engine.selector._current_selection_context = None

        self.assertEqual(without_evidence["recognition_transform_term"], 0.0)
        self.assertEqual(
            without_evidence["recognition_transform_confirmation_term"],
            0.0,
        )
        self.assertGreater(with_evidence["recognition_transform_term"], 0.0)
        self.assertGreater(
            with_evidence["recognition_transform_confirmation_term"],
            0.0,
        )

    def test_phase8_selector_uses_prediction_context_as_small_route_bias(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1", "n2"),
                "n1": ("sink",),
                "n2": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "n2": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=17,
        )
        system.environment.inject_signal(count=1)
        agent = system.agents["n0"]
        agent.substrate.seed_support(("n1", "n2"), value=0.6)
        available = agent.engine.actions.available_actions(history_size=0)
        action_without_context, _ = agent.engine.selector.select(available, history=[])
        context = SelectionContext(
            cycle=1,
            prior_coherence=0.5,
            predictions={
                "route:n1": LocalPrediction(
                    expected_delta=-0.05,
                    expected_coherence=0.46,
                    confidence=0.4,
                    uncertainty=0.4,
                ),
                "route:n2": LocalPrediction(
                    expected_delta=0.35,
                    expected_coherence=0.88,
                    confidence=0.95,
                    uncertainty=0.05,
                ),
            },
        )

        action_with_context, mode = agent.engine.selector.select_with_context(
            available,
            history=[],
            context=context,
        )

        self.assertEqual(action_without_context, "route:n1")
        self.assertEqual(action_with_context, "route:n2")
        self.assertEqual(mode, "guided")


if __name__ == "__main__":
    unittest.main()
