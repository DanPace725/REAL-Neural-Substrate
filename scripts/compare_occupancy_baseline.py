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


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_or_run_baseline_result(
    baseline_config: ExperimentConfig,
    *,
    cache_path: Path | None = None,
) -> dict[str, object]:
    if cache_path is not None and cache_path.exists():
        return _load_json(cache_path)
    baseline_result = run_experiment(baseline_config).to_dict()
    if cache_path is not None:
        _write_json(cache_path, baseline_result)
    return baseline_result


def run_seed_comparison(
    *,
    baseline_config: ExperimentConfig,
    baseline_result: dict[str, object],
    selector_seed: int,
    max_train_episodes: int | None = None,
    max_eval_episodes: int | None = None,
    summary_only: bool = False,
) -> dict[str, object]:
    real_result = run_occupancy_real_experiment(
        OccupancyRealConfig(
            csv_path=baseline_config.csv_path,
            window_size=baseline_config.window_size,
            train_fraction=baseline_config.train_fraction,
            normalize=baseline_config.normalize,
            selector_seed=int(selector_seed),
            max_train_episodes=max_train_episodes,
            max_eval_episodes=max_eval_episodes,
            summary_only=summary_only,
        )
    )
    eval_metrics = dict(real_result["eval_summary"]["metrics"])
    baseline_metrics = dict(baseline_result["metrics"])
    return {
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


def aggregate_comparison_runs(
    *,
    baseline_result: dict[str, object],
    comparison_runs: Sequence[dict[str, object]],
    selector_seeds: Sequence[int],
) -> dict[str, object]:
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
        "baseline": baseline_result,
        "selector_seeds": [int(seed) for seed in selector_seeds],
        "runs": list(comparison_runs),
        "aggregate": aggregate,
    }


def compare_occupancy_baseline(
    *,
    baseline_config: ExperimentConfig,
    selector_seeds: Sequence[int],
    max_train_episodes: int | None = None,
    max_eval_episodes: int | None = None,
    baseline_result: dict[str, object] | None = None,
    summary_only: bool = False,
) -> dict[str, object]:
    resolved_baseline = baseline_result or run_experiment(baseline_config).to_dict()
    comparison_runs = [
        run_seed_comparison(
            baseline_config=baseline_config,
            baseline_result=resolved_baseline,
            selector_seed=int(selector_seed),
            max_train_episodes=max_train_episodes,
            max_eval_episodes=max_eval_episodes,
            summary_only=summary_only,
        )
        for selector_seed in selector_seeds
    ]
    return aggregate_comparison_runs(
        baseline_result=resolved_baseline,
        comparison_runs=comparison_runs,
        selector_seeds=selector_seeds,
    )


def _seed_output_path(output_dir: Path, preset_name: str, selector_seed: int) -> Path:
    return output_dir / f"{preset_name}_seed_{int(selector_seed)}.json"


def _load_seed_run(path: Path) -> dict[str, object]:
    manifest = _load_json(path)
    result = dict(manifest.get("result", {}))
    if "run" in result:
        return dict(result["run"])
    if "runs" in result:
        runs = list(result["runs"])
        if len(runs) != 1:
            raise ValueError(f"Expected exactly one run in {path}")
        return dict(runs[0])
    raise ValueError(f"Could not find seed run payload in {path}")


def _compact_console_payload(
    result: dict[str, object],
    *,
    output_path: Path | None = None,
    seed_output_paths: Sequence[Path] | None = None,
    baseline_cache_path: Path | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "baseline_metrics": result["baseline"]["metrics"],
        "aggregate": result["aggregate"],
    }
    if output_path is not None:
        payload["aggregate_output"] = str(output_path)
    if seed_output_paths:
        payload["seed_outputs"] = [str(path) for path in seed_output_paths]
    if baseline_cache_path is not None:
        payload["baseline_cache"] = str(baseline_cache_path)
    return payload


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
    parser.add_argument("--baseline-cache", help="Optional path to cache or reuse the frozen baseline result JSON")
    parser.add_argument("--output-dir", help="Optional directory for per-seed manifest outputs")
    parser.add_argument("--resume", action="store_true", help="Reuse existing per-seed outputs when --output-dir is set")
    parser.add_argument("--summary-only", action="store_true", help="Omit per-episode REAL payloads from saved results")
    parser.add_argument("--print-full", action="store_true", help="Print the full result payload instead of a compact summary")
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
    baseline_cache_path = Path(args.baseline_cache) if args.baseline_cache else None
    baseline_result = load_or_run_baseline_result(
        baseline_config,
        cache_path=baseline_cache_path,
    )
    aggregate_output_path = Path(output_path) if output_path else None
    seed_output_paths: list[Path] = []

    if args.output_dir:
        output_dir = Path(args.output_dir)
        comparison_runs: list[dict[str, object]] = []
        for selector_seed in selector_seeds:
            seed_output_path = _seed_output_path(output_dir, preset_name, int(selector_seed))
            seed_output_paths.append(seed_output_path)
            if args.resume and seed_output_path.exists():
                comparison_runs.append(_load_seed_run(seed_output_path))
                continue
            run = run_seed_comparison(
                baseline_config=baseline_config,
                baseline_result=baseline_result,
                selector_seed=int(selector_seed),
                max_train_episodes=args.max_train_episodes,
                max_eval_episodes=args.max_eval_episodes,
                summary_only=args.summary_only,
            )
            seed_manifest = build_run_manifest(
                harness="occupancy_baseline_seed_comparison",
                seeds=(int(selector_seed),),
                scenarios=(preset_name,),
                result={
                    "baseline_metrics": baseline_result["metrics"],
                    "run": run,
                },
                metadata={
                    "csv_path": baseline_config.csv_path,
                    "window_size": baseline_config.window_size,
                    "train_fraction": baseline_config.train_fraction,
                    "normalize": baseline_config.normalize,
                    "max_train_episodes": args.max_train_episodes,
                    "max_eval_episodes": args.max_eval_episodes,
                    "summary_only": args.summary_only,
                },
            )
            write_run_manifest(seed_output_path, seed_manifest)
            comparison_runs.append(run)
        result = aggregate_comparison_runs(
            baseline_result=baseline_result,
            comparison_runs=comparison_runs,
            selector_seeds=selector_seeds,
        )
        if aggregate_output_path is None:
            aggregate_output_path = output_dir / f"{preset_name}_aggregate.json"
    else:
        result = compare_occupancy_baseline(
            baseline_config=baseline_config,
            selector_seeds=selector_seeds,
            max_train_episodes=args.max_train_episodes,
            max_eval_episodes=args.max_eval_episodes,
            baseline_result=baseline_result,
            summary_only=args.summary_only,
        )

    if aggregate_output_path is not None:
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
                "summary_only": args.summary_only,
            },
        )
        write_run_manifest(aggregate_output_path, manifest)

    console_payload = result if args.print_full else _compact_console_payload(
        result,
        output_path=aggregate_output_path,
        seed_output_paths=seed_output_paths,
        baseline_cache_path=baseline_cache_path,
    )
    print(json.dumps(console_payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
