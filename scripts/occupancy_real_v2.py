"""
occupancy_real_v2.py
--------------------
Redesigned REAL occupancy runner that addresses three structural mismatches
from the original occupancy_real.py:

  1. Feedback disabled during eval → ATP starvation, packet delivery collapse
     Fix: eval_feedback_fraction controls how much feedback runs during eval
          (default 1.0 = full feedback, same as training)

  2. No carryover eval mode
     Fix: carryover_mode="fresh_eval" saves substrate after training and
          evaluates in a fresh system loaded from that carryover, cleanly
          isolating what the substrate accumulated

  3. No context bit → latent context mechanism never activates
     Fix: context_bit_source="class"    → label as context (oracle upper bound)
          context_bit_source="co2_high" → CO2-derived context (realistic proxy)
          context_bit_source="none"     → v1 behaviour, no context
"""
from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable, Sequence

from occupancy_baseline import build_windowed_dataset, evaluate_binary_predictions, load_csv_dataset
from occupancy_baseline.experiment import _split_index
from phase8 import FeedbackPulse, NativeSubstrateSystem
from phase8.models import SignalPacket

from .occupancy_real import (
    DECISION_EMPTY,
    DECISION_OCCUPIED,
    FEATURE_SOURCE_IDS,
    VALUE_BIN_THRESHOLDS,
    OccupancyEpisode,
    OccupancyPacketSpec,
    occupancy_topology,
    _compact_system_summary,
    _direct_inject_packet,
    _episode_batches,
    _episode_resolved,
    _expected_decision_node,
    _packets_by_id,
    _decision_node_for_packet,
    summarize_episode_results,
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OccupancyRealV2Config:
    csv_path: str
    window_size: int = 5
    train_fraction: float = 0.8
    normalize: bool = True
    selector_seed: int = 13

    feedback_amount: float = 0.18
    eval_feedback_fraction: float = 1.0   # 1.0 = full feedback in eval, 0.0 = v1 (no feedback)

    packet_ttl: int = 8
    forward_drain_cycles: int = 16
    feedback_drain_cycles: int = 4

    # "continuous"  → same system for train + eval (substrate naturally carries)
    # "fresh_eval"  → save substrate after training, eval in a fresh system
    carryover_mode: str = "continuous"

    # "none"     → no context bit (v1 behaviour)
    # "class"    → context_bit = episode label (oracle upper bound)
    # "co2_high" → context_bit = 1 if mean window CO2 > training median
    context_bit_source: str = "none"

    max_train_episodes: int | None = None
    max_eval_episodes: int | None = None
    summary_only: bool = False


# ---------------------------------------------------------------------------
# Context bit derivation
# ---------------------------------------------------------------------------

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


def _mean_co2_for_episode(episode: OccupancyEpisode) -> float:
    co2_values = [
        spec.normalized_value
        for spec in episode.packets
        if spec.feature_name == "co2"
    ]
    return mean(co2_values) if co2_values else 0.0


def compute_co2_training_median(train_episodes: Sequence[OccupancyEpisode]) -> float:
    """Compute the median mean-CO2 value across all training episodes."""
    values = sorted(_mean_co2_for_episode(ep) for ep in train_episodes)
    n = len(values)
    if n == 0:
        return 0.0
    if n % 2 == 1:
        return values[n // 2]
    return (values[n // 2 - 1] + values[n // 2]) / 2.0


def context_bit_for_episode(
    episode: OccupancyEpisode,
    config: OccupancyRealV2Config,
    co2_median: float = 0.0,
) -> int | None:
    if config.context_bit_source == "none":
        return None
    if config.context_bit_source == "class":
        return int(episode.label)
    if config.context_bit_source == "co2_high":
        return 1 if _mean_co2_for_episode(episode) > co2_median else 0
    return None


# ---------------------------------------------------------------------------
# Episode loader (reuses v1 windowing, adds feature_name pass-through)
# ---------------------------------------------------------------------------

def load_occupancy_episodes_v2(config: OccupancyRealV2Config) -> dict[str, object]:
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
    if config.max_train_episodes is not None:
        train_episodes = train_episodes[: config.max_train_episodes]
    if config.max_eval_episodes is not None:
        eval_episodes = eval_episodes[: config.max_eval_episodes]

    return {
        "dataset_rows": dataset.size,
        "windowed_examples": len(episodes),
        "input_dim": windowed.input_dim,
        "train_episodes": tuple(train_episodes),
        "eval_episodes": tuple(eval_episodes),
    }


# ---------------------------------------------------------------------------
# Episode runner (v2 — feedback-aware, context-aware)
# ---------------------------------------------------------------------------

def run_episode_v2(
    system: NativeSubstrateSystem,
    episode: OccupancyEpisode,
    *,
    config: OccupancyRealV2Config,
    training: bool,
    context_bit: int | None = None,
) -> dict[str, object]:
    """
    Run a single episode through the substrate.

    Key differences from run_episode (v1):
      - eval_feedback_fraction: eval episodes receive feedback proportional to
        eval_feedback_fraction * feedback_amount instead of none
      - context_bit: optional integer context bit injected into each packet's
        metadata. When present, the substrate's latent context machinery
        activates context-indexed action supports.
    """
    packet_ids: list[str] = []
    original_feedback_amount = system.environment.feedback_amount
    active_feedback_amount = (
        config.feedback_amount
        if training
        else config.feedback_amount * config.eval_feedback_fraction
    )
    system.environment.feedback_amount = 0.0  # start suppressed; set during feedback phase

    for batch in _episode_batches(episode):
        batch_packet_ids: set[str] = set()
        for packet_spec in batch:
            packet = _direct_inject_packet(system, packet_spec)
            # Attach context bit to packet if present so nodes can observe it
            if context_bit is not None:
                if hasattr(packet, "context_bit"):
                    packet.context_bit = context_bit
                if hasattr(packet, "metadata") and isinstance(packet.metadata, dict):
                    packet.metadata["context_bit"] = context_bit
            packet_ids.append(packet.packet_id)
            batch_packet_ids.add(packet.packet_id)
        for _ in range(max(1, 8)):
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
        delivered_by_id[pid]
        for pid in packet_ids
        if pid in delivered_by_id
    ]
    dropped_packets = [
        dropped_by_id[pid]
        for pid in packet_ids
        if pid in dropped_by_id
    ]

    decision_counts = {DECISION_EMPTY: 0, DECISION_OCCUPIED: 0}
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

    # ------------------------------------------------------------------
    # Feedback phase — runs for both training AND eval (at scaled amount)
    # ------------------------------------------------------------------
    feedback_event_count = 0
    feedback_total = 0.0
    if active_feedback_amount > 0.0 and delivered_packets:
        system.environment.feedback_amount = active_feedback_amount
        pulses: list[FeedbackPulse] = []
        for packet in delivered_packets:
            if not packet.matched_target:
                continue
            pulse_kwargs: dict[str, object] = dict(
                packet_id=packet.packet_id,
                edge_path=list(packet.edge_path),
                amount=active_feedback_amount,
                transform_path=list(packet.transform_trace),
                bit_match_ratio=1.0,
                matched_target=True,
            )
            # Pass context_bit into the feedback pulse so node absorb_feedback
            # can index context-specific action supports
            if context_bit is not None:
                pulse_kwargs["context_bit"] = context_bit
            pulses.append(FeedbackPulse(**pulse_kwargs))
            packet.feedback_award = active_feedback_amount
        system.environment.pending_feedback.extend(pulses)
        feedback_event_count = len(pulses)
        feedback_total = round(len(pulses) * active_feedback_amount, 4)
        for _ in range(config.feedback_drain_cycles):
            if not system.environment.pending_feedback:
                break
            system.run_global_cycle()

    system.environment.feedback_amount = original_feedback_amount

    return {
        "episode_index": episode.episode_index,
        "label": int(episode.label),
        "prediction": int(predicted_label),
        "correct": bool(predicted_label == episode.label and delivered_count > 0),
        "context_bit": context_bit,
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
    }


# ---------------------------------------------------------------------------
# System builder
# ---------------------------------------------------------------------------

def build_occupancy_system_v2(config: OccupancyRealV2Config) -> NativeSubstrateSystem:
    adjacency, positions, source_id, sink_id = occupancy_topology()
    return NativeSubstrateSystem(
        adjacency=adjacency,
        positions=positions,
        source_id=source_id,
        sink_id=sink_id,
        selector_seed=config.selector_seed,
        packet_ttl=config.packet_ttl,
    )


# ---------------------------------------------------------------------------
# Full experiment runner
# ---------------------------------------------------------------------------

def run_occupancy_real_v2_experiment(config: OccupancyRealV2Config) -> dict[str, object]:
    episode_payload = load_occupancy_episodes_v2(config)
    train_episodes = tuple(episode_payload["train_episodes"])
    eval_episodes = tuple(episode_payload["eval_episodes"])

    # Compute CO2 median from training set (used only if context_bit_source="co2_high")
    co2_median = compute_co2_training_median(train_episodes)

    # ---- Training ----
    train_system = build_occupancy_system_v2(config)
    train_results = [
        run_episode_v2(
            train_system,
            episode,
            config=config,
            training=True,
            context_bit=context_bit_for_episode(episode, config, co2_median),
        )
        for episode in train_episodes
    ]

    # ---- Eval system prep ----
    if config.carryover_mode == "fresh_eval":
        carryover_dir = Path("tests_tmp") / "occupancy_v2_carryover"
        carryover_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(carryover_dir, ignore_errors=True)
        try:
            train_system.save_substrate_carryover(str(carryover_dir))
            eval_system = build_occupancy_system_v2(config)
            eval_system.load_substrate_carryover(str(carryover_dir))
        finally:
            shutil.rmtree(carryover_dir, ignore_errors=True)
    else:
        # "continuous" — same system, substrate already accumulated
        eval_system = train_system

    # ---- Evaluation ----
    eval_results = [
        run_episode_v2(
            eval_system,
            episode,
            config=config,
            training=False,
            context_bit=context_bit_for_episode(episode, config, co2_median),
        )
        for episode in eval_episodes
    ]

    adjacency, positions, source_id, sink_id = occupancy_topology()
    result = {
        "v2_config": asdict(config),
        "dataset_rows": int(episode_payload["dataset_rows"]),
        "windowed_examples": int(episode_payload["windowed_examples"]),
        "input_dim": int(episode_payload["input_dim"]),
        "train_episode_count": len(train_results),
        "eval_episode_count": len(eval_results),
        "topology": {
            "adjacency": adjacency,
            "positions": positions,
            "source_id": source_id,
            "sink_id": sink_id,
        },
        "co2_training_median": round(co2_median, 6),
        "train_summary": summarize_episode_results(train_results),
        "eval_summary": summarize_episode_results(eval_results),
        "system_summary": _compact_system_summary(eval_system.summarize()),
    }
    if not config.summary_only:
        result["train_results"] = train_results
        result["eval_results"] = eval_results
    return result


__all__ = [
    "OccupancyRealV2Config",
    "build_occupancy_system_v2",
    "compute_co2_training_median",
    "context_bit_for_episode",
    "load_occupancy_episodes_v2",
    "run_episode_v2",
    "run_occupancy_real_v2_experiment",
]
