from __future__ import annotations

import unittest

from scripts.probe_phase8_recognition_bias import (
    evaluate_phase8_recognition_bias_probe,
)


class TestPhase8RecognitionProbe(unittest.TestCase):
    def test_probe_reports_recognition_and_route_flip(self) -> None:
        result = evaluate_phase8_recognition_bias_probe(seed=17)

        promotion = result["promotion_recognition_probe"]
        route_bias = result["route_bias_probe"]

        self.assertTrue(promotion["recognized"])
        self.assertGreater(float(promotion["recognition_confidence"]), 0.0)
        self.assertEqual(promotion["dims_source"], "history")
        self.assertTrue(route_bias["route_flipped"])
        self.assertEqual(route_bias["action_without_context"], "route:n1")
        self.assertEqual(route_bias["action_with_context"], "route:n2")


if __name__ == "__main__":
    unittest.main()
