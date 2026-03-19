from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Sequence

from occupancy_baseline import ExperimentConfig, get_preset, list_presets, run_experiment
from scripts.experiment_manifest import build_run_manifest, write_run_manifest
from scripts.occupancy_real import (
    DEFAULT_SELECTOR_SEEDS,
    OccupancyRealConfig,
    run_occupancy_real_experiment,
)


SHARED_METRICS = ("accuracy", "precision", "recall", "f1")


def _resolve_baseline_config(args: argparse.Namespace) -> tuple[ExperimentConfig, str | None, str]:
    if args.preset:
        preset = get_preset(args.preset)
        return preset.config, args.output, preset.name
    if not args.csv:
        raise ValueError("Either --preset or --csv must be provided")
    return (
        ExperimentConfig(
            csv_path=args.csv,
            window_size=args.window_size,
            hidden_size=args.hidden_size,
            learning_rate=args.learning_rate,
            epochs=args.epochs,
            seed=args.baseline_seed,
            train_fraction=args.train_fraction,
            normalize=not args.no_normalize,
        ),
        args.output,
        "custom",
    )


def _selector_seeds_from_args(args: argparse.Namespace) -> tuple[int, ...]:
    if args.selector_seeds:
        return tuple(int(seed) for seed in args.selector_seeds)
    if args.default_series_seeds:
        return DEFAULT_SELECTOR_SEEDS
    return (int(args.selector_seed),)


def compare_occupancy_baseline(
    *,
    baseline_config: ExperimentConfig,
    selector_seeds: Sequence[int],
    max_train_episodes: int | None = None,
    max_eval_episodes: int | None = None,
) -> dict[str, object]:
    baseline_result = run_experiment(baseline_config)
    comparison_runs: list[dict[str, object]] = []

    for selector_seed in selector_seeds:
        real_result = run_occupancy_real_experiment(
            OccupancyRealConfig(
                csv_path=baseline_config.csv_path,
                window_size=baseline_config.window_size,
                train_fraction=baseline_config.train_fraction,
                normalize=baseline_config.normalize,
                selector_seed=int(selector_seed),
                max_train_episodes=max_train_episodes,
                max_eval_episodes=max_eval_episodes,
            )
        )
        eval_metrics = dict(real_result["eval_summary"]["metrics"])
        baseline_metrics = dict(baseline_result.metrics)
        comparison_runs.append(
            {
                "selector_seed": int(selector_seed),
                "real": real_result,
                "baseline_metrics": baseline_metrics,
                "eval_minus_baseline": {
                    metric_name: round(
                        float(eval_metrics.get(metric_name, 0.0))
                        - float(baseline_metrics.get(metric_name, 0.0)),
                        4,
                    )
                    for metric_name in SHARED_METRICS
                },
            }
        )

    aggregate = {
        "selector_seed_count": len(comparison_runs),
        "selector_seeds": [int(seed) for seed in selector_seeds],
        "mean_real_eval_metrics": {
            metric_name: round(
                mean(
                    float(run["real"]["eval_summary"]["metrics"][metric_name])
                    for run in comparison_runs
                ),
                4,
            )
            for metric_name in SHARED_METRICS
        },
        "mean_eval_minus_baseline": {
            metric_name: round(
                mean(
                    float(run["eval_minus_baseline"][metric_name])
                    for run in comparison_runs
                ),
                4,
            )
            for metric_name in SHARED_METRICS
        },
        "mean_real_train_accuracy": round(
            mean(
                float(run["real"]["train_summary"]["metrics"]["accuracy"])
                for run in comparison_runs
            ),
            4,
        ),
        "mean_real_eval_delivered_packets": round(
            mean(
                float(run["real"]["eval_summary"]["mean_delivered_packets"])
                for run in comparison_runs
            ),
            4,
        ),
        "mean_real_train_feedback_events": round(
            mean(
                float(run["real"]["train_summary"]["mean_feedback_events"])
                for run in comparison_runs
            ),
            4,
        ),
    }

    return {
        "baseline": baseline_result.to_dict(),
        "selector_seeds": [int(seed) for seed in selector_seeds],
        "runs": comparison_runs,
        "aggregate": aggregate,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare the occupancy MLP baseline against the REAL bridge.")
    parser.add_argument("--csv", help="Path to occupancy CSV file")
    parser.add_argument("--preset", default="synth_v1_default", help="Named occupancy preset to compare")
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--hidden-size", type=int, default=12)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--baseline-seed", type=int, default=0)
    parser.add_argument("--train-fraction", type=float, default=0.8)
    parser.add_argument("--no-normalize", action="store_true")
    parser.add_argument("--selector-seed", type=int, default=13)
    parser.add_argument("--selector-seeds", nargs="+", type=int)
    parser.add_argument("--default-series-seeds", action="store_true")
    parser.add_argument("--max-train-episodes", type=int)
    parser.add_argument("--max-eval-episodes", type=int)
    parser.add_argument("--output", help="Optional path to write the manifest JSON")
    parser.add_argument("--list-presets", action="store_true", help="List available presets and exit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.list_presets:
        payload = [
            {
                "name": preset.name,
                "description": preset.description,
                "default_output_json": preset.default_output_json,
                "config": preset.config.__dict__,
            }
            for preset in list_presets()
        ]
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    baseline_config, output_path, preset_name = _resolve_baseline_config(args)
    selector_seeds = _selector_seeds_from_args(args)
    result = compare_occupancy_baseline(
        baseline_config=baseline_config,
        selector_seeds=selector_seeds,
        max_train_episodes=args.max_train_episodes,
        max_eval_episodes=args.max_eval_episodes,
    )
    print(json.dumps(result, indent=2, sort_keys=True))

    if output_path:
        manifest = build_run_manifest(
            harness="occupancy_baseline_comparison",
            seeds=selector_seeds,
            scenarios=(preset_name,),
            result=result,
            metadata={
                "csv_path": baseline_config.csv_path,
                "window_size": baseline_config.window_size,
                "train_fraction": baseline_config.train_fraction,
                "normalize": baseline_config.normalize,
                "max_train_episodes": args.max_train_episodes,
                "max_eval_episodes": args.max_eval_episodes,
            },
        )
        write_run_manifest(Path(output_path), manifest)


if __name__ == "__main__":
    main()
