from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Tuple

from phase8 import ScenarioSpec
from phase8.models import SignalSpec


def ordered_signal_events(spec: ScenarioSpec) -> List[Tuple[int, SignalSpec]]:
    events: List[Tuple[int, SignalSpec]] = [
        (0, signal_spec) for signal_spec in spec.initial_signal_specs
    ]
    for cycle in sorted(dict(spec.signal_schedule_specs or {})):
        events.extend(
            (int(cycle), signal_spec)
            for signal_spec in dict(spec.signal_schedule_specs or {}).get(cycle, ())
        )
    return events


def expected_examples_for_signal_scenario(spec: ScenarioSpec) -> int:
    return len(ordered_signal_events(spec))


def signal_pass_span(spec: ScenarioSpec) -> int:
    events = ordered_signal_events(spec)
    if not events:
        return max(1, int(spec.cycles))
    return int(max(cycle for cycle, _ in events)) + 1


def repeat_signal_scenario(spec: ScenarioSpec, repeat_count: int) -> ScenarioSpec:
    events = ordered_signal_events(spec)
    if not events:
        raise ValueError("Experience extension currently requires explicit signal specs")
    last_signal_cycle = max(cycle for cycle, _ in events)
    tail_slack = max(0, int(spec.cycles) - int(last_signal_cycle))
    pass_span = int(last_signal_cycle) + 1
    repeated_events: List[Tuple[int, SignalSpec]] = []
    for repeat_index in range(max(int(repeat_count), 1)):
        offset = repeat_index * pass_span
        repeated_events.extend(
            (cycle + offset, signal_spec) for cycle, signal_spec in events
        )
    initial_signal_specs = tuple(
        signal_spec for cycle, signal_spec in repeated_events if cycle == 0
    )
    signal_schedule_specs: Dict[int, Tuple[SignalSpec, ...]] = {}
    for cycle, signal_spec in repeated_events:
        if cycle == 0:
            continue
        signal_schedule_specs.setdefault(int(cycle), tuple())
        signal_schedule_specs[int(cycle)] = signal_schedule_specs[int(cycle)] + (
            signal_spec,
        )
    repeated_cycles = int(
        last_signal_cycle + (max(int(repeat_count), 1) - 1) * pass_span + tail_slack
    )
    return replace(
        spec,
        cycles=repeated_cycles,
        initial_packets=0,
        packet_schedule={},
        initial_signal_specs=initial_signal_specs,
        signal_schedule_specs=signal_schedule_specs,
    )
