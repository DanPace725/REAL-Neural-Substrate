from __future__ import annotations

import unittest

from scripts.occupancy_real_v3_light import (
    OccupancyRealV3LightConfig,
    run_occupancy_real_v3_light,
)


class TestOccupancyRealV3Light(unittest.TestCase):
    def test_light_runner_returns_prediction_summary(self) -> None:
        result = run_occupancy_real_v3_light(
            OccupancyRealV3LightConfig(
                csv_path="occupancy_baseline/data/occupancy_synth_v1.csv",
                selector_seed=13,
                warmup_sessions=2,
                prediction_sessions=2,
                summary_only=True,
            )
        )
        self.assertEqual(result["warmup_session_count"], 2)
        self.assertEqual(result["prediction_session_count"], 2)
        self.assertIn("accuracy", result["prediction_summary"]["metrics"])
        self.assertIn("recent_session_accuracy", result["recent_prediction_window"])
        self.assertGreaterEqual(result["final_system_summary"]["delivery_ratio"], 0.0)


if __name__ == "__main__":
    unittest.main()
