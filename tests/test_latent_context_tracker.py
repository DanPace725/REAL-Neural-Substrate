from __future__ import annotations

import unittest

from phase8.environment import (
    LatentContextTracker,
    _candidate_transforms_for_task,
    _context_threshold_scale,
    _expected_transform_for_task,
)


class TestLatentContextTracker(unittest.TestCase):
    def test_context_threshold_scale_preserves_binary_and_relaxes_multistate(self) -> None:
        self.assertEqual(_context_threshold_scale(2), 1.0)
        self.assertLess(_context_threshold_scale(4), 1.0)

    def test_binary_task_mapping_still_resolves_original_contexts(self) -> None:
        tracker = LatentContextTracker()
        for cycle in range(1, 4):
            tracker.record_feedback(
                "task_b",
                "xor_mask_0101",
                bit_match_ratio=1.0,
                credit_signal=1.0,
            )
            tracker.observe_task("task_b", cycle)

        snapshot = tracker.snapshot("task_b")

        self.assertEqual(snapshot["estimate"], 1)
        self.assertEqual(snapshot["context_count"], 2)
        self.assertEqual(snapshot["promotion_threshold"], 0.78)
        self.assertIn(0, snapshot["channel_context_evidence"]["downstream_feedback"])
        self.assertIn(1, snapshot["channel_context_evidence"]["downstream_feedback"])
        self.assertEqual(_expected_transform_for_task("task_b", 1), "xor_mask_0101")

    def test_generated_c3_mapping_exposes_identity_as_valid_contextual_transform(self) -> None:
        tracker = LatentContextTracker()
        for cycle in range(1, 4):
            tracker.record_feedback(
                "ceiling_c3_task_a",
                "identity",
                bit_match_ratio=1.0,
                credit_signal=1.0,
            )
            tracker.observe_task("ceiling_c3_task_a", cycle)

        snapshot = tracker.snapshot("ceiling_c3_task_a")

        self.assertEqual(snapshot["estimate"], 3)
        self.assertEqual(snapshot["context_count"], 4)
        self.assertIn("identity", _candidate_transforms_for_task("ceiling_c3_task_a"))
        self.assertEqual(_expected_transform_for_task("ceiling_c3_task_a", 3), "identity")
        self.assertIn(3, snapshot["channel_context_evidence"]["downstream_feedback"])

    def test_generated_c3_sequence_context_uses_two_step_parity_state(self) -> None:
        tracker = LatentContextTracker()
        tracker.observe_packet("ceiling_c3_task_a", "p1", [1, 0, 0, 0])
        tracker.observe_packet("ceiling_c3_task_a", "p2", [1, 1, 0, 0])
        tracker.observe_packet("ceiling_c3_task_a", "p3", [0, 0, 0, 0])

        snapshot = tracker.snapshot("ceiling_c3_task_a")

        self.assertEqual(snapshot["sequence_context_estimate"], 2)
        self.assertGreater(snapshot["sequence_context_confidence"], 0.0)
        self.assertEqual(_expected_transform_for_task("ceiling_c3_task_a", 2), "xor_mask_0101")

    def test_multistate_promotion_threshold_is_cardinality_aware(self) -> None:
        tracker = LatentContextTracker()
        state = tracker._state_for("ceiling_c3_task_c")
        assert state is not None
        state.context_evidence_by_channel["downstream_feedback"] = {
            0: 0.05,
            1: 0.12,
            2: 0.62,
            3: 0.05,
        }
        tracker._recompute(state)
        tracker.observe_task("ceiling_c3_task_c", 1)
        snapshot = tracker.observe_task("ceiling_c3_task_c", 2)

        self.assertGreater(snapshot["confidence"], 0.55)
        self.assertLess(snapshot["confidence"], 0.78)
        self.assertLess(snapshot["promotion_threshold"], 0.78)
        self.assertTrue(snapshot["promotion_ready"])
        self.assertEqual(snapshot["growth_promotion_threshold"], 0.78)
        self.assertFalse(snapshot["growth_ready"])


if __name__ == "__main__":
    unittest.main()
