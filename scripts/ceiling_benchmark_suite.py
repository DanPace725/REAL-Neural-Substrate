from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

from phase8 import ScenarioSpec, SignalSpec, phase8_scenarios
from scripts.neural_baseline_data import SignalExample


SCENARIOS = phase8_scenarios()
FAMILY_ORDER = ("A", "B", "C")
TASK_ORDER = ("task_a", "task_b", "task_c")
BENCHMARK_TRANSFER_POINT_COUNT = 3

_CURRENT_TRANSFORM_MAPS: Dict[str, Dict[int, str]] = {
    "task_a": {0: "rotate_left_1", 1: "xor_mask_1010"},
    "task_b": {0: "rotate_left_1", 1: "xor_mask_0101"},
    "task_c": {0: "xor_mask_1010", 1: "xor_mask_0101"},
}

_AMBIGUOUS_3_TRANSFORM_MAPS: Dict[str, Dict[int, str]] = {
    "task_a": {0: "rotate_left_1", 1: "xor_mask_1010", 2: "xor_mask_0101", 3: "xor_mask_1010"},
    "task_b": {0: "rotate_left_1", 1: "xor_mask_0101", 2: "xor_mask_1010", 3: "xor_mask_0101"},
    "task_c": {0: "xor_mask_1010", 1: "xor_mask_0101", 2: "rotate_left_1", 3: "xor_mask_0101"},
}

_AMBIGUOUS_4_TRANSFORM_MAPS: Dict[str, Dict[int, str]] = {
    "task_a": {0: "rotate_left_1", 1: "xor_mask_1010", 2: "xor_mask_0101", 3: "identity"},
    "task_b": {0: "rotate_left_1", 1: "xor_mask_0101", 2: "identity", 3: "xor_mask_1010"},
    "task_c": {0: "xor_mask_1010", 1: "xor_mask_0101", 2: "rotate_left_1", 3: "identity"},
}


@dataclass(frozen=True)
class BenchmarkTaskSpec:
    task_key: str
    visible_scenario: ScenarioSpec
    latent_scenario: ScenarioSpec
    visible_examples: Tuple[SignalExample, ...]
    latent_examples: Tuple[SignalExample, ...]


@dataclass(frozen=True)
class BenchmarkPoint:
    benchmark_id: str
    family_id: str
    difficulty_index: int
    label: str
    description: str
    node_count: int
    expected_examples: int
    family_order: int
    tasks: Dict[str, BenchmarkTaskSpec]


def _bits4(value: int) -> List[int]:
    return [(value >> 3) & 1, (value >> 2) & 1, (value >> 1) & 1, value & 1]


def _parity(bits: Sequence[int]) -> int:
    return sum(int(bit) for bit in bits) % 2


def _apply_transform(bits: Sequence[int], transform: str) -> List[int]:
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


def _default_target_bits(
    input_bits: Sequence[int],
    *,
    task_id: str | None,
    context_bit: int | None,
) -> List[int]:
    if task_id is None or context_bit is None:
        return []
    task_suffix = str(task_id).split("_")[-1]
    transform_map = _CURRENT_TRANSFORM_MAPS.get(f"task_{task_suffix}")
    if transform_map is None:
        return []
    transform = transform_map[int(context_bit)]
    return _apply_transform(input_bits, transform)


def _ordered_signal_specs(spec: ScenarioSpec) -> Tuple[SignalSpec, ...]:
    ordered = list(spec.initial_signal_specs)
    if spec.signal_schedule_specs:
        for cycle in sorted(spec.signal_schedule_specs):
            ordered.extend(spec.signal_schedule_specs[cycle])
    return tuple(ordered)


