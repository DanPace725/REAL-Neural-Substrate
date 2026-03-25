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
from .lamination import HeuristicSliceRegulator
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
# Each policy is (capability_mode, carryover_filter, budget_multiplier, context_pressure).
# The REAL agent selects one policy per slice; the substrate learns which policy
# produces the best accuracy trajectory given the current observation context.

Policy = Tuple[str, str, float, str]

NAMED_POLICIES: Dict[str, Policy] = {
    # --- Visible family ---
    # Hold visible mode but soften memory to reduce stale context drag.
    "visible_explore":       ("visible",        "soften", 1.00, "medium"),
    # Visible mode, hard carryover reset — used when stalled.
    "visible_push":          ("visible",        "drop",   1.00, "high"),

    # --- Growth-visible family ---
    # Switch to growth, soften memory, keep budget — the standard upgrade path.
    "growth_engage":         ("growth-visible", "soften", 1.00, "high"),
    # Growth has converged well; maintain budget, reduce memory pressure.
    "growth_consolidate":    ("growth-visible", "keep",   1.00, "low"),
    # Growth is stalling; clear memory — budget stays constant.
    "growth_reset":          ("growth-visible", "drop",   1.00, "high"),
    # Growth is active; maintain without pressure changes.
    "growth_hold":           ("growth-visible", "keep",   1.00, "medium"),

    # --- Latent family ---
    "latent_explore":        ("latent",         "soften", 1.00, "medium"),
    "latent_push":           ("latent",         "drop",   1.00, "high"),

    # --- Growth-latent family ---
    "growth_latent_engage":       ("growth-latent", "soften", 1.00, "high"),
    "growth_latent_consolidate":  ("growth-latent", "keep",   1.00, "low"),
}

