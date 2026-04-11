from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List


DEFAULT_SIGNAL_WIDTH = 4
DEFAULT_LOCAL_UNIT_PRESET = "default"


def _normalize_bits(
    bits: Iterable[int] | None,
    *,
    width: int = DEFAULT_SIGNAL_WIDTH,
) -> List[int]:
    if bits is None:
        return []
    normalized = [1 if int(bit) else 0 for bit in bits]
    if len(normalized) > width:
        raise ValueError(f"bit vector width {len(normalized)} exceeds supported width {width}")
    return normalized


@dataclass
class SignalPacket:
    packet_id: str
    origin: str
    target: str
    created_cycle: int
    input_bits: List[int] = field(default_factory=list)
    payload_bits: List[int] = field(default_factory=list)
    context_bit: int | None = None
    task_id: str | None = None
    c_task_transform_belief: Dict[str, float] = field(default_factory=dict)
    c_task_hypothesis_transform: str | None = None
    c_task_hypothesis_confidence: float = 0.0
    c_task_resolved_transform: str | None = None
    c_task_resolution_confidence: float = 0.0
    c_task_preserve_mode: bool = False
    c_task_preserve_pressure: float = 0.0
    c_task_reopen_pressure: float = 0.0
    c_task_resolution_source: str | None = None
    c_task_resolution_depth: int = 0
    c_task_preserve_violation_count: int = 0
    teacher_trace: List[Dict[str, object]] = field(default_factory=list)
    selected_transform_trace: List[str] = field(default_factory=list)
    transform_trace: List[str] = field(default_factory=list)
    forced_transform_applied: bool = False
    forced_from_transform: str | None = None
    expected_transform_at_delivery: str | None = None
    substrate_bit_match_ratio: float | None = None
    substrate_matched_target: bool | None = None
    matched_target: bool | None = None
    bit_match_ratio: float | None = None
    feedback_award: float = 0.0
    target_bits: List[int] = field(default_factory=list)
    hops: List[str] = field(default_factory=list)
    edge_path: List[str] = field(default_factory=list)
    delivered: bool = False
    delivered_cycle: int | None = None
    last_moved_cycle: int | None = None
    dropped_cycle: int | None = None
    drop_reason: str | None = None

    def __post_init__(self) -> None:
        self.input_bits = _normalize_bits(self.input_bits)
        if self.payload_bits:
            self.payload_bits = _normalize_bits(self.payload_bits)
        else:
            self.payload_bits = list(self.input_bits)
        self.target_bits = _normalize_bits(self.target_bits)
        self.teacher_trace = [dict(item) for item in self.teacher_trace]
        self.selected_transform_trace = [str(item) for item in self.selected_transform_trace]
        self.transform_trace = [str(item) for item in self.transform_trace]
        if self.context_bit is not None:
            self.context_bit = int(self.context_bit)
        self.c_task_transform_belief = {
            str(key): max(0.0, min(1.0, float(value)))
            for key, value in dict(self.c_task_transform_belief).items()
        }
        if self.c_task_hypothesis_transform is not None:
            self.c_task_hypothesis_transform = str(self.c_task_hypothesis_transform)
        self.c_task_hypothesis_confidence = max(
            0.0,
            min(1.0, float(self.c_task_hypothesis_confidence)),
        )
        if self.c_task_resolved_transform is not None:
            self.c_task_resolved_transform = str(self.c_task_resolved_transform)
        self.c_task_resolution_confidence = max(
            0.0,
            min(1.0, float(self.c_task_resolution_confidence)),
        )
        self.c_task_preserve_mode = bool(self.c_task_preserve_mode)
        self.c_task_preserve_pressure = max(
            0.0,
            min(1.0, float(self.c_task_preserve_pressure)),
        )
        self.c_task_reopen_pressure = max(
            0.0,
            min(1.0, float(self.c_task_reopen_pressure)),
        )
        if self.c_task_resolution_source is not None:
            self.c_task_resolution_source = str(self.c_task_resolution_source)
        self.c_task_resolution_depth = max(0, int(self.c_task_resolution_depth))
        self.c_task_preserve_violation_count = max(
            0,
            int(self.c_task_preserve_violation_count),
        )


@dataclass(frozen=True)
class SignalSpec:
    input_bits: List[int]
    payload_bits: List[int] | None = None
    context_bit: int | None = None
    task_id: str | None = None
    target_bits: List[int] | None = None
    origin: str | None = None


@dataclass
class FeedbackPulse:
    packet_id: str
    edge_path: List[str]
    amount: float
    transform_path: List[str] = field(default_factory=list)
    context_bit: int | None = None
    task_id: str | None = None
    bit_match_ratio: float = 0.0
    matched_target: bool = False
    cursor: int = 0

    def next_edge(self) -> str | None:
        reverse_index = len(self.edge_path) - 1 - self.cursor
        if reverse_index < 0:
            return None
        return self.edge_path[reverse_index]

    def next_transform(self) -> str | None:
        reverse_index = len(self.transform_path) - 1 - self.cursor
        if reverse_index < 0:
            return None
        return self.transform_path[reverse_index]

    def advance(self) -> None:
        self.cursor += 1

    @property
    def complete(self) -> bool:
        return self.cursor >= len(self.edge_path)


