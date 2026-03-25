from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Sequence, Tuple

from phase8 import NativeSubstrateSystem, ScenarioSpec, SignalSpec, phase8_scenarios
from scripts.ceiling_benchmark_metrics import criterion_metrics_from_exact_and_accuracy
from scripts.compare_morphogenesis import benchmark_morphogenesis_config
from scripts.experiment_manifest import build_run_manifest, write_run_manifest


DEFAULT_BENCHMARK_IDS = ("C3S1", "C3S2", "C3S3", "C3S4", "C3S5", "C3S6")
DEFAULT_TASK_KEYS = ("task_a",)
DEFAULT_METHOD_IDS = ("fixed-visible", "fixed-latent", "growth-visible", "growth-latent")
DEFAULT_SEEDS = (13,)

AMBIGUOUS_4_TRANSFORM_MAPS: Dict[str, Dict[int, str]] = {
    "task_a": {0: "rotate_left_1", 1: "xor_mask_1010", 2: "xor_mask_0101", 3: "identity"},
    "task_b": {0: "rotate_left_1", 1: "xor_mask_0101", 2: "identity", 3: "xor_mask_1010"},
    "task_c": {0: "xor_mask_1010", 1: "xor_mask_0101", 2: "rotate_left_1", 3: "identity"},
}

BASE_VALUES: Tuple[int, ...] = (
    0b0001,
    0b0110,
    0b1011,
    0b0101,
    0b1110,
    0b0011,
    0b1100,
    0b1001,
    0b0111,
    0b1010,
    0b0100,
    0b1111,
    0b0000,
    0b1101,
    0b0010,
    0b1000,
    0b0110,
    0b1011,
)

CASE_SCALE_SPECS: Tuple[Tuple[int, int, str, str | None, Tuple[int, ...] | None], ...] = (
    (1, 1, "6-node, 18-example C3-style ambiguity scale anchor.", "cvt1_task_a_stage1", None),
    (2, 2, "10-node, 36-example C3-style ambiguity point on the large topology.", "cvt1_task_a_large", None),
    (3, 6, "30-node, 108-example C3-style ambiguity point on the scale topology.", "cvt1_task_a_scale", None),
    (4, 12, "50-node, 216-example C3-style ambiguity point on the ceiling topology.", "cvt1_task_a_ceiling", None),
    (5, 24, "75-node, 432-example aspirational C3-style ambiguity point.", None, (4, 6, 9, 12, 12, 11, 8, 6, 4, 2)),
    (6, 48, "100-node, 864-example aspirational C3-style ambiguity point.", None, (4, 8, 12, 16, 18, 16, 12, 8, 5)),
)


@dataclass(frozen=True)
class CScaleTaskSpec:
    task_key: str
    visible_scenario: ScenarioSpec
    latent_scenario: ScenarioSpec


@dataclass(frozen=True)
class CScaleCase:
    benchmark_id: str
    family_id: str
    difficulty_index: int
    label: str
    description: str
    source: str
    node_count: int
    expected_examples: int
    topology_depth: int
    tasks: Dict[str, CScaleTaskSpec]


def _bits4(value: int) -> list[int]:
    return [
        (value >> 3) & 1,
        (value >> 2) & 1,
        (value >> 1) & 1,
        value & 1,
    ]


def _parity(bits: Sequence[int]) -> int:
    return sum(int(bit) for bit in bits) % 2


def _apply_transform(bits: Sequence[int], transform: str) -> list[int]:
    payload = [1 if int(bit) else 0 for bit in bits]
    if transform == "identity":
        return list(payload)
    if transform == "rotate_left_1":
        return payload[1:] + payload[:1] if payload else []
    if transform == "xor_mask_1010":
        mask = [1, 0, 1, 0]
        return [payload[index] ^ mask[index] for index in range(min(len(payload), len(mask)))]
    if transform == "xor_mask_0101":
        mask = [0, 1, 0, 1]
        return [payload[index] ^ mask[index] for index in range(min(len(payload), len(mask)))]
    raise ValueError(f"Unsupported transform: {transform}")


