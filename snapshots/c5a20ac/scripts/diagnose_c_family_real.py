from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path
from typing import Dict, List, Sequence

from phase8 import NativeSubstrateSystem
from scripts.ceiling_benchmark_metrics import aggregate_run_metrics, criterion_metrics_from_exact_and_accuracy
from scripts.ceiling_benchmark_suite import TASK_ORDER, BenchmarkPoint, benchmark_suite_by_id
from scripts.compare_morphogenesis import benchmark_morphogenesis_config
from scripts.experiment_manifest import build_run_manifest, write_run_manifest


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEEDS = (13, 23, 37)
DEFAULT_BENCHMARKS = ("C3", "C4")
REAL_METHODS = ("fixed-visible", "fixed-latent", "growth-visible", "growth-latent")
TRANSFER_TASK_KEYS = ("task_b", "task_c")


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


def _method_flags(method_id: str) -> tuple[bool, bool]:
    latent = method_id in {"fixed-latent", "growth-latent"}
    morphogenesis = method_id in {"growth-visible", "growth-latent"}
    return latent, morphogenesis


def _build_system_from_spec(
    seed: int,
    point: BenchmarkPoint,
    *,
    latent: bool,
    morphogenesis_enabled: bool,
    latent_transfer_split_enabled: bool,
) -> NativeSubstrateSystem:
    reference_spec = point.tasks["task_a"].latent_scenario if latent else point.tasks["task_a"].visible_scenario
    return NativeSubstrateSystem(
        adjacency=reference_spec.adjacency,
        positions=reference_spec.positions,
        source_id=reference_spec.source_id,
        sink_id=reference_spec.sink_id,
        selector_seed=seed,
        packet_ttl=reference_spec.packet_ttl,
        source_admission_policy=reference_spec.source_admission_policy,
        source_admission_rate=reference_spec.source_admission_rate,
        source_admission_min_rate=reference_spec.source_admission_min_rate,
        source_admission_max_rate=reference_spec.source_admission_max_rate,
        morphogenesis_config=benchmark_morphogenesis_config() if morphogenesis_enabled else None,
        latent_transfer_split_enabled=latent_transfer_split_enabled,
    )


def _run_spec(system: NativeSubstrateSystem, spec) -> dict[str, object]:
    result = system.run_workload(
        cycles=spec.cycles,
        initial_packets=spec.initial_packets,
        packet_schedule=spec.packet_schedule,
        initial_signal_specs=spec.initial_signal_specs,
        signal_schedule_specs=spec.signal_schedule_specs,
    )
    return result["summary"]


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


def _task_spec(point: BenchmarkPoint, task_key: str, *, latent: bool):
    task = point.tasks[task_key]
    return task.latent_scenario if latent else task.visible_scenario


def _run_real_method(
    *,
    point: BenchmarkPoint,
    task_key: str,
    method_id: str,
    seed: int,
    latent_transfer_split_enabled: bool,
) -> Dict[str, object]:
    latent, morphogenesis = _method_flags(method_id)
    spec = _task_spec(point, task_key, latent=latent)
    system = _build_system_from_spec(
        seed,
        point,
        latent=latent,
        morphogenesis_enabled=morphogenesis,
        latent_transfer_split_enabled=latent_transfer_split_enabled,
    )
    _run_spec(system, spec)
    metrics = _system_metrics(system, expected_examples=point.expected_examples)
    return {
        "benchmark_id": point.benchmark_id,
        "family_id": point.family_id,
        "family_order": point.family_order,
        "difficulty_index": point.difficulty_index,
        "task_key": task_key,
        "method_id": method_id,
        "seed": seed,
        "expected_examples": point.expected_examples,
        "exact_matches": metrics["exact_matches"],
        "exact_match_rate": metrics["exact_match_rate"],
        "mean_bit_accuracy": metrics["mean_bit_accuracy"],
        "criterion_reached": metrics["criterion_reached"],
        "examples_to_criterion": metrics["examples_to_criterion"],
        "model_family": "real",
        "latent_context": latent,
        "morphogenesis_enabled": morphogenesis,
    }


