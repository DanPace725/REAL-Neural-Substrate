from __future__ import annotations

import random
import shutil
import unittest
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from real_core import (
    ActionOutcome,
    AnticipatorySelector,
    BasicConsolidationPipeline,
    CFARSelector,
    ConstraintPattern,
    CycleEntry,
    ForecastError,
    ForecastOutput,
    GCOStatus,
    LocalPrediction,
    MemorySubstrate,
    PatternRecognitionModel,
    PredictionError,
    RecognitionMatch,
    RecognitionState,
    RealCoreEngine,
    SelectionContext,
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

    def gco_status(self, dimensions: dict[str, float], coherence: float, *, state_after: dict[str, float] | None = None) -> GCOStatus:
        if coherence >= 0.75:
            return GCOStatus.STABLE
        if coherence >= 0.55:
            return GCOStatus.PARTIAL
        return GCOStatus.DEGRADED


@dataclass
class DummyExpectationModel:
    last_recognition: RecognitionState | None = None

    def predict(
        self,
        state_before: dict[str, float],
        available: list[str],
        history: list[CycleEntry],
        *,
        recognition: RecognitionState | None = None,
        prior_coherence: float | None = None,
        substrate: object | None = None,
    ) -> dict[str, LocalPrediction]:
        self.last_recognition = recognition
        signal = state_before.get("signal", 0.0)
        base_delta = signal - 0.5
        predictions: dict[str, LocalPrediction] = {}
        for action in available:
            direction = 1.0 if action == "nudge" else -1.0
            predictions[action] = LocalPrediction(
                expected_outcome={"signal": signal + 0.1 * direction},
                expected_coherence=max(0.0, min(1.0, 0.55 + 0.2 * signal * direction)),
                expected_delta=base_delta * direction
                + (0.1 * recognition.confidence if recognition is not None else 0.0),
                confidence=0.8 if action == "nudge" else 0.4,
                uncertainty=0.2 if action == "nudge" else 0.6,
                metadata={"source": "dummy_expectation"},
            )
        return predictions

    def compare(
        self,
        action: str,
        prediction: LocalPrediction | None,
        state_after: dict[str, float],
        dimensions: dict[str, float],
        coherence: float,
        delta: float,
        history: list[CycleEntry],
    ) -> PredictionError | None:
        if prediction is None:
            return None
        predicted_signal = float(prediction.expected_outcome.get("signal", 0.0))
        actual_signal = float(state_after.get("signal", 0.0))
        outcome_error = actual_signal - predicted_signal
        coherence_error = (
            None
            if prediction.expected_coherence is None
            else coherence - prediction.expected_coherence
        )
        delta_error = (
            None if prediction.expected_delta is None else delta - prediction.expected_delta
        )
        magnitude = abs(outcome_error)
        if coherence_error is not None:
            magnitude += abs(coherence_error)
        if delta_error is not None:
            magnitude += abs(delta_error)
        return PredictionError(
            outcome_error={"signal": outcome_error},
            coherence_error=coherence_error,
            delta_error=delta_error,
            magnitude=magnitude,
            metadata={"action": action},
        )


@dataclass
class DummyRecognitionModel:
    def recognize(
        self,
        state_before: dict[str, float],
        history: list[CycleEntry],
        *,
        prior_coherence: float | None = None,
        substrate: object | None = None,
    ) -> RecognitionState | None:
        signal = state_before.get("signal", 0.0)
        if signal < 0.5:
            return RecognitionState(
                confidence=0.85,
                novelty=0.2,
                matches=[
                    RecognitionMatch(
                        label="low_signal_pattern",
                        score=0.9,
                        source="dummy_recognizer",
                        strength=0.75,
                        metadata={"signal_band": "low"},
                    )
                ],
                metadata={"recognized_shape": "low_signal"},
            )
        return RecognitionState(
            confidence=0.25,
            novelty=0.8,
            matches=[],
            metadata={"recognized_shape": "unknown"},
        )


@dataclass
class DummyForecastModel:
    last_recognition: RecognitionState | None = None
    last_predictions: dict[str, LocalPrediction] | None = None

    def forecast(
        self,
        state_before: dict[str, float],
        available: list[str],
        history: list[CycleEntry],
        *,
        recognition: RecognitionState | None = None,
        predictions: dict[str, LocalPrediction] | None = None,
        prior_coherence: float | None = None,
        substrate: object | None = None,
    ) -> ForecastOutput | None:
        self.last_recognition = recognition
        self.last_predictions = dict(predictions or {})
        signal = float(state_before.get("signal", 0.0))
        direction = "rise" if signal >= 0.5 else "fall"
        confidence = 0.75 if direction == "rise" else 0.65
        return ForecastOutput(
            target_label=direction,
            confidence=confidence,
            candidates={"rise": signal, "fall": 1.0 - signal},
            domain="dummy_signal_trend",
            metadata={"source": "dummy_forecast"},
        )

    def compare(
        self,
        forecast: ForecastOutput | None,
        state_after: dict[str, float],
        dimensions: dict[str, float],
        coherence: float,
        delta: float,
        history: list[CycleEntry],
    ) -> ForecastError | None:
        if forecast is None:
            return None
        actual_label = "rise" if float(state_after.get("signal", 0.0)) >= 0.5 else "fall"
        correct = forecast.target_label == actual_label
        correctness = 1.0 if correct else 0.0
        confidence_error = float(forecast.confidence) - correctness
        return ForecastError(
            predicted_label=forecast.target_label,
            actual_label=actual_label,
            correct=correct,
            resolved=True,
            confidence_error=confidence_error,
            magnitude=abs(confidence_error),
            metadata={"source": "dummy_forecast"},
        )


@dataclass
class RecordingContextualSelector:
    last_context: SelectionContext | None = None

    def select(self, available: list[str], history: list[CycleEntry]) -> tuple[str, str]:
        return available[0], "fallback"

    def select_with_context(
        self,
        available: list[str],
        history: list[CycleEntry],
        context: SelectionContext,
    ) -> tuple[str, str]:
        self.last_context = context
        preferred = "nudge" if "nudge" in available else available[0]
        return preferred, "contextual"


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

    def test_engine_records_optional_predictions_and_errors(self) -> None:
        expectation_model = DummyExpectationModel()
        engine = RealCoreEngine(
            observer=DummyObserver(),
            actions=DummyActions(),
            coherence=DummyCoherence(),
            selector=CFARSelector(exploration_rate=0.0),
            expectation_model=expectation_model,
            domain_name="anticipation.domain",
        )

        entry = engine.run_cycle(1)

        self.assertIsNotNone(entry.prediction)
        self.assertIsNotNone(entry.prediction_error)
        self.assertIn("anticipation", entry.state_before)
        anticipation = entry.state_before["anticipation"]
        self.assertIn("predictions", anticipation)
        self.assertIn(entry.action, anticipation["predictions"])
        self.assertEqual(entry.prediction.metadata.get("source"), "dummy_expectation")
        self.assertIsNone(expectation_model.last_recognition)

    def test_engine_records_recognition_and_passes_it_to_prediction(self) -> None:
        expectation_model = DummyExpectationModel()
        engine = RealCoreEngine(
            observer=DummyObserver(),
            actions=DummyActions(),
            coherence=DummyCoherence(),
            selector=CFARSelector(exploration_rate=0.0),
            recognition_model=DummyRecognitionModel(),
            expectation_model=expectation_model,
            domain_name="recognition.domain",
        )

        entry = engine.run_cycle(1)

        self.assertIsNotNone(entry.recognition)
        assert entry.recognition is not None
        self.assertEqual(entry.recognition.metadata.get("recognized_shape"), "low_signal")
        self.assertIn("recognition", entry.state_before)
        self.assertEqual(
            entry.state_before["recognition"]["matches"][0]["label"],
            "low_signal_pattern",
        )
        self.assertIsNotNone(expectation_model.last_recognition)
        assert expectation_model.last_recognition is not None
        self.assertEqual(
            expectation_model.last_recognition.metadata.get("recognized_shape"),
            "low_signal",
        )

    def test_engine_passes_selection_context_to_contextual_selector(self) -> None:
        selector = RecordingContextualSelector()
        engine = RealCoreEngine(
            observer=DummyObserver(),
            actions=DummyActions(),
            coherence=DummyCoherence(),
            selector=selector,
            recognition_model=DummyRecognitionModel(),
            expectation_model=DummyExpectationModel(),
            domain_name="contextual.selection.domain",
        )

        entry = engine.run_cycle(1)

        self.assertEqual(entry.action, "nudge")
        self.assertEqual(entry.mode, "contextual")
        self.assertIsNotNone(selector.last_context)
        assert selector.last_context is not None
        self.assertEqual(selector.last_context.cycle, 1)
        self.assertIn("nudge", selector.last_context.predictions)
        self.assertIn("anticipation", selector.last_context.state_before)
        self.assertIsNotNone(selector.last_context.recognition)

    def test_engine_records_explicit_forecast_readout(self) -> None:
        forecast_model = DummyForecastModel()
        engine = RealCoreEngine(
            observer=DummyObserver(),
            actions=DummyActions(),
            coherence=DummyCoherence(),
            selector=CFARSelector(exploration_rate=0.0),
            recognition_model=DummyRecognitionModel(),
            expectation_model=DummyExpectationModel(),
            forecast_model=forecast_model,
            domain_name="forecast.domain",
        )

        entry = engine.run_cycle(1)

        self.assertIsNotNone(entry.forecast)
        self.assertIsNotNone(entry.forecast_error)
        self.assertIn("forecast", entry.state_before)
        assert entry.forecast is not None
        assert entry.forecast_error is not None
        self.assertEqual(entry.forecast.domain, "dummy_signal_trend")
        self.assertEqual(entry.forecast.metadata.get("source"), "dummy_forecast")
        self.assertTrue(entry.forecast_error.resolved)
        self.assertEqual(entry.forecast_error.metadata.get("source"), "dummy_forecast")
        self.assertEqual(
            forecast_model.last_recognition.metadata.get("recognized_shape"),
            "low_signal",
        )
        self.assertIn("nudge", forecast_model.last_predictions)

    def test_anticipatory_selector_prefers_high_confidence_prediction(self) -> None:
        selector = AnticipatorySelector(exploration_rate=0.0)
        context = SelectionContext(
            cycle=1,
            state_before={"signal": 0.2},
            recognition=RecognitionState(confidence=0.85, novelty=0.2),
            predictions={
                "rest": LocalPrediction(
                    expected_delta=-0.2,
                    expected_coherence=0.4,
                    confidence=0.35,
                    uncertainty=0.7,
                ),
                "nudge": LocalPrediction(
                    expected_delta=0.25,
                    expected_coherence=0.8,
                    confidence=0.9,
                    uncertainty=0.1,
                ),
            },
            prior_coherence=0.5,
            budget_remaining=1.0,
            action_costs={"rest": 0.0, "nudge": 0.15},
        )

        action, mode = selector.select_with_context(["rest", "nudge"], [], context)

        self.assertEqual(action, "nudge")
        self.assertEqual(mode, "anticipatory")

    def test_cfar_selector_rng_is_reproducible_when_injected(self) -> None:
        history = [
            CycleEntry(
                cycle=1,
                action="rest",
                mode="constraint",
                state_before={"signal": 0.1},
                state_after={"signal": 0.2},
                dimensions={"signal": 0.2},
                coherence=0.2,
                delta=0.0,
                gco=GCOStatus.DEGRADED,
                cost_secs=0.1,
            )
        ]
        selector_a = CFARSelector(exploration_rate=1.0, rng=random.Random(17))
        selector_b = CFARSelector(exploration_rate=1.0, rng=random.Random(17))

        action_a, mode_a = selector_a.select(["rest", "nudge", "wait"], history)
        action_b, mode_b = selector_b.select(["rest", "nudge", "wait"], history)

        self.assertEqual((action_a, mode_a), (action_b, mode_b))

    def test_pattern_recognition_model_matches_substrate_patterns(self) -> None:
        substrate = MemorySubstrate(SubstrateConfig(keys=("signal", "energy")))
        substrate.constraint_patterns.append(
            ConstraintPattern(
                dim_scores={"signal": 0.2, "energy": 0.8},
                dim_trends={"signal": 0.0, "energy": 0.0},
                valence=0.6,
                strength=0.9,
                coherence_level=0.72,
                match_count=4,
                source="low_signal_energy_pattern",
            )
        )
        recognizer = PatternRecognitionModel(min_match_score=0.5)

        recognition = recognizer.recognize(
            {"signal": 0.21, "energy": 0.79},
            history=[],
            substrate=substrate,
        )

        self.assertIsNotNone(recognition)
        assert recognition is not None
        self.assertGreater(recognition.confidence, 0.8)
        self.assertLess(recognition.novelty, 0.25)
        self.assertEqual(recognition.metadata.get("dims_source"), "state_before")
        self.assertTrue(recognition.metadata.get("matched"))
        self.assertEqual(recognition.matches[0].source, "low_signal_energy_pattern")

    def test_engine_records_pattern_based_recognition(self) -> None:
        substrate = MemorySubstrate(SubstrateConfig(keys=("signal", "energy")))
        substrate.constraint_patterns.append(
            ConstraintPattern(
                dim_scores={"signal": 0.2, "energy": 0.8},
                dim_trends={"signal": 0.0, "energy": 0.0},
                strength=0.85,
                coherence_level=0.7,
                source="low_signal_energy_pattern",
            )
        )
        expectation_model = DummyExpectationModel()
        engine = RealCoreEngine(
            observer=DummyObserver(),
            actions=DummyActions(),
            coherence=DummyCoherence(),
            selector=CFARSelector(exploration_rate=0.0),
            substrate=substrate,
            recognition_model=PatternRecognitionModel(min_match_score=0.5),
            expectation_model=expectation_model,
            domain_name="pattern.recognition.domain",
        )

        entry = engine.run_cycle(1)

        self.assertIsNotNone(entry.recognition)
        assert entry.recognition is not None
        self.assertTrue(entry.recognition.matches)
        self.assertEqual(
            entry.recognition.matches[0].source,
            "low_signal_energy_pattern",
        )
        self.assertIn("recognition", entry.state_before)
        self.assertEqual(
            entry.state_before["recognition"]["matches"][0]["source"],
            "low_signal_energy_pattern",
        )
        self.assertIsNotNone(expectation_model.last_recognition)
        assert expectation_model.last_recognition is not None
        self.assertEqual(
            expectation_model.last_recognition.matches[0].source,
            "low_signal_energy_pattern",
        )


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

    def test_session_state_store_round_trips_prediction_fields(self) -> None:
        temp_dir = ROOT / "tests_tmp" / f"real_core_prediction_state_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            path = SessionStateStore(Path(temp_dir) / "session_state.json")
            engine = RealCoreEngine(
                observer=DummyObserver(),
                actions=DummyActions(),
                coherence=DummyCoherence(),
                selector=CFARSelector(exploration_rate=0.0),
                expectation_model=DummyExpectationModel(),
                session_state_store=path,
                domain_name="prediction.state.domain",
            )
            engine.run_session(cycles=2)

            saved = engine.save_session_state()
            loaded = path.load()

            self.assertIsNotNone(loaded)
            self.assertIsNotNone(saved.episodic_entries[0].prediction)
            self.assertIsNotNone(loaded.episodic_entries[0].prediction)
            self.assertEqual(
                loaded.episodic_entries[0].prediction.metadata.get("source"),
                "dummy_expectation",
            )
            self.assertIsNotNone(loaded.episodic_entries[0].prediction_error)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_session_state_store_round_trips_forecast_fields(self) -> None:
        temp_dir = ROOT / "tests_tmp" / f"real_core_forecast_state_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            path = SessionStateStore(Path(temp_dir) / "session_state.json")
            engine = RealCoreEngine(
                observer=DummyObserver(),
                actions=DummyActions(),
                coherence=DummyCoherence(),
                selector=CFARSelector(exploration_rate=0.0),
                recognition_model=DummyRecognitionModel(),
                expectation_model=DummyExpectationModel(),
                forecast_model=DummyForecastModel(),
                session_state_store=path,
                domain_name="forecast.state.domain",
            )
            engine.run_session(cycles=2)

            saved = engine.save_session_state()
            loaded = path.load()

            self.assertIsNotNone(loaded)
            self.assertIsNotNone(saved.episodic_entries[0].forecast)
            self.assertIsNotNone(loaded.episodic_entries[0].forecast)
            self.assertIsNotNone(loaded.episodic_entries[0].forecast_error)
            assert loaded.episodic_entries[0].forecast is not None
            self.assertEqual(
                loaded.episodic_entries[0].forecast.metadata.get("source"),
                "dummy_forecast",
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_session_state_store_round_trips_recognition_fields(self) -> None:
        temp_dir = ROOT / "tests_tmp" / f"real_core_recognition_state_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            path = SessionStateStore(Path(temp_dir) / "session_state.json")
            engine = RealCoreEngine(
                observer=DummyObserver(),
                actions=DummyActions(),
                coherence=DummyCoherence(),
                selector=CFARSelector(exploration_rate=0.0),
                recognition_model=DummyRecognitionModel(),
                expectation_model=DummyExpectationModel(),
                session_state_store=path,
                domain_name="recognition.state.domain",
            )
            engine.run_session(cycles=2)

            saved = engine.save_session_state()
            loaded = path.load()

            self.assertIsNotNone(loaded)
            self.assertIsNotNone(saved.episodic_entries[0].recognition)
            self.assertIsNotNone(loaded.episodic_entries[0].recognition)
            assert loaded.episodic_entries[0].recognition is not None
            self.assertEqual(
                loaded.episodic_entries[0].recognition.matches[0].label,
                "low_signal_pattern",
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
