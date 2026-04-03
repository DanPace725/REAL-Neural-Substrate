"""
occupancy_real_v3_light.py
--------------------------
Lightweight REAL-native occupancy runner that keeps a single carried-forward
system alive across a short warmup phase and a rolling prediction phase.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean
from typing import Sequence

from occupancy_baseline.session_splitter import (
    assign_context_codes,
    compute_training_medians,
    segment_into_sessions,
    session_inventory,
)

from .occupancy_real_v3 import (
    CONTEXT_ONLINE,
    OccupancyRealV3Config,
    build_v3_system,
    load_all_episodes_v3,
    run_session_v3,
    _compact_v3_system_summary,
    _context_codes_for_session,
    _summarize_episode_results_v3,
)


@dataclass(frozen=True)
class OccupancyRealV3LightConfig:
    csv_path: str
    window_size: int = 5
    normalize: bool = True
    selector_seed: int = 13

    warmup_sessions: int = 8
    prediction_sessions: int = 8
    feedback_amount: float = 0.18
    prediction_feedback_fraction: float = 0.35

    packet_ttl: int = 8
    forward_drain_cycles: int = 16
    feedback_drain_cycles: int = 4

    topology_mode: str = "multihop_routing"
    context_mode: str = CONTEXT_ONLINE
    ingress_mode: str = "admission_source"
    summary_only: bool = True
    rolling_window: int = 3


def _lightweight_session_window(
    sessions: Sequence[dict[str, object]],
    rolling_window: int,
) -> dict[str, object]:
    if not sessions:
        return {
            "rolling_window": rolling_window,
            "recent_session_accuracy": None,
            "recent_session_delivery_ratio": None,
            "recent_first_episode_accuracy": None,
        }

    recent = list(sessions[-max(1, rolling_window):])
    return {
        "rolling_window": rolling_window,
        "recent_session_accuracy": round(
            mean(float(session["accuracy"]) for session in recent),
            4,
        ),
        "recent_session_delivery_ratio": round(
            mean(float(session["delivery_ratio"]) for session in recent),
            4,
        ),
        "recent_first_episode_accuracy": round(
            mean(float(session["first_episode_accuracy"]) for session in recent),
            4,
        ),
    }


def run_occupancy_real_v3_light(
    config: OccupancyRealV3LightConfig,
) -> dict[str, object]:
    all_episodes = load_all_episodes_v3(
        OccupancyRealV3Config(
            csv_path=config.csv_path,
            window_size=config.window_size,
            normalize=config.normalize,
            selector_seed=config.selector_seed,
            feedback_amount=config.feedback_amount,
            packet_ttl=config.packet_ttl,
            forward_drain_cycles=config.forward_drain_cycles,
            feedback_drain_cycles=config.feedback_drain_cycles,
            topology_mode=config.topology_mode,
            context_mode=config.context_mode,
            ingress_mode=config.ingress_mode,
            summary_only=True,
        )
    )
    all_sessions_raw = segment_into_sessions(all_episodes)

    warmup_count = max(1, min(config.warmup_sessions, len(all_sessions_raw)))
    prediction_count = max(1, min(config.prediction_sessions, len(all_sessions_raw) - warmup_count))
    warmup_sessions_raw = all_sessions_raw[:warmup_count]
    prediction_sessions_raw = all_sessions_raw[warmup_count : warmup_count + prediction_count]

    co2_median, light_median = compute_training_medians(warmup_sessions_raw)
    warmup_sessions = assign_context_codes(warmup_sessions_raw, co2_median, light_median)
    prediction_sessions = assign_context_codes(prediction_sessions_raw, co2_median, light_median)

    warmup_config = OccupancyRealV3Config(
        csv_path=config.csv_path,
        window_size=config.window_size,
        normalize=config.normalize,
        selector_seed=config.selector_seed,
        feedback_amount=config.feedback_amount,
        eval_feedback_fraction=1.0,
        packet_ttl=config.packet_ttl,
        forward_drain_cycles=config.forward_drain_cycles,
        feedback_drain_cycles=config.feedback_drain_cycles,
        topology_mode=config.topology_mode,
        context_mode=config.context_mode,
        ingress_mode=config.ingress_mode,
        summary_only=True,
    )
    prediction_config = OccupancyRealV3Config(
        csv_path=config.csv_path,
        window_size=config.window_size,
        normalize=config.normalize,
        selector_seed=config.selector_seed,
        feedback_amount=config.feedback_amount,
        eval_feedback_fraction=config.prediction_feedback_fraction,
        packet_ttl=config.packet_ttl,
        forward_drain_cycles=config.forward_drain_cycles,
        feedback_drain_cycles=config.feedback_drain_cycles,
        topology_mode=config.topology_mode,
        context_mode=config.context_mode,
        ingress_mode=config.ingress_mode,
        summary_only=True,
    )

    system = build_v3_system(warmup_config)
    warmup_results = [
        run_session_v3(
            system,
            session,
            config=warmup_config,
            training=True,
            episode_context_codes=_context_codes_for_session(
                session,
                context_mode=config.context_mode,
                co2_median=co2_median,
                light_median=light_median,
            ),
        )
        for session in warmup_sessions
    ]
    prediction_results = [
        run_session_v3(
            system,
            session,
            config=prediction_config,
            training=False,
            episode_context_codes=_context_codes_for_session(
                session,
                context_mode=config.context_mode,
                co2_median=co2_median,
                light_median=light_median,
            ),
        )
        for session in prediction_sessions
    ]

    warmup_episodes = [
        episode
        for session in warmup_results
        for episode in session["episode_results"]
    ]
    prediction_episodes = [
        episode
        for session in prediction_results
        for episode in session["episode_results"]
    ]

    result: dict[str, object] = {
        "light_config": asdict(config),
        "dataset_rows": len(all_episodes) + config.window_size - 1,
        "total_episodes": len(all_episodes),
        "total_sessions": len(all_sessions_raw),
        "warmup_session_count": len(warmup_sessions),
        "prediction_session_count": len(prediction_sessions),
        "co2_training_median": round(co2_median, 6),
        "light_training_median": round(light_median, 6),
        "warmup_inventory": session_inventory(warmup_sessions),
        "prediction_inventory": session_inventory(prediction_sessions),
        "warmup_summary": _summarize_episode_results_v3(warmup_episodes),
        "prediction_summary": _summarize_episode_results_v3(prediction_episodes),
        "recent_prediction_window": _lightweight_session_window(
            prediction_results,
            config.rolling_window,
        ),
        "final_system_summary": _compact_v3_system_summary(system.summarize()),
    }
    if not config.summary_only:
        result["warmup_session_results"] = warmup_results
        result["prediction_session_results"] = prediction_results
    return result


__all__ = [
    "OccupancyRealV3LightConfig",
    "run_occupancy_real_v3_light",
]
