from __future__ import annotations

from typing import Any, Dict, List, Protocol, Tuple

from .types import (
    ActionOutcome,
    CycleEntry,
    DimensionScores,
    GCOStatus,
    MemoryActionSpec,
    SessionCarryover,
    SubstrateSnapshot,
)


class ObservationAdapter(Protocol):
    def observe(self, cycle: int) -> Dict[str, float]:
        """Return an observation snapshot for the current cycle."""


class ActionBackend(Protocol):
    def available_actions(self, history_size: int) -> List[str]:
        """Return currently available action names."""

    def execute(self, action: str) -> ActionOutcome:
        """Execute an action and return outcome + measured cost."""


class CoherenceModel(Protocol):
    dimension_names: Tuple[str, ...]

    def score(self, state_after: Dict[str, float], history: List[CycleEntry]) -> DimensionScores:
        """Return six-dimensional coherence scores in [0, 1]."""

    def composite(self, dimensions: DimensionScores) -> float:
        """Return composite coherence score in [0, 1]."""

    def gco_status(self, dimensions: DimensionScores, coherence: float) -> GCOStatus:
        """Return global closure status."""


class Selector(Protocol):
    def select(self, available: List[str], history: List[CycleEntry]) -> Tuple[str, str]:
        """Return (action_name, mode_name)."""


class Consolidator(Protocol):
    def consolidate(self, entries: List[CycleEntry]) -> List[CycleEntry]:
        """Return retained entries after consolidation."""


class RegulatoryMesh(Protocol):
    def apply(self, dimensions: DimensionScores) -> DimensionScores:
        """Apply bounded inter-dimensional coupling."""


class MemorySubstrateProtocol(Protocol):
    """Generalized memory substrate with slow-layer persistence."""

    def update_fast(self, observation: Dict[str, float]) -> None:
        """Update fast-layer state from the current observation."""

    def update_dim_context(self, dim_scores: DimensionScores) -> None:
        """Update dimension context used for pattern matching or promotion."""

    def tick(self) -> None:
        """Advance substrate dynamics by one cycle."""

    def snapshot(self) -> SubstrateSnapshot:
        """Return a serializable substrate snapshot."""

    def save_state(self) -> SubstrateSnapshot:
        """Export substrate state for cross-session carryover."""

    def load_state(self, snapshot: SubstrateSnapshot) -> None:
        """Restore substrate state from a prior session."""


class ConsolidationPipeline(Protocol):
    """Promotion pipeline bridging episodic traces and durable constraint."""

    def consolidate(
        self,
        entries: List[CycleEntry],
        substrate: MemorySubstrateProtocol | None = None,
    ) -> List[CycleEntry]:
        """Retain or transform entries during within-session consolidation."""

    def export_carryover(
        self,
        entries: List[CycleEntry],
        substrate: MemorySubstrateProtocol | None = None,
        *,
        prior_coherence: float | None = None,
        dim_history: List[DimensionScores] | None = None,
    ) -> SessionCarryover:
        """Build a cross-session warm-start package."""

    def import_carryover(self, carryover: SessionCarryover) -> List[CycleEntry]:
        """Restore episodic state from a prior carryover package."""


class DomainMemoryBinding(Protocol):
    """Domain-specific bridge between generalized memory and local effects."""

    def modulate_observation(
        self,
        raw_obs: Dict[str, float],
        substrate: MemorySubstrateProtocol,
        cycle: int,
    ) -> Dict[str, float]:
        """Return observation after substrate-dependent modulation."""

    def extra_actions(
        self,
        substrate: MemorySubstrateProtocol,
        history: List[CycleEntry],
    ) -> List[str] | List[MemoryActionSpec]:
        """Return additional memory-side actions exposed to the engine."""

    def estimate_memory_action_cost(
        self,
        action: str,
        substrate: MemorySubstrateProtocol,
    ) -> float | None:
        """Estimate the metabolic cost of a memory action, if applicable."""

    def execute_memory_action(
        self,
        action: str,
        substrate: MemorySubstrateProtocol,
    ) -> ActionOutcome | None:
        """Execute a memory-side action, returning None if not handled."""

    def substrate_health_signal(
        self,
        substrate: MemorySubstrateProtocol,
        state_after: Dict[str, float],
        history: List[CycleEntry],
    ) -> Dict[str, Any]:
        """Return optional domain-specific health signals derived from substrate state."""
