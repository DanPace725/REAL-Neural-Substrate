from __future__ import annotations

import itertools
import json
import shutil
import uuid
from pathlib import Path
from statistics import mean

from compare_cold_warm import ROOT, build_system, run_workload
from compare_task_transfer import transfer_metrics


TASK_SCENARIOS = (
    "cvt1_task_a_stage1",
    "cvt1_task_b_stage1",
    "cvt1_task_c_stage1",
)
DEFAULT_SEEDS = (13, 23, 37, 51, 79)


def _context_stat(summary: dict[str, object], context_key: str, field: str) -> float:
    return float(
        summary.get("task_diagnostics", {})
        .get("contexts", {})
        .get(context_key, {})
        .get(field, 0.0)
    )


def _overall_stat(summary: dict[str, object], field: str) -> float:
    return float(summary.get("task_diagnostics", {}).get("overall", {}).get(field, 0.0))


def transfer_pair_for_seed(train_scenario: str, transfer_scenario: str, seed: int) -> dict[str, object]:
    training = build_system(seed, train_scenario)
    training_summary = run_workload(training, train_scenario)

    base_dir = ROOT / "tests_tmp" / f"matrix_{uuid.uuid4().hex}"
    full_dir = base_dir / "full"
    substrate_dir = base_dir / "substrate"
    full_dir.mkdir(parents=True, exist_ok=True)
    substrate_dir.mkdir(parents=True, exist_ok=True)
    try:
        training.save_memory_carryover(full_dir)
        training.save_substrate_carryover(substrate_dir)

        cold = build_system(seed, transfer_scenario)
        cold_summary = run_workload(cold, transfer_scenario)
        cold_metrics = transfer_metrics(cold)

        warm_full = build_system(seed, transfer_scenario)
        warm_full.load_memory_carryover(full_dir)
        warm_full_summary = run_workload(warm_full, transfer_scenario)
        warm_full_metrics = transfer_metrics(warm_full)

        warm_substrate = build_system(seed, transfer_scenario)
        warm_substrate.load_substrate_carryover(substrate_dir)
        warm_substrate_summary = run_workload(warm_substrate, transfer_scenario)
        warm_substrate_metrics = transfer_metrics(warm_substrate)
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)

    return {
        "seed": seed,
        "train_scenario": train_scenario,
        "transfer_scenario": transfer_scenario,
        "training_summary": training_summary,
        "cold_summary": cold_summary,
        "warm_full_summary": warm_full_summary,
        "warm_substrate_summary": warm_substrate_summary,
        "cold_metrics": cold_metrics,
        "warm_full_metrics": warm_full_metrics,
        "warm_substrate_metrics": warm_substrate_metrics,
    }


