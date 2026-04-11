from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean
from typing import Iterable, Sequence

from occupancy_baseline import build_windowed_dataset, evaluate_binary_predictions, load_csv_dataset
from occupancy_baseline.experiment import _split_index
from phase8 import FeedbackPulse, NativeSubstrateSystem
from phase8.models import SignalPacket


DECISION_EMPTY = "decision_empty"
DECISION_OCCUPIED = "decision_occupied"
FEATURE_SOURCE_IDS = {
    "temperature": "sensor_temperature",
    "humidity": "sensor_humidity",
    "light": "sensor_light",
    "co2": "sensor_co2",
    "humidity_ratio": "sensor_humidity_ratio",
}
VALUE_BIN_THRESHOLDS = (-0.75, 0.0, 0.75)
DEFAULT_SELECTOR_SEEDS = (13, 23, 37, 51, 79)


@dataclass(frozen=True)
class OccupancyRealConfig:
    csv_path: str
    window_size: int = 5
    train_fraction: float = 0.8
    normalize: bool = True
    selector_seed: int = 0
    feedback_amount: float = 0.18
    packet_ttl: int = 8
    timestep_drain_cycles: int = 8
    forward_drain_cycles: int = 16
    feedback_drain_cycles: int = 4
    max_train_episodes: int | None = None
    max_eval_episodes: int | None = None
    summary_only: bool = False


@dataclass(frozen=True)
class OccupancyPacketSpec:
    source_node_id: str
    feature_name: str
    timestep_offset: int
    normalized_value: float
    input_bits: tuple[int, ...]


@dataclass(frozen=True)
class OccupancyEpisode:
    episode_index: int
    label: int
    packets: tuple[OccupancyPacketSpec, ...]


def occupancy_topology() -> tuple[dict[str, tuple[str, ...]], dict[str, int], str, str]:
    adjacency: dict[str, tuple[str, ...]] = {
        "sensor_hub": (),
        "sensor_temperature": (DECISION_EMPTY, DECISION_OCCUPIED),
        "sensor_humidity": (DECISION_EMPTY, DECISION_OCCUPIED),
        "sensor_light": (DECISION_EMPTY, DECISION_OCCUPIED),
        "sensor_co2": (DECISION_EMPTY, DECISION_OCCUPIED),
        "sensor_humidity_ratio": (DECISION_EMPTY, DECISION_OCCUPIED),
        DECISION_EMPTY: ("sink",),
        DECISION_OCCUPIED: ("sink",),
        "sink": (),
    }
    positions = {
        "sensor_hub": 0,
        "sensor_temperature": 0,
        "sensor_humidity": 0,
        "sensor_light": 0,
        "sensor_co2": 0,
        "sensor_humidity_ratio": 0,
        DECISION_EMPTY: 1,
        DECISION_OCCUPIED: 1,
        "sink": 2,
    }
    return adjacency, positions, "sensor_hub", "sink"


def build_occupancy_system(config: OccupancyRealConfig) -> NativeSubstrateSystem:
    adjacency, positions, source_id, sink_id = occupancy_topology()
    return NativeSubstrateSystem(
        adjacency=adjacency,
        positions=positions,
        source_id=source_id,
        sink_id=sink_id,
        selector_seed=config.selector_seed,
        packet_ttl=config.packet_ttl,
    )


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


def _select_eval_preview(
    episodes: Sequence[OccupancyEpisode],
    *,
    per_label: int,
) -> tuple[OccupancyEpisode, ...]:
    if per_label <= 0:
        raise ValueError("eval_preview_per_label must be positive when provided")
    selected_by_label: dict[int, list[OccupancyEpisode]] = {
        0: [],
        1: [],
    }
    for episode in episodes:
        label = int(episode.label)
        if label not in selected_by_label:
            continue
        if len(selected_by_label[label]) >= per_label:
            continue
        selected_by_label[label].append(episode)
        if all(len(bucket) >= per_label for bucket in selected_by_label.values()):
            break
    selected_episode_indexes = {
        episode.episode_index
        for bucket in selected_by_label.values()
        for episode in bucket
    }
    return tuple(
        episode
        for episode in episodes
        if episode.episode_index in selected_episode_indexes
    )