def _clone_scenario(
    base: ScenarioSpec,
    *,
    name: str,
    description: str,
    signals: Sequence[SignalSpec],
) -> ScenarioSpec:
    signal_tuple = tuple(signals)
    return ScenarioSpec(
        name=name,
        description=description,
        adjacency=base.adjacency,
        positions=base.positions,
        source_id=base.source_id,
        sink_id=base.sink_id,
        cycles=len(signal_tuple) + max(base.cycles - len(_ordered_signal_specs(base)), 0),
        initial_packets=0,
        packet_schedule={},
        packet_ttl=base.packet_ttl,
        source_admission_policy=base.source_admission_policy,
        source_admission_rate=base.source_admission_rate,
        source_admission_min_rate=base.source_admission_min_rate,
        source_admission_max_rate=base.source_admission_max_rate,
        initial_signal_specs=(signal_tuple[0],),
        signal_schedule_specs={
            cycle: (signal_spec,)
            for cycle, signal_spec in enumerate(signal_tuple[1:], start=2)
        },
    )


def _latentize_signals(signals: Sequence[SignalSpec]) -> Tuple[SignalSpec, ...]:
    return tuple(
        SignalSpec(
            input_bits=list(spec.input_bits),
            payload_bits=list(spec.payload_bits) if spec.payload_bits is not None else None,
            context_bit=None,
            task_id=spec.task_id,
            target_bits=(
                list(spec.target_bits)
                if spec.target_bits is not None
                else _default_target_bits(
                    spec.input_bits,
                    task_id=spec.task_id,
                    context_bit=spec.context_bit,
                )
            ),
        )
        for spec in signals
    )


def _examples_from_signals(signals: Sequence[SignalSpec]) -> Tuple[SignalExample, ...]:
    return tuple(
        SignalExample(
            input_bits=list(spec.input_bits),
            context_bit=int(spec.context_bit) if spec.context_bit is not None else 0,
            target_bits=(
                list(spec.target_bits)
                if spec.target_bits is not None
                else _default_target_bits(
                    spec.input_bits,
                    task_id=spec.task_id,
                    context_bit=spec.context_bit,
                )
            ),
            task_id=str(spec.task_id or ""),
        )
        for spec in signals
    )


def _flatten_history(history: Sequence[Sequence[int]], window: int) -> List[int]:
    if window <= 0:
        return []
    padded = [[0, 0, 0, 0] for _ in range(max(window - len(history), 0))] + [list(bits) for bits in history[-window:]]
    flat: List[int] = []
    for bits in padded:
        flat.extend(bits)
    return flat


def _stage4_values() -> Tuple[int, ...]:
    base_values = [
        0b0001, 0b0110, 0b1011, 0b0101, 0b1110, 0b0011,
        0b1100, 0b1001, 0b0111, 0b1010, 0b0100, 0b1111,
        0b0000, 0b1101, 0b0010, 0b1000, 0b0110, 0b1011,
    ]
    masks = [
        0b0000, 0b1111, 0b0101, 0b1010, 0b0011, 0b1100,
        0b1001, 0b0110, 0b1110, 0b0001, 0b0100, 0b1011,
    ]
    return tuple(value ^ masks[pass_index] for pass_index in range(len(masks)) for value in base_values)


def _binary_memory_state(window: int) -> Callable[[Sequence[Sequence[int]], int, List[int]], int]:
    def resolve(history: Sequence[Sequence[int]], _: int, __: List[int]) -> int:
        return _parity(_flatten_history(history, window))

    return resolve


def _ambiguity_state(history: Sequence[Sequence[int]], _: int, __: List[int]) -> int:
    previous = list(history[-2:]) if history else []
    padded = [[0, 0, 0, 0] for _ in range(max(2 - len(previous), 0))] + previous
    low = _parity(padded[-1])
    high = _parity(padded[-2])
    return low + 2 * high


def _visible_binary_context(state: int, _: Sequence[Sequence[int]], __: int, ___: List[int]) -> int:
    return int(state)


def _visible_mod2_context(state: int, _: Sequence[Sequence[int]], __: int, ___: List[int]) -> int:
    return int(state % 2)


def _visible_scrambled_context(state: int, history: Sequence[Sequence[int]], index: int, bits: List[int]) -> int:
    recent = _flatten_history(history, 3)
    return int((_parity(recent) + state + index + sum(bits)) % 2)


