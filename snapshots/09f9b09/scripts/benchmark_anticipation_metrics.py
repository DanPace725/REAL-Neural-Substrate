from __future__ import annotations

from statistics import mean
from typing import Iterable


def _mean_or_none(values: Iterable[float | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    if not present:
        return None
    return round(mean(present), 4)


def anticipation_metrics(
    system,
    *,
    cycle_start: int | None = None,
    cycle_end: int | None = None,
) -> dict[str, object]:
    source_id = system.environment.source_id
    route_entry_count = 0
    source_route_entry_count = 0
    predicted_route_entry_count = 0
    predicted_source_route_entry_count = 0
    first_predicted_route_cycle = None
    first_predicted_source_route_cycle = None
    prediction_confidences: list[float] = []
    source_prediction_confidences: list[float] = []
    source_expected_deltas: list[float] = []
    source_stale_family_risks: list[float] = []

    for agent in system.agents.values():
        is_source = agent.node_id == source_id
        for entry in agent.engine.memory.entries:
            cycle = int(entry.cycle)
            if cycle_start is not None and cycle < cycle_start:
                continue
            if cycle_end is not None and cycle > cycle_end:
                continue
            action = str(entry.action)
            if not action.startswith("route"):
                continue
            route_entry_count += 1
            if is_source:
                source_route_entry_count += 1
            prediction = getattr(entry, "prediction", None)
            if prediction is None:
                continue
            predicted_route_entry_count += 1
            prediction_confidences.append(float(prediction.confidence))
            if first_predicted_route_cycle is None:
                first_predicted_route_cycle = cycle
            if not is_source:
                continue
            predicted_source_route_entry_count += 1
            source_prediction_confidences.append(float(prediction.confidence))
            if prediction.expected_delta is not None:
                source_expected_deltas.append(float(prediction.expected_delta))
            source_stale_family_risks.append(
                float(prediction.metadata.get("stale_family_risk", 0.0))
            )
            if first_predicted_source_route_cycle is None:
                first_predicted_source_route_cycle = cycle

    return {
        "route_entry_count": route_entry_count,
        "source_route_entry_count": source_route_entry_count,
        "predicted_route_entry_count": predicted_route_entry_count,
        "predicted_source_route_entry_count": predicted_source_route_entry_count,
        "predicted_route_entry_rate": round(
            predicted_route_entry_count / max(1, route_entry_count),
            4,
        ),
        "predicted_source_route_entry_rate": round(
            predicted_source_route_entry_count / max(1, source_route_entry_count),
            4,
        ),
        "first_predicted_route_cycle": first_predicted_route_cycle,
        "first_predicted_source_route_cycle": first_predicted_source_route_cycle,
        "mean_prediction_confidence": _mean_or_none(prediction_confidences),
        "mean_source_prediction_confidence": _mean_or_none(
            source_prediction_confidences
        ),
        "mean_source_expected_delta": _mean_or_none(source_expected_deltas),
        "mean_source_stale_family_risk": _mean_or_none(source_stale_family_risks),
    }
