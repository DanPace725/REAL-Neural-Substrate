from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .types import (
    CycleEntry,
    ForecastError,
    ForecastOutput,
    GCOStatus,
    LocalPrediction,
    PredictionError,
    RecognitionMatch,
    RecognitionState,
    SessionCarryover,
    SubstrateSnapshot,
)


def _serialize_recognition(recognition: RecognitionState | None) -> dict | None:
    if recognition is None:
        return None
    return {
        "confidence": recognition.confidence,
        "novelty": recognition.novelty,
        "matches": [
            {
                "label": match.label,
                "score": match.score,
                "source": match.source,
                "valence": match.valence,
                "strength": match.strength,
                "metadata": dict(match.metadata),
            }
            for match in recognition.matches
        ],
        "metadata": dict(recognition.metadata),
    }


def _deserialize_recognition(data: dict | None) -> RecognitionState | None:
    if not data:
        return None
    return RecognitionState(
        confidence=float(data.get("confidence", 0.0)),
        novelty=float(data.get("novelty", 1.0)),
        matches=[
            RecognitionMatch(
                label=str(item.get("label", "unknown")),
                score=float(item.get("score", 0.0)),
                source=str(item.get("source", "unknown")),
                valence=float(item.get("valence", 0.0)),
                strength=float(item.get("strength", 0.0)),
                metadata=dict(item.get("metadata", {})),
            )
            for item in data.get("matches", [])
        ],
        metadata=dict(data.get("metadata", {})),
    )


def _serialize_prediction(prediction: LocalPrediction | None) -> dict | None:
    if prediction is None:
        return None
    return {
        "expected_outcome": dict(prediction.expected_outcome),
        "expected_coherence": prediction.expected_coherence,
        "expected_delta": prediction.expected_delta,
        "confidence": prediction.confidence,
        "uncertainty": prediction.uncertainty,
        "metadata": dict(prediction.metadata),
    }


def _deserialize_prediction(data: dict | None) -> LocalPrediction | None:
    if not data:
        return None
    return LocalPrediction(
        expected_outcome=dict(data.get("expected_outcome", {})),
        expected_coherence=data.get("expected_coherence"),
        expected_delta=data.get("expected_delta"),
        confidence=float(data.get("confidence", 0.0)),
        uncertainty=float(data.get("uncertainty", 1.0)),
        metadata=dict(data.get("metadata", {})),
    )


def _serialize_prediction_error(error: PredictionError | None) -> dict | None:
    if error is None:
        return None
    return {
        "outcome_error": dict(error.outcome_error),
        "coherence_error": error.coherence_error,
        "delta_error": error.delta_error,
        "magnitude": error.magnitude,
        "metadata": dict(error.metadata),
    }


def _deserialize_prediction_error(data: dict | None) -> PredictionError | None:
    if not data:
        return None
    return PredictionError(
        outcome_error={
            str(key): float(value)
            for key, value in dict(data.get("outcome_error", {})).items()
        },
        coherence_error=data.get("coherence_error"),
        delta_error=data.get("delta_error"),
        magnitude=float(data.get("magnitude", 0.0)),
        metadata=dict(data.get("metadata", {})),
    )


def _serialize_forecast(forecast: ForecastOutput | None) -> dict | None:
    if forecast is None:
        return None
    return {
        "target_label": forecast.target_label,
        "confidence": forecast.confidence,
        "candidates": dict(forecast.candidates),
        "domain": forecast.domain,
        "horizon": forecast.horizon,
        "metadata": dict(forecast.metadata),
    }


def _deserialize_forecast(data: dict | None) -> ForecastOutput | None:
    if not data:
        return None
    return ForecastOutput(
        target_label=str(data.get("target_label", "unknown")),
        confidence=float(data.get("confidence", 0.0)),
        candidates={
            str(key): float(value)
            for key, value in dict(data.get("candidates", {})).items()
        },
        domain=str(data.get("domain", "unknown")),
        horizon=int(data.get("horizon", 1)),
        metadata=dict(data.get("metadata", {})),
    )


