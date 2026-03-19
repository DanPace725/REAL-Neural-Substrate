from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from scripts.evaluate_experience_extension import evaluate_experience_extension
from scripts.evaluate_runtime_slack import evaluate_runtime_slack
from scripts.experiment_manifest import build_run_manifest, write_run_manifest


DEFAULT_BENCHMARK_IDS = ("A1", "B2", "C3")
DEFAULT_TASK_KEYS = ("task_a",)
DEFAULT_METHOD_IDS = ("self-selected",)
DEFAULT_SEEDS = (13,)
DEFAULT_CYCLE_MULTIPLIERS = (1.0, 1.5, 2.0)
DEFAULT_REPEAT_COUNTS = (1, 2, 3)


def _compact_anticipation(metrics: dict[str, object]) -> dict[str, object]:
    return {
        "predicted_route_entry_count": int(metrics.get("predicted_route_entry_count", 0)),
        "predicted_source_route_entry_count": int(
            metrics.get("predicted_source_route_entry_count", 0)
        ),
        "predicted_route_entry_rate": float(
            metrics.get("predicted_route_entry_rate", 0.0)
        ),
        "predicted_source_route_entry_rate": float(
            metrics.get("predicted_source_route_entry_rate", 0.0)
        ),
        "first_predicted_route_cycle": metrics.get("first_predicted_route_cycle"),
        "first_predicted_source_route_cycle": metrics.get(
            "first_predicted_source_route_cycle"
        ),
        "mean_prediction_confidence": metrics.get("mean_prediction_confidence"),
        "mean_source_prediction_confidence": metrics.get(
            "mean_source_prediction_confidence"
        ),
        "mean_source_expected_delta": metrics.get("mean_source_expected_delta"),
        "mean_source_stale_family_risk": metrics.get("mean_source_stale_family_risk"),
    }


def _compact_runtime_case(case: dict[str, object]) -> dict[str, object]:
    return {
        "benchmark_id": case["benchmark_id"],
        "family_id": case["family_id"],
        "task_key": case["task_key"],
        "method_id": case["method_id"],
        "seed": int(case["seed"]),
        "runs": [
            {
                "cycle_multiplier": float(run["cycle_multiplier"]),
                "exact_match_rate": float(run["exact_match_rate"]),
                "mean_bit_accuracy": float(run["mean_bit_accuracy"]),
                "best_rolling_exact_rate": float(run["best_rolling_exact_rate"]),
                "delta_exact_match_rate": float(run["delta_exact_match_rate"]),
                "delta_best_rolling_exact_rate": float(
                    run["delta_best_rolling_exact_rate"]
                ),
                "anticipation": _compact_anticipation(
                    dict(run.get("anticipation", {}))
                ),
            }
            for run in case["runs"]
        ],
    }


def _compact_experience_case(case: dict[str, object]) -> dict[str, object]:
    return {
        "benchmark_id": case["benchmark_id"],
        "family_id": case["family_id"],
        "task_key": case["task_key"],
        "method_id": case["method_id"],
        "seed": int(case["seed"]),
        "runs": [
            {
                "repeat_count": int(run["repeat_count"]),
                "exact_match_rate": float(run["exact_match_rate"]),
                "mean_bit_accuracy": float(run["mean_bit_accuracy"]),
                "best_rolling_exact_rate": float(run["best_rolling_exact_rate"]),
                "delta_exact_match_rate": float(run["delta_exact_match_rate"]),
                "delta_final_pass_exact_match_rate": float(
                    run["delta_final_pass_exact_match_rate"]
                ),
                "anticipation": _compact_anticipation(
                    dict(run.get("anticipation", {}))
                ),
                "per_pass": [
                    {
                        "pass_index": int(item["pass_index"]),
                        "exact_match_rate": float(item["exact_match_rate"]),
                        "mean_bit_accuracy": float(item["mean_bit_accuracy"]),
                        "best_rolling_exact_rate": float(
                            item["best_rolling_exact_rate"]
                        ),
                        "anticipation": _compact_anticipation(
                            dict(item.get("anticipation", {}))
                        ),
                    }
                    for item in run["per_pass"]
                ],
            }
            for run in case["runs"]
        ],
    }


def evaluate_time_exposure_prediction_probe(
    *,
    benchmark_ids: Sequence[str] = DEFAULT_BENCHMARK_IDS,
    task_keys: Sequence[str] = DEFAULT_TASK_KEYS,
    method_ids: Sequence[str] = DEFAULT_METHOD_IDS,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    cycle_multipliers: Sequence[float] = DEFAULT_CYCLE_MULTIPLIERS,
    repeat_counts: Sequence[int] = DEFAULT_REPEAT_COUNTS,
    output_path: Path | None = None,
) -> dict[str, object]:
    runtime = evaluate_runtime_slack(
        benchmark_ids=benchmark_ids,
        task_keys=task_keys,
        method_ids=method_ids,
        seeds=seeds,
        cycle_multipliers=cycle_multipliers,
    )
    exposure = evaluate_experience_extension(
        benchmark_ids=benchmark_ids,
        task_keys=task_keys,
        method_ids=method_ids,
        seeds=seeds,
        repeat_counts=repeat_counts,
    )
    result = {
        "benchmark_ids": list(benchmark_ids),
        "task_keys": list(task_keys),
        "method_ids": list(method_ids),
        "seeds": [int(seed) for seed in seeds],
        "runtime_slack": {
            "cycle_multipliers": [float(value) for value in cycle_multipliers],
            "cases": [_compact_runtime_case(case) for case in runtime["results"]],
        },
        "experience_extension": {
            "repeat_counts": [int(value) for value in repeat_counts],
            "cases": [_compact_experience_case(case) for case in exposure["results"]],
        },
    }
    if output_path is not None:
        manifest = build_run_manifest(
            harness="time_exposure_prediction_probe",
            seeds=seeds,
            scenarios=[f"{benchmark_id}:{task_key}" for benchmark_id in benchmark_ids for task_key in task_keys],
            metadata={
                "benchmark_ids": list(benchmark_ids),
                "task_keys": list(task_keys),
                "method_ids": list(method_ids),
                "cycle_multipliers": [float(value) for value in cycle_multipliers],
                "repeat_counts": [int(value) for value in repeat_counts],
            },
            result=result,
        )
        write_run_manifest(output_path, manifest)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lightweight family probe around runtime slack, repeated exposure, and prediction."
    )
    parser.add_argument("--benchmarks", nargs="*", default=list(DEFAULT_BENCHMARK_IDS))
    parser.add_argument("--tasks", nargs="*", default=list(DEFAULT_TASK_KEYS))
    parser.add_argument("--methods", nargs="*", default=list(DEFAULT_METHOD_IDS))
    parser.add_argument("--seeds", nargs="*", type=int, default=list(DEFAULT_SEEDS))
    parser.add_argument(
        "--cycle-multipliers",
        nargs="*",
        type=float,
        default=list(DEFAULT_CYCLE_MULTIPLIERS),
    )
    parser.add_argument(
        "--repeat-counts",
        nargs="*",
        type=int,
        default=list(DEFAULT_REPEAT_COUNTS),
    )
    parser.add_argument("--output", type=str)
    args = parser.parse_args()

    result = evaluate_time_exposure_prediction_probe(
        benchmark_ids=tuple(args.benchmarks),
        task_keys=tuple(args.tasks),
        method_ids=tuple(args.methods),
        seeds=tuple(args.seeds),
        cycle_multipliers=tuple(args.cycle_multipliers),
        repeat_counts=tuple(args.repeat_counts),
        output_path=Path(args.output) if args.output else None,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
