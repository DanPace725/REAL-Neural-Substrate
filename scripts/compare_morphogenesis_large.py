"""Morphogenesis evaluation on the 10-node large topology (36-packet stage-2 sessions).

Mirrors compare_morphogenesis.py but targets the *_large scenario set where:
  - 10-node topology gives new nodes more routing paths to specialize into
  - 36-packet sessions provide longer ATP surplus windows and richer feedback
  - Aâ†’B transfer uses the large topology for both training and transfer

Uses the same benchmark_morphogenesis_config() as compare_morphogenesis.py.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from statistics import mean

from scripts.compare_morphogenesis import (
    DEFAULT_SEEDS,
    aggregate_growth_results,
    aggregate_transfer_growth_results,
    benchmark_morphogenesis_config,
    build_growth_system,
    compare_growth_for_seed,
    growth_counts_as_earned,
    growth_counts_as_win,
    transfer_growth_for_seed,
    _clone_config,
)
from scripts.compare_cold_warm import SCENARIOS
from scripts.experiment_manifest import build_run_manifest, write_run_manifest
from phase8 import MorphogenesisConfig

WORKLOAD_SCENARIOS = (
    "cvt1_task_a_large",
    "cvt1_task_b_large",
    "cvt1_task_c_large",
)
TRAIN_SCENARIO = "cvt1_task_a_large"
TRANSFER_SCENARIO = "cvt1_task_b_large"


def evaluate_morphogenesis_large(
    *,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    morphogenesis_config: MorphogenesisConfig | None = None,
    latent_context: bool = False,
    source_sequence_context_enabled: bool = True,
    latent_transfer_split_enabled: bool = True,
    output_path: Path | None = None,
) -> dict[str, object]:
    scenario_results = {}
    for scenario_name in WORKLOAD_SCENARIOS:
        results = [
            compare_growth_for_seed(
                seed,
                scenario_name,
                morphogenesis_config=morphogenesis_config,
                latent_context=latent_context,
                source_sequence_context_enabled=source_sequence_context_enabled,
                latent_transfer_split_enabled=latent_transfer_split_enabled,
            )
            for seed in seeds
        ]
        scenario_results[scenario_name] = {
            "description": SCENARIOS[scenario_name].description,
            "results": results,
            "aggregate": aggregate_growth_results(results),
        }

    transfer_results = [
        transfer_growth_for_seed(
            seed,
            train_scenario=TRAIN_SCENARIO,
            transfer_scenario=TRANSFER_SCENARIO,
            morphogenesis_config=morphogenesis_config,
            latent_context=latent_context,
            source_sequence_context_enabled=source_sequence_context_enabled,
            latent_transfer_split_enabled=latent_transfer_split_enabled,
        )
        for seed in seeds
    ]

    cloned_config = _clone_config(morphogenesis_config)
    result = {
        "latent_context": latent_context,
        "source_sequence_context_enabled": source_sequence_context_enabled,
        "latent_transfer_split_enabled": latent_transfer_split_enabled,
        "seeds": list(seeds),
        "topology": "cvt1_large (10 nodes, 5-hop paths)",
        "signal_set": "stage2 (36 packets)",
        "morphogenesis_config": asdict(cloned_config),
        "scenarios": scenario_results,
        "transfer": {
            "train_scenario": TRAIN_SCENARIO,
            "transfer_scenario": TRANSFER_SCENARIO,
            "results": transfer_results,
            "aggregate": aggregate_transfer_growth_results(transfer_results),
        },
    }
    if output_path is not None:
        manifest = build_run_manifest(
            harness="morphogenesis_large",
            seeds=seeds,
            scenarios=WORKLOAD_SCENARIOS,
            metadata={
                "train_scenario": TRAIN_SCENARIO,
                "transfer_scenario": TRANSFER_SCENARIO,
                "morphogenesis_config": result["morphogenesis_config"],
                "latent_context": latent_context,
                "source_sequence_context_enabled": source_sequence_context_enabled,
                "latent_transfer_split_enabled": latent_transfer_split_enabled,
            },
            result=result,
        )
        write_run_manifest(output_path, manifest)
    return result


def main() -> None:
    print(json.dumps(evaluate_morphogenesis_large(), indent=2))


if __name__ == "__main__":
    main()