def _serialize_forecast_error(error: ForecastError | None) -> dict | None:
    if error is None:
        return None
    return {
        "predicted_label": error.predicted_label,
        "actual_label": error.actual_label,
        "correct": error.correct,
        "resolved": error.resolved,
        "confidence_error": error.confidence_error,
        "magnitude": error.magnitude,
        "metadata": dict(error.metadata),
    }


def _deserialize_forecast_error(data: dict | None) -> ForecastError | None:
    if not data:
        return None
    return ForecastError(
        predicted_label=str(data.get("predicted_label", "unknown")),
        actual_label=(
            None
            if data.get("actual_label") is None
            else str(data.get("actual_label"))
        ),
        correct=data.get("correct"),
        resolved=bool(data.get("resolved", False)),
        confidence_error=data.get("confidence_error"),
        magnitude=float(data.get("magnitude", 0.0)),
        metadata=dict(data.get("metadata", {})),
    )


def _serialize_cycle_entry(entry: CycleEntry) -> dict:
    return {
        "cycle": entry.cycle,
        "action": entry.action,
        "mode": entry.mode,
        "state_before": entry.state_before,
        "state_after": entry.state_after,
        "dimensions": dict(entry.dimensions),
        "coherence": entry.coherence,
        "delta": entry.delta,
        "gco": entry.gco.value if hasattr(entry.gco, "value") else str(entry.gco),
        "cost_secs": entry.cost_secs,
        "recognition": _serialize_recognition(entry.recognition),
        "prediction": _serialize_prediction(entry.prediction),
        "prediction_error": _serialize_prediction_error(entry.prediction_error),
        "forecast": _serialize_forecast(entry.forecast),
        "forecast_error": _serialize_forecast_error(entry.forecast_error),
    }


def _deserialize_cycle_entry(data: dict) -> CycleEntry:
    gco = data.get("gco", GCOStatus.PARTIAL.value)
    if isinstance(gco, str):
        gco = GCOStatus(gco)
    return CycleEntry(
        cycle=int(data["cycle"]),
        action=str(data["action"]),
        mode=str(data["mode"]),
        state_before=dict(data.get("state_before", {})),
        state_after=dict(data.get("state_after", {})),
        dimensions=dict(data.get("dimensions", {})),
        coherence=float(data.get("coherence", 0.0)),
        delta=float(data.get("delta", 0.0)),
        gco=gco,
        cost_secs=float(data.get("cost_secs", 0.0)),
        recognition=_deserialize_recognition(data.get("recognition")),
        prediction=_deserialize_prediction(data.get("prediction")),
        prediction_error=_deserialize_prediction_error(
            data.get("prediction_error")
        ),
        forecast=_deserialize_forecast(data.get("forecast")),
        forecast_error=_deserialize_forecast_error(data.get("forecast_error")),
    )


def carryover_to_dict(carryover: SessionCarryover) -> dict:
    return {
        "substrate": asdict(carryover.substrate),
        "episodic_entries": [
            _serialize_cycle_entry(entry) for entry in carryover.episodic_entries
        ],
        "dim_history": [dict(item) for item in carryover.dim_history],
        "prior_coherence": carryover.prior_coherence,
        "metadata": dict(carryover.metadata),
    }


def carryover_from_dict(data: dict) -> SessionCarryover:
    substrate_data = data.get("substrate", {})
    substrate = SubstrateSnapshot(
        fast=dict(substrate_data.get("fast", {})),
        slow=dict(substrate_data.get("slow", {})),
        slow_age=dict(substrate_data.get("slow_age", {})),
        slow_velocity=dict(substrate_data.get("slow_velocity", {})),
        metadata=dict(substrate_data.get("metadata", {})),
    )
    return SessionCarryover(
        substrate=substrate,
        episodic_entries=[
            _deserialize_cycle_entry(entry)
            for entry in data.get("episodic_entries", [])
        ],
        dim_history=[dict(item) for item in data.get("dim_history", [])],
        prior_coherence=data.get("prior_coherence"),
        metadata=dict(data.get("metadata", {})),
    )


class SessionStateStore:
    """Persistent storage for cross-session warm-start state."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, carryover: SessionCarryover) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(carryover_to_dict(carryover), indent=2),
            encoding="utf-8",
        )

    def load(self) -> SessionCarryover | None:
        if not self.path.exists():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return carryover_from_dict(payload)