def _mask_for_pass(pass_index: int) -> int:
    return (5 * pass_index + 3) % 16


def _ambiguity_state(history: Sequence[Sequence[int]]) -> int:
    previous = list(history[-2:]) if history else []
    padded = [[0, 0, 0, 0] for _ in range(max(2 - len(previous), 0))] + previous
    low = _parity(padded[-1])
    high = _parity(padded[-2])
    return low + 2 * high


def _visible_mod2_context(state: int) -> int:
    return int(state % 2)


def _scaled_c3_task_signals(task_key: str, *, pass_count: int) -> tuple[SignalSpec, ...]:
    history: list[list[int]] = []
    signals: list[SignalSpec] = []
    for pass_index in range(pass_count):
        mask = _mask_for_pass(pass_index)
        for value in BASE_VALUES:
            masked_value = value ^ mask
            bits = _bits4(masked_value)
            hidden_state = _ambiguity_state(history)
            context_bit = _visible_mod2_context(hidden_state)
            transform = AMBIGUOUS_4_TRANSFORM_MAPS[task_key][hidden_state]
            signals.append(
                SignalSpec(
                    input_bits=bits,
                    context_bit=context_bit,
                    task_id=task_key,
                    target_bits=_apply_transform(bits, transform),
                )
            )
            history.append(bits)
    return tuple(signals)


def _latentize_signals(signals: Sequence[SignalSpec]) -> tuple[SignalSpec, ...]:
    return tuple(
        SignalSpec(
            input_bits=list(spec.input_bits),
            payload_bits=list(spec.payload_bits) if spec.payload_bits is not None else None,
            context_bit=None,
            task_id=spec.task_id,
            target_bits=list(spec.target_bits) if spec.target_bits is not None else None,
        )
        for spec in signals
    )


def _scenario_from_signals(
    *,
    name: str,
    description: str,
    adjacency: Dict[str, tuple[str, ...]],
    positions: Dict[str, int],
    source_id: str,
    sink_id: str,
    packet_ttl: int,
    slack_cycles: int,
    signals: Sequence[SignalSpec],
) -> ScenarioSpec:
    signal_tuple = tuple(signals)
    return ScenarioSpec(
        name=name,
        description=description,
        adjacency=adjacency,
        positions=positions,
        source_id=source_id,
        sink_id=sink_id,
        cycles=len(signal_tuple) + slack_cycles,
        initial_packets=0,
        packet_schedule={},
        packet_ttl=packet_ttl,
        source_admission_policy="adaptive",
        source_admission_min_rate=1,
        source_admission_max_rate=2,
        initial_signal_specs=(signal_tuple[0],),
        signal_schedule_specs={
            cycle: (signal_spec,)
            for cycle, signal_spec in enumerate(signal_tuple[1:], start=2)
        },
    )


def _select_targets(width: int, center: float, fanout: int) -> list[int]:
    if width <= 0:
        return []
    start = int(round(center)) - fanout // 2
    start = max(0, min(start, max(width - fanout, 0)))
    indices = list(range(start, min(width, start + fanout)))
    while len(indices) < min(width, fanout):
        candidate = min(width - 1, (indices[-1] + 1) if indices else 0)
        if candidate not in indices:
            indices.append(candidate)
        else:
            break
    return indices