def aggregate_pair(results: list[dict[str, object]]) -> dict[str, float]:
    cold_summaries = [item["cold_summary"] for item in results]
    warm_full_summaries = [item["warm_full_summary"] for item in results]
    warm_substrate_summaries = [item["warm_substrate_summary"] for item in results]
    cold_metrics = [item["cold_metrics"] for item in results]
    warm_full_metrics = [item["warm_full_metrics"] for item in results]
    warm_substrate_metrics = [item["warm_substrate_metrics"] for item in results]

    return {
        "avg_cold_exact": round(mean(summary["exact_matches"] for summary in cold_summaries), 4),
        "avg_warm_full_exact": round(mean(summary["exact_matches"] for summary in warm_full_summaries), 4),
        "avg_warm_substrate_exact": round(mean(summary["exact_matches"] for summary in warm_substrate_summaries), 4),
        "avg_cold_bit_accuracy": round(mean(summary["mean_bit_accuracy"] for summary in cold_summaries), 4),
        "avg_warm_full_bit_accuracy": round(mean(summary["mean_bit_accuracy"] for summary in warm_full_summaries), 4),
        "avg_warm_substrate_bit_accuracy": round(mean(summary["mean_bit_accuracy"] for summary in warm_substrate_summaries), 4),
        "avg_cold_context_1_bit_accuracy": round(mean(_context_stat(summary, "context_1", "mean_bit_accuracy") for summary in cold_summaries), 4),
        "avg_warm_full_context_1_bit_accuracy": round(mean(_context_stat(summary, "context_1", "mean_bit_accuracy") for summary in warm_full_summaries), 4),
        "avg_warm_substrate_context_1_bit_accuracy": round(mean(_context_stat(summary, "context_1", "mean_bit_accuracy") for summary in warm_substrate_summaries), 4),
        "avg_cold_wrong_transform_family": round(mean(_overall_stat(summary, "wrong_transform_family") for summary in cold_summaries), 4),
        "avg_warm_full_wrong_transform_family": round(mean(_overall_stat(summary, "wrong_transform_family") for summary in warm_full_summaries), 4),
        "avg_warm_substrate_wrong_transform_family": round(mean(_overall_stat(summary, "wrong_transform_family") for summary in warm_substrate_summaries), 4),
        "avg_cold_stale_support": round(mean(_overall_stat(summary, "stale_context_support_suspicions") for summary in cold_summaries), 4),
        "avg_warm_full_stale_support": round(mean(_overall_stat(summary, "stale_context_support_suspicions") for summary in warm_full_summaries), 4),
        "avg_warm_substrate_stale_support": round(mean(_overall_stat(summary, "stale_context_support_suspicions") for summary in warm_substrate_summaries), 4),
        "avg_warm_full_best_exact_rate": round(mean(metric["best_rolling_exact_rate"] for metric in warm_full_metrics), 4),
        "avg_warm_full_best_bit_accuracy": round(mean(metric["best_rolling_bit_accuracy"] for metric in warm_full_metrics), 4),
        "avg_warm_substrate_best_exact_rate": round(mean(metric["best_rolling_exact_rate"] for metric in warm_substrate_metrics), 4),
        "avg_warm_substrate_best_bit_accuracy": round(mean(metric["best_rolling_bit_accuracy"] for metric in warm_substrate_metrics), 4),
        "avg_delta_full_exact": round(mean(warm["exact_matches"] - cold["exact_matches"] for cold, warm in zip(cold_summaries, warm_full_summaries)), 4),
        "avg_delta_full_bit_accuracy": round(mean(warm["mean_bit_accuracy"] - cold["mean_bit_accuracy"] for cold, warm in zip(cold_summaries, warm_full_summaries)), 4),
        "avg_delta_substrate_exact": round(mean(warm["exact_matches"] - cold["exact_matches"] for cold, warm in zip(cold_summaries, warm_substrate_summaries)), 4),
        "avg_delta_substrate_bit_accuracy": round(mean(warm["mean_bit_accuracy"] - cold["mean_bit_accuracy"] for cold, warm in zip(cold_summaries, warm_substrate_summaries)), 4),
        "warm_full_seed_wins_exact": sum(1 for cold, warm in zip(cold_summaries, warm_full_summaries) if warm["exact_matches"] > cold["exact_matches"]),
        "warm_full_seed_wins_bit_accuracy": sum(1 for cold, warm in zip(cold_summaries, warm_full_summaries) if warm["mean_bit_accuracy"] > cold["mean_bit_accuracy"]),
        "warm_full_seed_wins_both": sum(
            1
            for cold, warm in zip(cold_summaries, warm_full_summaries)
            if warm["exact_matches"] > cold["exact_matches"]
            and warm["mean_bit_accuracy"] > cold["mean_bit_accuracy"]
        ),
    }


def run_transfer_matrix(
    *,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    scenarios: tuple[str, ...] = TASK_SCENARIOS,
) -> dict[str, object]:
    matrix: dict[str, object] = {}
    for train_scenario, transfer_scenario in itertools.permutations(scenarios, 2):
        key = f"{train_scenario}->{transfer_scenario}"
        results = [
            transfer_pair_for_seed(train_scenario, transfer_scenario, seed)
            for seed in seeds
        ]
        matrix[key] = {
            "train_scenario": train_scenario,
            "transfer_scenario": transfer_scenario,
            "seeds": list(seeds),
            "aggregate": aggregate_pair(results),
            "results": results,
        }
    return {
        "scenarios": list(scenarios),
        "seeds": list(seeds),
        "matrix": matrix,
    }


def main() -> None:
    print(json.dumps(run_transfer_matrix(), indent=2))


if __name__ == "__main__":
    main()