def load_occupancy_episodes(config: OccupancyRealConfig) -> dict[str, object]:
    dataset = load_csv_dataset(config.csv_path, normalize=config.normalize)
    windowed = build_windowed_dataset(
        dataset,
        window_size=config.window_size,
        flatten=False,
    )
    episodes: list[OccupancyEpisode] = []
    feature_names = tuple(str(name) for name in dataset.feature_names)
    for episode_index, (window, label) in enumerate(zip(windowed.features, windowed.labels)):
        packet_specs: list[OccupancyPacketSpec] = []
        rows = tuple(tuple(float(value) for value in row) for row in window)
        for timestep_index, row in enumerate(rows):
            timestep_offset = config.window_size - timestep_index - 1
            for feature_name, value in zip(feature_names, row):
                packet_specs.append(
                    OccupancyPacketSpec(
                        source_node_id=FEATURE_SOURCE_IDS[feature_name],
                        feature_name=feature_name,
                        timestep_offset=timestep_offset,
                        normalized_value=float(value),
                        input_bits=_bucket_to_bits(float(value)),
                    )
                )
        episodes.append(
            OccupancyEpisode(
                episode_index=episode_index,
                label=int(label),
                packets=tuple(packet_specs),
            )
        )
    split_index = _split_index(len(episodes), config.train_fraction)
    train_episodes = episodes[:split_index]
    eval_episodes = episodes[split_index:]
    full_eval_label_counts = {
        0: sum(1 for episode in eval_episodes if int(episode.label) == 0),
        1: sum(1 for episode in eval_episodes if int(episode.label) == 1),
    }
    if config.max_train_episodes is not None:
        train_episodes = train_episodes[: config.max_train_episodes]
    eval_selection = "tail"
    if config.eval_preview_per_label is not None:
        eval_episodes = list(
            _select_eval_preview(
                eval_episodes,
                per_label=config.eval_preview_per_label,
            )
        )
        eval_selection = "per_label_preview"
    if config.max_eval_episodes is not None:
        eval_episodes = eval_episodes[: config.max_eval_episodes]
    selected_eval_label_counts = {
        0: sum(1 for episode in eval_episodes if int(episode.label) == 0),
        1: sum(1 for episode in eval_episodes if int(episode.label) == 1),
    }
    return {
        "dataset_rows": dataset.size,
        "windowed_examples": len(episodes),
        "input_dim": windowed.input_dim,
        "train_episodes": tuple(train_episodes),
        "eval_episodes": tuple(eval_episodes),
        "eval_selection": eval_selection,
        "full_eval_label_counts": full_eval_label_counts,
        "selected_eval_label_counts": selected_eval_label_counts,
    }


def _direct_inject_packet(
    system: NativeSubstrateSystem,
    packet_spec: OccupancyPacketSpec,
) -> SignalPacket:
    packet = system.environment.create_packet(
        cycle=system.global_cycle,
        input_bits=packet_spec.input_bits,
        payload_bits=packet_spec.input_bits,
    )
    packet.origin = packet_spec.source_node_id
    system.environment.inboxes[packet_spec.source_node_id].append(packet)
    system.environment.total_injected += 1
    return packet


def _decision_node_for_packet(packet: SignalPacket) -> str | None:
    if not packet.edge_path:
        return None
    source_id, _, _ = packet.edge_path[-1].partition("->")
    return source_id or None


def _expected_decision_node(label: int) -> str:
    return DECISION_OCCUPIED if int(label) == 1 else DECISION_EMPTY


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


def _packets_by_id(packets: Iterable[SignalPacket]) -> dict[str, SignalPacket]:
    return {packet.packet_id: packet for packet in packets}


def _episode_batches(episode: OccupancyEpisode) -> tuple[tuple[OccupancyPacketSpec, ...], ...]:
    grouped: dict[int, list[OccupancyPacketSpec]] = {}
    for packet_spec in episode.packets:
        grouped.setdefault(int(packet_spec.timestep_offset), []).append(packet_spec)
    return tuple(
        tuple(grouped[timestep_offset])
        for timestep_offset in sorted(grouped.keys(), reverse=True)
    )


