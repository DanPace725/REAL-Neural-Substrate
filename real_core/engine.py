from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Dict, Optional

from .interfaces import (
    ActionBackend,
    CoherenceModel,
    ConsolidationPipeline,
    DomainMemoryBinding,
    MemorySubstrateProtocol,
    ObservationAdapter,
)
from .consolidation import BasicConsolidationPipeline
from .memory import EpisodicMemory
from .mesh import TiltRegulatoryMesh
from .selector import CFARSelector
from .session import SessionHistory
from .session_state import SessionStateStore
from .types import (
    ActionOutcome,
    CycleEntry,
    DimensionScores,
    MemoryActionSpec,
    SessionCarryover,
)


@dataclass
class SessionSummary:
    cycles: int
    mean_coherence: float
    final_coherence: float
    gco_counts: Dict[str, int]
    session_id: int | None = None


class RealCoreEngine:
    """Domain-agnostic REAL engine for generalized Phase 4 runs."""

    def __init__(
        self,
        observer: ObservationAdapter,
        actions: ActionBackend,
        coherence: CoherenceModel,
        selector: Optional[CFARSelector] = None,
        mesh: Optional[TiltRegulatoryMesh] = None,
        memory: Optional[EpisodicMemory] = None,
        substrate: Optional[MemorySubstrateProtocol] = None,
        consolidation_pipeline: Optional[ConsolidationPipeline] = None,
        memory_binding: Optional[DomainMemoryBinding] = None,
        domain_name: str = "unknown",
        session_history: Optional[SessionHistory] = None,
        session_state_store: Optional[SessionStateStore] = None,
        session_budget: float = float("inf"),
    ) -> None:
        self.observer = observer
        self.actions = actions
        self.coherence = coherence
        self.selector = selector or CFARSelector()
        self.mesh = mesh or TiltRegulatoryMesh()
        self.memory = memory or EpisodicMemory(maxlen=500)
        self.substrate = substrate
        self.consolidation_pipeline = consolidation_pipeline
        self.memory_binding = memory_binding
        self.domain_name = domain_name
        self.session_history = session_history
        self.session_state_store = session_state_store
        self.session_budget = session_budget
        self.budget_remaining = session_budget
        self._prior_coherence: Optional[float] = None
        self._memory_action_specs: Dict[str, MemoryActionSpec] = {}

    def _effective_consolidation_pipeline(self) -> ConsolidationPipeline:
        if self.consolidation_pipeline is not None:
            return self.consolidation_pipeline
        return BasicConsolidationPipeline()

    def _current_dim_history(self) -> list[DimensionScores]:
        if self.substrate is None:
            return []
        return list(getattr(self.substrate, "dim_history", []))

    def _modulate_observation(
        self, raw_obs: Dict[str, float], cycle: int
    ) -> Dict[str, float]:
        if self.substrate is None or self.memory_binding is None:
            return raw_obs
        return self.memory_binding.modulate_observation(
            raw_obs, self.substrate, cycle
        )

    def _available_actions(self) -> list[str]:
        available = list(self.actions.available_actions(len(self.memory.entries)))
        self._memory_action_specs = {}

        if self.substrate is None or self.memory_binding is None:
            return available

        extra_actions = self.memory_binding.extra_actions(
            self.substrate, self.memory.entries
        )
        for extra in extra_actions:
            if isinstance(extra, MemoryActionSpec):
                self._memory_action_specs[extra.action] = extra
                available.append(extra.action)
            else:
                available.append(extra)
        return available

    def _estimate_action_cost(self, action: str) -> float:
        spec = self._memory_action_specs.get(action)
        if spec is not None:
            return spec.estimated_cost

        if self.substrate is not None and self.memory_binding is not None:
            estimated = self.memory_binding.estimate_memory_action_cost(
                action, self.substrate
            )
            if estimated is not None:
                return estimated

        historical = [
            entry.cost_secs for entry in self.memory.entries if entry.action == action
        ]
        if historical:
            return sum(historical) / len(historical)
        return 0.0

    def _affordable_actions(self, available: list[str]) -> list[str]:
        if not isfinite(self.session_budget):
            return available

        affordable = [
            action
            for action in available
            if self._estimate_action_cost(action) <= self.budget_remaining + 1e-9
        ]
        if affordable:
            return affordable
        if "rest" in available:
            return ["rest"]
        return available[:1]

    def _execute_action(self, action: str) -> ActionOutcome:
        if self.substrate is not None and self.memory_binding is not None:
            outcome = self.memory_binding.execute_memory_action(
                action, self.substrate
            )
            if outcome is not None:
                return outcome
        return self.actions.execute(action)

    def _apply_substrate_health(
        self,
        raw_dimensions: DimensionScores,
        state_after: Dict[str, float],
    ) -> DimensionScores:
        if self.substrate is None or self.memory_binding is None:
            return raw_dimensions

        health_signal = self.memory_binding.substrate_health_signal(
            self.substrate, state_after, self.memory.entries
        )
        if not health_signal:
            return raw_dimensions

        blended = dict(raw_dimensions)
        for key, value in health_signal.items():
            if key not in blended or not isinstance(value, (int, float)):
                continue
            blended[key] = max(
                0.0, min(1.0, 0.5 * blended[key] + 0.5 * float(value))
            )
        return blended

    def _run_consolidation(self) -> None:
        retained = self._effective_consolidation_pipeline().consolidate(
            self.memory.entries, self.substrate
        )
        self.memory.entries = list(retained)

    def export_carryover(self) -> SessionCarryover:
        return self._effective_consolidation_pipeline().export_carryover(
            self.memory.entries,
            self.substrate,
            prior_coherence=self._prior_coherence,
            dim_history=self._current_dim_history(),
        )

    def load_carryover(self, carryover: SessionCarryover) -> None:
        pipeline = self._effective_consolidation_pipeline()
        self.memory.entries = list(pipeline.import_carryover(carryover))
        self._prior_coherence = carryover.prior_coherence

        if self.substrate is not None:
            self.substrate.load_state(carryover.substrate)
            if hasattr(self.substrate, "dim_history"):
                self.substrate.dim_history = [  # type: ignore[attr-defined]
                    dict(item) for item in carryover.dim_history
                ]

    def save_session_state(self) -> SessionCarryover:
        carryover = self.export_carryover()
        if self.session_state_store is not None:
            self.session_state_store.save(carryover)
        return carryover

    def restore_session_state(
        self, carryover: SessionCarryover | None = None
    ) -> SessionCarryover | None:
        payload = carryover
        if payload is None and self.session_state_store is not None:
            payload = self.session_state_store.load()
        if payload is None:
            return None
        self.load_carryover(payload)
        return payload

    def run_cycle(self, cycle: int) -> CycleEntry:
        before_raw = self.observer.observe(cycle)
        before = self._modulate_observation(before_raw, cycle)

        available = self._available_actions()
        available = self._affordable_actions(available)
        action, mode = self.selector.select(available, self.memory.entries)
        outcome = self._execute_action(action)
        self.budget_remaining = max(
            0.0, self.budget_remaining - max(0.0, outcome.cost_secs)
        )

        after_raw = self.observer.observe(cycle)
        after = self._modulate_observation(after_raw, cycle)

        raw_dimensions = self.coherence.score(after, self.memory.entries)
        raw_dimensions = self._apply_substrate_health(raw_dimensions, after)
        dimensions = self.mesh.apply(raw_dimensions)
        coherence = self.coherence.composite(dimensions)
        delta = (
            0.0
            if self._prior_coherence is None
            else coherence - self._prior_coherence
        )
        self._prior_coherence = coherence
        gco = self.coherence.gco_status(dimensions, coherence)

        entry = CycleEntry(
            cycle=cycle,
            action=action,
            mode=mode,
            state_before=before,
            state_after=after,
            dimensions=dimensions,
            coherence=coherence,
            delta=delta,
            gco=gco,
            cost_secs=outcome.cost_secs,
        )
        self.memory.record(entry)

        if self.substrate is not None:
            self.substrate.update_dim_context(dimensions)
            self.substrate.update_fast(after)
            self.substrate.tick()

        return entry

    def run_session(
        self, cycles: int = 50, consolidate_on_action: str = "rest"
    ) -> SessionSummary:
        self.budget_remaining = self.session_budget
        counts = {"STABLE": 0, "PARTIAL": 0, "DEGRADED": 0, "CRITICAL": 0}
        coherence_sum = 0.0

        for i in range(1, cycles + 1):
            entry = self.run_cycle(i)
            counts[entry.gco.value] += 1
            coherence_sum += entry.coherence

            if (
                entry.action == consolidate_on_action
                and len(self.memory.entries) > 40
            ):
                self._run_consolidation()

        final = self.memory.entries[-1].coherence if self.memory.entries else 0.0
        mean = coherence_sum / max(1, cycles)
        summary = SessionSummary(
            cycles=cycles,
            mean_coherence=mean,
            final_coherence=final,
            gco_counts=counts,
            session_id=None,
        )

        if self.session_history is not None:
            record = self.session_history.append(
                domain=self.domain_name,
                cycles=summary.cycles,
                mean_coherence=summary.mean_coherence,
                final_coherence=summary.final_coherence,
                gco_counts=summary.gco_counts,
            )
            summary.session_id = record.session_id

        return summary
