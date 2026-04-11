"""Phase 3 lamination: slow-layer regulator as a full RealCoreEngine.

The REALSliceRegulator wraps a RealCoreEngine whose task is to select a
*policy* for the next fast-layer slice.  A policy is a compound action that
bundles four control dimensions into one named choice:

    capability_mode      — which substrate mode to run (visible / growth-visible / …)
    carryover_filter     — how aggressively to clear episodic memory between slices
    budget_multiplier    — scale factor for next-slice cycle budget
    context_pressure     — pressure label forwarded to the fast layer

One engine cycle corresponds to one slice.  The engine observes SliceSummary
features, selects a policy, and scores the outcome by the accuracy improvement
that follows.  The substrate accumulates support for (context, policy) pairs
that produce good outcomes via the same bistable slow-memory mechanism the
fast layer uses for routing.

Settle/escalate/GCO decisions and bias updates are still delegated to
HeuristicSliceRegulator so the learning layer only needs to own the four
"how to run the next slice" dimensions.

Temporal structure
------------------
Slice N completes → regulate([...summary_N]) is called →
  obs_adapter.update(summary_N, prev=summary_{N-1})   # delta_min_ctx_acc set
  engine.run_cycle(N)                                   # observe, predict, select, execute, score
  policy = NAMED_POLICIES[chosen_action]               # extract 4 dimensions
  heuristic.regulate() consulted for settle/escalate
  RegulatorySignal(capability_mode=..., carryover=..., budget=..., pressure=...) returned
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .engine import RealCoreEngine
from .episodic import EpisodicMemory
from .lamination import GradientSliceRegulator, _context_debt_summary
from .substrate import MemorySubstrate, SubstrateConfig
from .types import (
    ActionOutcome,
    CycleEntry,
    DimensionScores,
    GCOStatus,
    RegulatorySignal,
    SettlementDecision,
    SliceSummary,
)


# ---------------------------------------------------------------------------
# Named policies
# ---------------------------------------------------------------------------
# Each policy is
# (capability_mode, growth_authorization, carryover_filter, budget_multiplier, context_pressure).
# The REAL agent selects one policy per slice; the substrate learns which policy
# produces the best accuracy trajectory given the current observation context.

Policy = Tuple[str | None, str | None, str, float, str]

NAMED_POLICIES: Dict[str, Policy] = {
    # --- Visible family ---
    "visible_explore":       (None,             "hold",      "soften", 1.00, "medium"),
    "visible_push":          (None,             "hold",      "drop",   1.15, "high"),

    # --- Growth authorization family ---
    "growth_engage":         (None,             "authorize", "soften", 1.15, "high"),
    "growth_consolidate":    (None,             "hold",      "keep",   1.00, "low"),
    "growth_reset":          (None,             "hold",      "drop",   1.00, "high"),
    "growth_hold":           (None,             "authorize", "keep",   1.00, "medium"),

    # --- Latent family ---
    "latent_explore":        ("latent",         "hold",      "soften", 1.00, "medium"),
    "latent_push":           ("latent",         "hold",      "drop",   1.10, "high"),

    # --- Growth-latent family ---
    "growth_latent_engage":       ("latent",        "authorize", "soften", 1.15, "high"),
    "growth_latent_consolidate":  ("latent",        "hold",      "keep",   1.00, "low"),
}

# Which policies are available given the current mode.
_MODE_FAMILY: Dict[str, str] = {
    "visible":        "visible",
    "self-selected":  "visible",
    "growth-visible": "visible",
    "latent":         "latent",
    "growth-latent":  "latent",
}

_POLICIES_BY_FAMILY: Dict[str, List[str]] = {
    # From visible/self-selected: can stay or upgrade to growth.
    "visible": [
        "visible_explore",
        "visible_push",
        "growth_engage",
        "growth_consolidate",
        "growth_reset",
        "growth_hold",
    ],
    # From latent: can stay or upgrade to growth-latent.
    "latent": [
        "latent_explore",
        "latent_push",
        "growth_latent_engage",
        "growth_latent_consolidate",
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _min_ctx_acc(summary: SliceSummary) -> float:
    context_exact = summary.metadata.get("context_exact_accuracy")
    if isinstance(context_exact, dict) and context_exact:
        return min(float(value) for value in context_exact.values())
    if summary.context_accuracy:
        return min(summary.context_accuracy.values())
    return _final_accuracy(summary)


def _final_accuracy(summary: SliceSummary) -> float:
    return float(
        summary.metadata.get(
            "exact_match_rate",
            summary.metadata.get(
                "final_accuracy",
                summary.metadata.get("mean_bit_accuracy", 0.0),
            ),
        )
    )


def _floor_accuracy(summary: SliceSummary) -> float:
    context_exact = summary.metadata.get("context_exact_accuracy")
    if isinstance(context_exact, dict) and context_exact:
        return min(float(value) for value in context_exact.values())
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


def _intervention_status(observed_delta: float, *, epsilon: float = 0.01) -> str:
    if observed_delta > epsilon:
        return "improved"
    if observed_delta < -epsilon:
        return "worsened"
    return "flat"


def _carryover_rank(mode: str) -> int:
    return {"keep": 0, "soften": 1, "drop": 2}.get(str(mode), 0)


def _pressure_rank(mode: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(str(mode), 0)


# ---------------------------------------------------------------------------
# Observation adapter
# ---------------------------------------------------------------------------

class SliceSummaryObservationAdapter:
    """Converts the most recent SliceSummary to a flat Dict[str, float].

    Updated by REALSliceRegulator before each engine cycle.  Includes
    delta_min_ctx_acc so the engine can score accuracy improvement, not
    just absolute level.
    """

    def __init__(self) -> None:
        self._current: Dict[str, float] = {
            "min_ctx_acc": 0.0,
            "best_ctx_acc": 0.0,
            "worst_ctx_acc": 0.0,
            "context_accuracy_spread": 0.0,
            "asymmetric_context_collapse": 0.0,
            "delta_min_ctx_acc": 0.0,
            "conflict": 0.5,
            "ambiguity": 0.5,
            "coherence_delta": 0.0,
            "mean_uncertainty": 1.0,
            "floor_accuracy": 0.0,
            "max_context_debt": 0.0,
            "total_context_debt": 0.0,
            "open_context_count": 0.0,
            "max_context_credit": 0.0,
            "mode_is_growth": 0.0,
            "growth_request_pressure": 0.0,
            "growth_request_readiness": 0.0,
            "pending_growth_proposals": 0.0,
            "active_growth_nodes": 0.0,
            "growth_authorized": 0.0,
        }

    def update(
        self,
        summary: SliceSummary,
        *,
        prev_min_ctx_acc: float | None = None,
        context_debt_summary: Dict[str, float | str | None] | None = None,
    ) -> None:
        cur = _min_ctx_acc(summary)
        mean_acc = float(summary.metadata.get("mean_bit_accuracy", 0.0))
        final_acc = _final_accuracy(summary)
        floor_acc = _floor_accuracy(summary)
        context_debt_summary = context_debt_summary or {}
        delta = (cur - prev_min_ctx_acc) if prev_min_ctx_acc is not None else 0.0
        growth_request = dict(summary.metadata.get("growth_request", {}))
        context_exact = summary.metadata.get("context_exact_accuracy")
        if isinstance(context_exact, dict) and context_exact:
            context_values = [float(value) for value in context_exact.values()]
            best_ctx_acc = max(context_values)
            worst_ctx_acc = min(context_values)
        elif summary.context_accuracy:
            context_values = [float(value) for value in summary.context_accuracy.values()]
            best_ctx_acc = max(context_values)
            worst_ctx_acc = min(context_values)
        else:
            best_ctx_acc = mean_acc
            worst_ctx_acc = mean_acc
        context_accuracy_spread = max(0.0, best_ctx_acc - worst_ctx_acc)
        asymmetric_context_collapse = 1.0 if (
            best_ctx_acc >= 0.75
            and worst_ctx_acc <= 0.25
            and context_accuracy_spread >= 0.45
        ) else 0.0
        self._current = {
            "min_ctx_acc": round(cur, 4),
            "best_ctx_acc": round(best_ctx_acc, 4),
            "worst_ctx_acc": round(worst_ctx_acc, 4),
            "context_accuracy_spread": round(context_accuracy_spread, 4),
            "asymmetric_context_collapse": asymmetric_context_collapse,
            "mean_bit_accuracy": round(mean_acc, 4),
            "final_accuracy": round(final_acc, 4),
            "floor_accuracy": round(floor_acc, 4),
            "max_context_debt": round(float(context_debt_summary.get("max_context_debt", 0.0)), 4),
            "total_context_debt": round(float(context_debt_summary.get("total_context_debt", 0.0)), 4),
            "open_context_count": round(float(context_debt_summary.get("open_context_count", 0.0)), 4),
            "max_context_credit": round(float(context_debt_summary.get("max_context_credit", 0.0)), 4),
            "delta_min_ctx_acc": round(delta, 4),
            "conflict": round(summary.conflict_level, 4),
            "ambiguity": round(summary.ambiguity_level, 4),
            "coherence_delta": round(summary.coherence_delta, 4),
            "mean_uncertainty": round(summary.mean_uncertainty, 4),
            "mode_is_growth": 1.0 if summary.mode_used.startswith("growth-") else 0.0,
            "growth_request_pressure": round(float(growth_request.get("max_pressure", 0.0)), 4),
            "growth_request_readiness": round(float(growth_request.get("max_readiness", 0.0)), 4),
            "pending_growth_proposals": round(
                min(1.0, float(growth_request.get("pending_proposals", 0.0)) / 3.0),
                4,
            ),
            "active_growth_nodes": round(
                min(1.0, float(growth_request.get("active_growth_nodes", 0.0)) / 3.0),
                4,
            ),
            "growth_authorized": 1.0
            if str(growth_request.get("authorization", "auto")) in {"authorize", "initiate"}
            else 0.0,
        }

    def observe(self, cycle: int) -> Dict[str, float]:  # noqa: ARG002
        return dict(self._current)


# ---------------------------------------------------------------------------
# Action backend
# ---------------------------------------------------------------------------

class PolicySelectionActionBackend:
    """Action backend whose actions are named policy choices.

    Each policy bundles capability_mode + carryover_filter + budget_multiplier
    + context_pressure into a single named action.  Available policies are
    filtered to the active scenario family (visible or latent) so the engine
    never selects a cross-family mode.

    Executing an action records the chosen policy; the actual outcome is
    reflected in the next engine cycle's observation.
    """

    def __init__(self) -> None:
        self._current_mode: str = "visible"
        self._last_policy: str = "visible_explore"

    def set_current_mode(self, mode: str) -> None:
        self._current_mode = mode

    @property
    def last_policy(self) -> str:
        return self._last_policy

    @property
    def last_chosen(self) -> Policy:
        return NAMED_POLICIES.get(
            self._last_policy,
            NAMED_POLICIES["visible_explore"],
        )

    def available_actions(self, history_size: int) -> List[str]:  # noqa: ARG002
        family = _MODE_FAMILY.get(self._current_mode, "visible")
        return [f"policy:{name}" for name in _POLICIES_BY_FAMILY[family]]

    def execute(self, action: str) -> ActionOutcome:
        name = action.removeprefix("policy:")
        if name not in NAMED_POLICIES:
            name = "visible_explore"
        self._last_policy = name
        policy = NAMED_POLICIES[name]
        return ActionOutcome(
            success=True,
            result={
                "policy": name,
                "capability_mode": policy[0],
                "growth_authorization": policy[1],
                "carryover_filter": policy[2],
                "budget_multiplier": policy[3],
                "context_pressure": policy[4],
            },
            cost_secs=0.001,
        )


# ---------------------------------------------------------------------------
# Coherence model
# ---------------------------------------------------------------------------

_DIMENSION_NAMES: Tuple[str, ...] = (
    "accuracy_level",
    "accuracy_progress",
    "policy_efficiency",
    "context_balance",
    "convergence",
    "stability",
)

_DIMENSION_WEIGHTS: Dict[str, float] = {
    "accuracy_level":    0.35,
    "accuracy_progress": 0.30,
    "policy_efficiency": 0.05,
    "context_balance":   0.15,
    "convergence":       0.10,
    "stability":         0.05,
}


class SliceAccuracyCoherenceModel:
    """Coherence model that scores based on accuracy trajectory.

    Dimensions
    ----------
    accuracy_level    : min_ctx_acc / threshold (how close to goal)
    accuracy_progress : whether accuracy is improving this cycle
    policy_efficiency : slight penalty for high-cost policies (growth + drop)
    context_balance   : low conflict → balanced contexts
    convergence       : low ambiguity → converging routing
    stability         : low oscillation in delta across cycles
    """

    dimension_names = _DIMENSION_NAMES

    def __init__(self, *, accuracy_threshold: float = 0.0) -> None:
        self.accuracy_threshold = accuracy_threshold

    def score(self, state_after: Dict[str, float], history: List[CycleEntry]) -> DimensionScores:
        min_acc = float(state_after.get("min_ctx_acc", 0.0))
        delta = float(state_after.get("delta_min_ctx_acc", 0.0))
        conflict = float(state_after.get("conflict", 0.5))
        ambiguity = float(state_after.get("ambiguity", 0.5))
        context_accuracy_spread = float(state_after.get("context_accuracy_spread", 0.0))
        asymmetric_context_collapse = float(state_after.get("asymmetric_context_collapse", 0.0))
        max_context_debt = float(state_after.get("max_context_debt", 0.0))
        growth_authorized = float(state_after.get("growth_authorized", 0.0))
        growth_request_pressure = float(state_after.get("growth_request_pressure", 0.0))
        growth_request_readiness = float(state_after.get("growth_request_readiness", 0.0))
        pending_growth_proposals = float(state_after.get("pending_growth_proposals", 0.0))
        active_growth_nodes = float(state_after.get("active_growth_nodes", 0.0))

        target = self.accuracy_threshold if self.accuracy_threshold > 0.0 else 1.0
        accuracy_level = min(1.0, min_acc / max(target, 1e-6))
        accuracy_progress = min(1.0, max(0.0, 0.5 + delta * 5.0))

        growth_load = min(
            1.0,
            max(
                growth_request_pressure,
                growth_request_readiness,
                pending_growth_proposals,
                active_growth_nodes,
            ),
        )
        policy_efficiency = 1.0 - (0.18 * growth_load if growth_authorized > 0.5 else 0.0)
        policy_efficiency = max(0.75, policy_efficiency)

        context_imbalance = max(conflict, context_accuracy_spread, min(1.0, max_context_debt))
        if asymmetric_context_collapse > 0.5:
            context_imbalance = min(1.0, context_imbalance + 0.2)
        context_balance = max(0.0, 1.0 - context_imbalance)
        convergence = max(0.0, 1.0 - ambiguity)

        if history:
            prev_delta = float(history[-1].state_after.get("delta_min_ctx_acc", 0.0))
            oscillation = abs(delta - prev_delta)
            stability = max(0.0, 1.0 - min(1.0, oscillation * 4.0))
        else:
            stability = 0.5

        return {
            "accuracy_level":    round(accuracy_level, 4),
            "accuracy_progress": round(accuracy_progress, 4),
            "policy_efficiency": round(policy_efficiency, 4),
            "context_balance":   round(context_balance, 4),
            "convergence":       round(convergence, 4),
            "stability":         round(stability, 4),
        }

    def composite(self, dimensions: DimensionScores) -> float:
        return round(
            sum(dimensions.get(k, 0.0) * w for k, w in _DIMENSION_WEIGHTS.items()),
            4,
        )

    def gco_status(self, dimensions: DimensionScores, coherence: float, *, state_after: Dict[str, float] | None = None) -> GCOStatus:
        # STABLE requires floor-first success: no collapsed context plus
        # aggregate success.
        final_acc = float(
            (state_after or {}).get(
                "exact_match_rate",
                (state_after or {}).get(
                    "final_accuracy",
                    (state_after or {}).get("mean_bit_accuracy", 0.0),
                ),
            )
        )
        floor_acc = float(
            (state_after or {}).get(
                "floor_accuracy",
                (state_after or {}).get("min_ctx_acc", final_acc),
            )
        )
        if (
            self.accuracy_threshold > 0.0
            and floor_acc >= self.accuracy_threshold
            and final_acc >= self.accuracy_threshold
        ):
            return GCOStatus.STABLE
        if self.accuracy_threshold > 0.0:
            if coherence >= 0.65:
                return GCOStatus.PARTIAL
            if coherence >= 0.35:
                return GCOStatus.DEGRADED
            return GCOStatus.CRITICAL
        if dimensions.get("accuracy_level", 0.0) >= 0.95:
            return GCOStatus.STABLE
        if coherence >= 0.65:
            return GCOStatus.PARTIAL
        if coherence >= 0.35:
            return GCOStatus.DEGRADED
        return GCOStatus.CRITICAL


# ---------------------------------------------------------------------------
# REALSliceRegulator
# ---------------------------------------------------------------------------

class REALSliceRegulator:
    """Phase 3 slow-layer regulator: a RealCoreEngine that learns policy selection.

    The engine selects one named policy per slice.  A policy bundles:
      - capability_mode      (which substrate mode to run)
      - carryover_filter     (how to clear episodic memory)
      - budget_multiplier    (scale factor for next-slice budget)
      - context_pressure     (pressure label for fast layer)

    The MemorySubstrate accumulates bistable support for (context, policy)
    pairs that produce good outcomes — the same mechanism the fast layer uses
    for routing, applied one level up.

    Budget, hygiene, pressure, growth, and portfolio drive come from
    GradientSliceRegulator, while terminal settle/escalate decisions are
    gated by this regulator's own engine-level GCO trajectory.
    """

    def __init__(
        self,
        *,
        accuracy_threshold: float = 0.0,
        **heuristic_kwargs,
    ) -> None:
        self._heuristic = GradientSliceRegulator(
            accuracy_threshold=accuracy_threshold,
            **heuristic_kwargs,
        )
        self.accuracy_threshold = accuracy_threshold

        self._obs_adapter = SliceSummaryObservationAdapter()
        self._action_backend = PolicySelectionActionBackend()
        coherence_model = SliceAccuracyCoherenceModel(accuracy_threshold=accuracy_threshold)

        self._engine = RealCoreEngine(
            observer=self._obs_adapter,
            actions=self._action_backend,
            coherence=coherence_model,
            substrate=MemorySubstrate(SubstrateConfig(keys=_DIMENSION_NAMES)),
            memory=EpisodicMemory(maxlen=100),
            domain_name="meta_policy_selector",
        )

        self._prev_min_ctx_acc: float | None = None
        self._current_budget: int = 0
        self._cycle: int = 0
        # GCO-driven settlement: consecutive STABLE cycles before settle.
        # No escalation — if criteria aren't met, the system keeps working.
        self._gco_settle_window: int = 2
        self._last_policy_name: str | None = None
        self._last_intervention_summary: dict[str, float | str | None] = {}

    @property
    def engine(self) -> RealCoreEngine:
        return self._engine

    def engine_history(self) -> List[Dict[str, object]]:
        """Return a compact summary of the engine's cycle history for logging."""
        out = []
        for entry in self._engine.memory.entries:
            sb = {k: round(v, 4) for k, v in entry.state_before.items()}
            out.append({
                "cycle": entry.cycle,
                "action": entry.action,
                "coherence": round(entry.coherence, 4),
                "delta": round(entry.delta, 4),
                "gco": entry.gco.value,
                "state_before": sb,
            })
        return out

    def regulate(self, history: List[SliceSummary]) -> RegulatorySignal:
        if not history:
            return RegulatorySignal()

        current = history[-1]
        current_min = _min_ctx_acc(current)
        debt_summary = _context_debt_summary(
            history,
            accuracy_threshold=self.accuracy_threshold,
        )
        if self._last_policy_name is not None and self._prev_min_ctx_acc is not None:
            observed_delta = current_min - self._prev_min_ctx_acc
            self._last_intervention_summary = {
                "intervention_target_metric": "min_ctx_acc",
                "intervention_status": _intervention_status(observed_delta),
                "intervention_signed_delta": round(float(observed_delta), 4),
                "intervention_payoff": round(float(observed_delta), 4),
                "intervention_observed_delta": round(float(observed_delta), 4),
                "intervention_policy": self._last_policy_name,
            }

        # Update observation with latest slice data (includes delta from previous)
        self._obs_adapter.update(
            current,
            prev_min_ctx_acc=self._prev_min_ctx_acc,
            context_debt_summary=debt_summary,
        )
        self._prev_min_ctx_acc = current_min

        # Sync action backend to current mode so it filters to the right family
        self._action_backend.set_current_mode(current.mode_used)
        self._current_budget = current.slice_budget

        # Run one engine cycle: observe → predict → select → execute → score
        self._cycle += 1
        entry = self._engine.run_cycle(cycle=self._cycle)

        # Extract chosen policy dimensions
        policy_name = entry.action.removeprefix("policy:")
        policy = NAMED_POLICIES.get(policy_name, NAMED_POLICIES["visible_explore"])
        chosen_mode, growth_authorization, chosen_carryover, budget_mult, chosen_pressure = policy

        # Consult the gradient controller for the primary continuous control
        # vector. Settlement decisions still come from the engine's own GCO
        # trajectory so criteria remain terminal rather than policy-like.
        signal = self._heuristic.regulate(history)

        # --- GCO-driven settlement from the engine's own coherence ---
        decision_hint = SettlementDecision.CONTINUE
        stop_reason = ""
        gco_decision = self._evaluate_gco_trajectory()
        if gco_decision is not None:
            decision_hint, stop_reason = gco_decision

        # Use the gradient controller's budget target when available.
        next_budget = (
            max(1, round(float(signal.budget_target)))
            if signal.budget_target is not None
            else max(1, round(self._current_budget * budget_mult))
        )
        if float(signal.bias_updates.get("max_context_debt", 0.0)) >= 1.0:
            chosen_carryover = signal.carryover_filter_mode
            chosen_pressure = signal.context_pressure
            if signal.growth_authorization == "initiate":
                growth_authorization = "initiate"
            if signal.growth_authorization == "hold":
                growth_authorization = "hold"
            if not stop_reason:
                stop_reason = signal.stop_reason
        else:
            chosen_carryover = signal.carryover_filter_mode
            chosen_pressure = signal.context_pressure
            if signal.growth_authorization is not None:
                growth_authorization = signal.growth_authorization
            if signal.next_slice_budget is not None:
                next_budget = int(signal.next_slice_budget)
        if float(signal.reframe_flags.get("context_differentiation", 0.0)) > 0.0:
            chosen_carryover = "drop"
            chosen_pressure = "high"
            growth_authorization = "hold"
            next_budget = min(next_budget, current.slice_budget)
            if not stop_reason:
                stop_reason = signal.stop_reason

        # Only emit capability_mode if it differs from what's currently running
        new_mode: str | None = chosen_mode if chosen_mode != current.mode_used else None
        self._last_policy_name = policy_name

        return RegulatorySignal(
            next_slice_budget=next_budget,
            carryover_filter_mode=chosen_carryover,
            context_pressure=chosen_pressure,
            decision_hint=decision_hint,
            capability_mode=new_mode,
            growth_authorization=growth_authorization,
            budget_target=signal.budget_target,
            pressure_level=signal.pressure_level,
            hygiene_level=signal.hygiene_level,
            growth_drive=signal.growth_drive,
            portfolio_drive=signal.portfolio_drive,
            settlement_confidence=signal.settlement_confidence,
            execution_plan=signal.execution_plan,
            gating_updates=signal.gating_updates,
            bias_updates=signal.bias_updates,
            reset_flags=signal.reset_flags,
            reframe_flags=signal.reframe_flags,
            stop_reason=stop_reason,
            metadata={
                "engine_coherence": round(entry.coherence, 4),
                "engine_delta": round(entry.delta, 4),
                "engine_gco": entry.gco.value,
                "chosen_policy": policy_name,
                "chosen_mode": chosen_mode,
                "growth_authorization": growth_authorization,
                "chosen_carryover": chosen_carryover,
                "budget_multiplier": budget_mult,
                "budget_target": signal.budget_target,
                "pressure_level": signal.pressure_level,
                "hygiene_level": signal.hygiene_level,
                "growth_drive": signal.growth_drive,
                "portfolio_drive": signal.portfolio_drive,
                "settlement_confidence": signal.settlement_confidence,
                "max_context_debt": float(debt_summary.get("max_context_debt", 0.0)),
                "total_context_debt": float(debt_summary.get("total_context_debt", 0.0)),
                "open_context_count": float(debt_summary.get("open_context_count", 0.0)),
                "best_debt_context": debt_summary.get("best_debt_context"),
                **self._last_intervention_summary,
            },
        )

    def _evaluate_gco_trajectory(self) -> tuple[SettlementDecision, str] | None:
        """Derive settlement from the engine's own GCO history.

        The only terminal condition is criteria being met consistently:
        consecutive STABLE cycles mean the accuracy threshold has been
        reached across all contexts.  There is no escalation based on
        poor performance — if the system hasn't solved the problem, it
        keeps working.  The safety_limit on the controller is the only
        guard against infinite loops.
        """
        entries = self._engine.memory.entries
        if len(entries) < self._gco_settle_window:
            return None

        # Settle: last N cycles all STABLE (accuracy criteria met consistently)
        recent = entries[-self._gco_settle_window:]
        if all(e.gco == GCOStatus.STABLE for e in recent):
            return SettlementDecision.SETTLE, "engine_gco_stable"

        return None
