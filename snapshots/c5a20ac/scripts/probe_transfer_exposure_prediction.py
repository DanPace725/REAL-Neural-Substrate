from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path
from typing import Dict, List, Sequence

from scripts.benchmark_anticipation_metrics import anticipation_metrics
from scripts.ceiling_benchmark_metrics import criterion_metrics_from_exact_and_accuracy
from scripts.compare_cold_warm import ROOT, SCENARIOS, build_system, run_workload
from scripts.compare_task_transfer import transfer_metrics
from scripts.repeated_signal_scenarios import (
    expected_examples_for_signal_scenario,
    repeat_signal_scenario,
    signal_pass_span,
)

DEFAULT_TRAIN_SCENARIO = "cvt1_task_a_stage1"
DEFAULT_TRANSFER_SCENARIO = "cvt1_task_b_stage1"
DEFAULT_SEEDS = (13,)
DEFAULT_REPEAT_COUNTS = (1, 2, 3)


def _ordered_scored_packets(system) -> List[object]:
    return sorted(
        [
            packet
            for packet in system.environment.delivered_packets
            if packet.bit_match_ratio is not None
        ],
        key=lambda packet: (
            packet.delivered_cycle
            if packet.delivered_cycle is not None
            else system.global_cycle,
            packet.created_cycle,
            packet.packet_id,
        ),
    )


def _load_transfer_carryover(
    system,
    *,
    carryover_mode: str,
    full_dir: Path,
    substrate_dir: Path,
) -> None:
    if carryover_mode == "full":
        system.load_memory_carryover(full_dir)
        return
    if carryover_mode == "substrate":
        system.load_substrate_carryover(substrate_dir)


def _pass_metrics(
    exact_results: Sequence[bool],
    bit_accuracies: Sequence[float],
    *,
    base_expected_examples: int,
    repeat_count: int,
) -> List[dict[str, object]]:
    passes: List[dict[str, object]] = []
    for pass_index in range(max(int(repeat_count), 1)):
        start = pass_index * base_expected_examples
        end = start + base_expected_examples
        exact_slice = list(exact_results[start:end])
        accuracy_slice = list(bit_accuracies[start:end])
        metrics = criterion_metrics_from_exact_and_accuracy(exact_slice, accuracy_slice)
        passes.append(
            {
                "pass_index": pass_index + 1,
                "exact_matches": sum(exact_slice),
                "exact_match_rate": round(
                    sum(exact_slice) / max(base_expected_examples, 1),
                    4,
                ),
                "mean_bit_accuracy": round(
                    sum(accuracy_slice) / max(base_expected_examples, 1),
                    4,
                ),
                "criterion_reached": bool(metrics["criterion_reached"]),
                "examples_to_criterion": metrics["examples_to_criterion"],
                "best_rolling_exact_rate": metrics["best_rolling_exact_rate"],
                "best_rolling_bit_accuracy": metrics["best_rolling_bit_accuracy"],
            }
        )
    return passes


def _run_transfer_exposure_case(
    *,
    seed: int,
    transfer_scenario: str,
    repeat_count: int,
    carryover_mode: str,
    full_dir: Path,
    substrate_dir: Path,
) -> Dict[str, object]:
    base_scenario = SCENARIOS[transfer_scenario]
    scenario = repeat_signal_scenario(base_scenario, repeat_count)
    system = build_system(seed, transfer_scenario)
    _load_transfer_carryover(
        system,
        carryover_mode=carryover_mode,
        full_dir=full_dir,
        substrate_dir=substrate_dir,
    )
    result = system.run_workload(
        cycles=scenario.cycles,
        initial_packets=scenario.initial_packets,
        packet_schedule=scenario.packet_schedule,
        initial_signal_specs=scenario.initial_signal_specs,
        signal_schedule_specs=scenario.signal_schedule_specs,
    )
    summary = result["summary"]
    packets = _ordered_scored_packets(system)
    expected_examples = expected_examples_for_signal_scenario(base_scenario) * max(
        int(repeat_count),
        1,
    )
    exact_results = [bool(packet.matched_target) for packet in packets]
    bit_accuracies = [float(packet.bit_match_ratio or 0.0) for packet in packets]
    if len(exact_results) < expected_examples:
        missing = expected_examples - len(exact_results)
        exact_results.extend([False] * missing)
        bit_accuracies.extend([0.0] * missing)
    per_pass = _pass_metrics(
        exact_results,
        bit_accuracies,
        base_expected_examples=expected_examples_for_signal_scenario(base_scenario),
        repeat_count=repeat_count,
    )
    pass_span = signal_pass_span(base_scenario)
    for pass_index, pass_metrics in enumerate(per_pass):
        pass_metrics["anticipation"] = anticipation_metrics(
            system,
            cycle_start=1 + pass_index * pass_span,
            cycle_end=(pass_index + 1) * pass_span,
        )
    return {
        "seed": seed,
        "repeat_count": int(repeat_count),
        "carryover_mode": carryover_mode,
        "base_cycles": int(base_scenario.cycles),
        "cycles": int(scenario.cycles),
        "expected_examples": expected_examples,
        "time_to_first_feedback": summary.get("time_to_first_feedback"),
        "exact_matches": sum(exact_results),
        "exact_match_rate": round(sum(exact_results) / max(expected_examples, 1), 4),
        "mean_bit_accuracy": round(
            sum(bit_accuracies) / max(expected_examples, 1),
            4,
        ),
        "transfer_metrics": transfer_metrics(system),
        "anticipation": anticipation_metrics(system),
        "per_pass": per_pass,
    }


