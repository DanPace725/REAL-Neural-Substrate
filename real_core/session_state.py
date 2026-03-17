from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .types import CycleEntry, GCOStatus, SessionCarryover, SubstrateSnapshot


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
