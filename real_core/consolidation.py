from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .types import CycleEntry, DimensionScores, SessionCarryover, SubstrateSnapshot


@dataclass
class BasicConsolidationPipeline:
    """Default consolidation path for the generalized core.

    The first Phase 4.5 version stays intentionally conservative:
    it preserves the existing three-tier episodic retention while also
    providing a standard carryover package for warm starts.
    """

    keep_attractors: int = 15
    keep_surprises: int = 15
    keep_boundaries: int = 10
    threshold: float = 0.65

    def consolidate(
        self,
        entries: List[CycleEntry],
        substrate=None,
    ) -> List[CycleEntry]:
        if len(entries) <= (
            self.keep_attractors + self.keep_surprises + self.keep_boundaries
        ):
            return list(entries)

        attractors = sorted(
            entries, key=lambda e: e.coherence, reverse=True
        )[: self.keep_attractors]
        surprises = sorted(
            entries, key=lambda e: abs(e.delta), reverse=True
        )[: self.keep_surprises]
        boundaries = sorted(
            entries, key=lambda e: abs(e.coherence - self.threshold)
        )[: self.keep_boundaries]

        merged = {}
        for entry in attractors + surprises + boundaries:
            merged[entry.cycle] = entry
        return sorted(merged.values(), key=lambda e: e.cycle)

    def export_carryover(
        self,
        entries: List[CycleEntry],
        substrate=None,
        *,
        prior_coherence: float | None = None,
        dim_history: List[DimensionScores] | None = None,
    ) -> SessionCarryover:
        retained = self.consolidate(entries, substrate)
        substrate_state = (
            substrate.save_state() if substrate is not None else SubstrateSnapshot()
        )
        return SessionCarryover(
            substrate=substrate_state,
            episodic_entries=list(retained),
            dim_history=list(dim_history or []),
            prior_coherence=prior_coherence,
            metadata={
                "retained_entries": len(retained),
                "source": "basic_consolidation_pipeline",
            },
        )

    def import_carryover(self, carryover: SessionCarryover) -> List[CycleEntry]:
        return list(carryover.episodic_entries)
