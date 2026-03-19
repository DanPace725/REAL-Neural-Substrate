from __future__ import annotations

import unittest

from scripts.diagnose_benchmark_node_probe import evaluate_benchmark_node_probe


class TestBenchmarkNodeProbe(unittest.TestCase):
    def test_benchmark_node_probe_runs_b2_self_selected_short_cycle_limit(self) -> None:
        result = evaluate_benchmark_node_probe(
            seed=13,
            benchmark_id="B2",
            task_keys=("task_a",),
            method_id="self-selected",
            cycle_limit=8,
        )

        self.assertEqual(result["benchmark_id"], "B2")
        self.assertEqual(result["method_id"], "self-selected")
        self.assertIn("task_a", result["task_runs"])
        task_run = result["task_runs"]["task_a"]
        self.assertTrue(task_run["focus_nodes"])
        self.assertEqual(task_run["focus_nodes"][0], "n0")
        first_node = task_run["focus_nodes"][0]
        self.assertIn(first_node, task_run["nodes"])
        self.assertTrue(task_run["nodes"][first_node]["timeline"])
        self.assertIn("first_latent_capability_cycle", task_run["nodes"][first_node]["summary"])
        self.assertIn("mean_source_sequence_context_confidence", task_run["nodes"][first_node]["summary"])
        self.assertIn("pre_sequence_guidance_match_rate", task_run["nodes"][first_node]["summary"])
        self.assertIn("first_prediction_cycle", task_run["nodes"][first_node]["summary"])
        self.assertIn("predicted_route_entry_count", task_run["nodes"][first_node]["summary"])
        self.assertIn("mean_prediction_confidence", task_run["nodes"][first_node]["summary"])


if __name__ == "__main__":
    unittest.main()
