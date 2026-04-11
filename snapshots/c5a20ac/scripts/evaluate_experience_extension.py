from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Sequence

from phase8 import NativeSubstrateSystem
from scripts.benchmark_anticipation_metrics import anticipation_metrics
from scripts.ceiling_benchmark_metrics import criterion_metrics_from_exact_and_accuracy
from scripts.ceiling_benchmark_suite import BenchmarkPoint, benchmark_suite_by_id
from scripts.compare_morphogenesis import benchmark_morphogenesis_config
from scripts.experiment_manifest import build_run_manifest, write_run_manifest
from scripts.repeated_signal_scenarios import (
    repeat_signal_scenario,
    signal_pass_span,
)


DEFAULT_BENCHMARK_IDS = ("B2",)
DEFAULT_TASK_KEYS = ("task_a",)
DEFAULT_METHOD_IDS = ("self-selected",)
DEFAULT_SEEDS = (13,)
DEFAULT_REPEAT_COUNTS = (1, 2, 3)


def _build_system_from_spec(
    seed: int,
    spec: ScenarioSpec,
    *,
    method_id: str,
) -> NativeSubstrateSystem:
    morphogenesis_enabled = method_id in ("growth-visible", "growth-latent", "self-selected")
    morphogenesis_config = benchmark_morphogenesis_config() if morphogenesis_enabled else None
    return NativeSubstrateSystem(
        adjacency=spec.adjacency,
        positions=spec.positions,
        source_id=spec.source_id,
        sink_id=spec.sink_id,
        selector_seed=seed,
        packet_ttl=spec.packet_ttl,
        source_admission_policy=spec.source_admission_policy,
        source_admission_rate=spec.source_admission_rate,
        source_admission_min_rate=spec.source_admission_min_rate,
        source_admission_max_rate=spec.source_admission_max_rate,
        morphogenesis_config=morphogenesis_config,
        capability_policy=method_id,
    )


def _ordered_scored_packets(system: NativeSubstrateSystem) -> List[object]:
    return sorted(
        [
            packet
            for packet in system.environment.delivered_packets
            if packet.bit_match_ratio is not None
        ],
        key=lambda packet: (
            packet.delivered_cycle if packet.delivered_cycle is not None else system.global_cycle,
            packet.created_cycle,
            packet.packet_id,
        ),
    )


def _system_metrics(
    system: NativeSubstrateSystem,
    *,
    expected_examples: int,
) -> Dict[str, object]:
    packets = _ordered_scored_packets(system)
    exact_results = [bool(packet.matched_target) for packet in packets]
    bit_accuracies = [float(packet.bit_match_ratio or 0.0) for packet in packets]
    if len(exact_results) < expected_examples:
        missing = expected_examples - len(exact_results)
        exact_results.extend([False] * missing)
        bit_accuracies.extend([0.0] * missing)
    metrics = criterion_metrics_from_exact_and_accuracy(exact_results, bit_accuracies)
    return {
        "expected_examples": expected_examples,
        "examples_evaluated": len(packets),
        "exact_matches": sum(exact_results),
        "exact_match_rate": round(sum(exact_results) / max(expected_examples, 1), 4),
        "mean_bit_accuracy": round(sum(bit_accuracies) / max(expected_examples, 1), 4),
        "criterion_reached": bool(metrics["criterion_reached"]),
        "examples_to_criterion": metrics["examples_to_criterion"],
        "best_rolling_exact_rate": metrics["best_rolling_exact_rate"],
        "best_rolling_bit_accuracy": metrics["best_rolling_bit_accuracy"],
        "exact_results": exact_results,
        "bit_accuracies": bit_accuracies,
    }


def _method_scenario(point: BenchmarkPoint, task_key: str, method_id: str) -> ScenarioSpec:
    task_spec = point.tasks[task_key]
    if method_id == "self-selected":
        return task_spec.visible_scenario
    if method_id in ("fixed-latent", "growth-latent"):
        return task_spec.latent_scenario
    return task_spec.visible_scenario


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
                "exact_match_rate": round(sum(exact_slice) / max(base_expected_examples, 1), 4),
                "mean_bit_accuracy": round(sum(accuracy_slice) / max(base_expected_examples, 1), 4),
                "criterion_reached": bool(metrics["criterion_reached"]),
                "examples_to_criterion": metrics["examples_to_criterion"],
                "best_rolling_exact_rate": metrics["best_rolling_exact_rate"],
                "best_rolling_bit_accuracy": metrics["best_rolling_bit_accuracy"],
            }
        )
    return passes


