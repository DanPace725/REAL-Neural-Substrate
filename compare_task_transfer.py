from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from statistics import mean

from compare_cold_warm import ROOT, SCENARIOS, build_system, run_workload


TRAIN_SCENARIO = "cvt1_task_a_stage1"
TRANSFER_SCENARIO = "cvt1_task_b_stage1"
CRITERION_WINDOW = 8
EXACT_THRESHOLD = 0.85
BIT_ACCURACY_THRESHOLD = 0.95


def _ordered_scored_packets(system) -> list[object]:
    return sorted(
        [
            packet
            for packet in system.environment.delivered_packets
            if packet.bit_match_ratio is not None
        ],
        key=lambda packet: (
            packet.delivered_cycle if packet.delivered_cycle is not None else system.global_cycle,
            packet.created_cycle,
            packet.packet_id,
        ),
    )


def transfer_metrics(system) -> dict[str, object]:
    packets = _ordered_scored_packets(system)
    if not packets:
        return {
            "packets_evaluated": 0,
            "criterion_window": CRITERION_WINDOW,
            "criterion_reached": False,
            "examples_to_criterion": None,
            "cycles_to_criterion": None,
            "best_rolling_exact_rate": 0.0,
            "best_rolling_bit_accuracy": 0.0,
        }

    best_exact = 0.0
    best_accuracy = 0.0
    examples_to_criterion = None
    cycles_to_criterion = None
    for end in range(CRITERION_WINDOW, len(packets) + 1):
        window = packets[end - CRITERION_WINDOW : end]
        exact_rate = sum(1 for packet in window if packet.matched_target) / CRITERION_WINDOW
        bit_accuracy = sum(float(packet.bit_match_ratio or 0.0) for packet in window) / CRITERION_WINDOW
        best_exact = max(best_exact, exact_rate)
        best_accuracy = max(best_accuracy, bit_accuracy)
        if (
            examples_to_criterion is None
            and exact_rate >= EXACT_THRESHOLD
            and bit_accuracy >= BIT_ACCURACY_THRESHOLD
        ):
            examples_to_criterion = end
            cycles_to_criterion = window[-1].delivered_cycle

    return {
        "packets_evaluated": len(packets),
        "criterion_window": CRITERION_WINDOW,
        "criterion_reached": examples_to_criterion is not None,
        "examples_to_criterion": examples_to_criterion,
        "cycles_to_criterion": cycles_to_criterion,
        "best_rolling_exact_rate": round(best_exact, 4),
        "best_rolling_bit_accuracy": round(best_accuracy, 4),
    }


def _context_stat(summary: dict[str, object], context_key: str, field: str) -> float:
    return float(summary.get("task_diagnostics", {}).get("contexts", {}).get(context_key, {}).get(field, 0.0))


def _overall_stat(summary: dict[str, object], field: str) -> float:
    return float(summary.get("task_diagnostics", {}).get("overall", {}).get(field, 0.0))


def _run_transfer_system(seed: int, scenario_name: str):
    system = build_system(seed, scenario_name)
    summary = run_workload(system, scenario_name)
    metrics = transfer_metrics(system)
    return system, summary, metrics


