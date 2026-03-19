from __future__ import annotations

import itertools
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import json

from .admission import AdmissionSubstrate
from .models import FeedbackPulse, NodeRuntimeState, SignalPacket, SignalSpec
from .topology import GrowthProposal, MorphogenesisConfig, TopologyManager, TopologyState

TRANSFORM_NAMES = ("identity", "rotate_left_1", "xor_mask_1010", "xor_mask_0101")
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
TASK_CONTEXT_MATCH_FLOOR = 0.75
DEBT_ACTIVATION_CREDIT = 0.30
DEBT_ACTIVATION_CONTEXT_CREDIT = 0.22
DEBT_ACTIVATION_EXISTING = 0.18
LATENT_CONTEXT_CONFIDENCE_THRESHOLD = 0.55
LATENT_CONTEXT_PROMOTION_THRESHOLD = 0.78
LATENT_CONTEXT_PROMOTION_STREAK = 2
LATENT_CONTEXT_EVIDENCE_DECAY = 0.88
LATENT_CONTEXT_ROUTE_GAIN = 0.08
LATENT_CONTEXT_FEEDBACK_GAIN = 0.42
LATENT_CONTEXT_EVIDENCE_SATURATION = 0.50
LATENT_EVIDENCE_CHANNELS = (
    "source_route",
    "downstream_route",
    "source_feedback",
    "downstream_feedback",
)
LATENT_SOURCE_COMMITMENT_BOOST = 0.12
LATENT_SOURCE_COMMITMENT_DAMP = 0.82
LATENT_SOURCE_FEEDBACK_REWRITE_MARGIN = 0.18
LATENT_TRANSFER_ADAPTATION_BOOST_SCALE = 0.05
LATENT_TRANSFER_ADAPTATION_DAMP_BLEND = 0.95
LATENT_TRANSFER_ADAPTATION_REWRITE_SCALE = 0.10
LATENT_TRANSFER_EFFECTIVE_THRESHOLD_BOOST = 0.18
LATENT_GROWTH_IDLE_TASK_WINDOW = 1
CAPABILITY_LATENT_IDLE_TASK_WINDOW = 12
CAPABILITY_POLICIES = (
    "fixed-visible",
    "fixed-latent",
    "growth-visible",
    "growth-latent",
    "self-selected",
)


def _edge_id(source_id: str, target_id: str) -> str:
    return f"{source_id}->{target_id}"


def _normalize_transform_name(transform_name: str | None) -> str:
    return str(transform_name or "identity")


def _context_credit_key(transform_name: str, context_bit: int) -> str:
    return f"{transform_name}:context_{int(context_bit)}"


def _branch_debt_key(neighbor_id: str, transform_name: str) -> str:
    return f"{neighbor_id}:{transform_name}"


def _context_branch_debt_key(neighbor_id: str, transform_name: str, context_bit: int) -> str:
    return f"{neighbor_id}:{transform_name}:context_{int(context_bit)}"


def _branch_context_debt_key(neighbor_id: str, context_bit: int) -> str:
    return f"{neighbor_id}:context_{int(context_bit)}"


def _parity_bits(bits: Sequence[int] | None) -> int | None:
    if bits is None:
        return None
    normalized = [1 if int(bit) else 0 for bit in bits]
    if not normalized:
        return None
    return sum(normalized) % 2


def _canonical_task_family(task_id: str | None) -> str | None:
    if task_id is None:
        return None
    task_key = str(task_id)
    for family in ("task_a", "task_b", "task_c"):
        if task_key == family or task_key.endswith(f"_{family}"):
            return family
    return task_key


def _task_transform_map(task_id: str | None) -> Dict[int, str] | None:
    task_family = _canonical_task_family(task_id)
    if task_family not in _CURRENT_TRANSFORM_MAPS:
        return None
    task_key = str(task_id or "")
    if task_key.startswith("ceiling_c1_"):
        base = _CURRENT_TRANSFORM_MAPS[task_family]
        return {0: base[0], 1: base[1], 2: base[0], 3: base[1]}
    if task_key.startswith("ceiling_c2_"):
        return _AMBIGUOUS_3_TRANSFORM_MAPS[task_family]
    if task_key.startswith("ceiling_c3_") or task_key.startswith("ceiling_c4_"):
        return _AMBIGUOUS_4_TRANSFORM_MAPS[task_family]
    return _CURRENT_TRANSFORM_MAPS[task_family]


def _task_context_candidates(task_id: str | None) -> tuple[int, ...]:
    transform_map = _task_transform_map(task_id)
    if not transform_map:
        return (0, 1)
    return tuple(sorted(int(context_bit) for context_bit in transform_map))


def _sequence_window_for_task(task_id: str | None) -> int | None:
    task_key = str(task_id or "")
    if task_key.startswith("ceiling_b1"):
        return 1
    if task_key.startswith("ceiling_b2"):
        return 2
    if task_key.startswith("ceiling_b3"):
        return 4
    if task_key.startswith("ceiling_b4"):
        return 8
    return None


def _sequence_context_estimate_for_task(
    task_id: str | None,
    *,
    prior_parities: Sequence[int] | None,
) -> tuple[int | None, float]:
    task_key = str(task_id or "")
    parity_history = [int(bit) & 1 for bit in list(prior_parities or [])]
    if task_key.startswith("ceiling_c"):
        if len(parity_history) < 2:
            return None, 0.0
        low = int(parity_history[-1])
        high = int(parity_history[-2])
        return int(low + 2 * high), 0.95
    sequence_window = _sequence_window_for_task(task_id)
    if sequence_window is not None:
        relevant = parity_history[-sequence_window:]
        padded = [0 for _ in range(max(sequence_window - len(relevant), 0))] + relevant
        return int(sum(padded) % 2), 0.95
    if not parity_history:
        return None, 0.0
    return int(parity_history[-1]), 0.95


def _context_threshold_scale(context_count: int) -> float:
    if context_count <= 2:
        return 1.0
    return max(0.5, (2.0 / max(float(context_count), 2.0)) ** 0.5)


