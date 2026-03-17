from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

DimensionScores = Dict[str, float]


class GCOStatus(str, Enum):
    STABLE = "STABLE"
    PARTIAL = "PARTIAL"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"


@dataclass
class ActionOutcome:
    success: bool
    result: Dict[str, Any] = field(default_factory=dict)
    cost_secs: float = 0.0


@dataclass
class CycleEntry:
    cycle: int
    action: str
    mode: str
    state_before: Dict[str, Any]
    state_after: Dict[str, Any]
    dimensions: DimensionScores
    coherence: float
    delta: float
    gco: GCOStatus
    cost_secs: float


@dataclass
class SubstrateSnapshot:
    """Serializable view of the generalized slow-memory substrate."""

    fast: Dict[str, float] = field(default_factory=dict)
    slow: Dict[str, float] = field(default_factory=dict)
    slow_age: Dict[str, int] = field(default_factory=dict)
    slow_velocity: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryActionSpec:
    """Typed description of a memory-side action exposed to the engine."""

    action: str
    estimated_cost: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionCarryover:
    """Cross-session state used to warm-start learning between runs."""

    substrate: SubstrateSnapshot = field(default_factory=SubstrateSnapshot)
    episodic_entries: List[CycleEntry] = field(default_factory=list)
    dim_history: List[DimensionScores] = field(default_factory=list)
    prior_coherence: float | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)
