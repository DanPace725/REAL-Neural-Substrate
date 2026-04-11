from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .types import CycleEntry


@dataclass
class EpisodicMemory:
    """Bounded episodic trace used by the current generalized REAL loop."""

    maxlen: int = 500

    def __post_init__(self) -> None:
        self.entries: List[CycleEntry] = []

    def record(self, entry: CycleEntry) -> None:
        self.entries.append(entry)
        if len(self.entries) > self.maxlen:
            self.entries = self.entries[-self.maxlen :]

    def recent(self, n: int) -> List[CycleEntry]:
        return self.entries[-n:]

    def action_mean_delta(self, action: str) -> float:
        vals = [e.delta for e in self.entries if e.action == action]
        if not vals:
            return 0.0
        return sum(vals) / len(vals)

    def action_mean_cost(self, action: str) -> float:
        vals = [e.cost_secs for e in self.entries if e.action == action]
        if not vals:
            return 0.0
        return sum(vals) / len(vals)

    def mean_cost(self) -> float:
        if not self.entries:
            return 0.0
        return sum(e.cost_secs for e in self.entries) / len(self.entries)

    def consolidate_three_tier(
        self,
        keep_attractors: int = 15,
        keep_surprises: int = 15,
        keep_boundaries: int = 10,
        threshold: float = 0.65,
    ) -> int:
        if len(self.entries) <= keep_attractors + keep_surprises + keep_boundaries:
            return 0

        attractors = sorted(
            self.entries, key=lambda e: e.coherence, reverse=True
        )[:keep_attractors]
        surprises = sorted(
            self.entries, key=lambda e: abs(e.delta), reverse=True
        )[:keep_surprises]
        boundaries = sorted(
            self.entries, key=lambda e: abs(e.coherence - threshold)
        )[:keep_boundaries]

        merged = {}
        for e in attractors + surprises + boundaries:
            merged[e.cycle] = e

        kept = sorted(merged.values(), key=lambda e: e.cycle)
        pruned = len(self.entries) - len(kept)
        self.entries = kept
        return pruned
