from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from phase8 import NativeSubstrateSystem, ScenarioSpec
from scripts.ceiling_benchmark_metrics import (
    aggregate_run_metrics,
    best_nn_aggregate,
    collapse_flag,
    criterion_metrics_from_exact_and_accuracy,
    frontier_summary,
)
from scripts.ceiling_benchmark_suite import (
    BENCHMARK_TRANSFER_POINT_COUNT,
    BenchmarkPoint,
    BenchmarkTaskSpec,
    TASK_ORDER,
    benchmark_suite_by_id,
    build_ceiling_benchmark_suite,
)
from scripts.compare_morphogenesis import benchmark_morphogenesis_config
from scripts.experiment_manifest import build_run_manifest, write_run_manifest
from scripts.neural_baseline import run_mlp_explicit, run_mlp_latent, run_rnn_latent
from scripts.neural_baseline_torch import (
    run_gru_latent,
    run_lstm_latent,
    run_transformer_latent,
    torch_available,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAIN_SEEDS = (13, 23, 37, 51, 79)
DEFAULT_PILOT_SEEDS = (13, 23, 37)
REAL_METHODS = ("fixed-visible", "fixed-latent", "growth-visible")
NN_METHODS = ("mlp-explicit", "mlp-latent", "elman", "gru", "lstm", "causal-transformer")
ALL_METHODS = REAL_METHODS + NN_METHODS


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


def _build_system_from_spec(
    seed: int,
    spec: ScenarioSpec,
    *,
    morphogenesis_enabled: bool = False,
    latent_transfer_split_enabled: bool = True,
) -> NativeSubstrateSystem:
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
        morphogenesis_config=benchmark_morphogenesis_config() if morphogenesis_enabled else None,
        latent_transfer_split_enabled=latent_transfer_split_enabled,
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


def _neural_result_to_run_record(
    *,
    point: BenchmarkPoint,
    task_key: str,
    method_id: str,
    seed: int,
    result,
) -> Dict[str, object]:
    expected_examples = point.expected_examples
    exact_matches = int(result.exact_matches)
    return {
        "benchmark_id": point.benchmark_id,
        "family_id": point.family_id,
        "family_order": point.family_order,
        "difficulty_index": point.difficulty_index,
        "task_key": task_key,
        "method_id": method_id,
        "seed": seed,
        "expected_examples": expected_examples,
        "exact_matches": exact_matches,
        "exact_match_rate": round(exact_matches / max(expected_examples, 1), 4),
        "mean_bit_accuracy": round(float(result.mean_bit_accuracy), 4),
        "criterion_reached": bool(result.criterion_reached),
        "examples_to_criterion": result.examples_to_criterion,
        "model_family": "nn",
    }


def _run_real_method(
    *,
    point: BenchmarkPoint,
    task_key: str,
    method_id: str,
    seed: int,
) -> Dict[str, object]:
    task_spec = point.tasks[task_key]
    latent = method_id == "fixed-latent"
    morphogenesis = method_id == "growth-visible"
    scenario = task_spec.latent_scenario if latent else task_spec.visible_scenario
    system = _build_system_from_spec(seed, scenario, morphogenesis_enabled=morphogenesis)
    _run_spec(system, scenario)
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
    }


