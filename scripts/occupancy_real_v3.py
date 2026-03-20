"""
occupancy_real_v3.py
--------------------
REAL-native occupancy harness built around session orientation, explicit
carryover protocols, source-buffer admission, and context-sensitive routing.
"""
from __future__ import annotations

import shutil
import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from statistics import mean
from typing import NamedTuple, Sequence
from uuid import uuid4

from occupancy_baseline import build_windowed_dataset, load_csv_dataset
from occupancy_baseline.session_splitter import (
    OccupancySession,
    assign_context_codes,
    compute_training_medians,
    segment_into_sessions,
    session_inventory,
)
from phase8 import FeedbackPulse, NativeSubstrateSystem
from phase8.models import SignalPacket

from .occupancy_real import (
    DECISION_EMPTY,
    DECISION_OCCUPIED,
    FEATURE_SOURCE_IDS,
    VALUE_BIN_THRESHOLDS,
    OccupancyEpisode,
    OccupancyPacketSpec,
    _decision_node_for_packet,
    _direct_inject_packet,
    _episode_batches,
    _episode_resolved,
    _expected_decision_node,
    _packets_by_id,
    occupancy_topology,
    summarize_episode_results,
)


OCCUPANCY_TASK_ID = "occupancy_session"
EVAL_PERSISTENT = "persistent_eval"
EVAL_FRESH = "fresh_session_eval"
EVAL_BOTH = "both"
TOPOLOGY_FIXED = "fixed_small"
TOPOLOGY_MULTIHOP = "multihop_routing"
CONTEXT_OFFLINE = "offline_session_context"
CONTEXT_ONLINE = "online_running_context"
CONTEXT_LATENT = "latent_context"
INGRESS_ADMISSION = "admission_source"
INGRESS_DIRECT = "direct_injection"
AUTO_CPU_TARGET_FRACTION = 0.75


@dataclass(frozen=True)
class OccupancyRealV3Config:
    csv_path: str
    window_size: int = 5
    normalize: bool = True
    selector_seed: int = 13

    feedback_amount: float = 0.18
    eval_feedback_fraction: float = 1.0

    packet_ttl: int = 8
    forward_drain_cycles: int = 16
    feedback_drain_cycles: int = 4

    train_session_fraction: float = 0.7
    eval_mode: str = EVAL_FRESH
    topology_mode: str = TOPOLOGY_MULTIHOP
    context_mode: str = CONTEXT_ONLINE
    ingress_mode: str = INGRESS_ADMISSION

    max_train_sessions: int | None = None
    max_eval_sessions: int | None = None
    summary_only: bool = False


@dataclass(frozen=True)
class OccupancyRealV3SweepWorkerPlan:
    requested_workers: int | None
    auto_cpu_target_fraction: float
    worker_budget: int
    seed_workers: int
    eval_workers_per_seed: int
    effective_total_workers: int


def auto_worker_budget(cpu_fraction: float = AUTO_CPU_TARGET_FRACTION) -> int:
    cpu_total = max(1, os.cpu_count() or 1)
    return max(1, math.floor(cpu_total * cpu_fraction))


def auto_worker_count(task_count: int, cpu_fraction: float = AUTO_CPU_TARGET_FRACTION) -> int:
    if task_count <= 1:
        return 1
    requested = auto_worker_budget(cpu_fraction=cpu_fraction)
    return max(1, min(task_count, requested))


def _resolve_worker_count(workers: int | None, task_count: int) -> int:
    if task_count <= 1:
        return 1
    if workers is None or workers <= 0:
        return auto_worker_count(task_count)
    return max(1, min(int(workers), task_count))


