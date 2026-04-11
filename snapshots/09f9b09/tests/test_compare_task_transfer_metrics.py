from __future__ import annotations

import unittest

from phase8.environment import NativeSubstrateSystem
from scripts.compare_task_transfer import aggregate_transfer, transfer_metrics


class TestCompareTaskTransferMetrics(unittest.TestCase):
    def test_transfer_metrics_reports_early_adaptation_fields(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=47,
        )
        for cycle in range(8):
            system.environment.inject_signal(
                count=1,
                cycle=cycle,
                packet_payloads=[[1, 0, 1, 1]],
                context_bits=[0],
                task_id="task_a",
            )
            system.environment.route_signal(
                "n0",
                "sink",
                cost=0.05,
                transform_name="rotate_left_1",
            )
            system.global_cycle = cycle + 1

        metrics = transfer_metrics(system)

        self.assertTrue(metrics["criterion_reached"])
        self.assertEqual(metrics["examples_to_criterion"], 8)
        self.assertEqual(metrics["first_exact_match_example"], 1)
        self.assertEqual(metrics["first_expected_transform_example"], 1)
        self.assertEqual(metrics["first_sustained_expected_transform_example"], 1)
        self.assertEqual(metrics["early_window_wrong_transform_family"], 0)
        self.assertEqual(metrics["early_window_exact_rate"], 1.0)
        self.assertEqual(metrics["anticipation"]["predicted_route_entry_count"], 0)

    def test_aggregate_transfer_reports_early_and_anticipation_metrics(self) -> None:
        results = [
            {
                "cold_task_b": {
                    "summary": {
                        "exact_matches": 1,
                        "mean_bit_accuracy": 0.4,
                        "mean_route_cost": 0.05,
                        "task_diagnostics": {
                            "overall": {
                                "wrong_transform_family": 2,
                                "identity_fallbacks": 1,
                                "stale_context_support_suspicions": 1,
                            },
                            "contexts": {"context_1": {"mean_bit_accuracy": 0.25}},
                        },
                    },
                    "transfer_metrics": {
                        "early_window_exact_rate": 0.25,
                        "early_window_wrong_transform_family_rate": 0.5,
                        "first_expected_transform_example": 4,
                        "anticipation": {
                            "recognized_source_transform_entry_count": 0,
                            "predicted_route_entry_count": 0,
                        },
                    },
                },
                "warm_full_task_b": {
                    "summary": {
                        "exact_matches": 2,
                        "mean_bit_accuracy": 0.45,
                        "mean_route_cost": 0.04,
                        "task_diagnostics": {
                            "overall": {
                                "wrong_transform_family": 1,
                                "identity_fallbacks": 0,
                                "stale_context_support_suspicions": 0,
                            },
                            "contexts": {"context_1": {"mean_bit_accuracy": 0.5}},
                        },
                    },
                    "transfer_metrics": {
                        "early_window_exact_rate": 0.5,
                        "early_window_wrong_transform_family_rate": 0.25,
                        "first_expected_transform_example": 2,
                        "anticipation": {
                            "recognized_source_transform_entry_count": 4,
                            "predicted_route_entry_count": 0,
                        },
                    },
                },
                "warm_substrate_task_b": {
                    "summary": {
                        "exact_matches": 3,
                        "mean_bit_accuracy": 0.5,
                        "mean_route_cost": 0.03,
                        "task_diagnostics": {
                            "overall": {
                                "wrong_transform_family": 0,
                                "identity_fallbacks": 0,
                                "stale_context_support_suspicions": 0,
                            },
                            "contexts": {"context_1": {"mean_bit_accuracy": 0.625}},
                        },
                    },
                    "transfer_metrics": {
                        "early_window_exact_rate": 0.625,
                        "early_window_wrong_transform_family_rate": 0.125,
                        "first_expected_transform_example": 1,
                        "anticipation": {
                            "recognized_source_transform_entry_count": 2,
                            "predicted_route_entry_count": 0,
                        },
                    },
                },
                "delta_full_task_b": {
                    "exact_matches": 1,
                    "mean_bit_accuracy": 0.05,
                    "mean_route_cost": -0.01,
                    "best_rolling_exact_rate": 0.125,
                    "best_rolling_bit_accuracy": 0.125,
                },
                "delta_substrate_task_b": {
                    "exact_matches": 2,
                    "mean_bit_accuracy": 0.1,
                    "mean_route_cost": -0.02,
                    "best_rolling_exact_rate": 0.25,
                    "best_rolling_bit_accuracy": 0.25,
                },
            }
        ]

        aggregate = aggregate_transfer(results)

        self.assertEqual(aggregate["avg_cold_task_b_early_exact_rate"], 0.25)
        self.assertEqual(
            aggregate["avg_warm_full_task_b_early_wrong_transform_family_rate"],
            0.25,
        )
        self.assertEqual(
            aggregate["avg_warm_full_task_b_first_expected_transform_example"],
            2.0,
        )
        self.assertEqual(
            aggregate["avg_warm_full_task_b_recognized_source_transform_entries"],
            4.0,
        )


if __name__ == "__main__":
    unittest.main()
