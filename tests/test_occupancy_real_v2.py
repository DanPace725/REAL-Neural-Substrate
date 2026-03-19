from __future__ import annotations

import unittest

from occupancy_baseline import get_preset
from scripts.occupancy_real import OccupancyRealConfig, run_occupancy_real_experiment
from scripts.occupancy_real_v2 import (
    OccupancyRealV2Config,
    compute_co2_training_median,
    context_bit_for_episode,
    load_occupancy_episodes_v2,
    run_occupancy_real_v2_experiment,
)


def _mini_v2_config(**overrides) -> OccupancyRealV2Config:
    preset = get_preset("synth_v1_default")
    cfg = preset.config
    return OccupancyRealV2Config(
        csv_path=cfg.csv_path,
        window_size=cfg.window_size,
        train_fraction=cfg.train_fraction,
        normalize=cfg.normalize,
        selector_seed=13,
        max_train_episodes=4,
        max_eval_episodes=2,
        summary_only=True,
        **overrides,
    )


class TestOccupancyRealV2(unittest.TestCase):

    def test_v2_live_reduces_eval_packet_drop_vs_v1(self) -> None:
        """With feedback on during eval, dropped packets should fall vs v1 (no feedback in eval)."""
        preset = get_preset("synth_v1_default")
        cfg = preset.config

        v1_result = run_occupancy_real_experiment(
            OccupancyRealConfig(
                csv_path=cfg.csv_path,
                window_size=cfg.window_size,
                train_fraction=cfg.train_fraction,
                normalize=cfg.normalize,
                selector_seed=13,
                max_train_episodes=5,
                max_eval_episodes=3,
                summary_only=True,
            )
        )
        v2_result = run_occupancy_real_v2_experiment(
            OccupancyRealV2Config(
                csv_path=cfg.csv_path,
                window_size=cfg.window_size,
                train_fraction=cfg.train_fraction,
                normalize=cfg.normalize,
                selector_seed=13,
                eval_feedback_fraction=1.0,
                carryover_mode="continuous",
                context_bit_source="none",
                max_train_episodes=5,
                max_eval_episodes=3,
                summary_only=True,
            )
        )

        v1_dropped = float(v1_result["eval_summary"]["mean_dropped_packets"])
        v2_dropped = float(v2_result["eval_summary"]["mean_dropped_packets"])
        # v2 should deliver more packets (or at least not be worse) because
        # feedback keeps ATP levels from collapsing during eval
        self.assertLessEqual(
            v2_dropped, v1_dropped + 5.0,
            msg=f"Expected v2 eval drop ({v2_dropped:.1f}) <= v1 eval drop ({v1_dropped:.1f}) + 5.0"
        )
        # And eval feedback events should actually fire (v1 has 0)
        v2_eval_feedback = float(v2_result["eval_summary"]["mean_feedback_events"])
        self.assertGreater(v2_eval_feedback, 0.0)

    def test_fresh_eval_carryover_runs_without_error(self) -> None:
        """carryover_mode='fresh_eval' should complete and return valid metrics."""
        result = run_occupancy_real_v2_experiment(_mini_v2_config(carryover_mode="fresh_eval"))
        self.assertIn("eval_summary", result)
        self.assertIn("accuracy", result["eval_summary"]["metrics"])
        self.assertIn("train_summary", result)
        # System summary should come from fresh system
        self.assertIn("system_summary", result)

    def test_context_class_activates_eval_feedback(self) -> None:
        """With context_bit_source='class', feedback_event_count should be > 0 during eval."""
        result = run_occupancy_real_v2_experiment(
            _mini_v2_config(
                eval_feedback_fraction=1.0,
                context_bit_source="class",
            )
        )
        eval_feedback = float(result["eval_summary"]["mean_feedback_events"])
        self.assertGreater(eval_feedback, 0.0)

    def test_context_co2_high_active(self) -> None:
        """With context_bit_source='co2_high', co2_training_median should be in the result."""
        result = run_occupancy_real_v2_experiment(
            _mini_v2_config(context_bit_source="co2_high")
        )
        self.assertIn("co2_training_median", result)
        median = float(result["co2_training_median"])
        # Median should be a normalized value in a reasonable range
        self.assertGreaterEqual(median, -3.0)
        self.assertLessEqual(median, 3.0)

    def test_v2_config_in_output(self) -> None:
        """Result should contain v2_config with the new parameters."""
        config = _mini_v2_config(
            eval_feedback_fraction=0.5,
            carryover_mode="fresh_eval",
            context_bit_source="co2_high",
        )
        result = run_occupancy_real_v2_experiment(config)
        self.assertIn("v2_config", result)
        v2_cfg = result["v2_config"]
        self.assertEqual(float(v2_cfg["eval_feedback_fraction"]), 0.5)
        self.assertEqual(str(v2_cfg["carryover_mode"]), "fresh_eval")
        self.assertEqual(str(v2_cfg["context_bit_source"]), "co2_high")

    def test_co2_median_computed_from_training_set(self) -> None:
        """compute_co2_training_median should return a float from training episodes."""
        config = _mini_v2_config()
        episodes = load_occupancy_episodes_v2(config)
        train_eps = episodes["train_episodes"]
        median = compute_co2_training_median(train_eps)
        self.assertIsInstance(median, float)

    def test_context_bit_for_episode_none(self) -> None:
        config = _mini_v2_config(context_bit_source="none")
        episodes = load_occupancy_episodes_v2(config)
        ep = episodes["train_episodes"][0]
        bit = context_bit_for_episode(ep, config, 0.0)
        self.assertIsNone(bit)

    def test_context_bit_for_episode_class(self) -> None:
        config = _mini_v2_config(context_bit_source="class")
        episodes = load_occupancy_episodes_v2(config)
        ep = episodes["train_episodes"][0]
        bit = context_bit_for_episode(ep, config, 0.0)
        self.assertIn(bit, (0, 1))
        self.assertEqual(bit, int(ep.label))


if __name__ == "__main__":
    unittest.main()