def transfer_for_seed(seed: int) -> dict[str, object]:
    training, training_summary, training_metrics = _run_transfer_system(seed, TRAIN_SCENARIO)

    base_dir = ROOT / "tests_tmp" / f"transfer_{uuid.uuid4().hex}"
    full_dir = base_dir / "full"
    substrate_dir = base_dir / "substrate"
    full_dir.mkdir(parents=True, exist_ok=True)
    substrate_dir.mkdir(parents=True, exist_ok=True)
    try:
        training.save_memory_carryover(full_dir)
        training.save_substrate_carryover(substrate_dir)

        cold_task_b, cold_summary, cold_metrics = _run_transfer_system(seed, TRANSFER_SCENARIO)

        warm_full = build_system(seed, TRANSFER_SCENARIO)
        warm_full.load_memory_carryover(full_dir)
        warm_full_summary = run_workload(warm_full, TRANSFER_SCENARIO)
        warm_full_metrics = transfer_metrics(warm_full)

        warm_substrate = build_system(seed, TRANSFER_SCENARIO)
        warm_substrate.load_substrate_carryover(substrate_dir)
        warm_substrate_summary = run_workload(warm_substrate, TRANSFER_SCENARIO)
        warm_substrate_metrics = transfer_metrics(warm_substrate)
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)

    return {
        "seed": seed,
        "train_scenario": TRAIN_SCENARIO,
        "transfer_scenario": TRANSFER_SCENARIO,
        "training_task_a": {
            "summary": training_summary,
            "transfer_metrics": training_metrics,
        },
        "cold_task_b": {
            "summary": cold_summary,
            "transfer_metrics": cold_metrics,
        },
        "warm_full_task_b": {
            "summary": warm_full_summary,
            "transfer_metrics": warm_full_metrics,
        },
        "warm_substrate_task_b": {
            "summary": warm_substrate_summary,
            "transfer_metrics": warm_substrate_metrics,
        },
        "delta_full_task_b": {
            "exact_matches": warm_full_summary["exact_matches"] - cold_summary["exact_matches"],
            "mean_bit_accuracy": round(
                warm_full_summary["mean_bit_accuracy"] - cold_summary["mean_bit_accuracy"],
                4,
            ),
            "mean_route_cost": round(
                warm_full_summary["mean_route_cost"] - cold_summary["mean_route_cost"],
                5,
            ),
            "best_rolling_exact_rate": round(
                warm_full_metrics["best_rolling_exact_rate"] - cold_metrics["best_rolling_exact_rate"],
                4,
            ),
            "best_rolling_bit_accuracy": round(
                warm_full_metrics["best_rolling_bit_accuracy"] - cold_metrics["best_rolling_bit_accuracy"],
                4,
            ),
        },
        "delta_substrate_task_b": {
            "exact_matches": warm_substrate_summary["exact_matches"] - cold_summary["exact_matches"],
            "mean_bit_accuracy": round(
                warm_substrate_summary["mean_bit_accuracy"] - cold_summary["mean_bit_accuracy"],
                4,
            ),
            "mean_route_cost": round(
                warm_substrate_summary["mean_route_cost"] - cold_summary["mean_route_cost"],
                5,
            ),
            "best_rolling_exact_rate": round(
                warm_substrate_metrics["best_rolling_exact_rate"] - cold_metrics["best_rolling_exact_rate"],
                4,
            ),
            "best_rolling_bit_accuracy": round(
                warm_substrate_metrics["best_rolling_bit_accuracy"] - cold_metrics["best_rolling_bit_accuracy"],
                4,
            ),
        },
    }


