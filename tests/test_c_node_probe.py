from __future__ import annotations

import unittest

from scripts.diagnose_c_node_probe import evaluate_c_node_probe


class TestCNodeProbe(unittest.TestCase):
    def test_c_node_probe_runs_single_task_with_short_cycle_limit(self) -> None:
        result = evaluate_c_node_probe(
            seed=13,
            benchmark_id="C1",
            task_keys=("task_b",),
            method_id="growth-latent",
            cycle_limit=8,
        )

        self.assertEqual(result["benchmark_id"], "C1")
        self.assertEqual(result["method_id"], "growth-latent")
        self.assertIn("task_b", result["task_runs"])
        task_run = result["task_runs"]["task_b"]
        self.assertTrue(task_run["focus_nodes"])
        first_node = task_run["focus_nodes"][0]
        self.assertIn(first_node, task_run["nodes"])
        self.assertTrue(task_run["nodes"][first_node]["timeline"])
        self.assertIn("route_count", task_run["nodes"][first_node]["summary"])


if __name__ == "__main__":
    unittest.main()
