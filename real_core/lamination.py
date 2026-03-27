from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .interfaces import SliceRegulator, SliceRunner
from .types import (
    ModeExperience,
    RegulatorySignal,
    SettlementDecision,
    SliceExecutionPlan,
    SliceSummary,
)


def _clamp_budget(value: int, *, minimum: int = 1, maximum: int = 4096) -> int:
    return max(minimum, min(maximum, int(value)))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _intervention_status(observed_delta: float, *, epsilon: float = 0.01) -> str:
    if observed_delta > epsilon:
        return "improved"
    if observed_delta < -epsilon:
        return "worsened"
    return "flat"


def _intervention_summary(
    *,
    observed_delta: float,
    predicted_delta: float | None = None,
    metric_name: str = "min_ctx_acc",
) -> dict[str, float | str | None]:
    prediction_error = (
        None if predicted_delta is None else abs(float(predicted_delta) - float(observed_delta))
    )
    return {
        "intervention_target_metric": metric_name,
        "intervention_status": _intervention_status(observed_delta),
        "intervention_signed_delta": round(float(observed_delta), 4),
        "intervention_payoff": round(float(observed_delta), 4),
        "intervention_regret": None
        if prediction_error is None
        else round(float(prediction_error), 4),
        "intervention_predicted_delta": None
        if predicted_delta is None
        else round(float(predicted_delta), 4),
        "intervention_observed_delta": round(float(observed_delta), 4),
    }


def _final_accuracy(summary: SliceSummary) -> float:
    return float(
        summary.metadata.get(
            "final_accuracy",
            summary.metadata.get("mean_bit_accuracy", 0.0),
        )
    )


def _floor_accuracy(summary: SliceSummary) -> float:
    if summary.context_accuracy:
        return min(float(value) for value in summary.context_accuracy.values())
    return float(
        summary.metadata.get(
            "worst_context_accuracy",
            summary.metadata.get(
                "floor_accuracy",
                _final_accuracy(summary),
            ),
        )
    )


def _context_asymmetry(summary: SliceSummary) -> dict[str, float]:
    if summary.context_accuracy:
        values = [float(value) for value in summary.context_accuracy.values()]
    else:
        final_acc = _final_accuracy(summary)
        values = [final_acc]
    best = max(values)
    worst = min(values)
    spread = max(0.0, best - worst)
    collapsed = 1.0 if (
        best >= 0.75
        and worst <= 0.25
        and spread >= 0.45
    ) else 0.0
    return {
        "best": best,
        "worst": worst,
        "spread": spread,
        "collapsed": collapsed,
    }


def _context_debt_summary(
    history: List[SliceSummary],
    *,
    accuracy_threshold: float,
) -> dict[str, float | str | None]:
    if not history or accuracy_threshold <= 0.0:
        return {
            "max_context_debt": 0.0,
            "total_context_debt": 0.0,
            "max_context_credit": 0.0,
            "open_context_count": 0.0,
            "best_debt_context": None,
            "best_debt_gap": 0.0,
        }

    context_keys: list[str] = []
    for summary in history:
        for key in summary.context_accuracy:
            if key not in context_keys:
                context_keys.append(str(key))
    if not context_keys:
        context_keys = ["aggregate"]

    debt: dict[str, float] = {key: 0.0 for key in context_keys}
    credit: dict[str, float] = {key: 0.0 for key in context_keys}

    for summary in history:
        observed = dict(summary.context_accuracy)
        for key in context_keys:
            if observed:
                if key not in observed:
                    credit[key] *= 0.85
                    continue
                accuracy = float(observed[key])
            else:
                if key != "aggregate":
                    credit[key] *= 0.85
                    continue
                accuracy = _final_accuracy(summary)

            shortfall = max(0.0, accuracy_threshold - accuracy)
            surplus = max(0.0, accuracy - accuracy_threshold)
            debt[key] = min(3.0, debt[key] * 0.85 + shortfall)
            credit[key] = min(3.0, credit[key] * 0.80 + surplus)
            if shortfall > 0.0:
                credit[key] *= 0.65
            elif surplus > 0.0:
                debt[key] = max(0.0, debt[key] - 0.75 * surplus)

    best_debt_context = max(context_keys, key=lambda key: debt[key], default="aggregate")
    max_context_debt = float(debt.get(best_debt_context, 0.0))
    open_context_count = float(sum(1 for value in debt.values() if value > 0.05))
    best_debt_gap = 0.0
    current = history[-1]
    if best_debt_context == "aggregate":
        best_debt_gap = max(0.0, accuracy_threshold - _final_accuracy(current))
    elif best_debt_context in current.context_accuracy:
        best_debt_gap = max(
            0.0,
            accuracy_threshold - float(current.context_accuracy[best_debt_context]),
        )

    return {
        "max_context_debt": round(max_context_debt, 4),
        "total_context_debt": round(sum(float(value) for value in debt.values()), 4),
        "max_context_credit": round(max(float(value) for value in credit.values()), 4),
        "open_context_count": round(open_context_count, 4),
        "best_debt_context": best_debt_context,
        "best_debt_gap": round(best_debt_gap, 4),
    }


@dataclass
class LaminatedRunResult:
    summaries: List[SliceSummary] = field(default_factory=list)
    final_signal: RegulatorySignal | None = None
    final_decision: SettlementDecision = SettlementDecision.CONTINUE
    final_cycle_budget: int = 0


