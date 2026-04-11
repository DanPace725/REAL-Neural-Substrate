"""
session_splitter.py
-------------------
State-transition session segmentation and composite context derivation for
the v3 REAL occupancy experiment.

A "session" is a maximal contiguous run of windowed episodes with the same
occupancy label.  Within a session the correct routing decision is constant,
so the substrate's task is to orient to that decision as quickly as possible.
The carryover question is then: does prior substrate make that orientation
happen faster?

Context derivation
------------------
Each session receives a context code (0-3) computed from the mean normalized
CO2 and light values across all episodes in the session, compared against the
training-set medians:

    co2_bit   = 1 if session_co2_mean  > co2_median  else 0
    light_bit = 1 if session_light_mean > light_median else 0
    context_code = co2_bit * 2 + light_bit

This is multi-feature (two independent sensor axes), non-leaking (CO2+light
are correlated with but not identical to occupancy), and maps to the four
context values the ConnectionSubstrate supports natively (0, 1, 2, 3 via
dynamic registration).

Typical context-code semantics on the synth_v1 dataset:
    0  low CO2  + dim light   → overnight / unoccupied empty
    1  low CO2  + bright light → daylit but unoccupied
    2  high CO2 + dim light   → post-occupied evening fade
    3  high CO2 + bright light → active occupancy, peak-use period
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from statistics import mean, median
from typing import Sequence

from .dataset import FEATURE_COLUMNS

# Feature column indices within the normalized feature vector
_CO2_IDX = FEATURE_COLUMNS.index("co2")
_LIGHT_IDX = FEATURE_COLUMNS.index("light")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OccupancySession:
    """A contiguous run of windowed episodes sharing the same occupancy label."""
    session_index: int
    label: int                       # 0 = unoccupied, 1 = occupied
    episodes: tuple                  # tuple[OccupancyEpisode, ...]
    co2_mean: float                  # mean normalized CO2 across all episode packets
    light_mean: float                # mean normalized light across all episode packets
    context_code: int = -1           # -1 until assign_context_codes() is called


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _feature_mean_for_episodes(episodes: tuple, feature_name: str) -> float:
    """Mean of normalized_value for all packets with the given feature_name."""
    values = [
        spec.normalized_value
        for episode in episodes
        for spec in episode.packets
        if spec.feature_name == feature_name
    ]
    return mean(values) if values else 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def segment_into_sessions(episodes: Sequence) -> list[OccupancySession]:
    """
    Group consecutive same-label episodes into sessions.

    Sessions preserve temporal order.  Single-episode sessions are retained
    so every episode participates in at least one session.
    """
    if not episodes:
        return []

    sessions: list[OccupancySession] = []
    current_label = int(episodes[0].label)
    current_group: list = [episodes[0]]

    def _flush(group: list, label: int, index: int) -> OccupancySession:
        ep_tuple = tuple(group)
        return OccupancySession(
            session_index=index,
            label=label,
            episodes=ep_tuple,
            co2_mean=_feature_mean_for_episodes(ep_tuple, "co2"),
            light_mean=_feature_mean_for_episodes(ep_tuple, "light"),
        )

    for episode in episodes[1:]:
        label = int(episode.label)
        if label == current_label:
            current_group.append(episode)
        else:
            sessions.append(_flush(current_group, current_label, len(sessions)))
            current_label = label
            current_group = [episode]

    sessions.append(_flush(current_group, current_label, len(sessions)))
    return sessions


def compute_training_medians(train_sessions: Sequence[OccupancySession]) -> tuple[float, float]:
    """
    Return (co2_median, light_median) from the training session set.

    These thresholds are computed once from training data and applied to all
    sessions (train and eval) to avoid threshold drift or leakage.
    """
    co2_values = sorted(s.co2_mean for s in train_sessions)
    light_values = sorted(s.light_mean for s in train_sessions)

    def _median(values: list[float]) -> float:
        n = len(values)
        if n == 0:
            return 0.0
        if n % 2 == 1:
            return values[n // 2]
        return (values[n // 2 - 1] + values[n // 2]) / 2.0

    return _median(co2_values), _median(light_values)


def assign_context_codes(
    sessions: Sequence[OccupancySession],
    co2_median: float,
    light_median: float,
) -> list[OccupancySession]:
    """
    Return a new list of sessions with context_code set for each session.

    context_code = (co2_bit * 2) + light_bit
    where co2_bit = 1 if co2_mean > co2_median, else 0
    and   light_bit = 1 if light_mean > light_median, else 0
    """
    result: list[OccupancySession] = []
    for session in sessions:
        co2_bit = 1 if session.co2_mean > co2_median else 0
        light_bit = 1 if session.light_mean > light_median else 0
        code = co2_bit * 2 + light_bit
        result.append(replace(session, context_code=code))
    return result


def session_inventory(sessions: Sequence[OccupancySession]) -> dict:
    """
    Summarize session statistics for diagnostic output.

    Returns counts by label, counts by context_code, session length
    distribution (min/mean/max episodes per session), and context codes
    seen per label.
    """
    if not sessions:
        return {
            "session_count": 0,
            "by_label": {},
            "by_context_code": {},
            "episode_lengths": {"min": 0, "mean": 0.0, "max": 0},
            "context_codes_by_label": {},
        }

    by_label: dict[int, int] = {}
    by_context: dict[int, int] = {}
    lengths: list[int] = []
    ctx_by_label: dict[int, set] = {}

    for session in sessions:
        label = int(session.label)
        code = int(session.context_code)
        length = len(session.episodes)

        by_label[label] = by_label.get(label, 0) + 1
        by_context[code] = by_context.get(code, 0) + 1
        lengths.append(length)
        ctx_by_label.setdefault(label, set()).add(code)

    return {
        "session_count": len(sessions),
        "by_label": by_label,
        "by_context_code": by_context,
        "episode_lengths": {
            "min": min(lengths),
            "mean": round(mean(lengths), 2),
            "max": max(lengths),
        },
        "context_codes_by_label": {
            label: sorted(codes)
            for label, codes in ctx_by_label.items()
        },
    }


__all__ = [
    "OccupancySession",
    "assign_context_codes",
    "compute_training_medians",
    "segment_into_sessions",
    "session_inventory",
]