def _build_layered_topology(
    layer_widths: Sequence[int],
) -> tuple[Dict[str, tuple[str, ...]], Dict[str, int], str, str]:
    source_id = "n0"
    sink_id = "sink"
    positions: Dict[str, int] = {source_id: 0}
    adjacency: Dict[str, tuple[str, ...]] = {}
    layers: list[list[str]] = []
    next_id = 1
    for layer_index, width in enumerate(layer_widths, start=1):
        layer_nodes = [f"n{next_id + offset}" for offset in range(width)]
        next_id += width
        layers.append(layer_nodes)
        for node_id in layer_nodes:
            positions[node_id] = layer_index
    positions[sink_id] = len(layer_widths) + 1

    if not layers:
        adjacency[source_id] = (sink_id,)
        adjacency[sink_id] = ()
        return adjacency, positions, source_id, sink_id

    adjacency[source_id] = tuple(layers[0])
    incoming: Dict[str, set[str]] = {node_id: set() for layer in layers for node_id in layer}

    for layer_index, current_layer in enumerate(layers[:-1]):
        next_layer = layers[layer_index + 1]
        for node_index, node_id in enumerate(current_layer):
            center = ((node_index + 0.5) * len(next_layer) / max(len(current_layer), 1)) - 0.5
            fanout = 3 if len(next_layer) >= 6 else 2
            target_indices = _select_targets(len(next_layer), center, fanout)
            neighbors = tuple(next_layer[target_index] for target_index in target_indices)
            adjacency[node_id] = neighbors
            for neighbor_id in neighbors:
                incoming[neighbor_id].add(node_id)

        for next_index, next_node_id in enumerate(next_layer):
            if incoming[next_node_id]:
                continue
            source_index = min(
                range(len(current_layer)),
                key=lambda index: abs(
                    ((index + 0.5) * len(next_layer) / max(len(current_layer), 1)) - (next_index + 0.5)
                ),
            )
            source_node_id = current_layer[source_index]
            neighbors = list(adjacency.get(source_node_id, ()))
            if next_node_id not in neighbors:
                neighbors.append(next_node_id)
                adjacency[source_node_id] = tuple(neighbors)
                incoming[next_node_id].add(source_node_id)

    for node_id in layers[-1]:
        adjacency[node_id] = (sink_id,)
    adjacency[sink_id] = ()
    return adjacency, positions, source_id, sink_id


def _registered_topology_case(
    *,
    benchmark_id: str,
    difficulty_index: int,
    description: str,
    base_scenario_name: str,
    pass_count: int,
) -> CScaleCase:
    scenarios = phase8_scenarios()
    base = scenarios[base_scenario_name]
    adjacency = base.adjacency
    positions = base.positions
    source_id = base.source_id
    sink_id = base.sink_id
    packet_ttl = base.packet_ttl
    slack_cycles = max(base.cycles - 18 * pass_count, 0)
    tasks: Dict[str, CScaleTaskSpec] = {}
    for task_key in ("task_a", "task_b", "task_c"):
        visible_signals = _scaled_c3_task_signals(task_key, pass_count=pass_count)
        latent_signals = _latentize_signals(visible_signals)
        visible_scenario = _scenario_from_signals(
            name=f"{benchmark_id.lower()}_{task_key}_visible",
            description=f"{description} ({task_key}, visible context).",
            adjacency=adjacency,
            positions=positions,
            source_id=source_id,
            sink_id=sink_id,
            packet_ttl=packet_ttl,
            slack_cycles=slack_cycles,
            signals=visible_signals,
        )
        latent_scenario = _scenario_from_signals(
            name=f"{benchmark_id.lower()}_{task_key}_latent",
            description=f"{description} ({task_key}, latent context).",
            adjacency=adjacency,
            positions=positions,
            source_id=source_id,
            sink_id=sink_id,
            packet_ttl=packet_ttl,
            slack_cycles=slack_cycles,
            signals=latent_signals,
        )
        tasks[task_key] = CScaleTaskSpec(
            task_key=task_key,
            visible_scenario=visible_scenario,
            latent_scenario=latent_scenario,
        )
    return CScaleCase(
        benchmark_id=benchmark_id,
        family_id="C",
        difficulty_index=difficulty_index,
        label=benchmark_id,
        description=description,
        source="registered_topology",
        node_count=sum(1 for node_id in positions if node_id != sink_id),
        expected_examples=18 * pass_count,
        topology_depth=max(int(position) for position in positions.values()),
        tasks=tasks,
    )