def run_episode(
    system: NativeSubstrateSystem,
    episode: OccupancyEpisode,
    *,
    config: OccupancyRealConfig,
    training: bool,
) -> dict[str, object]:
    packet_ids: list[str] = []
    original_feedback_amount = system.environment.feedback_amount
    system.environment.feedback_amount = 0.0

    for batch in _episode_batches(episode):
        batch_packet_ids: set[str] = set()
        for packet_spec in batch:
            packet = _direct_inject_packet(system, packet_spec)
            packet_ids.append(packet.packet_id)
            batch_packet_ids.add(packet.packet_id)
        for _ in range(max(1, config.timestep_drain_cycles)):
            if _episode_resolved(system, batch_packet_ids):
                break
            system.run_global_cycle()

    packet_id_set = set(packet_ids)
    for _ in range(config.forward_drain_cycles):
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
        DECISION_EMPTY: 0,
        DECISION_OCCUPIED: 0,
    }
    target_decision = _expected_decision_node(episode.label)
    for packet in delivered_packets:
        decision_node = _decision_node_for_packet(packet)
        if decision_node in decision_counts:
            decision_counts[decision_node] += 1
        packet.feedback_award = 0.0
        packet.matched_target = decision_node == target_decision
        packet.bit_match_ratio = 1.0 if decision_node == target_decision else 0.0

    occupied_votes = decision_counts[DECISION_OCCUPIED]
    empty_votes = decision_counts[DECISION_EMPTY]
    predicted_label = 1 if occupied_votes > empty_votes else 0
    decision_margin = abs(occupied_votes - empty_votes)
    delivered_count = len(delivered_packets)
    correct_packet_count = decision_counts[target_decision]

    feedback_event_count = 0
    feedback_total = 0.0
    if training and delivered_packets:
        system.environment.feedback_amount = config.feedback_amount
        pulses: list[FeedbackPulse] = []
        for packet in delivered_packets:
            if not packet.matched_target:
                continue
            pulses.append(
                FeedbackPulse(
                    packet_id=packet.packet_id,
                    edge_path=list(packet.edge_path),
                    amount=config.feedback_amount,
                    transform_path=list(packet.transform_trace),
                    bit_match_ratio=1.0,
                    matched_target=True,
                )
            )
            packet.feedback_award = config.feedback_amount
        system.environment.pending_feedback.extend(pulses)
        feedback_event_count = len(pulses)
        feedback_total = round(len(pulses) * config.feedback_amount, 4)
        for _ in range(config.feedback_drain_cycles):
            if not system.environment.pending_feedback:
                break
            system.run_global_cycle()
    else:
        system.environment.feedback_amount = original_feedback_amount

    system.environment.feedback_amount = original_feedback_amount
    return {
        "episode_index": episode.episode_index,
        "label": int(episode.label),
        "prediction": int(predicted_label),
        "correct": bool(predicted_label == episode.label and delivered_count > 0),
        "packet_count": len(episode.packets),
        "delivered_packets": delivered_count,
        "dropped_packets": len(dropped_packets),
        "decision_counts": dict(decision_counts),
        "decision_margin": int(decision_margin),
        "prediction_confidence": round(
            decision_margin / max(delivered_count, 1),
            4,
        ),
        "target_decision": target_decision,
        "correct_packet_count": int(correct_packet_count),
        "feedback_event_count": int(feedback_event_count),
        "feedback_total": float(feedback_total),
    }


def summarize_episode_results(results: Sequence[dict[str, object]]) -> dict[str, object]:
    labels = [int(result["label"]) for result in results]
    predictions = [int(result["prediction"]) for result in results]
    metrics = evaluate_binary_predictions(labels, predictions) if results else evaluate_binary_predictions([0], [0])
    if not results:
        metrics.update({"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0})
        metrics["tp"] = 0.0
        metrics["tn"] = 0.0
        metrics["fp"] = 0.0
        metrics["fn"] = 0.0
    return {
        "episode_count": len(results),
        "metrics": metrics,
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
        "mean_feedback_total": round(
            mean(float(result["feedback_total"]) for result in results),
            4,
        )
        if results
        else 0.0,
        "occupied_prediction_rate": round(
            sum(1 for result in results if int(result["prediction"]) == 1) / max(len(results), 1),
            4,
        ),
    }


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


def run_occupancy_real_experiment(config: OccupancyRealConfig) -> dict[str, object]:
    episode_payload = load_occupancy_episodes(config)
    system = build_occupancy_system(config)
    train_episodes = tuple(episode_payload["train_episodes"])
    eval_episodes = tuple(episode_payload["eval_episodes"])

    train_results = [
        run_episode(system, episode, config=config, training=True)
        for episode in train_episodes
    ]
    eval_results = [
        run_episode(system, episode, config=config, training=False)
        for episode in eval_episodes
    ]

    adjacency, positions, source_id, sink_id = occupancy_topology()
    result = {
        "config": asdict(config),
        "dataset_rows": int(episode_payload["dataset_rows"]),
        "windowed_examples": int(episode_payload["windowed_examples"]),
        "input_dim": int(episode_payload["input_dim"]),
        "train_episode_count": len(train_results),
        "eval_episode_count": len(eval_results),
        "eval_selection": str(episode_payload["eval_selection"]),
        "full_eval_label_counts": dict(episode_payload["full_eval_label_counts"]),
        "selected_eval_label_counts": dict(episode_payload["selected_eval_label_counts"]),
        "eval_episode_indices": [int(result["episode_index"]) for result in eval_results],
        "topology": {
            "adjacency": adjacency,
            "positions": positions,
            "source_id": source_id,
            "sink_id": sink_id,
        },
        "train_summary": summarize_episode_results(train_results),
        "eval_summary": summarize_episode_results(eval_results),
        "system_summary": _compact_system_summary(system.summarize()),
    }
    if not config.summary_only:
        result["train_results"] = train_results
        result["eval_results"] = eval_results
    return result


__all__ = [
    "DECISION_EMPTY",
    "DECISION_OCCUPIED",
    "DEFAULT_SELECTOR_SEEDS",
    "OccupancyEpisode",
    "OccupancyPacketSpec",
    "OccupancyRealConfig",
    "build_occupancy_system",
    "load_occupancy_episodes",
    "occupancy_topology",
    "run_episode",
    "run_occupancy_real_experiment",
    "summarize_episode_results",
]