def _run_real_transfer(
    *,
    point: BenchmarkPoint,
    method_id: str,
    seed: int,
    transfer_task_key: str,
    latent_transfer_split_enabled: bool,
) -> Dict[str, object]:
    latent, morphogenesis = _method_flags(method_id)
    train_spec = _task_spec(point, "task_a", latent=latent)
    eval_spec = _task_spec(point, transfer_task_key, latent=latent)

    base_dir = ROOT / "tests_tmp" / f"c_family_real_{uuid.uuid4().hex}"
    carryover_dir = base_dir / "memory"
    carryover_dir.mkdir(parents=True, exist_ok=True)
    try:
        train_system = _build_system_from_spec(
            seed,
            point,
            latent=latent,
            morphogenesis_enabled=morphogenesis,
            latent_transfer_split_enabled=latent_transfer_split_enabled,
        )
        _run_spec(train_system, train_spec)
        train_system.save_memory_carryover(carryover_dir)

        transfer_system = _build_system_from_spec(
            seed,
            point,
            latent=latent,
            morphogenesis_enabled=morphogenesis,
            latent_transfer_split_enabled=latent_transfer_split_enabled,
        )
        transfer_system.load_memory_carryover(carryover_dir)
        _run_spec(transfer_system, eval_spec)
        metrics = _system_metrics(transfer_system, expected_examples=point.expected_examples)
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)

    return {
        "benchmark_id": point.benchmark_id,
        "family_id": point.family_id,
        "family_order": point.family_order,
        "difficulty_index": point.difficulty_index,
        "method_id": method_id,
        "seed": seed,
        "train_task_key": "task_a",
        "transfer_task_key": transfer_task_key,
        "expected_examples": point.expected_examples,
        "exact_matches": metrics["exact_matches"],
        "exact_match_rate": metrics["exact_match_rate"],
        "mean_bit_accuracy": metrics["mean_bit_accuracy"],
        "criterion_reached": metrics["criterion_reached"],
        "examples_to_criterion": metrics["examples_to_criterion"],
        "model_family": "real",
        "latent_context": latent,
        "morphogenesis_enabled": morphogenesis,
        "carryover_mode": "full",
    }


def _suite_records(suite: Sequence[BenchmarkPoint]) -> List[Dict[str, object]]:
    return [
        {
            "benchmark_id": point.benchmark_id,
            "family_id": point.family_id,
            "difficulty_index": point.difficulty_index,
            "label": point.label,
            "description": point.description,
            "node_count": point.node_count,
            "expected_examples": point.expected_examples,
            "task_keys": list(point.tasks.keys()),
        }
        for point in suite
    ]


def _aggregate_cold_task_runs(
    suite: Sequence[BenchmarkPoint],
    runs: Sequence[Dict[str, object]],
) -> List[Dict[str, object]]:
    suite_by_id = {point.benchmark_id: point for point in suite}
    aggregates: List[Dict[str, object]] = []
    keys = sorted({(run["benchmark_id"], run["task_key"], run["method_id"]) for run in runs})
    for benchmark_id, task_key, method_id in keys:
        matching = [
            run
            for run in runs
            if run["benchmark_id"] == benchmark_id
            and run["task_key"] == task_key
            and run["method_id"] == method_id
        ]
        aggregate = aggregate_run_metrics(matching)
        point = suite_by_id[benchmark_id]
        aggregate.update(
            {
                "benchmark_id": benchmark_id,
                "family_id": point.family_id,
                "family_order": point.family_order,
                "difficulty_index": point.difficulty_index,
                "task_key": task_key,
                "method_id": method_id,
            }
        )
        aggregates.append(aggregate)
    return aggregates


def _aggregate_cold_method_runs(
    suite: Sequence[BenchmarkPoint],
    runs: Sequence[Dict[str, object]],
) -> List[Dict[str, object]]:
    suite_by_id = {point.benchmark_id: point for point in suite}
    aggregates: List[Dict[str, object]] = []
    keys = sorted({(run["benchmark_id"], run["method_id"]) for run in runs})
    for benchmark_id, method_id in keys:
        matching = [
            run
            for run in runs
            if run["benchmark_id"] == benchmark_id and run["method_id"] == method_id
        ]
        aggregate = aggregate_run_metrics(matching)
        point = suite_by_id[benchmark_id]
        aggregate.update(
            {
                "benchmark_id": benchmark_id,
                "family_id": point.family_id,
                "family_order": point.family_order,
                "difficulty_index": point.difficulty_index,
                "label": point.label,
                "description": point.description,
                "method_id": method_id,
            }
        )
        aggregates.append(aggregate)
    return aggregates


def _aggregate_transfer_runs(
    suite: Sequence[BenchmarkPoint],
    runs: Sequence[Dict[str, object]],
    cold_task_aggregates: Sequence[Dict[str, object]],
) -> List[Dict[str, object]]:
    suite_by_id = {point.benchmark_id: point for point in suite}
    cold_lookup = {
        (item["benchmark_id"], item["task_key"], item["method_id"]): item
        for item in cold_task_aggregates
    }
    aggregates: List[Dict[str, object]] = []
    keys = sorted({(run["benchmark_id"], run["method_id"], run["transfer_task_key"]) for run in runs})
    for benchmark_id, method_id, transfer_task_key in keys:
        matching = [
            run
            for run in runs
            if run["benchmark_id"] == benchmark_id
            and run["method_id"] == method_id
            and run["transfer_task_key"] == transfer_task_key
        ]
        aggregate = aggregate_run_metrics(matching)
        point = suite_by_id[benchmark_id]
        cold_baseline = cold_lookup[(benchmark_id, transfer_task_key, method_id)]
        aggregate.update(
            {
                "benchmark_id": benchmark_id,
                "family_id": point.family_id,
                "family_order": point.family_order,
                "difficulty_index": point.difficulty_index,
                "method_id": method_id,
                "train_task_key": "task_a",
                "transfer_task_key": transfer_task_key,
                "cold_mean_exact_match_rate": cold_baseline["mean_exact_match_rate"],
                "cold_mean_bit_accuracy": cold_baseline["mean_bit_accuracy"],
                "delta_vs_cold_exact_match_rate": round(
                    aggregate["mean_exact_match_rate"] - cold_baseline["mean_exact_match_rate"],
                    4,
                ),
                "delta_vs_cold_bit_accuracy": round(
                    aggregate["mean_bit_accuracy"] - cold_baseline["mean_bit_accuracy"],
                    4,
                ),
            }
        )
        aggregates.append(aggregate)
    return aggregates