def _generated_topology_case(
    *,
    benchmark_id: str,
    difficulty_index: int,
    description: str,
    layer_widths: Sequence[int],
    pass_count: int,
) -> CScaleCase:
    adjacency, positions, source_id, sink_id = _build_layered_topology(layer_widths)
    node_count = sum(1 for node_id in positions if node_id != sink_id)
    topology_depth = max(int(position) for position in positions.values())
    packet_ttl = max(28, topology_depth * 4)
    slack_cycles = max(32, topology_depth * 4)
    tasks: Dict[str, CScaleTaskSpec] = {}
    for task_key in ("task_a", "task_b", "task_c"):
        visible_signals = _scaled_c3_task_signals(task_key, pass_count=pass_count)
        latent_signals = _latentize_signals(visible_signals)
        visible_scenario = _scenario_from_signals(
            name=f"{benchmark_id.lower()}_{task_key}_visible",
            description=f"{description} ({task_key}, visible context).",
            adjacency=adjacency,
            positions=positions,
            source_id=source_id,
            sink_id=sink_id,
            packet_ttl=packet_ttl,
            slack_cycles=slack_cycles,
            signals=visible_signals,
        )
        latent_scenario = _scenario_from_signals(
            name=f"{benchmark_id.lower()}_{task_key}_latent",
            description=f"{description} ({task_key}, latent context).",
            adjacency=adjacency,
            positions=positions,
            source_id=source_id,
            sink_id=sink_id,
            packet_ttl=packet_ttl,
            slack_cycles=slack_cycles,
            signals=latent_signals,
        )
        tasks[task_key] = CScaleTaskSpec(
            task_key=task_key,
            visible_scenario=visible_scenario,
            latent_scenario=latent_scenario,
        )
    return CScaleCase(
        benchmark_id=benchmark_id,
        family_id="C",
        difficulty_index=difficulty_index,
        label=benchmark_id,
        description=description,
        source="generated_topology",
        node_count=node_count,
        expected_examples=18 * pass_count,
        topology_depth=topology_depth,
        tasks=tasks,
    )


def build_c_scale_cases() -> tuple[CScaleCase, ...]:
    cases: list[CScaleCase] = []
    for difficulty_index, pass_count, description, base_scenario_name, layer_widths in CASE_SCALE_SPECS:
        benchmark_id = f"C3S{difficulty_index}"
        if base_scenario_name is not None:
            cases.append(
                _registered_topology_case(
                    benchmark_id=benchmark_id,
                    difficulty_index=difficulty_index,
                    description=description,
                    base_scenario_name=base_scenario_name,
                    pass_count=pass_count,
                )
            )
        else:
            cases.append(
                _generated_topology_case(
                    benchmark_id=benchmark_id,
                    difficulty_index=difficulty_index,
                    description=description,
                    layer_widths=layer_widths or (),
                    pass_count=pass_count,
                )
            )
    return tuple(cases)


def c_scale_suite_by_id() -> Dict[str, CScaleCase]:
    return {case.benchmark_id: case for case in build_c_scale_cases()}


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


def _task_scenario(case: CScaleCase, task_key: str, method_id: str) -> ScenarioSpec:
    task = case.tasks[task_key]
    if method_id in ("fixed-latent", "growth-latent"):
        return task.latent_scenario
    return task.visible_scenario


def _runtime_commitment(system: NativeSubstrateSystem) -> dict[str, float]:
    memory_entry_count = sum(len(agent.engine.memory.entries) for agent in system.agents.values())
    pattern_count = sum(len(agent.substrate.constraint_patterns) for agent in system.agents.values())
    active_edge_count = sum(len(agent.substrate.active_neighbors()) for agent in system.agents.values())
    supported_context_count = sum(len(agent.substrate.supported_contexts) for agent in system.agents.values())
    branch_context_credit_total = 0.0
    branch_context_debt_total = 0.0
    context_branch_transform_credit_total = 0.0
    context_branch_transform_debt_total = 0.0
    for state in system.environment.node_states.values():
        branch_context_credit_total += sum(float(value) for value in state.branch_context_credit.values())
        branch_context_debt_total += sum(float(value) for value in state.branch_context_debt.values())
        context_branch_transform_credit_total += sum(
            float(value) for value in state.context_branch_transform_credit.values()
        )
        context_branch_transform_debt_total += sum(
            float(value) for value in state.context_branch_transform_debt.values()
        )
    return {
        "memory_entry_count": memory_entry_count,
        "pattern_count": pattern_count,
        "active_edge_count": active_edge_count,
        "supported_context_count": supported_context_count,
        "branch_context_credit_total": round(branch_context_credit_total, 4),
        "branch_context_debt_total": round(branch_context_debt_total, 4),
        "context_branch_transform_credit_total": round(context_branch_transform_credit_total, 4),
        "context_branch_transform_debt_total": round(context_branch_transform_debt_total, 4),
    }


