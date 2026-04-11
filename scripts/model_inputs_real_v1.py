from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable, Iterator, Sequence
from uuid import uuid4

from occupancy_baseline.mlp import evaluate_binary_predictions
from phase8 import (
    DEFAULT_LOCAL_UNIT_PRESET,
    FeedbackPulse,
    NativeSubstrateSystem,
)
from phase8.models import SignalPacket


DEFAULT_INPUT_PATH = Path(__file__).resolve().parents[2] / "model_inputs" / "chunks"
DEFAULT_OUTPUT_PATH = (
    Path(__file__).resolve().parents[1] / "docs" / "experiment_outputs" / "model_inputs_real_v1.json"
)
VALUE_BIN_THRESHOLDS = (-0.75, 0.0, 0.75)
DECISION_DOWN = "decision_next_down_or_flat"
DECISION_UP = "decision_next_up"
MODEL_INPUTS_TASK_ID = "model_inputs_next_sequence"
TOPOLOGY_LEGACY = "legacy"
TOPOLOGY_BOUNDED_OVERLAP = "bounded_overlap_13715"
TOPOLOGY_MULTIHOP = "feature_multihop_v1"
LOCAL_UNIT_LEGACY = "legacy"
LOCAL_UNIT_PULSE = "pulse_local_unit"
EVAL_FRESH = "fresh_session_eval"
EVAL_PERSISTENT = "persistent_eval"
EVAL_BOTH = "both"
CONTEXT_OFFLINE = "offline_scenario_context"
CONTEXT_ONLINE = "online_running_context"
CONTEXT_LATENT = "latent_context"
DEFAULT_CONTEXT_TREND_FEATURE = "prev_result_delta"
DEFAULT_CONTEXT_SHAPE_FEATURE = "gasf_abs_mean"


@dataclass(frozen=True)
class RunningFeatureStats:
    count: int = 0
    total: float = 0.0
    total_sq: float = 0.0

    def update(self, value: float) -> "RunningFeatureStats":
        return RunningFeatureStats(
            count=self.count + 1,
            total=self.total + float(value),
            total_sq=self.total_sq + float(value) * float(value),
        )

    @property
    def mean(self) -> float:
        if self.count <= 0:
            return 0.0
        return self.total / self.count

    @property
    def std(self) -> float:
        if self.count <= 0:
            return 1.0
        variance = max((self.total_sq / self.count) - (self.mean * self.mean), 1e-8)
        return math.sqrt(variance)


@dataclass(frozen=True)
class ModelInputsRowSummary:
    scenario_id: int
    window_start_index: int
    result_value: float
    feature_values: dict[str, float]


@dataclass(frozen=True)
class ModelInputsPacketSpec:
    source_node_id: str
    feature_name: str
    normalized_value: float
    input_bits: tuple[int, ...]


@dataclass(frozen=True)
class ModelInputsEpisode:
    scenario_id: int
    episode_index: int
    window_start_index: int
    current_result: float
    next_result: float
    next_delta: float
    label: int
    repeat_delta_baseline_prediction: int
    context_trend_value: float
    context_shape_value: float
    packets: tuple[ModelInputsPacketSpec, ...]


@dataclass(frozen=True)
class ModelInputsContextProfile:
    trend_feature_name: str
    shape_feature_name: str
    trend_median: float
    shape_median: float


@dataclass(frozen=True)
class ModelInputsRealConfig:
    input_path: str
    train_fraction: float = 0.7
    selector_seed: int = 13
    feedback_amount: float = 0.18
    eval_feedback_fraction: float = 1.0
    packet_ttl: int = 8
    forward_drain_cycles: int = 16
    feedback_drain_cycles: int = 4
    normalize_features: bool = True
    positive_delta_threshold: float = 0.0
    max_train_scenarios: int | None = None
    max_eval_scenarios: int | None = None
    max_train_episodes_per_scenario: int | None = None
    max_eval_episodes_per_scenario: int | None = None
    topology_mode: str = TOPOLOGY_LEGACY
    local_unit_mode: str = LOCAL_UNIT_LEGACY
    local_unit_preset: str = DEFAULT_LOCAL_UNIT_PRESET
    eval_mode: str = EVAL_FRESH
    context_mode: str = CONTEXT_ONLINE
    summary_only: bool = False


def _resolve_input_paths(input_path: str | Path) -> list[Path]:
    path = Path(input_path)
    if path.is_file():
        return [path]
    if path.is_dir():
        paths = sorted(path.glob("model_inputs_chunk_*.csv"))
        if paths:
            return paths
        csvs = sorted(path.glob("*.csv"))
        if csvs:
            return csvs
    raise FileNotFoundError(f"No CSV files found at {path}")


def _iter_scenario_rows(input_path: str | Path) -> Iterator[tuple[int, list[dict[str, str]]]]:
    csv.field_size_limit(1024 * 1024 * 256)
    current_scenario: int | None = None
    current_rows: list[dict[str, str]] = []

    for csv_path in _resolve_input_paths(input_path):
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                scenario_id = int(row["scenario_id"])
                if current_scenario is None:
                    current_scenario = scenario_id
                elif scenario_id != current_scenario:
                    yield current_scenario, current_rows
                    current_scenario = scenario_id
                    current_rows = []
                current_rows.append(row)

    if current_scenario is not None and current_rows:
        yield current_scenario, current_rows


def _split_index(size: int, train_fraction: float) -> int:
    if size < 2:
        raise ValueError("Need at least two scenarios for a train/eval split")
    raw = int(round(size * float(train_fraction)))
    return max(1, min(size - 1, raw))


def discover_scenario_ids(input_path: str | Path) -> list[int]:
    return [scenario_id for scenario_id, _ in _iter_scenario_rows(input_path)]


def select_scenario_splits(config: ModelInputsRealConfig) -> dict[str, list[int]]:
    scenario_ids = discover_scenario_ids(config.input_path)
    split_index = _split_index(len(scenario_ids), config.train_fraction)
    train_ids = list(scenario_ids[:split_index])
    eval_ids = list(scenario_ids[split_index:])
    if config.max_train_scenarios is not None:
        train_ids = train_ids[: int(config.max_train_scenarios)]
    if config.max_eval_scenarios is not None:
        eval_ids = eval_ids[: int(config.max_eval_scenarios)]
    if not train_ids:
        raise ValueError("No training scenarios selected")
    if not eval_ids:
        raise ValueError("No eval scenarios selected")
    return {
        "all": scenario_ids,
        "train": train_ids,
        "eval": eval_ids,
    }