def _build_task_family_signals(
    values: Iterable[int],
    *,
    task_ids: Sequence[str],
    transform_maps: Dict[str, Dict[int, str]],
    hidden_state_fn: Callable[[Sequence[Sequence[int]], int, List[int]], int],
    visible_context_fn: Callable[[int, Sequence[Sequence[int]], int, List[int]], int],
    task_prefix: str,
) -> Dict[str, Tuple[SignalSpec, ...]]:
    task_signals: Dict[str, List[SignalSpec]] = {task_key: [] for task_key in task_ids}
    history: List[List[int]] = []
    for index, value in enumerate(values):
        bits = _bits4(value)
        hidden_state = hidden_state_fn(history, index, bits)
        visible_context = visible_context_fn(hidden_state, history, index, bits)
        for task_key in task_ids:
            transform = transform_maps[task_key][hidden_state]
            task_signals[task_key].append(
                SignalSpec(
                    input_bits=list(bits),
                    context_bit=visible_context,
                    task_id=f"{task_prefix}_{task_key}",
                    target_bits=_apply_transform(bits, transform),
                )
            )
        history.append(bits)
    return {task_key: tuple(specs) for task_key, specs in task_signals.items()}


def _point_from_registered_scenarios(
    *,
    benchmark_id: str,
    family_id: str,
    difficulty_index: int,
    label: str,
    description: str,
    scenario_names: Dict[str, str],
) -> BenchmarkPoint:
    tasks: Dict[str, BenchmarkTaskSpec] = {}
    first_spec = SCENARIOS[next(iter(scenario_names.values()))]
    for task_key, scenario_name in scenario_names.items():
        visible_scenario = SCENARIOS[scenario_name]
        visible_signals = _ordered_signal_specs(visible_scenario)
        latent_signals = _latentize_signals(visible_signals)
        latent_scenario = _clone_scenario(
            visible_scenario,
            name=f"{visible_scenario.name}_latent",
            description=f"{visible_scenario.description} (latent context view)",
            signals=latent_signals,
        )
        tasks[task_key] = BenchmarkTaskSpec(
            task_key=task_key,
            visible_scenario=visible_scenario,
            latent_scenario=latent_scenario,
            visible_examples=_examples_from_signals(visible_signals),
            latent_examples=_examples_from_signals(latent_signals),
        )
    return BenchmarkPoint(
        benchmark_id=benchmark_id,
        family_id=family_id,
        difficulty_index=difficulty_index,
        label=label,
        description=description,
        node_count=sum(1 for node_id in first_spec.positions if node_id != first_spec.sink_id),
        expected_examples=len(_ordered_signal_specs(first_spec)),
        family_order=FAMILY_ORDER.index(family_id),
        tasks=tasks,
    )


def _point_from_generated_signals(
    *,
    benchmark_id: str,
    family_id: str,
    difficulty_index: int,
    label: str,
    description: str,
    base_scenario: ScenarioSpec,
    task_prefix: str,
    signals_by_task: Dict[str, Tuple[SignalSpec, ...]],
) -> BenchmarkPoint:
    tasks: Dict[str, BenchmarkTaskSpec] = {}
    for task_key in TASK_ORDER:
        visible_signals = signals_by_task[task_key]
        visible_scenario = _clone_scenario(
            base_scenario,
            name=f"{task_prefix}_{task_key}_visible",
            description=f"{description} ({task_key}, visible context)",
            signals=visible_signals,
        )
        latent_signals = _latentize_signals(visible_signals)
        latent_scenario = _clone_scenario(
            base_scenario,
            name=f"{task_prefix}_{task_key}_latent",
            description=f"{description} ({task_key}, latent context)",
            signals=latent_signals,
        )
        tasks[task_key] = BenchmarkTaskSpec(
            task_key=task_key,
            visible_scenario=visible_scenario,
            latent_scenario=latent_scenario,
            visible_examples=_examples_from_signals(visible_signals),
            latent_examples=_examples_from_signals(latent_signals),
        )
    return BenchmarkPoint(
        benchmark_id=benchmark_id,
        family_id=family_id,
        difficulty_index=difficulty_index,
        label=label,
        description=description,
        node_count=sum(1 for node_id in base_scenario.positions if node_id != base_scenario.sink_id),
        expected_examples=len(next(iter(signals_by_task.values()))),
        family_order=FAMILY_ORDER.index(family_id),
        tasks=tasks,
    )


