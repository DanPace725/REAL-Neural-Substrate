from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class SessionRecord:
    session_id: int
    timestamp: float
    domain: str
    cycles: int
    mean_coherence: float
    final_coherence: float
    gco_counts: Dict[str, int]


class SessionHistory:
    """Persistent cross-session summary log for any Phase 4 domain."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.records: List[SessionRecord] = []
        self._load()

    @property
    def count(self) -> int:
        return len(self.records)

    @property
    def latest(self) -> SessionRecord | None:
        return self.records[-1] if self.records else None

    def append(
        self,
        domain: str,
        cycles: int,
        mean_coherence: float,
        final_coherence: float,
        gco_counts: Dict[str, int],
    ) -> SessionRecord:
        record = SessionRecord(
            session_id=self.count + 1,
            timestamp=time.time(),
            domain=domain,
            cycles=cycles,
            mean_coherence=mean_coherence,
            final_coherence=final_coherence,
            gco_counts=dict(gco_counts),
        )
        self.records.append(record)
        self._save()
        return record

    def developmental_summary(self) -> Dict[str, object]:
        return {
            "sessions": self.count,
            "domains": sorted({r.domain for r in self.records}),
            "mean_coherence_trend": [r.mean_coherence for r in self.records],
            "final_coherence_trend": [r.final_coherence for r in self.records],
        }

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for item in data:
                self.records.append(SessionRecord(**item))
        except (json.JSONDecodeError, TypeError):
            self.records = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(r) for r in self.records]
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
