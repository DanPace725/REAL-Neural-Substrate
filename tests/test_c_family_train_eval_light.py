from __future__ import annotations

import unittest

from scripts.c_family_train_eval_light import (
    CFamilyTrainEvalLightConfig,
    run_c_family_train_eval_light,
)


class TestCFamilyTrainEvalLight(unittest.TestCase):
    def test_train_eval_split_returns_both_phases(self) -> None:
        result = run_c_family_train_eval_light(
            CFamilyTrainEvalLightConfig(
                benchmark_id="C3S1",
                task_key="task_c",
                mode="visible",
                regulator_type="gradient",
                initial_cycle_budget=4,
                train_ratio=0.5,
                train_safety_limit=2,
                eval_safety_limit=2,
                eval_feedback_fraction=0.0,
                eval_accuracy_threshold=0.8,
            )
        )
        self.assertEqual(result["benchmark_id"], "C3S1")
        self.assertGreater(result["train_signal_count"], 0)
        self.assertGreater(result["eval_signal_count"], 0)
        self.assertIn("final_accuracy", result["train_phase"])
        self.assertIn("final_accuracy", result["eval_phase"])


if __name__ == "__main__":
    unittest.main()
