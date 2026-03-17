from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List


DEFAULT_SIGNAL_WIDTH = 4


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
    transform_trace: List[str] = field(default_factory=list)
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
        self.transform_trace = [str(item) for item in self.transform_trace]
        if self.context_bit is not None:
            self.context_bit = 1 if int(self.context_bit) else 0


@dataclass(frozen=True)
class SignalSpec:
    input_bits: List[int]
    payload_bits: List[int] | None = None
    context_bit: int | None = None
    task_id: str | None = None
    target_bits: List[int] | None = None


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
