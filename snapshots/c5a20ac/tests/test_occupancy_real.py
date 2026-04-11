from __future__ import annotations

import json
import unittest
from pathlib import Path

from occupancy_baseline import get_preset
from scripts.compare_occupancy_baseline import (
    compare_occupancy_baseline,
    load_or_run_baseline_result,
)
from scripts.occupancy_real import (
    DECISION_EMPTY,
    OccupancyRealConfig,
    load_occupancy_episodes,
    run_occupancy_real_experiment,
)


class TestOccupancyReal(unittest.TestCase):
    def test_episode_adapter_preserves_window_shape_and_sensor_sources(self) -> None:
        preset = get_preset("synth_v1_default")
        payload = load_occupancy_episodes(
            OccupancyRealConfig(
                csv_path=preset.config.csv_path,
                window_size=preset.config.window_size,
                train_fraction=preset.config.train_fraction,
                normalize=preset.config.normalize,
                max_train_episodes=1,
                max_eval_episodes=0,
            )
        )

        first_episode = payload["train_episodes"][0]
        self.assertEqual(len(first_episode.packets), preset.config.window_size * 5)
        self.assertEqual(first_episode.packets[0].source_node_id, "sensor_temperature")
        self.assertEqual(first_episode.packets[4].source_node_id, "sensor_humidity_ratio")
        self.assertEqual(first_episode.packets[0].timestep_offset, preset.config.window_size - 1)
        self.assertEqual(first_episode.packets[-1].timestep_offset, 0)
        self.assertEqual(sum(first_episode.packets[0].input_bits), 1)

    def test_real_experiment_returns_train_and_eval_episode_metrics(self) -> None:
        preset = get_preset("synth_v1_default")
        result = run_occupancy_real_experiment(
            OccupancyRealConfig(
                csv_path=preset.config.csv_path,
                window_size=preset.config.window_size,
                train_fraction=preset.config.train_fraction,
                normalize=preset.config.normalize,
                selector_seed=13,
                max_train_episodes=3,
                max_eval_episodes=2,
            )
        )

        self.assertEqual(result["train_episode_count"], 3)
        self.assertEqual(result["eval_episode_count"], 2)
        self.assertIn("accuracy", result["train_summary"]["metrics"])
        self.assertIn("accuracy", result["eval_summary"]["metrics"])
        self.assertGreaterEqual(result["train_summary"]["mean_feedback_events"], 0.0)
        self.assertIn(DECISION_EMPTY, result["eval_results"][0]["decision_counts"])

    def test_real_summary_only_omits_episode_payloads(self) -> None:
        preset = get_preset("synth_v1_default")
        result = run_occupancy_real_experiment(
            OccupancyRealConfig(
                csv_path=preset.config.csv_path,
                window_size=preset.config.window_size,
                train_fraction=preset.config.train_fraction,
                normalize=preset.config.normalize,
                selector_seed=13,
                max_train_episodes=2,
                max_eval_episodes=1,
                summary_only=True,
            )
        )

        self.assertNotIn("train_results", result)
        self.assertNotIn("eval_results", result)
        self.assertIn("train_summary", result)
        self.assertIn("eval_summary", result)

    def test_comparison_reports_explicit_eval_deltas(self) -> None:
        preset = get_preset("synth_v1_default")
        result = compare_occupancy_baseline(
            baseline_config=preset.config,
            selector_seeds=(13, 23),
            max_train_episodes=3,
            max_eval_episodes=2,
            summary_only=True,
        )

        self.assertEqual(result["selector_seeds"], [13, 23])
        self.assertEqual(result["aggregate"]["selector_seed_count"], 2)
        self.assertIn("accuracy", result["baseline"]["metrics"])
        self.assertIn("accuracy", result["runs"][0]["eval_minus_baseline"])
        self.assertIn("mean_eval_minus_baseline", result["aggregate"])
        self.assertNotIn("eval_results", result["runs"][0]["real"])

    def test_baseline_cache_is_reused_when_present(self) -> None:
        preset = get_preset("synth_v1_default")
        cache_path = Path("tests_tmp") / "test_occupancy_baseline_cache.json"
        baseline = load_or_run_baseline_result(
            preset.config,
            cache_path=cache_path,
        )
        mutated = dict(baseline)
        mutated_metrics = dict(mutated["metrics"])
        mutated_metrics["accuracy"] = 0.1234
        mutated["metrics"] = mutated_metrics
        cache_path.write_text(json.dumps(mutated, indent=2), encoding="utf-8")

        loaded = load_or_run_baseline_result(
            preset.config,
            cache_path=cache_path,
        )

        self.assertEqual(loaded["metrics"]["accuracy"], 0.1234)


if __name__ == "__main__":
    unittest.main()
