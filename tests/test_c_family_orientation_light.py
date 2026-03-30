from __future__ import annotations

import unittest

from scripts.c_family_orientation_light import (
    CFamilyOrientationLightConfig,
    run_c_family_orientation_light,
)


class TestCFamilyOrientationLight(unittest.TestCase):
    def test_orientation_then_challenge_returns_both_phases(self) -> None:
        result = run_c_family_orientation_light(
            CFamilyOrientationLightConfig(
                benchmark_id="C3S1",
                challenge_task_key="task_c",
                orientation_task_keys=("task_a",),
                mode="visible",
                regulator_type="gradient",
                initial_cycle_budget=4,
                orientation_safety_limit=2,
                challenge_safety_limit=2,
                challenge_accuracy_threshold=0.8,
            )
        )
        self.assertEqual(result["benchmark_id"], "C3S1")
        self.assertEqual(len(result["orientation_phases"]), 1)
        self.assertEqual(result["orientation_phases"][0]["task_key"], "task_a")
        self.assertEqual(result["challenge_phase"]["task_key"], "task_c")
        self.assertIn("final_accuracy", result["challenge_phase"]["result"])

    def test_masked_orientation_task_key_is_supported(self) -> None:
        result = run_c_family_orientation_light(
            CFamilyOrientationLightConfig(
                benchmark_id="C3S1",
                challenge_task_key="task_c",
                orientation_task_keys=("task_c_masked",),
                mode="visible",
                regulator_type="gradient",
                initial_cycle_budget=4,
                orientation_safety_limit=1,
                challenge_safety_limit=1,
                challenge_accuracy_threshold=0.8,
            )
        )
        self.assertEqual(result["orientation_phases"][0]["task_key"], "task_c_masked")


if __name__ == "__main__":
    unittest.main()