@dataclass
class LatentTaskState:
    task_id: str
    context_evidence: Dict[int, float] = field(default_factory=dict)
    transform_evidence: Dict[str, float] = field(
        default_factory=lambda: {name: 0.0 for name in TRANSFORM_NAMES}
    )
    context_evidence_by_channel: Dict[str, Dict[int, float]] = field(
        default_factory=lambda: {
            channel: {}
            for channel in LATENT_EVIDENCE_CHANNELS
        }
    )
    transform_evidence_by_channel: Dict[str, Dict[str, float]] = field(
        default_factory=lambda: {
            channel: {name: 0.0 for name in TRANSFORM_NAMES}
            for channel in LATENT_EVIDENCE_CHANNELS
        }
    )
    dominant_context: int | None = None
    confidence: float = 0.0
    total_evidence: float = 0.0
    observation_streak: int = 0
    last_observed_cycle: int = -1
    last_observed_context: int | None = None
    last_packet_id: str | None = None
    last_input_bits: List[int] = field(default_factory=list)
    sequence_context_estimate: int | None = None
    sequence_context_confidence: float = 0.0
    sequence_recent_parities: List[int] = field(default_factory=list)
    sequence_prev_parity: int | None = None
    sequence_prev_bits: List[int] = field(default_factory=list)
    sequence_change_ratio: float = 0.0
    sequence_repeat_input: float = 0.0
    sequence_delta_bits: List[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "context_evidence": {
                str(key): float(value)
                for key, value in self.context_evidence.items()
            },
            "transform_evidence": {
                str(key): float(value)
                for key, value in self.transform_evidence.items()
            },
            "context_evidence_by_channel": {
                channel: {
                    str(key): float(value)
                    for key, value in channel_values.items()
                }
                for channel, channel_values in self.context_evidence_by_channel.items()
            },
            "transform_evidence_by_channel": {
                channel: {
                    str(key): float(value)
                    for key, value in channel_values.items()
                }
                for channel, channel_values in self.transform_evidence_by_channel.items()
            },
            "dominant_context": self.dominant_context,
            "confidence": self.confidence,
            "total_evidence": self.total_evidence,
            "observation_streak": self.observation_streak,
            "last_observed_cycle": self.last_observed_cycle,
            "last_observed_context": self.last_observed_context,
            "last_packet_id": self.last_packet_id,
            "last_input_bits": list(self.last_input_bits),
            "sequence_context_estimate": self.sequence_context_estimate,
            "sequence_context_confidence": self.sequence_context_confidence,
            "sequence_recent_parities": list(self.sequence_recent_parities),
            "sequence_prev_parity": self.sequence_prev_parity,
            "sequence_prev_bits": list(self.sequence_prev_bits),
            "sequence_change_ratio": self.sequence_change_ratio,
            "sequence_repeat_input": self.sequence_repeat_input,
            "sequence_delta_bits": list(self.sequence_delta_bits),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "LatentTaskState":
        state = cls(task_id=str(payload.get("task_id", "")))
        state.context_evidence = {
            int(key): float(value)
            for key, value in dict(payload.get("context_evidence", {})).items()
        }
        state.transform_evidence = {
            name: float(dict(payload.get("transform_evidence", {})).get(name, 0.0))
            for name in TRANSFORM_NAMES
        }
        channel_context_payload = dict(payload.get("context_evidence_by_channel", {}))
        state.context_evidence_by_channel = {
            channel: {
                int(key): float(value)
                for key, value in dict(channel_context_payload.get(channel, {})).items()
            }
            for channel in LATENT_EVIDENCE_CHANNELS
        }
        channel_transform_payload = dict(payload.get("transform_evidence_by_channel", {}))
        state.transform_evidence_by_channel = {
            channel: {
                name: float(dict(channel_transform_payload.get(channel, {})).get(name, 0.0))
                for name in TRANSFORM_NAMES
            }
            for channel in LATENT_EVIDENCE_CHANNELS
        }
        state.dominant_context = payload.get("dominant_context")
        if state.dominant_context is not None:
            state.dominant_context = int(state.dominant_context)
        state.confidence = float(payload.get("confidence", 0.0))
        state.total_evidence = float(payload.get("total_evidence", 0.0))
        state.observation_streak = int(payload.get("observation_streak", 0))
        state.last_observed_cycle = int(payload.get("last_observed_cycle", -1))
        state.last_observed_context = payload.get("last_observed_context")
        if state.last_observed_context is not None:
            state.last_observed_context = int(state.last_observed_context)
        state.last_packet_id = payload.get("last_packet_id")
        state.last_input_bits = [int(bit) for bit in payload.get("last_input_bits", [])]
        state.sequence_context_estimate = payload.get("sequence_context_estimate")
        if state.sequence_context_estimate is not None:
            state.sequence_context_estimate = int(state.sequence_context_estimate)
        state.sequence_context_confidence = float(payload.get("sequence_context_confidence", 0.0))
        state.sequence_recent_parities = [
            int(bit)
            for bit in payload.get("sequence_recent_parities", [])
        ]
        state.sequence_prev_parity = payload.get("sequence_prev_parity")
        if state.sequence_prev_parity is not None:
            state.sequence_prev_parity = int(state.sequence_prev_parity)
        state.sequence_prev_bits = [int(bit) for bit in payload.get("sequence_prev_bits", [])]
        state.sequence_change_ratio = float(payload.get("sequence_change_ratio", 0.0))
        state.sequence_repeat_input = float(payload.get("sequence_repeat_input", 0.0))
        state.sequence_delta_bits = [int(bit) for bit in payload.get("sequence_delta_bits", [])]
        return state


@dataclass
class LatentContextTracker:
    task_states: Dict[str, LatentTaskState] = field(default_factory=dict)
    evidence_decay: float = LATENT_CONTEXT_EVIDENCE_DECAY
    route_gain: float = LATENT_CONTEXT_ROUTE_GAIN
    feedback_gain: float = LATENT_CONTEXT_FEEDBACK_GAIN
    confidence_threshold: float = LATENT_CONTEXT_CONFIDENCE_THRESHOLD
    promotion_threshold: float = LATENT_CONTEXT_PROMOTION_THRESHOLD
    promotion_streak: int = LATENT_CONTEXT_PROMOTION_STREAK

    def _state_for(self, task_id: str | None) -> LatentTaskState | None:
        if not task_id:
            return None
        task_key = str(task_id)
        state = self.task_states.get(task_key)
        if state is None:
            state = LatentTaskState(task_id=task_key)
            self.task_states[task_key] = state
        self._ensure_task_contexts(state)
        return state

    def _context_ids(self, state: LatentTaskState) -> tuple[int, ...]:
        context_ids = set(_task_context_candidates(state.task_id))
        context_ids.update(int(context_bit) for context_bit in state.context_evidence)
        for channel_values in state.context_evidence_by_channel.values():
            context_ids.update(int(context_bit) for context_bit in channel_values)
        return tuple(sorted(context_ids))

    def _ensure_task_contexts(self, state: LatentTaskState) -> tuple[int, ...]:
        context_ids = self._context_ids(state)
        for context_bit in context_ids:
            state.context_evidence.setdefault(context_bit, 0.0)
        for channel in LATENT_EVIDENCE_CHANNELS:
            channel_context = state.context_evidence_by_channel.setdefault(channel, {})
            for context_bit in context_ids:
                channel_context.setdefault(context_bit, 0.0)
        return context_ids

    def _effective_confidence_threshold(self, state: LatentTaskState, *, adaptation_phase: float = 0.0) -> float:
        threshold_scale = _context_threshold_scale(len(self._context_ids(state)))
        base_threshold = self.confidence_threshold + adaptation_phase * LATENT_TRANSFER_EFFECTIVE_THRESHOLD_BOOST
        return max(0.0, min(1.0, base_threshold * threshold_scale))

    def _promotion_confidence_threshold(self, state: LatentTaskState) -> float:
        threshold_scale = _context_threshold_scale(len(self._context_ids(state)))
        return max(0.0, min(1.0, self.promotion_threshold * threshold_scale))

    def _growth_confidence_threshold(self, state: LatentTaskState) -> float:
        return max(self.promotion_threshold, self._promotion_confidence_threshold(state))

    def _recompute(self, state: LatentTaskState) -> None:
        context_ids = self._ensure_task_contexts(state)
        for context_bit in context_ids:
            state.context_evidence[context_bit] = sum(
                float(state.context_evidence_by_channel.get(channel, {}).get(context_bit, 0.0))
                for channel in LATENT_EVIDENCE_CHANNELS
            )
        for transform_name in TRANSFORM_NAMES:
            state.transform_evidence[transform_name] = sum(
                float(state.transform_evidence_by_channel.get(channel, {}).get(transform_name, 0.0))
                for channel in LATENT_EVIDENCE_CHANNELS
            )
        state.total_evidence = max(
            0.0,
            sum(float(state.context_evidence.get(context_bit, 0.0)) for context_bit in context_ids),
        )
        if state.total_evidence <= 1e-9:
            state.dominant_context = None
            state.confidence = 0.0
            return
        ranked_contexts = sorted(
            (
                (float(state.context_evidence.get(context_bit, 0.0)), int(context_bit))
                for context_bit in context_ids
            ),
            reverse=True,
        )
        dominant_score, dominant_context = ranked_contexts[0]
        runner_up_score = ranked_contexts[1][0] if len(ranked_contexts) > 1 else 0.0
        diff = max(0.0, dominant_score - runner_up_score)
        state.dominant_context = dominant_context
        purity = max(0.0, min(1.0, diff / max(state.total_evidence, 1e-9)))
        evidence_scale = max(0.0, min(1.0, state.total_evidence / LATENT_CONTEXT_EVIDENCE_SATURATION))
        state.confidence = purity * evidence_scale

    def _channel_estimate_confidence(
        self,
        state: LatentTaskState,
        channel: str,
    ) -> tuple[int | None, float, float]:
        self._ensure_task_contexts(state)
        channel_values = state.context_evidence_by_channel.get(channel, {})
        context_ids = self._context_ids(state)
        total = sum(float(channel_values.get(context_bit, 0.0)) for context_bit in context_ids)
        if total <= 1e-9:
            return None, 0.0, 0.0
        ranked_contexts = sorted(
            (
                (float(channel_values.get(context_bit, 0.0)), int(context_bit))
                for context_bit in context_ids
            ),
            reverse=True,
        )
        top_score, estimate = ranked_contexts[0]
        runner_up_score = ranked_contexts[1][0] if len(ranked_contexts) > 1 else 0.0
        diff = max(0.0, top_score - runner_up_score)
        purity = max(0.0, min(1.0, diff / max(total, 1e-9)))
        evidence_scale = max(0.0, min(1.0, total / LATENT_CONTEXT_EVIDENCE_SATURATION))
        confidence = purity * evidence_scale
        return estimate, confidence, total

    def _reinforce_source_commitment(
        self,
        state: LatentTaskState,
        *,
        adaptation_phase: float = 0.0,
    ) -> None:
        route_estimate, route_confidence, _ = self._channel_estimate_confidence(state, "source_route")
        feedback_estimate, feedback_confidence, _ = self._channel_estimate_confidence(state, "source_feedback")
        if feedback_estimate is None:
            self._recompute(state)
            return
        phase = max(0.0, min(1.0, adaptation_phase))
        commitment_boost = LATENT_SOURCE_COMMITMENT_BOOST * (
            (1.0 - phase) + phase * LATENT_TRANSFER_ADAPTATION_BOOST_SCALE
        )
        damp_factor = LATENT_SOURCE_COMMITMENT_DAMP + phase * (
            1.0 - LATENT_SOURCE_COMMITMENT_DAMP
        ) * LATENT_TRANSFER_ADAPTATION_DAMP_BLEND
        rewrite_margin = LATENT_SOURCE_FEEDBACK_REWRITE_MARGIN * (
            (1.0 - phase) + phase * LATENT_TRANSFER_ADAPTATION_REWRITE_SCALE
        )
        expected_transform = _expected_transform_for_task(state.task_id, int(feedback_estimate))
        source_route_context = state.context_evidence_by_channel.setdefault(
            "source_route",
            {0: 0.0, 1: 0.0},
        )
        source_feedback_context = state.context_evidence_by_channel.setdefault(
            "source_feedback",
            {0: 0.0, 1: 0.0},
        )
        source_route_transforms = state.transform_evidence_by_channel.setdefault(
            "source_route",
            {name: 0.0 for name in TRANSFORM_NAMES},
        )
        source_feedback_transforms = state.transform_evidence_by_channel.setdefault(
            "source_feedback",
            {name: 0.0 for name in TRANSFORM_NAMES},
        )
        if (
            route_estimate is not None
            and route_estimate == feedback_estimate
            and feedback_confidence >= 0.30
        ):
            boost = commitment_boost * max(0.35, min(route_confidence, feedback_confidence))
            context_ids = self._context_ids(state)
            source_route_context[int(feedback_estimate)] = max(
                0.0,
                source_route_context.get(int(feedback_estimate), 0.0) + boost,
            )
            source_feedback_context[int(feedback_estimate)] = max(
                0.0,
                source_feedback_context.get(int(feedback_estimate), 0.0) + 0.65 * boost,
            )
            for losing_context in context_ids:
                if losing_context == int(feedback_estimate):
                    continue
                source_route_context[losing_context] = max(
                    0.0,
                    source_route_context.get(losing_context, 0.0) * damp_factor,
                )
                source_feedback_context[losing_context] = max(
                    0.0,
                    source_feedback_context.get(losing_context, 0.0)
                    * (0.94 + 0.04 * (1.0 - feedback_confidence)),
                )
            if expected_transform is not None:
                source_route_transforms[expected_transform] = max(
                    0.0,
                    source_route_transforms.get(expected_transform, 0.0) + boost,
                )
                source_feedback_transforms[expected_transform] = max(
                    0.0,
                    source_feedback_transforms.get(expected_transform, 0.0) + 0.65 * boost,
                )
        elif (
            route_estimate is not None
            and route_estimate != feedback_estimate
            and feedback_confidence >= route_confidence + rewrite_margin
        ):
            losing_context = int(route_estimate)
            winning_context = int(feedback_estimate)
            source_route_context[losing_context] = max(
                0.0,
                source_route_context.get(losing_context, 0.0) * damp_factor,
            )
            source_route_context[winning_context] = max(
                0.0,
                source_route_context.get(winning_context, 0.0)
                + commitment_boost * feedback_confidence,
            )
            if expected_transform is not None:
                source_route_transforms[expected_transform] = max(
                    0.0,
                    source_route_transforms.get(expected_transform, 0.0)
                    + commitment_boost * feedback_confidence,
                )
        self._recompute(state)

    def _apply_decay(self, state: LatentTaskState) -> None:
        context_ids = self._ensure_task_contexts(state)
        for context_bit in context_ids:
            state.context_evidence[context_bit] = max(
                0.0,
                float(state.context_evidence.get(context_bit, 0.0)) * self.evidence_decay,
            )
        for channel in LATENT_EVIDENCE_CHANNELS:
            channel_context = state.context_evidence_by_channel.setdefault(channel, {})
            for context_bit in context_ids:
                channel_context[context_bit] = max(
                    0.0,
                    float(channel_context.get(context_bit, 0.0)) * self.evidence_decay,
                )
        for transform_name in TRANSFORM_NAMES:
            state.transform_evidence[transform_name] = max(
                0.0,
                float(state.transform_evidence.get(transform_name, 0.0)) * self.evidence_decay,
            )
        for channel in LATENT_EVIDENCE_CHANNELS:
            channel_transforms = state.transform_evidence_by_channel.setdefault(
                channel,
                {name: 0.0 for name in TRANSFORM_NAMES},
            )
            for transform_name in TRANSFORM_NAMES:
                channel_transforms[transform_name] = max(
                    0.0,
                    float(channel_transforms.get(transform_name, 0.0)) * self.evidence_decay,
                )

    def _apply_transform_signal(
        self,
        state: LatentTaskState,
        transform_name: str,
        signal: float,
        *,
        channel: str,
    ) -> None:
        transform = _normalize_transform_name(transform_name)
        self._apply_decay(state)
        state.transform_evidence[transform] = max(
            0.0,
            state.transform_evidence.get(transform, 0.0) + signal,
        )
        channel_transforms = state.transform_evidence_by_channel.setdefault(
            channel,
            {name: 0.0 for name in TRANSFORM_NAMES},
        )
        channel_transforms[transform] = max(
            0.0,
            channel_transforms.get(transform, 0.0) + signal,
        )
        for context_bit in _task_context_candidates(state.task_id):
            expected = _expected_transform_for_task(state.task_id, context_bit)
            if expected == transform:
                state.context_evidence[context_bit] = max(
                    0.0,
                    state.context_evidence.get(context_bit, 0.0) + signal,
                )
                channel_context = state.context_evidence_by_channel.setdefault(
                    channel,
                    {},
                )
                channel_context[context_bit] = max(
                    0.0,
                    channel_context.get(context_bit, 0.0) + signal,
                )
        self._recompute(state)

    def record_route(
        self,
        task_id: str | None,
        transform_name: str,
        *,
        is_source: bool = False,
        adaptation_phase: float = 0.0,
    ) -> None:
        state = self._state_for(task_id)
        if state is None:
            return
        self._apply_transform_signal(
            state,
            transform_name,
            self.route_gain,
            channel="source_route" if is_source else "downstream_route",
        )
        if is_source:
            self._reinforce_source_commitment(state, adaptation_phase=adaptation_phase)

    def record_feedback(
        self,
        task_id: str | None,
        transform_name: str,
        *,
        bit_match_ratio: float,
        credit_signal: float,
        is_source: bool = False,
        adaptation_phase: float = 0.0,
    ) -> None:
        state = self._state_for(task_id)
        if state is None:
            return
        signed_quality = max(-1.0, min(1.0, (bit_match_ratio - 0.5) * 2.0))
        signal = self.feedback_gain * max(0.20, credit_signal) * signed_quality
        self._apply_transform_signal(
            state,
            transform_name,
            signal,
            channel="source_feedback" if is_source else "downstream_feedback",
        )
        if is_source:
            self._reinforce_source_commitment(state, adaptation_phase=adaptation_phase)

    def observe_packet(
        self,
        task_id: str | None,
        packet_id: str | None,
        input_bits: Sequence[int] | None,
    ) -> None:
        state = self._state_for(task_id)
        if state is None or packet_id is None:
            return
        if state.last_packet_id == packet_id:
            return
        current_bits = [1 if int(bit) else 0 for bit in list(input_bits or [])]
        current_parity = _parity_bits(current_bits)
        prior_parities = list(state.sequence_recent_parities)
        prior_parity = prior_parities[-1] if prior_parities else None
        width = max(len(current_bits), len(state.last_input_bits), 4)
        padded_current = current_bits + [0] * max(0, width - len(current_bits))
        padded_previous = state.last_input_bits + [0] * max(0, width - len(state.last_input_bits))
        delta_bits = [
            int(current_bit != previous_bit)
            for current_bit, previous_bit in zip(padded_current, padded_previous)
        ]
        state.sequence_context_estimate, state.sequence_context_confidence = _sequence_context_estimate_for_task(
            state.task_id,
            prior_parities=prior_parities,
        )
        state.sequence_prev_parity = prior_parity
        state.sequence_prev_bits = list(padded_previous[:4])
        state.sequence_delta_bits = list(delta_bits[:4])
        state.sequence_change_ratio = sum(delta_bits) / max(len(delta_bits), 1)
        state.sequence_repeat_input = 1.0 if state.last_input_bits and current_bits == state.last_input_bits else 0.0
        state.last_packet_id = str(packet_id)
        state.last_input_bits = current_bits
        if current_parity is not None:
            state.sequence_recent_parities = (prior_parities + [int(current_parity)])[-8:]

    def observe_task(self, task_id: str | None, cycle: int) -> dict[str, object]:
        state = self._state_for(task_id)
        if state is None:
            return self.snapshot(task_id)
        if state.last_observed_cycle != cycle:
            if state.dominant_context is None:
                state.observation_streak = 0
                state.last_observed_context = None
            elif state.last_observed_context == state.dominant_context:
                state.observation_streak += 1
            else:
                state.observation_streak = 1
                state.last_observed_context = state.dominant_context
            state.last_observed_cycle = cycle
        return self.snapshot(task_id)

    def snapshot(self, task_id: str | None) -> dict[str, object]:
        state = self._state_for(task_id)
        if state is None:
            context_ids = _task_context_candidates(task_id)
            return {
                "available": False,
                "estimate": None,
                "confidence": 0.0,
                "context_count": len(context_ids),
                "context_ids": list(context_ids),
                "promotion_threshold": LATENT_CONTEXT_PROMOTION_THRESHOLD * _context_threshold_scale(len(context_ids)),
                "promotion_ready": False,
                "growth_promotion_threshold": LATENT_CONTEXT_PROMOTION_THRESHOLD,
                "growth_ready": False,
                "observation_streak": 0,
                "sequence_available": False,
                "sequence_context_estimate": None,
                "sequence_context_confidence": 0.0,
                "sequence_prev_parity": None,
                "sequence_change_ratio": 0.0,
                "sequence_repeat_input": 0.0,
                "sequence_prev_bits": [],
                "sequence_delta_bits": [],
                "transform_evidence": {name: 0.0 for name in TRANSFORM_NAMES},
                "channel_context_evidence": {
                    channel: {context_bit: 0.0 for context_bit in context_ids}
                    for channel in LATENT_EVIDENCE_CHANNELS
                },
                "channel_transform_evidence": {
                    channel: {name: 0.0 for name in TRANSFORM_NAMES}
                    for channel in LATENT_EVIDENCE_CHANNELS
                },
                "channel_context_confidence": {
                    channel: 0.0
                    for channel in LATENT_EVIDENCE_CHANNELS
                },
                "channel_context_estimate": {
                    channel: None
                    for channel in LATENT_EVIDENCE_CHANNELS
                },
            }
        context_ids = self._ensure_task_contexts(state)
        sequence_available = state.sequence_context_estimate is not None and state.sequence_context_confidence > 0.0
        available = state.dominant_context is not None and state.total_evidence > 0.0
        estimate = state.dominant_context
        confidence = state.confidence
        promotion_threshold = self._promotion_confidence_threshold(state)
        growth_promotion_threshold = self._growth_confidence_threshold(state)
        promotion_ready = bool(
            state.dominant_context is not None
            and state.confidence >= promotion_threshold
            and state.observation_streak >= self.promotion_streak
        )
        growth_ready = bool(
            state.dominant_context is not None
            and state.confidence >= growth_promotion_threshold
            and state.observation_streak >= self.promotion_streak
        )
        channel_context_confidence: dict[str, float] = {}
        channel_context_estimate: dict[str, int | None] = {}
        for channel in LATENT_EVIDENCE_CHANNELS:
            channel_values = state.context_evidence_by_channel.get(channel, {})
            total = sum(float(channel_values.get(context_bit, 0.0)) for context_bit in context_ids)
            if total <= 1e-9:
                channel_context_confidence[channel] = 0.0
                channel_context_estimate[channel] = None
                continue
            ranked_contexts = sorted(
                (
                    (float(channel_values.get(context_bit, 0.0)), int(context_bit))
                    for context_bit in context_ids
                ),
                reverse=True,
            )
            top_score, estimate = ranked_contexts[0]
            runner_up_score = ranked_contexts[1][0] if len(ranked_contexts) > 1 else 0.0
            diff = max(0.0, top_score - runner_up_score)
            channel_context_confidence[channel] = max(0.0, min(1.0, diff / max(total, 1e-9)))
            channel_context_estimate[channel] = estimate
        return {
            "available": available,
            "estimate": estimate,
            "confidence": confidence,
            "context_count": len(context_ids),
            "context_ids": list(context_ids),
            "promotion_threshold": promotion_threshold,
            "promotion_ready": promotion_ready,
            "growth_promotion_threshold": growth_promotion_threshold,
            "growth_ready": growth_ready,
            "observation_streak": state.observation_streak,
            "sequence_available": sequence_available,
            "sequence_context_estimate": state.sequence_context_estimate,
            "sequence_context_confidence": state.sequence_context_confidence,
            "sequence_prev_parity": state.sequence_prev_parity,
            "sequence_change_ratio": state.sequence_change_ratio,
            "sequence_repeat_input": state.sequence_repeat_input,
            "sequence_prev_bits": list(state.sequence_prev_bits),
            "sequence_delta_bits": list(state.sequence_delta_bits),
            "transform_evidence": {
                name: max(0.0, min(1.0, float(state.transform_evidence.get(name, 0.0))))
                for name in TRANSFORM_NAMES
            },
            "channel_context_evidence": {
                channel: {
                    context_bit: max(
                        0.0,
                        min(1.0, float(state.context_evidence_by_channel.get(channel, {}).get(context_bit, 0.0))),
                    )
                    for context_bit in context_ids
                }
                for channel in LATENT_EVIDENCE_CHANNELS
            },
            "channel_transform_evidence": {
                channel: {
                    name: max(
                        0.0,
                        min(1.0, float(state.transform_evidence_by_channel.get(channel, {}).get(name, 0.0))),
                    )
                    for name in TRANSFORM_NAMES
                }
                for channel in LATENT_EVIDENCE_CHANNELS
            },
            "channel_context_confidence": channel_context_confidence,
            "channel_context_estimate": channel_context_estimate,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "task_states": {
                task_id: state.to_dict()
                for task_id, state in self.task_states.items()
            }
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object] | None) -> "LatentContextTracker":
        tracker = cls()
        if not payload:
            return tracker
        tracker.task_states = {
            str(task_id): LatentTaskState.from_dict(dict(state_payload))
            for task_id, state_payload in dict(payload.get("task_states", {})).items()
        }
        return tracker


@dataclass
class CapabilityControlConfig:
    latent_support_decay: float = 0.88
    latent_support_gain: float = 0.18
    latent_activation_threshold: float = 0.44
    latent_visible_suppression_threshold: float = 0.58
    latent_maintenance_cost: float = 0.006
    growth_support_decay: float = 0.90
    growth_support_gain: float = 0.10
    growth_activation_threshold: float = 0.62
    growth_stability_threshold: float = 0.48
    growth_maintenance_cost: float = 0.005


@dataclass
class CapabilityState:
    latent_recruitment_pressure: float = 0.0
    latent_confidence_estimate: float = 0.0
    latent_support: float = 0.0
    latent_enabled: bool = False
    visible_context_trust: float = 1.0
    growth_recruitment_pressure: float = 0.0
    growth_stabilization_readiness: float = 0.0
    growth_support: float = 0.0
    growth_enabled: bool = False
    latent_recruitment_cycles: List[int] = field(default_factory=list)
    growth_recruitment_cycles: List[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "latent_recruitment_pressure": float(self.latent_recruitment_pressure),
            "latent_confidence_estimate": float(self.latent_confidence_estimate),
            "latent_support": float(self.latent_support),
            "latent_enabled": bool(self.latent_enabled),
            "visible_context_trust": float(self.visible_context_trust),
            "growth_recruitment_pressure": float(self.growth_recruitment_pressure),
            "growth_stabilization_readiness": float(self.growth_stabilization_readiness),
            "growth_support": float(self.growth_support),
            "growth_enabled": bool(self.growth_enabled),
            "latent_recruitment_cycles": [int(value) for value in self.latent_recruitment_cycles],
            "growth_recruitment_cycles": [int(value) for value in self.growth_recruitment_cycles],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object] | None) -> "CapabilityState":
        if not payload:
            return cls()
        return cls(
            latent_recruitment_pressure=float(payload.get("latent_recruitment_pressure", 0.0)),
            latent_confidence_estimate=float(payload.get("latent_confidence_estimate", 0.0)),
            latent_support=float(payload.get("latent_support", 0.0)),
            latent_enabled=bool(payload.get("latent_enabled", False)),
            visible_context_trust=float(payload.get("visible_context_trust", 1.0)),
            growth_recruitment_pressure=float(payload.get("growth_recruitment_pressure", 0.0)),
            growth_stabilization_readiness=float(payload.get("growth_stabilization_readiness", 0.0)),
            growth_support=float(payload.get("growth_support", 0.0)),
            growth_enabled=bool(payload.get("growth_enabled", False)),
            latent_recruitment_cycles=[
                int(value) for value in payload.get("latent_recruitment_cycles", [])
            ],
            growth_recruitment_cycles=[
                int(value) for value in payload.get("growth_recruitment_cycles", [])
            ],
        )


def _apply_transform(bits: Sequence[int], transform_name: str | None) -> List[int]:
    transform = _normalize_transform_name(transform_name)
    payload = [1 if int(bit) else 0 for bit in bits]
    if transform == "identity":
        return list(payload)
    if transform == "rotate_left_1":
        if not payload:
            return []
        return payload[1:] + payload[:1]
    if transform == "xor_mask_1010":
        mask = [1, 0, 1, 0]
        return [payload[index] ^ mask[index] for index in range(min(len(payload), len(mask)))]
    if transform == "xor_mask_0101":
        mask = [0, 1, 0, 1]
        return [payload[index] ^ mask[index] for index in range(min(len(payload), len(mask)))]
    raise ValueError(f"Unsupported transform '{transform}'")


def _target_bits_for_task(
    input_bits: Sequence[int],
    *,
    context_bit: int | None,
    task_id: str | None,
) -> List[int] | None:
    if not input_bits or task_id is None or context_bit is None:
        return None
    transform_map = _task_transform_map(task_id)
    if transform_map is not None and int(context_bit) in transform_map:
        transform = transform_map[int(context_bit)]
        return _apply_transform(input_bits, transform)
    return None


def _expected_transform_for_task(
    task_id: str | None,
    context_bit: int | None,
) -> str | None:
    if task_id is None or context_bit is None:
        return None
    transform_map = _task_transform_map(task_id)
    if transform_map is not None:
        return transform_map.get(int(context_bit))
    return None


def _candidate_transforms_for_task(task_id: str | None) -> tuple[str, ...]:
    transform_map = _task_transform_map(task_id)
    if transform_map is not None:
        return tuple(dict.fromkeys(transform_map.values()))
    return tuple()


def _bit_match_ratio(observed_bits: Sequence[int], target_bits: Sequence[int]) -> float:
    if not target_bits:
        return 0.0
    matched = 0
    for observed, target in zip(observed_bits, target_bits):
        matched += 1 if int(observed) == int(target) else 0
    return matched / max(len(target_bits), 1)


def _quality_scaled_credit(bit_match_ratio: float, *, floor: float = TASK_CONTEXT_MATCH_FLOOR) -> float:
    quality = max(0.0, min(1.0, bit_match_ratio))
    if quality <= floor:
        return 0.0
    return min(1.0, (quality - floor) / max(1.0 - floor, 1e-9))


def _transform_matches_resolved_context(
    task_id: str | None,
    context_bit: int | None,
    transform_name: str,
) -> bool:
    expected_transform = _expected_transform_for_task(task_id, context_bit)
    if expected_transform is None:
        return False
    return expected_transform == _normalize_transform_name(transform_name)


