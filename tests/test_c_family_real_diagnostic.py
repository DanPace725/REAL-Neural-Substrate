from __future__ import annotations

import unittest

from phase8.environment import _candidate_transforms_for_task, _expected_transform_for_task
from scripts.diagnose_c_family_real import evaluate_c_family_real_diagnostic


class TestCFamilyRealDiagnostic(unittest.TestCase):
    def test_generated_task_ids_map_to_canonical_task_families(self) -> None:
        self.assertEqual(_expected_transform_for_task("ceiling_c3_task_a", 0), "rotate_left_1")
        self.assertEqual(_expected_transform_for_task("ceiling_c4_task_b", 1), "xor_mask_0101")
        self.assertEqual(_expected_transform_for_task("ceiling_c4_task_c", 0), "xor_mask_1010")
        self.assertEqual(_expected_transform_for_task("ceiling_c3_task_c", 2), "rotate_left_1")
        self.assertEqual(_expected_transform_for_task("ceiling_c3_task_c", 3), "identity")
        self.assertEqual(
            _candidate_transforms_for_task("ceiling_c3_task_c"),
            ("xor_mask_1010", "xor_mask_0101", "rotate_left_1", "identity"),
        )

    def test_real_c_family_diagnostic_runs_single_seed(self) -> None:
        result = evaluate_c_family_real_diagnostic(
            seeds=(13,),
            benchmark_ids=("C1",),
            include_transfer=False,
        )

        self.assertEqual(result["suite"][0]["benchmark_id"], "C1")
        self.assertIn("growth-latent", result["methods"])
        self.assertIsNotNone(result["cold_start"])
        self.assertTrue(result["cold_start"]["task_aggregates"])
        self.assertTrue(result["cold_start"]["method_aggregates"])
        self.assertIsNone(result["transfer"])


if __name__ == "__main__":
    unittest.main()
