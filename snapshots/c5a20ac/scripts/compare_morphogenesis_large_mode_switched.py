"""Mode-switched morphogenesis on the 10-node large topology.

Compares three transfer policies on A -> B:
  - all_visible
  - all_latent
  - visible_train_latent_transfer
"""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from scripts.compare_cold_warm import ROOT
from scripts.compare_morphogenesis import (
    DEFAULT_SEEDS,
    _summary_delta,
    aggregate_transfer_growth_results,
    build_growth_system,
    build_system,
    growth_counts_as_earned,
    growth_counts_as_win,
    transfer_growth_for_seed,
    _run_growth_workload,
)
from scripts.compare_morphogenesis_large import TRAIN_SCENARIO, TRANSFER_SCENARIO
from scripts.experiment_manifest import build_run_manifest, write_run_manifest
from phase8 import MorphogenesisConfig


def mode_switched_transfer_for_seed(
    seed: int,
    *,
    morphogenesis_config: MorphogenesisConfig | None = None,
    source_sequence_context_enabled: bool = True,
    latent_transfer_split_enabled: bool = True,
) -> dict[str, object]:
    fixed_training = build_system(
        seed,
        TRAIN_SCENARIO,
        source_sequence_context_enabled=source_sequence_context_enabled,
        latent_transfer_split_enabled=latent_transfer_split_enabled,
    )
    fixed_training_summary = _run_growth_workload(
        fixed_training,
        TRAIN_SCENARIO,
        latent_context=False,
    )

    growth_training = build_growth_system(
        seed,
        TRAIN_SCENARIO,
        morphogenesis_config=morphogenesis_config,
        source_sequence_context_enabled=source_sequence_context_enabled,
        latent_transfer_split_enabled=latent_transfer_split_enabled,
    )
    growth_training_summary = _run_growth_workload(
        growth_training,
        TRAIN_SCENARIO,
        latent_context=False,
    )

    base_dir = ROOT / "tests_tmp" / f"mode_switched_large_{uuid.uuid4().hex}"
    fixed_dir = base_dir / "fixed"
    growth_dir = base_dir / "growth"
    fixed_dir.mkdir(parents=True, exist_ok=True)
    growth_dir.mkdir(parents=True, exist_ok=True)
    try:
        fixed_training.save_memory_carryover(fixed_dir)
        growth_training.save_memory_carryover(growth_dir)

        fixed_transfer = build_system(
            seed,
            TRANSFER_SCENARIO,
            source_sequence_context_enabled=source_sequence_context_enabled,
            latent_transfer_split_enabled=latent_transfer_split_enabled,
        )
        fixed_transfer.load_memory_carryover(fixed_dir)
        fixed_transfer_summary = _run_growth_workload(
            fixed_transfer,
            TRANSFER_SCENARIO,
            latent_context=True,
        )

        growth_transfer = build_growth_system(
            seed,
            TRANSFER_SCENARIO,
            morphogenesis_config=morphogenesis_config,
            source_sequence_context_enabled=source_sequence_context_enabled,
            latent_transfer_split_enabled=latent_transfer_split_enabled,
        )
        growth_transfer.load_memory_carryover(growth_dir)
        growth_transfer_summary = _run_growth_workload(
            growth_transfer,
            TRANSFER_SCENARIO,
            latent_context=True,
        )
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)

    return {
        "seed": seed,
        "policy": "visible_train_latent_transfer",
        "train_mode": "visible",
        "transfer_mode": "latent",
        "fixed_training": fixed_training_summary,
        "growth_training": {
            "summary": growth_training_summary,
            "earned_growth": growth_counts_as_earned(growth_training_summary),
        },
        "fixed_transfer": {
            "summary": fixed_transfer_summary,
        },
        "growth_transfer": {
            "summary": growth_transfer_summary,
            "earned_growth": growth_counts_as_earned(growth_transfer_summary),
            "growth_win": growth_counts_as_win(fixed_transfer_summary, growth_transfer_summary),
        },
        "delta": _summary_delta(fixed_transfer_summary, growth_transfer_summary),
    }