def _run_scale_case(
    *,
    case: CScaleCase,
    task_key: str,
    method_id: str,
    seed: int,
) -> dict[str, object]:
    scenario = _task_scenario(case, task_key, method_id)
    system = _build_system_from_spec(seed, scenario, method_id=method_id)
    start = time.monotonic()
    result = system.run_workload(
        cycles=scenario.cycles,
        initial_packets=scenario.initial_packets,
        packet_schedule=scenario.packet_schedule,
        initial_signal_specs=scenario.initial_signal_specs,
        signal_schedule_specs=scenario.signal_schedule_specs,
    )
    elapsed_seconds = time.monotonic() - start
    summary = result["summary"]
    metrics = _system_metrics(system, expected_examples=case.expected_examples)
    throughput_examples = case.expected_examples / max(elapsed_seconds, 1e-9)
    throughput_cycles = scenario.cycles / max(elapsed_seconds, 1e-9)
    commitment = _runtime_commitment(system)
    return {
        "benchmark_id": case.benchmark_id,
        "family_id": case.family_id,
        "difficulty_index": case.difficulty_index,
        "label": case.label,
        "description": case.description,
        "source": case.source,
        "task_key": task_key,
        "method_id": method_id,
        "seed": seed,
        "node_count": case.node_count,
        "expected_examples": case.expected_examples,
        "topology_depth": case.topology_depth,
        "cycles": int(scenario.cycles),
        "packet_ttl": int(scenario.packet_ttl),
        "elapsed_seconds": round(elapsed_seconds, 4),
        "examples_per_second": round(throughput_examples, 4),
        "cycles_per_second": round(throughput_cycles, 4),
        "exact_matches": metrics["exact_matches"],
        "exact_match_rate": metrics["exact_match_rate"],
        "mean_bit_accuracy": metrics["mean_bit_accuracy"],
        "criterion_reached": metrics["criterion_reached"],
        "examples_to_criterion": metrics["examples_to_criterion"],
        "best_rolling_exact_rate": metrics["best_rolling_exact_rate"],
        "best_rolling_bit_accuracy": metrics["best_rolling_bit_accuracy"],
        "mean_route_cost": round(float(summary.get("mean_route_cost", 0.0)), 5),
        "mean_source_efficiency": round(float(summary.get("mean_source_efficiency", 0.0)), 4),
        "max_inbox_depth": int(summary.get("max_inbox_depth", 0)),
        "max_source_backlog": int(summary.get("max_source_backlog", 0)),
        "dynamic_node_count": int(summary.get("dynamic_node_count", 0)),
        "node_count_runtime": int(summary.get("node_count", case.node_count)),
        "edge_count_runtime": int(summary.get("edge_count", 0)),
        "commitment": commitment,
    }


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    return round(mean(items), 4) if items else 0.0