def aggregate_transfer(results: list[dict[str, object]]) -> dict[str, float]:
    return {
        "avg_cold_task_b_exact_matches": round(mean(item["cold_task_b"]["summary"]["exact_matches"] for item in results), 4),
        "avg_warm_full_task_b_exact_matches": round(mean(item["warm_full_task_b"]["summary"]["exact_matches"] for item in results), 4),
        "avg_warm_substrate_task_b_exact_matches": round(mean(item["warm_substrate_task_b"]["summary"]["exact_matches"] for item in results), 4),
        "avg_cold_task_b_bit_accuracy": round(mean(item["cold_task_b"]["summary"]["mean_bit_accuracy"] for item in results), 4),
        "avg_warm_full_task_b_bit_accuracy": round(mean(item["warm_full_task_b"]["summary"]["mean_bit_accuracy"] for item in results), 4),
        "avg_warm_substrate_task_b_bit_accuracy": round(mean(item["warm_substrate_task_b"]["summary"]["mean_bit_accuracy"] for item in results), 4),
        "avg_cold_task_b_route_cost": round(mean(item["cold_task_b"]["summary"]["mean_route_cost"] for item in results), 5),
        "avg_warm_full_task_b_route_cost": round(mean(item["warm_full_task_b"]["summary"]["mean_route_cost"] for item in results), 5),
        "avg_warm_substrate_task_b_route_cost": round(mean(item["warm_substrate_task_b"]["summary"]["mean_route_cost"] for item in results), 5),
        "avg_delta_full_task_b_exact_matches": round(mean(item["delta_full_task_b"]["exact_matches"] for item in results), 4),
        "avg_delta_substrate_task_b_exact_matches": round(mean(item["delta_substrate_task_b"]["exact_matches"] for item in results), 4),
        "avg_delta_full_task_b_bit_accuracy": round(mean(item["delta_full_task_b"]["mean_bit_accuracy"] for item in results), 4),
        "avg_delta_substrate_task_b_bit_accuracy": round(mean(item["delta_substrate_task_b"]["mean_bit_accuracy"] for item in results), 4),
        "avg_delta_full_task_b_best_exact_rate": round(mean(item["delta_full_task_b"]["best_rolling_exact_rate"] for item in results), 4),
        "avg_delta_substrate_task_b_best_exact_rate": round(mean(item["delta_substrate_task_b"]["best_rolling_exact_rate"] for item in results), 4),
        "avg_delta_full_task_b_best_bit_accuracy": round(mean(item["delta_full_task_b"]["best_rolling_bit_accuracy"] for item in results), 4),
        "avg_delta_substrate_task_b_best_bit_accuracy": round(mean(item["delta_substrate_task_b"]["best_rolling_bit_accuracy"] for item in results), 4),
        "avg_cold_task_b_context_1_bit_accuracy": round(mean(_context_stat(item["cold_task_b"]["summary"], "context_1", "mean_bit_accuracy") for item in results), 4),
        "avg_warm_full_task_b_context_1_bit_accuracy": round(mean(_context_stat(item["warm_full_task_b"]["summary"], "context_1", "mean_bit_accuracy") for item in results), 4),
        "avg_warm_substrate_task_b_context_1_bit_accuracy": round(mean(_context_stat(item["warm_substrate_task_b"]["summary"], "context_1", "mean_bit_accuracy") for item in results), 4),
        "avg_cold_task_b_wrong_transform_family": round(mean(_overall_stat(item["cold_task_b"]["summary"], "wrong_transform_family") for item in results), 4),
        "avg_warm_full_task_b_wrong_transform_family": round(mean(_overall_stat(item["warm_full_task_b"]["summary"], "wrong_transform_family") for item in results), 4),
        "avg_warm_substrate_task_b_wrong_transform_family": round(mean(_overall_stat(item["warm_substrate_task_b"]["summary"], "wrong_transform_family") for item in results), 4),
        "avg_cold_task_b_identity_fallbacks": round(mean(_overall_stat(item["cold_task_b"]["summary"], "identity_fallbacks") for item in results), 4),
        "avg_warm_full_task_b_identity_fallbacks": round(mean(_overall_stat(item["warm_full_task_b"]["summary"], "identity_fallbacks") for item in results), 4),
        "avg_warm_substrate_task_b_identity_fallbacks": round(mean(_overall_stat(item["warm_substrate_task_b"]["summary"], "identity_fallbacks") for item in results), 4),
        "avg_cold_task_b_stale_support_suspicions": round(mean(_overall_stat(item["cold_task_b"]["summary"], "stale_context_support_suspicions") for item in results), 4),
        "avg_warm_full_task_b_stale_support_suspicions": round(mean(_overall_stat(item["warm_full_task_b"]["summary"], "stale_context_support_suspicions") for item in results), 4),
        "avg_warm_substrate_task_b_stale_support_suspicions": round(mean(_overall_stat(item["warm_substrate_task_b"]["summary"], "stale_context_support_suspicions") for item in results), 4),
    }


def main() -> None:
    seeds = [13, 23, 37, 51, 79]
    results = [transfer_for_seed(seed) for seed in seeds]
    summary = {
        "train_scenario": TRAIN_SCENARIO,
        "transfer_scenario": TRANSFER_SCENARIO,
        "criterion_window": CRITERION_WINDOW,
        "exact_threshold": EXACT_THRESHOLD,
        "bit_accuracy_threshold": BIT_ACCURACY_THRESHOLD,
        "results": results,
        "aggregate": aggregate_transfer(results),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