def _run_nn_method(
    *,
    point: BenchmarkPoint,
    task_key: str,
    method_id: str,
    seed: int,
    train_examples=None,
) -> Dict[str, object]:
    task_spec = point.tasks[task_key]
    mlp_hidden = point.node_count
    recurrent_hidden = point.node_count
    transformer_d_model = min(max(((point.node_count + 7) // 8) * 8, 8), 64)

    if method_id == "mlp-explicit":
        result = run_mlp_explicit(
            list(task_spec.visible_examples),
            seed=seed,
            hidden=mlp_hidden,
            train_examples=list(train_examples) if train_examples is not None else None,
        )
    elif method_id == "mlp-latent":
        result = run_mlp_latent(
            list(task_spec.latent_examples),
            seed=seed,
            hidden=mlp_hidden,
            train_examples=list(train_examples) if train_examples is not None else None,
        )
    elif method_id == "elman":
        result = run_rnn_latent(
            list(task_spec.latent_examples),
            seed=seed,
            hidden=recurrent_hidden,
            train_examples=list(train_examples) if train_examples is not None else None,
        )
    elif method_id == "gru":
        result = run_gru_latent(
            list(task_spec.latent_examples),
            seed=seed,
            hidden=recurrent_hidden,
            train_examples=list(train_examples) if train_examples is not None else None,
        )
    elif method_id == "lstm":
        result = run_lstm_latent(
            list(task_spec.latent_examples),
            seed=seed,
            hidden=recurrent_hidden,
            train_examples=list(train_examples) if train_examples is not None else None,
        )
    elif method_id == "causal-transformer":
        result = run_transformer_latent(
            list(task_spec.latent_examples),
            seed=seed,
            d_model=transformer_d_model,
            train_examples=list(train_examples) if train_examples is not None else None,
        )
    else:
        raise ValueError(f"Unsupported NN method: {method_id}")

    return _neural_result_to_run_record(
        point=point,
        task_key=task_key,
        method_id=method_id,
        seed=seed,
        result=result,
    )


def _aggregate_point_methods(
    point: BenchmarkPoint,
    runs: Sequence[Dict[str, object]],
) -> tuple[List[Dict[str, object]], Dict[str, object]]:
    method_aggregates: List[Dict[str, object]] = []
    for method_id in ALL_METHODS:
        method_runs = [run for run in runs if run["benchmark_id"] == point.benchmark_id and run["method_id"] == method_id]
        if not method_runs:
            continue
        aggregate = aggregate_run_metrics(method_runs)
        aggregate.update(
            {
                "benchmark_id": point.benchmark_id,
                "family_id": point.family_id,
                "family_order": point.family_order,
                "difficulty_index": point.difficulty_index,
                "label": point.label,
                "description": point.description,
                "method_id": method_id,
                "in_transfer_slice": False,
            }
        )
        method_aggregates.append(aggregate)

    nn_aggregates = [item for item in method_aggregates if item["method_id"] in NN_METHODS]
    real_aggregates = [item for item in method_aggregates if item["method_id"] in REAL_METHODS]
    for aggregate in real_aggregates:
        aggregate["collapse_flag"] = collapse_flag(aggregate, nn_aggregates)
    for aggregate in nn_aggregates:
        aggregate["collapse_flag"] = False

    best_nn = best_nn_aggregate(nn_aggregates)
    point_summary = {
        "benchmark_id": point.benchmark_id,
        "family_id": point.family_id,
        "family_order": point.family_order,
        "difficulty_index": point.difficulty_index,
        "label": point.label,
        "description": point.description,
        "best_nn_method_id": best_nn.get("method_id"),
        "best_nn_mean_bit_accuracy": best_nn.get("mean_bit_accuracy"),
        "best_nn_mean_exact_match_rate": best_nn.get("mean_exact_match_rate"),
        "all_real_collapsed": all(bool(item.get("collapse_flag")) for item in real_aggregates) if real_aggregates else False,
    }
    return method_aggregates, point_summary


def _select_transfer_points(
    suite: Sequence[BenchmarkPoint],
    point_summaries: Sequence[Dict[str, object]],
) -> List[BenchmarkPoint]:
    by_id = {point.benchmark_id: point for point in suite}
    summary_by_id = {point["benchmark_id"]: point for point in point_summaries}
    selected: List[BenchmarkPoint] = [suite[0]]
    frontier = frontier_summary(point_summaries)
    global_ceiling_id = frontier.get("earliest_global_ceiling")
    if global_ceiling_id:
        ceiling_summary = summary_by_id[global_ceiling_id]
        family_info = frontier["families"][ceiling_summary["family_id"]]
        pre_id = family_info.get("last_pre_collapse")
        if pre_id and pre_id not in {point.benchmark_id for point in selected}:
            selected.append(by_id[pre_id])
        if global_ceiling_id not in {point.benchmark_id for point in selected}:
            selected.append(by_id[global_ceiling_id])
    for point in suite:
        if len(selected) >= BENCHMARK_TRANSFER_POINT_COUNT:
            break
        if point.benchmark_id not in {item.benchmark_id for item in selected}:
            selected.append(point)
    return selected[:BENCHMARK_TRANSFER_POINT_COUNT]


def _run_real_transfer(
    *,
    point: BenchmarkPoint,
    method_id: str,
    seed: int,
    transfer_task_key: str,
) -> Dict[str, object]:
    train_task = point.tasks["task_a"]
    transfer_task = point.tasks[transfer_task_key]
    latent = method_id == "fixed-latent"
    morphogenesis = method_id == "growth-visible"
    train_scenario = train_task.latent_scenario if latent else train_task.visible_scenario
    eval_scenario = transfer_task.latent_scenario if latent else transfer_task.visible_scenario

    base_dir = ROOT / "tests_tmp" / f"ceiling_transfer_{uuid.uuid4().hex}"
    carryover_dir = base_dir / "memory"
    carryover_dir.mkdir(parents=True, exist_ok=True)
    try:
        train_system = _build_system_from_spec(seed, train_scenario, morphogenesis_enabled=morphogenesis)
        _run_spec(train_system, train_scenario)
        train_system.save_memory_carryover(carryover_dir)

        transfer_system = _build_system_from_spec(seed, eval_scenario, morphogenesis_enabled=morphogenesis)
        transfer_system.load_memory_carryover(carryover_dir)
        _run_spec(transfer_system, eval_scenario)
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
        "transfer_task_key": transfer_task_key,
        "expected_examples": point.expected_examples,
        "exact_matches": metrics["exact_matches"],
        "exact_match_rate": metrics["exact_match_rate"],
        "mean_bit_accuracy": metrics["mean_bit_accuracy"],
        "criterion_reached": metrics["criterion_reached"],
        "examples_to_criterion": metrics["examples_to_criterion"],
        "model_family": "real",
        "in_transfer_slice": True,
    }


def _transfer_train_examples(point: BenchmarkPoint, method_id: str):
    if method_id == "mlp-explicit":
        return point.tasks["task_a"].visible_examples
    return point.tasks["task_a"].latent_examples


def evaluate_ceiling_benchmarks(
    *,
    seeds: Sequence[int] = DEFAULT_MAIN_SEEDS,
    pilot_seeds: Sequence[int] = DEFAULT_PILOT_SEEDS,
    benchmark_ids: Sequence[str] | None = None,
    include_transfer: bool = True,
    allow_missing_torch: bool = False,
) -> Dict[str, object]:
    if not torch_available() and not allow_missing_torch:
        raise RuntimeError("PyTorch is not installed; install torch to run the ceiling benchmark suite.")

    suite = build_ceiling_benchmark_suite()
    if benchmark_ids:
        allowed = set(benchmark_ids)
        suite = tuple(point for point in suite if point.benchmark_id in allowed)

    cold_runs: List[Dict[str, object]] = []
    for point in suite:
        for task_key in TASK_ORDER:
            for seed in seeds:
                for method_id in REAL_METHODS:
                    cold_runs.append(_run_real_method(point=point, task_key=task_key, method_id=method_id, seed=seed))
                cold_runs.append(_run_nn_method(point=point, task_key=task_key, method_id="mlp-explicit", seed=seed))
                cold_runs.append(_run_nn_method(point=point, task_key=task_key, method_id="mlp-latent", seed=seed))
                cold_runs.append(_run_nn_method(point=point, task_key=task_key, method_id="elman", seed=seed))
                if torch_available():
                    cold_runs.append(_run_nn_method(point=point, task_key=task_key, method_id="gru", seed=seed))
                    cold_runs.append(_run_nn_method(point=point, task_key=task_key, method_id="lstm", seed=seed))
                    cold_runs.append(_run_nn_method(point=point, task_key=task_key, method_id="causal-transformer", seed=seed))

    cold_aggregates: List[Dict[str, object]] = []
    point_summaries: List[Dict[str, object]] = []
    for point in suite:
        aggregates, point_summary = _aggregate_point_methods(point, cold_runs)
        cold_aggregates.extend(aggregates)
        point_summaries.append(point_summary)

    frontier = frontier_summary(point_summaries)

    transfer_runs: List[Dict[str, object]] = []
    transfer_point_ids: List[str] = []
    if include_transfer and suite:
        transfer_points = _select_transfer_points(suite, point_summaries)
        transfer_point_ids = [point.benchmark_id for point in transfer_points]
        for aggregate in cold_aggregates:
            if aggregate["benchmark_id"] in transfer_point_ids:
                aggregate["in_transfer_slice"] = True
        for point in transfer_points:
            for transfer_task_key in ("task_b", "task_c"):
                for seed in seeds:
                    for method_id in REAL_METHODS:
                        transfer_runs.append(
                            _run_real_transfer(
                                point=point,
                                method_id=method_id,
                                seed=seed,
                                transfer_task_key=transfer_task_key,
                            )
                        )
                    for method_id in ("mlp-explicit", "mlp-latent", "elman"):
                        transfer_runs.append(
                            _run_nn_method(
                                point=point,
                                task_key=transfer_task_key,
                                method_id=method_id,
                                seed=seed,
                                train_examples=_transfer_train_examples(point, method_id),
                            )
                            | {"transfer_task_key": transfer_task_key, "in_transfer_slice": True}
                        )
                    if torch_available():
                        for method_id in ("gru", "lstm", "causal-transformer"):
                            transfer_runs.append(
                                _run_nn_method(
                                    point=point,
                                    task_key=transfer_task_key,
                                    method_id=method_id,
                                    seed=seed,
                                    train_examples=_transfer_train_examples(point, method_id),
                                )
                                | {"transfer_task_key": transfer_task_key, "in_transfer_slice": True}
                            )

    transfer_aggregates: List[Dict[str, object]] = []
    if transfer_runs:
        transfer_keys = sorted({(run["benchmark_id"], run["method_id"], run["transfer_task_key"]) for run in transfer_runs})
        for benchmark_id, method_id, transfer_task_key in transfer_keys:
            matching_runs = [
                run
                for run in transfer_runs
                if run["benchmark_id"] == benchmark_id
                and run["method_id"] == method_id
                and run["transfer_task_key"] == transfer_task_key
            ]
            aggregate = aggregate_run_metrics(matching_runs)
            point = benchmark_suite_by_id()[benchmark_id]
            aggregate.update(
                {
                    "benchmark_id": benchmark_id,
                    "family_id": point.family_id,
                    "family_order": point.family_order,
                    "difficulty_index": point.difficulty_index,
                    "method_id": method_id,
                    "transfer_task_key": transfer_task_key,
                    "in_transfer_slice": True,
                }
            )
            transfer_aggregates.append(aggregate)

    return {
        "suite": [
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
        ],
        "methods": list(ALL_METHODS if torch_available() else REAL_METHODS + ("mlp-explicit", "mlp-latent", "elman")),
        "seeds": list(seeds),
        "pilot_seeds": list(pilot_seeds),
        "cold_start": {
            "runs": cold_runs,
            "aggregates": cold_aggregates,
            "points": point_summaries,
            "frontier": frontier,
            "transfer_point_ids": transfer_point_ids,
        },
        "transfer_slice": {
            "runs": transfer_runs,
            "aggregates": transfer_aggregates,
        }
        if transfer_runs
        else None,
    }


def _default_output_stem() -> str:
    return "ceiling_benchmark_suite"


def main() -> None:
    parser = argparse.ArgumentParser(description="Ceiling-mapping benchmark harness for REAL vs neural baselines")
    parser.add_argument("--output", type=str, help="path to save the main JSON manifest")
    parser.add_argument("--benchmarks", nargs="*", help="optional benchmark ids to run, e.g. A1 B4 C4")
    parser.add_argument("--seeds", nargs="*", type=int, help="explicit seed list for the main sweep")
    parser.add_argument("--pilot-seeds", nargs="*", type=int, help="explicit seed list for the pilot metadata")
    parser.add_argument("--skip-transfer", action="store_true", help="skip the reduced transfer slice")
    parser.add_argument("--allow-missing-torch", action="store_true", help="run only the non-torch subset if torch is unavailable")
    args = parser.parse_args()

    result = evaluate_ceiling_benchmarks(
        seeds=tuple(args.seeds) if args.seeds else DEFAULT_MAIN_SEEDS,
        pilot_seeds=tuple(args.pilot_seeds) if args.pilot_seeds else DEFAULT_PILOT_SEEDS,
        benchmark_ids=args.benchmarks,
        include_transfer=not args.skip_transfer,
        allow_missing_torch=args.allow_missing_torch,
    )
    output = args.output
    if output:
        manifest = build_run_manifest(
            harness="ceiling_benchmark_suite",
            seeds=result["seeds"],
            scenarios=[item["benchmark_id"] for item in result["suite"]],
            result=result,
            metadata={
                "methods": result["methods"],
                "transfer_enabled": not args.skip_transfer,
                "torch_available": torch_available(),
            },
        )
        write_run_manifest(output, manifest)
        print(f"Saved run manifest to {output}")
        frontier_path = Path(output).with_name(f"{Path(output).stem}_frontier.json")
        frontier_payload = result["cold_start"]["frontier"]
        frontier_path.write_text(json.dumps(frontier_payload, indent=2), encoding="utf-8")
        print(f"Saved frontier summary to {frontier_path}")
        return

    print(json.dumps(result["cold_start"]["frontier"], indent=2))


__all__ = [
    "ALL_METHODS",
    "DEFAULT_MAIN_SEEDS",
    "DEFAULT_PILOT_SEEDS",
    "NN_METHODS",
    "REAL_METHODS",
    "evaluate_ceiling_benchmarks",
]


if __name__ == "__main__":
    main()