def resolve_sweep_worker_plan(
    selector_seed_count: int,
    workers: int | None = None,
    *,
    cpu_fraction: float = AUTO_CPU_TARGET_FRACTION,
) -> OccupancyRealV3SweepWorkerPlan:
    if selector_seed_count <= 0:
        raise ValueError("selector_seed_count must be positive")

    cpu_total = max(1, os.cpu_count() or 1)
    if workers is None or workers <= 0:
        worker_budget = auto_worker_budget(cpu_fraction=cpu_fraction)
    else:
        worker_budget = max(1, min(int(workers), cpu_total))

    seed_workers = max(1, min(selector_seed_count, worker_budget))
    eval_workers_per_seed = max(1, worker_budget // seed_workers)
    return OccupancyRealV3SweepWorkerPlan(
        requested_workers=workers,
        auto_cpu_target_fraction=cpu_fraction,
        worker_budget=worker_budget,
        seed_workers=seed_workers,
        eval_workers_per_seed=eval_workers_per_seed,
        effective_total_workers=seed_workers * eval_workers_per_seed,
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


def load_all_episodes_v3(config: OccupancyRealV3Config) -> list[OccupancyEpisode]:
    dataset = load_csv_dataset(config.csv_path, normalize=config.normalize)
    windowed = build_windowed_dataset(
        dataset,
        window_size=config.window_size,
        flatten=False,
    )
    feature_names = tuple(str(name) for name in dataset.feature_names)
    episodes: list[OccupancyEpisode] = []
    for episode_index, (window, label) in enumerate(zip(windowed.features, windowed.labels)):
        packet_specs: list[OccupancyPacketSpec] = []
        rows = tuple(tuple(float(v) for v in row) for row in window)
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
    return episodes


def _multihop_occupancy_topology() -> tuple[dict[str, tuple[str, ...]], dict[str, int], str, str]:
    adjacency: dict[str, tuple[str, ...]] = {
        "sensor_hub": (),
        "sensor_temperature": ("relay_climate", "relay_shared"),
        "sensor_humidity": ("relay_climate", "relay_shared"),
        "sensor_light": ("relay_light", "relay_shared"),
        "sensor_co2": ("relay_air", "relay_shared"),
        "sensor_humidity_ratio": ("relay_climate", "relay_air"),
        "relay_climate": ("integrator_empty", "integrator_occupied"),
        "relay_air": ("integrator_empty", "integrator_occupied"),
        "relay_light": ("integrator_empty", "integrator_occupied"),
        "relay_shared": ("integrator_empty", "integrator_occupied"),
        "integrator_empty": (DECISION_EMPTY, DECISION_OCCUPIED),
        "integrator_occupied": (DECISION_EMPTY, DECISION_OCCUPIED),
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
        "relay_climate": 1,
        "relay_air": 1,
        "relay_light": 1,
        "relay_shared": 1,
        "integrator_empty": 2,
        "integrator_occupied": 2,
        DECISION_EMPTY: 3,
        DECISION_OCCUPIED: 3,
        "sink": 4,
    }
    return adjacency, positions, "sensor_hub", "sink"


def occupancy_topology_v3(topology_mode: str) -> tuple[dict[str, tuple[str, ...]], dict[str, int], str, str]:
    if topology_mode == TOPOLOGY_FIXED:
        return occupancy_topology()
    if topology_mode == TOPOLOGY_MULTIHOP:
        return _multihop_occupancy_topology()
    raise ValueError(f"Unsupported topology_mode: {topology_mode}")


def build_v3_system(config: OccupancyRealV3Config) -> NativeSubstrateSystem:
    adjacency, positions, source_id, sink_id = occupancy_topology_v3(config.topology_mode)
    return NativeSubstrateSystem(
        adjacency=adjacency,
        positions=positions,
        source_id=source_id,
        sink_id=sink_id,
        selector_seed=config.selector_seed,
        packet_ttl=config.packet_ttl,
    )


def _mean_feature_for_episode(episode: OccupancyEpisode, feature_name: str) -> float:
    values = [
        spec.normalized_value
        for spec in episode.packets
        if spec.feature_name == feature_name
    ]
    return mean(values) if values else 0.0


def _context_code_from_means(co2_mean: float, light_mean: float, co2_median: float, light_median: float) -> int:
    co2_bit = 1 if co2_mean > co2_median else 0
    light_bit = 1 if light_mean > light_median else 0
    return co2_bit * 2 + light_bit


def _context_codes_for_session(
    session: OccupancySession,
    *,
    context_mode: str,
    co2_median: float,
    light_median: float,
) -> list[int | None]:
    if context_mode == CONTEXT_LATENT:
        return [None for _ in session.episodes]
    if context_mode == CONTEXT_OFFLINE:
        code = int(session.context_code) if session.context_code >= 0 else None
        return [code for _ in session.episodes]
    if context_mode != CONTEXT_ONLINE:
        raise ValueError(f"Unsupported context_mode: {context_mode}")

    codes: list[int | None] = []
    running_co2: list[float] = []
    running_light: list[float] = []
    for episode in session.episodes:
        running_co2.append(_mean_feature_for_episode(episode, "co2"))
        running_light.append(_mean_feature_for_episode(episode, "light"))
        codes.append(
            _context_code_from_means(
                mean(running_co2),
                mean(running_light),
                co2_median,
                light_median,
            )
        )
    return codes


def _collect_context_codes(
    sessions: Sequence[OccupancySession],
    *,
    context_mode: str,
    co2_median: float,
    light_median: float,
) -> set[int]:
    codes: set[int] = set()
    for session in sessions:
        codes.update(
            int(code)
            for code in _context_codes_for_session(
                session,
                context_mode=context_mode,
                co2_median=co2_median,
                light_median=light_median,
            )
            if code is not None
        )
    return codes


def _summarize_episode_results_v3(results: Sequence[dict[str, object]]) -> dict[str, object]:
    summary = summarize_episode_results(results)
    delivery_ratios = [
        float(result["delivered_packets"]) / max(float(result["packet_count"]), 1.0)
        for result in results
    ]
    summary["mean_delivery_ratio"] = round(mean(delivery_ratios), 4) if delivery_ratios else 0.0
    summary["mean_prediction_confidence"] = round(
        mean(float(result["prediction_confidence"]) for result in results),
        4,
    ) if results else 0.0
    return summary


def _compact_v3_system_summary(summary: dict[str, object]) -> dict[str, object]:
    keys = (
        "capability_policy",
        "cycles",
        "injected_packets",
        "admitted_packets",
        "delivered_packets",
        "delivery_ratio",
        "dropped_packets",
        "drop_ratio",
        "source_buffer",
        "mean_latency",
        "mean_hops",
        "node_atp_total",
        "mean_route_cost",
        "mean_feedback_award",
        "mean_source_admission",
        "last_source_admission",
        "source_admission_support",
        "source_admission_velocity",
        "mean_source_efficiency",
        "exact_matches",
        "mean_bit_accuracy",
    )
    return {key: summary[key] for key in keys if key in summary}


def _aggregate_compact_system_summaries(summaries: Sequence[dict[str, object]]) -> dict[str, object]:
    if not summaries:
        return {}
    if len(summaries) == 1:
        return dict(summaries[0])

    total_injected = sum(int(summary.get("injected_packets", 0)) for summary in summaries)
    total_delivered = sum(int(summary.get("delivered_packets", 0)) for summary in summaries)
    total_dropped = sum(int(summary.get("dropped_packets", 0)) for summary in summaries)
    total_cycles = sum(int(summary.get("cycles", 0)) for summary in summaries)
    total_admitted = sum(int(summary.get("admitted_packets", 0)) for summary in summaries)
    total_exact = sum(int(summary.get("exact_matches", 0)) for summary in summaries)

    def _weighted_average(key: str, weight_key: str) -> float:
        weighted_total = 0.0
        total_weight = 0.0
        for summary in summaries:
            weight = float(summary.get(weight_key, 0))
            weighted_total += float(summary.get(key, 0.0)) * weight
            total_weight += weight
        return round(weighted_total / max(total_weight, 1.0), 4)

    def _average(key: str) -> float:
        return round(mean(float(summary.get(key, 0.0)) for summary in summaries), 4)

    return {
        "capability_policy": str(summaries[0].get("capability_policy", "")),
        "cycles": total_cycles,
        "injected_packets": total_injected,
        "admitted_packets": total_admitted,
        "delivered_packets": total_delivered,
        "delivery_ratio": round(total_delivered / max(total_injected, 1), 4),
        "dropped_packets": total_dropped,
        "drop_ratio": round(total_dropped / max(total_injected, 1), 4),
        "source_buffer": max(int(summary.get("source_buffer", 0)) for summary in summaries),
        "mean_latency": _weighted_average("mean_latency", "delivered_packets"),
        "mean_hops": _weighted_average("mean_hops", "delivered_packets"),
        "node_atp_total": _average("node_atp_total"),
        "mean_route_cost": _weighted_average("mean_route_cost", "injected_packets"),
        "mean_feedback_award": _weighted_average("mean_feedback_award", "delivered_packets"),
        "mean_source_admission": round(total_admitted / max(total_cycles, 1), 4),
        "last_source_admission": int(summaries[-1].get("last_source_admission", 0)),
        "source_admission_support": _average("source_admission_support"),
        "source_admission_velocity": _average("source_admission_velocity"),
        "mean_source_efficiency": _average("mean_source_efficiency"),
        "exact_matches": total_exact,
        "mean_bit_accuracy": _weighted_average("mean_bit_accuracy", "delivered_packets"),
    }


def _inject_packet_batch(
    system: NativeSubstrateSystem,
    batch: Sequence[OccupancyPacketSpec],
    *,
    context_code: int | None,
    ingress_mode: str,
) -> list[str]:
    if ingress_mode == INGRESS_DIRECT:
        packets: list[SignalPacket] = []
        for spec in batch:
            packet = _direct_inject_packet(system, spec)
            packet.task_id = OCCUPANCY_TASK_ID
            if context_code is not None:
                packet.context_bit = context_code
            packets.append(packet)
        return [packet.packet_id for packet in packets]

    if ingress_mode != INGRESS_ADMISSION:
        raise ValueError(f"Unsupported ingress_mode: {ingress_mode}")

    packets = [
        system.environment.create_packet(
            cycle=system.global_cycle,
            input_bits=spec.input_bits,
            payload_bits=spec.input_bits,
            context_bit=context_code,
            task_id=OCCUPANCY_TASK_ID,
            origin=spec.source_node_id,
        )
        for spec in batch
    ]
    packet_ids = [packet.packet_id for packet in packets]
    system.environment.inject_packets(packets, cycle=system.global_cycle)
    return packet_ids


def _run_episode_v3(
    system: NativeSubstrateSystem,
    episode: OccupancyEpisode,
    *,
    config: OccupancyRealV3Config,
    training: bool,
    context_code: int | None,
) -> dict[str, object]:
    packet_ids: list[str] = []
    active_feedback = (
        config.feedback_amount
        if training
        else config.feedback_amount * config.eval_feedback_fraction
    )
    original_feedback = system.environment.feedback_amount
    system.environment.feedback_amount = 0.0

    for batch in _episode_batches(episode):
        batch_ids = _inject_packet_batch(
            system,
            batch,
            context_code=context_code,
            ingress_mode=config.ingress_mode,
        )
        packet_ids.extend(batch_ids)
        batch_id_set = set(batch_ids)
        for _ in range(8):
            if _episode_resolved(system, batch_id_set):
                break
            system.run_global_cycle()

    packet_id_set = set(packet_ids)
    for _ in range(config.forward_drain_cycles):
        if _episode_resolved(system, packet_id_set):
            break
        system.run_global_cycle()

    delivered_by_id = _packets_by_id(system.environment.delivered_packets)
    dropped_by_id = _packets_by_id(system.environment.dropped_packets)
    delivered_packets = [delivered_by_id[pid] for pid in packet_ids if pid in delivered_by_id]
    dropped_count = sum(1 for pid in packet_ids if pid in dropped_by_id)

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
    predicted = 1 if occupied_votes > empty_votes else 0
    delivered_count = len(delivered_packets)
    margin = abs(occupied_votes - empty_votes)
    correct_count = decision_counts[target_decision]

    feedback_events = 0
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
        feedback_events = len(pulses)
        feedback_total = round(active_feedback * len(pulses), 4)
        for _ in range(config.feedback_drain_cycles):
            if not system.environment.pending_feedback:
                break
            system.run_global_cycle()

    system.environment.feedback_amount = original_feedback
    return {
        "episode_index": int(episode.episode_index),
        "label": int(episode.label),
        "prediction": int(predicted),
        "correct": bool(predicted == episode.label and delivered_count > 0),
        "context_code": int(context_code) if context_code is not None else None,
        "packet_count": len(episode.packets),
        "delivered_packets": delivered_count,
        "dropped_packets": dropped_count,
        "decision_counts": dict(decision_counts),
        "decision_margin": int(margin),
        "prediction_confidence": round(margin / max(delivered_count, 1), 4),
        "target_decision": target_decision,
        "correct_packet_count": int(correct_count),
        "feedback_event_count": int(feedback_events),
        "feedback_total": float(feedback_total),
    }


def run_session_v3(
    system: NativeSubstrateSystem,
    session: OccupancySession,
    *,
    config: OccupancyRealV3Config,
    training: bool,
    episode_context_codes: Sequence[int | None],
) -> dict[str, object]:
    admission_start = len(system.environment.source_admission_history)
    efficiency_start = len(system.environment.source_efficiency_history)
    overload_start = int(system.environment.overload_events)

    episode_results = [
        _run_episode_v3(
            system,
            episode,
            config=config,
            training=training,
            context_code=context_code,
        )
        for episode, context_code in zip(session.episodes, episode_context_codes)
    ]

    total_packets = sum(int(result["packet_count"]) for result in episode_results)
    total_delivered = sum(int(result["delivered_packets"]) for result in episode_results)
    total_dropped = sum(int(result["dropped_packets"]) for result in episode_results)
    correct_episodes = sum(1 for result in episode_results if bool(result["correct"]))
    total_feedback = sum(int(result["feedback_event_count"]) for result in episode_results)

    admission_window = system.environment.source_admission_history[admission_start:]
    efficiency_window = system.environment.source_efficiency_history[efficiency_start:]
    explicit_context_codes = [int(code) for code in episode_context_codes if code is not None]

    first_episode = episode_results[0] if episode_results else None
    first_three = episode_results[:3]
    first_three_packets = sum(int(result["packet_count"]) for result in first_three)
    first_three_delivered = sum(int(result["delivered_packets"]) for result in first_three)

    return {
        "session_index": int(session.session_index),
        "label": int(session.label),
        "context_code": explicit_context_codes[-1] if explicit_context_codes else None,
        "context_codes_seen": sorted(set(explicit_context_codes)),
        "episode_context_codes": [
            int(code) if code is not None else None
            for code in episode_context_codes
        ],
        "episode_count": len(episode_results),
        "delivery_ratio": round(total_delivered / max(total_packets, 1), 4),
        "accuracy": round(correct_episodes / max(len(episode_results), 1), 4),
        "total_packets": int(total_packets),
        "total_delivered": int(total_delivered),
        "total_dropped": int(total_dropped),
        "total_feedback_events": int(total_feedback),
        "first_episode_delivery_ratio": round(
            float(first_episode["delivered_packets"]) / max(float(first_episode["packet_count"]), 1.0),
            4,
        ) if first_episode is not None else 0.0,
        "first_three_episode_delivery_ratio": round(
            first_three_delivered / max(first_three_packets, 1),
            4,
        ),
        "first_episode_accuracy": round(
            sum(1 for result in episode_results[:1] if bool(result["correct"])) / max(len(episode_results[:1]), 1),
            4,
        ) if episode_results else 0.0,
        "first_three_episode_accuracy": round(
            sum(1 for result in first_three if bool(result["correct"])) / max(len(first_three), 1),
            4,
        ) if first_three else 0.0,
        "admission_metrics": {
            "admitted_packets": sum(int(value) for value in admission_window),
            "mean_source_admission": round(mean(admission_window), 4) if admission_window else 0.0,
            "max_source_admission": max(admission_window, default=0),
            "mean_source_efficiency": round(mean(efficiency_window), 4) if efficiency_window else 0.0,
            "overload_events": int(system.environment.overload_events) - overload_start,
        },
        "episode_results": episode_results,
    }


def _efficiency_metrics(
    warm_results: Sequence[dict[str, object]],
    cold_results: Sequence[dict[str, object]],
) -> dict[str, object]:
    warm_curve = [float(result["delivery_ratio"]) for result in warm_results]
    cold_curve = [float(result["delivery_ratio"]) for result in cold_results]

    efficiency_ratio_curve: list[float | None] = []
    for warm_value, cold_value in zip(warm_curve, cold_curve):
        if cold_value > 0.0:
            efficiency_ratio_curve.append(round(warm_value / cold_value, 4))
        else:
            efficiency_ratio_curve.append(None)

    valid_ratios = [ratio for ratio in efficiency_ratio_curve if ratio is not None]
    warm_first_episode = [float(result["first_episode_delivery_ratio"]) for result in warm_results]
    cold_first_episode = [float(result["first_episode_delivery_ratio"]) for result in cold_results]
    warm_first_three = [float(result["first_three_episode_delivery_ratio"]) for result in warm_results]
    cold_first_three = [float(result["first_three_episode_delivery_ratio"]) for result in cold_results]

    def _sessions_to_threshold(curve: Sequence[float], threshold: float = 0.80) -> int | None:
        for index, value in enumerate(curve):
            if value >= threshold:
                return index
        return None

    return {
        "warm_delivery_curve": warm_curve,
        "cold_delivery_curve": cold_curve,
        "efficiency_ratio_curve": efficiency_ratio_curve,
        "mean_efficiency_ratio": round(mean(valid_ratios), 4) if valid_ratios else None,
        "warm_sessions_to_80pct": _sessions_to_threshold(warm_curve, 0.80),
        "cold_sessions_to_80pct": _sessions_to_threshold(cold_curve, 0.80),
        "session_1_delivery_delta": round(
            (warm_curve[0] if warm_curve else 0.0) - (cold_curve[0] if cold_curve else 0.0),
            4,
        ),
        "session_1_efficiency_ratio": efficiency_ratio_curve[0] if efficiency_ratio_curve else None,
        "mean_first_episode_delivery_delta": round(
            mean(warm_first_episode) - mean(cold_first_episode),
            4,
        ) if warm_first_episode and cold_first_episode else None,
        "mean_first_three_episode_delivery_delta": round(
            mean(warm_first_three) - mean(cold_first_three),
            4,
        ) if warm_first_three and cold_first_three else None,
        "warm_first_episode_delivery_mean": round(mean(warm_first_episode), 4) if warm_first_episode else None,
        "cold_first_episode_delivery_mean": round(mean(cold_first_episode), 4) if cold_first_episode else None,
        "warm_first_three_episode_delivery_mean": round(mean(warm_first_three), 4) if warm_first_three else None,
        "cold_first_three_episode_delivery_mean": round(mean(cold_first_three), 4) if cold_first_three else None,
        "warm_delivery_at": {
            "session_1": warm_curve[0] if warm_curve else None,
            "session_5": warm_curve[4] if len(warm_curve) > 4 else None,
            "session_10": warm_curve[9] if len(warm_curve) > 9 else None,
            "session_20": warm_curve[19] if len(warm_curve) > 19 else None,
        },
        "cold_delivery_at": {
            "session_1": cold_curve[0] if cold_curve else None,
            "session_5": cold_curve[4] if len(cold_curve) > 4 else None,
            "session_10": cold_curve[9] if len(cold_curve) > 9 else None,
            "session_20": cold_curve[19] if len(cold_curve) > 19 else None,
        },
    }


def _context_transfer_probe(
    warm_results: Sequence[dict[str, object]],
    cold_results: Sequence[dict[str, object]],
    *,
    training_context_codes: set[int],
    context_mode: str,
) -> dict[str, object]:
    if context_mode == CONTEXT_LATENT:
        return {
            "context_mode": context_mode,
            "training_context_codes": [],
            "comparison_applicable": False,
            "status": "not_applicable_latent_context",
            "warm_seen_mean_delivery": None,
            "warm_unseen_mean_delivery": None,
            "cold_seen_mean_delivery": None,
            "cold_unseen_mean_delivery": None,
            "warm_seen_session_count": 0,
            "warm_unseen_session_count": 0,
            "eval_context_codes": [],
        }

    def _split(results: Sequence[dict[str, object]]) -> tuple[list[float], list[float], set[int]]:
        seen: list[float] = []
        unseen: list[float] = []
        eval_codes: set[int] = set()
        for result in results:
            code = result.get("context_code")
            if code is None:
                continue
            code_int = int(code)
            eval_codes.add(code_int)
            target = seen if code_int in training_context_codes else unseen
            target.append(float(result["delivery_ratio"]))
        return seen, unseen, eval_codes

    warm_seen, warm_unseen, warm_codes = _split(warm_results)
    cold_seen, cold_unseen, cold_codes = _split(cold_results)
    eval_codes = sorted(warm_codes | cold_codes)

    if not eval_codes:
        status = "not_applicable_no_explicit_eval_contexts"
    elif set(eval_codes).issubset(training_context_codes):
        status = "not_applicable_all_eval_contexts_seen"
    else:
        status = "ok"

    def _avg(values: Sequence[float]) -> float | None:
        return round(mean(values), 4) if values else None

    return {
        "context_mode": context_mode,
        "training_context_codes": sorted(training_context_codes),
        "eval_context_codes": eval_codes,
        "comparison_applicable": status == "ok",
        "status": status,
        "warm_seen_mean_delivery": _avg(warm_seen),
        "warm_unseen_mean_delivery": _avg(warm_unseen),
        "cold_seen_mean_delivery": _avg(cold_seen),
        "cold_unseen_mean_delivery": _avg(cold_unseen),
        "warm_seen_session_count": len(warm_seen),
        "warm_unseen_session_count": len(warm_unseen),
    }


class _EvalWorkerSpec(NamedTuple):
    config: OccupancyRealV3Config
    sessions: tuple[OccupancySession, ...]
    carryover_path: str | None
    eval_protocol: str
    co2_median: float
    light_median: float


class _FreshEvalSessionSpec(NamedTuple):
    config: OccupancyRealV3Config
    session: OccupancySession
    carryover_path: str | None
    co2_median: float
    light_median: float
    condition: str


class _SweepSeedSpec(NamedTuple):
    config: OccupancyRealV3Config
    eval_workers: int


def _run_eval_worker(spec: _EvalWorkerSpec) -> dict[str, object]:
    if spec.eval_protocol not in (EVAL_PERSISTENT, EVAL_FRESH):
        raise ValueError(f"Unsupported eval protocol: {spec.eval_protocol}")

    session_results: list[dict[str, object]] = []
    system_summaries: list[dict[str, object]] = []

    def _run_on_system(system: NativeSubstrateSystem, session: OccupancySession) -> dict[str, object]:
        return run_session_v3(
            system,
            session,
            config=spec.config,
            training=False,
            episode_context_codes=_context_codes_for_session(
                session,
                context_mode=spec.config.context_mode,
                co2_median=spec.co2_median,
                light_median=spec.light_median,
            ),
        )

    if spec.eval_protocol == EVAL_PERSISTENT:
        system = build_v3_system(spec.config)
        if spec.carryover_path is not None:
            system.load_substrate_carryover(spec.carryover_path)
        for session in spec.sessions:
            session_results.append(_run_on_system(system, session))
        system_summaries.append(_compact_v3_system_summary(system.summarize()))
    else:
        for session in spec.sessions:
            system = build_v3_system(spec.config)
            if spec.carryover_path is not None:
                system.load_substrate_carryover(spec.carryover_path)
            session_results.append(_run_on_system(system, session))
            system_summaries.append(_compact_v3_system_summary(system.summarize()))

    return {
        "session_results": session_results,
        "system_summaries": system_summaries,
        "system_summary": _aggregate_compact_system_summaries(system_summaries),
        "reset_count": len(system_summaries),
    }


def _run_fresh_eval_session_worker(spec: _FreshEvalSessionSpec) -> dict[str, object]:
    system = build_v3_system(spec.config)
    if spec.carryover_path is not None:
        system.load_substrate_carryover(spec.carryover_path)
    session_result = run_session_v3(
        system,
        spec.session,
        config=spec.config,
        training=False,
        episode_context_codes=_context_codes_for_session(
            spec.session,
            context_mode=spec.config.context_mode,
            co2_median=spec.co2_median,
            light_median=spec.light_median,
        ),
    )
    return {
        "condition": spec.condition,
        "session_index": int(spec.session.session_index),
        "session_result": session_result,
        "system_summary": _compact_v3_system_summary(system.summarize()),
    }


def _run_sweep_seed_worker(spec: _SweepSeedSpec) -> dict[str, object]:
    result = run_occupancy_real_v3_experiment(spec.config, workers=spec.eval_workers)
    return {
        "selector_seed": int(spec.config.selector_seed),
        "eval_workers": int(spec.eval_workers),
        "result": result,
    }


def _session_results_for_output(
    results: Sequence[dict[str, object]],
    *,
    include_episodes: bool,
) -> list[dict[str, object]]:
    if include_episodes:
        return [dict(result) for result in results]
    return [
        {key: value for key, value in result.items() if key != "episode_results"}
        for result in results
    ]


def _build_protocol_payload(
    protocol_name: str,
    warm_payload: dict[str, object],
    cold_payload: dict[str, object],
    *,
    training_context_codes: set[int],
    context_mode: str,
    summary_only: bool,
) -> dict[str, object]:
    warm_results = list(warm_payload["session_results"])
    cold_results = list(cold_payload["session_results"])
    warm_episodes = [episode for session in warm_results for episode in session["episode_results"]]
    cold_episodes = [episode for session in cold_results for episode in session["episode_results"]]
    payload = {
        "eval_protocol": protocol_name,
        "warm_summary": _summarize_episode_results_v3(warm_episodes),
        "cold_summary": _summarize_episode_results_v3(cold_episodes),
        "efficiency": _efficiency_metrics(warm_results, cold_results),
        "context_transfer_probe": _context_transfer_probe(
            warm_results,
            cold_results,
            training_context_codes=training_context_codes,
            context_mode=context_mode,
        ),
        "warm_system_summary": dict(warm_payload["system_summary"]),
        "cold_system_summary": dict(cold_payload["system_summary"]),
        "warm_reset_count": int(warm_payload["reset_count"]),
        "cold_reset_count": int(cold_payload["reset_count"]),
        "workers_used": int(max(warm_payload.get("workers_used", 1), cold_payload.get("workers_used", 1))),
        "parallelism_status": str(
            warm_payload.get("parallelism_status")
            or cold_payload.get("parallelism_status")
            or "sequential"
        ),
    }
    if not summary_only:
        payload["warm_session_results"] = _session_results_for_output(
            warm_results,
            include_episodes=False,
        )
        payload["cold_session_results"] = _session_results_for_output(
            cold_results,
            include_episodes=False,
        )
        payload["warm_system_summaries"] = list(warm_payload["system_summaries"])
        payload["cold_system_summaries"] = list(cold_payload["system_summaries"])
    return payload


def _run_protocol_eval(
    *,
    protocol_name: str,
    config: OccupancyRealV3Config,
    eval_sessions: Sequence[OccupancySession],
    carryover_path: str | None,
    co2_median: float,
    light_median: float,
    workers: int | None,
) -> tuple[dict[str, object], dict[str, object]]:
    if protocol_name == EVAL_FRESH:
        return _run_fresh_protocol_eval(
            config=config,
            eval_sessions=eval_sessions,
            carryover_path=carryover_path,
            co2_median=co2_median,
            light_median=light_median,
            workers=workers,
        )
    return _run_persistent_protocol_eval(
        protocol_name=protocol_name,
        config=config,
        eval_sessions=eval_sessions,
        carryover_path=carryover_path,
        co2_median=co2_median,
        light_median=light_median,
        workers=workers,
    )


def _run_persistent_protocol_eval(
    *,
    protocol_name: str,
    config: OccupancyRealV3Config,
    eval_sessions: Sequence[OccupancySession],
    carryover_path: str | None,
    co2_median: float,
    light_median: float,
    workers: int | None,
) -> tuple[dict[str, object], dict[str, object]]:
    warm_spec = _EvalWorkerSpec(
        config=config,
        sessions=tuple(eval_sessions),
        carryover_path=carryover_path,
        eval_protocol=protocol_name,
        co2_median=co2_median,
        light_median=light_median,
    )
    cold_spec = _EvalWorkerSpec(
        config=config,
        sessions=tuple(eval_sessions),
        carryover_path=None,
        eval_protocol=protocol_name,
        co2_median=co2_median,
        light_median=light_median,
    )
    worker_count = _resolve_worker_count(workers, 2)
    parallelism_status = "sequential"
    effective_workers_used = 1
    if worker_count >= 2:
        try:
            with ProcessPoolExecutor(max_workers=2) as executor:
                warm_future = executor.submit(_run_eval_worker, warm_spec)
                cold_future = executor.submit(_run_eval_worker, cold_spec)
                warm_payload = warm_future.result()
                cold_payload = cold_future.result()
            parallelism_status = f"process_pool:{min(worker_count, 2)}"
            effective_workers_used = min(worker_count, 2)
        except (PermissionError, OSError):
            warm_payload = _run_eval_worker(warm_spec)
            cold_payload = _run_eval_worker(cold_spec)
            parallelism_status = "fallback_sequential"
    else:
        warm_payload = _run_eval_worker(warm_spec)
        cold_payload = _run_eval_worker(cold_spec)
    warm_payload["workers_used"] = effective_workers_used
    cold_payload["workers_used"] = effective_workers_used
    warm_payload["parallelism_status"] = parallelism_status
    cold_payload["parallelism_status"] = parallelism_status
    return warm_payload, cold_payload


def _run_fresh_protocol_eval(
    *,
    config: OccupancyRealV3Config,
    eval_sessions: Sequence[OccupancySession],
    carryover_path: str | None,
    co2_median: float,
    light_median: float,
    workers: int | None,
) -> tuple[dict[str, object], dict[str, object]]:
    task_specs: list[_FreshEvalSessionSpec] = []
    for condition, path in (("warm", carryover_path), ("cold", None)):
        for session in eval_sessions:
            task_specs.append(
                _FreshEvalSessionSpec(
                    config=config,
                    session=session,
                    carryover_path=path,
                    co2_median=co2_median,
                    light_median=light_median,
                    condition=condition,
                )
            )

    worker_count = _resolve_worker_count(workers, len(task_specs))
    records_by_condition: dict[str, list[dict[str, object]]] = {"warm": [], "cold": []}
    parallelism_status = "sequential"
    effective_workers_used = 1

    if worker_count >= 2:
        try:
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                futures = [executor.submit(_run_fresh_eval_session_worker, spec) for spec in task_specs]
                for future in as_completed(futures):
                    payload = future.result()
                    records_by_condition[str(payload["condition"])].append(payload)
            parallelism_status = f"process_pool:{worker_count}"
            effective_workers_used = worker_count
        except (PermissionError, OSError):
            for spec in task_specs:
                payload = _run_fresh_eval_session_worker(spec)
                records_by_condition[str(payload["condition"])].append(payload)
            parallelism_status = "fallback_sequential"
    else:
        for spec in task_specs:
            payload = _run_fresh_eval_session_worker(spec)
            records_by_condition[str(payload["condition"])].append(payload)

    def _materialize(condition: str) -> dict[str, object]:
        ordered = sorted(records_by_condition[condition], key=lambda item: int(item["session_index"]))
        system_summaries = [dict(item["system_summary"]) for item in ordered]
        return {
            "session_results": [dict(item["session_result"]) for item in ordered],
            "system_summaries": system_summaries,
            "system_summary": _aggregate_compact_system_summaries(system_summaries),
            "reset_count": len(system_summaries),
            "workers_used": effective_workers_used,
            "parallelism_status": parallelism_status,
        }

    return _materialize("warm"), _materialize("cold")


def _sweep_seed_summary(seed_result: dict[str, object]) -> dict[str, object]:
    primary_eval = dict(seed_result["primary_eval"])
    efficiency = dict(primary_eval["efficiency"])
    warm_summary = dict(primary_eval["warm_summary"])
    cold_summary = dict(primary_eval["cold_summary"])
    return {
        "selector_seed": int(seed_result["v3_config"]["selector_seed"]),
        "primary_eval_mode": str(seed_result["primary_eval_mode"]),
        "train_accuracy": float(seed_result["train_summary"]["metrics"].get("accuracy", 0.0)),
        "warm_accuracy": float(warm_summary["metrics"].get("accuracy", 0.0)),
        "cold_accuracy": float(cold_summary["metrics"].get("accuracy", 0.0)),
        "warm_mean_delivery_ratio": float(warm_summary.get("mean_delivery_ratio", 0.0)),
        "cold_mean_delivery_ratio": float(cold_summary.get("mean_delivery_ratio", 0.0)),
        "mean_efficiency_ratio": efficiency.get("mean_efficiency_ratio"),
        "session_1_delivery_delta": efficiency.get("session_1_delivery_delta"),
        "mean_first_episode_delivery_delta": efficiency.get("mean_first_episode_delivery_delta"),
        "mean_first_three_episode_delivery_delta": efficiency.get("mean_first_three_episode_delivery_delta"),
        "protocol_parallelism": {
            name: str(payload.get("parallelism_status", "sequential"))
            for name, payload in dict(seed_result["eval_protocols"]).items()
        },
        "eval_workers_by_protocol": dict(seed_result["worker_policy"]["eval_workers_by_protocol"]),
    }


def _mean_optional(values: Sequence[float | None]) -> float | None:
    valid = [float(value) for value in values if value is not None]
    return round(mean(valid), 4) if valid else None


def _best_seed_by_metric(
    seed_summaries: Sequence[dict[str, object]],
    metric_key: str,
) -> dict[str, object] | None:
    candidates = [
        summary
        for summary in seed_summaries
        if summary.get(metric_key) is not None
    ]
    if not candidates:
        return None
    best = max(candidates, key=lambda summary: float(summary[metric_key]))
    return {
        "selector_seed": int(best["selector_seed"]),
        "metric": metric_key,
        "value": float(best[metric_key]),
    }


def run_occupancy_real_v3_sweep(
    config: OccupancyRealV3Config,
    *,
    selector_seeds: Sequence[int],
    workers: int | None = None,
) -> dict[str, object]:
    ordered_seeds = tuple(dict.fromkeys(int(seed) for seed in selector_seeds))
    if not ordered_seeds:
        raise ValueError("selector_seeds must contain at least one seed")

    worker_plan = resolve_sweep_worker_plan(len(ordered_seeds), workers)
    seed_specs = [
        _SweepSeedSpec(
            config=replace(config, selector_seed=seed),
            eval_workers=worker_plan.eval_workers_per_seed,
        )
        for seed in ordered_seeds
    ]

    seed_records: list[dict[str, object]] = []
    parallelism_status = "sequential"
    if worker_plan.seed_workers >= 2:
        try:
            with ProcessPoolExecutor(max_workers=worker_plan.seed_workers) as executor:
                futures = [executor.submit(_run_sweep_seed_worker, spec) for spec in seed_specs]
                for future in as_completed(futures):
                    seed_records.append(future.result())
            parallelism_status = f"process_pool:{worker_plan.seed_workers}"
        except (PermissionError, OSError):
            seed_records = [_run_sweep_seed_worker(spec) for spec in seed_specs]
            parallelism_status = "fallback_sequential"
    else:
        seed_records = [_run_sweep_seed_worker(spec) for spec in seed_specs]

    ordered_records = sorted(seed_records, key=lambda item: int(item["selector_seed"]))
    seed_results = [dict(record["result"]) for record in ordered_records]
    seed_summaries = [_sweep_seed_summary(result) for result in seed_results]
    aggregate = {
        "selector_seed_count": len(ordered_seeds),
        "primary_eval_mode": str(seed_results[0]["primary_eval_mode"]) if seed_results else None,
        "mean_train_accuracy": round(
            mean(float(summary["train_accuracy"]) for summary in seed_summaries),
            4,
        ) if seed_summaries else None,
        "mean_warm_accuracy": round(
            mean(float(summary["warm_accuracy"]) for summary in seed_summaries),
            4,
        ) if seed_summaries else None,
        "mean_cold_accuracy": round(
            mean(float(summary["cold_accuracy"]) for summary in seed_summaries),
            4,
        ) if seed_summaries else None,
        "mean_warm_delivery_ratio": round(
            mean(float(summary["warm_mean_delivery_ratio"]) for summary in seed_summaries),
            4,
        ) if seed_summaries else None,
        "mean_cold_delivery_ratio": round(
            mean(float(summary["cold_mean_delivery_ratio"]) for summary in seed_summaries),
            4,
        ) if seed_summaries else None,
        "mean_efficiency_ratio": _mean_optional(
            [summary["mean_efficiency_ratio"] for summary in seed_summaries]
        ),
        "mean_session_1_delivery_delta": _mean_optional(
            [summary["session_1_delivery_delta"] for summary in seed_summaries]
        ),
        "mean_first_episode_delivery_delta": _mean_optional(
            [summary["mean_first_episode_delivery_delta"] for summary in seed_summaries]
        ),
        "mean_first_three_episode_delivery_delta": _mean_optional(
            [summary["mean_first_three_episode_delivery_delta"] for summary in seed_summaries]
        ),
        "best_seed_by_efficiency_ratio": _best_seed_by_metric(seed_summaries, "mean_efficiency_ratio"),
        "best_seed_by_session_1_delivery_delta": _best_seed_by_metric(
            seed_summaries,
            "session_1_delivery_delta",
        ),
    }

    base_config = asdict(config)
    base_config["selector_seed"] = None
    return {
        "v3_sweep_config": {
            "base_config": base_config,
            "selector_seeds": list(ordered_seeds),
        },
        "worker_policy": {
            **asdict(worker_plan),
            "parallelism_status": parallelism_status,
        },
        "seed_summaries": seed_summaries,
        "seed_results": seed_results,
        "aggregate": aggregate,
    }


def run_occupancy_real_v3_experiment(config: OccupancyRealV3Config, workers: int | None = None) -> dict[str, object]:
    all_episodes = load_all_episodes_v3(config)
    all_sessions_raw = segment_into_sessions(all_episodes)

    train_count = max(1, round(len(all_sessions_raw) * config.train_session_fraction))
    train_sessions_raw = all_sessions_raw[:train_count]
    eval_sessions_raw = all_sessions_raw[train_count:]

    co2_median, light_median = compute_training_medians(train_sessions_raw)
    train_sessions = assign_context_codes(train_sessions_raw, co2_median, light_median)
    eval_sessions = assign_context_codes(eval_sessions_raw, co2_median, light_median)

    if config.max_train_sessions is not None:
        train_sessions = train_sessions[: config.max_train_sessions]
    if config.max_eval_sessions is not None:
        eval_sessions = eval_sessions[: config.max_eval_sessions]

    training_context_codes = _collect_context_codes(
        train_sessions,
        context_mode=config.context_mode,
        co2_median=co2_median,
        light_median=light_median,
    )

    train_inventory = session_inventory(train_sessions)
    eval_inventory = session_inventory(eval_sessions)

    train_system = build_v3_system(config)
    train_session_results = [
        run_session_v3(
            train_system,
            session,
            config=config,
            training=True,
            episode_context_codes=_context_codes_for_session(
                session,
                context_mode=config.context_mode,
                co2_median=co2_median,
                light_median=light_median,
            ),
        )
        for session in train_sessions
    ]

    eval_protocols = [config.eval_mode] if config.eval_mode != EVAL_BOTH else [EVAL_FRESH, EVAL_PERSISTENT]
    protocol_results: dict[str, dict[str, object]] = {}

    carryover_root = Path("tests_tmp")
    carryover_root.mkdir(parents=True, exist_ok=True)
    carryover_dir = carryover_root / (
        f"real_v3_carryover_seed{config.selector_seed}_pid{os.getpid()}_{uuid4().hex[:8]}"
    )
    shutil.rmtree(carryover_dir, ignore_errors=True)
    try:
        train_system.save_substrate_carryover(carryover_dir)
        for protocol_name in eval_protocols:
            warm_payload, cold_payload = _run_protocol_eval(
                protocol_name=protocol_name,
                config=config,
                eval_sessions=eval_sessions,
                carryover_path=str(carryover_dir),
                co2_median=co2_median,
                light_median=light_median,
                workers=workers,
            )

            protocol_results[protocol_name] = _build_protocol_payload(
                protocol_name,
                warm_payload,
                cold_payload,
                training_context_codes=training_context_codes,
                context_mode=config.context_mode,
                summary_only=config.summary_only,
            )
    finally:
        shutil.rmtree(carryover_dir, ignore_errors=True)

    primary_eval_mode = EVAL_FRESH if config.eval_mode == EVAL_BOTH else config.eval_mode
    primary_eval = protocol_results[primary_eval_mode]
    train_episodes_flat = [
        episode
        for session in train_session_results
        for episode in session["episode_results"]
    ]

    result: dict[str, object] = {
        "v3_config": asdict(config),
        "worker_policy": {
            "requested_workers": workers,
            "auto_cpu_target_fraction": AUTO_CPU_TARGET_FRACTION,
            "eval_workers_by_protocol": {
                name: int(payload["workers_used"])
                for name, payload in protocol_results.items()
            },
        },
        "dataset_rows": len(all_episodes) + config.window_size - 1,
        "total_episodes": len(all_episodes),
        "total_sessions": len(all_sessions_raw),
        "train_session_count": len(train_sessions),
        "eval_session_count": len(eval_sessions),
        "co2_training_median": round(co2_median, 6),
        "light_training_median": round(light_median, 6),
        "training_context_codes": sorted(training_context_codes),
        "train_inventory": train_inventory,
        "eval_inventory": eval_inventory,
        "train_summary": _summarize_episode_results_v3(train_episodes_flat),
        "train_system_summary": _compact_v3_system_summary(train_system.summarize()),
        "primary_eval_mode": primary_eval_mode,
        "primary_eval": primary_eval,
        "eval_protocols": protocol_results,
        "warm_eval_summary": primary_eval["warm_summary"],
        "cold_eval_summary": primary_eval["cold_summary"],
        "carryover_efficiency": primary_eval["efficiency"],
        "context_transfer_probe": primary_eval["context_transfer_probe"],
        "warm_system_summary": primary_eval["warm_system_summary"],
        "cold_system_summary": primary_eval["cold_system_summary"],
    }

    if not config.summary_only:
        result["train_session_results"] = _session_results_for_output(
            train_session_results,
            include_episodes=False,
        )

    return result


__all__ = [
    "AUTO_CPU_TARGET_FRACTION",
    "OccupancyRealV3SweepWorkerPlan",
    "OccupancyRealV3Config",
    "auto_worker_budget",
    "auto_worker_count",
    "build_v3_system",
    "load_all_episodes_v3",
    "occupancy_topology_v3",
    "resolve_sweep_worker_plan",
    "run_occupancy_real_v3_experiment",
    "run_occupancy_real_v3_sweep",
    "run_session_v3",
]
