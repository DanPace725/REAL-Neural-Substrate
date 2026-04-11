from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from phase8 import NativeSubstrateSystem, ScenarioSpec
from scripts.ceiling_benchmark_metrics import criterion_metrics_from_exact_and_accuracy
from scripts.ceiling_benchmark_suite import BenchmarkPoint, TASK_ORDER, benchmark_suite_by_id
from scripts.compare_morphogenesis import benchmark_morphogenesis_config
from scripts.experiment_manifest import build_run_manifest, write_run_manifest


DEFAULT_BENCHMARK_IDS = ("A1", "B2", "C3")
DEFAULT_TASK_KEYS = ("task_a",)
DEFAULT_SEEDS = (13,)
FIXED_REAL_METHODS = ("fixed-visible", "fixed-latent", "growth-visible", "growth-latent")
SMOKE_METHODS = FIXED_REAL_METHODS + ("self-selected",)


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


def _run_spec(system: NativeSubstrateSystem, spec: ScenarioSpec) -> dict[str, object]:
    result = system.run_workload(
        cycles=spec.cycles,
        initial_packets=spec.initial_packets,
        packet_schedule=spec.packet_schedule,
        initial_signal_specs=spec.initial_signal_specs,
        signal_schedule_specs=spec.signal_schedule_specs,
    )
    return result["summary"]


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
    }


def _method_scenario(point: BenchmarkPoint, task_key: str, method_id: str) -> ScenarioSpec:
    task_spec = point.tasks[task_key]
    if method_id == "self-selected":
        return task_spec.visible_scenario
    if method_id in ("fixed-latent", "growth-latent"):
        return task_spec.latent_scenario
    return task_spec.visible_scenario


def _run_smoke_method(
    *,
    point: BenchmarkPoint,
    task_key: str,
    method_id: str,
    seed: int,
) -> Dict[str, object]:
    scenario = _method_scenario(point, task_key, method_id)
    system = _build_system_from_spec(seed, scenario, method_id=method_id)
    summary = _run_spec(system, scenario)
    metrics = _system_metrics(system, expected_examples=point.expected_examples)
    source_id = scenario.source_id
    capability_support = dict(summary.get("capability_supports", {}).get(source_id, {}))
    capability_timeline = list(summary.get("capability_timeline", []))
    return {
        "benchmark_id": point.benchmark_id,
        "family_id": point.family_id,
        "task_key": task_key,
        "seed": seed,
        "method_id": method_id,
        "exact_matches": metrics["exact_matches"],
        "exact_match_rate": metrics["exact_match_rate"],
        "mean_bit_accuracy": metrics["mean_bit_accuracy"],
        "criterion_reached": metrics["criterion_reached"],
        "examples_to_criterion": metrics["examples_to_criterion"],
        "capability_policy": summary.get("capability_policy", method_id),
        "capability_support": capability_support,
        "capability_timeline_preview": capability_timeline[:6],
        "capability_timeline_tail": capability_timeline[-3:],
        "latent_recruitment_cycles": list(summary.get("latent_recruitment_cycles", {}).get(source_id, [])),
        "growth_recruitment_cycles": list(summary.get("growth_recruitment_cycles", {}).get(source_id, [])),
    }


def evaluate_self_selected_smoke(
    *,
    benchmark_ids: Sequence[str] = DEFAULT_BENCHMARK_IDS,
    task_keys: Sequence[str] = DEFAULT_TASK_KEYS,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    output_path: Path | None = None,
) -> dict[str, object]:
    suite = benchmark_suite_by_id()
    selected_points = [suite[benchmark_id] for benchmark_id in benchmark_ids]
    point_results: List[dict[str, object]] = []
    for point in selected_points:
        for task_key in task_keys:
            for seed in seeds:
                method_runs = [
                    _run_smoke_method(
                        point=point,
                        task_key=task_key,
                        method_id=method_id,
                        seed=seed,
                    )
                    for method_id in SMOKE_METHODS
                ]
                fixed_runs = [run for run in method_runs if run["method_id"] in FIXED_REAL_METHODS]
                oracle = max(
                    fixed_runs,
                    key=lambda run: (float(run["exact_match_rate"]), float(run["mean_bit_accuracy"])),
                )
                self_selected = next(run for run in method_runs if run["method_id"] == "self-selected")
                point_results.append(
                    {
                        "benchmark_id": point.benchmark_id,
                        "family_id": point.family_id,
                        "task_key": task_key,
                        "seed": seed,
                        "oracle_method_id": oracle["method_id"],
                        "oracle_exact_match_rate": oracle["exact_match_rate"],
                        "self_selected_oracle_gap": round(
                            float(oracle["exact_match_rate"]) - float(self_selected["exact_match_rate"]),
                            4,
                        ),
                        "methods": method_runs,
                    }
                )

    aggregate = {
        "point_count": len(point_results),
        "mean_self_selected_oracle_gap": round(
            sum(float(item["self_selected_oracle_gap"]) for item in point_results)
            / max(len(point_results), 1),
            4,
        ),
        "by_family": {
            family_id: round(
                sum(
                    float(item["self_selected_oracle_gap"])
                    for item in point_results
                    if item["family_id"] == family_id
                )
                / max(1, sum(1 for item in point_results if item["family_id"] == family_id)),
                4,
            )
            for family_id in sorted({item["family_id"] for item in point_results})
        },
    }
    result = {
        "benchmark_ids": list(benchmark_ids),
        "task_keys": list(task_keys),
        "seeds": list(seeds),
        "methods": list(SMOKE_METHODS),
        "results": point_results,
        "aggregate": aggregate,
    }
    if output_path is not None:
        manifest = build_run_manifest(
            harness="self_selected_smoke",
            seeds=seeds,
            scenarios=benchmark_ids,
            metadata={"task_keys": list(task_keys), "methods": list(SMOKE_METHODS)},
            result=result,
        )
        write_run_manifest(output_path, manifest)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Lightweight smoke harness for self-selected REAL capability recruitment")
    parser.add_argument("--benchmarks", nargs="*", default=list(DEFAULT_BENCHMARK_IDS))
    parser.add_argument("--tasks", nargs="*", default=list(DEFAULT_TASK_KEYS), choices=list(TASK_ORDER))
    parser.add_argument("--seeds", nargs="*", type=int, default=list(DEFAULT_SEEDS))
    parser.add_argument("--output", type=str)
    args = parser.parse_args()

    result = evaluate_self_selected_smoke(
        benchmark_ids=tuple(args.benchmarks),
        task_keys=tuple(args.tasks),
        seeds=tuple(args.seeds),
        output_path=Path(args.output) if args.output else None,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