def _parse_matrix_values(matrix_text: str) -> list[float]:
    cleaned = matrix_text.replace("[", " ").replace("]", " ")
    values = [float(token) for token in cleaned.split()]
    if not values:
        raise ValueError("Failed to parse matrix values")
    return values


def _mean(values: Sequence[float]) -> float:
    return sum(values) / max(len(values), 1)


def _median(values: Sequence[float]) -> float:
    ordered = sorted(float(value) for value in values)
    size = len(ordered)
    if size <= 0:
        return 0.0
    middle = size // 2
    if size % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _std(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    avg = _mean(values)
    variance = sum((value - avg) ** 2 for value in values) / len(values)
    return math.sqrt(max(variance, 0.0))


def _square_diag_mean(values: Sequence[float]) -> float:
    side = int(round(math.sqrt(float(len(values)))))
    if side > 0 and side * side == len(values):
        diagonal = [values[index * side + index] for index in range(side)]
        return _mean(diagonal)
    return _mean(values)


def summarize_model_inputs_row(
    row: dict[str, str],
    *,
    previous_result: float | None,
) -> ModelInputsRowSummary:
    result_value = float(row["result"])
    gasf_values = _parse_matrix_values(row["gasf"])
    gadf_values = _parse_matrix_values(row["gadf"])
    previous_delta = 0.0 if previous_result is None else result_value - float(previous_result)
    feature_values = {
        "result_value": result_value,
        "prev_result_delta": previous_delta,
        "gasf_mean": _mean(gasf_values),
        "gasf_std": _std(gasf_values),
        "gasf_abs_mean": _mean([abs(value) for value in gasf_values]),
        "gasf_diag_mean": _square_diag_mean(gasf_values),
        "gadf_mean": _mean(gadf_values),
        "gadf_std": _std(gadf_values),
        "gadf_abs_mean": _mean([abs(value) for value in gadf_values]),
        "gadf_diag_mean": _square_diag_mean(gadf_values),
    }
    return ModelInputsRowSummary(
        scenario_id=int(row["scenario_id"]),
        window_start_index=int(row["window_start_index"]),
        result_value=result_value,
        feature_values=feature_values,
    )


def _build_row_summaries(rows: Sequence[dict[str, str]]) -> list[ModelInputsRowSummary]:
    ordered = sorted(rows, key=lambda item: int(item["window_start_index"]))
    summaries: list[ModelInputsRowSummary] = []
    previous_result: float | None = None
    for row in ordered:
        summary = summarize_model_inputs_row(row, previous_result=previous_result)
        summaries.append(summary)
        previous_result = summary.result_value
    return summaries


def _bucket_to_bits(value: float) -> tuple[int, ...]:
    if value < VALUE_BIN_THRESHOLDS[0]:
        index = 0
    elif value < VALUE_BIN_THRESHOLDS[1]:
        index = 1
    elif value < VALUE_BIN_THRESHOLDS[2]:
        index = 2
    else:
        index = 3
    return tuple(1 if bucket_index == index else 0 for bucket_index in range(4))


def build_feature_stats(
    input_path: str | Path,
    scenario_ids: Sequence[int],
) -> dict[str, RunningFeatureStats]:
    selected = set(int(scenario_id) for scenario_id in scenario_ids)
    stats: dict[str, RunningFeatureStats] = {}
    for scenario_id, rows in _iter_scenario_rows(input_path):
        if scenario_id not in selected:
            continue
        row_summaries = _build_row_summaries(rows)
        for current_summary in row_summaries[:-1]:
            for feature_name, value in current_summary.feature_values.items():
                stats[feature_name] = stats.get(feature_name, RunningFeatureStats()).update(value)
    return stats


def _normalize_feature(
    value: float,
    feature_name: str,
    feature_stats: dict[str, RunningFeatureStats],
    *,
    normalize: bool,
) -> float:
    if not normalize:
        return float(value)
    stats = feature_stats.get(feature_name)
    if stats is None:
        return float(value)
    return (float(value) - stats.mean) / max(stats.std, 1e-6)


def build_episodes_for_scenario(
    rows: Sequence[dict[str, str]],
    *,
    feature_stats: dict[str, RunningFeatureStats],
    normalize_features: bool,
    positive_delta_threshold: float,
    context_profile: ModelInputsContextProfile | None = None,
) -> list[ModelInputsEpisode]:
    row_summaries = _build_row_summaries(rows)
    if len(row_summaries) < 2:
        return []

    episodes: list[ModelInputsEpisode] = []
    source_node_ids = {
        feature_name: f"source_{feature_name}"
        for feature_name in row_summaries[0].feature_values.keys()
    }
    for episode_index, current_summary in enumerate(row_summaries[:-1]):
        next_summary = row_summaries[episode_index + 1]
        next_delta = next_summary.result_value - current_summary.result_value
        label = 1 if next_delta > positive_delta_threshold else 0
        repeat_delta_prediction = (
            1
            if current_summary.feature_values.get("prev_result_delta", 0.0) > positive_delta_threshold
            else 0
        )
        context_trend_value = float(
            current_summary.feature_values.get(
                context_profile.trend_feature_name if context_profile is not None else DEFAULT_CONTEXT_TREND_FEATURE,
                0.0,
            )
        )
        context_shape_value = float(
            current_summary.feature_values.get(
                context_profile.shape_feature_name if context_profile is not None else DEFAULT_CONTEXT_SHAPE_FEATURE,
                0.0,
            )
        )
        packets: list[ModelInputsPacketSpec] = []
        for feature_name, raw_value in current_summary.feature_values.items():
            normalized_value = _normalize_feature(
                raw_value,
                feature_name,
                feature_stats,
                normalize=normalize_features,
            )
            packets.append(
                ModelInputsPacketSpec(
                    source_node_id=source_node_ids[feature_name],
                    feature_name=feature_name,
                    normalized_value=normalized_value,
                    input_bits=_bucket_to_bits(normalized_value),
                )
            )
        episodes.append(
            ModelInputsEpisode(
                scenario_id=current_summary.scenario_id,
                episode_index=episode_index,
                window_start_index=current_summary.window_start_index,
                current_result=current_summary.result_value,
                next_result=next_summary.result_value,
                next_delta=next_delta,
                label=label,
                repeat_delta_baseline_prediction=repeat_delta_prediction,
                context_trend_value=context_trend_value,
                context_shape_value=context_shape_value,
                packets=tuple(packets),
            )
        )
    return episodes


def build_context_profile(
    input_path: str | Path,
    scenario_ids: Sequence[int],
    *,
    trend_feature_name: str = DEFAULT_CONTEXT_TREND_FEATURE,
    shape_feature_name: str = DEFAULT_CONTEXT_SHAPE_FEATURE,
) -> ModelInputsContextProfile:
    selected = set(int(scenario_id) for scenario_id in scenario_ids)
    trend_values: list[float] = []
    shape_values: list[float] = []
    for scenario_id, rows in _iter_scenario_rows(input_path):
        if scenario_id not in selected:
            continue
        row_summaries = _build_row_summaries(rows)
        if len(row_summaries) < 2:
            continue
        episode_rows = row_summaries[:-1]
        trend_values.append(
            _mean(
                [
                    float(summary.feature_values.get(trend_feature_name, 0.0))
                    for summary in episode_rows
                ]
            )
        )
        shape_values.append(
            _mean(
                [
                    float(summary.feature_values.get(shape_feature_name, 0.0))
                    for summary in episode_rows
                ]
            )
        )
    return ModelInputsContextProfile(
        trend_feature_name=trend_feature_name,
        shape_feature_name=shape_feature_name,
        trend_median=_median(trend_values),
        shape_median=_median(shape_values),
    )


def _context_code_from_values(
    trend_value: float,
    shape_value: float,
    context_profile: ModelInputsContextProfile,
) -> int:
    trend_bit = 1 if float(trend_value) > float(context_profile.trend_median) else 0
    shape_bit = 1 if float(shape_value) > float(context_profile.shape_median) else 0
    return trend_bit * 2 + shape_bit


def _context_codes_for_scenario(
    episodes: Sequence[ModelInputsEpisode],
    *,
    context_mode: str,
    context_profile: ModelInputsContextProfile,
) -> list[int | None]:
    if context_mode == CONTEXT_LATENT:
        return [None for _ in episodes]
    if context_mode == CONTEXT_OFFLINE:
        if not episodes:
            return []
        code = _context_code_from_values(
            _mean([episode.context_trend_value for episode in episodes]),
            _mean([episode.context_shape_value for episode in episodes]),
            context_profile,
        )
        return [code for _ in episodes]
    if context_mode != CONTEXT_ONLINE:
        raise ValueError(f"Unsupported context_mode: {context_mode}")

    codes: list[int | None] = []
    running_trend: list[float] = []
    running_shape: list[float] = []
    for episode in episodes:
        running_trend.append(float(episode.context_trend_value))
        running_shape.append(float(episode.context_shape_value))
        codes.append(
            _context_code_from_values(
                _mean(running_trend),
                _mean(running_shape),
                context_profile,
            )
        )
    return codes


def _collect_context_codes(
    episodes_by_scenario: Sequence[Sequence[ModelInputsEpisode]],
    *,
    context_mode: str,
    context_profile: ModelInputsContextProfile,
) -> set[int]:
    codes: set[int] = set()
    for episodes in episodes_by_scenario:
        codes.update(
            int(code)
            for code in _context_codes_for_scenario(
                episodes,
                context_mode=context_mode,
                context_profile=context_profile,
            )
            if code is not None
        )
    return codes


def _bounded_overlap_children(
    *,
    source_index: int,
    next_width: int,
    span: int = 3,
) -> tuple[int, int]:
    start = min(max(0, 2 * source_index), max(next_width - span, 0))
    return start, min(start + min(span, next_width), next_width)


def _bounded_overlap_feature_topology(
    feature_names: Sequence[str],
    layer_widths: Sequence[int] = (3, 7, 15),
) -> tuple[dict[str, tuple[str, ...]], dict[str, int], str, str]:
    source_id = "source_hub"
    sink_id = "sink"
    adjacency: dict[str, tuple[str, ...]] = {source_id: ()}
    positions: dict[str, int] = {source_id: 0, sink_id: len(layer_widths) + 2}

    source_nodes = [f"source_{feature_name}" for feature_name in feature_names]
    for node_id in source_nodes:
        positions[node_id] = 0

    layers: list[list[str]] = []
    next_id = 0
    for layer_index, width in enumerate(layer_widths, start=1):
        layer_nodes = [f"overlap_{layer_index}_{next_id + offset}" for offset in range(width)]
        next_id += width
        layers.append(layer_nodes)
        for node_id in layer_nodes:
            positions[node_id] = layer_index

    if not layers:
        for node_id in source_nodes:
            adjacency[node_id] = (DECISION_DOWN, DECISION_UP)
        positions[DECISION_DOWN] = 1
        positions[DECISION_UP] = 1
        adjacency[DECISION_DOWN] = (sink_id,)
        adjacency[DECISION_UP] = (sink_id,)
        adjacency[sink_id] = ()
        return adjacency, positions, source_id, sink_id

    first_layer = layers[0]
    for source_index, node_id in enumerate(source_nodes):
        start, end = _bounded_overlap_children(
            source_index=source_index,
            next_width=len(first_layer),
        )
        adjacency[node_id] = tuple(first_layer[start:end])

    for current_layer, next_layer in zip(layers, layers[1:]):
        for node_index, node_id in enumerate(current_layer):
            start, end = _bounded_overlap_children(
                source_index=node_index,
                next_width=len(next_layer),
            )
            adjacency[node_id] = tuple(next_layer[start:end])

    positions[DECISION_DOWN] = len(layer_widths) + 1
    positions[DECISION_UP] = len(layer_widths) + 1
    for node_id in layers[-1]:
        adjacency[node_id] = (DECISION_DOWN, DECISION_UP)
    adjacency[DECISION_DOWN] = (sink_id,)
    adjacency[DECISION_UP] = (sink_id,)
    adjacency[sink_id] = ()
    return adjacency, positions, source_id, sink_id


def _feature_family(feature_name: str) -> str:
    if feature_name.startswith("gasf_"):
        return "gasf"
    if feature_name.startswith("gadf_"):
        return "gadf"
    if feature_name in {"result_value", "prev_result_delta"}:
        return "trend"
    return "shared"


def _multihop_feature_topology(
    feature_names: Sequence[str],
) -> tuple[dict[str, tuple[str, ...]], dict[str, int], str, str]:
    source_id = "source_hub"
    sink_id = "sink"
    relay_nodes = {
        "trend": "relay_trend",
        "gasf": "relay_gasf",
        "gadf": "relay_gadf",
        "shared": "relay_shared",
    }
    integrator_nodes = (
        "integrator_regime",
        "integrator_momentum",
        "integrator_shared",
    )
    vote_nodes = (
        "vote_down",
        "vote_up",
    )
    adjacency: dict[str, tuple[str, ...]] = {
        source_id: (),
        "relay_trend": ("integrator_momentum", "integrator_shared"),
        "relay_gasf": ("integrator_regime", "integrator_shared"),
        "relay_gadf": ("integrator_regime", "integrator_shared"),
        "relay_shared": ("integrator_regime", "integrator_momentum"),
        "integrator_regime": ("vote_down", "vote_up"),
        "integrator_momentum": ("vote_down", "vote_up"),
        "integrator_shared": ("vote_down", "vote_up"),
        "vote_down": (DECISION_DOWN, DECISION_UP),
        "vote_up": (DECISION_DOWN, DECISION_UP),
        DECISION_DOWN: (sink_id,),
        DECISION_UP: (sink_id,),
        sink_id: (),
    }
    positions: dict[str, int] = {
        source_id: 0,
        "relay_trend": 1,
        "relay_gasf": 1,
        "relay_gadf": 1,
        "relay_shared": 1,
        "integrator_regime": 2,
        "integrator_momentum": 2,
        "integrator_shared": 2,
        "vote_down": 3,
        "vote_up": 3,
        DECISION_DOWN: 4,
        DECISION_UP: 4,
        sink_id: 5,
    }

    for feature_name in feature_names:
        node_id = f"source_{feature_name}"
        family = _feature_family(feature_name)
        primary_relay = relay_nodes.get(family, "relay_shared")
        relay_targets = [primary_relay]
        if primary_relay != "relay_shared":
            relay_targets.append("relay_shared")
        adjacency[node_id] = tuple(relay_targets)
        positions[node_id] = 0

    for node_id in integrator_nodes + vote_nodes:
        adjacency.setdefault(node_id, ())
        positions.setdefault(node_id, positions[node_id])
    return adjacency, positions, source_id, sink_id


def model_inputs_topology(
    feature_names: Sequence[str],
    *,
    topology_mode: str,
) -> tuple[dict[str, tuple[str, ...]], dict[str, int], str, str]:
    if topology_mode == TOPOLOGY_MULTIHOP:
        return _multihop_feature_topology(feature_names)
    if topology_mode == TOPOLOGY_BOUNDED_OVERLAP:
        return _bounded_overlap_feature_topology(feature_names)
    if topology_mode != TOPOLOGY_LEGACY:
        raise ValueError(f"Unsupported topology_mode: {topology_mode}")
    adjacency: dict[str, tuple[str, ...]] = {
        "source_hub": (),
        DECISION_DOWN: ("sink",),
        DECISION_UP: ("sink",),
        "sink": (),
    }
    positions = {
        "source_hub": 0,
        DECISION_DOWN: 1,
        DECISION_UP: 1,
        "sink": 2,
    }
    for feature_name in feature_names:
        node_id = f"source_{feature_name}"
        adjacency[node_id] = (DECISION_DOWN, DECISION_UP)
        positions[node_id] = 0
    return adjacency, positions, "source_hub", "sink"


def build_model_inputs_system(
    config: ModelInputsRealConfig,
    *,
    feature_names: Sequence[str],
) -> NativeSubstrateSystem:
    adjacency, positions, source_id, sink_id = model_inputs_topology(
        feature_names,
        topology_mode=config.topology_mode,
    )
    topology_depth = max(int(position) for position in positions.values())
    return NativeSubstrateSystem(
        adjacency=adjacency,
        positions=positions,
        source_id=source_id,
        sink_id=sink_id,
        selector_seed=config.selector_seed,
        packet_ttl=max(int(config.packet_ttl), topology_depth * 4),
        local_unit_mode=config.local_unit_mode,
        local_unit_preset=config.local_unit_preset,
    )


def _direct_inject_packet(
    system: NativeSubstrateSystem,
    packet_spec: ModelInputsPacketSpec,
    *,
    context_code: int | None,
) -> SignalPacket:
    packet = system.environment.create_packet(
        cycle=system.global_cycle,
        input_bits=packet_spec.input_bits,
        payload_bits=packet_spec.input_bits,
        context_bit=context_code,
        task_id=MODEL_INPUTS_TASK_ID if context_code is not None else None,
    )
    packet.origin = packet_spec.source_node_id
    packet.target = "sink"
    if context_code is not None:
        packet.context_bit = int(context_code)
        packet.task_id = MODEL_INPUTS_TASK_ID
    system.environment.inboxes[packet_spec.source_node_id].append(packet)
    system.environment.total_injected += 1
    return packet


def _packets_by_id(packets: Iterable[SignalPacket]) -> dict[str, SignalPacket]:
    return {packet.packet_id: packet for packet in packets}


def _episode_resolved(system: NativeSubstrateSystem, packet_ids: set[str]) -> bool:
    unresolved = set(packet_ids)
    for packet in system.environment.delivered_packets:
        unresolved.discard(packet.packet_id)
    for packet in system.environment.dropped_packets:
        unresolved.discard(packet.packet_id)
    if unresolved:
        return False
    for packets in system.environment.inboxes.values():
        if any(packet.packet_id in packet_ids for packet in packets):
            return False
    return True


def _decision_node_for_packet(packet: SignalPacket) -> str | None:
    if not packet.edge_path:
        return None
    source_id, _, _ = packet.edge_path[-1].partition("->")
    return source_id or None


def _expected_decision_node(label: int) -> str:
    return DECISION_UP if int(label) == 1 else DECISION_DOWN


def run_episode(
    system: NativeSubstrateSystem,
    episode: ModelInputsEpisode,
    *,
    config: ModelInputsRealConfig,
    training: bool,
    default_prediction: int,
    context_code: int | None,
) -> dict[str, object]:
    packet_ids: list[str] = []
    active_feedback = (
        config.feedback_amount
        if training
        else config.feedback_amount * config.eval_feedback_fraction
    )
    original_feedback_amount = system.environment.feedback_amount
    system.environment.feedback_amount = 0.0

    for packet_spec in episode.packets:
        packet = _direct_inject_packet(
            system,
            packet_spec,
            context_code=context_code,
        )
        packet_ids.append(packet.packet_id)

    packet_id_set = set(packet_ids)
    for _ in range(max(1, config.forward_drain_cycles)):
        if _episode_resolved(system, packet_id_set):
            break
        system.run_global_cycle()

    delivered_by_id = _packets_by_id(system.environment.delivered_packets)
    dropped_by_id = _packets_by_id(system.environment.dropped_packets)
    delivered_packets = [
        delivered_by_id[packet_id]
        for packet_id in packet_ids
        if packet_id in delivered_by_id
    ]
    dropped_packets = [
        dropped_by_id[packet_id]
        for packet_id in packet_ids
        if packet_id in dropped_by_id
    ]

    decision_counts = {
        DECISION_DOWN: 0,
        DECISION_UP: 0,
    }
    target_decision = _expected_decision_node(episode.label)
    for packet in delivered_packets:
        decision_node = _decision_node_for_packet(packet)
        if decision_node in decision_counts:
            decision_counts[decision_node] += 1
        packet.feedback_award = 0.0
        packet.matched_target = decision_node == target_decision
        packet.bit_match_ratio = 1.0 if decision_node == target_decision else 0.0

    up_votes = decision_counts[DECISION_UP]
    down_votes = decision_counts[DECISION_DOWN]
    if up_votes == down_votes:
        predicted_label = int(default_prediction)
    else:
        predicted_label = 1 if up_votes > down_votes else 0
    decision_margin = abs(up_votes - down_votes)
    delivered_count = len(delivered_packets)
    correct_packet_count = decision_counts[target_decision]

    feedback_event_count = 0
    feedback_total = 0.0
    if active_feedback > 0.0 and delivered_packets:
        system.environment.feedback_amount = active_feedback
        pulses: list[FeedbackPulse] = []
        for packet in delivered_packets:
            if not packet.matched_target:
                continue
            pulses.append(
                FeedbackPulse(
                    packet_id=packet.packet_id,
                    edge_path=list(packet.edge_path),
                    amount=active_feedback,
                    transform_path=list(packet.transform_trace),
                    context_bit=context_code,
                    task_id=packet.task_id,
                    bit_match_ratio=1.0,
                    matched_target=True,
                )
            )
            packet.feedback_award = active_feedback
        system.environment.pending_feedback.extend(pulses)
        feedback_event_count = len(pulses)
        feedback_total = round(len(pulses) * active_feedback, 4)
        for _ in range(max(1, config.feedback_drain_cycles)):
            if not system.environment.pending_feedback:
                break
            system.run_global_cycle()
    system.environment.feedback_amount = original_feedback_amount

    return {
        "scenario_id": int(episode.scenario_id),
        "episode_index": int(episode.episode_index),
        "window_start_index": int(episode.window_start_index),
        "label": int(episode.label),
        "prediction": int(predicted_label),
        "correct": bool(predicted_label == episode.label and delivered_count > 0),
        "context_code": int(context_code) if context_code is not None else None,
        "current_result": float(episode.current_result),
        "next_result": float(episode.next_result),
        "next_delta": float(episode.next_delta),
        "packet_count": len(episode.packets),
        "delivered_packets": delivered_count,
        "dropped_packets": len(dropped_packets),
        "decision_counts": dict(decision_counts),
        "decision_margin": int(decision_margin),
        "prediction_confidence": round(decision_margin / max(delivered_count, 1), 4),
        "target_decision": target_decision,
        "correct_packet_count": int(correct_packet_count),
        "feedback_event_count": int(feedback_event_count),
        "feedback_total": float(feedback_total),
        "repeat_delta_baseline_prediction": int(episode.repeat_delta_baseline_prediction),
    }


def summarize_binary_results(
    labels: Sequence[int],
    predictions: Sequence[int],
) -> dict[str, object]:
    if not labels:
        metrics = evaluate_binary_predictions([0], [0])
        metrics.update({"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0})
        metrics["tp"] = 0.0
        metrics["tn"] = 0.0
        metrics["fp"] = 0.0
        metrics["fn"] = 0.0
        return {
            "episode_count": 0,
            "metrics": metrics,
            "positive_label_rate": 0.0,
            "positive_prediction_rate": 0.0,
        }
    metrics = evaluate_binary_predictions(labels, predictions)
    return {
        "episode_count": len(labels),
        "metrics": {key: round(float(value), 4) for key, value in metrics.items()},
        "positive_label_rate": round(sum(labels) / max(len(labels), 1), 4),
        "positive_prediction_rate": round(sum(predictions) / max(len(predictions), 1), 4),
    }


def summarize_episode_results(results: Sequence[dict[str, object]]) -> dict[str, object]:
    labels = [int(result["label"]) for result in results]
    predictions = [int(result["prediction"]) for result in results]
    summary = summarize_binary_results(labels, predictions)
    per_scenario_outcomes: dict[int, list[int]] = defaultdict(list)
    for result in results:
        per_scenario_outcomes[int(result["scenario_id"])].append(1 if bool(result["correct"]) else 0)
    scenario_accuracies = [
        sum(outcomes) / max(len(outcomes), 1)
        for outcomes in per_scenario_outcomes.values()
    ]
    summary.update(
        {
            "scenario_count": len(per_scenario_outcomes),
            "mean_scenario_accuracy": round(mean(scenario_accuracies), 4) if scenario_accuracies else 0.0,
            "mean_prediction_confidence": round(
                mean(float(result["prediction_confidence"]) for result in results),
                4,
            )
            if results
            else 0.0,
            "mean_delivered_packets": round(
                mean(float(result["delivered_packets"]) for result in results),
                4,
            )
            if results
            else 0.0,
            "mean_dropped_packets": round(
                mean(float(result["dropped_packets"]) for result in results),
                4,
            )
            if results
            else 0.0,
            "mean_feedback_events": round(
                mean(float(result["feedback_event_count"]) for result in results),
                4,
            )
            if results
            else 0.0,
        }
    )
    return summary


def _compact_system_summary(summary: dict[str, object]) -> dict[str, object]:
    keys = (
        "cycles",
        "injected_packets",
        "delivered_packets",
        "delivery_ratio",
        "dropped_packets",
        "drop_ratio",
        "mean_latency",
        "mean_route_cost",
        "mean_feedback_award",
        "node_atp_total",
        "exact_matches",
        "mean_bit_accuracy",
    )
    return {key: summary[key] for key in keys if key in summary}


def _feature_names_from_stats(feature_stats: dict[str, RunningFeatureStats]) -> list[str]:
    return sorted(feature_stats.keys())


def _majority_label_from_training(
    input_path: str | Path,
    train_ids: Sequence[int],
    *,
    feature_stats: dict[str, RunningFeatureStats],
    normalize_features: bool,
    positive_delta_threshold: float,
) -> int:
    labels: list[int] = []
    selected = set(int(scenario_id) for scenario_id in train_ids)
    for scenario_id, rows in _iter_scenario_rows(input_path):
        if scenario_id not in selected:
            continue
        for episode in build_episodes_for_scenario(
            rows,
            feature_stats=feature_stats,
            normalize_features=normalize_features,
            positive_delta_threshold=positive_delta_threshold,
        ):
            labels.append(int(episode.label))
    positives = sum(labels)
    negatives = len(labels) - positives
    return 1 if positives > negatives else 0


def _clone_system_from_carryover(
    config: ModelInputsRealConfig,
    *,
    feature_names: Sequence[str],
    carryover_dir: Path,
) -> NativeSubstrateSystem:
    cloned = build_model_inputs_system(config, feature_names=feature_names)
    loaded = cloned.load_carryover(carryover_dir)
    if not loaded:
        raise RuntimeError(f"Failed to load carryover from {carryover_dir}")
    return cloned


def _limit_episodes(
    episodes: list[ModelInputsEpisode],
    limit: int | None,
) -> list[ModelInputsEpisode]:
    if limit is None:
        return episodes
    return episodes[: max(int(limit), 0)]


def _normalize_eval_mode(eval_mode: str) -> str:
    normalized = str(eval_mode).strip().lower()
    aliases = {
        "fresh": EVAL_FRESH,
        EVAL_FRESH: EVAL_FRESH,
        "persistent": EVAL_PERSISTENT,
        EVAL_PERSISTENT: EVAL_PERSISTENT,
        "both": EVAL_BOTH,
        EVAL_BOTH: EVAL_BOTH,
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported eval_mode: {eval_mode}") from exc


def _protocol_payload(
    *,
    protocol_name: str,
    results: Sequence[dict[str, object]],
    baseline_labels: Sequence[int],
    baseline_repeat_predictions: Sequence[int],
    majority_label: int,
    system_summary: dict[str, object],
    training_context_codes: set[int],
    context_mode: str,
) -> dict[str, object]:
    eval_summary = summarize_episode_results(results)
    majority_baseline_summary = summarize_binary_results(
        baseline_labels,
        [int(majority_label) for _ in baseline_labels],
    )
    repeat_baseline_summary = summarize_binary_results(
        baseline_labels,
        baseline_repeat_predictions,
    )
    eval_context_codes = sorted(
        {
            int(result["context_code"])
            for result in results
            if result.get("context_code") is not None
        }
    )
    seen_results = [
        result
        for result in results
        if result.get("context_code") is not None
        and int(result["context_code"]) in training_context_codes
    ]
    unseen_results = [
        result
        for result in results
        if result.get("context_code") is not None
        and int(result["context_code"]) not in training_context_codes
    ]

    def _context_accuracy(items: Sequence[dict[str, object]]) -> float | None:
        if not items:
            return None
        return round(
            sum(1 for item in items if bool(item["correct"])) / max(len(items), 1),
            4,
        )

    if context_mode == CONTEXT_LATENT:
        context_probe = {
            "context_mode": context_mode,
            "training_context_codes": [],
            "eval_context_codes": [],
            "comparison_applicable": False,
            "status": "not_applicable_latent_context",
            "seen_episode_count": 0,
            "unseen_episode_count": 0,
            "seen_accuracy": None,
            "unseen_accuracy": None,
        }
    else:
        status = "ok"
        if not eval_context_codes:
            status = "not_applicable_no_explicit_eval_contexts"
        elif set(eval_context_codes).issubset(training_context_codes):
            status = "not_applicable_all_eval_contexts_seen"
        context_probe = {
            "context_mode": context_mode,
            "training_context_codes": sorted(training_context_codes),
            "eval_context_codes": eval_context_codes,
            "comparison_applicable": status == "ok",
            "status": status,
            "seen_episode_count": len(seen_results),
            "unseen_episode_count": len(unseen_results),
            "seen_accuracy": _context_accuracy(seen_results),
            "unseen_accuracy": _context_accuracy(unseen_results),
        }
    return {
        "protocol_name": protocol_name,
        "eval_episode_count": len(results),
        "eval_summary": eval_summary,
        "eval_baselines": {
            "majority_label": majority_baseline_summary,
            "repeat_last_delta_direction": repeat_baseline_summary,
        },
        "eval_accuracy_deltas": {
            "vs_majority_label": round(
                float(eval_summary["metrics"]["accuracy"])
                - float(majority_baseline_summary["metrics"]["accuracy"]),
                4,
            ),
            "vs_repeat_last_delta_direction": round(
                float(eval_summary["metrics"]["accuracy"])
                - float(repeat_baseline_summary["metrics"]["accuracy"]),
                4,
            ),
        },
        "context_probe": context_probe,
        "system_summary": system_summary,
        "results": list(results),
    }


def _run_eval_protocol(
    *,
    protocol_name: str,
    config: ModelInputsRealConfig,
    input_path: str | Path,
    eval_ids: set[int],
    feature_stats: dict[str, RunningFeatureStats],
    feature_names: Sequence[str],
    majority_label: int,
    carryover_dir: Path,
    context_profile: ModelInputsContextProfile,
    training_context_codes: set[int],
) -> dict[str, object]:
    protocol_system: NativeSubstrateSystem | None = None
    results: list[dict[str, object]] = []
    baseline_repeat_predictions: list[int] = []
    baseline_labels: list[int] = []

    if protocol_name == EVAL_PERSISTENT:
        protocol_system = _clone_system_from_carryover(
            config,
            feature_names=feature_names,
            carryover_dir=carryover_dir,
        )

    for scenario_id, rows in _iter_scenario_rows(input_path):
        if scenario_id not in eval_ids:
            continue
        episodes = build_episodes_for_scenario(
            rows,
            feature_stats=feature_stats,
            normalize_features=config.normalize_features,
            positive_delta_threshold=config.positive_delta_threshold,
            context_profile=context_profile,
        )
        episodes = _limit_episodes(episodes, config.max_eval_episodes_per_scenario)
        context_codes = _context_codes_for_scenario(
            episodes,
            context_mode=config.context_mode,
            context_profile=context_profile,
        )
        if protocol_name == EVAL_FRESH:
            protocol_system = _clone_system_from_carryover(
                config,
                feature_names=feature_names,
                carryover_dir=carryover_dir,
            )
        if protocol_system is None:
            raise RuntimeError("Protocol system was not initialized")
        for episode, context_code in zip(episodes, context_codes):
            baseline_labels.append(int(episode.label))
            baseline_repeat_predictions.append(int(episode.repeat_delta_baseline_prediction))
            results.append(
                run_episode(
                    protocol_system,
                    episode,
                    config=config,
                    training=False,
                    default_prediction=majority_label,
                    context_code=context_code,
                )
            )

    return _protocol_payload(
        protocol_name=protocol_name,
        results=results,
        baseline_labels=baseline_labels,
        baseline_repeat_predictions=baseline_repeat_predictions,
        majority_label=majority_label,
        system_summary=_compact_system_summary(protocol_system.summarize()) if protocol_system is not None else {},
        training_context_codes=training_context_codes,
        context_mode=config.context_mode,
    )


def run_model_inputs_real_experiment(config: ModelInputsRealConfig) -> dict[str, object]:
    eval_mode = _normalize_eval_mode(config.eval_mode)
    scenario_splits = select_scenario_splits(config)
    feature_stats = build_feature_stats(config.input_path, scenario_splits["train"])
    context_profile = build_context_profile(config.input_path, scenario_splits["train"])
    feature_names = _feature_names_from_stats(feature_stats)
    majority_label = _majority_label_from_training(
        config.input_path,
        scenario_splits["train"],
        feature_stats=feature_stats,
        normalize_features=config.normalize_features,
        positive_delta_threshold=config.positive_delta_threshold,
    )

    train_system = build_model_inputs_system(config, feature_names=feature_names)
    train_results: list[dict[str, object]] = []
    train_episodes_by_scenario: list[list[ModelInputsEpisode]] = []
    train_ids = set(int(scenario_id) for scenario_id in scenario_splits["train"])
    eval_ids = set(int(scenario_id) for scenario_id in scenario_splits["eval"])

    for scenario_id, rows in _iter_scenario_rows(config.input_path):
        if scenario_id not in train_ids:
            continue
        episodes = build_episodes_for_scenario(
            rows,
            feature_stats=feature_stats,
            normalize_features=config.normalize_features,
            positive_delta_threshold=config.positive_delta_threshold,
            context_profile=context_profile,
        )
        episodes = _limit_episodes(episodes, config.max_train_episodes_per_scenario)
        train_episodes_by_scenario.append(list(episodes))
        context_codes = _context_codes_for_scenario(
            episodes,
            context_mode=config.context_mode,
            context_profile=context_profile,
        )
        for episode, context_code in zip(episodes, context_codes):
            train_results.append(
                run_episode(
                    train_system,
                    episode,
                    config=config,
                    training=True,
                    default_prediction=majority_label,
                    context_code=context_code,
                )
            )

    trained_system_summary = _compact_system_summary(train_system.summarize())
    training_context_codes = _collect_context_codes(
        train_episodes_by_scenario,
        context_mode=config.context_mode,
        context_profile=context_profile,
    )

    carryover_root = Path(__file__).resolve().parents[1] / "tests_tmp"
    carryover_dir = carryover_root / f"model_inputs_real_v1_{uuid4().hex}"
    try:
        carryover_root.mkdir(parents=True, exist_ok=True)
        train_system.save_carryover(carryover_dir)
        eval_protocols = (
            [EVAL_FRESH, EVAL_PERSISTENT]
            if eval_mode == EVAL_BOTH
            else [eval_mode]
        )
        protocol_payloads = {
            protocol_name: _run_eval_protocol(
                protocol_name=protocol_name,
                config=config,
                input_path=config.input_path,
                eval_ids=eval_ids,
                feature_stats=feature_stats,
                feature_names=feature_names,
                majority_label=majority_label,
                carryover_dir=carryover_dir,
                context_profile=context_profile,
                training_context_codes=training_context_codes,
            )
            for protocol_name in eval_protocols
        }
    finally:
        if carryover_dir.exists():
            shutil.rmtree(carryover_dir, ignore_errors=True)
    primary_eval_mode = EVAL_FRESH if eval_mode == EVAL_BOTH else eval_mode
    primary_eval = protocol_payloads[primary_eval_mode]

    result = {
        "config": asdict(config),
        "scenario_inventory": {
            "total_scenarios": len(scenario_splits["all"]),
            "train_scenarios": list(scenario_splits["train"]),
            "eval_scenarios": list(scenario_splits["eval"]),
        },
        "feature_names": feature_names,
        "feature_stats": {
            feature_name: {
                "count": stats.count,
                "mean": round(stats.mean, 6),
                "std": round(stats.std, 6),
            }
            for feature_name, stats in feature_stats.items()
        },
        "context_profile": asdict(context_profile),
        "training_context_codes": sorted(training_context_codes),
        "majority_label": int(majority_label),
        "train_episode_count": len(train_results),
        "eval_episode_count": int(primary_eval["eval_episode_count"]),
        "train_summary": summarize_episode_results(train_results),
        "primary_eval_mode": primary_eval_mode,
        "eval_summary": primary_eval["eval_summary"],
        "eval_baselines": primary_eval["eval_baselines"],
        "eval_accuracy_deltas": primary_eval["eval_accuracy_deltas"],
        "eval_protocols": {
            name: {
                "protocol_name": payload["protocol_name"],
                "eval_episode_count": payload["eval_episode_count"],
                "eval_summary": payload["eval_summary"],
                "eval_baselines": payload["eval_baselines"],
                "eval_accuracy_deltas": payload["eval_accuracy_deltas"],
                "context_probe": payload["context_probe"],
                "system_summary": payload["system_summary"],
            }
            for name, payload in protocol_payloads.items()
        },
        "trained_system_summary": trained_system_summary,
        "topology_mode": config.topology_mode,
        "local_unit_mode": config.local_unit_mode,
        "local_unit_preset": config.local_unit_preset,
        "context_mode": config.context_mode,
    }
    result["eval_system_summary"] = primary_eval["system_summary"]
    result["eval_context_probe"] = primary_eval["context_probe"]
    if not config.summary_only:
        result["train_results"] = train_results
        result["eval_results"] = primary_eval["results"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run a first-pass REAL harness on model_inputs by predicting whether "
            "the next result value increases."
        )
    )
    parser.add_argument(
        "--input-path",
        default=str(DEFAULT_INPUT_PATH),
        help="CSV file or chunk directory produced from model_inputs.csv",
    )
    parser.add_argument(
        "--train-fraction",
        type=float,
        default=0.7,
        help="Fraction of scenarios to use for training",
    )
    parser.add_argument(
        "--selector-seed",
        type=int,
        default=13,
        help="Selector seed for the REAL substrate",
    )
    parser.add_argument(
        "--max-train-scenarios",
        type=int,
        default=None,
        help="Optional cap on the number of train scenarios",
    )
    parser.add_argument(
        "--max-eval-scenarios",
        type=int,
        default=None,
        help="Optional cap on the number of eval scenarios",
    )
    parser.add_argument(
        "--max-train-episodes-per-scenario",
        type=int,
        default=None,
        help="Optional cap on train episodes within each scenario",
    )
    parser.add_argument(
        "--max-eval-episodes-per-scenario",
        type=int,
        default=None,
        help="Optional cap on eval episodes within each scenario",
    )
    parser.add_argument(
        "--positive-delta-threshold",
        type=float,
        default=0.0,
        help="Threshold above which the next result delta is treated as positive",
    )
    parser.add_argument(
        "--eval-feedback-fraction",
        type=float,
        default=1.0,
        help="Fraction of feedback kept active during evaluation runs",
    )
    parser.add_argument(
        "--topology-mode",
        choices=(TOPOLOGY_LEGACY, TOPOLOGY_BOUNDED_OVERLAP, TOPOLOGY_MULTIHOP),
        default=TOPOLOGY_LEGACY,
        help="Routing topology for the model-input harness",
    )
    parser.add_argument(
        "--local-unit-mode",
        choices=(LOCAL_UNIT_LEGACY, LOCAL_UNIT_PULSE),
        default=LOCAL_UNIT_LEGACY,
        help="Use legacy nodes or the pulse local-unit path",
    )
    parser.add_argument(
        "--local-unit-preset",
        default=DEFAULT_LOCAL_UNIT_PRESET,
        help="Pulse local-unit preset name",
    )
    parser.add_argument(
        "--eval-mode",
        choices=("fresh", "persistent", "both", EVAL_FRESH, EVAL_PERSISTENT, EVAL_BOTH),
        default=EVAL_FRESH,
        help="Fresh clones carryover per eval scenario, persistent keeps one warm system, both runs both protocols",
    )
    parser.add_argument(
        "--context-mode",
        choices=(CONTEXT_LATENT, CONTEXT_OFFLINE, CONTEXT_ONLINE),
        default=CONTEXT_ONLINE,
        help="Latent disables explicit context bits, offline reuses one scenario code, online updates a running context code within each scenario",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Omit per-episode payloads from the JSON output",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Optional JSON output path",
    )
    args = parser.parse_args()

    config = ModelInputsRealConfig(
        input_path=str(args.input_path),
        train_fraction=float(args.train_fraction),
        selector_seed=int(args.selector_seed),
        eval_feedback_fraction=float(args.eval_feedback_fraction),
        positive_delta_threshold=float(args.positive_delta_threshold),
        max_train_scenarios=args.max_train_scenarios,
        max_eval_scenarios=args.max_eval_scenarios,
        max_train_episodes_per_scenario=args.max_train_episodes_per_scenario,
        max_eval_episodes_per_scenario=args.max_eval_episodes_per_scenario,
        topology_mode=str(args.topology_mode),
        local_unit_mode=str(args.local_unit_mode),
        local_unit_preset=str(args.local_unit_preset),
        eval_mode=str(args.eval_mode),
        context_mode=str(args.context_mode),
        summary_only=bool(args.summary_only),
    )
    result = run_model_inputs_real_experiment(config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "train_episode_count": result["train_episode_count"],
                "eval_episode_count": result["eval_episode_count"],
                "primary_eval_mode": result["primary_eval_mode"],
                "eval_accuracy": result["eval_summary"]["metrics"]["accuracy"],
                "eval_accuracy_delta_vs_majority": result["eval_accuracy_deltas"]["vs_majority_label"],
                "eval_accuracy_delta_vs_repeat_delta": result["eval_accuracy_deltas"]["vs_repeat_last_delta_direction"],
                "topology_mode": result["topology_mode"],
                "local_unit_mode": result["local_unit_mode"],
                "local_unit_preset": result["local_unit_preset"],
                "context_mode": result["context_mode"],
                "output": str(args.output),
            },
            indent=2,
        )
    )


__all__ = [
    "DECISION_DOWN",
    "DECISION_UP",
    "ModelInputsEpisode",
    "ModelInputsPacketSpec",
    "ModelInputsContextProfile",
    "ModelInputsRealConfig",
    "ModelInputsRowSummary",
    "build_episodes_for_scenario",
    "build_context_profile",
    "build_feature_stats",
    "discover_scenario_ids",
    "run_episode",
    "run_model_inputs_real_experiment",
    "select_scenario_splits",
    "summarize_model_inputs_row",
    "TOPOLOGY_MULTIHOP",
]


if __name__ == "__main__":
    main()
