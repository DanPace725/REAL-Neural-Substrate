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
class LocalPrediction:
    """Locally generated expectation for a candidate action."""

    expected_outcome: Dict[str, Any] = field(default_factory=dict)
    expected_coherence: float | None = None
    expected_delta: float | None = None
    confidence: float = 0.0
    uncertainty: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PredictionError:
    """Difference between an anticipated and observed local outcome."""

    outcome_error: Dict[str, float] = field(default_factory=dict)
    coherence_error: float | None = None
    delta_error: float | None = None
    magnitude: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecognitionMatch:
    """Recognized resemblance to a prior local problem shape or pattern."""

    label: str
    score: float
    source: str = "unknown"
    valence: float = 0.0
    strength: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecognitionState:
    """Current-cycle recognition summary separate from forward prediction."""

    confidence: float = 0.0
    novelty: float = 1.0
    matches: List[RecognitionMatch] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SelectionContext:
    """Current-cycle anticipatory context exposed to opt-in selectors."""

    cycle: int
    state_before: Dict[str, Any] = field(default_factory=dict)
    recognition: RecognitionState | None = None
    predictions: Dict[str, LocalPrediction] = field(default_factory=dict)
    prior_coherence: float | None = None
    budget_remaining: float | None = None
    action_costs: Dict[str, float] = field(default_factory=dict)


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
    recognition: RecognitionState | None = None
    prediction: LocalPrediction | None = None
    prediction_error: PredictionError | None = None


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
