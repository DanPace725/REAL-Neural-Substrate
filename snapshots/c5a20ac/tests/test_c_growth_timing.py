from __future__ import annotations

import unittest

from scripts.diagnose_c_growth_timing import _summarize_growth_timing, evaluate_c_growth_timing


class TestCGrowthTiming(unittest.TestCase):
    def test_growth_timing_summary_tracks_promotion_growth_and_bud_cycles(self) -> None:
        records = [
            {
                "cycle": 1,
                "latent_context_available": 1.0,
                "latent_context_confidence": 0.30,
                "effective_has_context": 0.0,
                "effective_context_confidence": 0.0,
                "context_promotion_ready": 0.0,
                "context_growth_ready": 0.0,
                "source_sequence_context_confidence": 0.70,
                "source_route_context_confidence": 0.20,
                "source_feedback_context_confidence": 0.10,
                "downstream_mean_route_context_confidence": 0.10,
                "downstream_mean_feedback_context_confidence": 0.10,
                "source_atp_ratio": 0.9,
                "delta_wrong_transform_family": 1.0,
                "delta_transform_unstable_across_inferred_context_boundary": 0.0,
                "delta_delayed_correction": 0.0,
                "delta_route_wrong_transform_potentially_right": 0.0,
                "delta_route_right_transform_wrong": 0.0,
                "mean_bit_accuracy": 0.25,
                "exact_matches": 0,
                "bud_action_available": 0.0,
                "bud_action_available_count": 0,
                "bud_successes": 0,
                "dynamic_node_count": 0,
            },
            {
                "cycle": 2,
                "latent_context_available": 1.0,
                "latent_context_confidence": 0.72,
                "effective_has_context": 1.0,
                "effective_context_confidence": 0.72,
                "context_promotion_ready": 1.0,
                "context_growth_ready": 0.0,
                "source_sequence_context_confidence": 0.80,
                "source_route_context_confidence": 0.30,
                "source_feedback_context_confidence": 0.20,
                "downstream_mean_route_context_confidence": 0.20,
                "downstream_mean_feedback_context_confidence": 0.20,
                "source_atp_ratio": 0.8,
                "delta_wrong_transform_family": 0.0,
                "delta_transform_unstable_across_inferred_context_boundary": 1.0,
                "delta_delayed_correction": 0.0,
                "delta_route_wrong_transform_potentially_right": 0.0,
                "delta_route_right_transform_wrong": 0.0,
                "mean_bit_accuracy": 0.50,
                "exact_matches": 1,
                "bud_action_available": 0.0,
                "bud_action_available_count": 0,
                "bud_successes": 0,
                "dynamic_node_count": 0,
            },
            {
                "cycle": 3,
                "latent_context_available": 1.0,
                "latent_context_confidence": 0.85,
                "effective_has_context": 1.0,
                "effective_context_confidence": 0.85,
                "context_promotion_ready": 1.0,
                "context_growth_ready": 1.0,
                "source_sequence_context_confidence": 0.90,
                "source_route_context_confidence": 0.40,
                "source_feedback_context_confidence": 0.30,
                "downstream_mean_route_context_confidence": 0.25,
                "downstream_mean_feedback_context_confidence": 0.25,
                "source_atp_ratio": 0.7,
                "delta_wrong_transform_family": 0.0,
                "delta_transform_unstable_across_inferred_context_boundary": 0.0,
                "delta_delayed_correction": 1.0,
                "delta_route_wrong_transform_potentially_right": 0.0,
                "delta_route_right_transform_wrong": 0.0,
                "mean_bit_accuracy": 0.75,
                "exact_matches": 2,
                "bud_action_available": 1.0,
                "bud_action_available_count": 2,
                "bud_successes": 1,
                "dynamic_node_count": 1,
            },
        ]

        summary = _summarize_growth_timing(records)

        self.assertEqual(summary["first_context_promotion_ready_cycle"], 2)
        self.assertEqual(summary["first_context_growth_ready_cycle"], 3)
        self.assertEqual(summary["first_bud_action_available_cycle"], 3)
        self.assertEqual(summary["first_bud_success_cycle"], 3)
        self.assertEqual(summary["first_dynamic_node_cycle"], 3)
        self.assertEqual(summary["promotion_before_growth_cycle_count"], 1)

    def test_growth_timing_probe_runs_single_method_single_task(self) -> None:
        result = evaluate_c_growth_timing(
            seed=13,
            benchmark_id="C1",
            task_key="task_b",
            method_id="growth-latent",
        )

        self.assertEqual(result["benchmark_id"], "C1")
        self.assertEqual(result["task_key"], "task_b")
        self.assertEqual(result["method_id"], "growth-latent")
        self.assertTrue(result["timeline"])
        self.assertIn("first_context_growth_ready_cycle", result["summary"])


if __name__ == "__main__":
    unittest.main()