@dataclass
class RoutingEnvironment:
    adjacency: Dict[str, tuple[str, ...]]
    positions: Dict[str, int]
    source_id: str
    sink_id: str
    max_atp: float = 1.0
    rest_gain: float = 0.02
    ambient_gain: float = 0.005
    inhibit_cost: float = 0.02
    inhibit_duration: int = 1
    inbox_capacity: int = 4
    feedback_amount: float = 0.18
    packet_ttl: int = 8
    source_admission_policy: str = "fixed"
    source_admission_rate: int | None = None
    source_admission_min_rate: int = 1
    source_admission_max_rate: int | None = None
    topology_state: TopologyState | None = None
    morphogenesis_config: MorphogenesisConfig = field(default_factory=MorphogenesisConfig)
    source_sequence_context_enabled: bool = True
    latent_transfer_split_enabled: bool = True
    transfer_adaptation_window: int = 10
    capability_policy: str = "fixed-visible"
    capability_control_config: CapabilityControlConfig = field(default_factory=CapabilityControlConfig)

    def __post_init__(self) -> None:
        if self.topology_state is None:
            self.topology_state = TopologyState.from_graph(
                self.adjacency,
                self.positions,
                source_id=self.source_id,
                sink_id=self.sink_id,
            )
        self.pending_growth_proposals: List[GrowthProposal] = []
        self.sync_topology()
        self.inboxes: Dict[str, List[SignalPacket]] = {
            node_id: [] for node_id in self.positions
        }
        self.node_states: Dict[str, NodeRuntimeState] = {
            node_id: NodeRuntimeState(
                node_id=node_id,
                position=position,
                atp=self.max_atp,
                max_atp=self.max_atp,
            )
            for node_id, position in self.positions.items()
            if node_id != self.sink_id
        }
        self.delivered_packets: List[SignalPacket] = []
        self.dropped_packets: List[SignalPacket] = []
        self.source_buffer: List[SignalPacket] = []
        self.pending_feedback: List[FeedbackPulse] = []
        self.total_injected = 0
        self.admitted_packets = 0
        self._next_packet_id = 1
        self.packet_counter = itertools.count(self._next_packet_id)
        self.current_cycle = 0
        self.overload_events = 0
        self.max_inbox_depth = 0
        self.max_source_backlog = 0
        self.last_source_admission = 0
        self.source_admission_history: List[int] = []
        self.admission_substrate = AdmissionSubstrate()
        self._source_cycle_start_feedback = 0
        self._source_cycle_start_routed = 0
        self._source_cycle_start_backlog = 0
        self._source_cycle_action_cost = 0.0
        self.last_source_efficiency = 0.0
        self.source_efficiency_history: List[float] = []
        self.latent_context_trackers: Dict[str, LatentContextTracker] = {
            node_id: LatentContextTracker()
            for node_id in self.node_states
        }
        self.capability_states: Dict[str, CapabilityState] = {
            node_id: self._initial_capability_state()
            for node_id in self.node_states
        }
        self.carryover_task_ids: set[str] = set()
        self.transfer_adaptation_start_cycle = 0

    def sync_topology(self) -> None:
        if self.topology_state is None:
            return
        self.adjacency = self.topology_state.adjacency_map()
        self.positions = self.topology_state.positions_map()
        prior_inboxes = getattr(self, "inboxes", {})
        self.inboxes = {
            node_id: list(prior_inboxes.get(node_id, []))
            for node_id in self.positions
        }
        prior_states = getattr(self, "node_states", {})
        self.node_states = {}
        for node_id, position in self.positions.items():
            if node_id == self.sink_id:
                continue
            state = prior_states.get(node_id)
            if state is None:
                state = NodeRuntimeState(
                    node_id=node_id,
                    position=position,
                    atp=self.max_atp,
                    max_atp=self.max_atp,
                )
            state.position = position
            self.node_states[node_id] = state
        prior_trackers = getattr(self, "latent_context_trackers", {})
        self.latent_context_trackers = {
            node_id: prior_trackers.get(node_id, LatentContextTracker())
            for node_id in self.node_states
        }
        prior_capabilities = getattr(self, "capability_states", {})
        self.capability_states = {
            node_id: prior_capabilities.get(node_id, self._initial_capability_state())
            for node_id in self.node_states
        }

    def _initial_capability_state(self) -> CapabilityState:
        latent_enabled = self.capability_policy in ("fixed-latent", "growth-latent")
        growth_enabled = self.capability_policy in ("growth-visible", "growth-latent")
        return CapabilityState(
            latent_support=1.0 if latent_enabled else 0.0,
            latent_enabled=latent_enabled,
            visible_context_trust=0.0 if latent_enabled else 1.0,
            growth_support=1.0 if growth_enabled else 0.0,
            growth_enabled=growth_enabled,
        )

    def agent_ids(self) -> List[str]:
        return sorted(
            self.node_states.keys(),
            key=lambda node_id: self.positions[node_id],
        )

    def neighbors_of(self, node_id: str) -> tuple[str, ...]:
        return self.adjacency.get(node_id, ())

    def state_for(self, node_id: str) -> NodeRuntimeState:
        return self.node_states[node_id]

    def create_packet(
        self,
        *,
        cycle: int,
        input_bits: Sequence[int] | None = None,
        payload_bits: Sequence[int] | None = None,
        context_bit: int | None = None,
        task_id: str | None = None,
        target_bits: Sequence[int] | None = None,
    ) -> SignalPacket:
        packet_number = next(self.packet_counter)
        self._next_packet_id = packet_number + 1
        packet_id = f"pkt-{packet_number}"
        return SignalPacket(
            packet_id=packet_id,
            origin=self.source_id,
            target=self.sink_id,
            created_cycle=cycle,
            input_bits=list(input_bits or payload_bits or []),
            payload_bits=list(payload_bits or input_bits or []),
            context_bit=context_bit,
            task_id=task_id,
            target_bits=list(target_bits or []),
        )

    def inject_packets(
        self,
        packets: Iterable[SignalPacket],
        *,
        cycle: int | None = None,
    ) -> None:
        if cycle is not None:
            self.current_cycle = max(self.current_cycle, cycle)
        for packet in packets:
            self.source_buffer.append(packet)
            self.total_injected += 1
        self._admit_source_packets()
        self._record_inbox_pressure()

    def inject_signal(
        self,
        count: int = 1,
        cycle: int = 0,
        *,
        packet_payloads: Sequence[Sequence[int]] | None = None,
        context_bits: Sequence[int | None] | None = None,
        task_id: str | None = None,
    ) -> None:
        self.current_cycle = max(self.current_cycle, cycle)
        payloads = list(packet_payloads or [])
        contexts = list(context_bits or [])
        if payloads and len(payloads) != count:
            raise ValueError("packet_payloads length must match count")
        if contexts and len(contexts) != count:
            raise ValueError("context_bits length must match count")

        packets = []
        for index in range(count):
            payload_bits = payloads[index] if payloads else None
            context_bit = contexts[index] if contexts else None
            packets.append(
                self.create_packet(
                    cycle=cycle,
                    input_bits=payload_bits,
                    payload_bits=payload_bits,
                    context_bit=context_bit,
                    task_id=task_id,
                )
            )
        self.inject_packets(packets, cycle=cycle)

    def prepare_cycle(self, cycle: int) -> None:
        self.current_cycle = cycle
        source_state = self.state_for(self.source_id)
        self._source_cycle_start_feedback = source_state.received_feedback
        self._source_cycle_start_routed = source_state.routed_packets
        self._source_cycle_start_backlog = len(self.source_buffer)
        self._source_cycle_action_cost = 0.0
        self._admit_source_packets()
        self._prioritize_all_queues()
        self._record_inbox_pressure()

    def export_latent_context_state(self) -> dict[str, object]:
        return {
            node_id: tracker.to_dict()
            for node_id, tracker in self.latent_context_trackers.items()
        }

    def export_capability_state(self) -> dict[str, object]:
        return {
            node_id: state.to_dict()
            for node_id, state in self.capability_states.items()
        }

    def configure_transfer_regime(
        self,
        *,
        task_ids_seen: Iterable[str] | None,
        start_cycle: int,
    ) -> None:
        self.carryover_task_ids = {
            str(task_id)
            for task_id in list(task_ids_seen or [])
            if task_id is not None
        }
        self.transfer_adaptation_start_cycle = int(start_cycle)

    def clear_transfer_regime(self) -> None:
        self.carryover_task_ids = set()
        self.transfer_adaptation_start_cycle = 0

    def transfer_adaptation_phase(self, task_id: str | None, *, node_id: str | None = None) -> float:
        if not self.latent_transfer_split_enabled:
            return 0.0
        if node_id is not None and node_id != self.source_id:
            return 0.0
        if not task_id or not self.carryover_task_ids:
            return 0.0
        if str(task_id) in self.carryover_task_ids:
            return 0.0
        elapsed = max(0, self.current_cycle - self.transfer_adaptation_start_cycle)
        if elapsed >= self.transfer_adaptation_window:
            return 0.0
        remaining = self.transfer_adaptation_window - elapsed
        return max(0.0, min(1.0, remaining / max(self.transfer_adaptation_window, 1)))

    def load_latent_context_state(self, payload: dict[str, object] | None) -> None:
        payload = payload or {}
        self.latent_context_trackers = {
            node_id: LatentContextTracker.from_dict(
                dict(payload.get(node_id, {})) if node_id in payload else None
            )
            for node_id in self.node_states
        }

    def load_capability_state(self, payload: dict[str, object] | None) -> None:
        payload = payload or {}
        self.capability_states = {
            node_id: CapabilityState.from_dict(
                dict(payload.get(node_id, {})) if node_id in payload else None
            )
            for node_id in self.node_states
        }

    def capability_snapshot(self, node_id: str) -> dict[str, object]:
        state = self.capability_states.get(node_id, self._initial_capability_state())
        return {
            "latent_recruitment_pressure": round(state.latent_recruitment_pressure, 5),
            "latent_confidence_estimate": round(state.latent_confidence_estimate, 5),
            "latent_support": round(state.latent_support, 5),
            "latent_enabled": bool(state.latent_enabled),
            "visible_context_trust": round(state.visible_context_trust, 5),
            "growth_recruitment_pressure": round(state.growth_recruitment_pressure, 5),
            "growth_stabilization_readiness": round(state.growth_stabilization_readiness, 5),
            "growth_support": round(state.growth_support, 5),
            "growth_enabled": bool(state.growth_enabled),
            "latent_recruitment_cycles": list(state.latent_recruitment_cycles),
            "growth_recruitment_cycles": list(state.growth_recruitment_cycles),
        }

    def capability_summary(self) -> dict[str, object]:
        return {
            node_id: self.capability_snapshot(node_id)
            for node_id in self.node_states
        }

    def _visible_context_exposed(
        self,
        node_id: str,
        packet: SignalPacket | None,
    ) -> bool:
        if packet is None or packet.context_bit is None:
            return False
        if self.capability_policy in ("fixed-visible", "growth-visible"):
            return True
        if self.capability_policy in ("fixed-latent", "growth-latent"):
            return False
        state = self.capability_states.get(node_id)
        if state is None:
            return True
        return (
            state.visible_context_trust
            >= self.capability_control_config.latent_visible_suppression_threshold
        )

    def _latent_tracker_engaged(
        self,
        node_id: str,
        packet: SignalPacket | None,
    ) -> bool:
        if packet is None or packet.task_id is None:
            return False
        # In self-selected mode, the source can observe sequence evidence in parallel
        # with visible context so latent support can accumulate before explicit failure.
        if (
            self.capability_policy == "self-selected"
            and node_id == self.source_id
            and self.source_sequence_context_enabled
        ):
            return True
        return packet.context_bit is None or not self._visible_context_exposed(node_id, packet)

    def _capability_focus_packet(self, node_id: str) -> SignalPacket | None:
        packets = self.inboxes.get(node_id, [])
        if packets:
            return packets[0]
        if node_id == self.source_id and self.source_buffer:
            return self.source_buffer[0]
        return None

    def _update_capability_states(self) -> None:
        if self.capability_policy != "self-selected":
            return
        config = self.capability_control_config
        for node_id, runtime in self.node_states.items():
            capability = self.capability_states.setdefault(node_id, self._initial_capability_state())
            packets = self.inboxes.get(node_id, [])
            head_packet = self._capability_focus_packet(node_id)
            task_active = 1.0 if head_packet is not None and head_packet.task_id is not None else 0.0
            visible_context_present = (
                1.0
                if head_packet is not None and head_packet.context_bit is not None
                else 0.0
            )
            contradiction = self._contradiction_pressure(node_id)
            local_load = min(1.0, len(packets) / max(self.inbox_capacity, 1))
            mismatch_signal = 0.0
            if runtime.received_feedback > 0:
                mismatch_signal = max(0.0, 1.0 - min(1.0, runtime.last_match_ratio))
            recent_latent = self._recent_latent_task_summary(node_id)
            latent_confidence = float(recent_latent.get("confidence", 0.0))
            latent_recency = float(recent_latent.get("recency_weight", 0.0))
            effective_latent_confidence = latent_confidence * (0.35 + 0.65 * latent_recency)
            visible_reliability = (
                visible_context_present
                * max(0.0, 1.0 - 0.75 * contradiction)
                * max(0.0, 1.0 - 0.60 * mismatch_signal)
            )
            latent_pressure = max(
                0.0,
                min(
                    1.0,
                    0.60 * contradiction * task_active
                    + 0.48 * mismatch_signal * task_active
                    + 0.06 * local_load * task_active
                    + 0.08 * float(recent_latent.get("growth_ready", 0.0))
                    + 0.12 * effective_latent_confidence
                    + 0.18 * effective_latent_confidence * max(0.0, 1.0 - capability.visible_context_trust)
                    - 0.18 * visible_reliability
                    - 0.06 * (1.0 - task_active),
                ),
            )
            prior_latent_enabled = capability.latent_enabled
            capability.latent_recruitment_pressure = latent_pressure
            capability.latent_confidence_estimate = effective_latent_confidence
            capability.latent_support = max(
                0.0,
                min(
                    1.0,
                    capability.latent_support * config.latent_support_decay
                    + config.latent_support_gain * latent_pressure
                    + 0.18 * effective_latent_confidence
                    - 0.12 * visible_reliability
                    - 0.08 * (1.0 - task_active),
                ),
            )
            capability.latent_enabled = (
                capability.latent_support >= config.latent_activation_threshold
            )
            capability.visible_context_trust = max(
                0.0,
                min(
                    1.0,
                    capability.visible_context_trust * (0.98 if task_active < 0.5 else 1.0)
                    if task_active < 0.5
                    else visible_context_present
                    * (
                        0.65 * visible_reliability
                        + 0.20 * max(0.0, 1.0 - contradiction)
                        + 0.15 * max(0.0, 1.0 - effective_latent_confidence)
                    ),
                ),
            )
            if capability.latent_enabled and not prior_latent_enabled:
                capability.latent_recruitment_cycles.append(self.current_cycle)

            node_spec = self.topology_state.node_specs.get(node_id) if self.topology_state is not None else None
            routing_feedback = (
                max(0.0, min(1.0, float(node_spec.feedback_recent)))
                if node_spec is not None
                else 0.0
            )
            stabilization = max(
                0.0,
                min(
                    1.0,
                    0.42 * routing_feedback
                    + 0.28 * max(float(recent_latent.get("growth_ready", 0.0)), visible_context_present)
                    + 0.24 * max(0.0, min(1.0, runtime.atp / max(runtime.max_atp, 1e-9)))
                    - 0.22 * contradiction,
                ),
            )
            growth_pressure = max(
                0.0,
                min(
                    1.0,
                    0.16 * contradiction * task_active
                + 0.18 * local_load * task_active
                + (
                    0.12 * min(1.0, len(self.source_buffer) / max(self.inbox_capacity, 1))
                    if node_id == self.source_id
                    else 0.0
                )
                + 0.14 * routing_feedback
                + (
                    0.08 * max(0.0, min(1.0, float(node_spec.net_energy_recent)))
                    if node_spec is not None
                    else 0.0
                )
                + 0.06 * capability.growth_support
                - 0.28 * max(0.0, 1.0 - stabilization)
                - 0.18 * capability.latent_enabled * max(0.0, 1.0 - effective_latent_confidence)
                - 0.10 * visible_reliability,
                ),
            )
            prior_growth_enabled = capability.growth_enabled
            capability.growth_recruitment_pressure = max(0.0, min(1.0, growth_pressure))
            capability.growth_stabilization_readiness = stabilization
            capability.growth_support = max(
                0.0,
                min(
                    1.0,
                    capability.growth_support * config.growth_support_decay
                    + config.growth_support_gain * capability.growth_recruitment_pressure
                    + 0.06 * stabilization
                    - 0.12 * max(0.0, 1.0 - stabilization),
                ),
            )
            capability.growth_enabled = (
                capability.growth_support >= config.growth_activation_threshold
                and stabilization >= config.growth_stability_threshold
                and (
                    not capability.latent_enabled
                    or effective_latent_confidence >= LATENT_CONTEXT_CONFIDENCE_THRESHOLD
                    or visible_context_present >= 0.5
                )
            )
            if capability.growth_enabled and not prior_growth_enabled:
                capability.growth_recruitment_cycles.append(self.current_cycle)

    def _apply_capability_costs(self) -> None:
        if self.capability_policy != "self-selected":
            return
        config = self.capability_control_config
        for node_id, capability in self.capability_states.items():
            runtime = self.node_states.get(node_id)
            if runtime is None:
                continue
            total_cost = 0.0
            if capability.latent_enabled:
                total_cost += config.latent_maintenance_cost * (0.5 + capability.latent_support)
            if capability.growth_enabled:
                total_cost += config.growth_maintenance_cost * (0.5 + capability.growth_support)
            if total_cost > 0.0:
                runtime.atp = max(0.0, runtime.atp - total_cost)

    def _latent_snapshot(
        self,
        node_id: str,
        task_id: str | None,
        *,
        observe: bool = False,
        packet_id: str | None = None,
        input_bits: Sequence[int] | None = None,
    ) -> dict[str, object]:
        tracker = self.latent_context_trackers.get(node_id)
        if tracker is None:
            return LatentContextTracker().snapshot(task_id)
        if observe:
            tracker.observe_packet(task_id, packet_id, input_bits)
            return tracker.observe_task(task_id, self.current_cycle)
        return tracker.snapshot(task_id)

    def _recent_latent_task_summary(self, node_id: str) -> dict[str, float]:
        tracker = self.latent_context_trackers.get(node_id)
        if tracker is None:
            return {
                "active": 0.0,
                "task_age": 0.0,
                "recency_weight": 0.0,
                "has_context": 0.0,
                "confidence": 0.0,
                "promotion_ready": 0.0,
                "growth_ready": 0.0,
            }
        best_task_id: str | None = None
        best_age: int | None = None
        best_confidence = -1.0
        for task_id, state in tracker.task_states.items():
            if state.last_observed_cycle < 0:
                continue
            age = max(0, self.current_cycle - state.last_observed_cycle)
            if age > CAPABILITY_LATENT_IDLE_TASK_WINDOW:
                continue
            confidence = float(state.confidence)
            if (
                best_age is None
                or age < best_age
                or (age == best_age and confidence > best_confidence)
            ):
                best_task_id = task_id
                best_age = age
                best_confidence = confidence
        if best_task_id is None or best_age is None:
            return {
                "active": 0.0,
                "task_age": 0.0,
                "recency_weight": 0.0,
                "has_context": 0.0,
                "confidence": 0.0,
                "promotion_ready": 0.0,
                "growth_ready": 0.0,
            }
        snapshot = tracker.snapshot(best_task_id)
        recency_weight = max(
            0.0,
            min(
                1.0,
                1.0 - (float(best_age) / max(float(CAPABILITY_LATENT_IDLE_TASK_WINDOW), 1.0)),
            ),
        )
        return {
            "active": 1.0,
            "task_age": float(best_age),
            "recency_weight": recency_weight,
            "has_context": 1.0 if snapshot.get("available") else 0.0,
            "confidence": float(snapshot.get("confidence", 0.0)),
            "promotion_ready": 1.0 if snapshot.get("promotion_ready") else 0.0,
            "growth_ready": 1.0 if snapshot.get("growth_ready") else 0.0,
        }

    def _record_latent_route(
        self,
        node_id: str,
        *,
        task_id: str | None,
        context_bit: int | None,
        transform_name: str,
    ) -> None:
        route_packet = (
            SignalPacket(
                packet_id=f"capability-route-{node_id}-{self.current_cycle}",
                origin=self.source_id,
                target=self.sink_id,
                created_cycle=self.current_cycle,
                context_bit=context_bit,
                task_id=task_id,
            )
            if context_bit is not None
            else None
        )
        if context_bit is not None and self._visible_context_exposed(node_id, route_packet):
            return
        tracker = self.latent_context_trackers.get(node_id)
        if tracker is None:
            return
        tracker.record_route(
            task_id,
            transform_name,
            is_source=node_id == self.source_id,
            adaptation_phase=self.transfer_adaptation_phase(task_id, node_id=node_id),
        )

    def _resolved_feedback_context(
        self,
        node_id: str,
        pulse: FeedbackPulse,
        transform_name: str,
        *,
        credit_signal: float,
    ) -> tuple[int | None, float, bool]:
        feedback_packet = (
            SignalPacket(
                packet_id=pulse.packet_id,
                origin=self.source_id,
                target=self.sink_id,
                created_cycle=self.current_cycle,
                context_bit=pulse.context_bit,
                task_id=pulse.task_id,
            )
            if pulse.context_bit is not None
            else None
        )
        if pulse.context_bit is not None and self._visible_context_exposed(node_id, feedback_packet):
            return int(pulse.context_bit), 1.0, True
        tracker = self.latent_context_trackers.get(node_id)
        if tracker is None:
            return None, 0.0, False
        tracker.record_feedback(
            pulse.task_id,
            transform_name,
            bit_match_ratio=float(pulse.bit_match_ratio),
            credit_signal=credit_signal,
            is_source=node_id == self.source_id,
            adaptation_phase=self.transfer_adaptation_phase(pulse.task_id, node_id=node_id),
        )
        snapshot = tracker.observe_task(pulse.task_id, self.current_cycle)
        if not snapshot.get("promotion_ready"):
            return None, float(snapshot.get("confidence", 0.0)), False
        estimate = snapshot.get("estimate")
        if estimate is None:
            return None, float(snapshot.get("confidence", 0.0)), False
        return int(estimate), float(snapshot.get("confidence", 0.0)), True

    def observe_local(self, node_id: str) -> dict[str, float]:
        state = self.state_for(node_id)
        local_packets = self.inboxes[node_id]
        local_ages = [self._packet_wait_age(packet) for packet in local_packets]
        overflow = max(0, len(local_packets) - self.inbox_capacity)
        head_packet = self._capability_focus_packet(node_id)
        head_age = self._packet_wait_age(head_packet) if head_packet is not None else 0
        oldest_age = max(local_ages, default=head_age)
        head_task_id = head_packet.task_id if head_packet is not None else None
        visible_context_exposed = self._visible_context_exposed(node_id, head_packet)
        latent_snapshot = self._latent_snapshot(
            node_id,
            head_task_id,
            observe=bool(
                head_packet is not None
                and self._latent_tracker_engaged(node_id, head_packet)
                and head_task_id is not None
                and node_id == self.source_id
                and self.source_sequence_context_enabled
            ),
            packet_id=head_packet.packet_id if head_packet is not None else None,
            input_bits=head_packet.input_bits if head_packet is not None else None,
        )
        source_sequence_available = (
            1.0
            if (
                node_id == self.source_id
                and head_packet is not None
                and self._latent_tracker_engaged(node_id, head_packet)
                and self.source_sequence_context_enabled
                and latent_snapshot.get("sequence_available")
            )
            else 0.0
        )
        raw_has_context = (
            1.0
            if head_packet is not None and head_packet.context_bit is not None and visible_context_exposed
            else 0.0
        )
        transfer_adaptation_phase = (
            self.transfer_adaptation_phase(head_task_id, node_id=node_id)
            if (
                head_packet is not None
                and head_packet.context_bit is None
                and head_task_id is not None
            )
            else 0.0
        )
        transfer_hidden_unseen_task = (
            1.0
            if (
                transfer_adaptation_phase > 0.0
                and raw_has_context < 0.5
            )
            else 0.0
        )
        latent_available = 1.0 if latent_snapshot.get("available") else 0.0
        latent_estimate = latent_snapshot.get("estimate")
        latent_confidence = float(latent_snapshot.get("confidence", 0.0))
        recent_latent = self._recent_latent_task_summary(node_id)
        latent_context_count = int(latent_snapshot.get("context_count", 2))
        effective_context_threshold = max(
            0.0,
            min(
                1.0,
                (
                    LATENT_CONTEXT_CONFIDENCE_THRESHOLD
                    + transfer_adaptation_phase * LATENT_TRANSFER_EFFECTIVE_THRESHOLD_BOOST
                )
                * _context_threshold_scale(latent_context_count),
            ),
        )
        effective_context_bit = None
        effective_context_confidence = 0.0
        effective_has_context = 0.0
        context_promotion_ready = 0.0
        context_growth_ready = 0.0
        if raw_has_context >= 0.5 and head_packet is not None and head_packet.context_bit is not None:
            effective_context_bit = int(head_packet.context_bit)
            effective_context_confidence = 1.0
            effective_has_context = 1.0
            context_promotion_ready = 1.0
            context_growth_ready = 1.0
        elif (
            latent_available >= 0.5
            and latent_estimate is not None
            and latent_confidence >= effective_context_threshold
        ):
            effective_context_bit = int(latent_estimate)
            effective_context_confidence = latent_confidence
            effective_has_context = 1.0
            context_promotion_ready = 1.0 if latent_snapshot.get("promotion_ready") else 0.0
            context_growth_ready = 1.0 if latent_snapshot.get("growth_ready") else 0.0
        local = {
            "atp_ratio": state.atp / max(state.max_atp, 1e-9),
            "inbox_load": min(1.0, len(self.inboxes[node_id]) / max(self.inbox_capacity, 1)),
            "reward_buffer": min(1.0, state.reward_buffer / max(state.max_atp, 1e-9)),
            "neighbor_density": len(self.neighbors_of(node_id)) / max(len(self.positions) - 1, 1),
            "feedback_pending": self._feedback_pending_ratio(node_id),
            "oldest_packet_age": min(1.0, oldest_age / max(self.packet_ttl, 1)),
            "queue_pressure": min(1.0, overflow / max(self.inbox_capacity, 1)),
            "ingress_backlog": (
                min(1.0, len(self.source_buffer) / max(self.inbox_capacity, 1))
                if node_id == self.source_id
                else 0.0
            ),
            "has_packet": 1.0 if head_packet is not None else 0.0,
            "head_has_task": 1.0 if head_task_id is not None else 0.0,
            "head_transform_depth": (
                min(1.0, len(head_packet.transform_trace) / 4.0)
                if head_packet is not None
                else 0.0
            ),
            "head_has_context": (
                raw_has_context
            ),
            "head_context_bit": (
                float(head_packet.context_bit)
                if head_packet is not None and head_packet.context_bit is not None
                else 0.0
            ),
            "latent_context_available": latent_available,
            "latent_context_estimate": (
                float(latent_estimate) if latent_estimate is not None else 0.0
            ),
            "latent_context_confidence": latent_confidence,
            "effective_context_threshold": effective_context_threshold,
            "transfer_adaptation_phase": transfer_adaptation_phase,
            "transfer_hidden_unseen_task": transfer_hidden_unseen_task,
            "source_sequence_available": source_sequence_available,
            "source_sequence_context_estimate": (
                float(latent_snapshot.get("sequence_context_estimate"))
                if latent_snapshot.get("sequence_context_estimate") is not None
                else 0.0
            ),
            "source_sequence_context_confidence": float(
                latent_snapshot.get("sequence_context_confidence", 0.0)
            ),
            "source_sequence_prev_parity": (
                float(latent_snapshot.get("sequence_prev_parity"))
                if latent_snapshot.get("sequence_prev_parity") is not None
                else 0.0
            ),
            "source_sequence_change_ratio": float(
                latent_snapshot.get("sequence_change_ratio", 0.0)
            ),
            "source_sequence_repeat_input": float(
                latent_snapshot.get("sequence_repeat_input", 0.0)
            ),
            "recent_latent_task_active": float(recent_latent.get("active", 0.0)),
            "recent_latent_task_age": float(recent_latent.get("task_age", 0.0)),
            "recent_latent_has_context": float(recent_latent.get("has_context", 0.0)),
            "recent_latent_context_confidence": float(recent_latent.get("confidence", 0.0)),
            "recent_latent_promotion_ready": float(recent_latent.get("promotion_ready", 0.0)),
            "recent_latent_growth_ready": float(recent_latent.get("growth_ready", 0.0)),
            "visible_context_trust": float(
                self.capability_states.get(node_id, self._initial_capability_state()).visible_context_trust
            ),
            "latent_recruitment_pressure": float(
                self.capability_states.get(node_id, self._initial_capability_state()).latent_recruitment_pressure
            ),
            "latent_capability_support": float(
                self.capability_states.get(node_id, self._initial_capability_state()).latent_support
            ),
            "latent_capability_enabled": 1.0
            if self.capability_states.get(node_id, self._initial_capability_state()).latent_enabled
            else 0.0,
            "growth_recruitment_pressure": float(
                self.capability_states.get(node_id, self._initial_capability_state()).growth_recruitment_pressure
            ),
            "growth_capability_support": float(
                self.capability_states.get(node_id, self._initial_capability_state()).growth_support
            ),
            "growth_capability_enabled": 1.0
            if self.capability_states.get(node_id, self._initial_capability_state()).growth_enabled
            else 0.0,
            "growth_stabilization_readiness": float(
                self.capability_states.get(node_id, self._initial_capability_state()).growth_stabilization_readiness
            ),
            "effective_has_context": effective_has_context,
            "effective_context_bit": (
                float(effective_context_bit) if effective_context_bit is not None else 0.0
            ),
            "effective_context_confidence": effective_context_confidence,
            "context_promotion_ready": context_promotion_ready,
            "context_growth_ready": context_growth_ready,
            "last_feedback_amount": min(
                1.0,
                state.last_feedback_amount / max(self.feedback_amount, 1e-9),
            ),
            "last_match_ratio": min(1.0, max(0.0, state.last_match_ratio)),
            "dormant": 1.0 if state.dormant else 0.0,
        }
        transform_evidence = dict(latent_snapshot.get("transform_evidence", {}))
        candidate_transforms = set(_candidate_transforms_for_task(head_task_id))
        sequence_estimate = latent_snapshot.get("sequence_context_estimate")
        sequence_confidence = float(latent_snapshot.get("sequence_context_confidence", 0.0))
        sequence_prev_bits = list(latent_snapshot.get("sequence_prev_bits", []))
        sequence_delta_bits = list(latent_snapshot.get("sequence_delta_bits", []))
        expected_sequence_transform = (
            _expected_transform_for_task(head_task_id, int(sequence_estimate))
            if sequence_estimate is not None
            else None
        )
        for index in range(4):
            local[f"source_prev_bit_{index}"] = (
                float(sequence_prev_bits[index]) if source_sequence_available >= 0.5 and index < len(sequence_prev_bits) else 0.0
            )
            local[f"source_delta_bit_{index}"] = (
                float(sequence_delta_bits[index]) if source_sequence_available >= 0.5 and index < len(sequence_delta_bits) else 0.0
            )
        for transform_name in TRANSFORM_NAMES:
            local[f"history_transform_evidence_{transform_name}"] = max(
                0.0,
                min(1.0, float(transform_evidence.get(transform_name, 0.0))),
            )
            if head_task_id is None:
                affinity = 0.0
            elif transform_name in candidate_transforms:
                affinity = 1.0
            elif transform_name == "identity":
                affinity = 0.0
            else:
                affinity = -1.0
            local[f"task_transform_affinity_{transform_name}"] = affinity
            sequence_hint = 0.0
            if source_sequence_available >= 0.5 and expected_sequence_transform is not None:
                if transform_name == expected_sequence_transform:
                    sequence_hint = sequence_confidence
                elif transform_name in candidate_transforms:
                    sequence_hint = (0.10 if transform_name == "identity" else 0.15) * sequence_confidence
                elif transform_name == "identity":
                    sequence_hint = -0.35 * sequence_confidence
                else:
                    sequence_hint = -0.20 * sequence_confidence
            local[f"source_sequence_transform_hint_{transform_name}"] = sequence_hint
        contradiction_pressure = self._contradiction_pressure(node_id)
        node_spec = self.topology_state.node_specs.get(node_id) if self.topology_state is not None else None
        candidate_targets = self._candidate_growth_targets(node_id)
        frontier_slots = self._candidate_frontier_slots(node_id)
        local["contradiction_pressure"] = contradiction_pressure
        local["growth_surplus_streak"] = (
            min(
                1.0,
                (node_spec.surplus_streak if node_spec is not None else 0)
                / max(self.morphogenesis_config.surplus_window, 1),
            )
            if self.morphogenesis_config.enabled
            else 0.0
        )
        local["growth_candidate_count"] = min(1.0, len(candidate_targets) / 3.0)
        local["frontier_slot_count"] = min(1.0, len(frontier_slots) / 2.0)
        local["node_probationary"] = 1.0 if node_spec is not None and node_spec.probationary else 0.0
        local["lineage_depth"] = (
            min(1.0, float(node_spec.lineage_depth))
            if node_spec is not None
            else 0.0
        )
        local["dynamic_node"] = 1.0 if node_spec is not None and node_spec.dynamic else 0.0
        local["energy_balance"] = (
            max(-1.0, min(1.0, node_spec.net_energy_recent))
            if node_spec is not None
            else 0.0
        )
        local["energy_surplus"] = (
            max(0.0, min(1.0, node_spec.net_energy_recent + 0.35 * local["reward_buffer"] + 0.25 * local["atp_ratio"]))
            if node_spec is not None
            else 0.0
        )
        local["maintenance_load"] = (
            min(
                1.0,
                (
                    node_spec.maintenance_cost_recent
                    + node_spec.structural_upkeep_recent
                    + node_spec.growth_cost_recent
                ) / 0.25,
            )
            if node_spec is not None
            else 0.0
        )
        local["structural_value"] = (
            max(-1.0, min(1.0, node_spec.value_recent))
            if node_spec is not None
            else 0.0
        )
        observed_context_bit = effective_context_bit
        payload_bits = head_packet.payload_bits if head_packet is not None else []
        for index in range(4):
            local[f"payload_bit_{index}"] = (
                float(payload_bits[index]) if index < len(payload_bits) else 0.0
            )
        for transform_name in TRANSFORM_NAMES:
            local[f"feedback_credit_{transform_name}"] = min(
                1.0,
                max(0.0, state.transform_credit.get(transform_name, 0.0)),
            )
            local[f"feedback_debt_{transform_name}"] = min(
                1.0,
                max(0.0, state.transform_debt.get(transform_name, 0.0)),
            )
            context_credit = 0.0
            context_debt = 0.0
            if observed_context_bit is not None:
                context_credit = state.context_transform_credit.get(
                    _context_credit_key(transform_name, int(observed_context_bit)),
                    0.0,
                )
                context_debt = state.context_transform_debt.get(
                    _context_credit_key(transform_name, int(observed_context_bit)),
                    0.0,
                )
            local[f"context_feedback_credit_{transform_name}"] = min(
                1.0,
                max(0.0, context_credit),
            )
            local[f"context_feedback_debt_{transform_name}"] = min(
                1.0,
                max(0.0, context_debt),
            )
        sink_position = self.positions[self.sink_id]
        span = max(abs(sink_position - self.positions[self.source_id]), 1)

        for neighbor_id in self.neighbors_of(node_id):
            neighbor_position = self.positions[neighbor_id]
            progress = 1.0 - abs(sink_position - neighbor_position) / span
            local[f"progress_{neighbor_id}"] = max(0.0, min(1.0, progress))
            local[f"congestion_{neighbor_id}"] = min(
                1.0,
                len(self.inboxes[neighbor_id]) / max(self.inbox_capacity, 1),
            )
            if self.topology_state is not None:
                neighbor_spec = self.topology_state.node_specs.get(neighbor_id)
                local[f"neighbor_dynamic_{neighbor_id}"] = (
                    1.0 if neighbor_spec is not None and neighbor_spec.dynamic else 0.0
                )
                local[f"neighbor_probationary_{neighbor_id}"] = (
                    1.0 if neighbor_spec is not None and neighbor_spec.probationary else 0.0
                )
            for transform_name in TRANSFORM_NAMES:
                branch_credit = state.branch_transform_credit.get(
                    _branch_debt_key(neighbor_id, transform_name),
                    0.0,
                )
                branch_debt = state.branch_transform_debt.get(
                    _branch_debt_key(neighbor_id, transform_name),
                    0.0,
                )
                context_branch_credit = 0.0
                context_branch_debt = 0.0
                if observed_context_bit is not None:
                    context_branch_credit = state.context_branch_transform_credit.get(
                        _context_branch_debt_key(
                            neighbor_id,
                            transform_name,
                            int(observed_context_bit),
                        ),
                        0.0,
                    )
                    context_branch_debt = state.context_branch_transform_debt.get(
                        _context_branch_debt_key(
                            neighbor_id,
                            transform_name,
                            int(observed_context_bit),
                        ),
                        0.0,
                    )
                local[f"branch_feedback_credit_{neighbor_id}_{transform_name}"] = min(
                    1.0,
                    max(0.0, branch_credit),
                )
                local[f"branch_feedback_debt_{neighbor_id}_{transform_name}"] = min(
                    1.0,
                    max(0.0, branch_debt),
                )
                local[f"context_branch_feedback_credit_{neighbor_id}_{transform_name}"] = min(
                    1.0,
                    max(0.0, context_branch_credit),
                )
                local[f"context_branch_feedback_debt_{neighbor_id}_{transform_name}"] = min(
                    1.0,
                    max(0.0, context_branch_debt),
                )
            branch_context_debt = 0.0
            branch_context_credit = 0.0
            if observed_context_bit is not None:
                branch_context_credit = state.branch_context_credit.get(
                    _branch_context_debt_key(neighbor_id, int(observed_context_bit)),
                    0.0,
                )
                branch_context_debt = state.branch_context_debt.get(
                    _branch_context_debt_key(neighbor_id, int(observed_context_bit)),
                    0.0,
                )
            local[f"branch_context_feedback_credit_{neighbor_id}"] = min(
                1.0,
                max(0.0, branch_context_credit),
            )
            local[f"branch_context_feedback_debt_{neighbor_id}"] = min(
                1.0,
                max(0.0, branch_context_debt),
            )
            if neighbor_id == self.sink_id:
                local[f"inhibited_{neighbor_id}"] = 0.0
            else:
                local[f"inhibited_{neighbor_id}"] = (
                    1.0 if self.state_for(neighbor_id).inhibited_for > 0 else 0.0
                )
        for target_id in candidate_targets:
            if f"progress_{target_id}" not in local:
                target_position = self.positions[target_id]
                progress = 1.0 - abs(sink_position - target_position) / span
                local[f"progress_{target_id}"] = max(0.0, min(1.0, progress))
                local[f"congestion_{target_id}"] = min(
                    1.0,
                    len(self.inboxes[target_id]) / max(self.inbox_capacity, 1),
                )
        return local

    def _contradiction_pressure(self, node_id: str) -> float:
        state = self.state_for(node_id)
        debt_total = (
            sum(state.transform_debt.values())
            + sum(state.context_transform_debt.values())
            + sum(state.branch_transform_debt.values())
            + sum(state.context_branch_transform_debt.values())
            + sum(state.branch_context_debt.values())
        )
        credit_total = (
            sum(state.transform_credit.values())
            + sum(state.context_transform_credit.values())
            + sum(state.branch_transform_credit.values())
            + sum(state.context_branch_transform_credit.values())
            + sum(state.branch_context_credit.values())
        )
        if debt_total <= 0.0 and credit_total <= 0.0:
            return 0.0
        return max(0.0, min(1.0, debt_total / max(debt_total + credit_total, 1e-9)))

    def _candidate_growth_targets(self, node_id: str) -> List[str]:
        if self.topology_state is None or not self.morphogenesis_config.enabled:
            return []
        return self.topology_state.candidate_targets(
            node_id,
            hop_limit=self.morphogenesis_config.frontier_hop_limit,
        )

    def _candidate_frontier_slots(self, node_id: str) -> List[int]:
        if self.topology_state is None or not self.morphogenesis_config.enabled:
            return []
        return self.topology_state.node_layer_slots(node_id)

    def growth_action_specs(self, node_id: str) -> List[dict[str, object]]:
        if not self.morphogenesis_config.enabled or self.topology_state is None:
            return []
        if node_id in (self.sink_id,):
            return []
        if node_id not in self.node_states:
            return []
        if (
            self.capability_policy == "self-selected"
            and not self.capability_states.get(node_id, self._initial_capability_state()).growth_enabled
        ):
            return []
        state = self.state_for(node_id)
        observation = self.observe_local(node_id)
        node_spec = self.topology_state.node_specs.get(node_id)
        if node_spec is None:
            return []
        atp_ratio = observation.get("atp_ratio", 0.0)
        backlog_crisis = (
            observation.get("ingress_backlog", 0.0) >= 0.85
            or observation.get("queue_pressure", 0.0) >= 0.85
        )
        contradiction = observation.get("contradiction_pressure", 0.0)
        overload = max(
            observation.get("queue_pressure", 0.0),
            observation.get("oldest_packet_age", 0.0),
            observation.get("ingress_backlog", 0.0),
        )
        energy_balance = float(node_spec.net_energy_recent)
        energy_surplus = float(observation.get("energy_surplus", 0.0))
        structural_value = float(node_spec.value_recent)
        structurally_motivated = (
            contradiction >= self.morphogenesis_config.contradiction_threshold
            or overload >= self.morphogenesis_config.overload_threshold
        )
        feedback_gate = self.morphogenesis_config.routing_feedback_gate
        routing_has_feedback = (
            feedback_gate <= 0.0
            or node_spec.feedback_recent >= feedback_gate
        )
        growth_ready = (
            atp_ratio >= self.morphogenesis_config.atp_surplus_threshold
            and node_spec.positive_energy_streak >= 1
            and node_spec.surplus_streak >= max(1, self.morphogenesis_config.surplus_window - 1)
            and not backlog_crisis
            and energy_balance >= self.morphogenesis_config.growth_energy_threshold
            and structural_value >= self.morphogenesis_config.growth_energy_threshold
            and structurally_motivated
            and not self.topology_state.max_dynamic_nodes_reached(self.morphogenesis_config)
            and routing_has_feedback
        )

        specs: List[dict[str, object]] = []
        local_queue_window = len(self.inboxes[node_id])
        low_local_pressure = local_queue_window <= self.morphogenesis_config.growth_queue_tolerance
        # Context-resolution gate: suppress bud actions while a task packet is
        # present and effective context confidence is below the configured
        # threshold.  This prevents noisy structural growth during the window
        # when the node is still inferring which transform context applies.
        # Prune and apoptosis proposals are generated regardless.
        context_gate = self.morphogenesis_config.context_resolution_growth_gate
        latent_context_unpromoted = (
            observation.get("head_has_task", 0.0) >= 0.5
            and observation.get("head_has_context", 0.0) < 0.5
            and observation.get("context_growth_ready", 0.0) < 0.5
        )
        latent_recent_idle_task = (
            observation.get("recent_latent_task_active", 0.0) >= 0.5
            and observation.get("head_has_task", 0.0) < 0.5
        )
        context_gate_active = (
            context_gate > 0.0
            and observation.get("head_has_task", 0.0) >= 0.5
            and (
                observation.get("effective_context_confidence", 0.0) < context_gate
                or latent_context_unpromoted
            )
        )
        anticipatory_threshold = self.morphogenesis_config.anticipatory_growth_backlog_threshold
        # Anticipatory growth fires under pre-overload pressure even without
        # ATP surplus — so positive_energy_streak is intentionally not required
        # here (it would be false precisely when this path is most needed).
        anticipatory_ready = (
            anticipatory_threshold > 0.0
            and (
                observation.get("ingress_backlog", 0.0) >= anticipatory_threshold
                or observation.get("queue_pressure", 0.0) >= anticipatory_threshold
            )
            and not backlog_crisis
            and not self.topology_state.max_dynamic_nodes_reached(self.morphogenesis_config)
            and routing_has_feedback
        )
        latent_idle_growth_gate_active = (
            context_gate > 0.0
            and latent_recent_idle_task
        )
        if (
            ((growth_ready and not latent_idle_growth_gate_active) or anticipatory_ready)
            and low_local_pressure
            and not context_gate_active
        ):
            for target_id in self._candidate_growth_targets(node_id):
                target_pos = self.positions[target_id]
                node_pos = self.positions[node_id]
                progress = 1.0 - abs(self.positions[self.sink_id] - target_pos) / max(
                    abs(self.positions[self.sink_id] - self.positions[self.source_id]),
                    1,
                )
                edge_projection = (
                    energy_surplus
                    + 0.18 * contradiction
                    + 0.10 * overload
                    + 0.12 * progress
                    - self.morphogenesis_config.bud_edge_cost
                )
                if target_pos == node_pos + 1:
                    if edge_projection >= self.morphogenesis_config.growth_energy_threshold:
                        specs.append(
                            {
                                "action": f"bud_edge:{target_id}",
                                "cost": self.morphogenesis_config.bud_edge_cost,
                                "score": (
                                    0.20
                                    + edge_projection
                                    + 0.08 * atp_ratio
                                    + 0.06 * observation.get("reward_buffer", 0.0)
                                ),
                                "target_id": target_id,
                                "reason": "energy_affordable_contradiction_escape",
                            }
                        )
                if target_pos > node_pos + 1:
                    slot = node_pos + 1
                    node_projection = (
                        energy_surplus
                        + 0.22 * contradiction
                        + 0.08 * overload
                        + 0.10 * progress
                        - 1.15 * self.morphogenesis_config.bud_node_cost
                    )
                    if node_projection >= self.morphogenesis_config.growth_energy_threshold:
                        specs.append(
                            {
                                "action": f"bud_node:{slot}:{target_id}",
                                "cost": self.morphogenesis_config.bud_node_cost,
                                "score": (
                                    0.22
                                    + node_projection
                                    + 0.06 * atp_ratio
                                    + 0.06 * observation.get("reward_buffer", 0.0)
                                ),
                                "target_id": target_id,
                                "slot": slot,
                                "reason": "energy_affordable_branch_bypass",
                            }
                        )

        neighbors = self.neighbors_of(node_id)
        if len(self.inboxes[node_id]) == 0:
            for neighbor_id in neighbors:
                idle_ticks = 0
                edge = None
                if self.topology_state is not None and self.topology_state.has_edge(node_id, neighbor_id):
                    edge = self.topology_state.edge_specs.get(_edge_id(node_id, neighbor_id))
                    if edge is not None:
                        if edge.last_used_cycle is None:
                            idle_ticks = self.current_cycle - edge.created_cycle
                        else:
                            idle_ticks = self.current_cycle - edge.last_used_cycle
                if edge is None or not edge.dynamic:
                    continue
                prune_ready = (
                    edge.negative_value_streak >= self.morphogenesis_config.edge_prune_ticks
                    or (
                        idle_ticks >= self.morphogenesis_config.edge_prune_ticks
                        and edge.value_recent <= self.morphogenesis_config.prune_energy_threshold
                    )
                )
                if prune_ready and len(neighbors) > 1:
                    specs.append(
                        {
                            "action": f"prune_edge:{neighbor_id}",
                            "cost": self.morphogenesis_config.prune_edge_cost,
                            "score": (
                                0.22
                                + max(0.0, -edge.value_recent)
                                + 0.18 * idle_ticks / max(self.morphogenesis_config.edge_prune_ticks, 1)
                            ),
                            "target_id": neighbor_id,
                            "reason": "energetically_net_negative",
                        }
                    )
            if (
                node_spec.dynamic
                and node_spec.negative_energy_streak >= self.morphogenesis_config.isolation_ticks
                and (
                    len(neighbors) == 0
                    or node_spec.isolated_ticks >= self.morphogenesis_config.isolation_ticks
                    or node_spec.dormant_ticks >= self.morphogenesis_config.isolation_ticks
                )
            ):
                specs.append(
                    {
                        "action": "apoptosis_request",
                        "cost": self.morphogenesis_config.apoptosis_cost,
                        "score": 0.95,
                        "reason": "energetically_unsustainable",
                    }
                )
        return specs

    def queue_growth_proposal(self, node_id: str, action: str, *, score: float, cost: float) -> GrowthProposal:
        target_id = None
        slot = None
        if action.startswith("bud_edge:"):
            target_id = action.split(":", 1)[1]
        elif action.startswith("bud_node:"):
            _, slot_raw, target_id = action.split(":", 2)
            slot = int(slot_raw)
        elif action.startswith("prune_edge:"):
            target_id = action.split(":", 1)[1]
        proposal = GrowthProposal(
            action=action,
            node_id=node_id,
            cycle=self.current_cycle,
            score=score,
            cost=cost,
            target_id=target_id,
            slot=slot,
            reason="queued_locally",
        )
        self.pending_growth_proposals.append(proposal)
        return proposal

    def route_available(self, node_id: str, neighbor_id: str, cost: float) -> bool:
        state = self.state_for(node_id)
        if state.atp + 1e-9 < cost:
            return False
        if not self.inboxes[node_id]:
            return False
        if neighbor_id != self.sink_id and self.state_for(neighbor_id).inhibited_for > 0:
            return False
        return len(self.inboxes.get(neighbor_id, [])) < self.inbox_capacity

    def inhibit_available(self, node_id: str) -> bool:
        return self.state_for(node_id).atp + 1e-9 >= self.inhibit_cost

    def rest_node(self, node_id: str) -> float:
        state = self.state_for(node_id)
        recovered = min(self.rest_gain, state.reward_buffer)
        if recovered <= 0.0:
            recovered = self.ambient_gain
        state.atp = min(state.max_atp, state.atp + recovered)
        state.reward_buffer = max(0.0, state.reward_buffer - recovered)
        state.rest_count += 1
        return recovered

    def score_packet(self, packet: SignalPacket) -> float:
        target_bits = list(packet.target_bits) if packet.target_bits else _target_bits_for_task(
            packet.input_bits,
            context_bit=packet.context_bit,
            task_id=packet.task_id,
        )
        if target_bits is None:
            packet.target_bits = []
            packet.matched_target = None
            packet.bit_match_ratio = None
            packet.feedback_award = self.feedback_amount
            return self.feedback_amount

        packet.target_bits = list(target_bits)
        packet.bit_match_ratio = _bit_match_ratio(packet.payload_bits, packet.target_bits)
        packet.matched_target = packet.bit_match_ratio >= 1.0 - 1e-9
        packet.feedback_award = self.feedback_amount * packet.bit_match_ratio
        return packet.feedback_award

    def route_signal(
        self,
        node_id: str,
        neighbor_id: str,
        cost: float,
        *,
        transform_name: str | None = None,
    ) -> dict:
        if not self.route_available(node_id, neighbor_id, cost):
            return {"success": False, "cost": 0.0, "delivered": False}

        self._prioritize_inbox(node_id)
        packet = self.inboxes[node_id].pop(0)
        transform = _normalize_transform_name(transform_name)
        packet.payload_bits = _apply_transform(packet.payload_bits, transform)
        packet.transform_trace.append(transform)
        packet.hops.append(node_id)
        packet.edge_path.append(_edge_id(node_id, neighbor_id))
        packet.last_moved_cycle = self.current_cycle
        self._record_latent_route(
            node_id,
            task_id=packet.task_id,
            context_bit=packet.context_bit,
            transform_name=transform,
        )
        if self.topology_state is not None:
            self.topology_state.record_edge_use(node_id, neighbor_id, self.current_cycle, cost=cost)

        source_state = self.state_for(node_id)
        source_state.atp = max(0.0, source_state.atp - cost)
        source_state.routed_packets += 1
        if node_id == self.source_id:
            self._source_cycle_action_cost += cost

        if neighbor_id == self.sink_id:
            packet.hops.append(neighbor_id)
            packet.delivered = True
            packet.delivered_cycle = self.current_cycle
            feedback_award = self.score_packet(packet)
            self.delivered_packets.append(packet)
            if feedback_award > 0.0:
                self.pending_feedback.append(
                    FeedbackPulse(
                        packet_id=packet.packet_id,
                        edge_path=list(packet.edge_path),
                        amount=feedback_award,
                        transform_path=list(packet.transform_trace),
                        context_bit=packet.context_bit,
                        task_id=packet.task_id,
                        bit_match_ratio=float(packet.bit_match_ratio or 0.0),
                        matched_target=bool(packet.matched_target),
                    )
                )
            return {
                "success": True,
                "cost": cost,
                "delivered": True,
                "packet_id": packet.packet_id,
                "transform": transform,
                "feedback_award": feedback_award,
            }

        self.inboxes[neighbor_id].append(packet)
        self._prioritize_inbox(neighbor_id)
        self._record_inbox_pressure()
        return {
            "success": True,
            "cost": cost,
            "delivered": False,
            "packet_id": packet.packet_id,
            "transform": transform,
        }

    def inhibit_neighbor(self, node_id: str, neighbor_id: str) -> dict:
        if neighbor_id == self.sink_id or not self.inhibit_available(node_id):
            return {"success": False, "cost": 0.0}
        source_state = self.state_for(node_id)
        source_state.atp = max(0.0, source_state.atp - self.inhibit_cost)
        if node_id == self.source_id:
            self._source_cycle_action_cost += self.inhibit_cost
        target_state = self.state_for(neighbor_id)
        target_state.inhibited_for = max(target_state.inhibited_for, self.inhibit_duration)
        return {"success": True, "cost": self.inhibit_cost}

    def advance_feedback(self) -> List[dict]:
        delivered = []
        remaining = []
        for pulse in self.pending_feedback:
            edge = pulse.next_edge()
            if edge is None:
                continue
            source_id, neighbor_id = edge.split("->", 1)
            if source_id not in self.node_states:
                # Dynamic topology changes can remove a node after a packet has
                # already committed a forward path through it. In that case the
                # stale feedback edge should be skipped rather than crashing the
                # whole workload run.
                pulse.advance()
                if not pulse.complete:
                    remaining.append(pulse)
                continue
            state = self.state_for(source_id)
            state.atp = min(state.max_atp, state.atp + pulse.amount)
            state.reward_buffer = min(state.max_atp, state.reward_buffer + pulse.amount)
            state.received_feedback += 1
            state.last_feedback_amount = pulse.amount
            state.last_match_ratio = pulse.bit_match_ratio
            transform_name = pulse.next_transform() or "identity"
            credit_signal = min(1.0, pulse.amount / max(self.feedback_amount, 1e-9))
            prior_credit = state.transform_credit.get(transform_name, 0.0)
            prior_debt = state.transform_debt.get(transform_name, 0.0)
            branch_key = _branch_debt_key(neighbor_id, transform_name)
            transform_matches_context = False
            resolved_context_bit, resolved_context_confidence, context_promotion_ready = self._resolved_feedback_context(
                source_id,
                pulse,
                transform_name,
                credit_signal=credit_signal,
            )
            if resolved_context_bit is None:
                state.transform_credit[transform_name] = min(
                    1.0,
                    0.55 * prior_credit + 0.45 * credit_signal,
                )
                state.branch_transform_credit[branch_key] = min(
                    1.0,
                    0.55 * state.branch_transform_credit.get(branch_key, 0.0)
                    + 0.45 * credit_signal,
                )
                state.transform_debt[transform_name] = max(0.0, prior_debt * 0.65)
            else:
                context_key = _context_credit_key(transform_name, int(resolved_context_bit))
                context_branch_key = _context_branch_debt_key(
                    neighbor_id,
                    transform_name,
                    int(resolved_context_bit),
                )
                branch_context_key = _branch_context_debt_key(
                    neighbor_id,
                    int(resolved_context_bit),
                )
                prior_context_credit = state.context_transform_credit.get(context_key, 0.0)
                prior_branch_credit = state.branch_transform_credit.get(branch_key, 0.0)
                prior_context_branch_credit = state.context_branch_transform_credit.get(
                    context_branch_key,
                    0.0,
                )
                prior_context_debt = state.context_transform_debt.get(context_key, 0.0)
                prior_branch_debt = state.branch_transform_debt.get(branch_key, 0.0)
                prior_context_branch_debt = state.context_branch_transform_debt.get(
                    context_branch_key,
                    0.0,
                )
                prior_branch_context_credit = state.branch_context_credit.get(
                    branch_context_key,
                    0.0,
                )
                prior_branch_context_debt = state.branch_context_debt.get(
                    branch_context_key,
                    0.0,
                )
                match_ratio = max(0.0, min(1.0, pulse.bit_match_ratio))
                transform_matches_context = (
                    match_ratio > 0.0
                    and _transform_matches_resolved_context(
                        pulse.task_id,
                        resolved_context_bit,
                        transform_name,
                    )
                )
                if match_ratio < TASK_CONTEXT_MATCH_FLOOR:
                    contradiction = (
                        TASK_CONTEXT_MATCH_FLOOR - match_ratio
                    ) / max(TASK_CONTEXT_MATCH_FLOOR, 1e-9)
                    debt_signal = max(contradiction, 1.0 - match_ratio)
                    stale_commitment = max(
                        prior_credit,
                        prior_context_credit,
                        prior_branch_credit,
                        prior_context_branch_credit,
                        prior_branch_context_credit,
                        prior_debt,
                        prior_context_debt,
                    )
                    debt_activation_ready = (
                        prior_credit >= DEBT_ACTIVATION_CREDIT
                        or prior_context_credit >= DEBT_ACTIVATION_CONTEXT_CREDIT
                        or prior_branch_credit >= DEBT_ACTIVATION_CONTEXT_CREDIT
                        or prior_context_branch_credit >= DEBT_ACTIVATION_CONTEXT_CREDIT
                        or prior_branch_context_credit >= DEBT_ACTIVATION_CONTEXT_CREDIT
                        or prior_debt >= DEBT_ACTIVATION_EXISTING
                        or prior_context_debt >= DEBT_ACTIVATION_EXISTING
                        or prior_branch_debt >= DEBT_ACTIVATION_EXISTING
                        or prior_context_branch_debt >= DEBT_ACTIVATION_EXISTING
                        or prior_branch_context_debt >= DEBT_ACTIVATION_EXISTING
                    )
                    if transform_matches_context:
                        quality_credit = max(
                            0.0,
                            min(1.0, match_ratio / max(TASK_CONTEXT_MATCH_FLOOR, 1e-9)),
                        )
                        residual_generic = max(0.16 * credit_signal, 0.14 * quality_credit)
                        residual_context = max(0.14 * credit_signal, 0.18 * quality_credit)
                        residual_branch = max(0.10 * credit_signal, 0.10 * quality_credit)
                        state.transform_credit[transform_name] = min(
                            1.0,
                            max(
                                residual_generic,
                                prior_credit * max(0.45, 0.84 - 0.12 * contradiction),
                            ),
                        )
                        state.context_transform_credit[context_key] = min(
                            1.0,
                            max(
                                residual_context,
                                prior_context_credit * max(0.48, 0.86 - 0.10 * contradiction),
                            ),
                        )
                        state.branch_transform_credit[branch_key] = min(
                            1.0,
                            max(
                                residual_branch,
                                prior_branch_credit * max(0.35, 0.72 - 0.14 * contradiction),
                            ),
                        )
                        state.context_branch_transform_credit[context_branch_key] = min(
                            1.0,
                            max(
                                residual_branch,
                                prior_context_branch_credit
                                * max(0.30, 0.68 - 0.16 * contradiction),
                            ),
                        )
                        state.branch_context_credit[branch_context_key] = min(
                            1.0,
                            max(
                                residual_branch,
                                prior_branch_context_credit
                                * max(0.26, 0.62 - 0.16 * contradiction),
                            ),
                        )
                        state.transform_debt[transform_name] = max(
                            0.0,
                            prior_debt * max(0.45, 0.82 - 0.18 * contradiction),
                        )
                        state.context_transform_debt[context_key] = max(
                            0.0,
                            prior_context_debt * max(0.45, 0.84 - 0.18 * contradiction),
                        )
                        branch_debt_signal = max(0.12, 0.55 * debt_signal)
                        if debt_activation_ready:
                            state.branch_transform_debt[branch_key] = min(
                                1.0,
                                0.72 * prior_branch_debt + 0.28 * branch_debt_signal,
                            )
                            state.context_branch_transform_debt[context_branch_key] = min(
                                1.0,
                                0.62 * prior_context_branch_debt + 0.38 * branch_debt_signal,
                            )
                            state.branch_context_debt[branch_context_key] = min(
                                1.0,
                                0.56 * prior_branch_context_debt + 0.44 * branch_debt_signal,
                            )
                        else:
                            state.branch_transform_debt[branch_key] = max(
                                0.0,
                                prior_branch_debt * 0.68,
                            )
                            state.context_branch_transform_debt[context_branch_key] = max(
                                0.0,
                                prior_context_branch_debt * 0.62,
                            )
                            state.branch_context_debt[branch_context_key] = max(
                                0.0,
                                prior_branch_context_debt * 0.58,
                            )
                    else:
                        residual_generic = 0.10 * credit_signal
                        residual_context = 0.05 * credit_signal
                        state.transform_credit[transform_name] = min(
                            1.0,
                            max(
                                residual_generic,
                                prior_credit * max(0.15, 0.58 - 0.24 * contradiction),
                            ),
                        )
                        state.context_transform_credit[context_key] = min(
                            1.0,
                            max(
                                residual_context,
                                prior_context_credit * max(0.05, 0.32 - 0.18 * contradiction),
                            ),
                        )
                        state.branch_transform_credit[branch_key] = min(
                            1.0,
                            max(
                                residual_context,
                                prior_branch_credit * max(0.08, 0.40 - 0.20 * contradiction),
                            ),
                        )
                        state.context_branch_transform_credit[context_branch_key] = min(
                            1.0,
                            max(
                                residual_context,
                                prior_context_branch_credit
                                * max(0.04, 0.28 - 0.16 * contradiction),
                            ),
                        )
                        state.branch_context_credit[branch_context_key] = min(
                            1.0,
                            max(
                                residual_context,
                                prior_branch_context_credit
                                * max(0.06, 0.34 - 0.20 * contradiction),
                            ),
                        )
                        if debt_activation_ready:
                            state.transform_debt[transform_name] = min(
                                1.0,
                                0.70 * prior_debt + 0.30 * debt_signal,
                            )
                            state.context_transform_debt[context_key] = min(
                                1.0,
                                0.55 * prior_context_debt + 0.45 * debt_signal,
                            )
                            state.branch_transform_debt[branch_key] = min(
                                1.0,
                                0.65 * prior_branch_debt + 0.35 * debt_signal,
                            )
                            state.context_branch_transform_debt[context_branch_key] = min(
                                1.0,
                                0.50 * prior_context_branch_debt + 0.50 * debt_signal,
                            )
                            state.branch_context_debt[branch_context_key] = min(
                                1.0,
                                0.45 * prior_branch_context_debt + 0.55 * debt_signal,
                            )
                        else:
                            mild_decay = max(0.0, 0.55 - 0.20 * stale_commitment)
                            state.transform_debt[transform_name] = max(
                                0.0,
                                prior_debt * mild_decay,
                            )
                            state.context_transform_debt[context_key] = max(
                                0.0,
                                prior_context_debt * max(0.45, mild_decay - 0.05),
                            )
                            state.branch_transform_debt[branch_key] = max(
                                0.0,
                                prior_branch_debt * 0.60,
                            )
                            state.context_branch_transform_debt[context_branch_key] = max(
                                0.0,
                                prior_context_branch_debt * 0.55,
                            )
                            state.branch_context_debt[branch_context_key] = max(
                                0.0,
                                prior_branch_context_debt * 0.52,
                            )
                else:
                    quality_credit = _quality_scaled_credit(match_ratio)
                    generic_mix = 0.18 + 0.12 * quality_credit
                    context_mix = 0.42 + 0.23 * quality_credit
                    branch_mix = 0.30 + 0.18 * quality_credit
                    context_branch_mix = 0.46 + 0.24 * quality_credit
                    branch_context_mix = 0.34 + 0.24 * quality_credit
                    effective_credit = 0.55 * credit_signal + 0.45 * quality_credit
                    state.transform_credit[transform_name] = min(
                        1.0,
                        (1.0 - generic_mix) * prior_credit + generic_mix * effective_credit,
                    )
                    state.context_transform_credit[context_key] = min(
                        1.0,
                        (1.0 - context_mix) * prior_context_credit + context_mix * effective_credit,
                    )
                    state.branch_transform_credit[branch_key] = min(
                        1.0,
                        (1.0 - branch_mix) * prior_branch_credit + branch_mix * effective_credit,
                    )
                    state.context_branch_transform_credit[context_branch_key] = min(
                        1.0,
                        (1.0 - context_branch_mix) * prior_context_branch_credit
                        + context_branch_mix * effective_credit,
                    )
                    state.branch_context_credit[branch_context_key] = min(
                        1.0,
                        (1.0 - branch_context_mix) * prior_branch_context_credit
                        + branch_context_mix * effective_credit,
                    )
                    state.transform_debt[transform_name] = max(
                        0.0,
                        prior_debt * max(0.10, 0.55 - 0.30 * quality_credit),
                    )
                    state.context_transform_debt[context_key] = max(
                        0.0,
                        prior_context_debt * max(0.05, 0.45 - 0.35 * quality_credit),
                    )
                    state.branch_transform_debt[branch_key] = max(
                        0.0,
                        prior_branch_debt * max(0.10, 0.55 - 0.35 * quality_credit),
                    )
                    state.context_branch_transform_debt[context_branch_key] = max(
                        0.0,
                        prior_context_branch_debt * max(0.05, 0.40 - 0.35 * quality_credit),
                    )
                    state.branch_context_debt[branch_context_key] = max(
                        0.0,
                        prior_branch_context_debt * max(0.04, 0.38 - 0.30 * quality_credit),
                    )
            delivered.append(
                {
                    "packet_id": pulse.packet_id,
                    "edge": edge,
                    "node_id": source_id,
                    "amount": pulse.amount,
                    "transform": transform_name,
                    "context_bit": resolved_context_bit,
                    "raw_context_bit": pulse.context_bit,
                    "effective_context_confidence": resolved_context_confidence,
                    "context_promotion_ready": context_promotion_ready,
                    "task_id": pulse.task_id,
                    "bit_match_ratio": pulse.bit_match_ratio,
                    "transform_matches_context": transform_matches_context,
                }
            )
            if self.topology_state is not None:
                self.topology_state.record_feedback(
                    source_id,
                    pulse.amount,
                    self.current_cycle,
                    self.morphogenesis_config,
                    neighbor_id=neighbor_id,
                )
            pulse.advance()
            if not pulse.complete:
                remaining.append(pulse)
        self.pending_feedback = remaining
        return delivered

    def tick(self, cycle: int | None = None) -> None:
        if cycle is not None:
            self.current_cycle = cycle
        for state in self.node_states.values():
            if state.inhibited_for > 0:
                state.inhibited_for -= 1
            state.last_feedback_amount *= 0.85
            state.last_match_ratio *= 0.90
            for transform_name in list(state.transform_credit.keys()):
                state.transform_credit[transform_name] *= 0.92
                if state.transform_credit[transform_name] < 1e-4:
                    del state.transform_credit[transform_name]
            for transform_name in list(state.transform_debt.keys()):
                state.transform_debt[transform_name] *= 0.90
                if state.transform_debt[transform_name] < 1e-4:
                    del state.transform_debt[transform_name]
            for key in list(state.context_transform_credit.keys()):
                state.context_transform_credit[key] *= 0.94
                if state.context_transform_credit[key] < 1e-4:
                    del state.context_transform_credit[key]
            for key in list(state.branch_transform_credit.keys()):
                state.branch_transform_credit[key] *= 0.93
                if state.branch_transform_credit[key] < 1e-4:
                    del state.branch_transform_credit[key]
            for key in list(state.context_branch_transform_credit.keys()):
                state.context_branch_transform_credit[key] *= 0.95
                if state.context_branch_transform_credit[key] < 1e-4:
                    del state.context_branch_transform_credit[key]
            for key in list(state.context_transform_debt.keys()):
                state.context_transform_debt[key] *= 0.92
                if state.context_transform_debt[key] < 1e-4:
                    del state.context_transform_debt[key]
            for key in list(state.branch_transform_debt.keys()):
                state.branch_transform_debt[key] *= 0.90
                if state.branch_transform_debt[key] < 1e-4:
                    del state.branch_transform_debt[key]
            for key in list(state.context_branch_transform_debt.keys()):
                state.context_branch_transform_debt[key] *= 0.91
                if state.context_branch_transform_debt[key] < 1e-4:
                    del state.context_branch_transform_debt[key]
            for key in list(state.branch_context_debt.keys()):
                state.branch_context_debt[key] *= 0.92
                if state.branch_context_debt[key] < 1e-4:
                    del state.branch_context_debt[key]
            for key in list(state.branch_context_credit.keys()):
                state.branch_context_credit[key] *= 0.94
                if state.branch_context_credit[key] < 1e-4:
                    del state.branch_context_credit[key]
        self._update_admission_substrate()
        self._update_capability_states()
        self._apply_capability_costs()
        if self.topology_state is not None:
            self.topology_state.update_node_counters(
                node_states=self.node_states,
                adjacency=self.adjacency,
                config=self.morphogenesis_config,
                cycle=self.current_cycle,
            )
        self._expire_stale_packets()
        self._admit_source_packets()
        self._prioritize_all_queues()
        self._record_inbox_pressure()

    def snapshot(self) -> dict:
        scored_packets = [
            packet for packet in self.delivered_packets if packet.bit_match_ratio is not None
        ]
        exact_matches = sum(1 for packet in scored_packets if packet.matched_target)
        partial_matches = sum(
            1
            for packet in scored_packets
            if packet.bit_match_ratio is not None and 0.0 < packet.bit_match_ratio < 1.0
        )
        return {
            "nodes": {
                node_id: {
                    "atp": round(state.atp, 4),
                    "reward_buffer": round(state.reward_buffer, 4),
                    "inbox": len(self.inboxes[node_id]),
                    "inhibited_for": state.inhibited_for,
                    "routed_packets": state.routed_packets,
                    "received_feedback": state.received_feedback,
                }
                for node_id, state in self.node_states.items()
            },
            "delivered_packets": len(self.delivered_packets),
            "dropped_packets": len(self.dropped_packets),
            "pending_feedback": len(self.pending_feedback),
            "source_buffer": len(self.source_buffer),
            "last_source_admission": self.last_source_admission,
            "source_admission_support": round(self.admission_substrate.support, 4),
            "source_admission_velocity": round(self.admission_substrate.velocity, 4),
            "last_source_efficiency": round(self.last_source_efficiency, 4),
            "exact_matches": exact_matches,
            "partial_matches": partial_matches,
            "mean_bit_accuracy": round(
                sum(packet.bit_match_ratio for packet in scored_packets)
                / max(len(scored_packets), 1),
                4,
            ),
            "overload_events": self.overload_events,
            "max_inbox_depth": self.max_inbox_depth,
            "max_source_backlog": self.max_source_backlog,
            "pending_growth_proposals": len(self.pending_growth_proposals),
            "capability_policy": self.capability_policy,
            "capability_summary": self.capability_summary(),
        }

    def export_runtime_state(self) -> dict:
        return {
            "topology": self.topology_state.to_dict() if self.topology_state is not None else None,
            "node_states": {
                node_id: asdict(state)
                for node_id, state in self.node_states.items()
            },
            "inboxes": {
                node_id: [asdict(packet) for packet in packets]
                for node_id, packets in self.inboxes.items()
            },
            "delivered_packets": [asdict(packet) for packet in self.delivered_packets],
            "pending_feedback": [asdict(pulse) for pulse in self.pending_feedback],
            "total_injected": self.total_injected,
            "admitted_packets": self.admitted_packets,
            "next_packet_id": self._next_packet_id,
            "current_cycle": self.current_cycle,
            "dropped_packets": [asdict(packet) for packet in self.dropped_packets],
            "source_buffer": [asdict(packet) for packet in self.source_buffer],
            "last_source_admission": self.last_source_admission,
            "source_admission_history": list(self.source_admission_history),
            "admission_substrate": self.admission_substrate.export_state(),
            "last_source_efficiency": self.last_source_efficiency,
            "source_efficiency_history": list(self.source_efficiency_history),
            "overload_events": self.overload_events,
            "max_inbox_depth": self.max_inbox_depth,
            "max_source_backlog": self.max_source_backlog,
            "pending_growth_proposals": [asdict(proposal) for proposal in self.pending_growth_proposals],
            "latent_context_trackers": self.export_latent_context_state(),
            "capability_states": self.export_capability_state(),
            "capability_policy": self.capability_policy,
        }

    def load_runtime_state(self, payload: dict) -> None:
        topology_payload = payload.get("topology")
        if topology_payload:
            self.topology_state = TopologyState.from_dict(topology_payload)
            self.sync_topology()
        self._next_packet_id = int(payload.get("next_packet_id", 1))
        self.packet_counter = itertools.count(self._next_packet_id)
        self.current_cycle = int(payload.get("current_cycle", 0))

        node_states = payload.get("node_states", {})
        for node_id, state_data in node_states.items():
            if node_id not in self.node_states:
                continue
            self.node_states[node_id] = NodeRuntimeState(**state_data)

        inboxes = payload.get("inboxes", {})
        self.inboxes = {node_id: [] for node_id in self.positions}
        for node_id, packets in inboxes.items():
            if node_id in self.inboxes:
                self.inboxes[node_id] = [SignalPacket(**packet) for packet in packets]

        self.delivered_packets = [
            SignalPacket(**packet) for packet in payload.get("delivered_packets", [])
        ]
        self.pending_feedback = [
            FeedbackPulse(**pulse) for pulse in payload.get("pending_feedback", [])
        ]
        self.dropped_packets = [
            SignalPacket(**packet) for packet in payload.get("dropped_packets", [])
        ]
        self.source_buffer = [
            SignalPacket(**packet) for packet in payload.get("source_buffer", [])
        ]
        self.total_injected = int(payload.get("total_injected", 0))
        self.admitted_packets = int(payload.get("admitted_packets", 0))
        self.last_source_admission = int(payload.get("last_source_admission", 0))
        self.source_admission_history = [
            int(value) for value in payload.get("source_admission_history", [])
        ]
        self.admission_substrate = AdmissionSubstrate.from_state(
            payload.get("admission_substrate")
        )
        self.last_source_efficiency = float(payload.get("last_source_efficiency", 0.0))
        self.source_efficiency_history = [
            float(value) for value in payload.get("source_efficiency_history", [])
        ]
        self.overload_events = int(payload.get("overload_events", 0))
        self.max_inbox_depth = int(payload.get("max_inbox_depth", 0))
        self.max_source_backlog = int(payload.get("max_source_backlog", 0))
        self.pending_growth_proposals = [
            GrowthProposal(**proposal)
            for proposal in payload.get("pending_growth_proposals", [])
        ]
        self.load_latent_context_state(payload.get("latent_context_trackers"))
        self.capability_policy = str(payload.get("capability_policy", self.capability_policy))
        self.load_capability_state(payload.get("capability_states"))

    def _feedback_pending_ratio(self, node_id: str) -> float:
        pending = 0
        for pulse in self.pending_feedback:
            if any(edge.startswith(f"{node_id}->") for edge in pulse.edge_path):
                pending += 1
        return min(1.0, pending / 3.0)

    def _packet_wait_age(self, packet: SignalPacket) -> int:
        anchor = packet.last_moved_cycle
        if anchor is None:
            anchor = packet.created_cycle
        return max(0, self.current_cycle - anchor)

    def _expire_stale_packets(self) -> None:
        if self.packet_ttl <= 0:
            return
        for node_id, packets in self.inboxes.items():
            kept = []
            for packet in packets:
                if self._packet_wait_age(packet) >= self.packet_ttl:
                    packet.dropped_cycle = self.current_cycle
                    packet.drop_reason = "ttl_expired"
                    self.dropped_packets.append(packet)
                    continue
                kept.append(packet)
            self.inboxes[node_id] = kept

    def _record_inbox_pressure(self) -> None:
        depths = [len(packets) for packets in self.inboxes.values()]
        if depths:
            self.max_inbox_depth = max(self.max_inbox_depth, max(depths))
        self.overload_events += sum(
            1 for depth in depths if depth > self.inbox_capacity
        )
        self.max_source_backlog = max(self.max_source_backlog, len(self.source_buffer))

    def _admit_source_packets(self) -> None:
        if self.source_id not in self.inboxes:
            return
        available_slots = max(0, self.inbox_capacity - len(self.inboxes[self.source_id]))
        if available_slots <= 0 or not self.source_buffer:
            self.last_source_admission = 0
            self.source_admission_history.append(0)
            self.max_source_backlog = max(self.max_source_backlog, len(self.source_buffer))
            return

        allowance = self._source_admission_allowance(available_slots)
        admitted = min(allowance, len(self.source_buffer))

        for _ in range(admitted):
            packet = self.source_buffer.pop(0)
            packet.last_moved_cycle = self.current_cycle
            self.inboxes[self.source_id].append(packet)
            self.admitted_packets += 1
        self.last_source_admission = admitted
        self.source_admission_history.append(admitted)
        self._prioritize_inbox(self.source_id)
        self.max_source_backlog = max(self.max_source_backlog, len(self.source_buffer))

    def _source_admission_allowance(self, available_slots: int) -> int:
        if self.source_admission_policy == "adaptive":
            return self._adaptive_source_admission_allowance(available_slots)

        allowance = available_slots
        if self.source_admission_rate is not None:
            allowance = min(allowance, max(0, self.source_admission_rate))
        return allowance

    def _adaptive_source_admission_allowance(self, available_slots: int) -> int:
        source_state = self.state_for(self.source_id)
        if source_state.dormant:
            return 0

        observation = self.observe_local(self.source_id)
        backlog = len(self.source_buffer)
        atp_ratio = observation.get("atp_ratio", 0.0)
        inbox_load = observation.get("inbox_load", 0.0)
        reward_ratio = observation.get("reward_buffer", 0.0)
        oldest_age = observation.get("oldest_packet_age", 0.0)
        feedback_pending = observation.get("feedback_pending", 0.0)

        ceiling = self.source_admission_max_rate
        if ceiling is None:
            ceiling = self.inbox_capacity

        return self.admission_substrate.allowance(
            available_slots=available_slots,
            backlog_pressure=min(1.0, backlog / max(self.inbox_capacity, 1)),
            atp_ratio=atp_ratio,
            reward_ratio=reward_ratio,
            inbox_load=inbox_load,
            oldest_age=oldest_age,
            feedback_pending=feedback_pending,
            min_rate=self.source_admission_min_rate,
            max_rate=ceiling,
        )

    def _update_admission_substrate(self) -> None:
        if self.source_admission_policy != "adaptive":
            return
        observation = self.observe_local(self.source_id)
        source_state = self.state_for(self.source_id)
        feedback_gained = source_state.received_feedback - self._source_cycle_start_feedback
        routed_packets = source_state.routed_packets - self._source_cycle_start_routed
        feedback_energy = max(0.0, feedback_gained) * self.feedback_amount
        action_cost = max(0.0, self._source_cycle_action_cost)
        net_energy = feedback_energy - action_cost
        update = self.admission_substrate.update(
            backlog_before=self._source_cycle_start_backlog,
            backlog_after=len(self.source_buffer),
            admitted=self.last_source_admission,
            routed_packets=max(0, routed_packets),
            feedback_gained=max(0, feedback_gained),
            action_cost=action_cost,
            feedback_energy=feedback_energy,
            net_energy=net_energy,
            inbox_load=observation.get("inbox_load", 0.0),
            oldest_age=observation.get("oldest_packet_age", 0.0),
            atp_ratio=observation.get("atp_ratio", 0.0),
        )
        self.last_source_efficiency = update["efficiency_signal"]
        self.source_efficiency_history.append(self.last_source_efficiency)

    def _prioritize_all_queues(self) -> None:
        for node_id in self.node_states:
            self._prioritize_inbox(node_id)

    def _prioritize_inbox(self, node_id: str) -> None:
        packets = self.inboxes.get(node_id)
        if not packets or len(packets) < 2:
            return
        packets.sort(
            key=lambda packet: (
                -self._packet_wait_age(packet),
                -len(packet.edge_path),
                packet.created_cycle,
                packet.packet_id,
            )
        )


