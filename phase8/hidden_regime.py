from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Dict, Sequence, Tuple

from .models import SignalSpec
from .scenarios import (
    ScenarioSpec,
    basic_demo_topology,
    branch_pressure_topology,
    detour_resilience_topology,
)

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

TASK_TRANSFORMS_BINARY: Dict[str, Dict[int, str]] = {
    "task_a": {0: "rotate_left_1", 1: "xor_mask_1010"},
    "task_b": {0: "rotate_left_1", 1: "xor_mask_0101"},
    "task_c": {0: "xor_mask_1010", 1: "xor_mask_0101"},
}

TASK_TRANSFORMS_QUAD: Dict[str, Dict[int, str]] = {
    "task_a": {0: "rotate_left_1", 1: "xor_mask_1010", 2: "xor_mask_0101", 3: "identity"},
    "task_b": {0: "rotate_left_1", 1: "xor_mask_0101", 2: "identity", 3: "xor_mask_1010"},
    "task_c": {0: "xor_mask_1010", 1: "xor_mask_0101", 2: "rotate_left_1", 3: "identity"},
}


@dataclass(frozen=True)
class HiddenRegimeTaskSpec:
    task_key: str
    task_id: str
    visible_scenario: ScenarioSpec
    hidden_scenario: ScenarioSpec


@dataclass(frozen=True)
class HiddenRegimeCase:
    benchmark_id: str
    label: str
    description: str
    regime_cardinality: int
    sequence_memory_window: int
    pass_count: int
    expected_examples: int
    topology_name: str
    tasks: Dict[str, HiddenRegimeTaskSpec]


@dataclass(frozen=True)
class _HiddenRegimeFamilySpec:
    benchmark_id: str
    label: str
    description: str
    task_prefix: str
    regime_cardinality: int
    sequence_memory_window: int
    pass_count: int
    packet_ttl: int
    slack_cycles: int
    topology_name: str
    topology_builder: Callable[[], tuple[Dict[str, tuple[str, ...]], Dict[str, int], str, str]]


_FAMILY_SPECS: Tuple[_HiddenRegimeFamilySpec, ...] = (
    _HiddenRegimeFamilySpec(
        benchmark_id="HR1",
        label="Binary hidden regime, short memory",
        description="Binary hidden regime driven by the parity of the previous symbol, using a compact 4-node topology.",
        task_prefix="hidden_regime_hr1",
        regime_cardinality=2,
        sequence_memory_window=1,
        pass_count=2,
        packet_ttl=8,
        slack_cycles=8,
        topology_name="basic_demo",
        topology_builder=basic_demo_topology,
    ),
    _HiddenRegimeFamilySpec(
        benchmark_id="HR2",
        label="Binary hidden regime, extended memory",
        description="Binary hidden regime driven by a three-step parity window, forcing longer symbolic evidence accumulation.",
        task_prefix="hidden_regime_hr2",
        regime_cardinality=2,
        sequence_memory_window=3,
        pass_count=3,
        packet_ttl=10,
        slack_cycles=12,
        topology_name="branch_pressure",
        topology_builder=branch_pressure_topology,
    ),
    _HiddenRegimeFamilySpec(
        benchmark_id="HR3",
        label="Quad hidden regime, paired parity state",
        description="Four hidden regimes derived from the last two parity observations, with each regime mapped to a distinct transform.",
        task_prefix="hidden_regime_hr3",
        regime_cardinality=4,
        sequence_memory_window=2,
        pass_count=4,
        packet_ttl=12,
        slack_cycles=16,
        topology_name="detour_resilience",
        topology_builder=detour_resilience_topology,
    ),
    _HiddenRegimeFamilySpec(
        benchmark_id="HR4",
        label="Binary hidden regime with mid-run rule shift",
        description="Binary hidden regime with a mid-run remapping of regime-to-transform bindings, forcing the laminated controller to adapt after the shift.",
        task_prefix="hidden_regime_hr4",
        regime_cardinality=2,
        sequence_memory_window=3,
        pass_count=4,
        packet_ttl=10,
        slack_cycles=12,
        topology_name="branch_pressure",
        topology_builder=branch_pressure_topology,
    ),
)


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


def _binary_regime(parity_history: Sequence[int], *, window: int) -> int:
    relevant = [int(bit) & 1 for bit in list(parity_history)[-window:]]
    padded = [0 for _ in range(max(window - len(relevant), 0))] + relevant
    return int(sum(padded) % 2)


def _quad_regime(parity_history: Sequence[int]) -> int:
    history = [int(bit) & 1 for bit in list(parity_history)]
    low = history[-1] if len(history) >= 1 else 0
    high = history[-2] if len(history) >= 2 else 0
    return int(low + 2 * high)