@dataclass
class SignalState:
    accumulators: Dict[str, float] = field(default_factory=dict)
    cooldowns: Dict[str, int] = field(default_factory=dict)
    delay_streaks: Dict[str, int] = field(default_factory=dict)
    base_threshold: float = 0.68
    accumulator_decay: float = 0.82
    cooldown_ticks: int = 1
    suppressed_route_attempts: int = 0
    fired_route_count: int = 0
    last_fire_cycle: int = -1
    last_fired_channel: str | None = None


@dataclass
class ContextState:
    ambiguity_reservoir: float = 0.0
    commitment_margin: float = 1.0
    latent_confidence: float = 0.0
    unresolved_streak: int = 0
    transform_belief: Dict[str, float] = field(default_factory=dict)
    hypothesis_transform: str | None = None
    hypothesis_confidence: float = 0.0
    dominant_transform: str | None = None
    transform_confidence: float = 0.0
    preserve_mode: bool = False
    preserve_pressure: float = 0.0
    reopen_pressure: float = 0.0
    contradiction_load: float = 0.0
    commitment_age: int = 0


@dataclass
class PlasticityState:
    plasticity_gate: float = 0.0
    promotion_ready: bool = False
    growth_request_pressure: float = 0.0
    failed_resolution_streak: int = 0


@dataclass
class LocalUnitState:
    signal: SignalState = field(default_factory=SignalState)
    context: ContextState = field(default_factory=ContextState)
    plasticity: PlasticityState = field(default_factory=PlasticityState)

    def to_dict(self) -> Dict[str, object]:
        return {
            "signal": {
                "accumulators": {
                    str(key): float(value)
                    for key, value in self.signal.accumulators.items()
                },
                "cooldowns": {
                    str(key): int(value)
                    for key, value in self.signal.cooldowns.items()
                },
                "delay_streaks": {
                    str(key): int(value)
                    for key, value in self.signal.delay_streaks.items()
                },
                "base_threshold": float(self.signal.base_threshold),
                "accumulator_decay": float(self.signal.accumulator_decay),
                "cooldown_ticks": int(self.signal.cooldown_ticks),
                "suppressed_route_attempts": int(self.signal.suppressed_route_attempts),
                "fired_route_count": int(self.signal.fired_route_count),
                "last_fire_cycle": int(self.signal.last_fire_cycle),
                "last_fired_channel": self.signal.last_fired_channel,
            },
            "context": {
                "ambiguity_reservoir": float(self.context.ambiguity_reservoir),
                "commitment_margin": float(self.context.commitment_margin),
                "latent_confidence": float(self.context.latent_confidence),
                "unresolved_streak": int(self.context.unresolved_streak),
                "transform_belief": {
                    str(key): float(value)
                    for key, value in self.context.transform_belief.items()
                },
                "hypothesis_transform": self.context.hypothesis_transform,
                "hypothesis_confidence": float(self.context.hypothesis_confidence),
                "dominant_transform": self.context.dominant_transform,
                "transform_confidence": float(self.context.transform_confidence),
                "preserve_mode": bool(self.context.preserve_mode),
                "preserve_pressure": float(self.context.preserve_pressure),
                "reopen_pressure": float(self.context.reopen_pressure),
                "contradiction_load": float(self.context.contradiction_load),
                "commitment_age": int(self.context.commitment_age),
            },
            "plasticity": {
                "plasticity_gate": float(self.plasticity.plasticity_gate),
                "promotion_ready": bool(self.plasticity.promotion_ready),
                "growth_request_pressure": float(self.plasticity.growth_request_pressure),
                "failed_resolution_streak": int(self.plasticity.failed_resolution_streak),
            },
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object] | None) -> "LocalUnitState":
        if not payload:
            return cls()
        signal_payload = dict(payload.get("signal", {}))
        context_payload = dict(payload.get("context", {}))
        plasticity_payload = dict(payload.get("plasticity", {}))
        return cls(
            signal=SignalState(
                accumulators={
                    str(key): float(value)
                    for key, value in dict(signal_payload.get("accumulators", {})).items()
                },
                cooldowns={
                    str(key): int(value)
                    for key, value in dict(signal_payload.get("cooldowns", {})).items()
                },
                delay_streaks={
                    str(key): int(value)
                    for key, value in dict(signal_payload.get("delay_streaks", {})).items()
                },
                base_threshold=float(signal_payload.get("base_threshold", 0.68)),
                accumulator_decay=float(signal_payload.get("accumulator_decay", 0.82)),
                cooldown_ticks=int(signal_payload.get("cooldown_ticks", 1)),
                suppressed_route_attempts=int(signal_payload.get("suppressed_route_attempts", 0)),
                fired_route_count=int(signal_payload.get("fired_route_count", 0)),
                last_fire_cycle=int(signal_payload.get("last_fire_cycle", -1)),
                last_fired_channel=signal_payload.get("last_fired_channel"),
            ),
            context=ContextState(
                ambiguity_reservoir=float(context_payload.get("ambiguity_reservoir", 0.0)),
                commitment_margin=float(context_payload.get("commitment_margin", 1.0)),
                latent_confidence=float(context_payload.get("latent_confidence", 0.0)),
                unresolved_streak=int(context_payload.get("unresolved_streak", 0)),
                transform_belief={
                    str(key): float(value)
                    for key, value in dict(context_payload.get("transform_belief", {})).items()
                },
                hypothesis_transform=(
                    str(context_payload.get("hypothesis_transform"))
                    if context_payload.get("hypothesis_transform") is not None
                    else None
                ),
                hypothesis_confidence=float(context_payload.get("hypothesis_confidence", 0.0)),
                dominant_transform=(
                    str(context_payload.get("dominant_transform"))
                    if context_payload.get("dominant_transform") is not None
                    else None
                ),
                transform_confidence=float(context_payload.get("transform_confidence", 0.0)),
                preserve_mode=bool(context_payload.get("preserve_mode", False)),
                preserve_pressure=float(context_payload.get("preserve_pressure", 0.0)),
                reopen_pressure=float(context_payload.get("reopen_pressure", 0.0)),
                contradiction_load=float(context_payload.get("contradiction_load", 0.0)),
                commitment_age=int(context_payload.get("commitment_age", 0)),
            ),
            plasticity=PlasticityState(
                plasticity_gate=float(plasticity_payload.get("plasticity_gate", 0.0)),
                promotion_ready=bool(plasticity_payload.get("promotion_ready", False)),
                growth_request_pressure=float(plasticity_payload.get("growth_request_pressure", 0.0)),
                failed_resolution_streak=int(plasticity_payload.get("failed_resolution_streak", 0)),
            ),
        )


