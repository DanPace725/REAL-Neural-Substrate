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


class SettlementDecision(str, Enum):
    CONTINUE = "continue"
    SETTLE = "settle"
    BRANCH = "branch"
    ESCALATE = "escalate"


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


@dataclass
class ModeExperience:
    """One observed (mode → accuracy delta) experience for the learning regulator.

    Stored after each slice to build a history the regulator can use to predict
    which capability mode is likely to produce the best improvement given the
    current substrate state.
    """

    mode: str
    features: Dict[str, float]        # substrate state features at time of prediction
    predicted_delta: float | None      # what the regulator expected before the slice ran
    observed_delta: float              # actual min-context-accuracy improvement
    prediction_error: float | None     # abs(predicted - observed); None on first slice


def _ensure_summary_safe(value: Any, *, path: str) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, Enum):
        return
    if isinstance(
        value,
        (
            ActionOutcome,
            CycleEntry,
            LocalPrediction,
            PredictionError,
            RecognitionMatch,
            RecognitionState,
            SelectionContext,
            SubstrateSnapshot,
            MemoryActionSpec,
            SessionCarryover,
        ),
    ):
        raise TypeError(f"{path} must stay summary-safe, got {type(value).__name__}")
    if isinstance(value, dict):
        for key, item in value.items():
            _ensure_summary_safe(key, path=f"{path}.key")
            _ensure_summary_safe(item, path=f"{path}[{key!r}]")
        return
    if isinstance(value, (list, tuple, set)):
        for index, item in enumerate(value):
            _ensure_summary_safe(item, path=f"{path}[{index}]")
        return
    raise TypeError(f"{path} must stay summary-safe, got unsupported type {type(value).__name__}")


@dataclass
class SliceSummary:
    """Compact summary emitted by one bounded fast-layer slice."""

    slice_id: int
    slice_budget: int
    cycles_used: int
    examples_seen: int
    benchmark_family: str = "unknown"
    task_key: str = "unknown"
    mean_coherence: float = 0.0
    final_coherence: float = 0.0
    coherence_delta: float = 0.0
    mean_uncertainty: float = 1.0
    ambiguity_level: float = 0.0
    conflict_level: float = 0.0
    guidance_alignment: float | None = None
    candidate_carryover_labels: List[str] = field(default_factory=list)
    candidate_carryover_count: int = 0
    cost_summary: Dict[str, float] = field(default_factory=dict)
    settlement_hint: str = "continue"
    context_accuracy: Dict[str, float] = field(default_factory=dict)
    mode_used: str = "visible"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.candidate_carryover_labels = [str(label) for label in self.candidate_carryover_labels]
        if self.candidate_carryover_count <= 0:
            self.candidate_carryover_count = len(self.candidate_carryover_labels)
        _ensure_summary_safe(self.candidate_carryover_labels, path="candidate_carryover_labels")
        _ensure_summary_safe(self.cost_summary, path="cost_summary")
        _ensure_summary_safe(self.context_accuracy, path="context_accuracy")
        _ensure_summary_safe(self.metadata, path="metadata")


@dataclass
class RegulatorySignal:
    """Low-bandwidth slow-layer control for the next slice."""

    next_slice_budget: int | None = None
    carryover_filter_mode: str = "keep"
    context_pressure: str = "medium"
    decision_hint: SettlementDecision = SettlementDecision.CONTINUE
    capability_mode: str | None = None
    bias_updates: Dict[str, float] = field(default_factory=dict)
    gating_updates: Dict[str, float] = field(default_factory=dict)
    reset_flags: Dict[str, float] = field(default_factory=dict)
    reframe_flags: Dict[str, float] = field(default_factory=dict)
    stop_reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_summary_safe(self.bias_updates, path="bias_updates")
        _ensure_summary_safe(self.gating_updates, path="gating_updates")
        _ensure_summary_safe(self.reset_flags, path="reset_flags")
        _ensure_summary_safe(self.reframe_flags, path="reframe_flags")
        _ensure_summary_safe(self.metadata, path="metadata")
