from __future__ import annotations

import unittest

from scripts.diagnose_b_to_c_carryover import diagnose_b_to_c_carryover


class TestBToCCarryoverDiagnosis(unittest.TestCase):
    def test_diagnosis_reports_context_cases_for_all_carryover_modes(self) -> None:
        result = diagnose_b_to_c_carryover(seeds=(13,))

        self.assertEqual(result["train_scenario"], "cvt1_task_b_stage1")
        self.assertEqual(result["transfer_scenario"], "cvt1_task_c_stage1")
        case = result["results"][0]
        self.assertIn("carryover_modes", case)
        for carryover_mode in ("none", "substrate", "full"):
            self.assertIn(carryover_mode, case["carryover_modes"])
            context_case = case["carryover_modes"][carryover_mode]["context_0"]
            self.assertIn("carryover_summary", context_case)
            self.assertIn("chosen_breakdown", context_case)
            self.assertIn("state_before", context_case)
            self.assertEqual(context_case["expected_transform"], "xor_mask_1010")
            self.assertIn(
                "rotate_left_1",
                context_case["state_before"]["transform_fields"],
            )


if __name__ == "__main__":
    unittest.main()
