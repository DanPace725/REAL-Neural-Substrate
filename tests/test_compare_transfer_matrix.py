from __future__ import annotations

import unittest

from scripts.compare_transfer_matrix import aggregate_pair


class TestCompareTransferMatrix(unittest.TestCase):
    def test_aggregate_pair_reports_prediction_fields(self) -> None:
        results = [
            {
                "cold_summary": {
                    "exact_matches": 1,
                    "mean_bit_accuracy": 0.4,
                    "task_diagnostics": {
                        "overall": {
                            "wrong_transform_family": 2,
                            "stale_context_support_suspicions": 1,
                        },
                        "contexts": {"context_1": {"mean_bit_accuracy": 0.2}},
                    },
                },
                "warm_full_summary": {
                    "exact_matches": 2,
                    "mean_bit_accuracy": 0.5,
                    "task_diagnostics": {
                        "overall": {
                            "wrong_transform_family": 1,
                            "stale_context_support_suspicions": 0,
                        },
                        "contexts": {"context_1": {"mean_bit_accuracy": 0.5}},
                    },
                },
                "warm_substrate_summary": {
                    "exact_matches": 3,
                    "mean_bit_accuracy": 0.6,
                    "task_diagnostics": {
                        "overall": {
                            "wrong_transform_family": 0,
                            "stale_context_support_suspicions": 0,
                        },
                        "contexts": {"context_1": {"mean_bit_accuracy": 0.7}},
                    },
                },
                "cold_metrics": {
                    "best_rolling_exact_rate": 0.25,
                    "best_rolling_bit_accuracy": 0.5,
                    "anticipation": {
                        "predicted_route_entry_count": 4,
                        "predicted_source_route_entry_count": 2,
                        "first_predicted_source_route_cycle": 9,
                    },
                },
                "warm_full_metrics": {
                    "best_rolling_exact_rate": 0.5,
                    "best_rolling_bit_accuracy": 0.75,
                    "anticipation": {
                        "predicted_route_entry_count": 8,
                        "predicted_source_route_entry_count": 5,
                        "first_predicted_source_route_cycle": 4,
                    },
                },
                "warm_substrate_metrics": {
                    "best_rolling_exact_rate": 0.625,
                    "best_rolling_bit_accuracy": 0.8,
                    "anticipation": {
                        "predicted_route_entry_count": 6,
                        "predicted_source_route_entry_count": 3,
                        "first_predicted_source_route_cycle": 6,
                    },
                },
            }
        ]

        aggregate = aggregate_pair(results)

        self.assertEqual(aggregate["avg_cold_predicted_route_entries"], 4.0)
        self.assertEqual(aggregate["avg_warm_full_predicted_source_route_entries"], 5.0)
        self.assertEqual(
            aggregate["avg_warm_substrate_first_predicted_source_route_cycle"],
            6.0,
        )


if __name__ == "__main__":
    unittest.main()