@dataclass
class PortfolioCandidateResult:
    label: str
    summary: SliceSummary
    score: float
    snapshot: dict[str, object]


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
        self.failed_hygiene_window = 3

    def regulate(self, history: List[SliceSummary]) -> RegulatorySignal:
        if not history:
            return RegulatorySignal()

        current = history[-1]
        previous = history[-2] if len(history) >= 2 else None
        debt_summary = _context_debt_summary(
            history,
            accuracy_threshold=self.accuracy_threshold,
        )

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
        weak_context_gap: float = float(debt_summary.get("best_debt_gap", 0.0))
        best_debt_context = debt_summary.get("best_debt_context")
        if (
            self.accuracy_threshold > 0.0
            and isinstance(best_debt_context, str)
            and best_debt_context.startswith("context_")
            and weak_context_gap > 0.0
        ):
            suffix = best_debt_context.removeprefix("context_")
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

        floor_accuracy = _floor_accuracy(current)
        accuracy_gap = (
            max(0.0, self.accuracy_threshold - floor_accuracy)
            if self.accuracy_threshold > 0.0
            else 0.0
        )
        aggregate_accuracy_gap = (
            max(0.0, self.accuracy_threshold - _final_accuracy(current))
            if self.accuracy_threshold > 0.0
            else 0.0
        )
        bias_updates: dict[str, float] = {
            "guidance_weight": round(float(current.guidance_alignment or 0.0), 4),
            "coherence_delta": round(current.coherence_delta, 4),
            "max_context_debt": float(debt_summary.get("max_context_debt", 0.0)),
            "total_context_debt": float(debt_summary.get("total_context_debt", 0.0)),
            "open_context_count": float(debt_summary.get("open_context_count", 0.0)),
        }
        if accuracy_gap > 0.0:
            bias_updates["accuracy_gap"] = round(accuracy_gap, 4)
        if aggregate_accuracy_gap > 0.0:
            bias_updates["aggregate_accuracy_gap"] = round(aggregate_accuracy_gap, 4)
        if weak_context_bit is not None and weak_context_gap > 0.0:
            bias_updates["weak_context_bit"] = weak_context_bit
            bias_updates["weak_context_gap"] = round(weak_context_gap, 4)

        growth_authorization = self._select_growth_authorization(history)
        reset_flags: dict[str, float] = {}
        reframe_flags: dict[str, float] = {}
        asymmetry = _context_asymmetry(current)
        if float(debt_summary.get("max_context_debt", 0.0)) >= 1.0:
            context_pressure = "high"
        if self._should_reframe_for_persistent_asymmetry(history):
            carryover_filter_mode = "drop"
            context_pressure = "high"
            growth_authorization = "hold"
            next_slice_budget = min(next_slice_budget, current.slice_budget)
            reset_flags["episodic"] = 1.0
            reframe_flags["context_differentiation"] = 1.0
            bias_updates["context_accuracy_spread"] = round(asymmetry["spread"], 4)
            bias_updates["context_debt_reframe"] = 1.0
            stop_reason = "persistent_context_asymmetry"
        elif self._should_reframe_for_failed_hygiene(history):
            carryover_filter_mode = "drop"
            context_pressure = "high"
            growth_authorization = "hold"
            next_slice_budget = min(next_slice_budget, current.slice_budget)
            reset_flags["episodic"] = 1.0
            reframe_flags["context_differentiation"] = 1.0
            bias_updates["context_debt_reframe"] = 1.0
            bias_updates["failed_hygiene_reframe"] = 1.0
            stop_reason = "failed_hygiene_recovery"

        return RegulatorySignal(
            next_slice_budget=next_slice_budget,
            carryover_filter_mode=carryover_filter_mode,
            context_pressure=context_pressure,
            decision_hint=decision_hint,
            growth_authorization=growth_authorization,
            gating_updates={
                "conflict_penalty": round(current.conflict_level, 4),
                "uncertainty_gate": round(current.mean_uncertainty, 4),
                "context_debt_pressure": min(
                    1.0,
                    float(debt_summary.get("max_context_debt", 0.0)),
                ),
            },
            bias_updates=bias_updates,
            reset_flags=reset_flags,
            reframe_flags=reframe_flags,
            stop_reason=stop_reason,
        )

    def _should_settle(self, history: List[SliceSummary]) -> bool:
        if self.accuracy_threshold > 0.0 and history:
            # Explicit accuracy target: aggregate-only success can mask dead
            # contexts, so the floor must pass before the aggregate can settle.
            window = history[-2:] if len(history) >= 2 else history[-1:]

            def _meets_threshold(s: SliceSummary) -> bool:
                return (
                    _floor_accuracy(s) >= self.accuracy_threshold
                    and _final_accuracy(s) >= self.accuracy_threshold
                )

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

    def _should_reframe_for_persistent_asymmetry(self, history: List[SliceSummary]) -> bool:
        if len(history) < 2:
            return False
        debt_summary = _context_debt_summary(
            history,
            accuracy_threshold=self.accuracy_threshold,
        )
        if float(debt_summary.get("max_context_debt", 0.0)) < 1.0:
            return False
        recent = history[-2:]
        if not all(_context_asymmetry(item)["collapsed"] > 0.5 for item in recent):
            return False
        if self.accuracy_threshold > 0.0 and all(
            _floor_accuracy(item) >= self.accuracy_threshold for item in recent
        ):
            return False
        prior = history[-3:-1]
        if len(prior) >= 2 and all(_context_asymmetry(item)["collapsed"] > 0.5 for item in prior):
            return False
        return True

    def _should_reframe_for_failed_hygiene(self, history: List[SliceSummary]) -> bool:
        if len(history) < self.failed_hygiene_window:
            return False
        debt_summary = _context_debt_summary(
            history,
            accuracy_threshold=self.accuracy_threshold,
        )
        if float(debt_summary.get("max_context_debt", 0.0)) < 1.5:
            return False
        recent = history[-self.failed_hygiene_window :]
        drop_slices = sum(
            1
            for item in recent
            if str(item.metadata.get("applied_carryover_filter_mode", "")) == "drop"
        )
        if drop_slices < 2:
            return False
        floors = [_floor_accuracy(item) for item in recent]
        if floors[-1] > floors[0] + 0.05:
            return False
        if self.accuracy_threshold > 0.0 and floors[-1] >= self.accuracy_threshold:
            return False

        hardened_slices = 0
        for item in recent:
            ambiguity = float(item.metadata.get("mean_provisional_context_ambiguity", 0.0))
            margin = float(item.metadata.get("mean_transform_commitment_margin", 0.0))
            if ambiguity <= 0.08 and margin >= 0.55:
                hardened_slices += 1
        if hardened_slices < 2:
            return False

        if any(float(item.metadata.get("context_debt_reframe", 0.0)) > 0.0 for item in recent[:-1]):
            return False
        return True

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

    def _select_growth_authorization(self, history: List[SliceSummary]) -> str | None:
        """Return a compact slow-layer answer to fast-layer growth requests."""
        if not history:
            return None
        current = history[-1]
        growth_request = dict(current.metadata.get("growth_request", {}))
        pressure = float(growth_request.get("max_pressure", 0.0))
        readiness = float(growth_request.get("max_readiness", 0.0))
        requesting_nodes = float(growth_request.get("requesting_nodes", 0.0))
        active_growth_nodes = float(growth_request.get("active_growth_nodes", 0.0))
        pending_proposals = float(growth_request.get("pending_proposals", 0.0))

        current_acc = _floor_accuracy(current)
        if self._should_initiate_growth(history):
            if (
                self.accuracy_threshold <= 0.0
                or current_acc < self.accuracy_threshold
            ):
                return "initiate"

        if requesting_nodes <= 0.0 and active_growth_nodes <= 0.0 and pending_proposals <= 0.0:
            return None
        if (
            pressure >= 0.55
            and readiness >= 0.45
            and (
                self.accuracy_threshold <= 0.0
                or current_acc < self.accuracy_threshold
            )
        ):
            return "authorize"
        if (
            (active_growth_nodes > 0.0 or pending_proposals > 0.0)
            and pressure <= 0.30
            and readiness <= 0.35
        ):
            return "hold"
        if self.accuracy_threshold > 0.0 and current_acc >= self.accuracy_threshold:
            return "hold"
        if current.conflict_level >= self.high_conflict_threshold and current.mean_uncertainty >= self.high_uncertainty_threshold:
            return "hold"
        if pressure >= 0.45 and readiness >= 0.40:
            return "authorize"
        return None

    def _should_initiate_growth(self, history: List[SliceSummary]) -> bool:
        if not history:
            return False
        current = history[-1]
        if current.mode_used.startswith("growth-"):
            return False
        if self.accuracy_threshold > 0.0 and _floor_accuracy(current) >= self.accuracy_threshold:
            return False

        growth_request = dict(current.metadata.get("growth_request", {}))
        if (
            float(growth_request.get("active_growth_nodes", 0.0)) > 0.0
            or float(growth_request.get("pending_proposals", 0.0)) > 0.0
        ):
            return False

        window_size = max(3, self.stall_slices_before_growth + 1)
        recent = history[-window_size:]
        if len(recent) < window_size:
            return False

        floors = [_floor_accuracy(item) for item in recent]
        if floors[-1] > floors[0] + 0.05:
            return False

        debt_summary = _context_debt_summary(
            history,
            accuracy_threshold=self.accuracy_threshold,
        )
        if (
            float(debt_summary.get("max_context_debt", 0.0)) < 1.0
            and (
                self.accuracy_threshold <= 0.0
                or max(0.0, self.accuracy_threshold - _final_accuracy(current)) < 0.15
            )
        ):
            return False

        pressure = float(growth_request.get("max_pressure", 0.0))
        readiness = float(growth_request.get("max_readiness", 0.0))
        if pressure >= 0.45 and readiness >= 0.40:
            return False

        if self._should_reframe_for_failed_hygiene(history):
            return True

        hardened_slices = 0
        for item in recent:
            ambiguity = float(item.metadata.get("mean_provisional_context_ambiguity", 0.0))
            margin = float(item.metadata.get("mean_transform_commitment_margin", 0.0))
            if ambiguity <= 0.08 and margin >= 0.55:
                hardened_slices += 1
        if hardened_slices >= 2:
            return True

        return (
            self._recently_flat(recent[-2:])
            and current.mean_uncertainty >= max(0.4, self.high_uncertainty_threshold - 0.1)
            and current.conflict_level >= max(0.3, self.high_conflict_threshold - 0.15)
        )

    def _is_input_tapering(self, summary: SliceSummary) -> bool:
        return (
            summary.cycles_used > 0
            and summary.examples_seen > 0
            and summary.examples_seen <= max(1, summary.cycles_used // 2)
        )


class GradientSliceRegulator(HeuristicSliceRegulator):
    """Continuous-control regulator used by the newer laminated path."""

    def __init__(
        self,
        *,
        portfolio_trigger: float = 0.68,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.portfolio_trigger = float(portfolio_trigger)

    def regulate(self, history: List[SliceSummary]) -> RegulatorySignal:
        if not history:
            return RegulatorySignal()

        current = history[-1]
        previous = history[-2] if len(history) >= 2 else None
        debt_summary = _context_debt_summary(
            history,
            accuracy_threshold=self.accuracy_threshold,
        )
        asymmetry = _context_asymmetry(current)
        floor_accuracy = _floor_accuracy(current)
        final_accuracy = _final_accuracy(current)
        threshold = self.accuracy_threshold if self.accuracy_threshold > 0.0 else 1.0
        floor_gap = _clamp01(max(0.0, threshold - floor_accuracy) / max(threshold, 1e-6))
        final_gap = _clamp01(max(0.0, threshold - final_accuracy) / max(threshold, 1e-6))
        debt_mass = _clamp01(float(debt_summary.get("max_context_debt", 0.0)) / 3.0)
        debt_total = _clamp01(float(debt_summary.get("total_context_debt", 0.0)) / 4.0)
        open_context_mass = _clamp01(float(debt_summary.get("open_context_count", 0.0)) / 2.0)
        spread = _clamp01(asymmetry["spread"])
        uncertainty = _clamp01(current.mean_uncertainty)
        conflict = _clamp01(current.conflict_level)
        ambiguity = _clamp01(current.ambiguity_level)
        provisional_ambiguity = _clamp01(
            float(current.metadata.get("mean_provisional_context_ambiguity", ambiguity)),
        )
        commitment_hardness = _clamp01(
            float(current.metadata.get("mean_transform_commitment_margin", 1.0 - provisional_ambiguity)),
        )
        hidden_ambiguity = _clamp01(
            float(current.metadata.get("hidden_packet_mean_provisional_context_ambiguity", provisional_ambiguity)),
        )
        growth_request = dict(current.metadata.get("growth_request", {}))
        growth_pressure = _clamp01(float(growth_request.get("max_pressure", 0.0)))
        growth_readiness = _clamp01(float(growth_request.get("max_readiness", 0.0)))
        active_growth = _clamp01(float(growth_request.get("active_growth_nodes", 0.0)) / 3.0)
        pending_growth = _clamp01(float(growth_request.get("pending_proposals", 0.0)) / 3.0)
        exact_matches = float(current.cost_summary.get("exact_matches", 0.0))
        bit_accuracy_per_cost = _clamp01(float(current.cost_summary.get("bit_accuracy_per_cost", 0.0)))

        floor_delta = 0.0 if previous is None else floor_accuracy - _floor_accuracy(previous)
        final_delta = 0.0 if previous is None else final_accuracy - _final_accuracy(previous)
        coherence_velocity = float(current.coherence_delta)
        progress_velocity = _clamp01(0.5 + 4.0 * floor_delta + 2.0 * final_delta + 3.0 * coherence_velocity)
        stall = _clamp01(1.0 - progress_velocity)

        recent = history[-max(3, self.failed_hygiene_window) :]
        drop_recent = sum(
            1
            for item in recent
            if str(item.metadata.get("applied_carryover_filter_mode", "")) == "drop"
        )
        failed_hygiene_persistence = _clamp01(drop_recent / max(len(recent), 1))
        hardened_commitment = _clamp01(max(0.0, commitment_hardness - provisional_ambiguity))
        growth_struggle = _clamp01(
            max(
                debt_mass,
                0.7 * floor_gap + 0.3 * final_gap,
            )
            * max(0.35, stall)
        )
        slice_efficiency = _clamp01(
            max(
                0.25 * bit_accuracy_per_cost,
                0.10 * exact_matches,
                0.55 * final_accuracy + 0.45 * floor_accuracy,
            )
        )

        pressure_level = _clamp01(
            0.38 * debt_mass
            + 0.18 * debt_total
            + 0.16 * spread
            + 0.14 * floor_gap
            + 0.08 * uncertainty
            + 0.06 * conflict
        )
        hygiene_level = _clamp01(
            0.40 * conflict
            + 0.22 * failed_hygiene_persistence
            + 0.18 * spread
            + 0.12 * debt_mass
            + 0.08 * hardened_commitment
        )
        growth_drive = _clamp01(
            0.34 * growth_pressure
            + 0.20 * growth_readiness
            + 0.20 * growth_struggle
            + 0.14 * failed_hygiene_persistence
            + 0.12 * open_context_mass
        )
        portfolio_drive = _clamp01(
            0.28 * debt_mass
            + 0.22 * failed_hygiene_persistence
            + 0.18 * stall
            + 0.16 * spread
            + 0.16 * hardened_commitment
        )
        settlement_confidence = _clamp01(
            0.50 * min(floor_accuracy / max(threshold, 1e-6), 1.0)
            + 0.35 * min(final_accuracy / max(threshold, 1e-6), 1.0)
            + 0.10 * (1.0 - conflict)
            + 0.05 * (1.0 - ambiguity)
        )

        budget_scale = 0.80 + 0.65 * stall + 0.35 * pressure_level + 0.30 * portfolio_drive - 0.40 * settlement_confidence
        requested_budget = max(1.0, current.slice_budget * budget_scale)
        max_growth_budget = max(12, current.slice_budget + max(2, current.slice_budget // 2))
        budget_target = float(
            _clamp_budget(
                round(min(requested_budget, max_growth_budget)),
                maximum=max_growth_budget,
            )
        )
        next_slice_budget = _clamp_budget(round(budget_target))

        carryover_filter_mode = self._compat_hygiene_mode(hygiene_level)
        context_pressure = self._compat_pressure_mode(pressure_level)
        growth_authorization = self._compat_growth_authorization(
            growth_drive=growth_drive,
            growth_pressure=growth_pressure,
            growth_readiness=growth_readiness,
            active_growth=active_growth,
            pending_growth=pending_growth,
            settlement_confidence=settlement_confidence,
        )

        decision_hint = SettlementDecision.CONTINUE
        stop_reason = ""
        if self._should_settle(history):
            decision_hint = SettlementDecision.SETTLE
            stop_reason = "criteria_threshold_sustained"
        elif self._should_escalate(history):
            decision_hint = SettlementDecision.ESCALATE
            stop_reason = "low_gradient_under_high_conflict"

        bias_updates: dict[str, float] = {
            "guidance_weight": round(float(current.guidance_alignment or 0.0), 4),
            "coherence_delta": round(current.coherence_delta, 4),
            "max_context_debt": float(debt_summary.get("max_context_debt", 0.0)),
            "total_context_debt": float(debt_summary.get("total_context_debt", 0.0)),
            "open_context_count": float(debt_summary.get("open_context_count", 0.0)),
            "floor_gap": round(floor_gap, 4),
            "aggregate_gap": round(final_gap, 4),
            "context_accuracy_spread": round(spread, 4),
            "commitment_hardness": round(commitment_hardness, 4),
            "provisional_ambiguity": round(provisional_ambiguity, 4),
            "progress_velocity": round(progress_velocity, 4),
            "failed_hygiene_persistence": round(failed_hygiene_persistence, 4),
            "slice_efficiency": round(slice_efficiency, 4),
        }

        best_debt_context = debt_summary.get("best_debt_context")
        weak_context_gap = float(debt_summary.get("best_debt_gap", 0.0))
        if (
            self.accuracy_threshold > 0.0
            and isinstance(best_debt_context, str)
            and best_debt_context.startswith("context_")
            and weak_context_gap > 0.0
        ):
            suffix = best_debt_context.removeprefix("context_")
            try:
                bias_updates["weak_context_bit"] = float(suffix)
                bias_updates["weak_context_gap"] = round(weak_context_gap, 4)
            except ValueError:
                pass

        reset_flags: dict[str, float] = {}
        reframe_flags: dict[str, float] = {}
        if self._should_reframe_for_persistent_asymmetry(history):
            carryover_filter_mode = "drop"
            context_pressure = "high"
            hygiene_level = max(hygiene_level, 0.9)
            pressure_level = max(pressure_level, 0.9)
            growth_authorization = "hold"
            next_slice_budget = min(next_slice_budget, current.slice_budget)
            reset_flags["episodic"] = 1.0
            reframe_flags["context_differentiation"] = 1.0
            bias_updates["context_debt_reframe"] = 1.0
            stop_reason = "persistent_context_asymmetry"
        elif self._should_reframe_for_failed_hygiene(history):
            carryover_filter_mode = "drop"
            context_pressure = "high"
            hygiene_level = max(hygiene_level, 0.95)
            pressure_level = max(pressure_level, 0.85)
            growth_authorization = "hold"
            next_slice_budget = min(next_slice_budget, current.slice_budget)
            reset_flags["episodic"] = 1.0
            reframe_flags["context_differentiation"] = 1.0
            bias_updates["context_debt_reframe"] = 1.0
            bias_updates["failed_hygiene_reframe"] = 1.0
            stop_reason = "failed_hygiene_recovery"

        execution_plan = self._build_execution_plan(
            current_budget=current.slice_budget,
            budget_target=budget_target,
            pressure_level=pressure_level,
            hygiene_level=hygiene_level,
            portfolio_drive=portfolio_drive,
            provisional_ambiguity=provisional_ambiguity,
            commitment_hardness=commitment_hardness,
        )
        if decision_hint != SettlementDecision.CONTINUE:
            portfolio_drive = 0.0

        metadata = {
            "regulator_mode": "gradient",
            "best_debt_context": best_debt_context,
            "budget_target": round(budget_target, 4),
            "pressure_level": round(pressure_level, 4),
            "hygiene_level": round(hygiene_level, 4),
            "growth_drive": round(growth_drive, 4),
            "portfolio_drive": round(portfolio_drive, 4),
            "settlement_confidence": round(settlement_confidence, 4),
            "progress_velocity": round(progress_velocity, 4),
            "failed_hygiene_persistence": round(failed_hygiene_persistence, 4),
            "commitment_hardness": round(commitment_hardness, 4),
            "provisional_ambiguity": round(provisional_ambiguity, 4),
            "hidden_provisional_ambiguity": round(hidden_ambiguity, 4),
        }

        return RegulatorySignal(
            next_slice_budget=next_slice_budget,
            budget_target=budget_target,
            pressure_level=pressure_level,
            hygiene_level=hygiene_level,
            growth_drive=growth_drive,
            portfolio_drive=portfolio_drive,
            settlement_confidence=settlement_confidence,
            carryover_filter_mode=carryover_filter_mode,
            context_pressure=context_pressure,
            decision_hint=decision_hint,
            growth_authorization=growth_authorization,
            execution_plan=execution_plan,
            gating_updates={
                "conflict_penalty": round(conflict, 4),
                "uncertainty_gate": round(uncertainty, 4),
                "context_debt_pressure": round(debt_mass, 4),
            },
            bias_updates=bias_updates,
            reset_flags=reset_flags,
            reframe_flags=reframe_flags,
            stop_reason=stop_reason,
            metadata=metadata,
        )

    def _compat_hygiene_mode(self, hygiene_level: float) -> str:
        if hygiene_level >= 0.72:
            return "drop"
        if hygiene_level >= 0.30:
            return "soften"
        return "keep"

    def _compat_pressure_mode(self, pressure_level: float) -> str:
        if pressure_level >= 0.72:
            return "high"
        if pressure_level >= 0.38:
            return "medium"
        return "low"

    def _compat_growth_authorization(
        self,
        *,
        growth_drive: float,
        growth_pressure: float,
        growth_readiness: float,
        active_growth: float,
        pending_growth: float,
        settlement_confidence: float,
    ) -> str | None:
        if settlement_confidence >= 0.98:
            return "hold"
        if active_growth > 0.0 or pending_growth > 0.0:
            if growth_drive <= 0.18:
                return "hold"
            return "authorize"
        if growth_drive >= 0.70 and growth_pressure <= 0.25:
            return "initiate"
        if growth_drive >= 0.48 and (growth_pressure >= 0.12 or growth_readiness >= 0.35):
            return "authorize"
        return None

    def _build_execution_plan(
        self,
        *,
        current_budget: int,
        budget_target: float,
        pressure_level: float,
        hygiene_level: float,
        portfolio_drive: float,
        provisional_ambiguity: float,
        commitment_hardness: float,
    ) -> SliceExecutionPlan:
        target = max(1, int(round(budget_target)))
        # Keep adaptive slices bounded so a hard case does not silently turn
        # back into a monolithic long run. Rescue should happen through more
        # slices or a short portfolio, not by letting one slice balloon.
        target = min(target, max(12, current_budget * 2))
        initial_budget = _clamp_budget(
            max(1, round(target * (0.45 + 0.20 * (1.0 - hygiene_level)))),
            maximum=max(target, current_budget * 2, 1),
        )
        extend_step = _clamp_budget(
            max(1, round(target * (0.20 + 0.15 * pressure_level))),
            maximum=max(4, target // 2, current_budget, 1),
        )
        soft_cap = _clamp_budget(
            max(initial_budget, round(target * (1.0 + 0.15 * portfolio_drive))),
            maximum=max(initial_budget, target + extend_step * 2, 1),
        )
        hard_cap = _clamp_budget(
            max(
                soft_cap,
                round(
                    min(
                        target * (1.25 + 0.35 * max(0.0, commitment_hardness - provisional_ambiguity)),
                        max(target + extend_step * 3, current_budget * 3, 12),
                    )
                ),
            ),
            maximum=max(soft_cap, target + extend_step * 3, current_budget * 3, 12),
        )
        patience = 1 + int(max(0.0, provisional_ambiguity - commitment_hardness) >= 0.10)
        return SliceExecutionPlan(
            initial_budget=initial_budget,
            extend_step=extend_step,
            soft_cap=soft_cap,
            hard_cap=hard_cap,
            early_stop_patience=patience,
            metadata={
                "target_budget": target,
                "pressure_level": round(pressure_level, 4),
                "portfolio_drive": round(portfolio_drive, 4),
            },
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
    # Warm-start priors when no memory exists for a mode
    _MODE_PRIORS: Dict[str, float] = {
        "hold": 0.04,
        "authorize": 0.08,
        "initiate": 0.09,
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
        self._last_intervention_summary: Dict[str, float | str | None] = {}

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
            self._last_intervention_summary = _intervention_summary(
                observed_delta=observed_delta,
                predicted_delta=predicted_delta,
            )

        # --- Delegate settle/escalate/GCO/bias/budget to heuristic layer ---
        signal = self._heuristic.regulate(history)

        # On terminal decisions, clear pending state and return unchanged
        if signal.decision_hint in (SettlementDecision.SETTLE, SettlementDecision.ESCALATE):
            self._pending_prediction = None
            self._prev_min_ctx_acc = None
            self._prev_features = None
            return signal

        # --- Predict: estimate delta for each candidate authorization ---
        debt_summary = _context_debt_summary(
            history,
            accuracy_threshold=self._heuristic.accuracy_threshold,
        )
        current_features = self._extract_features(current, debt_summary=debt_summary)
        current_authorization = self._current_authorization(current, signal)
        candidates = self._candidate_authorizations(current, signal)
        predictions = {
            authorization: self._predict_delta(authorization, current_features)
            for authorization in candidates
        }

        best_authorization = max(predictions, key=lambda authorization: predictions[authorization])

        # --- Store pending prediction for the next score step ---
        self._pending_prediction = (best_authorization, predictions[best_authorization])
        self._prev_min_ctx_acc = current_min
        self._prev_features = current_features

        # --- Select: emit authorization change only if improvement margin is meaningful ---
        growth_authorization = signal.growth_authorization
        if growth_authorization == "initiate":
            prediction_meta: Dict[str, object] = {
                f"predicted_delta_{authorization}": round(value, 4)
                for authorization, value in predictions.items()
            }
            prediction_meta["memory_size"] = float(len(self._experiences))
            for key, value in self._last_intervention_summary.items():
                if value is not None:
                    prediction_meta[key] = value
            return RegulatorySignal(
                next_slice_budget=signal.next_slice_budget,
                context_pressure=signal.context_pressure,
                decision_hint=signal.decision_hint,
                capability_mode=signal.capability_mode,
                growth_authorization=growth_authorization,
                gating_updates=signal.gating_updates,
                bias_updates=signal.bias_updates,
                reset_flags=signal.reset_flags,
                reframe_flags=signal.reframe_flags,
                stop_reason=signal.stop_reason,
                metadata=prediction_meta,
            )
        current_pred = predictions.get(
            current_authorization,
            self._MODE_PRIORS.get(current_authorization, 0.0),
        )
        if (
            best_authorization != current_authorization
            and predictions[best_authorization] > current_pred + self.switch_margin
        ):
            growth_authorization = best_authorization

        prediction_meta: Dict[str, object] = {
            f"predicted_delta_{authorization}": round(value, 4)
            for authorization, value in predictions.items()
        }
        prediction_meta["memory_size"] = float(len(self._experiences))
        for key, value in self._last_intervention_summary.items():
            if value is not None:
                prediction_meta[key] = value

        return RegulatorySignal(
            next_slice_budget=signal.next_slice_budget,
            carryover_filter_mode=signal.carryover_filter_mode,
            context_pressure=signal.context_pressure,
            decision_hint=signal.decision_hint,
            capability_mode=signal.capability_mode,
            growth_authorization=growth_authorization,
            gating_updates=signal.gating_updates,
            bias_updates=signal.bias_updates,
            reset_flags=signal.reset_flags,
            reframe_flags=signal.reframe_flags,
            stop_reason=signal.stop_reason,
            metadata=prediction_meta,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _candidate_authorizations(
        self,
        current: SliceSummary,
        signal: RegulatorySignal,
    ) -> List[str]:
        growth_request = dict(current.metadata.get("growth_request", {}))
        has_request = any(
            float(growth_request.get(key, 0.0)) > 0.0
            for key in ("requesting_nodes", "active_growth_nodes", "pending_proposals")
        )
        current_authorization = self._current_authorization(current, signal)
        if not has_request:
            return [current_authorization]

        candidates = [current_authorization]
        for option in ("hold", "authorize", "initiate"):
            if option not in candidates:
                candidates.append(option)
        return candidates

    def _current_authorization(
        self,
        current: SliceSummary,
        signal: RegulatorySignal,
    ) -> str:
        if signal.growth_authorization in {"authorize", "hold", "initiate"}:
            return str(signal.growth_authorization)
        growth_request = dict(current.metadata.get("growth_request", {}))
        if growth_request.get("authorization") in {"authorize", "hold", "initiate"}:
            return str(growth_request["authorization"])
        return "hold"

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

    def _extract_features(
        self,
        summary: SliceSummary,
        *,
        debt_summary: Dict[str, float | str | None] | None = None,
    ) -> Dict[str, float]:
        growth_request = dict(summary.metadata.get("growth_request", {}))
        debt_summary = debt_summary or {}
        if summary.context_accuracy:
            context_values = [float(value) for value in summary.context_accuracy.values()]
            best_ctx_acc = max(context_values)
            worst_ctx_acc = min(context_values)
        else:
            best_ctx_acc = _final_accuracy(summary)
            worst_ctx_acc = _final_accuracy(summary)
        return {
            "min_ctx_acc": self._min_ctx_acc(summary),
            "best_ctx_acc": best_ctx_acc,
            "worst_ctx_acc": worst_ctx_acc,
            "context_accuracy_spread": max(0.0, best_ctx_acc - worst_ctx_acc),
            "max_context_debt": float(debt_summary.get("max_context_debt", 0.0)),
            "total_context_debt": float(debt_summary.get("total_context_debt", 0.0)),
            "open_context_count": float(debt_summary.get("open_context_count", 0.0)),
            "conflict": summary.conflict_level,
            "ambiguity": summary.ambiguity_level,
            "coherence_delta": summary.coherence_delta,
            "growth_request_pressure": float(growth_request.get("max_pressure", 0.0)),
            "growth_request_readiness": float(growth_request.get("max_readiness", 0.0)),
            "pending_growth_proposals": float(growth_request.get("pending_proposals", 0.0)),
            "active_growth_nodes": float(growth_request.get("active_growth_nodes", 0.0)),
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
        portfolio_threshold: float = 0.68,
    ) -> None:
        self.runner = runner
        self.regulator = regulator or HeuristicSliceRegulator()
        self.initial_cycle_budget = _clamp_budget(initial_cycle_budget)
        self.safety_limit = max(1, int(safety_limit))
        self.portfolio_threshold = float(portfolio_threshold)

    def run(self) -> LaminatedRunResult:
        history: List[SliceSummary] = []
        cycle_budget = self.initial_cycle_budget
        signal: RegulatorySignal | None = None
        decision = SettlementDecision.CONTINUE
        slice_id = 0

        while True:
            slice_id += 1
            execution_plan = self._execution_plan_for_slice(cycle_budget, signal)
            summary = self._execute_slice(
                history,
                slice_id=slice_id,
                cycle_budget=cycle_budget,
                execution_plan=execution_plan,
                signal=signal,
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
            cycle_budget = _clamp_budget(
                round(signal.budget_target)
                if signal is not None and signal.budget_target is not None
                else (signal.next_slice_budget or cycle_budget),
            )

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

    def _execution_plan_for_slice(
        self,
        cycle_budget: int,
        signal: RegulatorySignal | None,
    ) -> SliceExecutionPlan:
        if signal is not None and signal.execution_plan is not None:
            return signal.execution_plan
        return SliceExecutionPlan(
            initial_budget=max(1, min(4, cycle_budget)),
            extend_step=max(1, max(2, cycle_budget // 4)),
            soft_cap=cycle_budget,
            hard_cap=max(cycle_budget, cycle_budget + max(2, cycle_budget // 4)),
            early_stop_patience=1,
            metadata={"target_budget": cycle_budget, "source": "fallback"},
        )

    def _execute_slice(
        self,
        history: List[SliceSummary],
        *,
        slice_id: int,
        cycle_budget: int,
        execution_plan: SliceExecutionPlan,
        signal: RegulatorySignal | None,
    ) -> SliceSummary:
        if self._should_run_portfolio(history, signal):
            return self._run_rescue_portfolio(
                history,
                slice_id=slice_id,
                execution_plan=execution_plan,
                signal=signal,
            )
        if hasattr(self.runner, "run_slice_plan"):
            return self.runner.run_slice_plan(
                slice_id=slice_id,
                execution_plan=execution_plan,
                regulatory_signal=signal,
            )
        return self.runner.run_slice(
            slice_id=slice_id,
            cycle_budget=cycle_budget,
            regulatory_signal=signal,
        )

    def _should_run_portfolio(
        self,
        history: List[SliceSummary],
        signal: RegulatorySignal | None,
    ) -> bool:
        return bool(
            history
            and signal is not None
            and signal.portfolio_drive >= self.portfolio_threshold
            and hasattr(self.runner, "run_slice_plan")
            and hasattr(self.runner, "snapshot_fast_state")
            and hasattr(self.runner, "restore_fast_state")
        )

    def _run_rescue_portfolio(
        self,
        history: List[SliceSummary],
        *,
        slice_id: int,
        execution_plan: SliceExecutionPlan,
        signal: RegulatorySignal,
    ) -> SliceSummary:
        base_snapshot = self.runner.snapshot_fast_state()
        candidates: list[PortfolioCandidateResult] = []
        for label, plan in self._candidate_plans(execution_plan):
            self.runner.restore_fast_state(base_snapshot)
            summary = self.runner.run_slice_plan(
                slice_id=slice_id,
                execution_plan=plan,
                regulatory_signal=signal,
            )
            snapshot = self.runner.snapshot_fast_state()
            score = self._score_candidate(history, summary)
            candidates.append(
                PortfolioCandidateResult(
                    label=label,
                    summary=summary,
                    score=score,
                    snapshot=snapshot,
                )
            )
        winner = max(candidates, key=lambda item: item.score)
        self.runner.restore_fast_state(winner.snapshot)
        winner.summary.metadata["portfolio_active"] = True
        winner.summary.metadata["portfolio_drive"] = round(float(signal.portfolio_drive), 4)
        winner.summary.metadata["portfolio_candidate_scores"] = {
            item.label: round(item.score, 4) for item in candidates
        }
        winner.summary.metadata["portfolio_selected"] = winner.label
        winner.summary.metadata["portfolio_candidate_budgets"] = {
            item.label: int(item.summary.cycles_used) for item in candidates
        }
        return winner.summary

    def _candidate_plans(
        self,
        execution_plan: SliceExecutionPlan,
    ) -> list[tuple[str, SliceExecutionPlan]]:
        target = int(execution_plan.metadata.get("target_budget", execution_plan.soft_cap))
        budgets = [
            ("short", max(1, round(target * 0.75))),
            ("base", max(1, round(target * 1.0))),
            ("long", max(1, round(target * 1.5))),
        ]
        candidates: list[tuple[str, SliceExecutionPlan]] = []
        for label, budget in budgets:
            candidates.append(
                (
                    label,
                    SliceExecutionPlan(
                        initial_budget=max(1, min(execution_plan.initial_budget, budget)),
                        extend_step=max(1, execution_plan.extend_step),
                        soft_cap=max(1, budget),
                        hard_cap=max(budget, min(execution_plan.hard_cap, _clamp_budget(round(budget * 1.25)))),
                        early_stop_patience=execution_plan.early_stop_patience,
                        metadata={
                            **dict(execution_plan.metadata),
                            "portfolio_label": label,
                            "target_budget": budget,
                        },
                    ),
                )
            )
        return candidates

    def _score_candidate(
        self,
        history: List[SliceSummary],
        summary: SliceSummary,
    ) -> float:
        previous = history[-1] if history else None
        floor_accuracy = _floor_accuracy(summary)
        final_accuracy = _final_accuracy(summary)
        floor_delta = 0.0 if previous is None else floor_accuracy - _floor_accuracy(previous)
        final_delta = 0.0 if previous is None else final_accuracy - _final_accuracy(previous)
        previous_spread = 0.0 if previous is None else _context_asymmetry(previous)["spread"]
        spread_reduction = max(0.0, previous_spread - _context_asymmetry(summary)["spread"])
        ambiguity_retained = _clamp01(float(summary.metadata.get("mean_provisional_context_ambiguity", 0.0)))
        commitment_hardness = _clamp01(float(summary.metadata.get("mean_transform_commitment_margin", 1.0)))
        challengeability = max(0.0, ambiguity_retained - 0.35 * commitment_hardness)
        efficiency = _clamp01(float(summary.cost_summary.get("bit_accuracy_per_cost", 0.0)))
        return (
            4.0 * floor_accuracy
            + 2.5 * max(0.0, floor_delta)
            + 1.75 * spread_reduction
            + 1.25 * final_accuracy
            + 0.50 * challengeability
            + 0.15 * efficiency
            + 0.10 * max(0.0, final_delta)
        )
