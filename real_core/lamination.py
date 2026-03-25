from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .interfaces import SliceRegulator, SliceRunner
from .types import ModeExperience, RegulatorySignal, SettlementDecision, SliceSummary


def _clamp_budget(value: int, *, minimum: int = 1, maximum: int = 4096) -> int:
    return max(minimum, min(maximum, int(value)))


@dataclass
class LaminatedRunResult:
    summaries: List[SliceSummary] = field(default_factory=list)
    final_signal: RegulatorySignal | None = None
    final_decision: SettlementDecision = SettlementDecision.CONTINUE
    final_cycle_budget: int = 0


class HeuristicSliceRegulator:
    """Deterministic v0 regulator over compact slice summaries."""

    def __init__(
        self,
        *,
        flat_delta_epsilon: float = 0.02,
        low_conflict_threshold: float = 0.2,
        high_conflict_threshold: float = 0.5,
        high_uncertainty_threshold: float = 0.6,
        accuracy_threshold: float = 0.0,
        stall_slices_before_growth: int = 2,
    ) -> None:
        self.flat_delta_epsilon = float(flat_delta_epsilon)
        self.low_conflict_threshold = float(low_conflict_threshold)
        self.high_conflict_threshold = float(high_conflict_threshold)
        self.high_uncertainty_threshold = float(high_uncertainty_threshold)
        self.accuracy_threshold = float(accuracy_threshold)
        self.stall_slices_before_growth = max(1, int(stall_slices_before_growth))

    def regulate(self, history: List[SliceSummary]) -> RegulatorySignal:
        if not history:
            return RegulatorySignal()

        current = history[-1]
        previous = history[-2] if len(history) >= 2 else None

        improving = current.coherence_delta > self.flat_delta_epsilon
        uncertainty_dropping = (
            previous is None
            or current.mean_uncertainty < previous.mean_uncertainty - 0.02
        )
        guidance_improving = (
            previous is None
            or current.guidance_alignment is None
            or previous.guidance_alignment is None
            or current.guidance_alignment >= previous.guidance_alignment
        )

        if current.conflict_level >= 0.75:
            carryover_filter_mode = "drop"
        elif current.conflict_level >= 0.35:
            carryover_filter_mode = "soften"
        else:
            carryover_filter_mode = "keep"

        if current.mean_uncertainty >= self.high_uncertainty_threshold and guidance_improving:
            context_pressure = "high"
        elif current.mean_uncertainty <= 0.3 and current.conflict_level <= self.low_conflict_threshold:
            context_pressure = "low"
        else:
            context_pressure = "medium"

        decision_hint = SettlementDecision.CONTINUE
        stop_reason = ""
        if self._should_settle(history):
            decision_hint = SettlementDecision.SETTLE
            stop_reason = "coherence_flat_and_conflict_low"
        elif self._should_escalate(history):
            decision_hint = SettlementDecision.ESCALATE
            stop_reason = "coherence_flat_and_conflict_high"
        elif (
            carryover_filter_mode == "drop"
            and improving
            and current.candidate_carryover_count > 0
        ):
            decision_hint = SettlementDecision.BRANCH
            stop_reason = "productive_but_carried_context_incompatible"

        # Find weakest context and compute accuracy gap against it
        weak_context_bit: float | None = None
        weak_context_gap: float = 0.0
        if self.accuracy_threshold > 0.0 and current.context_accuracy:
            worst_ctx = min(current.context_accuracy, key=lambda k: current.context_accuracy[k])
            worst_acc = current.context_accuracy[worst_ctx]
            gap = max(0.0, self.accuracy_threshold - worst_acc)
            if gap > 0.0:
                weak_context_gap = gap
                # Parse context_bit from key like "context_0" or "context_1"
                suffix = worst_ctx.removeprefix("context_")
                try:
                    weak_context_bit = float(suffix)
                except ValueError:
                    weak_context_bit = None

        next_slice_budget = current.slice_budget
        if not improving and previous is not None and current.mean_uncertainty >= previous.mean_uncertainty:
            # Stalling: the system needs more time, not less.
            next_slice_budget = _clamp_budget(round(current.slice_budget * 1.25))
        elif improving and uncertainty_dropping:
            # Converging well: maintain current budget (no need to grow).
            next_slice_budget = current.slice_budget

        accuracy_gap = (
            max(0.0, self.accuracy_threshold - float(current.metadata.get("mean_bit_accuracy", 0.0)))
            if self.accuracy_threshold > 0.0
            else 0.0
        )
        bias_updates: dict[str, float] = {
            "guidance_weight": round(float(current.guidance_alignment or 0.0), 4),
            "coherence_delta": round(current.coherence_delta, 4),
        }
        if accuracy_gap > 0.0:
            bias_updates["accuracy_gap"] = round(accuracy_gap, 4)
        if weak_context_bit is not None and weak_context_gap > 0.0:
            bias_updates["weak_context_bit"] = weak_context_bit
            bias_updates["weak_context_gap"] = round(weak_context_gap, 4)

        capability_mode = self._select_capability_mode(history)

        return RegulatorySignal(
            next_slice_budget=next_slice_budget,
            carryover_filter_mode=carryover_filter_mode,
            context_pressure=context_pressure,
            decision_hint=decision_hint,
            capability_mode=capability_mode,
            gating_updates={
                "conflict_penalty": round(current.conflict_level, 4),
                "uncertainty_gate": round(current.mean_uncertainty, 4),
            },
            bias_updates=bias_updates,
            stop_reason=stop_reason,
        )

    def _should_settle(self, history: List[SliceSummary]) -> bool:
        if self.accuracy_threshold > 0.0 and history:
            # Explicit accuracy target: only settle when threshold is met.
            # Coherence-flatness paths are skipped — flat-but-inaccurate is not convergence.
            window = history[-2:] if len(history) >= 2 else history[-1:]

            def _meets_threshold(s: SliceSummary) -> bool:
                if s.context_accuracy:
                    return min(s.context_accuracy.values()) >= self.accuracy_threshold
                return float(s.metadata.get("mean_bit_accuracy", 0.0)) >= self.accuracy_threshold

            return all(_meets_threshold(s) for s in window)

        # No accuracy target: fall back to coherence-flatness heuristics.
        if len(history) < 2:
            return False
        recent = history[-2:]
        if all(
            abs(item.coherence_delta) <= self.flat_delta_epsilon
            and item.ambiguity_level <= self.low_conflict_threshold
            and item.conflict_level <= self.low_conflict_threshold
            for item in recent
        ):
            return True

        latest = recent[-1]
        return (
            self._recently_flat(recent)
            and self._is_productive(latest)
            and self._is_input_tapering(latest)
            and latest.conflict_level <= self.high_conflict_threshold + 0.05
        )

    def _should_escalate(self, history: List[SliceSummary]) -> bool:
        if len(history) < 2:
            return False
        recent = history[-2:]
        return (
            self._recently_flat(recent)
            and all(
                item.ambiguity_level >= self.high_conflict_threshold
                or item.conflict_level >= self.high_conflict_threshold
                for item in recent
            )
            and not any(self._is_productive(item) for item in recent)
        )

    def _recently_flat(self, recent: List[SliceSummary]) -> bool:
        return all(
            abs(item.coherence_delta) <= self.flat_delta_epsilon
            for item in recent
        )

    def _is_productive(self, summary: SliceSummary) -> bool:
        exact_matches = float(summary.cost_summary.get("exact_matches", 0.0))
        partial_matches = float(summary.cost_summary.get("partial_matches", 0.0))
        bit_accuracy = float(summary.metadata.get("mean_bit_accuracy", 0.0))
        bit_accuracy_per_cost = float(
            summary.cost_summary.get("bit_accuracy_per_cost", 0.0),
        )
        guidance_alignment = float(summary.guidance_alignment or 0.0)
        return (
            exact_matches > 0.0
            or bit_accuracy >= 0.6
            or (partial_matches > 0.0 and bit_accuracy_per_cost >= 0.3)
            or guidance_alignment >= 0.7
        )

    def _select_capability_mode(self, history: List[SliceSummary]) -> str | None:
        """Suggest a capability mode for the next slice.

        Returns None if the current mode should be kept.  Promotes the current
        mode to its growth variant when accuracy is stalling below threshold
        across enough consecutive slices and the substrate has not yet grown.
        """
        if self.accuracy_threshold <= 0.0 or not history:
            return None

        # Only promote non-growth modes.
        current_mode = history[-1].mode_used
        if current_mode.startswith("growth-"):
            return None

        # Check whether the last N slices are all below threshold with no improvement.
        window = history[-self.stall_slices_before_growth :]
        if len(window) < self.stall_slices_before_growth:
            return None

        def _min_ctx_acc(s: SliceSummary) -> float:
            if s.context_accuracy:
                return min(s.context_accuracy.values())
            return float(s.metadata.get("mean_bit_accuracy", 0.0))

        accs = [_min_ctx_acc(s) for s in window]
        if any(acc >= self.accuracy_threshold for acc in accs):
            return None  # already reached threshold at some point — don't promote

        # Stalling: no improvement across the window
        improving = accs[-1] > accs[0] + 0.02
        if improving:
            return None

        # Promote visible → growth-visible, latent → growth-latent
        if current_mode == "latent":
            return "growth-latent"
        return "growth-visible"

    def _is_input_tapering(self, summary: SliceSummary) -> bool:
        return (
            summary.cycles_used > 0
            and summary.examples_seen > 0
            and summary.examples_seen <= max(1, summary.cycles_used // 2)
        )


class LearningSliceRegulator:
    """Slow-layer regulator with episodic memory, prediction, and learned mode selection.

    Wraps HeuristicSliceRegulator for all settle/escalate/GCO decisions.
    Adds the REAL observe→predict→select→score→compare loop at the meta level:

      observe   : SliceSummary → extract feature vector
      predict   : for each candidate mode, estimate expected accuracy delta using
                  similarity-weighted average over past ModeExperience records
      select    : emit capability_mode for the mode with highest predicted delta
                  (only if the margin over the current mode exceeds switch_margin)
      score     : after the next slice runs, compare predicted vs actual delta
      compare   : compute prediction_error and store ModeExperience in memory

    Mode candidates are restricted to the current mode and its growth upgrade
    (visible → growth-visible, latent → growth-latent) so the learning stays
    in-distribution with the active scenario.
    """

    # Growth upgrade paths — other direction switches are not considered
    _MODE_UPGRADE: Dict[str, str] = {
        "visible": "growth-visible",
        "latent": "growth-latent",
        "self-selected": "growth-visible",
    }

    # Warm-start priors when no memory exists for a mode
    _MODE_PRIORS: Dict[str, float] = {
        "visible": 0.05,
        "latent": 0.05,
        "self-selected": 0.05,
        "growth-visible": 0.20,
        "growth-latent": 0.10,
    }

    def __init__(
        self,
        *,
        accuracy_threshold: float = 0.0,
        memory_capacity: int = 50,
        switch_margin: float = 0.03,
        **heuristic_kwargs,
    ) -> None:
        self._heuristic = HeuristicSliceRegulator(
            accuracy_threshold=accuracy_threshold,
            **heuristic_kwargs,
        )
        self.memory_capacity = memory_capacity
        self.switch_margin = switch_margin
        self._experiences: List[ModeExperience] = []
        # State carried between regulate() calls for the score step
        self._pending_prediction: tuple[str, float] | None = None  # (mode, predicted_delta)
        self._prev_min_ctx_acc: float | None = None
        self._prev_features: Dict[str, float] | None = None

    @property
    def experiences(self) -> List[ModeExperience]:
        return list(self._experiences)

    def regulate(self, history: List[SliceSummary]) -> RegulatorySignal:
        if not history:
            return RegulatorySignal()

        current = history[-1]
        current_min = self._min_ctx_acc(current)

        # --- Score: compare last prediction to what actually happened ---
        if (
            self._pending_prediction is not None
            and self._prev_min_ctx_acc is not None
            and self._prev_features is not None
        ):
            predicted_mode, predicted_delta = self._pending_prediction
            observed_delta = current_min - self._prev_min_ctx_acc
            prediction_error = abs(predicted_delta - observed_delta)
            self._experiences.append(
                ModeExperience(
                    mode=predicted_mode,
                    features=self._prev_features,
                    predicted_delta=predicted_delta,
                    observed_delta=observed_delta,
                    prediction_error=prediction_error,
                )
            )
            if len(self._experiences) > self.memory_capacity:
                self._experiences = self._experiences[-self.memory_capacity :]

        # --- Delegate settle/escalate/GCO/bias/budget to heuristic layer ---
        signal = self._heuristic.regulate(history)

        # On terminal decisions, clear pending state and return unchanged
        if signal.decision_hint in (SettlementDecision.SETTLE, SettlementDecision.ESCALATE):
            self._pending_prediction = None
            self._prev_min_ctx_acc = None
            self._prev_features = None
            return signal

        # --- Predict: estimate delta for each candidate mode ---
        current_features = self._extract_features(current)
        current_mode = current.mode_used
        candidates = self._candidate_modes(current_mode)
        predictions = {m: self._predict_delta(m, current_features) for m in candidates}

        best_mode = max(predictions, key=lambda m: predictions[m])

        # --- Store pending prediction for the next score step ---
        self._pending_prediction = (best_mode, predictions[best_mode])
        self._prev_min_ctx_acc = current_min
        self._prev_features = current_features

        # --- Select: emit mode switch only if improvement margin is meaningful ---
        new_mode: str | None = None
        current_pred = predictions.get(current_mode, self._MODE_PRIORS.get(current_mode, 0.0))
        if best_mode != current_mode and predictions[best_mode] > current_pred + self.switch_margin:
            new_mode = best_mode

        prediction_meta: Dict[str, float] = {
            f"predicted_delta_{m}": round(v, 4) for m, v in predictions.items()
        }
        prediction_meta["memory_size"] = float(len(self._experiences))

        return RegulatorySignal(
            next_slice_budget=signal.next_slice_budget,
            carryover_filter_mode=signal.carryover_filter_mode,
            context_pressure=signal.context_pressure,
            decision_hint=signal.decision_hint,
            capability_mode=new_mode if new_mode != signal.capability_mode else signal.capability_mode,
            gating_updates=signal.gating_updates,
            bias_updates=signal.bias_updates,
            stop_reason=signal.stop_reason,
            metadata=prediction_meta,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _candidate_modes(self, current_mode: str) -> List[str]:
        candidates = [current_mode]
        upgrade = self._MODE_UPGRADE.get(current_mode)
        if upgrade and upgrade not in candidates:
            candidates.append(upgrade)
        return candidates

    def _predict_delta(self, mode: str, features: Dict[str, float]) -> float:
        """Return similarity-weighted average observed_delta for this mode.

        Falls back to a warm-start prior when no memory exists for the mode.
        """
        relevant = [e for e in self._experiences if e.mode == mode]
        if not relevant:
            return self._MODE_PRIORS.get(mode, 0.0)

        weights: List[float] = []
        deltas: List[float] = []
        for exp in relevant:
            sq_dist = sum(
                (features.get(k, 0.0) - exp.features.get(k, 0.0)) ** 2
                for k in features
            )
            w = 1.0 / (1.0 + sq_dist ** 0.5)
            weights.append(w)
            deltas.append(exp.observed_delta)

        total_w = sum(weights)
        return sum(w * d for w, d in zip(weights, deltas)) / total_w

    def _extract_features(self, summary: SliceSummary) -> Dict[str, float]:
        return {
            "min_ctx_acc": self._min_ctx_acc(summary),
            "conflict": summary.conflict_level,
            "ambiguity": summary.ambiguity_level,
            "coherence_delta": summary.coherence_delta,
        }

    def _min_ctx_acc(self, summary: SliceSummary) -> float:
        if summary.context_accuracy:
            return min(summary.context_accuracy.values())
        return float(summary.metadata.get("mean_bit_accuracy", 0.0))


class LaminatedController:
    """Reusable orchestration layer above bounded fast-layer slices.

    The loop is criteria-driven: it runs until the regulator issues a
    non-CONTINUE settlement decision (SETTLE, ESCALATE, or BRANCH).
    ``safety_limit`` exists only to prevent runaway loops during
    development — it is not a budget and should not constrain normal
    operation.
    """

    def __init__(
        self,
        runner: SliceRunner,
        regulator: SliceRegulator | None = None,
        *,
        initial_cycle_budget: int = 8,
        safety_limit: int = 200,
    ) -> None:
        self.runner = runner
        self.regulator = regulator or HeuristicSliceRegulator()
        self.initial_cycle_budget = _clamp_budget(initial_cycle_budget)
        self.safety_limit = max(1, int(safety_limit))

    def run(self) -> LaminatedRunResult:
        history: List[SliceSummary] = []
        cycle_budget = self.initial_cycle_budget
        signal: RegulatorySignal | None = None
        decision = SettlementDecision.CONTINUE
        slice_id = 0

        while True:
            slice_id += 1
            summary = self.runner.run_slice(
                slice_id=slice_id,
                cycle_budget=cycle_budget,
                regulatory_signal=signal,
            )
            history.append(summary)
            signal = self.regulator.regulate(history)
            decision = self._resolve_decision(history, signal)
            if decision != SettlementDecision.CONTINUE:
                return LaminatedRunResult(
                    summaries=history,
                    final_signal=signal,
                    final_decision=decision,
                    final_cycle_budget=cycle_budget,
                )
            cycle_budget = _clamp_budget(signal.next_slice_budget or cycle_budget)

            if slice_id >= self.safety_limit:
                return LaminatedRunResult(
                    summaries=history,
                    final_signal=signal,
                    final_decision=decision,
                    final_cycle_budget=cycle_budget,
                )

    def _resolve_decision(
        self,
        history: List[SliceSummary],
        signal: RegulatorySignal | None,
    ) -> SettlementDecision:
        if signal is None:
            return SettlementDecision.CONTINUE
        if signal.decision_hint == SettlementDecision.BRANCH:
            latest = history[-1]
            if latest.candidate_carryover_count > 0 and latest.conflict_level >= 0.5:
                return SettlementDecision.BRANCH
            return SettlementDecision.CONTINUE
        if signal.decision_hint in (
            SettlementDecision.SETTLE,
            SettlementDecision.ESCALATE,
        ):
            return signal.decision_hint
        return SettlementDecision.CONTINUE