def _run_experience_case(
    *,
    point: BenchmarkPoint,
    task_key: str,
    method_id: str,
    seed: int,
    repeat_count: int,
) -> Dict[str, object]:
    base_scenario = _method_scenario(point, task_key, method_id)
    scenario = repeat_signal_scenario(base_scenario, repeat_count)
    system = _build_system_from_spec(seed, scenario, method_id=method_id)
    result = system.run_workload(
        cycles=scenario.cycles,
        initial_packets=scenario.initial_packets,
        packet_schedule=scenario.packet_schedule,
        initial_signal_specs=scenario.initial_signal_specs,
        signal_schedule_specs=scenario.signal_schedule_specs,
    )
    summary = result["summary"]
    expected_examples = int(point.expected_examples) * max(int(repeat_count), 1)
    metrics = _system_metrics(system, expected_examples=expected_examples)
    anticipation = anticipation_metrics(system)
    per_pass = _pass_metrics(
        metrics["exact_results"],
        metrics["bit_accuracies"],
        base_expected_examples=int(point.expected_examples),
        repeat_count=repeat_count,
    )
    pass_span = signal_pass_span(base_scenario)
    per_pass_anticipation = [
        anticipation_metrics(
            system,
            cycle_start=1 + pass_index * pass_span,
            cycle_end=(pass_index + 1) * pass_span,
        )
        for pass_index in range(max(int(repeat_count), 1))
    ]
    for pass_metrics, pass_anticipation in zip(per_pass, per_pass_anticipation):
        pass_metrics["anticipation"] = pass_anticipation
    return {
        "benchmark_id": point.benchmark_id,
        "family_id": point.family_id,
        "task_key": task_key,
        "method_id": method_id,
        "seed": seed,
        "repeat_count": int(repeat_count),
        "base_cycles": int(base_scenario.cycles),
        "cycles": int(scenario.cycles),
        "base_expected_examples": int(point.expected_examples),
        "expected_examples": expected_examples,
        "exact_matches": metrics["exact_matches"],
        "exact_match_rate": metrics["exact_match_rate"],
        "mean_bit_accuracy": metrics["mean_bit_accuracy"],
        "criterion_reached": metrics["criterion_reached"],
        "examples_to_criterion": metrics["examples_to_criterion"],
        "best_rolling_exact_rate": metrics["best_rolling_exact_rate"],
        "best_rolling_bit_accuracy": metrics["best_rolling_bit_accuracy"],
        "time_to_first_feedback": summary.get("time_to_first_feedback"),
        "anticipation": anticipation,
        "latent_recruitment_cycles": list(summary.get("latent_recruitment_cycles", {}).get(base_scenario.source_id, [])),
        "growth_recruitment_cycles": list(summary.get("growth_recruitment_cycles", {}).get(base_scenario.source_id, [])),
        "per_pass": per_pass,
    }


def evaluate_experience_extension(
    *,
    benchmark_ids: Sequence[str] = DEFAULT_BENCHMARK_IDS,
    task_keys: Sequence[str] = DEFAULT_TASK_KEYS,
    method_ids: Sequence[str] = DEFAULT_METHOD_IDS,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    repeat_counts: Sequence[int] = DEFAULT_REPEAT_COUNTS,
    output_path: Path | None = None,
) -> dict[str, object]:
    suite = benchmark_suite_by_id()
    results: List[dict[str, object]] = []
    for benchmark_id in benchmark_ids:
        point = suite[benchmark_id]
        for task_key in task_keys:
            for method_id in method_ids:
                for seed in seeds:
                    runs = [
                        _run_experience_case(
                            point=point,
                            task_key=task_key,
                            method_id=method_id,
                            seed=seed,
                            repeat_count=repeat_count,
                        )
                        for repeat_count in repeat_counts
                    ]
                    baseline = next((run for run in runs if int(run["repeat_count"]) == 1), runs[0])
                    for run in runs:
                        run["delta_exact_match_rate"] = round(
                            float(run["exact_match_rate"]) - float(baseline["exact_match_rate"]),
                            4,
                        )
                        run["delta_best_rolling_exact_rate"] = round(
                            float(run["best_rolling_exact_rate"]) - float(baseline["best_rolling_exact_rate"]),
                            4,
                        )
                        final_pass = run["per_pass"][-1]
                        baseline_pass = baseline["per_pass"][-1]
                        run["delta_final_pass_exact_match_rate"] = round(
                            float(final_pass["exact_match_rate"]) - float(baseline_pass["exact_match_rate"]),
                            4,
                        )
                    results.append(
                        {
                            "benchmark_id": benchmark_id,
                            "family_id": point.family_id,
                            "task_key": task_key,
                            "method_id": method_id,
                            "seed": seed,
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
            if int(run["repeat_count"]) > 1 and float(run["delta_final_pass_exact_match_rate"]) > 0.0
        ),
    }
    result = {
        "benchmark_ids": list(benchmark_ids),
        "task_keys": list(task_keys),
        "method_ids": list(method_ids),
        "seeds": list(seeds),
        "repeat_counts": [int(value) for value in repeat_counts],
        "results": results,
        "aggregate": aggregate,
    }
    if output_path is not None:
        manifest = build_run_manifest(
            harness="experience_extension",
            seeds=seeds,
            scenarios=[f"{benchmark_id}:{task_key}" for benchmark_id in benchmark_ids for task_key in task_keys],
            metadata={
                "benchmark_ids": list(benchmark_ids),
                "task_keys": list(task_keys),
                "method_ids": list(method_ids),
                "repeat_counts": [int(value) for value in repeat_counts],
            },
            result=result,
        )
        write_run_manifest(output_path, manifest)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate whether repeating the same benchmark stream changes eventual performance.")
    parser.add_argument("--benchmarks", nargs="*", default=list(DEFAULT_BENCHMARK_IDS))
    parser.add_argument("--tasks", nargs="*", default=list(DEFAULT_TASK_KEYS))
    parser.add_argument("--methods", nargs="*", default=list(DEFAULT_METHOD_IDS))
    parser.add_argument("--seeds", nargs="*", type=int, default=list(DEFAULT_SEEDS))
    parser.add_argument("--repeat-counts", nargs="*", type=int, default=list(DEFAULT_REPEAT_COUNTS))
    parser.add_argument("--output", type=str)
    args = parser.parse_args()

    result = evaluate_experience_extension(
        benchmark_ids=tuple(args.benchmarks),
        task_keys=tuple(args.tasks),
        method_ids=tuple(args.methods),
        seeds=tuple(args.seeds),
        repeat_counts=tuple(args.repeat_counts),
        output_path=Path(args.output) if args.output else None,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
