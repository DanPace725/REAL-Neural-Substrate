from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from real_core.types import (
    CycleEntry,
    ForecastError,
    ForecastOutput,
    LocalPrediction,
    RecognitionState,
)

from .environment import TRANSFORM_NAMES


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass
class Phase8ForecastReadout:
    """Compact symbolic transform forecaster for laminated Phase 8 slices."""

    environment: object
    node_id: str

    def forecast(
        self,
        state_before: Dict[str, float],
        available: List[str],
        history: List[CycleEntry],
        *,
        recognition: RecognitionState | None = None,
        predictions: Dict[str, LocalPrediction] | None = None,
        prior_coherence: float | None = None,
        substrate=None,
    ) -> ForecastOutput | None:
        if state_before.get("has_packet", 0.0) < 0.5:
            return None
        if state_before.get("head_has_task", 0.0) < 0.5:
            return None

        prediction_by_transform = self._prediction_by_transform(predictions or {})
        candidate_scores: dict[str, float] = {}
        for transform_name in TRANSFORM_NAMES:
            history_evidence = float(
                state_before.get(f"history_transform_evidence_{transform_name}", 0.0)
            )
            task_affinity = float(
                state_before.get(f"task_transform_affinity_{transform_name}", 0.0)
            )
            sequence_hint = float(
                state_before.get(f"source_sequence_transform_hint_{transform_name}", 0.0)
            )
            prediction_score = prediction_by_transform.get(transform_name, 0.0)
            recognition_bonus = 0.0
            if recognition is not None and recognition.confidence > 0.0:
                recognition_bonus = 0.05 * recognition.confidence
            candidate_scores[transform_name] = (
                0.28 * max(0.0, task_affinity)
                + 0.32 * max(0.0, sequence_hint)
                + 0.22 * history_evidence
                + 0.20 * prediction_score
                + recognition_bonus
                - 0.10 * max(0.0, -task_affinity)
                - 0.12 * max(0.0, -sequence_hint)
            )

        target_label = max(candidate_scores, key=candidate_scores.get)
        sorted_scores = sorted(candidate_scores.values(), reverse=True)
        margin = (
            0.0
            if len(sorted_scores) < 2
            else max(0.0, float(sorted_scores[0]) - float(sorted_scores[1]))
        )
        confidence = _clamp(
            0.30
            + 0.40 * _clamp(candidate_scores[target_label])
            + 0.30 * _clamp(margin / 0.35)
        )
        normalized = self._normalize_candidates(candidate_scores)
        return ForecastOutput(
            target_label=target_label,
            confidence=confidence,
            candidates=normalized,
            domain="phase8_transform_forecast",
            horizon=1,
            metadata={
                "source": "phase8_forecast",
                "node_id": self.node_id,
                "candidate_margin": round(margin, 6),
            },
        )

    def compare(
        self,
        forecast: ForecastOutput | None,
        state_after: Dict[str, float],
        dimensions: Dict[str, float],
        coherence: float,
        delta: float,
        history: List[CycleEntry],
    ) -> ForecastError | None:
        if forecast is None:
            return None
        actual_label = self._actual_transform_label(state_after)
        if actual_label is None:
            return ForecastError(
                predicted_label=forecast.target_label,
                actual_label=None,
                correct=None,
                resolved=False,
                confidence_error=None,
                magnitude=0.0,
                metadata={
                    "source": "phase8_forecast",
                    "resolved": False,
                    "reason": "expected_transform_unavailable",
                },
            )
        correct = forecast.target_label == actual_label
        confidence_error = float(forecast.confidence) - (1.0 if correct else 0.0)
        return ForecastError(
            predicted_label=forecast.target_label,
            actual_label=actual_label,
            correct=correct,
            resolved=True,
            confidence_error=confidence_error,
            magnitude=abs(confidence_error),
            metadata={
                "source": "phase8_forecast",
                "resolved": True,
                "domain": forecast.domain,
            },
        )

    def _prediction_by_transform(
        self,
        predictions: Dict[str, LocalPrediction],
    ) -> Dict[str, float]:
        best_by_transform: Dict[str, float] = {name: 0.0 for name in TRANSFORM_NAMES}
        for action, prediction in predictions.items():
            if not action.startswith("route_transform:"):
                continue
            parts = action.split(":")
            if len(parts) != 3:
                continue
            transform_name = parts[2]
            score = _clamp(
                float(prediction.confidence) * (1.0 - float(prediction.uncertainty))
            )
            best_by_transform[transform_name] = max(
                best_by_transform.get(transform_name, 0.0),
                score,
            )
        return best_by_transform

    def _normalize_candidates(
        self,
        candidate_scores: Dict[str, float],
    ) -> Dict[str, float]:
        shifted = {
            name: max(0.0, float(score) + 0.20)
            for name, score in candidate_scores.items()
        }
        total = sum(shifted.values())
        if total <= 1e-9:
            return {name: 0.0 for name in candidate_scores}
        return {
            name: round(value / total, 6)
            for name, value in shifted.items()
        }

    def _actual_transform_label(self, state_after: Dict[str, float]) -> str | None:
        if state_after.get("expected_transform_available", 0.0) < 0.5:
            return None
        scores = {
            name: float(state_after.get(f"expected_transform_{name}", 0.0))
            for name in TRANSFORM_NAMES
        }
        if not any(score > 0.0 for score in scores.values()):
            return None
        return max(scores, key=scores.get)
