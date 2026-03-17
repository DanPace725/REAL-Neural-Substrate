"""Sequential three-task transfer evaluation: A â†’ B â†’ C.

Measures:
  - Aâ†’B transfer (baseline, for comparison with compare_task_transfer.py)
  - Bâ†’C transfer: does shared ctx1=xor_0101 help, or does stale ctx0=rotate_left_1 hurt?
  - Aâ†’Bâ†’C chain: warm B (trained with A carryover) â†’ C
  - Aâ†’C direct: skip B entirely; how much does the intermediate task matter?

All conditions use full memory carryover (edge + action supports).
"""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from statistics import mean

from scripts.compare_cold_warm import ROOT, SCENARIOS, build_system
from scripts.compare_latent_context import latent_signal_specs
from scripts.compare_task_transfer import transfer_metrics
from scripts.experiment_manifest import build_run_manifest, write_run_manifest

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


def run_scenario(
    seed: int,
    scenario_name: str,
    *,
    latent_context: bool,
    source_sequence_context_enabled: bool,
    carryover_dir: Path | None = None,
) -> tuple[object, dict[str, object]]:
    scenario = SCENARIOS[scenario_name]
    system = build_system(
        seed,
        scenario_name,
        source_sequence_context_enabled=source_sequence_context_enabled,
    )
    initial_specs = scenario.initial_signal_specs
    schedule_specs = scenario.signal_schedule_specs
    if latent_context:
        initial_specs, schedule_specs = latent_signal_specs(scenario_name)
    if carryover_dir is not None:
        system.load_memory_carryover(carryover_dir)
    result = system.run_workload(
        cycles=scenario.cycles,
        initial_packets=scenario.initial_packets,
        packet_schedule=scenario.packet_schedule,
        initial_signal_specs=initial_specs,
        signal_schedule_specs=schedule_specs,
    )
    return system, result["summary"]