@dataclass(frozen=True)
class PulseLocalUnitPreset:
    name: str
    base_threshold: float = 0.68
    accumulator_decay: float = 0.82
    cooldown_ticks: int = 1
    initial_plasticity_gate: float = 0.0

    def apply(self, state: LocalUnitState | None = None) -> LocalUnitState:
        resolved = state if state is not None else LocalUnitState()
        resolved.signal.base_threshold = float(self.base_threshold)
        resolved.signal.accumulator_decay = float(self.accumulator_decay)
        resolved.signal.cooldown_ticks = int(self.cooldown_ticks)
        resolved.plasticity.plasticity_gate = float(self.initial_plasticity_gate)
        resolved.plasticity.promotion_ready = (
            resolved.plasticity.plasticity_gate >= 0.55
            and resolved.context.commitment_margin >= 0.50
            and resolved.context.ambiguity_reservoir <= 0.35
        )
        return resolved


PULSE_LOCAL_UNIT_PRESETS: Dict[str, PulseLocalUnitPreset] = {
    DEFAULT_LOCAL_UNIT_PRESET: PulseLocalUnitPreset(name=DEFAULT_LOCAL_UNIT_PRESET),
    "c_hr_overlap_tuned_v1": PulseLocalUnitPreset(
        name="c_hr_overlap_tuned_v1",
        base_threshold=0.45,
        accumulator_decay=0.92,
        cooldown_ticks=1,
        initial_plasticity_gate=0.05,
    ),
}


def pulse_local_unit_preset_names() -> tuple[str, ...]:
    return tuple(PULSE_LOCAL_UNIT_PRESETS)


def resolve_pulse_local_unit_preset(name: str | None) -> PulseLocalUnitPreset:
    preset_name = str(name or DEFAULT_LOCAL_UNIT_PRESET)
    try:
        return PULSE_LOCAL_UNIT_PRESETS[preset_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported local_unit_preset: {preset_name}") from exc


@dataclass
class NodeRuntimeState:
    node_id: str
    position: int
    atp: float
    max_atp: float
    reward_buffer: float = 0.0
    inhibited_for: int = 0
    routed_packets: int = 0
    received_feedback: int = 0
    rest_count: int = 0
    last_feedback_amount: float = 0.0
    last_match_ratio: float = 0.0
    last_prediction_confidence: float = 0.0
    last_prediction_expected_delta: float = 0.0
    last_prediction_expected_match_ratio: float = 0.0
    last_prediction_error_magnitude: float = 0.0
    provisional_transform_credit: Dict[str, float] = field(default_factory=dict)
    provisional_context_transform_credit: Dict[str, float] = field(default_factory=dict)
    transform_credit: Dict[str, float] = field(default_factory=dict)
    context_transform_credit: Dict[str, float] = field(default_factory=dict)
    branch_transform_credit: Dict[str, float] = field(default_factory=dict)
    context_branch_transform_credit: Dict[str, float] = field(default_factory=dict)
    transform_debt: Dict[str, float] = field(default_factory=dict)
    context_transform_debt: Dict[str, float] = field(default_factory=dict)
    branch_transform_debt: Dict[str, float] = field(default_factory=dict)
    context_branch_transform_debt: Dict[str, float] = field(default_factory=dict)
    branch_context_credit: Dict[str, float] = field(default_factory=dict)
    branch_context_debt: Dict[str, float] = field(default_factory=dict)

    @property
    def dormant(self) -> bool:
        return self.atp <= 0.0