class NativeSubstrateSystem:
    """Small Phase 8 scaffold for local-routing experiments."""

    def __init__(
        self,
        adjacency: Dict[str, Iterable[str]],
        positions: Dict[str, int],
        source_id: str,
        sink_id: str,
        *,
        max_atp: float = 1.0,
        selector_seed: int | None = None,
        packet_ttl: int = 8,
        source_admission_policy: str = "fixed",
        source_admission_rate: int | None = None,
        source_admission_min_rate: int = 1,
        source_admission_max_rate: int | None = None,
        morphogenesis_config: MorphogenesisConfig | None = None,
        source_sequence_context_enabled: bool = True,
        latent_transfer_split_enabled: bool = True,
        capability_policy: str | None = None,
        capability_control_config: CapabilityControlConfig | None = None,
    ) -> None:
        from .node_agent import NodeAgent

        normalized = {
            node_id: tuple(neighbor_ids)
            for node_id, neighbor_ids in adjacency.items()
        }
        self.selector_seed = selector_seed
        self.max_atp = max_atp
        resolved_policy = capability_policy
        if resolved_policy is None:
            resolved_policy = "growth-visible" if (morphogenesis_config and morphogenesis_config.enabled) else "fixed-visible"
        if resolved_policy not in CAPABILITY_POLICIES:
            raise ValueError(f"Unsupported capability policy: {resolved_policy}")
        self.topology_state = TopologyState.from_graph(
            normalized,
            positions,
            source_id=source_id,
            sink_id=sink_id,
        )
        self.capability_policy = resolved_policy
        self.capability_control_config = capability_control_config or CapabilityControlConfig()
        self.morphogenesis_config = morphogenesis_config or MorphogenesisConfig()
        if resolved_policy in ("growth-visible", "growth-latent", "self-selected"):
            self.morphogenesis_config.enabled = True
        self.topology_manager = TopologyManager(self.morphogenesis_config)
        self.environment = RoutingEnvironment(
            adjacency=normalized,
            positions=positions,
            source_id=source_id,
            sink_id=sink_id,
            max_atp=max_atp,
            packet_ttl=packet_ttl,
            source_admission_policy=source_admission_policy,
            source_admission_rate=source_admission_rate,
            source_admission_min_rate=source_admission_min_rate,
            source_admission_max_rate=source_admission_max_rate,
            topology_state=self.topology_state,
            morphogenesis_config=self.morphogenesis_config,
            source_sequence_context_enabled=source_sequence_context_enabled,
            latent_transfer_split_enabled=latent_transfer_split_enabled,
            capability_policy=resolved_policy,
            capability_control_config=self.capability_control_config,
        )
        self.global_cycle = 0
        self.session_start_cycle = 0
        self.capability_timeline: List[dict[str, object]] = []
        self.agents: Dict[str, NodeAgent] = {}
        for node_id in self.environment.agent_ids():
            self.ensure_agent(node_id)

    def _selector_seed_for(self, node_id: str) -> int | None:
        if self.selector_seed is None:
            return None
        ordered = self.environment.agent_ids()
        try:
            index = ordered.index(node_id)
        except ValueError:
            index = len(ordered)
        return self.selector_seed + index

    def ensure_agent(self, node_id: str, *, probationary: bool = False) -> None:
        from .node_agent import NodeAgent

        if node_id == self.environment.sink_id:
            return
        if node_id in self.agents:
            return
        self.agents[node_id] = NodeAgent(
            node_id=node_id,
            neighbor_ids=self.environment.neighbors_of(node_id),
            environment=self.environment,
            selector_seed=self._selector_seed_for(node_id),
            probationary=probationary,
        )

    def refresh_agent_neighbors(self, node_id: str) -> None:
        if node_id not in self.agents:
            self.ensure_agent(node_id)
            return
        self.agents[node_id].refresh_neighbors(self.environment.neighbors_of(node_id))

    def remove_agent(self, node_id: str) -> None:
        self.agents.pop(node_id, None)

    def rebuild_agents_from_topology(self) -> None:
        current_agents = set(self.agents)
        desired_agents = set(self.environment.agent_ids())
        for node_id in sorted(desired_agents - current_agents):
            probationary = False
            if self.topology_state is not None and node_id in self.topology_state.node_specs:
                probationary = self.topology_state.node_specs[node_id].probationary
            self.ensure_agent(node_id, probationary=probationary)
        for node_id in sorted(current_agents - desired_agents):
            self.remove_agent(node_id)
        for node_id in sorted(desired_agents):
            self.refresh_agent_neighbors(node_id)

    def inject_signal(self, count: int = 1) -> None:
        self.environment.inject_signal(count=count, cycle=self.global_cycle)

    def inject_signal_specs(self, signal_specs: Iterable[SignalSpec]) -> None:
        packets = [
            self.environment.create_packet(
                cycle=self.global_cycle,
                input_bits=spec.input_bits,
                payload_bits=spec.payload_bits,
                context_bit=spec.context_bit,
                task_id=spec.task_id,
                target_bits=spec.target_bits,
            )
            for spec in signal_specs
        ]
        self.environment.inject_packets(packets, cycle=self.global_cycle)

    def run_global_cycle(self) -> dict[str, object]:
        self.global_cycle += 1
        self.rebuild_agents_from_topology()
        self.environment.prepare_cycle(self.global_cycle)
        cycle_entries = {}
        for node_id in self.environment.agent_ids():
            cycle_entries[node_id] = self.agents[node_id].step()
        for packet in self.environment.delivered_packets:
            if packet.delivered_cycle is None:
                packet.delivered_cycle = self.global_cycle
        feedback = self.environment.advance_feedback()
        for node_id, agent in self.agents.items():
            local_feedback = [
                event for event in feedback if event.get("node_id") == node_id
            ]
            if local_feedback:
                agent.absorb_feedback(local_feedback)
        self.environment.tick(self.global_cycle)
        topology_events = []
        if self.topology_manager.should_checkpoint(self.global_cycle):
            topology_events = self.topology_manager.apply_checkpoint(self, self.global_cycle)
            self.rebuild_agents_from_topology()
        source_capability = self.environment.capability_snapshot(self.environment.source_id)
        self.capability_timeline.append(
            {
                "cycle": self.global_cycle,
                "source": source_capability,
                "active_latent_nodes": sum(
                    1
                    for state in self.environment.capability_states.values()
                    if state.latent_enabled
                ),
                "active_growth_nodes": sum(
                    1
                    for state in self.environment.capability_states.values()
                    if state.growth_enabled
                ),
            }
        )
        return {
            "cycle": self.global_cycle,
            "entries": cycle_entries,
            "feedback": feedback,
            "topology_events": [asdict(event) for event in topology_events],
            "snapshot": self.environment.snapshot(),
        }

    def summarize(self) -> dict[str, object]:
        delivered = self.environment.delivered_packets
        scored_packets = [
            packet for packet in delivered if packet.bit_match_ratio is not None
        ]
        context_breakdown = {}
        transform_counts = {}
        task_diagnostics = self._task_diagnostics(scored_packets)
        for packet in scored_packets:
            context_key = f"context_{packet.context_bit}"
            stats = context_breakdown.setdefault(
                context_key,
                {"count": 0, "exact_matches": 0, "bit_accuracy_total": 0.0},
            )
            stats["count"] += 1
            stats["exact_matches"] += 1 if packet.matched_target else 0
            stats["bit_accuracy_total"] += float(packet.bit_match_ratio or 0.0)
            if packet.transform_trace:
                transform_key = packet.transform_trace[-1]
                transform_counts[transform_key] = transform_counts.get(transform_key, 0) + 1
        for stats in context_breakdown.values():
            stats["mean_bit_accuracy"] = round(
                stats["bit_accuracy_total"] / max(stats["count"], 1),
                4,
            )
            del stats["bit_accuracy_total"]
        exact_matches = sum(1 for packet in scored_packets if packet.matched_target)
        partial_matches = sum(
            1
            for packet in scored_packets
            if packet.bit_match_ratio is not None and 0.0 < packet.bit_match_ratio < 1.0
        )
        mean_latency = (
            sum(
                max(0, (packet.delivered_cycle or self.global_cycle) - packet.created_cycle)
                for packet in delivered
            ) / len(delivered)
            if delivered
            else 0.0
        )
        mean_hops = (
            sum(len(packet.edge_path) for packet in delivered) / len(delivered)
            if delivered
            else 0.0
        )
        remaining_inboxes = sum(len(packets) for packets in self.environment.inboxes.values())
        node_atp_total = sum(
            state.atp for state in self.environment.node_states.values()
        )
        node_reward_total = sum(
            state.reward_buffer for state in self.environment.node_states.values()
        )
        dropped = self.environment.dropped_packets
        all_entries = [
            entry
            for agent in self.agents.values()
            for entry in agent.engine.memory.entries
        ]
        route_entries = [
            entry
            for entry in all_entries
            if entry.action.startswith("route:") or entry.action.startswith("route_transform:")
        ]
        mean_route_cost = (
            sum(entry.cost_secs for entry in route_entries) / len(route_entries)
            if route_entries
            else 0.0
        )
        total_action_cost = sum(entry.cost_secs for entry in all_entries)
        session_cycles = max(1, self.global_cycle - self.session_start_cycle)
        topology_events = list(self.topology_state.events) if self.topology_state is not None else []
        bud_events = [event for event in topology_events if event.event_type in ("bud_edge", "bud_node")]
        prune_events = [event for event in topology_events if event.event_type == "prune_edge"]
        apoptosis_events = [event for event in topology_events if event.event_type == "apoptosis"]
        dynamic_specs = [
            spec
            for spec in (self.topology_state.node_specs.values() if self.topology_state is not None else [])
            if spec.dynamic
        ]
        dynamic_edges = [
            edge
            for edge in (self.topology_state.edge_specs.values() if self.topology_state is not None else [])
            if edge.dynamic
        ]
        utilized_dynamic_nodes = 0
        first_feedback_samples = []
        for spec in dynamic_specs:
            state = self.environment.node_states.get(spec.node_id)
            if state is not None and (state.routed_packets > 0 or state.received_feedback > 0):
                utilized_dynamic_nodes += 1
            if spec.first_feedback_cycle is not None:
                first_feedback_samples.append(max(0, spec.first_feedback_cycle - spec.created_cycle))
        return {
            "capability_policy": self.capability_policy,
            "cycles": self.global_cycle,
            "injected_packets": self.environment.total_injected,
            "delivered_packets": len(delivered),
            "delivery_ratio": round(
                len(delivered) / max(self.environment.total_injected, 1),
                4,
            ),
            "dropped_packets": len(dropped),
            "drop_ratio": round(
                len(dropped) / max(self.environment.total_injected, 1),
                4,
            ),
            "remaining_inboxes": remaining_inboxes,
            "pending_feedback": len(self.environment.pending_feedback),
            "source_buffer": len(self.environment.source_buffer),
            "mean_latency": round(mean_latency, 4),
            "mean_hops": round(mean_hops, 4),
            "node_atp_total": round(node_atp_total, 4),
            "node_reward_total": round(node_reward_total, 4),
            "mean_route_cost": round(mean_route_cost, 5),
            "total_action_cost": round(total_action_cost, 5),
            "admitted_packets": self.environment.admitted_packets,
            "mean_source_admission": round(
                self.environment.admitted_packets / session_cycles,
                4,
            ),
            "last_source_admission": self.environment.last_source_admission,
            "source_admission_support": round(self.environment.admission_substrate.support, 4),
            "source_admission_velocity": round(self.environment.admission_substrate.velocity, 4),
            "mean_source_efficiency": round(
                sum(self.environment.source_efficiency_history)
                / max(len(self.environment.source_efficiency_history), 1),
                4,
            ),
            "last_source_efficiency": round(self.environment.last_source_efficiency, 4),
            "exact_matches": exact_matches,
            "partial_matches": partial_matches,
            "mean_bit_accuracy": round(
                sum(packet.bit_match_ratio for packet in scored_packets)
                / max(len(scored_packets), 1),
                4,
            ),
            "mean_feedback_award": round(
                sum(packet.feedback_award for packet in delivered) / max(len(delivered), 1),
                4,
            ),
            "overload_events": self.environment.overload_events,
            "max_inbox_depth": self.environment.max_inbox_depth,
            "max_source_backlog": self.environment.max_source_backlog,
            "node_count": len(self.topology_state.node_specs) if self.topology_state is not None else len(self.environment.positions),
            "edge_count": len(self.topology_state.edge_specs) if self.topology_state is not None else sum(len(neighbors) for neighbors in self.environment.adjacency.values()),
            "bud_attempts": len(bud_events),
            "bud_successes": len(bud_events),
            "prune_events": len(prune_events),
            "apoptosis_events": len(apoptosis_events),
            "dynamic_node_count": len(dynamic_specs),
            "new_node_utilization": round(
                utilized_dynamic_nodes / max(len(dynamic_specs), 1),
                4,
            ),
            "mean_dynamic_node_value": round(
                sum(spec.value_recent for spec in dynamic_specs) / max(len(dynamic_specs), 1),
                4,
            ) if dynamic_specs else None,
            "mean_dynamic_net_energy": round(
                sum(spec.net_energy_recent for spec in dynamic_specs) / max(len(dynamic_specs), 1),
                4,
            ) if dynamic_specs else None,
            "mean_dynamic_edge_value": round(
                sum(edge.value_recent for edge in dynamic_edges) / max(len(dynamic_edges), 1),
                4,
            ) if dynamic_edges else None,
            "time_to_first_feedback": round(
                sum(first_feedback_samples) / max(len(first_feedback_samples), 1),
                4,
            ) if first_feedback_samples else None,
            "context_breakdown": context_breakdown,
            "final_transform_counts": transform_counts,
            "task_diagnostics": task_diagnostics,
            "active_edges": {
                node_id: agent.substrate.active_neighbors()
                for node_id, agent in self.agents.items()
            },
            "pattern_counts": {
                node_id: len(agent.substrate.constraint_patterns)
                for node_id, agent in self.agents.items()
            },
            "supports": {
                node_id: {
                    neighbor_id: round(agent.substrate.support(neighbor_id), 4)
                    for neighbor_id in agent.neighbor_ids
                }
                for node_id, agent in self.agents.items()
            },
            "action_supports": {
                node_id: {
                    neighbor_id: {
                        transform_name: round(
                            agent.substrate.action_support(neighbor_id, transform_name),
                            4,
                        )
                        for transform_name in ("identity", "rotate_left_1", "xor_mask_1010", "xor_mask_0101")
                    }
                    for neighbor_id in agent.neighbor_ids
                }
                for node_id, agent in self.agents.items()
            },
            "context_action_supports": {
                node_id: {
                    neighbor_id: {
                        f"context_{context_bit}": {
                            transform_name: round(
                                agent.substrate.action_support(
                                    neighbor_id,
                                    transform_name,
                                    context_bit,
                                ),
                                4,
                            )
                            for transform_name in ("identity", "rotate_left_1", "xor_mask_1010", "xor_mask_0101")
                        }
                        for context_bit in agent.substrate.supported_contexts
                    }
                    for neighbor_id in agent.neighbor_ids
                }
                for node_id, agent in self.agents.items()
            },
            "substrate_maintenance": {
                node_id: {
                    key: round(value, 4)
                    for key, value in agent.substrate.maintenance_metrics().items()
                }
                for node_id, agent in self.agents.items()
            },
            "capability_timeline": list(self.capability_timeline),
            "latent_recruitment_cycles": {
                node_id: list(snapshot["latent_recruitment_cycles"])
                for node_id, snapshot in self.environment.capability_summary().items()
            },
            "growth_recruitment_cycles": {
                node_id: list(snapshot["growth_recruitment_cycles"])
                for node_id, snapshot in self.environment.capability_summary().items()
            },
            "capability_supports": self.environment.capability_summary(),
        }

    def _task_diagnostics(self, scored_packets: Sequence[SignalPacket]) -> dict[str, object]:
        diagnostics: dict[str, object] = {
            "packets_evaluated": len(scored_packets),
            "contexts": {},
            "overall": {
                "exact_matches": 0,
                "partial_matches": 0,
                "zero_matches": 0,
                "identity_fallbacks": 0,
                "wrong_transform_family": 0,
                "route_wrong_transform_potentially_right": 0,
                "route_right_transform_wrong": 0,
                "transform_unstable_across_inferred_context_boundary": 0,
                "delayed_correction": 0,
                "stale_context_support_suspicions": 0,
                "branch_counts": {},
                "mismatch_branch_counts": {},
                "final_transform_counts": {},
                "mismatch_transform_counts": {},
            },
        }
        overall = diagnostics["overall"]
        successful_branches = self._successful_branches_by_group(scored_packets)
        for packet in scored_packets:
            context_key = f"context_{packet.context_bit}"
            expected_transform = _expected_transform_for_task(packet.task_id, packet.context_bit)
            final_transform = packet.transform_trace[-1] if packet.transform_trace else "identity"
            first_hop = self._packet_first_hop(packet)
            stats = diagnostics["contexts"].setdefault(
                context_key,
                {
                    "count": 0,
                    "expected_transform": expected_transform,
                    "exact_matches": 0,
                    "partial_matches": 0,
                    "zero_matches": 0,
                    "identity_fallbacks": 0,
                    "wrong_transform_family": 0,
                    "route_wrong_transform_potentially_right": 0,
                    "route_right_transform_wrong": 0,
                    "transform_unstable_across_inferred_context_boundary": 0,
                    "delayed_correction": 0,
                    "stale_context_support_suspicions": 0,
                    "mean_bit_accuracy_total": 0.0,
                    "final_transform_counts": {},
                    "mismatch_transform_counts": {},
                    "branch_counts": {},
                    "mismatch_branch_counts": {},
                },
            )
            stats["count"] += 1
            stats["mean_bit_accuracy_total"] += float(packet.bit_match_ratio or 0.0)
            self._increment_count(stats["final_transform_counts"], final_transform)
            self._increment_count(overall["final_transform_counts"], final_transform)
            self._increment_count(stats["branch_counts"], first_hop)
            self._increment_count(overall["branch_counts"], first_hop)

            bit_match_ratio = float(packet.bit_match_ratio or 0.0)
            if packet.matched_target:
                stats["exact_matches"] += 1
                overall["exact_matches"] += 1
            elif bit_match_ratio > 0.0:
                stats["partial_matches"] += 1
                overall["partial_matches"] += 1
            else:
                stats["zero_matches"] += 1
                overall["zero_matches"] += 1

            if not packet.matched_target:
                self._increment_count(stats["mismatch_transform_counts"], final_transform)
                self._increment_count(overall["mismatch_transform_counts"], final_transform)
                self._increment_count(stats["mismatch_branch_counts"], first_hop)
                self._increment_count(overall["mismatch_branch_counts"], first_hop)
                if final_transform == "identity":
                    stats["identity_fallbacks"] += 1
                    overall["identity_fallbacks"] += 1
                if (
                    expected_transform is not None
                    and final_transform == expected_transform
                ):
                    stats["route_wrong_transform_potentially_right"] += 1
                    overall["route_wrong_transform_potentially_right"] += 1
                if self._route_right_transform_wrong(
                    packet,
                    expected_transform=expected_transform,
                    final_transform=final_transform,
                    first_hop=first_hop,
                    successful_branches=successful_branches,
                ):
                    stats["route_right_transform_wrong"] += 1
                    overall["route_right_transform_wrong"] += 1
                if self._latent_transform_instability(
                    scored_packets,
                    packet=packet,
                    final_transform=final_transform,
                ):
                    stats["transform_unstable_across_inferred_context_boundary"] += 1
                    overall["transform_unstable_across_inferred_context_boundary"] += 1
                if self._delayed_correction(
                    scored_packets,
                    packet=packet,
                    first_hop=first_hop,
                    final_transform=final_transform,
                ):
                    stats["delayed_correction"] += 1
                    overall["delayed_correction"] += 1
                if expected_transform is not None and final_transform != expected_transform:
                    stats["wrong_transform_family"] += 1
                    overall["wrong_transform_family"] += 1
                    if self._suspect_stale_context_support(
                        packet,
                        expected_transform=expected_transform,
                        final_transform=final_transform,
                        first_hop=first_hop,
                    ):
                        stats["stale_context_support_suspicions"] += 1
                        overall["stale_context_support_suspicions"] += 1

        for stats in diagnostics["contexts"].values():
            stats["mean_bit_accuracy"] = round(
                stats["mean_bit_accuracy_total"] / max(stats["count"], 1),
                4,
            )
            del stats["mean_bit_accuracy_total"]
        diagnostics["admission"] = {
            "mean_source_admission": round(
                self.environment.admitted_packets
                / max(1, self.global_cycle - self.session_start_cycle),
                4,
            ),
            "max_source_backlog": self.environment.max_source_backlog,
            "mean_latency": round(
                sum(
                    max(0, (packet.delivered_cycle or self.global_cycle) - packet.created_cycle)
                    for packet in scored_packets
                )
                / max(len(scored_packets), 1),
                4,
            ),
            "overload_events": self.environment.overload_events,
        }
        return diagnostics

    @staticmethod
    def _increment_count(counter: dict[str, int], key: str) -> None:
        counter[key] = counter.get(key, 0) + 1

    def _packet_first_hop(self, packet: SignalPacket) -> str:
        if not packet.edge_path:
            return "none"
        edge = packet.edge_path[0]
        if "->" not in edge:
            return "none"
        source_id, neighbor_id = edge.split("->", 1)
        if source_id != self.environment.source_id:
            return "none"
        return neighbor_id

    def _suspect_stale_context_support(
        self,
        packet: SignalPacket,
        *,
        expected_transform: str,
        final_transform: str,
        first_hop: str,
    ) -> bool:
        if (
            packet.context_bit is None
            or first_hop == "none"
            or self.environment.source_id not in self.agents
        ):
            return False
        source_agent = self.agents[self.environment.source_id]
        if first_hop not in source_agent.neighbor_ids:
            return False
        chosen_support = source_agent.substrate.action_support(
            first_hop,
            final_transform,
            packet.context_bit,
        )
        expected_support = source_agent.substrate.action_support(
            first_hop,
            expected_transform,
            packet.context_bit,
        )
        return chosen_support > expected_support + 0.05

    def _successful_branches_by_group(
        self,
        scored_packets: Sequence[SignalPacket],
    ) -> dict[tuple[str, str], set[str]]:
        successful: dict[tuple[str, str], set[str]] = {}
        for packet in scored_packets:
            if not packet.matched_target:
                continue
            group_key = (str(packet.task_id), f"context_{packet.context_bit}")
            successful.setdefault(group_key, set()).add(self._packet_first_hop(packet))
        return successful

    def _route_right_transform_wrong(
        self,
        packet: SignalPacket,
        *,
        expected_transform: str | None,
        final_transform: str,
        first_hop: str,
        successful_branches: dict[tuple[str, str], set[str]],
    ) -> bool:
        if expected_transform is None or final_transform == expected_transform:
            return False
        if first_hop == "sink":
            return True
        group_key = (str(packet.task_id), f"context_{packet.context_bit}")
        return first_hop in successful_branches.get(group_key, set())

    def _latent_transform_instability(
        self,
        scored_packets: Sequence[SignalPacket],
        *,
        packet: SignalPacket,
        final_transform: str,
    ) -> bool:
        if packet.context_bit is not None or packet.task_id is None:
            return False
        admissible = set(_candidate_transforms_for_task(packet.task_id))
        if final_transform not in admissible or len(admissible) < 2:
            return False
        siblings = [
            other
            for other in scored_packets
            if other is not packet
            and other.context_bit is None
            and other.task_id == packet.task_id
        ]
        for other in siblings[-4:]:
            other_transform = other.transform_trace[-1] if other.transform_trace else "identity"
            if other_transform in admissible and other_transform != final_transform:
                return True
        return False

    def _delayed_correction(
        self,
        scored_packets: Sequence[SignalPacket],
        *,
        packet: SignalPacket,
        first_hop: str,
        final_transform: str,
    ) -> bool:
        start_index = -1
        for index, candidate in enumerate(scored_packets):
            if candidate is packet:
                start_index = index
                break
        if start_index < 0:
            return False
        seen_same_task = 0
        for other in scored_packets[start_index + 1 :]:
            if other.task_id != packet.task_id:
                continue
            seen_same_task += 1
            if seen_same_task > 3:
                break
            other_hop = self._packet_first_hop(other)
            other_transform = other.transform_trace[-1] if other.transform_trace else "identity"
            if not other.matched_target:
                continue
            if other_hop == first_hop or other_transform == final_transform:
                return True
        return False

    def run_workload(
        self,
        *,
        cycles: int,
        initial_packets: int,
        packet_schedule: Dict[int, int] | None = None,
        initial_signal_specs: Sequence[SignalSpec] | None = None,
        signal_schedule_specs: Dict[int, Sequence[SignalSpec]] | None = None,
    ) -> dict[str, object]:
        if initial_signal_specs:
            self.inject_signal_specs(initial_signal_specs)
        elif initial_packets > 0:
            self.inject_signal(count=initial_packets)
        schedule = dict(packet_schedule or {})
        signal_schedule = dict(signal_schedule_specs or {})
        reports = []
        for cycle_index in range(1, cycles + 1):
            scheduled_specs = signal_schedule.get(cycle_index)
            if scheduled_specs:
                self.inject_signal_specs(scheduled_specs)
            else:
                scheduled = schedule.get(cycle_index, 0)
                if scheduled > 0:
                    self.inject_signal(count=scheduled)
            reports.append(self.run_global_cycle())
        return {
            "reports": reports,
            "summary": self.summarize(),
        }

    def _task_ids_seen(self) -> list[str]:
        task_ids = {
            str(packet.task_id)
            for packet in self.environment.delivered_packets
            if packet.task_id is not None
        }
        for tracker in self.environment.latent_context_trackers.values():
            task_ids.update(str(task_id) for task_id in tracker.task_states.keys())
        return sorted(task_ids)

    def save_carryover(self, root_dir: str | Path) -> Path:
        target = Path(root_dir)
        target.mkdir(parents=True, exist_ok=True)
        nodes_dir = target / "nodes"
        nodes_dir.mkdir(parents=True, exist_ok=True)

        for node_id, agent in self.agents.items():
            agent.save_carryover(nodes_dir / f"{node_id}.json")

        manifest = {
            "global_cycle": self.global_cycle,
            "environment": self.environment.export_runtime_state(),
            "agent_ids": list(self.agents.keys()),
            "topology": self.topology_state.to_dict(),
            "task_ids_seen": self._task_ids_seen(),
            "capability_policy": self.capability_policy,
            "capability_timeline": list(self.capability_timeline),
        }
        manifest_path = target / "system_state.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest_path

    def save_memory_carryover(self, root_dir: str | Path) -> Path:
        target = Path(root_dir)
        target.mkdir(parents=True, exist_ok=True)
        nodes_dir = target / "nodes"
        nodes_dir.mkdir(parents=True, exist_ok=True)
        for node_id, agent in self.agents.items():
            agent.save_carryover(nodes_dir / f"{node_id}.json")

        manifest = {
            "global_cycle": self.global_cycle,
            "agent_ids": list(self.agents.keys()),
            "admission_substrate": self.environment.admission_substrate.export_state(),
            "topology": self.topology_state.to_dict(),
            "latent_context_trackers": self.environment.export_latent_context_state(),
            "capability_states": self.environment.export_capability_state(),
            "task_ids_seen": self._task_ids_seen(),
            "capability_policy": self.capability_policy,
        }
        manifest_path = target / "memory_state.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest_path

    def save_substrate_carryover(self, root_dir: str | Path) -> Path:
        target = Path(root_dir)
        target.mkdir(parents=True, exist_ok=True)
        nodes_dir = target / "nodes"
        nodes_dir.mkdir(parents=True, exist_ok=True)
        for node_id, agent in self.agents.items():
            agent.save_substrate_carryover(nodes_dir / f"{node_id}.json")

        manifest = {
            "global_cycle": self.global_cycle,
            "agent_ids": list(self.agents.keys()),
            "admission_substrate": self.environment.admission_substrate.export_state(),
            "topology": self.topology_state.to_dict(),
            "latent_context_trackers": self.environment.export_latent_context_state(),
            "capability_states": self.environment.export_capability_state(),
            "task_ids_seen": self._task_ids_seen(),
            "capability_policy": self.capability_policy,
        }
        manifest_path = target / "substrate_state.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest_path

    def load_memory_carryover(self, root_dir: str | Path) -> bool:
        target = Path(root_dir)
        manifest_path = target / "memory_state.json"
        if not manifest_path.exists():
            return False
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.global_cycle = int(manifest.get("global_cycle", 0))
        self.session_start_cycle = self.global_cycle
        self.capability_policy = str(manifest.get("capability_policy", self.capability_policy))
        self.environment.capability_policy = self.capability_policy
        topology_payload = manifest.get("topology")
        if topology_payload:
            self.topology_state = TopologyState.from_dict(topology_payload)
            self.environment.topology_state = self.topology_state
            self.environment.sync_topology()
            self.rebuild_agents_from_topology()
        self.environment.admission_substrate = AdmissionSubstrate.from_state(
            manifest.get("admission_substrate")
        )
        self.environment.load_latent_context_state(manifest.get("latent_context_trackers"))
        self.environment.load_capability_state(manifest.get("capability_states"))
        self.environment.configure_transfer_regime(
            task_ids_seen=manifest.get("task_ids_seen", []),
            start_cycle=self.global_cycle,
        )
        nodes_dir = target / "nodes"
        for node_id, agent in self.agents.items():
            agent.load_carryover(nodes_dir / f"{node_id}.json")
        return True

    def load_substrate_carryover(self, root_dir: str | Path) -> bool:
        target = Path(root_dir)
        manifest_path = target / "substrate_state.json"
        if not manifest_path.exists():
            return False
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.global_cycle = int(manifest.get("global_cycle", 0))
        self.session_start_cycle = self.global_cycle
        self.capability_policy = str(manifest.get("capability_policy", self.capability_policy))
        self.environment.capability_policy = self.capability_policy
        topology_payload = manifest.get("topology")
        if topology_payload:
            self.topology_state = TopologyState.from_dict(topology_payload)
            self.environment.topology_state = self.topology_state
            self.environment.sync_topology()
            self.rebuild_agents_from_topology()
        self.environment.admission_substrate = AdmissionSubstrate.from_state(
            manifest.get("admission_substrate")
        )
        self.environment.load_latent_context_state(manifest.get("latent_context_trackers"))
        self.environment.load_capability_state(manifest.get("capability_states"))
        self.environment.configure_transfer_regime(
            task_ids_seen=manifest.get("task_ids_seen", []),
            start_cycle=self.global_cycle,
        )
        nodes_dir = target / "nodes"
        for node_id, agent in self.agents.items():
            agent.load_substrate_carryover(nodes_dir / f"{node_id}.json")
        return True

    def load_carryover(self, root_dir: str | Path) -> bool:
        target = Path(root_dir)
        manifest_path = target / "system_state.json"
        if not manifest_path.exists():
            return False

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.global_cycle = int(manifest.get("global_cycle", 0))
        self.session_start_cycle = self.global_cycle
        self.environment.load_runtime_state(manifest.get("environment", {}))
        self.capability_policy = str(manifest.get("capability_policy", self.capability_policy))
        self.environment.capability_policy = self.capability_policy
        self.capability_timeline = list(manifest.get("capability_timeline", []))
        self.environment.configure_transfer_regime(
            task_ids_seen=manifest.get("task_ids_seen", []),
            start_cycle=self.global_cycle,
        )
        self.topology_state = self.environment.topology_state
        self.rebuild_agents_from_topology()

        nodes_dir = target / "nodes"
        for node_id, agent in self.agents.items():
            agent.load_carryover(nodes_dir / f"{node_id}.json")
        return True