def _aggregate_runs(runs: Sequence[dict[str, object]]) -> dict[str, object]:
    return {
        "seed_count": len(runs),
        "mean_elapsed_seconds": _mean(float(run["elapsed_seconds"]) for run in runs),
        "mean_examples_per_second": _mean(float(run["examples_per_second"]) for run in runs),
        "mean_cycles_per_second": _mean(float(run["cycles_per_second"]) for run in runs),
        "mean_exact_match_rate": _mean(float(run["exact_match_rate"]) for run in runs),
        "mean_bit_accuracy": _mean(float(run["mean_bit_accuracy"]) for run in runs),
        "criterion_rate": _mean(1.0 if bool(run["criterion_reached"]) else 0.0 for run in runs),
        "mean_best_rolling_exact_rate": _mean(float(run["best_rolling_exact_rate"]) for run in runs),
        "mean_best_rolling_bit_accuracy": _mean(float(run["best_rolling_bit_accuracy"]) for run in runs),
        "mean_mean_route_cost": _mean(float(run["mean_route_cost"]) for run in runs),
        "mean_mean_source_efficiency": _mean(float(run["mean_source_efficiency"]) for run in runs),
        "mean_max_inbox_depth": _mean(float(run["max_inbox_depth"]) for run in runs),
        "mean_max_source_backlog": _mean(float(run["max_source_backlog"]) for run in runs),
        "mean_dynamic_node_count": _mean(float(run["dynamic_node_count"]) for run in runs),
        "mean_memory_entry_count": _mean(float(run["commitment"]["memory_entry_count"]) for run in runs),
        "mean_pattern_count": _mean(float(run["commitment"]["pattern_count"]) for run in runs),
        "mean_active_edge_count": _mean(float(run["commitment"]["active_edge_count"]) for run in runs),
        "mean_supported_context_count": _mean(float(run["commitment"]["supported_context_count"]) for run in runs),
        "mean_branch_context_credit_total": _mean(
            float(run["commitment"]["branch_context_credit_total"]) for run in runs
        ),
        "mean_branch_context_debt_total": _mean(
            float(run["commitment"]["branch_context_debt_total"]) for run in runs
        ),
    }


def _attach_scale_deltas(aggregates: list[dict[str, object]]) -> None:
    baselines: dict[tuple[str, str], dict[str, object]] = {}
    for aggregate in aggregates:
        key = (str(aggregate["task_key"]), str(aggregate["method_id"]))
        if str(aggregate["benchmark_id"]).endswith("S1"):
            baselines[key] = aggregate
    for aggregate in aggregates:
        key = (str(aggregate["task_key"]), str(aggregate["method_id"]))
        baseline = baselines.get(key)
        if baseline is None:
            continue
        baseline_elapsed = float(baseline["mean_elapsed_seconds"])
        baseline_eps = float(baseline["mean_examples_per_second"])
        aggregate["elapsed_ratio_vs_s1"] = round(
            float(aggregate["mean_elapsed_seconds"]) / max(baseline_elapsed, 1e-9),
            4,
        )
        aggregate["examples_per_second_ratio_vs_s1"] = round(
            float(aggregate["mean_examples_per_second"]) / max(baseline_eps, 1e-9),
            4,
        )
        aggregate["exact_match_rate_delta_vs_s1"] = round(
            float(aggregate["mean_exact_match_rate"]) - float(baseline["mean_exact_match_rate"]),
            4,
        )
        aggregate["bit_accuracy_delta_vs_s1"] = round(
            float(aggregate["mean_bit_accuracy"]) - float(baseline["mean_bit_accuracy"]),
            4,
        )