def _policy_comparison(
    visible_results: list[dict[str, object]],
    latent_results: list[dict[str, object]],
    switched_results: list[dict[str, object]],
) -> dict[str, object]:
    visible = aggregate_transfer_growth_results(visible_results)
    latent = aggregate_transfer_growth_results(latent_results)
    switched = aggregate_transfer_growth_results(switched_results)
    return {
        "all_visible": visible,
        "all_latent": latent,
        "visible_train_latent_transfer": switched,
        "switched_minus_visible": {
            "delta_transfer_exact_matches": round(
                switched["avg_delta_transfer_exact_matches"] - visible["avg_delta_transfer_exact_matches"],
                4,
            ),
            "delta_transfer_bit_accuracy": round(
                switched["avg_delta_transfer_bit_accuracy"] - visible["avg_delta_transfer_bit_accuracy"],
                4,
            ),
            "growth_transfer_win_rate": round(
                switched["growth_transfer_win_rate"] - visible["growth_transfer_win_rate"],
                4,
            ),
        },
        "switched_minus_latent": {
            "delta_transfer_exact_matches": round(
                switched["avg_delta_transfer_exact_matches"] - latent["avg_delta_transfer_exact_matches"],
                4,
            ),
            "delta_transfer_bit_accuracy": round(
                switched["avg_delta_transfer_bit_accuracy"] - latent["avg_delta_transfer_bit_accuracy"],
                4,
            ),
            "growth_transfer_win_rate": round(
                switched["growth_transfer_win_rate"] - latent["growth_transfer_win_rate"],
                4,
            ),
        },
    }


def evaluate_morphogenesis_large_mode_switched(
    *,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    morphogenesis_config: MorphogenesisConfig | None = None,
    source_sequence_context_enabled: bool = True,
    latent_transfer_split_enabled: bool = True,
    output_path: Path | None = None,
) -> dict[str, object]:
    visible_results = [
        transfer_growth_for_seed(
            seed,
            train_scenario=TRAIN_SCENARIO,
            transfer_scenario=TRANSFER_SCENARIO,
            morphogenesis_config=morphogenesis_config,
            latent_context=False,
            source_sequence_context_enabled=source_sequence_context_enabled,
            latent_transfer_split_enabled=latent_transfer_split_enabled,
        )
        for seed in seeds
    ]
    latent_results = [
        transfer_growth_for_seed(
            seed,
            train_scenario=TRAIN_SCENARIO,
            transfer_scenario=TRANSFER_SCENARIO,
            morphogenesis_config=morphogenesis_config,
            latent_context=True,
            source_sequence_context_enabled=source_sequence_context_enabled,
            latent_transfer_split_enabled=latent_transfer_split_enabled,
        )
        for seed in seeds
    ]
    switched_results = [
        mode_switched_transfer_for_seed(
            seed,
            morphogenesis_config=morphogenesis_config,
            source_sequence_context_enabled=source_sequence_context_enabled,
            latent_transfer_split_enabled=latent_transfer_split_enabled,
        )
        for seed in seeds
    ]

    result = {
        "seeds": list(seeds),
        "train_scenario": TRAIN_SCENARIO,
        "transfer_scenario": TRANSFER_SCENARIO,
        "source_sequence_context_enabled": source_sequence_context_enabled,
        "latent_transfer_split_enabled": latent_transfer_split_enabled,
        "all_visible": {
            "results": visible_results,
            "aggregate": aggregate_transfer_growth_results(visible_results),
        },
        "all_latent": {
            "results": latent_results,
            "aggregate": aggregate_transfer_growth_results(latent_results),
        },
        "visible_train_latent_transfer": {
            "results": switched_results,
            "aggregate": aggregate_transfer_growth_results(switched_results),
        },
        "comparison": _policy_comparison(visible_results, latent_results, switched_results),
    }
    if output_path is not None:
        manifest = build_run_manifest(
            harness="morphogenesis_large_mode_switched",
            seeds=seeds,
            scenarios=(TRAIN_SCENARIO, TRANSFER_SCENARIO),
            metadata={
                "train_scenario": TRAIN_SCENARIO,
                "transfer_scenario": TRANSFER_SCENARIO,
                "source_sequence_context_enabled": source_sequence_context_enabled,
                "latent_transfer_split_enabled": latent_transfer_split_enabled,
            },
            result=result,
        )
        write_run_manifest(output_path, manifest)
    return result


def main() -> None:
    print(json.dumps(evaluate_morphogenesis_large_mode_switched(), indent=2))


if __name__ == "__main__":
    main()
