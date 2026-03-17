from __future__ import annotations

import shutil
import unittest
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from real_core import (
    ActionOutcome,
    BasicConsolidationPipeline,
    CFARSelector,
    CycleEntry,
    GCOStatus,
    MemorySubstrate,
    RealCoreEngine,
    SessionStateStore,
    SubstrateConfig,
)

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class DummyObserver:
    values: list[dict[str, float]] = field(
        default_factory=lambda: [
            {"signal": 0.2, "energy": 0.8},
            {"signal": 0.6, "energy": 0.7},
            {"signal": 0.9, "energy": 0.9},
        ]
    )

    def observe(self, cycle: int) -> dict[str, float]:
        return dict(self.values[(cycle - 1) % len(self.values)])


@dataclass
class DummyActions:
    def available_actions(self, history_size: int) -> list[str]:
        return ["rest", "nudge"]

    def execute(self, action: str) -> ActionOutcome:
        if action == "nudge":
            return ActionOutcome(success=True, result={"action": action}, cost_secs=0.15)
        return ActionOutcome(success=True, result={"action": action}, cost_secs=0.0)


@dataclass
class DummyCoherence:
    def score(self, state_after: dict[str, float], history: list[object]) -> dict[str, float]:
        signal = state_after.get("signal", 0.0)
        energy = state_after.get("energy", 0.0)
        history_ratio = min(len(history) / 5.0, 1.0)
        return {
            "continuity": signal,
            "vitality": energy,
            "contextual_fit": 0.5 + 0.5 * signal,
            "differentiation": 0.4 + 0.3 * history_ratio,
            "accountability": 0.45 + 0.25 * history_ratio,
            "reflexivity": 0.35 + 0.25 * history_ratio,
        }

    def composite(self, dimensions: dict[str, float]) -> float:
        return sum(dimensions.values()) / len(dimensions)

    def gco_status(self, dimensions: dict[str, float], coherence: float) -> GCOStatus:
        if coherence >= 0.75:
            return GCOStatus.STABLE
        if coherence >= 0.55:
            return GCOStatus.PARTIAL
        return GCOStatus.DEGRADED


class TestRealCoreEngine(unittest.TestCase):
    def test_engine_runs_cycles_and_records_memory(self) -> None:
        engine = RealCoreEngine(
            observer=DummyObserver(),
            actions=DummyActions(),
            coherence=DummyCoherence(),
            selector=CFARSelector(exploration_rate=0.0),
            domain_name="test.domain",
        )

        summary = engine.run_session(cycles=4)

        self.assertEqual(summary.cycles, 4)
        self.assertEqual(len(engine.memory.entries), 4)
        self.assertGreaterEqual(summary.mean_coherence, 0.0)
        self.assertLessEqual(summary.mean_coherence, 1.0)

    def test_engine_respects_budget_and_falls_back_to_rest(self) -> None:
        engine = RealCoreEngine(
            observer=DummyObserver(),
            actions=DummyActions(),
            coherence=DummyCoherence(),
            selector=CFARSelector(exploration_rate=0.0),
            domain_name="budget.domain",
            session_budget=0.0,
        )
        engine.memory.record(
            CycleEntry(
                cycle=0,
                action="nudge",
                mode="guided",
                state_before={"signal": 0.0},
                state_after={"signal": 0.1},
                dimensions={
                    "continuity": 0.5,
                    "vitality": 0.5,
                    "contextual_fit": 0.5,
                    "differentiation": 0.5,
                    "accountability": 0.5,
                    "reflexivity": 0.5,
                },
                coherence=0.5,
                delta=0.0,
                gco=GCOStatus.PARTIAL,
                cost_secs=0.15,
            )
        )

        entry = engine.run_cycle(1)

        self.assertEqual(entry.action, "rest")
        self.assertEqual(engine.budget_remaining, 0.0)

    def test_carryover_round_trip_restores_prior_state(self) -> None:
        substrate = MemorySubstrate(SubstrateConfig())
        engine = RealCoreEngine(
            observer=DummyObserver(),
            actions=DummyActions(),
            coherence=DummyCoherence(),
            selector=CFARSelector(exploration_rate=0.0),
            substrate=substrate,
            consolidation_pipeline=BasicConsolidationPipeline(),
            domain_name="carryover.domain",
        )
        engine.run_session(cycles=3)

        carryover = engine.export_carryover()

        restored = RealCoreEngine(
            observer=DummyObserver(),
            actions=DummyActions(),
            coherence=DummyCoherence(),
            selector=CFARSelector(exploration_rate=0.0),
            substrate=MemorySubstrate(SubstrateConfig()),
            consolidation_pipeline=BasicConsolidationPipeline(),
            domain_name="carryover.domain",
        )
        restored.load_carryover(carryover)

        self.assertEqual(len(restored.memory.entries), len(engine.memory.entries))
        self.assertEqual(restored.export_carryover().prior_coherence, carryover.prior_coherence)


class TestSessionStateStore(unittest.TestCase):
    def test_session_state_store_round_trip(self) -> None:
        temp_dir = ROOT / "tests_tmp" / f"real_core_state_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            path = SessionStateStore(Path(temp_dir) / "session_state.json")
            engine = RealCoreEngine(
                observer=DummyObserver(),
                actions=DummyActions(),
                coherence=DummyCoherence(),
                selector=CFARSelector(exploration_rate=0.0),
                substrate=MemorySubstrate(SubstrateConfig()),
                consolidation_pipeline=BasicConsolidationPipeline(),
                session_state_store=path,
                domain_name="state.domain",
            )
            engine.run_session(cycles=2)

            saved = engine.save_session_state()
            loaded = path.load()

            self.assertIsNotNone(loaded)
            self.assertEqual(len(saved.episodic_entries), len(loaded.episodic_entries))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
