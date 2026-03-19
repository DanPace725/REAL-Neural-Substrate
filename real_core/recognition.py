from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence

from .patterns import ConstraintPattern
from .types import CycleEntry, RecognitionMatch, RecognitionState


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass
class PatternRecognitionModel:
    """Reusable pattern-based recognizer for generalized REAL runs."""

    min_match_score: float = 0.45
    max_matches: int = 3

    def recognize(
        self,
        state_before: Dict[str, float],
        history: List[CycleEntry],
        *,
        prior_coherence: float | None = None,
        substrate=None,
    ) -> RecognitionState | None:
        patterns = self._patterns(substrate)
        if not patterns:
            return None

        pattern_keys = self._pattern_keys(patterns)
        candidates = self._candidate_states(
            state_before,
            history,
            substrate,
            pattern_keys,
        )
        if not candidates:
            return None

        best_source = ""
        best_trend_source = ""
        best_score = -1.0
        best_scored: list[tuple[int, ConstraintPattern, float]] = []
        for dims_source, current_dims, trend_source, current_trends in candidates:
            scored: list[tuple[int, ConstraintPattern, float]] = []
            for index, pattern in enumerate(patterns):
                scored.append(
                    (
                        index,
                        pattern,
                        pattern.match_score(current_dims, current_trends),
                    )
                )
            scored.sort(key=lambda item: item[2], reverse=True)
            top_score = scored[0][2] if scored else 0.0
            if top_score > best_score:
                best_score = top_score
                best_source = dims_source
                best_trend_source = trend_source
                best_scored = scored

        if not best_scored:
            return None

        matches = [
            RecognitionMatch(
                label=self._pattern_label(pattern, index),
                score=score,
                source=pattern.source,
                valence=pattern.valence,
                strength=pattern.strength,
                metadata={
                    "pattern_index": index,
                    "coherence_level": pattern.coherence_level,
                    "match_count": pattern.match_count,
                },
            )
            for index, pattern, score in best_scored[: self.max_matches]
            if score >= self.min_match_score
        ]

        return RecognitionState(
            confidence=best_score,
            novelty=max(0.0, 1.0 - best_score),
            matches=matches,
            metadata={
                "pattern_count": len(patterns),
                "dims_source": best_source,
                "trend_source": best_trend_source,
                "matched": bool(matches),
                "prior_coherence": prior_coherence,
            },
        )

    def _patterns(self, substrate) -> list[ConstraintPattern]:
        if substrate is None:
            return []
        return list(getattr(substrate, "constraint_patterns", []))

    def _pattern_keys(
        self, patterns: Sequence[ConstraintPattern]
    ) -> list[str]:
        keys: list[str] = []
        for pattern in patterns:
            for key in pattern.dim_scores:
                if key not in keys:
                    keys.append(key)
        return keys

    def _candidate_states(
        self,
        state_before: Dict[str, float],
        history: List[CycleEntry],
        substrate,
        pattern_keys: Sequence[str],
    ) -> list[tuple[str, Dict[str, float], str, Dict[str, float]]]:
        candidates: list[tuple[str, Dict[str, float], str, Dict[str, float]]] = []
        observed = {
            key: float(state_before[key])
            for key in pattern_keys
            if key in state_before and _is_number(state_before[key])
        }
        if observed:
            trend_values, trend_source = self._current_trends(
                history,
                substrate,
                observed.keys(),
            )
            candidates.append(("state_before", observed, trend_source, trend_values))
            relative = self._relative_candidate(observed)
            if relative is not None:
                candidates.append(
                    (
                        "state_before_relative",
                        relative,
                        trend_source,
                        trend_values,
                    )
                )

        dim_history = list(getattr(substrate, "dim_history", [])) if substrate is not None else []
        if dim_history:
            current_dims = dict(dim_history[-1])
            trend_values, trend_source = self._current_trends(
                history,
                substrate,
                current_dims.keys(),
            )
            candidates.append(
                ("substrate.dim_history", current_dims, trend_source, trend_values)
            )

        if history:
            current_dims = dict(history[-1].dimensions)
            trend_values, trend_source = self._current_trends(
                history,
                substrate,
                current_dims.keys(),
            )
            candidates.append(("history", current_dims, trend_source, trend_values))

        return candidates

    def _relative_candidate(
        self,
        dims: Dict[str, float],
    ) -> Dict[str, float] | None:
        if len(dims) < 2:
            return None
        values = list(dims.values())
        low = min(values)
        high = max(values)
        if high - low <= 1e-9:
            return None
        scale = high - low
        # Route-style attractor patterns are often about relative branch shape
        # before absolute support has fully consolidated.
        return {
            key: 0.25 + 0.60 * ((value - low) / scale)
            for key, value in dims.items()
        }

    def _current_trends(
        self,
        history: List[CycleEntry],
        substrate,
        keys: Iterable[str],
    ) -> tuple[Dict[str, float], str]:
        dim_history = list(getattr(substrate, "dim_history", [])) if substrate is not None else []
        if len(dim_history) >= 2:
            previous = dim_history[-2]
            current = dim_history[-1]
            return (
                {
                    key: float(current.get(key, 0.0) - previous.get(key, 0.0))
                    for key in keys
                },
                "substrate.dim_history",
            )

        if len(history) >= 2:
            previous = history[-2].dimensions
            current = history[-1].dimensions
            return (
                {
                    key: float(current.get(key, 0.0) - previous.get(key, 0.0))
                    for key in keys
                },
                "history",
            )

        return ({key: 0.0 for key in keys}, "none")

    def _pattern_label(self, pattern: ConstraintPattern, index: int) -> str:
        source = pattern.source.strip() or "pattern"
        return f"{source}:{index}"
