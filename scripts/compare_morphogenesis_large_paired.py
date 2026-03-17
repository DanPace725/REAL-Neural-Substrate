"""Paired visible-vs-latent morphogenesis evaluation on the 10-node large topology."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.compare_morphogenesis_large import (
    DEFAULT_SEEDS,
    TRAIN_SCENARIO,
    TRANSFER_SCENARIO,
    WORKLOAD_SCENARIOS,
    evaluate_morphogenesis_large,
)
from scripts.experiment_manifest import build_run_manifest, write_run_manifest
from phase8 import MorphogenesisConfig


def _comparison_block(
    visible: dict[str, object],
    latent: dict[str, object],
) -> dict[str, object]:
    scenario_comparison = {}
    for scenario_name in WORKLOAD_SCENARIOS:
        visible_aggregate = visible["scenarios"][scenario_name]["aggregate"]
        latent_aggregate = latent["scenarios"][scenario_name]["aggregate"]
        scenario_comparison[scenario_name] = {
            "visible_avg_delta_exact_matches": visible_aggregate["avg_delta_exact_matches"],
            "latent_avg_delta_exact_matches": latent_aggregate["avg_delta_exact_matches"],
            "latent_minus_visible_delta_exact_matches": round(
                latent_aggregate["avg_delta_exact_matches"] - visible_aggregate["avg_delta_exact_matches"],
                4,
            ),
            "visible_avg_delta_bit_accuracy": visible_aggregate["avg_delta_bit_accuracy"],
            "latent_avg_delta_bit_accuracy": latent_aggregate["avg_delta_bit_accuracy"],
            "latent_minus_visible_delta_bit_accuracy": round(
                latent_aggregate["avg_delta_bit_accuracy"] - visible_aggregate["avg_delta_bit_accuracy"],
                4,
            ),
            "visible_growth_win_rate": visible_aggregate["growth_win_rate"],
            "latent_growth_win_rate": latent_aggregate["growth_win_rate"],
            "latent_minus_visible_growth_win_rate": round(
                latent_aggregate["growth_win_rate"] - visible_aggregate["growth_win_rate"],
                4,
            ),
        }

    visible_transfer = visible["transfer"]["aggregate"]
    latent_transfer = latent["transfer"]["aggregate"]
    transfer_comparison = {
        "visible_avg_delta_transfer_exact_matches": visible_transfer["avg_delta_transfer_exact_matches"],
        "latent_avg_delta_transfer_exact_matches": latent_transfer["avg_delta_transfer_exact_matches"],
        "latent_minus_visible_delta_transfer_exact_matches": round(
            latent_transfer["avg_delta_transfer_exact_matches"]
            - visible_transfer["avg_delta_transfer_exact_matches"],
            4,
        ),
        "visible_avg_delta_transfer_bit_accuracy": visible_transfer["avg_delta_transfer_bit_accuracy"],
        "latent_avg_delta_transfer_bit_accuracy": latent_transfer["avg_delta_transfer_bit_accuracy"],
        "latent_minus_visible_delta_transfer_bit_accuracy": round(
            latent_transfer["avg_delta_transfer_bit_accuracy"]
            - visible_transfer["avg_delta_transfer_bit_accuracy"],
            4,
        ),
        "visible_growth_transfer_win_rate": visible_transfer["growth_transfer_win_rate"],
        "latent_growth_transfer_win_rate": latent_transfer["growth_transfer_win_rate"],
        "latent_minus_visible_growth_transfer_win_rate": round(
            latent_transfer["growth_transfer_win_rate"]
            - visible_transfer["growth_transfer_win_rate"],
            4,
        ),
    }

    return {
        "scenarios": scenario_comparison,
        "transfer": transfer_comparison,
    }


def evaluate_morphogenesis_large_paired(
    *,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    morphogenesis_config: MorphogenesisConfig | None = None,
    source_sequence_context_enabled: bool = True,
    latent_transfer_split_enabled: bool = True,
    output_path: Path | None = None,
) -> dict[str, object]:
    visible = evaluate_morphogenesis_large(
        seeds=seeds,
        morphogenesis_config=morphogenesis_config,
        latent_context=False,
        source_sequence_context_enabled=source_sequence_context_enabled,
        latent_transfer_split_enabled=latent_transfer_split_enabled,
    )
    latent = evaluate_morphogenesis_large(
        seeds=seeds,
        morphogenesis_config=morphogenesis_config,
        latent_context=True,
        source_sequence_context_enabled=source_sequence_context_enabled,
        latent_transfer_split_enabled=latent_transfer_split_enabled,
    )
    result = {
        "seeds": list(seeds),
        "topology": visible["topology"],
        "signal_set": visible["signal_set"],
        "train_scenario": TRAIN_SCENARIO,
        "transfer_scenario": TRANSFER_SCENARIO,
        "source_sequence_context_enabled": source_sequence_context_enabled,
        "latent_transfer_split_enabled": latent_transfer_split_enabled,
        "visible": visible,
        "latent": latent,
        "comparison": _comparison_block(visible, latent),
    }
    if output_path is not None:
        manifest = build_run_manifest(
            harness="morphogenesis_large_paired",
            seeds=seeds,
            scenarios=WORKLOAD_SCENARIOS,
            metadata={
                "train_scenario": TRAIN_SCENARIO,
                "transfer_scenario": TRANSFER_SCENARIO,
                "source_sequence_context_enabled": source_sequence_context_enabled,
                "latent_transfer_split_enabled": latent_transfer_split_enabled,
                "morphogenesis_config": visible["morphogenesis_config"],
            },
            result=result,
        )
        write_run_manifest(output_path, manifest)
    return result


def main() -> None:
    print(json.dumps(evaluate_morphogenesis_large_paired(), indent=2))


if __name__ == "__main__":
    main()

