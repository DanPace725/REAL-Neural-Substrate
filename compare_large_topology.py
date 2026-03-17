"""Cold/warm and A→B transfer evaluation on the 10-node large topology (36-packet sessions).

Runs each of three tasks cold, then tests A→B transfer on the larger graph.
Morphogenesis is disabled here — use compare_morphogenesis.py with the *_large
scenario names to run morphogenesis on the expanded topology.
"""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from statistics import mean

from compare_cold_warm import ROOT, SCENARIOS, build_system, run_workload
from compare_task_transfer import transfer_metrics

DEFAULT_SEEDS = (13, 23, 37, 51, 79)

TASK_A = "cvt1_task_a_large"
TASK_B = "cvt1_task_b_large"
TASK_C = "cvt1_task_c_large"


def _context_stat(summary: dict[str, object], context_key: str, field: str) -> float:
    return float(
        summary.get("task_diagnostics", {})
        .get("contexts", {})
        .get(context_key, {})
        .get(field, 0.0)
    )


def large_topology_for_seed(seed: int) -> dict[str, object]:
    base_dir = ROOT / "tests_tmp" / f"large_topo_{uuid.uuid4().hex}"
    dir_a = base_dir / "a"
    dir_a.mkdir(parents=True, exist_ok=True)

    try:
        # ── Cold runs for all three tasks ─────────────────────────────────
        sys_a = build_system(seed, TASK_A)
        sum_a = run_workload(sys_a, TASK_A)
        sys_a.save_memory_carryover(dir_a)

        sys_b_cold = build_system(seed, TASK_B)
        sum_b_cold = run_workload(sys_b_cold, TASK_B)

        sys_c_cold = build_system(seed, TASK_C)
        sum_c_cold = run_workload(sys_c_cold, TASK_C)

        # ── A→B transfer ──────────────────────────────────────────────────
        sys_b_warm = build_system(seed, TASK_B)
        sys_b_warm.load_memory_carryover(dir_a)
        sum_b_warm = run_workload(sys_b_warm, TASK_B)

    finally:
        shutil.rmtree(base_dir, ignore_errors=True)

    def _delta(warm: dict, cold: dict) -> dict[str, object]:
        return {
            "exact_matches": int(warm["exact_matches"]) - int(cold["exact_matches"]),
            "mean_bit_accuracy": round(
                float(warm["mean_bit_accuracy"]) - float(cold["mean_bit_accuracy"]), 4
            ),
            "ctx0_bit_accuracy": round(
                _context_stat(warm, "context_0", "mean_bit_accuracy")
                - _context_stat(cold, "context_0", "mean_bit_accuracy"),
                4,
            ),
            "ctx1_bit_accuracy": round(
                _context_stat(warm, "context_1", "mean_bit_accuracy")
                - _context_stat(cold, "context_1", "mean_bit_accuracy"),
                4,
            ),
        }

    return {
        "seed": seed,
        "task_a_cold": {
            "summary": sum_a,
            "transfer_metrics": transfer_metrics(sys_a),
        },
        "task_b_cold": {
            "summary": sum_b_cold,
            "transfer_metrics": transfer_metrics(sys_b_cold),
        },
        "task_c_cold": {
            "summary": sum_c_cold,
            "transfer_metrics": transfer_metrics(sys_c_cold),
        },
        "task_b_warm": {
            "summary": sum_b_warm,
            "transfer_metrics": transfer_metrics(sys_b_warm),
            "delta_vs_cold": _delta(sum_b_warm, sum_b_cold),
        },
    }


def aggregate_large(results: list[dict[str, object]]) -> dict[str, object]:
    def _avg(key_path: list[str]) -> float:
        vals = []
        for r in results:
            obj = r
            for k in key_path:
                obj = obj[k]
            vals.append(float(obj))
        return round(mean(vals), 4)

    return {
        # ── Cold baselines ─────────────────────────────────────────────
        "avg_task_a_cold_exact": _avg(["task_a_cold", "summary", "exact_matches"]),
        "avg_task_a_cold_bit_accuracy": _avg(["task_a_cold", "summary", "mean_bit_accuracy"]),
        "avg_task_b_cold_exact": _avg(["task_b_cold", "summary", "exact_matches"]),
        "avg_task_b_cold_bit_accuracy": _avg(["task_b_cold", "summary", "mean_bit_accuracy"]),
        "avg_task_c_cold_exact": _avg(["task_c_cold", "summary", "exact_matches"]),
        "avg_task_c_cold_bit_accuracy": _avg(["task_c_cold", "summary", "mean_bit_accuracy"]),
        # ── A→B transfer ──────────────────────────────────────────────────
        "avg_task_b_warm_exact": _avg(["task_b_warm", "summary", "exact_matches"]),
        "avg_task_b_warm_bit_accuracy": _avg(["task_b_warm", "summary", "mean_bit_accuracy"]),
        "avg_delta_b_exact": _avg(["task_b_warm", "delta_vs_cold", "exact_matches"]),
        "avg_delta_b_bit_accuracy": _avg(["task_b_warm", "delta_vs_cold", "mean_bit_accuracy"]),
        "avg_delta_b_ctx0": _avg(["task_b_warm", "delta_vs_cold", "ctx0_bit_accuracy"]),
        "avg_delta_b_ctx1": _avg(["task_b_warm", "delta_vs_cold", "ctx1_bit_accuracy"]),
    }


def evaluate_large_topology(
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
) -> dict[str, object]:
    results = [large_topology_for_seed(seed) for seed in seeds]
    return {
        "seeds": list(seeds),
        "topology": "cvt1_large (10 nodes, 5-hop paths)",
        "signal_set": "stage2 (36 packets)",
        "task_a_scenario": TASK_A,
        "task_b_scenario": TASK_B,
        "task_c_scenario": TASK_C,
        "results": results,
        "aggregate": aggregate_large(results),
    }


def main() -> None:
    print(json.dumps(evaluate_large_topology(), indent=2))


if __name__ == "__main__":
    main()