# Which policies are available given the current mode.
# Growth modes get their own family so the engine can never step *back*
# from growth-visible to plain visible (which would destroy accumulated growth).
_MODE_FAMILY: Dict[str, str] = {
    "visible":        "visible",
    "self-selected":  "visible",
    "growth-visible": "growth-visible",
    "latent":         "latent",
    "growth-latent":  "growth-latent",
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
    # Once in growth-visible: only growth policies — no stepping back.
    "growth-visible": [
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
    # Once in growth-latent: only growth-latent policies.
    "growth-latent": [
        "growth_latent_engage",
        "growth_latent_consolidate",
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _min_ctx_acc(summary: SliceSummary) -> float:
    if summary.context_accuracy:
        return min(summary.context_accuracy.values())
    return float(summary.metadata.get("mean_bit_accuracy", 0.0))


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
            "delta_min_ctx_acc": 0.0,
            "conflict": 0.5,
            "ambiguity": 0.5,
            "coherence_delta": 0.0,
            "mean_uncertainty": 1.0,
            "mode_is_growth": 0.0,
        }

    def update(self, summary: SliceSummary, *, prev_min_ctx_acc: float | None = None) -> None:
        cur = _min_ctx_acc(summary)
        mean_acc = float(summary.metadata.get("mean_bit_accuracy", 0.0))
        delta = (cur - prev_min_ctx_acc) if prev_min_ctx_acc is not None else 0.0
        self._current = {
            "min_ctx_acc": round(cur, 4),
            "mean_bit_accuracy": round(mean_acc, 4),
            "delta_min_ctx_acc": round(delta, 4),
            "conflict": round(summary.conflict_level, 4),
            "ambiguity": round(summary.ambiguity_level, 4),
            "coherence_delta": round(summary.coherence_delta, 4),
            "mean_uncertainty": round(summary.mean_uncertainty, 4),
            "mode_is_growth": 1.0 if summary.mode_used.startswith("growth-") else 0.0,
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
                "carryover_filter": policy[1],
                "budget_multiplier": policy[2],
                "context_pressure": policy[3],
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
        mode_is_growth = float(state_after.get("mode_is_growth", 0.0))

        target = self.accuracy_threshold if self.accuracy_threshold > 0.0 else 1.0
        accuracy_level = min(1.0, min_acc / max(target, 1e-6))
        accuracy_progress = min(1.0, max(0.0, 0.5 + delta * 5.0))

        # growth mode costs more; reflect that in efficiency dimension
        policy_efficiency = 0.7 if mode_is_growth > 0.5 else 1.0

        context_balance = max(0.0, 1.0 - conflict)
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
        # STABLE = mean accuracy meets threshold (the actual task criterion).
        mean_acc = float((state_after or {}).get("mean_bit_accuracy", 0.0))
        if self.accuracy_threshold > 0.0 and mean_acc >= self.accuracy_threshold:
            return GCOStatus.STABLE
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

    Settle/escalate/GCO decisions and bias updates are still delegated to
    HeuristicSliceRegulator.
    """

    def __init__(
        self,
        *,
        accuracy_threshold: float = 0.0,
        **heuristic_kwargs,
    ) -> None:
        self._heuristic = HeuristicSliceRegulator(
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
        # Growth-mode hysteresis: consecutive DEGRADED/CRITICAL cycles while in growth mode.
        # Reversion to non-growth is only allowed after _GROWTH_LOCK_THRESHOLD bad cycles.
        self._growth_degraded_streak: int = 0
        self._GROWTH_LOCK_THRESHOLD: int = 2
        # GCO-driven settlement: consecutive STABLE cycles before settle.
        # No escalation — if criteria aren't met, the system keeps working.
        self._gco_settle_window: int = 2

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

        # Update observation with latest slice data (includes delta from previous)
        self._obs_adapter.update(current, prev_min_ctx_acc=self._prev_min_ctx_acc)
        self._prev_min_ctx_acc = _min_ctx_acc(current)

        # Sync action backend to current mode so it filters to the right family
        self._action_backend.set_current_mode(current.mode_used)
        self._current_budget = current.slice_budget

        # Run one engine cycle: observe → predict → select → execute → score
        self._cycle += 1
        entry = self._engine.run_cycle(cycle=self._cycle)

        # Extract chosen policy dimensions
        policy_name = entry.action.removeprefix("policy:")
        policy = NAMED_POLICIES.get(policy_name, NAMED_POLICIES["visible_explore"])
        chosen_mode, chosen_carryover, budget_mult, chosen_pressure = policy

        # Growth-mode hysteresis: once in a growth mode, don't revert to a non-growth mode
        # unless the engine has reported DEGRADED or CRITICAL for enough consecutive cycles.
        in_growth = current.mode_used.startswith("growth-")
        if in_growth:
            if entry.gco.value in ("DEGRADED", "CRITICAL"):
                self._growth_degraded_streak += 1
            else:
                self._growth_degraded_streak = 0

            if not chosen_mode.startswith("growth-") and self._growth_degraded_streak < self._GROWTH_LOCK_THRESHOLD:
                # Lock: override to growth_hold (keep carryover, neutral budget)
                lock_policy = NAMED_POLICIES["growth_hold"]
                policy_name = "growth_hold"
                chosen_mode, chosen_carryover, budget_mult, chosen_pressure = lock_policy
        else:
            self._growth_degraded_streak = 0

        # Consult heuristic only for tilt-style bias and gating signals.
        # Settlement decisions come from the engine's own GCO trajectory.
        signal = self._heuristic.regulate(history)

        # --- GCO-driven settlement from the engine's own coherence ---
        decision_hint = SettlementDecision.CONTINUE
        stop_reason = ""
        gco_decision = self._evaluate_gco_trajectory()
        if gco_decision is not None:
            decision_hint, stop_reason = gco_decision

        # Compute next budget from multiplier
        next_budget = max(1, round(self._current_budget * budget_mult))

        # Only emit capability_mode if it differs from what's currently running
        new_mode: str | None = chosen_mode if chosen_mode != current.mode_used else None

        return RegulatorySignal(
            next_slice_budget=next_budget,
            carryover_filter_mode=chosen_carryover,
            context_pressure=chosen_pressure,
            decision_hint=decision_hint,
            capability_mode=new_mode,
            gating_updates=signal.gating_updates,
            bias_updates=signal.bias_updates,
            stop_reason=stop_reason,
            metadata={
                "engine_coherence": round(entry.coherence, 4),
                "engine_delta": round(entry.delta, 4),
                "engine_gco": entry.gco.value,
                "chosen_policy": policy_name,
                "chosen_mode": chosen_mode,
                "chosen_carryover": chosen_carryover,
                "budget_multiplier": budget_mult,
                "growth_degraded_streak": self._growth_degraded_streak,
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