def evaluate_c_family_real_diagnostic(
    *,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    benchmark_ids: Sequence[str] = DEFAULT_BENCHMARKS,
    include_transfer: bool = True,
    latent_transfer_split_enabled: bool = True,
) -> Dict[str, object]:
    suite_lookup = benchmark_suite_by_id()
    suite = [suite_lookup[benchmark_id] for benchmark_id in benchmark_ids]

    cold_runs: List[Dict[str, object]] = []
    for point in suite:
        for task_key in TASK_ORDER:
            for seed in seeds:
                for method_id in REAL_METHODS:
                    cold_runs.append(
                        _run_real_method(
                            point=point,
                            task_key=task_key,
                            method_id=method_id,
                            seed=seed,
                            latent_transfer_split_enabled=latent_transfer_split_enabled,
                        )
                    )

    cold_task_aggregates = _aggregate_cold_task_runs(suite, cold_runs)
    cold_method_aggregates = _aggregate_cold_method_runs(suite, cold_runs)

    transfer_runs: List[Dict[str, object]] = []
    if include_transfer:
        for point in suite:
            for transfer_task_key in TRANSFER_TASK_KEYS:
                for seed in seeds:
                    for method_id in REAL_METHODS:
                        transfer_runs.append(
                            _run_real_transfer(
                                point=point,
                                method_id=method_id,
                                seed=seed,
                                transfer_task_key=transfer_task_key,
                                latent_transfer_split_enabled=latent_transfer_split_enabled,
                            )
                        )

    transfer_aggregates = (
        _aggregate_transfer_runs(suite, transfer_runs, cold_task_aggregates)
        if transfer_runs
        else []
    )

    return {
        "suite": _suite_records(suite),
        "methods": list(REAL_METHODS),
        "seeds": list(seeds),
        "cold_start": {
            "runs": cold_runs,
            "task_aggregates": cold_task_aggregates,
            "method_aggregates": cold_method_aggregates,
        },
        "transfer": {
            "runs": transfer_runs,
            "aggregates": transfer_aggregates,
        }
        if include_transfer
        else None,
        "metadata": {
            "latent_transfer_split_enabled": latent_transfer_split_enabled,
            "full_capability_modes": {
                "fixed-visible": {"latent_context": False, "morphogenesis_enabled": False},
                "fixed-latent": {"latent_context": True, "morphogenesis_enabled": False},
                "growth-visible": {"latent_context": False, "morphogenesis_enabled": True},
                "growth-latent": {"latent_context": True, "morphogenesis_enabled": True},
            },
            "carryover_mode": "full",
            "train_task_key": "task_a",
            "transfer_task_keys": list(TRANSFER_TASK_KEYS),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="REAL-only C-family diagnostic with full capability coverage."
    )
    parser.add_argument("--output", type=str, help="path to save the JSON manifest")
    parser.add_argument("--benchmarks", nargs="*", default=list(DEFAULT_BENCHMARKS))
    parser.add_argument("--seeds", nargs="*", type=int, default=list(DEFAULT_SEEDS))
    parser.add_argument("--skip-transfer", action="store_true", help="skip A->B / A->C carryover runs")
    args = parser.parse_args()

    result = evaluate_c_family_real_diagnostic(
        seeds=tuple(args.seeds),
        benchmark_ids=tuple(args.benchmarks),
        include_transfer=not args.skip_transfer,
    )
    if args.output:
        manifest = build_run_manifest(
            harness="c_family_real_diagnostic",
            seeds=result["seeds"],
            scenarios=[item["benchmark_id"] for item in result["suite"]],
            result=result,
            metadata={
                "methods": result["methods"],
                "transfer_enabled": not args.skip_transfer,
                "full_capability_modes": result["metadata"]["full_capability_modes"],
            },
        )
        write_run_manifest(args.output, manifest)
        print(f"Saved run manifest to {args.output}")
        return

    print(json.dumps(result, indent=2))


__all__ = [
    "DEFAULT_BENCHMARKS",
    "DEFAULT_SEEDS",
    "REAL_METHODS",
    "TRANSFER_TASK_KEYS",
    "evaluate_c_family_real_diagnostic",
]


if __name__ == "__main__":
    main()
