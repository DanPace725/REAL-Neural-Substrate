from __future__ import annotations

import io
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path

from analyze_experiment_output import analyze_v3, is_v3_format, write_summary_v3


def _single_v3_payload(seed: int = 13) -> dict[str, object]:
    protocol_payload = {
        "warm_summary": {
            "episode_count": 4,
            "metrics": {"accuracy": 0.75, "precision": 0.8, "recall": 0.7, "f1": 0.7467},
            "mean_delivered_packets": 24.0,
            "mean_dropped_packets": 1.0,
            "mean_feedback_events": 18.0,
        },
        "cold_summary": {
            "episode_count": 4,
            "metrics": {"accuracy": 0.5, "precision": 0.5, "recall": 0.5, "f1": 0.5},
            "mean_delivered_packets": 22.0,
            "mean_dropped_packets": 3.0,
            "mean_feedback_events": 15.0,
        },
        "efficiency": {
            "mean_efficiency_ratio": 1.1,
            "session_1_delivery_delta": 0.1,
            "session_1_efficiency_ratio": 1.125,
            "mean_first_episode_delivery_delta": 0.05,
            "mean_first_three_episode_delivery_delta": 0.04,
            "warm_sessions_to_80pct": 0,
            "cold_sessions_to_80pct": 1,
            "warm_delivery_at": {"session_1": 0.9},
            "cold_delivery_at": {"session_1": 0.8},
            "warm_delivery_curve": [0.9, 1.0],
            "cold_delivery_curve": [0.8, 0.9],
            "efficiency_ratio_curve": [1.125, 1.1111],
        },
        "context_transfer_probe": {
            "status": "ok",
            "training_context_codes": [0, 1],
            "eval_context_codes": [0, 1, 2],
            "warm_seen_mean_delivery": 0.93,
            "warm_unseen_mean_delivery": 0.81,
            "cold_seen_mean_delivery": 0.82,
            "cold_unseen_mean_delivery": 0.77,
            "warm_seen_session_count": 2,
            "warm_unseen_session_count": 1,
        },
        "warm_system_summary": {"admitted_packets": 20, "delivery_ratio": 0.95},
        "cold_system_summary": {"admitted_packets": 18, "delivery_ratio": 0.84},
        "warm_reset_count": 2,
        "cold_reset_count": 2,
        "workers_used": 7,
        "parallelism_status": "process_pool:7",
    }
    return {
        "v3_config": {
            "csv_path": "occupancy_baseline/data/occupancy_synth_v1.csv",
            "window_size": 5,
            "normalize": True,
            "selector_seed": seed,
            "feedback_amount": 0.18,
            "eval_feedback_fraction": 1.0,
            "packet_ttl": 8,
            "train_session_fraction": 0.7,
            "eval_mode": "both",
            "topology_mode": "multihop_routing",
            "context_mode": "online_running_context",
            "ingress_mode": "admission_source",
            "summary_only": True,
        },
        "manifest": {
            "run_id": f"v3_seed{seed}_20260320T180000",
            "run_at": "2026-03-20T18:00:00+00:00",
            "git_sha": "abc1234",
            "csv": "occupancy_baseline/data/occupancy_synth_v1.csv",
            "selector_seeds": [seed],
            "window_size": 5,
            "train_session_fraction": 0.7,
            "eval_mode": "both",
            "topology_mode": "multihop_routing",
            "context_mode": "online_running_context",
            "ingress_mode": "admission_source",
            "workers": None,
        },
        "worker_policy": {
            "requested_workers": None,
            "auto_cpu_target_fraction": 0.75,
            "eval_workers_by_protocol": {
                "fresh_session_eval": 7,
                "persistent_eval": 2,
            },
        },
        "dataset_rows": 100,
        "total_episodes": 96,
        "total_sessions": 12,
        "train_session_count": 8,
        "eval_session_count": 4,
        "co2_training_median": 0.5,
        "light_training_median": 0.6,
        "training_context_codes": [0, 1],
        "train_inventory": {"session_count": 8, "by_label": {"0": 4}, "by_context_code": {"0": 4}, "episode_lengths": {"min": 1, "mean": 2.0, "max": 4}},
        "eval_inventory": {"session_count": 4, "by_label": {"1": 4}, "by_context_code": {"1": 4}, "episode_lengths": {"min": 1, "mean": 2.0, "max": 4}},
        "train_summary": {
            "episode_count": 8,
            "metrics": {"accuracy": 0.9, "precision": 0.9, "recall": 0.9, "f1": 0.9},
            "mean_delivered_packets": 23.0,
            "mean_dropped_packets": 2.0,
            "mean_feedback_events": 17.0,
        },
        "train_system_summary": {"delivery_ratio": 0.92, "admitted_packets": 40},
        "primary_eval_mode": "fresh_session_eval",
        "eval_protocols": {
            "fresh_session_eval": protocol_payload,
            "persistent_eval": {
                **protocol_payload,
                "workers_used": 2,
                "parallelism_status": "process_pool:2",
            },
        },
        "warm_eval_summary": protocol_payload["warm_summary"],
        "cold_eval_summary": protocol_payload["cold_summary"],
        "carryover_efficiency": protocol_payload["efficiency"],
        "context_transfer_probe": protocol_payload["context_transfer_probe"],
        "warm_system_summary": protocol_payload["warm_system_summary"],
        "cold_system_summary": protocol_payload["cold_system_summary"],
    }


