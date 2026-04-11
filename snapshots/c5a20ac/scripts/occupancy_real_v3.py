"""
occupancy_real_v3.py
--------------------
Session-structured REAL occupancy experiment designed around what REAL
actually does: local allostatic routing with substrate carryover across
sessions.

Key design differences from v1/v2
----------------------------------
v1/v2 framed the task as supervised binary classification — "classify each
5-timestep window as occupied/unoccupied" — and measured final accuracy vs
MLP.  That is the wrong comparison axis.

v3 reframes around REAL's core claims:

  1. Substrate carryover:  training substrate accelerates routing on new
     sessions of the same type.  The primary metric is how quickly the
     substrate orients to the correct routing decision in eval sessions,
     warm (carryover) vs cold (no carryover).

  2. Context-conditional routing:  a 4-class composite context code derived
     from per-session CO2+light signatures activates context-indexed action
     supports in the ConnectionSubstrate.

  3. Session-structured learning curve:  the unit of observation is a session
     (a contiguous block of same-label episodes), not individual windows.
     We record delivery ratio at each session index to measure how quickly
     the substrate builds effective routing.

Experiment phases
-----------------
Phase 1 — Session inventory
    Parse all state-transition sessions.  Report counts, context distribution,
    session length distribution.  No substrate involved.

Phase 2 — Sequential training run  (learning curve baseline)
    Run all training sessions sequentially through a single substrate.
    Record per-session delivery ratio.  Shows how fast substrate accumulates
    on the training data before any carryover test.

Phase 3 — Carryover efficiency test  (core claim)
    Warm path:  fresh system loaded from training substrate → runs eval sessions
    Cold path:  fresh system with no substrate → runs same eval sessions
    Both paths record per-session delivery ratio.
    Carryover efficiency ratio = warm[i] / cold[i] at each eval session index.

Phase 4 — Context transfer probe
    Within eval, partition sessions by whether their context_code appeared
    in the training set.  Compare warm delivery ratio for seen vs unseen
    context codes.  Tests whether substrate generalises across context shifts.

Feedback policy
---------------
Feedback is always on (eval_feedback_fraction=1.0 by default).  This is the
lesson from v2: suppressing feedback during eval causes ATP starvation and
collapses routing.  Both warm and cold eval paths receive full feedback.
"""
from __future__ import annotations

import shutil
import tempfile
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import NamedTuple, Sequence

from occupancy_baseline import build_windowed_dataset, load_csv_dataset
from occupancy_baseline.session_splitter import (
    OccupancySession,
    assign_context_codes,
    compute_training_medians,
    segment_into_sessions,
    session_inventory,
)
from phase8 import FeedbackPulse, NativeSubstrateSystem

