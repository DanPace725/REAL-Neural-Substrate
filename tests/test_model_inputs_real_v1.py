from __future__ import annotations

import csv
import unittest
from pathlib import Path

from scripts.model_inputs_real_v1 import (
    CONTEXT_OFFLINE,
    EVAL_FRESH,
    ModelInputsRealConfig,
    TOPOLOGY_MULTIHOP,
    build_episodes_for_scenario,
    build_context_profile,
    build_feature_stats,
    build_model_inputs_system,
    discover_scenario_ids,
    run_model_inputs_real_experiment,
    select_scenario_splits,
    summarize_model_inputs_row,
)


def _matrix_to_text(values: list[list[float]]) -> str:
    rows = ["[" + " ".join(f"{value:.4f}" for value in row) + "]" for row in values]
    return "[" + "\n ".join(rows) + "]"


def _write_fixture_csv(path: Path) -> None:
    rows: list[dict[str, object]] = []
    scenario_templates = {
        0: [0.10, 0.20, 0.35, 0.50],
        1: [0.00, -0.05, 0.10, 0.25],
        2: [0.40, 0.38, 0.36, 0.34],
        3: [0.15, 0.10, 0.05, 0.00],
    }
    for scenario_id, results in scenario_templates.items():
        for window_start_index, result_value in enumerate(results):
            gasf = [
                [result_value + 0.1, result_value + 0.2],
                [result_value + 0.3, result_value + 0.4],
            ]
            gadf = [
                [result_value - 0.1, result_value - 0.2],
                [result_value - 0.3, result_value - 0.4],
            ]
            rows.append(
                {
                    "": len(rows),
                    "scenario_id": scenario_id,
                    "window_start_index": window_start_index,
                    "result": result_value,
                    "gasf": _matrix_to_text(gasf),
                    "gadf": _matrix_to_text(gadf),
                }
            )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["", "scenario_id", "window_start_index", "result", "gasf", "gadf"],
        )
        writer.writeheader()
        writer.writerows(rows)


