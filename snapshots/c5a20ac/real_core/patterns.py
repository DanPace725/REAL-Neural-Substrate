from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable

from .types import DimensionScores


def _safe_mean(values: Iterable[float], default: float = 0.0) -> float:
    vals = list(values)
    if not vals:
        return default
    return sum(vals) / len(vals)


@dataclass
class ConstraintPattern:
    """Portable pattern primitive for consolidated memory signatures."""

    dim_scores: DimensionScores = field(default_factory=dict)
    dim_trends: DimensionScores = field(default_factory=dict)
    valence: float = 0.0
    strength: float = 0.0
    coherence_level: float = 0.0
    match_count: int = 0
    source: str = "unknown"

    def match_score(
        self,
        current_dims: Dict[str, float],
        current_trends: Dict[str, float] | None = None,
    ) -> float:
        """Return a bounded similarity score for the current signature."""
        if not self.dim_scores:
            return 0.0

        trends = current_trends or {}
        dims = sorted(set(self.dim_scores) | set(current_dims))

        score_diffs = [
            abs(current_dims.get(dim, 0.5) - self.dim_scores.get(dim, 0.5))
            for dim in dims
        ]
        trend_diffs = [
            abs(trends.get(dim, 0.0) - self.dim_trends.get(dim, 0.0))
            for dim in dims
        ]

        score_sim = max(0.0, 1.0 - _safe_mean(score_diffs) * 5.0)
        trend_sim = max(0.0, 1.0 - _safe_mean(trend_diffs) * 15.0)
        return 0.65 * score_sim + 0.35 * trend_sim

    def to_dict(self) -> dict:
        return {
            "dim_scores": dict(self.dim_scores),
            "dim_trends": dict(self.dim_trends),
            "valence": self.valence,
            "strength": self.strength,
            "coherence_level": self.coherence_level,
            "match_count": self.match_count,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConstraintPattern":
        return cls(**data)