def _sweep_v3_payload() -> dict[str, object]:
    seed13 = _single_v3_payload(13)
    seed23 = _single_v3_payload(23)
    return {
        "v3_sweep_config": {
            "base_config": {
                **seed13["v3_config"],
                "selector_seed": None,
            },
            "selector_seeds": [13, 23],
        },
        "worker_policy": {
            "requested_workers": None,
            "auto_cpu_target_fraction": 0.75,
            "worker_budget": 15,
            "seed_workers": 2,
            "eval_workers_per_seed": 7,
            "effective_total_workers": 14,
            "parallelism_status": "process_pool:2",
        },
        "aggregate": {
            "selector_seed_count": 2,
            "primary_eval_mode": "fresh_session_eval",
            "mean_train_accuracy": 0.9,
            "mean_warm_accuracy": 0.8,
            "mean_cold_accuracy": 0.6,
            "mean_warm_delivery_ratio": 0.95,
            "mean_cold_delivery_ratio": 0.84,
            "mean_efficiency_ratio": 1.1,
            "mean_session_1_delivery_delta": 0.1,
            "mean_first_episode_delivery_delta": 0.05,
            "mean_first_three_episode_delivery_delta": 0.04,
            "best_seed_by_efficiency_ratio": {"selector_seed": 13, "metric": "mean_efficiency_ratio", "value": 1.1},
        },
        "seed_summaries": [
            {
                "selector_seed": 13,
                "train_accuracy": 0.9,
                "warm_accuracy": 0.8,
                "cold_accuracy": 0.6,
                "warm_mean_delivery_ratio": 0.95,
                "cold_mean_delivery_ratio": 0.84,
                "mean_efficiency_ratio": 1.1,
                "session_1_delivery_delta": 0.1,
                "mean_first_episode_delivery_delta": 0.05,
                "mean_first_three_episode_delivery_delta": 0.04,
                "eval_workers_by_protocol": {"fresh_session_eval": 7},
                "protocol_parallelism": {"fresh_session_eval": "process_pool:7"},
            },
            {
                "selector_seed": 23,
                "train_accuracy": 0.88,
                "warm_accuracy": 0.79,
                "cold_accuracy": 0.61,
                "warm_mean_delivery_ratio": 0.94,
                "cold_mean_delivery_ratio": 0.85,
                "mean_efficiency_ratio": 1.09,
                "session_1_delivery_delta": 0.08,
                "mean_first_episode_delivery_delta": 0.04,
                "mean_first_three_episode_delivery_delta": 0.03,
                "eval_workers_by_protocol": {"fresh_session_eval": 7},
                "protocol_parallelism": {"fresh_session_eval": "process_pool:7"},
            },
        ],
        "seed_results": [seed13, seed23],
        "manifest": {
            "run_id": "v3_sweep2seeds_20260320T180000",
            "run_at": "2026-03-20T18:00:00+00:00",
            "git_sha": "abc1234",
            "csv": "occupancy_baseline/data/occupancy_synth_v1.csv",
            "selector_seeds": [13, 23],
            "window_size": 5,
            "train_session_fraction": 0.7,
            "eval_mode": "fresh_session_eval",
            "topology_mode": "multihop_routing",
            "context_mode": "online_running_context",
            "ingress_mode": "admission_source",
            "workers": None,
        },
    }


class TestAnalyzeExperimentOutput(unittest.TestCase):
    def test_is_v3_format_accepts_sweep_payload(self) -> None:
        self.assertTrue(is_v3_format(_sweep_v3_payload()))

    def test_analyze_v3_prints_protocol_and_worker_policy(self) -> None:
        payload = _single_v3_payload()
        stream = io.StringIO()
        with redirect_stdout(stream):
            analyze_v3(payload, Namespace(seed=None, no_plots=True, rolling=5, summary=None))
        output = stream.getvalue()
        self.assertIn("Worker policy", output)
        self.assertIn("fresh_session_eval", output)
        self.assertIn("parallelism_status", output)

    def test_write_summary_v3_sweep_includes_aggregate_and_seed_summary(self) -> None:
        payload = _sweep_v3_payload()
        out_dir = Path("tests_tmp") / "analyze_experiment_output"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "v3_sweep_summary.md"
        write_summary_v3(payload, out_path)
        text = out_path.read_text(encoding="utf-8")
        self.assertIn("REAL Occupancy v3 - multi-seed sweep", text)
        self.assertIn("## Aggregate", text)
        self.assertIn("## Per-seed summary", text)
        self.assertIn("selector_seed", text)


if __name__ == "__main__":
    unittest.main()
