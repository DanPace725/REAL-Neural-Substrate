from __future__ import annotations

import random
from pathlib import Path

from real_core.engine import RealCoreEngine
from real_core.session_state import SessionStateStore

from .adapters import (
    LocalNodeActionBackend,
    LocalNodeCoherenceModel,
    LocalNodeMemoryBinding,
    LocalNodeObservationAdapter,
)
from .consolidation import Phase8ConsolidationPipeline
from .environment import RoutingEnvironment
from .selector import Phase8Selector
from .substrate import ConnectionSubstrate


class NodeAgent:
    """Phase 8 node wrapper around the generalized REAL core."""

    def __init__(
        self,
        node_id: str,
        neighbor_ids: tuple[str, ...],
        environment: RoutingEnvironment,
        *,
        selector_seed: int | None = None,
        carryover_path: str | Path | None = None,
        probationary: bool = False,
    ) -> None:
        self.node_id = node_id
        self.neighbor_ids = tuple(neighbor_ids)
        self.environment = environment
        self.probationary = probationary
        self.substrate = ConnectionSubstrate(self.neighbor_ids)

        rng = random.Random(selector_seed)
        selector = Phase8Selector(
            environment=environment,
            node_id=node_id,
            substrate=self.substrate,
            rng=rng,
        )

        observer = LocalNodeObservationAdapter(environment, node_id)
        actions = LocalNodeActionBackend(
            environment,
            node_id,
            self.neighbor_ids,
            self.substrate,
        )
        coherence = LocalNodeCoherenceModel()
        pipeline = Phase8ConsolidationPipeline()
        binding = LocalNodeMemoryBinding(
            environment=environment,
            node_id=node_id,
            neighbor_ids=self.neighbor_ids,
            substrate=self.substrate,
            rng=rng,
        )
        state_store = (
            SessionStateStore(Path(carryover_path))
            if carryover_path is not None
            else None
        )

        self.engine = RealCoreEngine(
            observer=observer,
            actions=actions,
            coherence=coherence,
            selector=selector,
            substrate=self.substrate,
            consolidation_pipeline=pipeline,
            memory_binding=binding,
            domain_name=f"phase8.node.{node_id}",
            session_state_store=state_store,
            session_budget=float("inf"),
        )
        self.cycle = 0

    def refresh_neighbors(self, neighbor_ids: tuple[str, ...]) -> None:
        neighbor_ids = tuple(neighbor_ids)
        if neighbor_ids == self.neighbor_ids:
            return
        refreshed = ConnectionSubstrate(neighbor_ids)
        refreshed.copy_overlap_from(self.substrate)
        self.neighbor_ids = neighbor_ids
        self.substrate = refreshed
        self.engine.substrate = refreshed
        self.engine.selector.substrate = refreshed
        self.engine.actions.neighbor_ids = neighbor_ids
        self.engine.actions.substrate = refreshed
        self.engine.memory_binding.neighbor_ids = neighbor_ids
        self.engine.memory_binding.substrate = refreshed

    @property
    def atp(self) -> float:
        return self.environment.state_for(self.node_id).atp

    def step(self):
        self.cycle += 1
        entry = self.engine.run_cycle(self.cycle)
        if entry.action == "rest" and len(self.engine.memory.entries) >= 8:
            self.engine._run_consolidation()
        return entry

    def absorb_feedback(self, feedback_events: list[dict[str, object]]) -> None:
        for event in feedback_events:
            edge = str(event.get("edge", ""))
            if "->" not in edge:
                continue
            source_id, neighbor_id = edge.split("->", 1)
            if source_id != self.node_id:
                continue
            transform_name = str(event.get("transform", "identity"))
            context_bit = event.get("context_bit")
            if context_bit is not None:
                context_bit = int(context_bit)
            promotion_ready = bool(event.get("context_promotion_ready", context_bit is not None))
            amount = float(event.get("amount", 0.0))
            bit_match_ratio = float(event.get("bit_match_ratio", 0.0))
            feedback_scale = amount / max(self.environment.feedback_amount, 1e-9)
            if promotion_ready:
                self.substrate.record_context_feedback(
                    neighbor_id,
                    transform_name,
                    context_bit,
                    credit_signal=feedback_scale,
                    bit_match_ratio=bit_match_ratio,
                )

    def save_carryover(self, path: str | Path) -> None:
        state_store = SessionStateStore(Path(path))
        state_store.save(self.engine.export_carryover())

    def load_carryover(self, path: str | Path) -> bool:
        state_store = SessionStateStore(Path(path))
        payload = state_store.load()
        if payload is None:
            return False
        self.engine.load_carryover(payload)
        self.cycle = max((entry.cycle for entry in self.engine.memory.entries), default=0)
        return True

    def save_substrate_carryover(self, path: str | Path) -> None:
        carryover = self.engine.export_carryover()
        carryover.episodic_entries = []
        state_store = SessionStateStore(Path(path))
        state_store.save(carryover)

    def load_substrate_carryover(self, path: str | Path) -> bool:
        state_store = SessionStateStore(Path(path))
        payload = state_store.load()
        if payload is None:
            return False
        payload.episodic_entries = []
        self.engine.load_carryover(payload)
        self.engine.memory.entries = []
        self.cycle = 0
        return True