def _task_transform_map(task_key: str, *, regime_cardinality: int) -> Dict[int, str]:
    if regime_cardinality == 4:
        return TASK_TRANSFORMS_QUAD[task_key]
    return TASK_TRANSFORMS_BINARY[task_key]


def _generate_hidden_regime_signals(
    task_key: str,
    *,
    task_id: str,
    regime_cardinality: int,
    sequence_memory_window: int,
    pass_count: int,
) -> tuple[SignalSpec, ...]:
    parity_history: list[int] = []
    signals: list[SignalSpec] = []
    transform_map = _task_transform_map(task_key, regime_cardinality=regime_cardinality)
    for pass_index in range(pass_count):
        mask = _mask_for_pass(pass_index)
        for value in BASE_VALUES:
            bits = _bits4(value ^ mask)
            if regime_cardinality == 4:
                regime = _quad_regime(parity_history)
            else:
                regime = _binary_regime(
                    parity_history,
                    window=sequence_memory_window,
                )
            transform = transform_map[regime]
            signals.append(
                SignalSpec(
                    input_bits=bits,
                    context_bit=regime,
                    task_id=task_id,
                    target_bits=_apply_transform(bits, transform),
                )
            )
            parity_history.append(_parity(bits))
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


@lru_cache(maxsize=1)
def hidden_regime_suite_by_id() -> Dict[str, HiddenRegimeCase]:
    suite: Dict[str, HiddenRegimeCase] = {}
    for spec in _FAMILY_SPECS:
        adjacency, positions, source_id, sink_id = spec.topology_builder()
        tasks: Dict[str, HiddenRegimeTaskSpec] = {}
        for task_key in ("task_a", "task_b", "task_c"):
            task_id = f"{spec.task_prefix}_{task_key}"
            if spec.benchmark_id == "HR4":
                phase1_task_id = f"{spec.task_prefix}_phase1_{task_key}"
                phase2_task_id = f"{spec.task_prefix}_phase2_{task_key}"
                phase1_signals = _generate_hidden_regime_signals(
                    task_key,
                    task_id=phase1_task_id,
                    regime_cardinality=spec.regime_cardinality,
                    sequence_memory_window=spec.sequence_memory_window,
                    pass_count=spec.pass_count // 2,
                )
                phase2_signals = _generate_hidden_regime_signals(
                    task_key,
                    task_id=phase2_task_id,
                    regime_cardinality=spec.regime_cardinality,
                    sequence_memory_window=spec.sequence_memory_window,
                    pass_count=spec.pass_count // 2,
                )
                visible_signals = tuple(list(phase1_signals) + list(phase2_signals))
            else:
                visible_signals = _generate_hidden_regime_signals(
                    task_key,
                    task_id=task_id,
                    regime_cardinality=spec.regime_cardinality,
                    sequence_memory_window=spec.sequence_memory_window,
                    pass_count=spec.pass_count,
                )
            hidden_signals = _latentize_signals(visible_signals)
            visible_scenario = _scenario_from_signals(
                name=f"{spec.benchmark_id}_{task_key}_visible",
                description=f"{spec.description} Visible regime labels are exposed as an ablation.",
                adjacency=adjacency,
                positions=positions,
                source_id=source_id,
                sink_id=sink_id,
                packet_ttl=spec.packet_ttl,
                slack_cycles=spec.slack_cycles,
                signals=visible_signals,
            )
            hidden_scenario = _scenario_from_signals(
                name=f"{spec.benchmark_id}_{task_key}_hidden",
                description=f"{spec.description} Regime labels are hidden; the sequence must carry the evidence.",
                adjacency=adjacency,
                positions=positions,
                source_id=source_id,
                sink_id=sink_id,
                packet_ttl=spec.packet_ttl,
                slack_cycles=spec.slack_cycles,
                signals=hidden_signals,
            )
            tasks[task_key] = HiddenRegimeTaskSpec(
                task_key=task_key,
                task_id=task_id,
                visible_scenario=visible_scenario,
                hidden_scenario=hidden_scenario,
            )

        suite[spec.benchmark_id] = HiddenRegimeCase(
            benchmark_id=spec.benchmark_id,
            label=spec.label,
            description=spec.description,
            regime_cardinality=spec.regime_cardinality,
            sequence_memory_window=spec.sequence_memory_window,
            pass_count=spec.pass_count,
            expected_examples=spec.pass_count * len(BASE_VALUES),
            topology_name=spec.topology_name,
            tasks=tasks,
        )
    return suite