def build_ceiling_benchmark_suite() -> Tuple[BenchmarkPoint, ...]:
    family_a = (
        _point_from_registered_scenarios(
            benchmark_id="A1",
            family_id="A",
            difficulty_index=1,
            label="A1",
            description="Scale/horizon anchor on the original 6-node, 18-packet task family.",
            scenario_names={
                "task_a": "cvt1_task_a_stage1",
                "task_b": "cvt1_task_b_stage1",
                "task_c": "cvt1_task_c_stage1",
            },
        ),
        _point_from_registered_scenarios(
            benchmark_id="A2",
            family_id="A",
            difficulty_index=2,
            label="A2",
            description="Large-topology anchor on the 10-node, 36-packet task family.",
            scenario_names={
                "task_a": "cvt1_task_a_large",
                "task_b": "cvt1_task_b_large",
                "task_c": "cvt1_task_c_large",
            },
        ),
        _point_from_registered_scenarios(
            benchmark_id="A3",
            family_id="A",
            difficulty_index=3,
            label="A3",
            description="Scale anchor on the 30-node, 108-packet task family.",
            scenario_names={
                "task_a": "cvt1_task_a_scale",
                "task_b": "cvt1_task_b_scale",
                "task_c": "cvt1_task_c_scale",
            },
        ),
        _point_from_registered_scenarios(
            benchmark_id="A4",
            family_id="A",
            difficulty_index=4,
            label="A4",
            description="Ceiling scale point on the 50-node, 216-packet task family.",
            scenario_names={
                "task_a": "cvt1_task_a_ceiling",
                "task_b": "cvt1_task_b_ceiling",
                "task_c": "cvt1_task_c_ceiling",
            },
        ),
    )

    scale_base = SCENARIOS["cvt1_task_a_scale"]
    ceiling_base = SCENARIOS["cvt1_task_a_ceiling"]
    scale_values = tuple(int("".join(str(bit) for bit in spec.input_bits), 2) for spec in _ordered_signal_specs(scale_base))
    ceiling_values = _stage4_values()

    family_b = (
        _point_from_generated_signals(
            benchmark_id="B1",
            family_id="B",
            difficulty_index=1,
            label="B1",
            description="Hidden-memory anchor using previous-packet parity on the 30-node, 108-packet topology.",
            base_scenario=scale_base,
            task_prefix="ceiling_b1",
            signals_by_task=_build_task_family_signals(
                scale_values,
                task_ids=TASK_ORDER,
                transform_maps=_CURRENT_TRANSFORM_MAPS,
                hidden_state_fn=_binary_memory_state(1),
                visible_context_fn=_visible_binary_context,
                task_prefix="ceiling_b1",
            ),
        ),
        _point_from_generated_signals(
            benchmark_id="B2",
            family_id="B",
            difficulty_index=2,
            label="B2",
            description="Hidden-memory task where context depends on parity over the previous two packets.",
            base_scenario=scale_base,
            task_prefix="ceiling_b2",
            signals_by_task=_build_task_family_signals(
                scale_values,
                task_ids=TASK_ORDER,
                transform_maps=_CURRENT_TRANSFORM_MAPS,
                hidden_state_fn=_binary_memory_state(2),
                visible_context_fn=_visible_binary_context,
                task_prefix="ceiling_b2",
            ),
        ),
        _point_from_generated_signals(
            benchmark_id="B3",
            family_id="B",
            difficulty_index=3,
            label="B3",
            description="Hidden-memory task where context depends on parity over the previous four packets.",
            base_scenario=scale_base,
            task_prefix="ceiling_b3",
            signals_by_task=_build_task_family_signals(
                scale_values,
                task_ids=TASK_ORDER,
                transform_maps=_CURRENT_TRANSFORM_MAPS,
                hidden_state_fn=_binary_memory_state(4),
                visible_context_fn=_visible_binary_context,
                task_prefix="ceiling_b3",
            ),
        ),
        _point_from_generated_signals(
            benchmark_id="B4",
            family_id="B",
            difficulty_index=4,
            label="B4",
            description="Hidden-memory task where context depends on an eight-step rolling parity summary.",
            base_scenario=scale_base,
            task_prefix="ceiling_b4",
            signals_by_task=_build_task_family_signals(
                scale_values,
                task_ids=TASK_ORDER,
                transform_maps=_CURRENT_TRANSFORM_MAPS,
                hidden_state_fn=_binary_memory_state(8),
                visible_context_fn=_visible_binary_context,
                task_prefix="ceiling_b4",
            ),
        ),
    )

    family_c = (
        _point_from_generated_signals(
            benchmark_id="C1",
            family_id="C",
            difficulty_index=1,
            label="C1",
            description="Current 2-transform family on the 30-node, 108-packet topology.",
            base_scenario=scale_base,
            task_prefix="ceiling_c1",
            signals_by_task=_build_task_family_signals(
                scale_values,
                task_ids=TASK_ORDER,
                transform_maps={
                    task_key: {
                        0: transforms[0],
                        1: transforms[1],
                        2: transforms[0],
                        3: transforms[1],
                    }
                    for task_key, transforms in _CURRENT_TRANSFORM_MAPS.items()
                },
                hidden_state_fn=_ambiguity_state,
                visible_context_fn=_visible_mod2_context,
                task_prefix="ceiling_c1",
            ),
        ),
        _point_from_generated_signals(
            benchmark_id="C2",
            family_id="C",
            difficulty_index=2,
            label="C2",
            description="Three-transform family with one added nontrivial transform.",
            base_scenario=scale_base,
            task_prefix="ceiling_c2",
            signals_by_task=_build_task_family_signals(
                scale_values,
                task_ids=TASK_ORDER,
                transform_maps=_AMBIGUOUS_3_TRANSFORM_MAPS,
                hidden_state_fn=_ambiguity_state,
                visible_context_fn=_visible_mod2_context,
                task_prefix="ceiling_c2",
            ),
        ),
        _point_from_generated_signals(
            benchmark_id="C3",
            family_id="C",
            difficulty_index=3,
            label="C3",
            description="Four-transform family with two added transforms and a 4-state controller.",
            base_scenario=scale_base,
            task_prefix="ceiling_c3",
            signals_by_task=_build_task_family_signals(
                scale_values,
                task_ids=TASK_ORDER,
                transform_maps=_AMBIGUOUS_4_TRANSFORM_MAPS,
                hidden_state_fn=_ambiguity_state,
                visible_context_fn=_visible_mod2_context,
                task_prefix="ceiling_c3",
            ),
        ),
        _point_from_generated_signals(
            benchmark_id="C4",
            family_id="C",
            difficulty_index=4,
            label="C4",
            description="Four-transform family with increased latent ambiguity on the 50-node, 216-packet topology.",
            base_scenario=ceiling_base,
            task_prefix="ceiling_c4",
            signals_by_task=_build_task_family_signals(
                ceiling_values,
                task_ids=TASK_ORDER,
                transform_maps=_AMBIGUOUS_4_TRANSFORM_MAPS,
                hidden_state_fn=_ambiguity_state,
                visible_context_fn=_visible_scrambled_context,
                task_prefix="ceiling_c4",
            ),
        ),
    )

    return family_a + family_b + family_c


def benchmark_point_ids(points: Sequence[BenchmarkPoint] | None = None) -> Tuple[str, ...]:
    suite = points or build_ceiling_benchmark_suite()
    return tuple(point.benchmark_id for point in suite)


def benchmark_suite_by_id() -> Dict[str, BenchmarkPoint]:
    return {point.benchmark_id: point for point in build_ceiling_benchmark_suite()}


__all__ = [
    "BENCHMARK_TRANSFER_POINT_COUNT",
    "BenchmarkPoint",
    "BenchmarkTaskSpec",
    "FAMILY_ORDER",
    "TASK_ORDER",
    "benchmark_point_ids",
    "benchmark_suite_by_id",
    "build_ceiling_benchmark_suite",
]