def sequential_transfer_for_seed(
    seed: int,
    *,
    latent_context: bool = False,
    source_sequence_context_enabled: bool = True,
) -> dict[str, object]:
    """Run the full Aâ†’Bâ†’C evaluation chain for a single seed."""
    base_dir = ROOT / "tests_tmp" / f"seq_transfer_{uuid.uuid4().hex}"
    dir_a = base_dir / "a"
    dir_b_cold = base_dir / "b_cold"
    dir_b_warm = base_dir / "b_warm"
    for d in (dir_a, dir_b_cold, dir_b_warm):
        d.mkdir(parents=True, exist_ok=True)

    try:
        # â”€â”€ Task A (cold) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        sys_a, sum_a = run_scenario(
            seed,
            TASK_A,
            latent_context=latent_context,
            source_sequence_context_enabled=source_sequence_context_enabled,
        )
        sys_a.save_memory_carryover(dir_a)

        # â”€â”€ Task B cold (control) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        sys_b_cold, sum_b_cold = run_scenario(
            seed,
            TASK_B,
            latent_context=latent_context,
            source_sequence_context_enabled=source_sequence_context_enabled,
        )
        sys_b_cold.save_memory_carryover(dir_b_cold)

        # â”€â”€ Task B warm from A (Aâ†’B) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        sys_b_warm, sum_b_warm = run_scenario(
            seed,
            TASK_B,
            latent_context=latent_context,
            source_sequence_context_enabled=source_sequence_context_enabled,
            carryover_dir=dir_a,
        )
        sys_b_warm.save_memory_carryover(dir_b_warm)

        # â”€â”€ Task C cold (control) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        sys_c_cold, sum_c_cold = run_scenario(
            seed,
            TASK_C,
            latent_context=latent_context,
            source_sequence_context_enabled=source_sequence_context_enabled,
        )

        # â”€â”€ Task C warm from cold B (Bâ†’C, no A context) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        sys_c_from_cold_b, sum_c_from_cold_b = run_scenario(
            seed,
            TASK_C,
            latent_context=latent_context,
            source_sequence_context_enabled=source_sequence_context_enabled,
            carryover_dir=dir_b_cold,
        )

        # â”€â”€ Task C warm from warm B (Aâ†’Bâ†’C chain) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        sys_c_from_warm_b, sum_c_from_warm_b = run_scenario(
            seed,
            TASK_C,
            latent_context=latent_context,
            source_sequence_context_enabled=source_sequence_context_enabled,
            carryover_dir=dir_b_warm,
        )

        # â”€â”€ Task C warm directly from A (Aâ†’C, skip B) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        sys_c_from_a, sum_c_from_a = run_scenario(
            seed,
            TASK_C,
            latent_context=latent_context,
            source_sequence_context_enabled=source_sequence_context_enabled,
            carryover_dir=dir_a,
        )

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
        "latent_context": latent_context,
        "source_sequence_context_enabled": source_sequence_context_enabled,
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
        # â”€â”€ Task A baseline â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        "avg_task_a_exact": _avg(["task_a", "summary", "exact_matches"]),
        "avg_task_a_bit_accuracy": _avg(["task_a", "summary", "mean_bit_accuracy"]),
        # â”€â”€ Task B: cold vs warm from A â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        "avg_cold_b_exact": _avg(["cold_b", "summary", "exact_matches"]),
        "avg_warm_b_exact": _avg(["warm_b_from_a", "summary", "exact_matches"]),
        "avg_delta_b_exact": _avg(["warm_b_from_a", "delta_vs_cold", "exact_matches"]),
        "avg_cold_b_bit_accuracy": _avg(["cold_b", "summary", "mean_bit_accuracy"]),
        "avg_warm_b_bit_accuracy": _avg(["warm_b_from_a", "summary", "mean_bit_accuracy"]),
        "avg_delta_b_bit_accuracy": _avg(["warm_b_from_a", "delta_vs_cold", "mean_bit_accuracy"]),
        "avg_warm_b_ctx0_delta": _avg(["warm_b_from_a", "delta_vs_cold", "ctx0_bit_accuracy"]),
        "avg_warm_b_ctx1_delta": _avg(["warm_b_from_a", "delta_vs_cold", "ctx1_bit_accuracy"]),
        # â”€â”€ Task C: cold â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        "avg_cold_c_exact": _avg(["cold_c", "summary", "exact_matches"]),
        "avg_cold_c_bit_accuracy": _avg(["cold_c", "summary", "mean_bit_accuracy"]),
        # â”€â”€ Task C: warm from cold B (Bâ†’C) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        "avg_warm_c_from_cold_b_exact": _avg(["warm_c_from_cold_b", "summary", "exact_matches"]),
        "avg_warm_c_from_cold_b_bit_accuracy": _avg(["warm_c_from_cold_b", "summary", "mean_bit_accuracy"]),
        "avg_delta_c_from_cold_b_exact": _avg(["warm_c_from_cold_b", "delta_vs_cold", "exact_matches"]),
        "avg_delta_c_from_cold_b_bit_accuracy": _avg(["warm_c_from_cold_b", "delta_vs_cold", "mean_bit_accuracy"]),
        "avg_delta_c_from_cold_b_ctx0": _avg(["warm_c_from_cold_b", "delta_vs_cold", "ctx0_bit_accuracy"]),
        "avg_delta_c_from_cold_b_ctx1": _avg(["warm_c_from_cold_b", "delta_vs_cold", "ctx1_bit_accuracy"]),
        # â”€â”€ Task C: warm from warm B (Aâ†’Bâ†’C chain) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        "avg_warm_c_from_warm_b_exact": _avg(["warm_c_from_warm_b", "summary", "exact_matches"]),
        "avg_warm_c_from_warm_b_bit_accuracy": _avg(["warm_c_from_warm_b", "summary", "mean_bit_accuracy"]),
        "avg_delta_c_from_warm_b_exact": _avg(["warm_c_from_warm_b", "delta_vs_cold", "exact_matches"]),
        "avg_delta_c_from_warm_b_bit_accuracy": _avg(["warm_c_from_warm_b", "delta_vs_cold", "mean_bit_accuracy"]),
        "avg_delta_c_from_warm_b_ctx0": _avg(["warm_c_from_warm_b", "delta_vs_cold", "ctx0_bit_accuracy"]),
        "avg_delta_c_from_warm_b_ctx1": _avg(["warm_c_from_warm_b", "delta_vs_cold", "ctx1_bit_accuracy"]),
        # â”€â”€ Task C: warm directly from A (Aâ†’C skip) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        "avg_warm_c_from_a_exact": _avg(["warm_c_from_a", "summary", "exact_matches"]),
        "avg_warm_c_from_a_bit_accuracy": _avg(["warm_c_from_a", "summary", "mean_bit_accuracy"]),
        "avg_delta_c_from_a_exact": _avg(["warm_c_from_a", "delta_vs_cold", "exact_matches"]),
        "avg_delta_c_from_a_bit_accuracy": _avg(["warm_c_from_a", "delta_vs_cold", "mean_bit_accuracy"]),
        "avg_delta_c_from_a_ctx0": _avg(["warm_c_from_a", "delta_vs_cold", "ctx0_bit_accuracy"]),
        "avg_delta_c_from_a_ctx1": _avg(["warm_c_from_a", "delta_vs_cold", "ctx1_bit_accuracy"]),
    }


def evaluate_sequential_transfer(
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    *,
    latent_context: bool = False,
    source_sequence_context_enabled: bool = True,
    output_path: Path | None = None,
) -> dict[str, object]:
    results = [
        sequential_transfer_for_seed(
            seed,
            latent_context=latent_context,
            source_sequence_context_enabled=source_sequence_context_enabled,
        )
        for seed in seeds
    ]
    result = {
        "seeds": list(seeds),
        "latent_context": latent_context,
        "source_sequence_context_enabled": source_sequence_context_enabled,
        "task_a_scenario": TASK_A,
        "task_b_scenario": TASK_B,
        "task_c_scenario": TASK_C,
        "results": results,
        "aggregate": aggregate_sequential(results),
    }
    if output_path is not None:
        manifest = build_run_manifest(
            harness="sequential_transfer",
            seeds=seeds,
            scenarios=(TASK_A, TASK_B, TASK_C),
            latent_context=latent_context,
            metadata={
                "source_sequence_context_enabled": source_sequence_context_enabled,
                "task_a_scenario": TASK_A,
                "task_b_scenario": TASK_B,
                "task_c_scenario": TASK_C,
            },
            result=result,
        )
        write_run_manifest(output_path, manifest)
    return result


def main() -> None:
    print(json.dumps(evaluate_sequential_transfer(), indent=2))


if __name__ == "__main__":
    main()

