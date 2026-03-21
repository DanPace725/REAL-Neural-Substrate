from __future__ import annotations

import unittest

from scripts.paper_interpretability_figures import (
    b2_guidance_points,
    c_node_case_points,
    occupancy_progress_points,
)


class TestPaperInterpretabilityFigures(unittest.TestCase):
    def test_occupancy_progress_points_extract_expected_series(self) -> None:
        payload = occupancy_progress_points()

        self.assertEqual(len(payload["f1_points"]), 5)
        self.assertEqual(payload["f1_points"][0]["label"], "MLP baseline")
        self.assertAlmostEqual(payload["f1_points"][0]["value"], 0.9629629629, places=4)
        self.assertEqual(len(payload["efficiency_points"]), 3)
        self.assertAlmostEqual(payload["efficiency_mean"], 0.9915, places=4)

    def test_c_node_case_points_loads_before_and_after_payloads(self) -> None:
        payload = c_node_case_points(task_key="task_c", node_id="n3")

        self.assertEqual(payload["task_key"], "task_c")
        self.assertEqual(payload["node_id"], "n3")
        self.assertTrue(payload["before"]["timeline"])
        self.assertTrue(payload["after"]["timeline"])

    def test_b2_guidance_points_runs_short_probe(self) -> None:
        payload = b2_guidance_points(cycle_limit=8)

        self.assertEqual(payload["source_id"], "n0")
        self.assertTrue(payload["records"])
        self.assertIn("pre_sequence_guidance_match_rate", payload["summary"])


if __name__ == "__main__":
    unittest.main()
