from __future__ import annotations

import unittest

from scripts.experiment_manifest import build_run_manifest


class TestExperimentManifest(unittest.TestCase):
    def test_build_run_manifest_surfaces_final_accuracy_and_total_slices(self) -> None:
        manifest = build_run_manifest(
            harness="laminated_phase8",
            seeds=[13],
            scenarios=["B2S1"],
            result={
                "laminated_run": {
                    "slice_summaries": [
                        {"metadata": {"final_accuracy": 0.625}},
                        {"metadata": {"final_accuracy": 0.8125}},
                    ]
                }
            },
        )

        self.assertEqual(manifest["total_slices"], 2)
        self.assertEqual(manifest["final_accuracy"], 0.8125)

    def test_build_run_manifest_skips_summary_for_suite_payload(self) -> None:
        manifest = build_run_manifest(
            harness="hidden_regime_forecasting_suite",
            seeds=[13],
            scenarios=["HR1", "HR2"],
            result={"runs": [{"benchmark_id": "HR1"}, {"benchmark_id": "HR2"}]},
        )

        self.assertNotIn("total_slices", manifest)
        self.assertNotIn("final_accuracy", manifest)


if __name__ == "__main__":
    unittest.main()
