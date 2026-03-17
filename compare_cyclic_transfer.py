"""Cyclic transfer evaluation: A -> B -> C -> A."""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from statistics import mean

from compare_cold_warm import ROOT
from compare_sequential_transfer import run_scenario
from experiment_manifest import build_run_manifest, write_run_manifest

DEFAULT_SEEDS = (13, 23, 37, 51, 79)

TASK_A = "cvt1_task_a_stage1"
TASK_B = "cvt1_task_b_stage1"
TASK_C = "cvt1_task_c_stage1"


def _delta_summary(warm: dict[str, object], cold: dict[str, object]) -> dict[str, float]:
    return {
        "exact_matches": int(warm["exact_matches"]) - int(cold["exact_matches"]),
        "mean_bit_accuracy": round(
            float(warm["mean_bit_accuracy"]) - float(cold["mean_bit_accuracy"]),
            4,
        ),
    }


def cyclic_transfer_for_seed(
    seed: int,
    *,
    latent_context: bool = False,
    source_sequence_context_enabled: bool = True,
) -> dict[str, object]:
    base_dir = ROOT / "tests_tmp" / f"cyclic_transfer_{uuid.uuid4().hex}"
    dir_a = base_dir / "a"
    dir_b = base_dir / "b"
    dir_c = base_dir / "c"
    for directory in (dir_a, dir_b, dir_c):
        directory.mkdir(parents=True, exist_ok=True)

    try:
        sys_a_cold, sum_a_cold = run_scenario(
            seed,
            TASK_A,
            latent_context=latent_context,
            source_sequence_context_enabled=source_sequence_context_enabled,
        )
        sys_a_cold.save_memory_carryover(dir_a)

        sys_b_from_a, sum_b_from_a = run_scenario(
            seed,
            TASK_B,
            latent_context=latent_context,
            source_sequence_context_enabled=source_sequence_context_enabled,
            carryover_dir=dir_a,
        )
        sys_b_from_a.save_memory_carryover(dir_b)

        sys_c_from_b, sum_c_from_b = run_scenario(
            seed,
            TASK_C,
            latent_context=latent_context,
            source_sequence_context_enabled=source_sequence_context_enabled,
            carryover_dir=dir_b,
        )
        sys_c_from_b.save_memory_carryover(dir_c)

        _, sum_a_from_c = run_scenario(
            seed,
            TASK_A,
            latent_context=latent_context,
            source_sequence_context_enabled=source_sequence_context_enabled,
            carryover_dir=dir_c,
        )
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)

    return {
        "seed": seed,
        "latent_context": latent_context,
        "source_sequence_context_enabled": source_sequence_context_enabled,
        "task_a_cold": sum_a_cold,
        "task_b_from_a": sum_b_from_a,
        "task_c_from_b": sum_c_from_b,
        "task_a_from_c": sum_a_from_c,
        "delta_vs_cold": _delta_summary(sum_a_from_c, sum_a_cold),
    }


def aggregate_cyclic(results: list[dict[str, object]]) -> dict[str, float]:
    def _avg(path: list[str]) -> float:
        values = []
        for result in results:
            obj: object = result
            for key in path:
                obj = obj[key]  # type: ignore[index]
            values.append(float(obj))
        return round(mean(values), 4)

    return {
        "avg_cold_a_exact_matches": _avg(["task_a_cold", "exact_matches"]),
        "avg_final_a_exact_matches": _avg(["task_a_from_c", "exact_matches"]),
        "avg_delta_exact_matches": _avg(["delta_vs_cold", "exact_matches"]),
        "avg_cold_a_bit_accuracy": _avg(["task_a_cold", "mean_bit_accuracy"]),
        "avg_final_a_bit_accuracy": _avg(["task_a_from_c", "mean_bit_accuracy"]),
        "avg_delta_mean_bit_accuracy": _avg(["delta_vs_cold", "mean_bit_accuracy"]),
    }


def evaluate_cyclic_transfer(
    *,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    latent_context: bool = False,
    source_sequence_context_enabled: bool = True,
    output_path: Path | None = None,
) -> dict[str, object]:
    results = [
        cyclic_transfer_for_seed(
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
        "task_sequence": [TASK_A, TASK_B, TASK_C, TASK_A],
        "results": results,
        "aggregate": aggregate_cyclic(results),
    }
    if output_path is not None:
        manifest = build_run_manifest(
            harness="cyclic_transfer",
            seeds=seeds,
            scenarios=(TASK_A, TASK_B, TASK_C, TASK_A),
            latent_context=latent_context,
            metadata={
                "source_sequence_context_enabled": source_sequence_context_enabled,
                "task_sequence": result["task_sequence"],
            },
            result=result,
        )
        write_run_manifest(output_path, manifest)
    return result


def main() -> None:
    print(json.dumps(evaluate_cyclic_transfer(), indent=2))


if __name__ == "__main__":
    main()
