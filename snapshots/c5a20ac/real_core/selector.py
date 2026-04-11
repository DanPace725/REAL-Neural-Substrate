from __future__ import annotations

import random
from enum import Enum
from typing import List, Optional, Tuple

from .types import CycleEntry, LocalPrediction, SelectionContext


class SelectionMode(str, Enum):
    ANTICIPATORY = "anticipatory"
    FLUCTUATION = "fluctuation"
    CONSTRAINT = "constraint"
    GUIDED = "guided"


class CFARSelector:
    def __init__(
        self,
        exploration_rate: float = 0.40,
        stagnation_window: int = 5,
        stagnation_threshold: float = 0.005,
        guided_threshold: int = 12,
        budget_mode: bool = True,
    ) -> None:
        self.exploration_rate = exploration_rate
        self.stagnation_window = stagnation_window
        self.stagnation_threshold = stagnation_threshold
        self.guided_threshold = guided_threshold
        self.budget_mode = budget_mode
        self.last_weakest_dimension: Optional[str] = None

    def select(self, available: List[str], history: List[CycleEntry]) -> Tuple[str, str]:
        if not available:
            raise ValueError("No available actions")

        mode = self._choose_mode(history)
        if mode == SelectionMode.FLUCTUATION:
            return self._fluctuate(available, history), mode.value
        if mode == SelectionMode.GUIDED:
            return self._guided(available, history), mode.value
        return self._exploit(available, history), mode.value

    def _choose_mode(self, history: List[CycleEntry]) -> SelectionMode:
        if len(history) < 3:
            return SelectionMode.FLUCTUATION

        maturity = min(1.0, len(history) / 100.0)
        rate = self.exploration_rate * (1.0 - 0.6 * maturity)

        recent = history[-self.stagnation_window :]
        if len(recent) == self.stagnation_window:
            mean_delta = sum(e.delta for e in recent) / len(recent)
            if abs(mean_delta) < self.stagnation_threshold:
                rate = min(0.8, rate + 0.3)

        if random.random() < rate:
            return SelectionMode.FLUCTUATION

        if len(history) >= self.guided_threshold and random.random() < 0.30:
            return SelectionMode.GUIDED

        return SelectionMode.CONSTRAINT

    def _fluctuate(self, available: List[str], history: List[CycleEntry]) -> str:
        usage = {}
        for e in history:
            usage[e.action] = usage.get(e.action, 0) + 1
        max_used = max(usage.values()) if usage else 1
        weights = [max(1, max_used - usage.get(a, 0) + 1) for a in available]
        return random.choices(available, weights=weights, k=1)[0]

    def _mean_cost(self, history: List[CycleEntry]) -> float:
        return sum(e.cost_secs for e in history) / max(1, len(history))

    def _history_score(
        self, action: str, history: List[CycleEntry], mean_cost: float
    ) -> float:
        deltas = [e.delta for e in history if e.action == action]
        score = (sum(deltas) / len(deltas)) if deltas else 0.01

        if self.budget_mode and mean_cost > 0:
            costs = [e.cost_secs for e in history if e.action == action]
            if costs:
                action_cost = sum(costs) / len(costs)
                score *= 1.0 / (1.0 + action_cost / mean_cost)
        return score

    def _exploit(self, available: List[str], history: List[CycleEntry]) -> str:
        if not history:
            return random.choice(available)

        mean_cost = self._mean_cost(history)

        best = available[0]
        best_score = -1e9
        for a in available:
            score = self._history_score(a, history, mean_cost)
            if score > best_score:
                best_score = score
                best = a

        return best

    def _guided(self, available: List[str], history: List[CycleEntry]) -> str:
        if len(history) < 4:
            return self._exploit(available, history)

        dims = list(history[-1].dimensions.keys())
        if not dims:
            return self._exploit(available, history)

        recent = history[-8:]
        weakest = min(
            dims,
            key=lambda d: sum(e.dimensions.get(d, 0.0) for e in recent) / len(recent),
        )
        self.last_weakest_dimension = weakest

        improvements = {}
        for a in available:
            vals = [e.dimensions.get(weakest, 0.0) for e in history if e.action == a]
            if vals:
                improvements[a] = sum(vals) / len(vals)

        if not improvements:
            return self._exploit(available, history)

        return max(improvements, key=improvements.get)


class AnticipatorySelector(CFARSelector):
    def __init__(
        self,
        exploration_rate: float = 0.40,
        stagnation_window: int = 5,
        stagnation_threshold: float = 0.005,
        guided_threshold: int = 12,
        budget_mode: bool = True,
        prediction_confidence_threshold: float = 0.6,
        uncertainty_tolerance: float = 0.5,
        prediction_margin_threshold: float = 0.05,
        predictive_weight: float = 1.0,
        retrospective_weight: float = 0.35,
    ) -> None:
        super().__init__(
            exploration_rate=exploration_rate,
            stagnation_window=stagnation_window,
            stagnation_threshold=stagnation_threshold,
            guided_threshold=guided_threshold,
            budget_mode=budget_mode,
        )
        self.prediction_confidence_threshold = prediction_confidence_threshold
        self.uncertainty_tolerance = uncertainty_tolerance
        self.prediction_margin_threshold = prediction_margin_threshold
        self.predictive_weight = predictive_weight
        self.retrospective_weight = retrospective_weight

    def select_with_context(
        self,
        available: List[str],
        history: List[CycleEntry],
        context: SelectionContext,
    ) -> Tuple[str, str]:
        if not available:
            raise ValueError("No available actions")

        anticipatory = self._anticipatory_choice(available, history, context)
        if anticipatory is not None:
            return anticipatory, SelectionMode.ANTICIPATORY.value

        return self.select(available, history)

    def _anticipatory_choice(
        self,
        available: List[str],
        history: List[CycleEntry],
        context: SelectionContext,
    ) -> str | None:
        predictions = {
            action: prediction
            for action, prediction in context.predictions.items()
            if action in available
        }
        if len(predictions) < 2:
            return None

        scores = {
            action: self._anticipatory_score(action, prediction, history, context)
            for action, prediction in predictions.items()
        }
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best_action, best_score = ranked[0]
        runner_up_score = ranked[1][1] if len(ranked) > 1 else -1e9
        best_prediction = predictions[best_action]
        if best_prediction.confidence < self.prediction_confidence_threshold:
            return None
        if best_prediction.uncertainty > self.uncertainty_tolerance:
            return None
        if best_score - runner_up_score < self.prediction_margin_threshold:
            return None
        return best_action

    def _anticipatory_score(
        self,
        action: str,
        prediction: LocalPrediction,
        history: List[CycleEntry],
        context: SelectionContext,
    ) -> float:
        predictive = 0.0
        if prediction.expected_delta is not None:
            predictive += prediction.expected_delta
        if (
            prediction.expected_coherence is not None
            and context.prior_coherence is not None
        ):
            predictive += prediction.expected_coherence - context.prior_coherence
        elif prediction.expected_coherence is not None:
            predictive += 0.25 * prediction.expected_coherence

        predictive *= max(0.0, prediction.confidence)
        predictive -= 0.5 * max(0.0, prediction.uncertainty)

        action_cost = context.action_costs.get(action, 0.0)
        mean_cost = sum(context.action_costs.values()) / max(1, len(context.action_costs))
        if self.budget_mode and mean_cost > 0:
            predictive *= 1.0 / (1.0 + action_cost / mean_cost)

        retrospective = 0.0
        if history:
            retrospective = self._history_score(action, history, self._mean_cost(history))

        return self.predictive_weight * predictive + self.retrospective_weight * retrospective
