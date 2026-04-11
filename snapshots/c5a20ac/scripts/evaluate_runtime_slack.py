from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Sequence

from phase8 import NativeSubstrateSystem, ScenarioSpec
from scripts.benchmark_anticipation_metrics import anticipation_metrics
from scripts.ceiling_benchmark_metrics import criterion_metrics_from_exact_and_accuracy
from scripts.ceiling_benchmark_suite import BenchmarkPoint, benchmark_suite_by_id
from scripts.compare_morphogenesis import benchmark_morphogenesis_config
from scripts.experiment_manifest import build_run_manifest, write_run_manifest


DEFAULT_BENCHMARK_IDS = ("B2",)
DEFAULT_TASK_KEYS = ("task_a",)
DEFAULT_METHOD_IDS = ("self-selected",)
DEFAULT_SEEDS = (13,)
DEFAULT_CYCLE_MULTIPLIERS = (1.0, 1.5, 2.0)


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
    }


def _method_scenario(point: BenchmarkPoint, task_key: str, method_id: str) -> ScenarioSpec:
    task_spec = point.tasks[task_key]
    if method_id == "self-selected":
        return task_spec.visible_scenario
    if method_id in ("fixed-latent", "growth-latent"):
        return task_spec.latent_scenario
    return task_spec.visible_scenario


def _scaled_scenario(spec: ScenarioSpec, cycle_multiplier: float) -> ScenarioSpec:
    scaled_cycles = max(spec.cycles, int(round(spec.cycles * float(cycle_multiplier))))
    return replace(spec, cycles=scaled_cycles)


def _run_runtime_slack_case(
    *,
    point: BenchmarkPoint,
    task_key: str,
    method_id: str,
    seed: int,
    cycle_multiplier: float,
) -> Dict[str, object]:
    base_scenario = _method_scenario(point, task_key, method_id)
    scenario = _scaled_scenario(base_scenario, cycle_multiplier)
    system = _build_system_from_spec(seed, scenario, method_id=method_id)
    result = system.run_workload(
        cycles=scenario.cycles,
        initial_packets=scenario.initial_packets,
        packet_schedule=scenario.packet_schedule,
        initial_signal_specs=scenario.initial_signal_specs,
        signal_schedule_specs=scenario.signal_schedule_specs,
    )
    summary = result["summary"]
    metrics = _system_metrics(system, expected_examples=point.expected_examples)
    anticipation = anticipation_metrics(system)
    return {
        "benchmark_id": point.benchmark_id,
        "family_id": point.family_id,
        "task_key": task_key,
        "method_id": method_id,
        "seed": seed,
        "cycle_multiplier": round(float(cycle_multiplier), 3),
        "base_cycles": int(base_scenario.cycles),
        "cycles": int(scenario.cycles),
        "extra_cycles": int(scenario.cycles - base_scenario.cycles),
        "expected_examples": int(point.expected_examples),
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
    }


def evaluate_runtime_slack(
    *,
    benchmark_ids: Sequence[str] = DEFAULT_BENCHMARK_IDS,
    task_keys: Sequence[str] = DEFAULT_TASK_KEYS,
    method_ids: Sequence[str] = DEFAULT_METHOD_IDS,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    cycle_multipliers: Sequence[float] = DEFAULT_CYCLE_MULTIPLIERS,
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
                        _run_runtime_slack_case(
                            point=point,
                            task_key=task_key,
                            method_id=method_id,
                            seed=seed,
                            cycle_multiplier=cycle_multiplier,
                        )
                        for cycle_multiplier in cycle_multipliers
                    ]
                    baseline = next(
                        (run for run in runs if abs(float(run["cycle_multiplier"]) - 1.0) < 1e-9),
                        runs[0],
                    )
                    for run in runs:
                        run["delta_exact_match_rate"] = round(
                            float(run["exact_match_rate"]) - float(baseline["exact_match_rate"]),
                            4,
                        )
                        run["delta_best_rolling_exact_rate"] = round(
                            float(run["best_rolling_exact_rate"]) - float(baseline["best_rolling_exact_rate"]),
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
        "improved_exact_match_cases": sum(
            1
            for case in results
            for run in case["runs"]
            if float(run["cycle_multiplier"]) > 1.0 and float(run["delta_exact_match_rate"]) > 0.0
        ),
        "improved_best_rolling_cases": sum(
            1
            for case in results
            for run in case["runs"]
            if float(run["cycle_multiplier"]) > 1.0 and float(run["delta_best_rolling_exact_rate"]) > 0.0
        ),
    }
    result = {
        "benchmark_ids": list(benchmark_ids),
        "task_keys": list(task_keys),
        "method_ids": list(method_ids),
        "seeds": list(seeds),
        "cycle_multipliers": [round(float(value), 3) for value in cycle_multipliers],
        "results": results,
        "aggregate": aggregate,
    }
    if output_path is not None:
        manifest = build_run_manifest(
            harness="runtime_slack",
            seeds=seeds,
            scenarios=[f"{benchmark_id}:{task_key}" for benchmark_id in benchmark_ids for task_key in task_keys],
            metadata={
                "benchmark_ids": list(benchmark_ids),
                "task_keys": list(task_keys),
                "method_ids": list(method_ids),
                "cycle_multipliers": [round(float(value), 3) for value in cycle_multipliers],
            },
            result=result,
        )
        write_run_manifest(output_path, manifest)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate whether extra runtime slack changes benchmark outcomes.")
    parser.add_argument("--benchmarks", nargs="*", default=list(DEFAULT_BENCHMARK_IDS))
    parser.add_argument("--tasks", nargs="*", default=list(DEFAULT_TASK_KEYS))
    parser.add_argument("--methods", nargs="*", default=list(DEFAULT_METHOD_IDS))
    parser.add_argument("--seeds", nargs="*", type=int, default=list(DEFAULT_SEEDS))
    parser.add_argument("--cycle-multipliers", nargs="*", type=float, default=list(DEFAULT_CYCLE_MULTIPLIERS))
    parser.add_argument("--output", type=str)
    args = parser.parse_args()

    result = evaluate_runtime_slack(
        benchmark_ids=tuple(args.benchmarks),
        task_keys=tuple(args.tasks),
        method_ids=tuple(args.methods),
        seeds=tuple(args.seeds),
        cycle_multipliers=tuple(args.cycle_multipliers),
        output_path=Path(args.output) if args.output else None,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