def evaluate_c_scale_suite(
    *,
    benchmark_ids: Sequence[str] = DEFAULT_BENCHMARK_IDS,
    task_keys: Sequence[str] = DEFAULT_TASK_KEYS,
    method_ids: Sequence[str] = DEFAULT_METHOD_IDS,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    output_path: Path | None = None,
) -> dict[str, object]:
    suite = c_scale_suite_by_id()
    selected_cases = [suite[benchmark_id] for benchmark_id in benchmark_ids]
    start = time.monotonic()
    runs: list[dict[str, object]] = []
    for case in selected_cases:
        for task_key in task_keys:
            for method_id in method_ids:
                for seed in seeds:
                    runs.append(
                        _run_scale_case(
                            case=case,
                            task_key=task_key,
                            method_id=method_id,
                            seed=seed,
                        )
                    )

    aggregate_rows: list[dict[str, object]] = []
    for case in selected_cases:
        for task_key in task_keys:
            for method_id in method_ids:
                matching_runs = [
                    run
                    for run in runs
                    if run["benchmark_id"] == case.benchmark_id
                    and run["task_key"] == task_key
                    and run["method_id"] == method_id
                ]
                if not matching_runs:
                    continue
                aggregate_rows.append(
                    {
                        "benchmark_id": case.benchmark_id,
                        "family_id": case.family_id,
                        "difficulty_index": case.difficulty_index,
                        "label": case.label,
                        "description": case.description,
                        "source": case.source,
                        "task_key": task_key,
                        "method_id": method_id,
                        "node_count": case.node_count,
                        "expected_examples": case.expected_examples,
                        "topology_depth": case.topology_depth,
                        **_aggregate_runs(matching_runs),
                    }
                )

    _attach_scale_deltas(aggregate_rows)
    method_summary: dict[str, dict[str, object]] = {}
    for method_id in method_ids:
        method_aggregates = [aggregate for aggregate in aggregate_rows if aggregate["method_id"] == method_id]
        if not method_aggregates:
            continue
        method_summary[method_id] = {
            "mean_elapsed_seconds": _mean(float(item["mean_elapsed_seconds"]) for item in method_aggregates),
            "mean_examples_per_second": _mean(float(item["mean_examples_per_second"]) for item in method_aggregates),
            "mean_exact_match_rate": _mean(float(item["mean_exact_match_rate"]) for item in method_aggregates),
            "mean_bit_accuracy": _mean(float(item["mean_bit_accuracy"]) for item in method_aggregates),
        }

    elapsed_seconds = round(time.monotonic() - start, 4)
    result = {
        "benchmark_ids": list(benchmark_ids),
        "task_keys": list(task_keys),
        "method_ids": list(method_ids),
        "seeds": list(seeds),
        "suite": [
            {
                "benchmark_id": case.benchmark_id,
                "label": case.label,
                "family_id": case.family_id,
                "difficulty_index": case.difficulty_index,
                "description": case.description,
                "source": case.source,
                "node_count": case.node_count,
                "expected_examples": case.expected_examples,
                "topology_depth": case.topology_depth,
                "task_keys": list(case.tasks.keys()),
            }
            for case in selected_cases
        ],
        "runs": runs,
        "aggregates": aggregate_rows,
        "method_summary": method_summary,
        "elapsed_seconds": elapsed_seconds,
    }
    if output_path is not None:
        manifest = build_run_manifest(
            harness="c_scale_suite",
            seeds=seeds,
            scenarios=benchmark_ids,
            metadata={
                "task_keys": list(task_keys),
                "method_ids": list(method_ids),
                "ambiguity_mode": "c3_fixed",
            },
            result=result,
        )
        write_run_manifest(output_path, manifest)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Dedicated C-family scaling harness for REAL.")
    parser.add_argument("--benchmarks", nargs="*", default=list(DEFAULT_BENCHMARK_IDS))
    parser.add_argument("--tasks", nargs="*", default=list(DEFAULT_TASK_KEYS))
    parser.add_argument("--methods", nargs="*", default=list(DEFAULT_METHOD_IDS))
    parser.add_argument("--seeds", nargs="*", type=int, default=list(DEFAULT_SEEDS))
    parser.add_argument("--output", type=str)
    args = parser.parse_args()

    result = evaluate_c_scale_suite(
        benchmark_ids=tuple(args.benchmarks),
        task_keys=tuple(args.tasks),
        method_ids=tuple(args.methods),
        seeds=tuple(args.seeds),
        output_path=Path(args.output) if args.output else None,
    )
    print(json.dumps(result, indent=2))


__all__ = [
    "CScaleCase",
    "CScaleTaskSpec",
    "DEFAULT_BENCHMARK_IDS",
    "DEFAULT_METHOD_IDS",
    "DEFAULT_SEEDS",
    "DEFAULT_TASK_KEYS",
    "build_c_scale_cases",
    "c_scale_suite_by_id",
    "evaluate_c_scale_suite",
]


if __name__ == "__main__":
    main()
