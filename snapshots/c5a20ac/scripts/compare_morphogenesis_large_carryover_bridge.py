"""Carryover-bridge diagnostics for large-topology morphogenesis transfer.

Compares full vs substrate-only carryover across three transfer policies:
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
    _run_growth_workload,
)
from scripts.compare_morphogenesis_large import TRAIN_SCENARIO, TRANSFER_SCENARIO
from scripts.experiment_manifest import build_run_manifest, write_run_manifest
from phase8 import MorphogenesisConfig


def _save_carryover(system, root_dir: Path, carryover_mode: str) -> None:
    if carryover_mode == "full":
        system.save_memory_carryover(root_dir)
        return
    if carryover_mode == "substrate":
        system.save_substrate_carryover(root_dir)
        return
    raise ValueError(f"Unsupported carryover mode: {carryover_mode}")


def _load_carryover(system, root_dir: Path, carryover_mode: str) -> bool:
    if carryover_mode == "full":
        return system.load_memory_carryover(root_dir)
    if carryover_mode == "substrate":
        return system.load_substrate_carryover(root_dir)
    raise ValueError(f"Unsupported carryover mode: {carryover_mode}")


def bridge_transfer_for_seed(
    seed: int,
    *,
    train_mode: str,
    transfer_mode: str,
    carryover_mode: str,
    morphogenesis_config: MorphogenesisConfig | None = None,
    source_sequence_context_enabled: bool = True,
    latent_transfer_split_enabled: bool = True,
) -> dict[str, object]:
    train_latent = train_mode == "latent"
    transfer_latent = transfer_mode == "latent"

    fixed_training = build_system(
        seed,
        TRAIN_SCENARIO,
        source_sequence_context_enabled=source_sequence_context_enabled,
        latent_transfer_split_enabled=latent_transfer_split_enabled,
    )
    fixed_training_summary = _run_growth_workload(
        fixed_training,
        TRAIN_SCENARIO,
        latent_context=train_latent,
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
        latent_context=train_latent,
    )

    base_dir = ROOT / "tests_tmp" / f"carryover_bridge_{uuid.uuid4().hex}"
    fixed_dir = base_dir / "fixed"
    growth_dir = base_dir / "growth"
    fixed_dir.mkdir(parents=True, exist_ok=True)
    growth_dir.mkdir(parents=True, exist_ok=True)
    try:
        _save_carryover(fixed_training, fixed_dir, carryover_mode)
        _save_carryover(growth_training, growth_dir, carryover_mode)

        fixed_transfer = build_system(
            seed,
            TRANSFER_SCENARIO,
            source_sequence_context_enabled=source_sequence_context_enabled,
            latent_transfer_split_enabled=latent_transfer_split_enabled,
        )
        _load_carryover(fixed_transfer, fixed_dir, carryover_mode)
        fixed_transfer_summary = _run_growth_workload(
            fixed_transfer,
            TRANSFER_SCENARIO,
            latent_context=transfer_latent,
        )

        growth_transfer = build_growth_system(
            seed,
            TRANSFER_SCENARIO,
            morphogenesis_config=morphogenesis_config,
            source_sequence_context_enabled=source_sequence_context_enabled,
            latent_transfer_split_enabled=latent_transfer_split_enabled,
        )
        _load_carryover(growth_transfer, growth_dir, carryover_mode)
        growth_transfer_summary = _run_growth_workload(
            growth_transfer,
            TRANSFER_SCENARIO,
            latent_context=transfer_latent,
        )
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)

    return {
        "seed": seed,
        "train_mode": train_mode,
        "transfer_mode": transfer_mode,
        "carryover_mode": carryover_mode,
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


def _aggregate_policy(
    *,
    seeds: tuple[int, ...],
    train_mode: str,
    transfer_mode: str,
    carryover_mode: str,
    morphogenesis_config: MorphogenesisConfig | None = None,
    source_sequence_context_enabled: bool = True,
    latent_transfer_split_enabled: bool = True,
) -> dict[str, object]:
    results = [
        bridge_transfer_for_seed(
            seed,
            train_mode=train_mode,
            transfer_mode=transfer_mode,
            carryover_mode=carryover_mode,
            morphogenesis_config=morphogenesis_config,
            source_sequence_context_enabled=source_sequence_context_enabled,
            latent_transfer_split_enabled=latent_transfer_split_enabled,
        )
        for seed in seeds
    ]
    return {
        "train_mode": train_mode,
        "transfer_mode": transfer_mode,
        "carryover_mode": carryover_mode,
        "results": results,
        "aggregate": aggregate_transfer_growth_results(results),
    }


def _comparison_block(policies: dict[str, dict[str, object]]) -> dict[str, object]:
    def agg(policy: str, carryover_mode: str) -> dict[str, object]:
        return policies[policy][carryover_mode]["aggregate"]

    return {
        "visible_full_minus_substrate": {
            "delta_transfer_exact_matches": round(
                agg("all_visible", "full")["avg_delta_transfer_exact_matches"]
                - agg("all_visible", "substrate")["avg_delta_transfer_exact_matches"],
                4,
            ),
            "delta_transfer_bit_accuracy": round(
                agg("all_visible", "full")["avg_delta_transfer_bit_accuracy"]
                - agg("all_visible", "substrate")["avg_delta_transfer_bit_accuracy"],
                4,
            ),
        },
        "latent_full_minus_substrate": {
            "delta_transfer_exact_matches": round(
                agg("all_latent", "full")["avg_delta_transfer_exact_matches"]
                - agg("all_latent", "substrate")["avg_delta_transfer_exact_matches"],
                4,
            ),
            "delta_transfer_bit_accuracy": round(
                agg("all_latent", "full")["avg_delta_transfer_bit_accuracy"]
                - agg("all_latent", "substrate")["avg_delta_transfer_bit_accuracy"],
                4,
            ),
        },
        "switched_full_minus_substrate": {
            "delta_transfer_exact_matches": round(
                agg("visible_train_latent_transfer", "full")["avg_delta_transfer_exact_matches"]
                - agg("visible_train_latent_transfer", "substrate")["avg_delta_transfer_exact_matches"],
                4,
            ),
            "delta_transfer_bit_accuracy": round(
                agg("visible_train_latent_transfer", "full")["avg_delta_transfer_bit_accuracy"]
                - agg("visible_train_latent_transfer", "substrate")["avg_delta_transfer_bit_accuracy"],
                4,
            ),
        },
        "switched_substrate_minus_latent_substrate": {
            "delta_transfer_exact_matches": round(
                agg("visible_train_latent_transfer", "substrate")["avg_delta_transfer_exact_matches"]
                - agg("all_latent", "substrate")["avg_delta_transfer_exact_matches"],
                4,
            ),
            "delta_transfer_bit_accuracy": round(
                agg("visible_train_latent_transfer", "substrate")["avg_delta_transfer_bit_accuracy"]
                - agg("all_latent", "substrate")["avg_delta_transfer_bit_accuracy"],
                4,
            ),
        },
        "switched_substrate_minus_visible_substrate": {
            "delta_transfer_exact_matches": round(
                agg("visible_train_latent_transfer", "substrate")["avg_delta_transfer_exact_matches"]
                - agg("all_visible", "substrate")["avg_delta_transfer_exact_matches"],
                4,
            ),
            "delta_transfer_bit_accuracy": round(
                agg("visible_train_latent_transfer", "substrate")["avg_delta_transfer_bit_accuracy"]
                - agg("all_visible", "substrate")["avg_delta_transfer_bit_accuracy"],
                4,
            ),
        },
    }


def evaluate_morphogenesis_large_carryover_bridge(
    *,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    morphogenesis_config: MorphogenesisConfig | None = None,
    source_sequence_context_enabled: bool = True,
    latent_transfer_split_enabled: bool = True,
    output_path: Path | None = None,
) -> dict[str, object]:
    policy_specs = {
        "all_visible": ("visible", "visible"),
        "all_latent": ("latent", "latent"),
        "visible_train_latent_transfer": ("visible", "latent"),
    }
    policies: dict[str, dict[str, object]] = {}
    for policy_name, (train_mode, transfer_mode) in policy_specs.items():
        policies[policy_name] = {}
        for carryover_mode in ("full", "substrate"):
            policies[policy_name][carryover_mode] = _aggregate_policy(
                seeds=seeds,
                train_mode=train_mode,
                transfer_mode=transfer_mode,
                carryover_mode=carryover_mode,
                morphogenesis_config=morphogenesis_config,
                source_sequence_context_enabled=source_sequence_context_enabled,
                latent_transfer_split_enabled=latent_transfer_split_enabled,
            )

    result = {
        "seeds": list(seeds),
        "train_scenario": TRAIN_SCENARIO,
        "transfer_scenario": TRANSFER_SCENARIO,
        "source_sequence_context_enabled": source_sequence_context_enabled,
        "latent_transfer_split_enabled": latent_transfer_split_enabled,
        "policies": policies,
        "comparison": _comparison_block(policies),
    }
    if output_path is not None:
        manifest = build_run_manifest(
            harness="morphogenesis_large_carryover_bridge",
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
    print(json.dumps(evaluate_morphogenesis_large_carryover_bridge(), indent=2))


if __name__ == "__main__":
    main()