def evaluate_transfer_exposure_prediction(
    *,
    train_scenario: str = DEFAULT_TRAIN_SCENARIO,
    transfer_scenario: str = DEFAULT_TRANSFER_SCENARIO,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    repeat_counts: Sequence[int] = DEFAULT_REPEAT_COUNTS,
    carryover_mode: str = "full",
) -> dict[str, object]:
    results: List[dict[str, object]] = []
    for seed in seeds:
        training = build_system(seed, train_scenario)
        training_summary = run_workload(training, train_scenario)
        base_dir = ROOT / "tests_tmp" / f"transfer_exposure_{uuid.uuid4().hex}"
        full_dir = base_dir / "full"
        substrate_dir = base_dir / "substrate"
        full_dir.mkdir(parents=True, exist_ok=True)
        substrate_dir.mkdir(parents=True, exist_ok=True)
        try:
            training.save_memory_carryover(full_dir)
            training.save_substrate_carryover(substrate_dir)
            runs = [
                _run_transfer_exposure_case(
                    seed=seed,
                    transfer_scenario=transfer_scenario,
                    repeat_count=repeat_count,
                    carryover_mode=carryover_mode,
                    full_dir=full_dir,
                    substrate_dir=substrate_dir,
                )
                for repeat_count in repeat_counts
            ]
        finally:
            shutil.rmtree(base_dir, ignore_errors=True)
        baseline = next(
            (run for run in runs if int(run["repeat_count"]) == 1),
            runs[0],
        )
        baseline_prediction_confidence = baseline["anticipation"].get(
            "mean_source_prediction_confidence"
        )
        for run in runs:
            run["delta_exact_match_rate"] = round(
                float(run["exact_match_rate"]) - float(baseline["exact_match_rate"]),
                4,
            )
            run["delta_best_rolling_exact_rate"] = round(
                float(run["transfer_metrics"]["best_rolling_exact_rate"])
                - float(baseline["transfer_metrics"]["best_rolling_exact_rate"]),
                4,
            )
            run["delta_final_pass_exact_match_rate"] = round(
                float(run["per_pass"][-1]["exact_match_rate"])
                - float(baseline["per_pass"][-1]["exact_match_rate"]),
                4,
            )
            prediction_confidence = run["anticipation"].get(
                "mean_source_prediction_confidence"
            )
            if (
                baseline_prediction_confidence is not None
                and prediction_confidence is not None
            ):
                run["delta_mean_source_prediction_confidence"] = round(
                    float(prediction_confidence) - float(baseline_prediction_confidence),
                    4,
                )
            else:
                run["delta_mean_source_prediction_confidence"] = None
        results.append(
            {
                "seed": seed,
                "train_scenario": train_scenario,
                "transfer_scenario": transfer_scenario,
                "carryover_mode": carryover_mode,
                "training_summary": training_summary,
                "runs": runs,
            }
        )
    aggregate = {
        "case_count": len(results),
        "improved_overall_exact_cases": sum(
            1
            for case in results
            for run in case["runs"]
            if int(run["repeat_count"]) > 1 and float(run["delta_exact_match_rate"]) > 0.0
        ),
        "improved_final_pass_cases": sum(
            1
            for case in results
            for run in case["runs"]
            if int(run["repeat_count"]) > 1
            and float(run["delta_final_pass_exact_match_rate"]) > 0.0
        ),
        "increased_prediction_confidence_cases": sum(
            1
            for case in results
            for run in case["runs"]
            if int(run["repeat_count"]) > 1
            and run["delta_mean_source_prediction_confidence"] is not None
            and float(run["delta_mean_source_prediction_confidence"]) > 0.0
        ),
    }
    return {
        "train_scenario": train_scenario,
        "transfer_scenario": transfer_scenario,
        "carryover_mode": carryover_mode,
        "seeds": [int(seed) for seed in seeds],
        "repeat_counts": [int(value) for value in repeat_counts],
        "results": results,
        "aggregate": aggregate,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe how repeated transfer exposure changes prediction and adaptation.",
    )
    parser.add_argument(
        "--train-scenario",
        default=DEFAULT_TRAIN_SCENARIO,
    )
    parser.add_argument(
        "--transfer-scenario",
        default=DEFAULT_TRANSFER_SCENARIO,
    )
    parser.add_argument(
        "--seeds",
        nargs="+",
        type=int,
        default=list(DEFAULT_SEEDS),
    )
    parser.add_argument(
        "--repeat-counts",
        nargs="+",
        type=int,
        default=list(DEFAULT_REPEAT_COUNTS),
    )
    parser.add_argument(
        "--carryover-mode",
        choices=("none", "full", "substrate"),
        default="full",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            evaluate_transfer_exposure_prediction(
                train_scenario=args.train_scenario,
                transfer_scenario=args.transfer_scenario,
                seeds=tuple(args.seeds),
                repeat_counts=tuple(args.repeat_counts),
                carryover_mode=args.carryover_mode,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
