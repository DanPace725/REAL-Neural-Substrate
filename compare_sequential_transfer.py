"""Sequential three-task transfer evaluation: A → B → C.

Measures:
  - A→B transfer (baseline, for comparison with compare_task_transfer.py)
  - B→C transfer: does shared ctx1=xor_0101 help, or does stale ctx0=rotate_left_1 hurt?
  - A→B→C chain: warm B (trained with A carryover) → C
  - A→C direct: skip B entirely; how much does the intermediate task matter?

All conditions use full memory carryover (edge + action supports).
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

TASK_A = "cvt1_task_a_stage1"
TASK_B = "cvt1_task_b_stage1"
TASK_C = "cvt1_task_c_stage1"


def _context_stat(summary: dict[str, object], context_key: str, field: str) -> float:
    return float(
        summary.get("task_diagnostics", {})
        .get("contexts", {})
        .get(context_key, {})
        .get(field, 0.0)
    )


def sequential_transfer_for_seed(seed: int) -> dict[str, object]:
    """Run the full A→B→C evaluation chain for a single seed."""
    base_dir = ROOT / "tests_tmp" / f"seq_transfer_{uuid.uuid4().hex}"
    dir_a = base_dir / "a"
    dir_b_cold = base_dir / "b_cold"
    dir_b_warm = base_dir / "b_warm"
    for d in (dir_a, dir_b_cold, dir_b_warm):
        d.mkdir(parents=True, exist_ok=True)

    try:
        # ── Task A (cold) ───────────────────────────────────────────────
        sys_a = build_system(seed, TASK_A)
        sum_a = run_workload(sys_a, TASK_A)
        sys_a.save_memory_carryover(dir_a)

        # ── Task B cold (control) ────────────────────────────────────────
        sys_b_cold = build_system(seed, TASK_B)
        sum_b_cold = run_workload(sys_b_cold, TASK_B)
        sys_b_cold.save_memory_carryover(dir_b_cold)

        # ── Task B warm from A (A→B) ─────────────────────────────────────
        sys_b_warm = build_system(seed, TASK_B)
        sys_b_warm.load_memory_carryover(dir_a)
        sum_b_warm = run_workload(sys_b_warm, TASK_B)
        sys_b_warm.save_memory_carryover(dir_b_warm)

        # ── Task C cold (control) ────────────────────────────────────────
        sys_c_cold = build_system(seed, TASK_C)
        sum_c_cold = run_workload(sys_c_cold, TASK_C)

        # ── Task C warm from cold B (B→C, no A context) ──────────────────
        sys_c_from_cold_b = build_system(seed, TASK_C)
        sys_c_from_cold_b.load_memory_carryover(dir_b_cold)
        sum_c_from_cold_b = run_workload(sys_c_from_cold_b, TASK_C)

        # ── Task C warm from warm B (A→B→C chain) ───────────────────────
        sys_c_from_warm_b = build_system(seed, TASK_C)
        sys_c_from_warm_b.load_memory_carryover(dir_b_warm)
        sum_c_from_warm_b = run_workload(sys_c_from_warm_b, TASK_C)

        # ── Task C warm directly from A (A→C, skip B) ───────────────────
        sys_c_from_a = build_system(seed, TASK_C)
        sys_c_from_a.load_memory_carryover(dir_a)
        sum_c_from_a = run_workload(sys_c_from_a, TASK_C)

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
        "task_a": {
            "summary": sum_a,
            "transfer_metrics": transfer_metrics(sys_a),
        },
        "cold_b": {
            "summary": sum_b_cold,
            "transfer_metrics": transfer_metrics(sys_b_cold),
        },
        "warm_b_from_a": {
            "summary": sum_b_warm,
            "transfer_metrics": transfer_metrics(sys_b_warm),
            "delta_vs_cold": _delta(sum_b_warm, sum_b_cold),
        },
        "cold_c": {
            "summary": sum_c_cold,
            "transfer_metrics": transfer_metrics(sys_c_cold),
        },
        "warm_c_from_cold_b": {
            "summary": sum_c_from_cold_b,
            "transfer_metrics": transfer_metrics(sys_c_from_cold_b),
            "delta_vs_cold": _delta(sum_c_from_cold_b, sum_c_cold),
        },
        "warm_c_from_warm_b": {
            "summary": sum_c_from_warm_b,
            "transfer_metrics": transfer_metrics(sys_c_from_warm_b),
            "delta_vs_cold": _delta(sum_c_from_warm_b, sum_c_cold),
        },
        "warm_c_from_a": {
            "summary": sum_c_from_a,
            "transfer_metrics": transfer_metrics(sys_c_from_a),
            "delta_vs_cold": _delta(sum_c_from_a, sum_c_cold),
        },
    }


def aggregate_sequential(results: list[dict[str, object]]) -> dict[str, object]:
    def _avg(key_path: list[str]) -> float:
        vals = []
        for r in results:
            obj = r
            for k in key_path:
                obj = obj[k]
            vals.append(float(obj))
        return round(mean(vals), 4)

    return {
        # ── Task A baseline ──────────────────────────────────────────────
        "avg_task_a_exact": _avg(["task_a", "summary", "exact_matches"]),
        "avg_task_a_bit_accuracy": _avg(["task_a", "summary", "mean_bit_accuracy"]),
        # ── Task B: cold vs warm from A ──────────────────────────────────
        "avg_cold_b_exact": _avg(["cold_b", "summary", "exact_matches"]),
        "avg_warm_b_exact": _avg(["warm_b_from_a", "summary", "exact_matches"]),
        "avg_delta_b_exact": _avg(["warm_b_from_a", "delta_vs_cold", "exact_matches"]),
        "avg_cold_b_bit_accuracy": _avg(["cold_b", "summary", "mean_bit_accuracy"]),
        "avg_warm_b_bit_accuracy": _avg(["warm_b_from_a", "summary", "mean_bit_accuracy"]),
        "avg_delta_b_bit_accuracy": _avg(["warm_b_from_a", "delta_vs_cold", "mean_bit_accuracy"]),
        "avg_warm_b_ctx0_delta": _avg(["warm_b_from_a", "delta_vs_cold", "ctx0_bit_accuracy"]),
        "avg_warm_b_ctx1_delta": _avg(["warm_b_from_a", "delta_vs_cold", "ctx1_bit_accuracy"]),
        # ── Task C: cold ─────────────────────────────────────────────────
        "avg_cold_c_exact": _avg(["cold_c", "summary", "exact_matches"]),
        "avg_cold_c_bit_accuracy": _avg(["cold_c", "summary", "mean_bit_accuracy"]),
        # ── Task C: warm from cold B (B→C) ───────────────────────────────
        "avg_warm_c_from_cold_b_exact": _avg(["warm_c_from_cold_b", "summary", "exact_matches"]),
        "avg_warm_c_from_cold_b_bit_accuracy": _avg(["warm_c_from_cold_b", "summary", "mean_bit_accuracy"]),
        "avg_delta_c_from_cold_b_exact": _avg(["warm_c_from_cold_b", "delta_vs_cold", "exact_matches"]),
        "avg_delta_c_from_cold_b_bit_accuracy": _avg(["warm_c_from_cold_b", "delta_vs_cold", "mean_bit_accuracy"]),
        "avg_delta_c_from_cold_b_ctx0": _avg(["warm_c_from_cold_b", "delta_vs_cold", "ctx0_bit_accuracy"]),
        "avg_delta_c_from_cold_b_ctx1": _avg(["warm_c_from_cold_b", "delta_vs_cold", "ctx1_bit_accuracy"]),
        # ── Task C: warm from warm B (A→B→C chain) ───────────────────────
        "avg_warm_c_from_warm_b_exact": _avg(["warm_c_from_warm_b", "summary", "exact_matches"]),
        "avg_warm_c_from_warm_b_bit_accuracy": _avg(["warm_c_from_warm_b", "summary", "mean_bit_accuracy"]),
        "avg_delta_c_from_warm_b_exact": _avg(["warm_c_from_warm_b", "delta_vs_cold", "exact_matches"]),
        "avg_delta_c_from_warm_b_bit_accuracy": _avg(["warm_c_from_warm_b", "delta_vs_cold", "mean_bit_accuracy"]),
        "avg_delta_c_from_warm_b_ctx0": _avg(["warm_c_from_warm_b", "delta_vs_cold", "ctx0_bit_accuracy"]),
        "avg_delta_c_from_warm_b_ctx1": _avg(["warm_c_from_warm_b", "delta_vs_cold", "ctx1_bit_accuracy"]),
        # ── Task C: warm directly from A (A→C skip) ──────────────────────
        "avg_warm_c_from_a_exact": _avg(["warm_c_from_a", "summary", "exact_matches"]),
        "avg_warm_c_from_a_bit_accuracy": _avg(["warm_c_from_a", "summary", "mean_bit_accuracy"]),
        "avg_delta_c_from_a_exact": _avg(["warm_c_from_a", "delta_vs_cold", "exact_matches"]),
        "avg_delta_c_from_a_bit_accuracy": _avg(["warm_c_from_a", "delta_vs_cold", "mean_bit_accuracy"]),
        "avg_delta_c_from_a_ctx0": _avg(["warm_c_from_a", "delta_vs_cold", "ctx0_bit_accuracy"]),
        "avg_delta_c_from_a_ctx1": _avg(["warm_c_from_a", "delta_vs_cold", "ctx1_bit_accuracy"]),
    }


def evaluate_sequential_transfer(
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
) -> dict[str, object]:
    results = [sequential_transfer_for_seed(seed) for seed in seeds]
    return {
        "seeds": list(seeds),
        "task_a_scenario": TASK_A,
        "task_b_scenario": TASK_B,
        "task_c_scenario": TASK_C,
        "results": results,
        "aggregate": aggregate_sequential(results),
    }


def main() -> None:
    print(json.dumps(evaluate_sequential_transfer(), indent=2))


if __name__ == "__main__":
    main()
