from __future__ import annotations

import json
from statistics import mean

from compare_latent_context import (
    DEFAULT_SEEDS,
    TRAIN_SCENARIO,
    TRANSFER_SCENARIO,
    evaluate_latent_context,
)


def _mean(values: list[float]) -> float:
    return round(mean(values), 4)


def _overall(summary: dict[str, object], field: str) -> float:
    diagnostics = summary.get("task_diagnostics", {})
    overall = diagnostics.get("overall", {})
    return float(overall.get(field, 0.0))


def _aggregate_failure_counts(results: list[dict[str, object]], *, summary_key: str) -> dict[str, float]:
    fields = (
        "identity_fallbacks",
        "wrong_transform_family",
        "route_wrong_transform_potentially_right",
        "route_right_transform_wrong",
        "transform_unstable_across_inferred_context_boundary",
        "delayed_correction",
    )
    return {
        f"avg_{field}": _mean([_overall(item[summary_key]["summary"], field) for item in results])
        for field in fields
    }


def run_ablation_suite(*, seeds: tuple[int, ...] = DEFAULT_SEEDS) -> dict[str, object]:
    configs = {
        "latent_no_source_sequence": evaluate_latent_context(
            seeds=seeds,
            source_sequence_context_enabled=False,
        ),
        "latent_with_source_sequence": evaluate_latent_context(
            seeds=seeds,
            source_sequence_context_enabled=True,
        ),
    }

    output: dict[str, object] = {"seeds": list(seeds), "ablations": {}}
    for name, result in configs.items():
        task_a_results = result["scenarios"][TRAIN_SCENARIO]["results"]
        task_b_results = result["scenarios"][TRANSFER_SCENARIO]["results"]
        transfer_results = result["transfer"]["results"]
        output["ablations"][name] = {
            "task_a": {
                **result["scenarios"][TRAIN_SCENARIO]["aggregate"],
                **_aggregate_failure_counts(task_a_results, summary_key="latent"),
            },
            "task_b": {
                **result["scenarios"][TRANSFER_SCENARIO]["aggregate"],
                **_aggregate_failure_counts(task_b_results, summary_key="latent"),
            },
            "transfer": {
                **result["transfer"]["aggregate"],
                **_aggregate_failure_counts(
                    [
                        {
                            "latent": {"summary": item["latent_transfer"]},
                        }
                        for item in transfer_results
                    ],
                    summary_key="latent",
                ),
            },
        }
    return output


def main() -> None:
    print(json.dumps(run_ablation_suite(), indent=2))


if __name__ == "__main__":
    main()