class TestModelInputsRealV1(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path("tests_tmp") / "model_inputs_real_v1"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.tmp_dir / "fixture.csv"
        _write_fixture_csv(self.csv_path)

    def test_row_summary_extracts_expected_features(self) -> None:
        with self.csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            first_row = next(reader)

        summary = summarize_model_inputs_row(first_row, previous_result=None)

        self.assertEqual(summary.scenario_id, 0)
        self.assertEqual(summary.window_start_index, 0)
        self.assertAlmostEqual(summary.result_value, 0.10, places=4)
        self.assertIn("gasf_mean", summary.feature_values)
        self.assertIn("gadf_diag_mean", summary.feature_values)
        self.assertAlmostEqual(summary.feature_values["prev_result_delta"], 0.0, places=6)

    def test_scenario_split_and_stats_cover_fixture(self) -> None:
        config = ModelInputsRealConfig(
            input_path=str(self.csv_path),
            train_fraction=0.5,
            max_train_scenarios=2,
            max_eval_scenarios=2,
        )

        scenario_ids = discover_scenario_ids(config.input_path)
        splits = select_scenario_splits(config)
        stats = build_feature_stats(config.input_path, splits["train"])

        self.assertEqual(scenario_ids, [0, 1, 2, 3])
        self.assertEqual(splits["train"], [0, 1])
        self.assertEqual(splits["eval"], [2, 3])
        self.assertIn("result_value", stats)
        self.assertGreater(stats["result_value"].count, 0)

    def test_episode_builder_uses_next_step_as_label(self) -> None:
        rows: list[dict[str, str]] = []
        with self.csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if int(row["scenario_id"]) == 0:
                    rows.append(row)
        stats = build_feature_stats(self.csv_path, [0])

        episodes = build_episodes_for_scenario(
            rows,
            feature_stats=stats,
            normalize_features=True,
            positive_delta_threshold=0.0,
        )

        self.assertEqual(len(episodes), 3)
        self.assertEqual(episodes[0].label, 1)
        self.assertGreater(episodes[0].next_delta, 0.0)
        self.assertEqual(len(episodes[0].packets), 10)

    def test_context_profile_uses_training_scenario_medians(self) -> None:
        profile = build_context_profile(self.csv_path, [0, 1])

        self.assertEqual(profile.trend_feature_name, "prev_result_delta")
        self.assertEqual(profile.shape_feature_name, "gasf_abs_mean")
        self.assertAlmostEqual(profile.trend_median, 0.058333, places=5)
        self.assertAlmostEqual(profile.shape_median, 0.366667, places=5)

    def test_overlap_topology_and_pulse_local_unit_build_cleanly(self) -> None:
        stats = build_feature_stats(self.csv_path, [0, 1])
        system = build_model_inputs_system(
            ModelInputsRealConfig(
                input_path=str(self.csv_path),
                topology_mode="bounded_overlap_13715",
                local_unit_mode="pulse_local_unit",
                local_unit_preset="c_hr_overlap_tuned_v1",
            ),
            feature_names=sorted(stats.keys()),
        )

        self.assertEqual(system.environment.local_unit_mode, "pulse_local_unit")
        self.assertEqual(system.environment.local_unit_preset, "c_hr_overlap_tuned_v1")
        self.assertGreater(max(system.topology_state.positions_map().values()), 2)

    def test_multihop_topology_builds_relay_and_integrator_layers(self) -> None:
        stats = build_feature_stats(self.csv_path, [0, 1])
        system = build_model_inputs_system(
            ModelInputsRealConfig(
                input_path=str(self.csv_path),
                topology_mode=TOPOLOGY_MULTIHOP,
            ),
            feature_names=sorted(stats.keys()),
        )

        positions = system.topology_state.positions_map()
        self.assertEqual(positions["relay_trend"], 1)
        self.assertEqual(positions["integrator_regime"], 2)
        self.assertEqual(positions["vote_up"], 3)
        self.assertEqual(positions["decision_next_up"], 4)
        self.assertEqual(positions["sink"], 5)

    def test_experiment_returns_eval_metrics_and_baselines(self) -> None:
        result = run_model_inputs_real_experiment(
            ModelInputsRealConfig(
                input_path=str(self.csv_path),
                train_fraction=0.5,
                selector_seed=13,
                max_train_scenarios=2,
                max_eval_scenarios=2,
                eval_mode=EVAL_FRESH,
                summary_only=True,
            )
        )

        self.assertEqual(result["train_episode_count"], 6)
        self.assertEqual(result["eval_episode_count"], 6)
        self.assertIn("accuracy", result["eval_summary"]["metrics"])
        self.assertIn("majority_label", result["eval_baselines"])
        self.assertIn("repeat_last_delta_direction", result["eval_baselines"])
        self.assertIn("vs_majority_label", result["eval_accuracy_deltas"])
        self.assertNotIn("eval_results", result)

    def test_offline_context_mode_surfaces_context_probe_and_episode_codes(self) -> None:
        result = run_model_inputs_real_experiment(
            ModelInputsRealConfig(
                input_path=str(self.csv_path),
                train_fraction=0.5,
                selector_seed=13,
                max_train_scenarios=2,
                max_eval_scenarios=2,
                eval_mode=EVAL_FRESH,
                context_mode=CONTEXT_OFFLINE,
            )
        )

        self.assertEqual(result["context_mode"], CONTEXT_OFFLINE)
        self.assertIn("context_profile", result)
        self.assertGreater(len(result["training_context_codes"]), 0)
        self.assertIn("context_probe", result["eval_protocols"][EVAL_FRESH])
        self.assertIn("status", result["eval_context_probe"])
        self.assertTrue(all("context_code" in item for item in result["eval_results"]))
        self.assertTrue(any(item["context_code"] is not None for item in result["eval_results"]))

    def test_both_eval_mode_reports_protocols(self) -> None:
        result = run_model_inputs_real_experiment(
            ModelInputsRealConfig(
                input_path=str(self.csv_path),
                train_fraction=0.5,
                selector_seed=13,
                max_train_scenarios=2,
                max_eval_scenarios=2,
                eval_mode="both",
                summary_only=True,
            )
        )

        self.assertEqual(result["primary_eval_mode"], "fresh_session_eval")
        self.assertIn("fresh_session_eval", result["eval_protocols"])
        self.assertIn("persistent_eval", result["eval_protocols"])


if __name__ == "__main__":
    unittest.main()
