from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path

from scripts.compare_cold_warm import ROOT, build_system, run_workload
from scripts.compare_task_transfer import transfer_metrics
from scripts.experiment_manifest import build_run_manifest, write_run_manifest


def _set_recognition_bias(system, *, enabled: bool) -> None:
    for agent in system.agents.values():
        selector = agent.engine.selector
        selector.recognition_route_bonus = 0.12 if enabled else 0.0
        selector.recognition_route_penalty = 0.10 if enabled else 0.0
        selector.recognition_transform_bonus = 0.10 if enabled else 0.0


def _compact_transfer_metrics(metrics: dict[str, object]) -> dict[str, object]:
    anticipation = dict(metrics.get("anticipation", {}))
    return {
        "packets_evaluated": int(metrics.get("packets_evaluated", 0)),
        "best_rolling_exact_rate": float(metrics.get("best_rolling_exact_rate", 0.0)),
        "best_rolling_bit_accuracy": float(metrics.get("best_rolling_bit_accuracy", 0.0)),
        "first_exact_match_example": metrics.get("first_exact_match_example"),
        "first_expected_transform_example": metrics.get("first_expected_transform_example"),
        "first_sustained_expected_transform_example": metrics.get(
            "first_sustained_expected_transform_example"
        ),
        "early_window_exact_rate": float(metrics.get("early_window_exact_rate", 0.0)),
        "early_window_bit_accuracy": float(metrics.get("early_window_bit_accuracy", 0.0)),
        "early_window_wrong_transform_family": int(
            metrics.get("early_window_wrong_transform_family", 0)
        ),
        "early_window_wrong_transform_family_rate": float(
            metrics.get("early_window_wrong_transform_family_rate", 0.0)
        ),
        "anticipation": {
            "recognized_route_entry_count": int(
                anticipation.get("recognized_route_entry_count", 0)
            ),
            "recognized_source_route_entry_count": int(
                anticipation.get("recognized_source_route_entry_count", 0)
            ),
            "recognized_source_transform_entry_count": int(
                anticipation.get("recognized_source_transform_entry_count", 0)
            ),
            "predicted_route_entry_count": int(
                anticipation.get("predicted_route_entry_count", 0)
            ),
            "first_recognized_route_cycle": anticipation.get(
                "first_recognized_route_cycle"
            ),
            "first_recognized_source_transform_cycle": anticipation.get(
                "first_recognized_source_transform_cycle"
            ),
            "first_predicted_route_cycle": anticipation.get(
                "first_predicted_route_cycle"
            ),
        },
    }


def _run_transfer_variant(
    *,
    seed: int,
    train_scenario: str,
    transfer_scenario: str,
    recognition_bias_enabled: bool,
) -> dict[str, object]:
    base_dir = ROOT / "tests_tmp" / f"transfer_adapt_probe_{uuid.uuid4().hex}"
    carryover_dir = base_dir / "carryover"
    carryover_dir.mkdir(parents=True, exist_ok=True)
    try:
        training = build_system(seed, train_scenario)
        run_workload(training, train_scenario)
        training.save_memory_carryover(carryover_dir)

        system = build_system(seed, transfer_scenario)
        _set_recognition_bias(system, enabled=recognition_bias_enabled)
        system.load_memory_carryover(carryover_dir)
        summary = run_workload(system, transfer_scenario)
        metrics = transfer_metrics(system)
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)

    return {
        "recognition_bias_enabled": bool(recognition_bias_enabled),
        "summary": {
            "exact_matches": int(summary["exact_matches"]),
            "mean_bit_accuracy": round(float(summary["mean_bit_accuracy"]), 4),
            "mean_route_cost": round(float(summary["mean_route_cost"]), 5),
        },
        "transfer_metrics": _compact_transfer_metrics(metrics),
    }


def evaluate_transfer_adaptation_recognition(
    *,
    train_scenario: str,
    transfer_scenario: str,
    seeds: tuple[int, ...] = (13, 23, 37),
    output_path: Path | None = None,
) -> dict[str, object]:
    results = []
    for seed in seeds:
        enabled = _run_transfer_variant(
            seed=seed,
            train_scenario=train_scenario,
            transfer_scenario=transfer_scenario,
            recognition_bias_enabled=True,
        )
        disabled = _run_transfer_variant(
            seed=seed,
            train_scenario=train_scenario,
            transfer_scenario=transfer_scenario,
            recognition_bias_enabled=False,
        )
        results.append(
            {
                "seed": int(seed),
                "recognition_bias_enabled": enabled,
                "recognition_bias_disabled": disabled,
                "delta": {
                    "exact_matches": (
                        enabled["summary"]["exact_matches"]
                        - disabled["summary"]["exact_matches"]
                    ),
                    "mean_bit_accuracy": round(
                        enabled["summary"]["mean_bit_accuracy"]
                        - disabled["summary"]["mean_bit_accuracy"],
                        4,
                    ),
                    "early_window_exact_rate": round(
                        enabled["transfer_metrics"]["early_window_exact_rate"]
                        - disabled["transfer_metrics"]["early_window_exact_rate"],
                        4,
                    ),
                    "early_window_wrong_transform_family_rate": round(
                        enabled["transfer_metrics"][
                            "early_window_wrong_transform_family_rate"
                        ]
                        - disabled["transfer_metrics"][
                            "early_window_wrong_transform_family_rate"
                        ],
                        4,
                    ),
                    "first_expected_transform_example": (
                        None
                        if enabled["transfer_metrics"][
                            "first_expected_transform_example"
                        ]
                        is None
                        or disabled["transfer_metrics"][
                            "first_expected_transform_example"
                        ]
                        is None
                        else int(
                            enabled["transfer_metrics"][
                                "first_expected_transform_example"
                            ]
                        )
                        - int(
                            disabled["transfer_metrics"][
                                "first_expected_transform_example"
                            ]
                        )
                    ),
                },
            }
        )

    result = {
        "train_scenario": train_scenario,
        "transfer_scenario": transfer_scenario,
        "seeds": [int(seed) for seed in seeds],
        "results": results,
    }
    if output_path is not None:
        manifest = build_run_manifest(
            harness="transfer_adaptation_recognition_probe",
            seeds=tuple(int(seed) for seed in seeds),
            scenarios=(f"{train_scenario}->{transfer_scenario}",),
            metadata={},
            result=result,
        )
        write_run_manifest(output_path, manifest)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare transfer adaptation metrics with recognition bias on vs off."
    )
    parser.add_argument("--train-scenario", default="cvt1_task_a_stage1")
    parser.add_argument("--transfer-scenario", default="cvt1_task_b_stage1")
    parser.add_argument("--seeds", nargs="+", type=int, default=[13, 23, 37])
    parser.add_argument("--output", type=str)
    args = parser.parse_args()

    result = evaluate_transfer_adaptation_recognition(
        train_scenario=str(args.train_scenario),
        transfer_scenario=str(args.transfer_scenario),
        seeds=tuple(int(seed) for seed in args.seeds),
        output_path=Path(args.output) if args.output else None,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
