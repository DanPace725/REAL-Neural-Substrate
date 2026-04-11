from __future__ import annotations

from statistics import mean
from typing import Dict, Iterable, List, Sequence

from scripts.neural_baseline_data import EXACT_THRESHOLD, rolling_window_metrics


CHANCE_BIT_ACCURACY = 0.5
COLLAPSE_BIT_ACCURACY_THRESHOLD = 0.55
COLLAPSE_EXACT_MATCH_RATE_THRESHOLD = 0.10
NN_ADVANTAGE_BIT_ACCURACY = 0.10
NN_ADVANTAGE_EXACT_RATE_MULTIPLIER = 2.0


def aggregate_run_metrics(runs: Sequence[Dict[str, object]]) -> Dict[str, object]:
    if not runs:
        return {}

    exact_rates = [float(run["exact_match_rate"]) for run in runs]
    bit_accuracies = [float(run["mean_bit_accuracy"]) for run in runs]
    reached = [run for run in runs if bool(run.get("criterion_reached"))]
    etc_values = [int(run["examples_to_criterion"]) for run in reached if run.get("examples_to_criterion") is not None]
    exact_counts = [int(run["exact_matches"]) for run in runs]
    expected_examples = [int(run["expected_examples"]) for run in runs]
    return {
        "n_runs": len(runs),
        "mean_exact_matches": round(mean(exact_counts), 4),
        "mean_expected_examples": round(mean(expected_examples), 4),
        "mean_exact_match_rate": round(mean(exact_rates), 4),
        "mean_bit_accuracy": round(mean(bit_accuracies), 4),
        "criterion_rate": round(len(reached) / len(runs), 4),
        "mean_examples_to_criterion": round(mean(etc_values), 4) if etc_values else None,
        "min_examples_to_criterion": min(etc_values) if etc_values else None,
        "mean_delta_vs_chance": round(mean(value - CHANCE_BIT_ACCURACY for value in bit_accuracies), 4),
    }


def collapse_flag(
    real_aggregate: Dict[str, object],
    nn_aggregates: Iterable[Dict[str, object]],
) -> bool:
    criterion_rate = float(real_aggregate.get("criterion_rate", 0.0))
    bit_accuracy = float(real_aggregate.get("mean_bit_accuracy", 0.0))
    exact_rate = float(real_aggregate.get("mean_exact_match_rate", 0.0))
    if criterion_rate > 0.0 or bit_accuracy > COLLAPSE_BIT_ACCURACY_THRESHOLD or exact_rate > COLLAPSE_EXACT_MATCH_RATE_THRESHOLD:
        return False

    best_nn = best_nn_aggregate(nn_aggregates)
    if not best_nn:
        return False
    best_nn_bit_accuracy = float(best_nn.get("mean_bit_accuracy", 0.0))
    best_nn_exact_rate = float(best_nn.get("mean_exact_match_rate", 0.0))
    exact_rate_floor = max(exact_rate, 1e-9)
    nn_advantage = (
        best_nn_bit_accuracy >= bit_accuracy + NN_ADVANTAGE_BIT_ACCURACY
        or best_nn_exact_rate >= exact_rate_floor * NN_ADVANTAGE_EXACT_RATE_MULTIPLIER
    )
    return bool(nn_advantage)


def best_nn_aggregate(nn_aggregates: Iterable[Dict[str, object]]) -> Dict[str, object]:
    aggregates = list(nn_aggregates)
    if not aggregates:
        return {}
    return max(
        aggregates,
        key=lambda aggregate: (
            float(aggregate.get("mean_bit_accuracy", 0.0)),
            float(aggregate.get("mean_exact_match_rate", 0.0)),
            float(aggregate.get("criterion_rate", 0.0)),
        ),
    )


def frontier_summary(point_results: Sequence[Dict[str, object]]) -> Dict[str, object]:
    by_family: Dict[str, List[Dict[str, object]]] = {}
    for point in point_results:
        by_family.setdefault(str(point["family_id"]), []).append(point)

    family_frontiers: Dict[str, Dict[str, object]] = {}
    global_ceiling: Dict[str, object] | None = None
    for family_id, points in by_family.items():
        ordered = sorted(points, key=lambda point: int(point["difficulty_index"]))
        ceiling_point = None
        for index, point in enumerate(ordered):
            if bool(point.get("all_real_collapsed")) and all(
                bool(harder.get("all_real_collapsed")) for harder in ordered[index:]
            ):
                ceiling_point = point
                break
        last_pre = None
        if ceiling_point is not None:
            ceiling_index = ordered.index(ceiling_point)
            if ceiling_index > 0:
                last_pre = ordered[ceiling_index - 1]
        family_frontiers[family_id] = {
            "ceiling_band": ceiling_point["benchmark_id"] if ceiling_point is not None else None,
            "last_pre_collapse": last_pre["benchmark_id"] if last_pre is not None else None,
            "best_nn_by_band": {
                point["benchmark_id"]: point.get("best_nn_method_id")
                for point in ordered
            },
        }
        if ceiling_point is not None:
            if global_ceiling is None or (
                int(ceiling_point["family_order"]),
                int(ceiling_point["difficulty_index"]),
            ) < (
                int(global_ceiling["family_order"]),
                int(global_ceiling["difficulty_index"]),
            ):
                global_ceiling = ceiling_point

    return {
        "families": family_frontiers,
        "earliest_global_ceiling": global_ceiling["benchmark_id"] if global_ceiling is not None else None,
    }


def criterion_metrics_from_exact_and_accuracy(
    exact_results: Sequence[bool],
    bit_accuracies: Sequence[float],
) -> Dict[str, object]:
    summary = rolling_window_metrics(exact_results, bit_accuracies)
    return {
        "criterion_reached": bool(summary["criterion_reached"]),
        "examples_to_criterion": int(summary["examples_to_criterion"]) if summary["examples_to_criterion"] is not None else None,
        "best_rolling_exact_rate": float(summary["best_rolling_exact_rate"]),
        "best_rolling_bit_accuracy": float(summary["best_rolling_bit_accuracy"] or 0.0),
        "exact_threshold": EXACT_THRESHOLD,
    }


__all__ = [
    "CHANCE_BIT_ACCURACY",
    "COLLAPSE_BIT_ACCURACY_THRESHOLD",
    "COLLAPSE_EXACT_MATCH_RATE_THRESHOLD",
    "NN_ADVANTAGE_BIT_ACCURACY",
    "NN_ADVANTAGE_EXACT_RATE_MULTIPLIER",
    "aggregate_run_metrics",
    "best_nn_aggregate",
    "collapse_flag",
    "criterion_metrics_from_exact_and_accuracy",
    "frontier_summary",
]