from .occupancy_real import (
    DECISION_EMPTY,
    DECISION_OCCUPIED,
    FEATURE_SOURCE_IDS,
    VALUE_BIN_THRESHOLDS,
    OccupancyEpisode,
    OccupancyPacketSpec,
    _compact_system_summary,
    _decision_node_for_packet,
    _direct_inject_packet,
    _episode_batches,
    _episode_resolved,
    _expected_decision_node,
    _packets_by_id,
    occupancy_topology,
    summarize_episode_results,
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OccupancyRealV3Config:
    csv_path: str
    window_size: int = 5
    normalize: bool = True
    selector_seed: int = 13

    feedback_amount: float = 0.18
    # Feedback is always on in v3.  This mirrors v2's lesson.
    eval_feedback_fraction: float = 1.0

    packet_ttl: int = 8
    forward_drain_cycles: int = 16
    feedback_drain_cycles: int = 4

    # Fraction of sessions (in temporal order) used for training.
    # The remaining sessions form the eval set.
    train_session_fraction: float = 0.7


    # Optional caps on the number of sessions to run in each phase.
    # None = run all sessions.  Useful for quick smoke tests.
    max_train_sessions: int | None = None
    max_eval_sessions: int | None = None

    summary_only: bool = False


# ---------------------------------------------------------------------------
# Episode loading (all episodes, no pre-split)
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


def load_all_episodes_v3(config: OccupancyRealV3Config) -> list[OccupancyEpisode]:
    """Load all windowed episodes from the CSV without applying a train/eval split."""
    dataset = load_csv_dataset(config.csv_path, normalize=config.normalize)
    windowed = build_windowed_dataset(
        dataset,
        window_size=config.window_size,
        flatten=False,
    )
    feature_names = tuple(str(name) for name in dataset.feature_names)
    episodes: list[OccupancyEpisode] = []
    for episode_index, (window, label) in enumerate(
        zip(windowed.features, windowed.labels)
    ):
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


# ---------------------------------------------------------------------------
# System builder
# ---------------------------------------------------------------------------

def build_v3_system(config: OccupancyRealV3Config) -> NativeSubstrateSystem:
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
# Episode runner (adapted from v2, context-aware, feedback always on)
# ---------------------------------------------------------------------------

def _run_episode_v3(
    system: NativeSubstrateSystem,
    episode: OccupancyEpisode,
    *,
    config: OccupancyRealV3Config,
    training: bool,
    context_code: int | None,
) -> dict:
    """
    Run one episode through the substrate with optional context_code.

    training=True  → full feedback_amount
    training=False → feedback_amount * eval_feedback_fraction  (default: full)

    context_code is passed into each packet's metadata and into FeedbackPulse
    so the ConnectionSubstrate indexes context-specific action supports.
    """
    packet_ids: list[str] = []
    active_feedback = (
        config.feedback_amount
        if training
        else config.feedback_amount * config.eval_feedback_fraction
    )
    original_fb = system.environment.feedback_amount
    system.environment.feedback_amount = 0.0

    for batch in _episode_batches(episode):
        batch_ids: set[str] = set()
        for spec in batch:
            packet = _direct_inject_packet(system, spec)
            if context_code is not None:
                if hasattr(packet, "context_bit"):
                    packet.context_bit = context_code
                if hasattr(packet, "metadata") and isinstance(packet.metadata, dict):
                    packet.metadata["context_bit"] = context_code
            packet_ids.append(packet.packet_id)
            batch_ids.add(packet.packet_id)
        for _ in range(8):
            if _episode_resolved(system, batch_ids):
                break
            system.run_global_cycle()

    pid_set = set(packet_ids)
    for _ in range(config.forward_drain_cycles):
        if _episode_resolved(system, pid_set):
            break
        system.run_global_cycle()

    delivered_by_id = _packets_by_id(system.environment.delivered_packets)
    dropped_by_id = _packets_by_id(system.environment.dropped_packets)
    delivered = [delivered_by_id[pid] for pid in packet_ids if pid in delivered_by_id]
    dropped_count = sum(1 for pid in packet_ids if pid in dropped_by_id)

    decision_counts = {DECISION_EMPTY: 0, DECISION_OCCUPIED: 0}
    target = _expected_decision_node(episode.label)
    for packet in delivered:
        node = _decision_node_for_packet(packet)
        if node in decision_counts:
            decision_counts[node] += 1
        packet.feedback_award = 0.0
        packet.matched_target = node == target
        packet.bit_match_ratio = 1.0 if node == target else 0.0

    occupied_votes = decision_counts[DECISION_OCCUPIED]
    empty_votes = decision_counts[DECISION_EMPTY]
    predicted = 1 if occupied_votes > empty_votes else 0
    margin = abs(occupied_votes - empty_votes)
    delivered_count = len(delivered)
    correct_count = decision_counts[target]

    feedback_events = 0
    feedback_total = 0.0
    if active_feedback > 0.0 and delivered:
        system.environment.feedback_amount = active_feedback
        pulses: list[FeedbackPulse] = []
        for packet in delivered:
            if not packet.matched_target:
                continue
            kwargs: dict = dict(
                packet_id=packet.packet_id,
                edge_path=list(packet.edge_path),
                amount=active_feedback,
                transform_path=list(packet.transform_trace),
                bit_match_ratio=1.0,
                matched_target=True,
            )
            if context_code is not None:
                kwargs["context_bit"] = context_code
            pulses.append(FeedbackPulse(**kwargs))
            packet.feedback_award = active_feedback
        system.environment.pending_feedback.extend(pulses)
        feedback_events = len(pulses)
        feedback_total = round(len(pulses) * active_feedback, 4)
        for _ in range(config.feedback_drain_cycles):
            if not system.environment.pending_feedback:
                break
            system.run_global_cycle()

    system.environment.feedback_amount = original_fb
    return {
        "episode_index": episode.episode_index,
        "label": int(episode.label),
        "prediction": int(predicted),
        "correct": bool(predicted == episode.label and delivered_count > 0),
        "context_code": context_code,
        "packet_count": len(episode.packets),
        "delivered_packets": delivered_count,
        "dropped_packets": dropped_count,
        "decision_counts": dict(decision_counts),
        "decision_margin": int(margin),
        "prediction_confidence": round(margin / max(delivered_count, 1), 4),
        "target_decision": target,
        "correct_packet_count": int(correct_count),
        "feedback_event_count": int(feedback_events),
        "feedback_total": float(feedback_total),
    }


# ---------------------------------------------------------------------------
# Session runner
# ---------------------------------------------------------------------------

def run_session_v3(
    system: NativeSubstrateSystem,
    session: OccupancySession,
    *,
    config: OccupancyRealV3Config,
    training: bool,
) -> dict:
    """
    Run all episodes in a session and return session-level metrics.

    All episodes receive the session's context_code and full feedback
    (routing-during-priming: even the first episodes route and learn).
    """
    context_code = int(session.context_code) if session.context_code >= 0 else None
    episode_results = [
        _run_episode_v3(
            system,
            episode,
            config=config,
            training=training,
            context_code=context_code,
        )
        for episode in session.episodes
    ]

    total_packets = sum(r["packet_count"] for r in episode_results)
    total_delivered = sum(r["delivered_packets"] for r in episode_results)
    total_dropped = sum(r["dropped_packets"] for r in episode_results)
    correct_episodes = sum(1 for r in episode_results if r["correct"])
    total_feedback = sum(r["feedback_event_count"] for r in episode_results)

    delivery_ratio = round(total_delivered / max(total_packets, 1), 4)
    accuracy = round(correct_episodes / max(len(episode_results), 1), 4)

    return {
        "session_index": int(session.session_index),
        "label": int(session.label),
        "context_code": context_code,
        "episode_count": len(episode_results),
        "delivery_ratio": delivery_ratio,
        "accuracy": accuracy,
        "total_packets": int(total_packets),
        "total_delivered": int(total_delivered),
        "total_dropped": int(total_dropped),
        "total_feedback_events": int(total_feedback),
        "episode_results": episode_results,
    }


# ---------------------------------------------------------------------------
# Carryover efficiency computation
# ---------------------------------------------------------------------------

def _efficiency_metrics(
    warm_results: list[dict],
    cold_results: list[dict],
) -> dict:
    """
    Compute carryover efficiency from parallel warm/cold session result lists.

    efficiency_ratio[i] = warm_delivery[i] / cold_delivery[i]
                          (None when cold == 0 to avoid division by zero)

    sessions_to_threshold: first session index where delivery_ratio >= 0.80,
    separately for warm and cold.
    """
    warm_curve = [r["delivery_ratio"] for r in warm_results]
    cold_curve = [r["delivery_ratio"] for r in cold_results]

    efficiency_ratio: list[float | None] = []
    for w, c in zip(warm_curve, cold_curve):
        if c > 0.0:
            efficiency_ratio.append(round(w / c, 4))
        else:
            efficiency_ratio.append(None)

    def _sessions_to_threshold(curve: list[float], threshold: float = 0.80) -> int | None:
        for i, v in enumerate(curve):
            if v >= threshold:
                return i
        return None

    def _mean_ratio(ratios: list) -> float | None:
        valid = [r for r in ratios if r is not None]
        return round(mean(valid), 4) if valid else None

    warm_at = {
        "session_1": warm_curve[0] if warm_curve else None,
        "session_5": warm_curve[4] if len(warm_curve) > 4 else None,
        "session_10": warm_curve[9] if len(warm_curve) > 9 else None,
        "session_20": warm_curve[19] if len(warm_curve) > 19 else None,
    }
    cold_at = {
        "session_1": cold_curve[0] if cold_curve else None,
        "session_5": cold_curve[4] if len(cold_curve) > 4 else None,
        "session_10": cold_curve[9] if len(cold_curve) > 9 else None,
        "session_20": cold_curve[19] if len(cold_curve) > 19 else None,
    }

    return {
        "warm_delivery_curve": warm_curve,
        "cold_delivery_curve": cold_curve,
        "efficiency_ratio_curve": efficiency_ratio,
        "mean_efficiency_ratio": _mean_ratio(efficiency_ratio),
        "warm_sessions_to_80pct": _sessions_to_threshold(warm_curve, 0.80),
        "cold_sessions_to_80pct": _sessions_to_threshold(cold_curve, 0.80),
        "warm_delivery_at": warm_at,
        "cold_delivery_at": cold_at,
    }


# ---------------------------------------------------------------------------
# Context transfer probe
# ---------------------------------------------------------------------------

def _context_transfer_probe(
    warm_results: list[dict],
    cold_results: list[dict],
    training_context_codes: set[int],
) -> dict:
    """
    Partition eval sessions by whether their context_code was seen in training.

    Returns mean delivery_ratio for seen vs unseen context codes, for both
    warm and cold paths.
    """
    def _split(results: list[dict]) -> tuple[list[float], list[float]]:
        seen, unseen = [], []
        for r in results:
            code = r.get("context_code")
            target = seen if (code is not None and code in training_context_codes) else unseen
            target.append(r["delivery_ratio"])
        return seen, unseen

    warm_seen, warm_unseen = _split(warm_results)
    cold_seen, cold_unseen = _split(cold_results)

    def _avg(vals: list[float]) -> float | None:
        return round(mean(vals), 4) if vals else None

    return {
        "training_context_codes": sorted(training_context_codes),
        "warm_seen_mean_delivery": _avg(warm_seen),
        "warm_unseen_mean_delivery": _avg(warm_unseen),
        "cold_seen_mean_delivery": _avg(cold_seen),
        "cold_unseen_mean_delivery": _avg(cold_unseen),
        "warm_seen_session_count": len(warm_seen),
        "warm_unseen_session_count": len(warm_unseen),
    }


# ---------------------------------------------------------------------------
# Parallel eval worker
# ---------------------------------------------------------------------------

class _EvalWorkerSpec(NamedTuple):
    """
    Plain NamedTuple so ProcessPoolExecutor can pickle it across processes.

    carryover_path=None  →  cold start (fresh substrate)
    carryover_path=str   →  warm start (load accumulated substrate)
    """
    config: OccupancyRealV3Config
    sessions: tuple           # tuple[OccupancySession, ...]
    carryover_path: str | None


def _run_eval_worker(spec: _EvalWorkerSpec) -> dict:
    """
    Top-level function (module scope) so it can be pickled for ProcessPoolExecutor.

    Builds its own NativeSubstrateSystem, optionally loads carryover, runs all
    eval sessions, and returns session results plus a compact system summary.
    """
    system = build_v3_system(spec.config)
    if spec.carryover_path is not None:
        system.load_substrate_carryover(spec.carryover_path)
    session_results = [
        run_session_v3(system, session, config=spec.config, training=False)
        for session in spec.sessions
    ]
    return {
        "session_results": session_results,
        "system_summary": _compact_system_summary(system.summarize()),
    }


# ---------------------------------------------------------------------------
# Full experiment
# ---------------------------------------------------------------------------

def run_occupancy_real_v3_experiment(config: OccupancyRealV3Config, workers: int = 2) -> dict:
    """
    Run the three-phase v3 experiment and return a single result dict.

    Phases:
      1. Session inventory — diagnostic only, no substrate
      2. Training run — sequential sessions through one substrate (always serial)
      3. Carryover test — warm vs cold eval run in parallel (workers >= 2)
      4. Context transfer probe — seen vs unseen context codes in eval

    workers >= 2 runs warm and cold eval in separate processes (halves wall time).
    workers=1  falls back to sequential execution (useful for debugging).
    """
    # ------------------------------------------------------------------
    # Load and segment
    # ------------------------------------------------------------------
    all_episodes = load_all_episodes_v3(config)
    all_sessions_raw = segment_into_sessions(all_episodes)

    n_train = max(1, round(len(all_sessions_raw) * config.train_session_fraction))
    train_sessions_raw = all_sessions_raw[:n_train]
    eval_sessions_raw = all_sessions_raw[n_train:]

    co2_median, light_median = compute_training_medians(train_sessions_raw)

    train_sessions = assign_context_codes(train_sessions_raw, co2_median, light_median)
    eval_sessions = assign_context_codes(eval_sessions_raw, co2_median, light_median)

    if config.max_train_sessions is not None:
        train_sessions = train_sessions[: config.max_train_sessions]
    if config.max_eval_sessions is not None:
        eval_sessions = eval_sessions[: config.max_eval_sessions]

    training_context_codes = {int(s.context_code) for s in train_sessions}

    # ------------------------------------------------------------------
    # Phase 1: session inventory
    # ------------------------------------------------------------------
    train_inventory = session_inventory(train_sessions)
    eval_inventory = session_inventory(eval_sessions)

    # ------------------------------------------------------------------
    # Phase 2: sequential training run
    # ------------------------------------------------------------------
    train_system = build_v3_system(config)
    train_session_results = [
        run_session_v3(train_system, session, config=config, training=True)
        for session in train_sessions
    ]

    # ------------------------------------------------------------------
    # Phase 3: carryover test — warm and cold eval
    # Warm and cold are fully independent: run in parallel when workers >= 2.
    # The carryover dir must outlive both worker processes, so we use mkdtemp
    # (not a context manager) and clean up in a finally block.
    # ------------------------------------------------------------------
    carryover_dir = tempfile.mkdtemp(prefix="real_v3_carryover_")
    try:
        train_system.save_substrate_carryover(carryover_dir)

        warm_spec = _EvalWorkerSpec(config, tuple(eval_sessions), carryover_dir)
        cold_spec = _EvalWorkerSpec(config, tuple(eval_sessions), None)

        if workers >= 2:
            with ProcessPoolExecutor(max_workers=2) as ex:
                warm_future = ex.submit(_run_eval_worker, warm_spec)
                cold_future = ex.submit(_run_eval_worker, cold_spec)
                warm_payload = warm_future.result()
                cold_payload = cold_future.result()
        else:
            warm_payload = _run_eval_worker(warm_spec)
            cold_payload = _run_eval_worker(cold_spec)
    finally:
        shutil.rmtree(carryover_dir, ignore_errors=True)

    warm_eval_results = warm_payload["session_results"]
    cold_eval_results = cold_payload["session_results"]

    # ------------------------------------------------------------------
    # Phase 4: context transfer probe
    # ------------------------------------------------------------------
    transfer_probe = _context_transfer_probe(
        warm_eval_results,
        cold_eval_results,
        training_context_codes,
    )

    # ------------------------------------------------------------------
    # Efficiency metrics
    # ------------------------------------------------------------------
    efficiency = _efficiency_metrics(warm_eval_results, cold_eval_results)

    # ------------------------------------------------------------------
    # Aggregate episode-level summaries for train and both eval paths
    # ------------------------------------------------------------------
    train_episodes_flat = [
        ep for sr in train_session_results for ep in sr["episode_results"]
    ]
    warm_episodes_flat = [
        ep for sr in warm_eval_results for ep in sr["episode_results"]
    ]
    cold_episodes_flat = [
        ep for sr in cold_eval_results for ep in sr["episode_results"]
    ]

    result: dict = {
        "v3_config": asdict(config),
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
        "train_summary": summarize_episode_results(train_episodes_flat),
        "warm_eval_summary": summarize_episode_results(warm_episodes_flat),
        "cold_eval_summary": summarize_episode_results(cold_episodes_flat),
        "carryover_efficiency": efficiency,
        "context_transfer_probe": transfer_probe,
        "train_system_summary": _compact_system_summary(train_system.summarize()),
        "warm_system_summary": warm_payload["system_summary"],
        "cold_system_summary": cold_payload["system_summary"],
    }

    if not config.summary_only:
        result["train_session_results"] = [
            {k: v for k, v in sr.items() if k != "episode_results"}
            for sr in train_session_results
        ]
        result["warm_eval_session_results"] = [
            {k: v for k, v in sr.items() if k != "episode_results"}
            for sr in warm_eval_results
        ]
        result["cold_eval_session_results"] = [
            {k: v for k, v in sr.items() if k != "episode_results"}
            for sr in cold_eval_results
        ]

    return result


__all__ = [
    "OccupancyRealV3Config",
    "build_v3_system",
    "load_all_episodes_v3",
    "run_occupancy_real_v3_experiment",
    "run_session_v3",
]
