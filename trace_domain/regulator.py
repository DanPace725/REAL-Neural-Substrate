"""Dimension-Action Regulator: the slow layer that biases action selection.

This is the piece that was missing — the system's ability to connect
"what's wrong" (which dimension is the bottleneck) to "what to do about
it" (which actions tend to improve that dimension).

The regulator:
  1. Tracks which actions improve which dimensions (learned from history)
  2. Identifies the current bottleneck dimension
  3. Emits a bias map that the selector uses to weight action choices
  4. Updates its own bias map when a 'reorient' action fires

The bias map is tilt-only — it shifts weights, it doesn't restructure
the action space or rewrite the coherence model.  Respects the
parametric wall: bias magnitudes are capped.

Lifecycle:
  - after_cycle(): called after each engine cycle with the CycleEntry
  - get_bias(): returns current action bias weights for the selector
  - reorient(): triggered by the 'reorient' action, forces a strategy review
  - save_state() / load_state(): persistence across sessions
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from real_core.types import CycleEntry, DimensionScores


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PARAMETRIC_WALL = 0.289       # max bias magnitude (from TCL)
VIABILITY_FLOOR = 0.757       # dimension must be above this to NOT be a bottleneck candidate
BOTTLENECK_THRESHOLD = 0.55   # dimension below this is considered a bottleneck
LEARNING_RATE = 0.15          # how fast the dim→action map updates
DECAY_RATE = 0.02             # slow decay on learned associations
MIN_HISTORY_FOR_BIAS = 8      # don't emit bias until enough data
REORIENT_COOLDOWN = 10        # minimum cycles between reorient actions
STAGNATION_LOOKBACK = 15      # cycles to check for stagnation triggering reorient

# Frustration parameters — gentle restlessness, not panic.
# Like fidgeting when you've been sitting too long: enough to make you
# want to get up, not enough to make you run screaming.
FRUSTRATION_ONSET = 12        # cycles without improvement before frustration builds
FRUSTRATION_RATE = 0.03       # how fast frustration accumulates per stale cycle
FRUSTRATION_DECAY = 0.20      # drops quickly when progress happens (reward)
FRUSTRATION_MAX = 0.5         # ceiling — restless, not desperate
FRUSTRATION_REPETITION_WINDOW = 15  # look back this many cycles for repetition detection


# ---------------------------------------------------------------------------
# The Regulator
# ---------------------------------------------------------------------------

@dataclass
class DimensionActionRegulator:
    """Slow-layer regulator that learns dimension→action associations
    and biases the selector toward actions that address bottlenecks.

    The dim_action_map is a Dict[dimension, Dict[action_type, float]]
    where the float is a running estimate of how much that action type
    tends to improve that dimension.  Positive = improves, negative = hurts.
    """

    # Learned: which action types tend to improve which dimensions
    dim_action_map: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Current bottleneck diagnosis
    bottleneck_dim: Optional[str] = None
    bottleneck_severity: float = 0.0

    # Current bias signal (action_type → weight bonus)
    current_bias: Dict[str, float] = field(default_factory=dict)

    # Tracking
    cycle_count: int = 0
    last_reorient_cycle: int = -100
    reorient_count: int = 0

    # Recent cycle history (kept internally for reorient)
    _recent_entries: List[CycleEntry] = field(default_factory=list)
    _max_recent: int = 50

    # History of bottleneck shifts for reflexivity
    bottleneck_history: List[Tuple[int, str, float]] = field(default_factory=list)

    # Frustration: accumulated pressure from stagnation that drives
    # the system toward novel actions. Like discomfort from sitting
    # still too long — the agent gets restless.
    frustration: float = 0.0
    _best_coherence: float = 0.0
    _cycles_since_improvement: int = 0

    # Frontier awareness: how much unexplored territory exists.
    # Updated each cycle from the observation. The regulator doesn't
    # know about the environment — it just receives this signal.
    _frontier_pressure: float = 1.0  # starts maximal (nothing explored)

    # Workspace guidance: downward signal from real_system's integrative
    # layer.  Tells this regulator which dimensions the wider system
    # cares about most, so local decisions can align with workspace-level
    # priorities without losing autonomy.
    _workspace_guidance: Optional[Dict[str, Any]] = None

    def _action_type(self, action: str) -> str:
        """Normalize action to its type (strip group-specific suffixes)."""
        if action.startswith("tag:"):
            return "tag"
        if action.startswith("split:"):
            return "split"
        if action.startswith("organize:"):
            return "organize"
        if action.startswith("grow:"):
            return "grow"
        if action.startswith("activate:"):
            return "activate"
        if action.startswith("feed:"):
            return "feed"
        if action.startswith("read_"):
            return "read_trace"
        return action

    # ------------------------------------------------------------------
    # Core learning: update dim→action associations from each cycle
    # ------------------------------------------------------------------

    def after_cycle(self, entry: CycleEntry) -> None:
        """Called after each engine cycle.  Updates the learned dim→action map
        and recomputes the current bias signal.
        """
        self.cycle_count += 1
        self._recent_entries.append(entry)
        if len(self._recent_entries) > self._max_recent:
            self._recent_entries = self._recent_entries[-self._max_recent:]
        action_type = self._action_type(entry.action)

        # For each dimension, record whether this action improved or hurt it
        if len(entry.dimensions) > 0:
            for dim_name, dim_value in entry.dimensions.items():
                if dim_name not in self.dim_action_map:
                    self.dim_action_map[dim_name] = {}
                action_map = self.dim_action_map[dim_name]

                # Use delta as the learning signal
                # Positive delta after this action = this action helps
                signal = entry.delta  # overall coherence delta

                # Also use dimension-specific signal if we can extract it
                # from state_before/state_after
                if isinstance(entry.state_before, dict) and isinstance(entry.state_after, dict):
                    before_val = entry.state_before.get(dim_name)
                    after_val = entry.state_after.get(dim_name)
                    if isinstance(before_val, (int, float)) and isinstance(after_val, (int, float)):
                        dim_signal = float(after_val) - float(before_val)
                        signal = 0.5 * entry.delta + 0.5 * dim_signal

                # Exponential moving average update
                old = action_map.get(action_type, 0.0)
                action_map[action_type] = old + LEARNING_RATE * (signal - old)

        # Apply slow decay to all associations (forgetting)
        for dim_name, action_map in self.dim_action_map.items():
            for atype in list(action_map.keys()):
                action_map[atype] *= (1.0 - DECAY_RATE)
                if abs(action_map[atype]) < 0.001:
                    del action_map[atype]

        # Update frontier awareness from observation state
        if isinstance(entry.state_after, dict):
            self._frontier_pressure = entry.state_after.get("frontier_pressure", self._frontier_pressure)

        # Track frustration — builds when stuck, decays when progressing
        self._update_frustration(entry.coherence)

        # Recompute bottleneck and bias
        self._update_bottleneck(entry.dimensions)
        self._update_bias()

    # ------------------------------------------------------------------
    # Frustration: accumulated stagnation pressure
    # ------------------------------------------------------------------

    def _update_frustration(self, coherence: float) -> None:
        """Update frustration level based on whether we're making progress.

        Frustration builds when coherence stagnates — like the discomfort
        of sitting still when you know you should be doing something.
        It decays quickly when genuine progress happens, rewarding
        exploration that pays off.
        """
        improvement_threshold = 0.005  # aligned with engine stagnation detection

        if coherence > self._best_coherence + improvement_threshold:
            # Genuine improvement — frustration drops sharply
            self._best_coherence = coherence
            self._cycles_since_improvement = 0
            self.frustration = max(0.0, self.frustration - FRUSTRATION_DECAY)
        else:
            self._cycles_since_improvement += 1

            # Frustration only builds after the onset window
            if self._cycles_since_improvement > FRUSTRATION_ONSET:
                self.frustration = min(
                    FRUSTRATION_MAX,
                    self.frustration + FRUSTRATION_RATE,
                )

        # Plateau-satisfied check: coherence is fine but there's unexplored
        # territory.  The system isn't frustrated (things are going well)
        # but it should feel a gentle restlessness — like knowing there's
        # a room you haven't entered yet.  Not urgency, just curiosity.
        if self.frustration < 0.1 and self._frontier_pressure > 0.3:
            nudge = FRUSTRATION_RATE * 0.5 * self._frontier_pressure
            self.frustration = min(FRUSTRATION_MAX, self.frustration + nudge)

    def _frustration_bias(self) -> Dict[str, float]:
        """Compute frustration-driven bias: suppress repetitive actions,
        boost exploratory/novel ones.

        When frustration is high, the system should feel restless —
        biased toward things it HASN'T been doing, away from things
        it's been stuck in a loop on.
        """
        if self.frustration < 0.1 or len(self._recent_entries) < 5:
            return {}

        # Count recent action type frequencies
        window = self._recent_entries[-FRUSTRATION_REPETITION_WINDOW:]
        type_counts: Dict[str, int] = {}
        for e in window:
            atype = self._action_type(e.action)
            type_counts[atype] = type_counts.get(atype, 0) + 1

        total = len(window)
        bias: Dict[str, float] = {}

        for atype, count in type_counts.items():
            fraction = count / total
            if fraction > 0.40:
                # This action dominates recent history — gentle suppression.
                # Not "stop doing this" but "maybe try something else?"
                penalty = -self.frustration * PARAMETRIC_WALL * 0.5 * min(1.0, fraction)
                bias[atype] = penalty

        # Gently boost actions that haven't been tried recently.
        # These represent unexplored directions — the restlessness
        # makes them more appealing, like noticing a door you
        # haven't opened yet.
        all_known_types = set(type_counts.keys())
        exploratory_types = {
            "read_trace", "read_neighbor", "read_gap", "read_surprise",
            "split", "merge_groups", "create_group",
            "grow", "activate", "organize", "reorient",
        }
        # Frontier amplification: when there's unexplored territory,
        # exploratory actions get a stronger nudge.  The slime mold
        # extends pseudopods more aggressively when nutrients are nearby.
        frontier_amp = 1.0 + self._frontier_pressure  # 1.0 → 2.0

        for atype in exploratory_types - all_known_types:
            # Not used at all recently — moderate boost, amplified by frontier
            bias[atype] = self.frustration * PARAMETRIC_WALL * 0.4 * frontier_amp
        for atype in exploratory_types & all_known_types:
            if type_counts[atype] / total < 0.10:
                # Used rarely — mild boost, amplified by frontier
                bias[atype] = bias.get(atype, 0.0) + self.frustration * PARAMETRIC_WALL * 0.2 * frontier_amp

        return bias

    # ------------------------------------------------------------------
    # Workspace guidance: downward signal from real_system
    # ------------------------------------------------------------------

    def load_workspace_guidance(self, guidance_path: Path) -> bool:
        """Load workspace-level guidance from real_system.

        The guidance file contains primitive_tensions, integration_pressure,
        and the workspace's top bottleneck.  This regulator uses those
        signals to nudge its own bottleneck assessment and bias — like
        hearing a heartbeat from the larger organism you're part of.

        Returns True if guidance was loaded successfully.
        """
        if not guidance_path.exists():
            return False
        try:
            with open(guidance_path, "r", encoding="utf-8") as fh:
                self._workspace_guidance = json.load(fh)
            return True
        except (json.JSONDecodeError, OSError):
            return False

    def _workspace_bias(self) -> Dict[str, float]:
        """Compute bias from workspace-level guidance.

        The workspace tells us which primitives have high tension system-wide.
        We translate that into action bias through our dim_action_map:
        if the workspace says 'continuity has high tension' and we know
        which of our actions help continuity, we boost those actions.

        Blending: workspace influence is scaled by integration_pressure
        (0.0 → 1.0).  When integration pressure is low, local decisions
        dominate.  When it's high, the workspace signal gets louder —
        but never louder than the parametric wall.

        This is the reflexive loop closing: real_system reads our state,
        fuses it with other domains, and sends back a signal that shapes
        our next actions.
        """
        if self._workspace_guidance is None:
            return {}

        tensions = self._workspace_guidance.get("primitive_tensions", {})
        integration_pressure = self._workspace_guidance.get("integration_pressure", 0.0)

        if not tensions or integration_pressure < 0.05:
            return {}

        # Scale: workspace influence is 30% at max integration pressure.
        # The regulator's own learned associations still dominate.
        workspace_weight = 0.30 * min(1.0, integration_pressure / 0.5)

        bias: Dict[str, float] = {}

        # For each primitive with positive tension (i.e., it's a weakness
        # at the workspace level), boost actions we've learned help that
        # dimension.
        for prim_name, tension in tensions.items():
            if tension <= 0.0:
                continue  # no tension or it's a strength — skip

            action_map = self.dim_action_map.get(prim_name, {})
            if not action_map:
                continue

            # Tension is already weighted by severity × confidence at the
            # workspace level.  Scale it by our workspace_weight to get
            # a bias magnitude.
            for atype, association in action_map.items():
                if association > 0.005:
                    # This action helps a dimension the workspace needs
                    nudge = association * tension * workspace_weight * 3.0
                    nudge = min(PARAMETRIC_WALL * 0.5, nudge)  # don't overpower local bias
                    bias[atype] = bias.get(atype, 0.0) + nudge
                elif association < -0.005:
                    # This action hurts a dimension the workspace needs
                    penalty = association * tension * workspace_weight * 1.5
                    penalty = max(-PARAMETRIC_WALL * 0.3, penalty)
                    bias[atype] = bias.get(atype, 0.0) + penalty

        # Clamp all biases to parametric wall
        for atype in bias:
            bias[atype] = max(-PARAMETRIC_WALL, min(PARAMETRIC_WALL, bias[atype]))

        return bias

    # ------------------------------------------------------------------
    # Bottleneck diagnosis
    # ------------------------------------------------------------------

    def _update_bottleneck(self, dimensions: DimensionScores) -> None:
        """Identify the dimension that's dragging the system down."""
        if not dimensions:
            return

        # Find the weakest dimension
        weakest_dim = min(dimensions, key=dimensions.get)
        weakest_val = dimensions[weakest_dim]

        # Only declare a bottleneck if it's meaningfully below threshold
        if weakest_val < BOTTLENECK_THRESHOLD:
            old_bottleneck = self.bottleneck_dim
            self.bottleneck_dim = weakest_dim
            self.bottleneck_severity = max(0.0, BOTTLENECK_THRESHOLD - weakest_val)

            # Record bottleneck shifts
            if old_bottleneck != weakest_dim:
                self.bottleneck_history.append(
                    (self.cycle_count, weakest_dim, weakest_val)
                )
                # Keep history bounded
                if len(self.bottleneck_history) > 50:
                    self.bottleneck_history = self.bottleneck_history[-50:]
        else:
            # No bottleneck — all dimensions above threshold
            self.bottleneck_dim = None
            self.bottleneck_severity = 0.0

    # ------------------------------------------------------------------
    # Bias computation
    # ------------------------------------------------------------------

    def _update_bias(self) -> None:
        """Compute the current action bias from bottleneck + learned map."""
        self.current_bias = {}

        if self.bottleneck_dim is None:
            return  # no bottleneck, no bias needed

        if self.cycle_count < MIN_HISTORY_FOR_BIAS:
            return  # not enough data to bias meaningfully

        action_map = self.dim_action_map.get(self.bottleneck_dim, {})
        if not action_map:
            return

        # Find actions that have positive associations with the bottleneck dimension
        # Scale bias by severity (worse bottleneck = stronger bias)
        severity_scale = min(1.0, self.bottleneck_severity / 0.3)

        for action_type, association in action_map.items():
            if association > 0.005:
                # This action tends to improve the bottleneck dimension
                # Bias magnitude: association strength × severity, capped at parametric wall
                bias = min(PARAMETRIC_WALL, association * severity_scale * 3.0)
                self.current_bias[action_type] = bias
            elif association < -0.005:
                # This action tends to hurt the bottleneck dimension
                # Mild negative bias (don't completely suppress, just discourage)
                bias = max(-PARAMETRIC_WALL * 0.5, association * severity_scale * 2.0)
                self.current_bias[action_type] = bias

    # ------------------------------------------------------------------
    # Bias access (called by the selector)
    # ------------------------------------------------------------------

    def get_bias(self) -> Dict[str, float]:
        """Return current action type → bias weight map.

        Three layers of bias, combined additively:
          1. Bottleneck bias   — from local dimension diagnosis
          2. Frustration bias  — from stagnation pressure
          3. Workspace bias    — from real_system's cross-domain guidance

        Positive = favor this action type.
        Negative = disfavor this action type.
        Magnitudes capped at PARAMETRIC_WALL.
        """
        combined = dict(self.current_bias)

        # Layer frustration bias on top of bottleneck bias
        frust_bias = self._frustration_bias()
        for atype, value in frust_bias.items():
            combined[atype] = combined.get(atype, 0.0) + value

        # Layer workspace guidance on top of local + frustration
        ws_bias = self._workspace_bias()
        for atype, value in ws_bias.items():
            combined[atype] = combined.get(atype, 0.0) + value

        # Clamp everything to parametric wall
        for atype in combined:
            combined[atype] = max(-PARAMETRIC_WALL, min(PARAMETRIC_WALL, combined[atype]))

        return combined

    def get_diagnosis(self) -> Dict[str, Any]:
        """Return current diagnostic state for logging/display."""
        diag = {
            "bottleneck_dim": self.bottleneck_dim,
            "bottleneck_severity": round(self.bottleneck_severity, 4),
            "bias": {k: round(v, 4) for k, v in self.current_bias.items()},
            "frustration": round(self.frustration, 4),
            "frontier_pressure": round(self._frontier_pressure, 4),
            "cycles_since_improvement": self._cycles_since_improvement,
            "cycle_count": self.cycle_count,
            "reorient_count": self.reorient_count,
            "dim_action_map_size": {
                dim: len(actions) for dim, actions in self.dim_action_map.items()
            },
        }
        # Workspace guidance state
        if self._workspace_guidance is not None:
            diag["workspace_guidance"] = {
                "top_bottleneck": self._workspace_guidance.get("top_bottleneck_primitive"),
                "integration_pressure": self._workspace_guidance.get("integration_pressure", 0.0),
                "cycle_count": self._workspace_guidance.get("cycle_count", 0),
            }
            ws_bias = self._workspace_bias()
            if ws_bias:
                diag["workspace_bias"] = {k: round(v, 4) for k, v in ws_bias.items()}
        return diag

    # ------------------------------------------------------------------
    # Reorient action: explicit strategy shift
    # ------------------------------------------------------------------

    def can_reorient(self) -> bool:
        """Whether a reorient is allowed (respects cooldown)."""
        return (self.cycle_count - self.last_reorient_cycle) >= REORIENT_COOLDOWN

    def reorient(self, dimensions: DimensionScores, history: List[CycleEntry]) -> Dict[str, Any]:
        """Perform an explicit strategy review and emit updated bias.

        This is triggered by the 'reorient' action.  It:
          1. Diagnoses the current bottleneck from full dimension history
          2. Computes action effectiveness from recent history
          3. Emits a stronger, more targeted bias signal
          4. Records the reorientation event

        Returns diagnostic info about what changed.
        """
        self.last_reorient_cycle = self.cycle_count
        self.reorient_count += 1

        old_bottleneck = self.bottleneck_dim
        old_bias = dict(self.current_bias)

        # 1. Fresh bottleneck diagnosis from recent dimension history
        if history:
            # Use mean of recent dimensions, not just latest
            recent = history[-STAGNATION_LOOKBACK:]
            dim_means: Dict[str, float] = {}
            for entry in recent:
                for dim, val in entry.dimensions.items():
                    if dim not in dim_means:
                        dim_means[dim] = []
                    dim_means[dim].append(val)
            dim_means = {dim: sum(vals) / len(vals) for dim, vals in dim_means.items()}
            self._update_bottleneck(dim_means)

        # 2. Recompute action effectiveness from recent history specifically
        if len(history) >= 5:
            recent = history[-min(30, len(history)):]
            # For the bottleneck dimension, which actions actually helped?
            if self.bottleneck_dim:
                fresh_map: Dict[str, List[float]] = {}
                for entry in recent:
                    atype = self._action_type(entry.action)
                    dim_val = entry.dimensions.get(self.bottleneck_dim, 0.0)
                    if atype not in fresh_map:
                        fresh_map[atype] = []
                    fresh_map[atype].append(entry.delta)

                # Update the dim_action_map with fresh data (stronger weight)
                if self.bottleneck_dim not in self.dim_action_map:
                    self.dim_action_map[self.bottleneck_dim] = {}
                for atype, deltas in fresh_map.items():
                    mean_delta = sum(deltas) / len(deltas)
                    # Reorient uses a stronger learning rate
                    old = self.dim_action_map[self.bottleneck_dim].get(atype, 0.0)
                    self.dim_action_map[self.bottleneck_dim][atype] = (
                        old + 0.4 * (mean_delta - old)
                    )

        # 3. Recompute bias with potentially new bottleneck
        self._update_bias()

        return {
            "old_bottleneck": old_bottleneck,
            "new_bottleneck": self.bottleneck_dim,
            "bottleneck_severity": round(self.bottleneck_severity, 4),
            "old_bias": {k: round(v, 4) for k, v in old_bias.items()},
            "new_bias": {k: round(v, 4) for k, v in self.current_bias.items()},
            "reorient_count": self.reorient_count,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_state(self) -> Dict[str, Any]:
        """Export regulator state for cross-session carryover."""
        return {
            "dim_action_map": {
                dim: dict(actions)
                for dim, actions in self.dim_action_map.items()
            },
            "bottleneck_dim": self.bottleneck_dim,
            "bottleneck_severity": self.bottleneck_severity,
            "current_bias": dict(self.current_bias),
            "cycle_count": self.cycle_count,
            "reorient_count": self.reorient_count,
            "bottleneck_history": [
                {"cycle": c, "dim": d, "val": round(v, 4)}
                for c, d, v in self.bottleneck_history
            ],
            "frustration": self.frustration,
            "best_coherence": self._best_coherence,
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """Restore regulator state from a prior session."""
        self.dim_action_map = {
            dim: dict(actions)
            for dim, actions in state.get("dim_action_map", {}).items()
        }
        self.bottleneck_dim = state.get("bottleneck_dim")
        self.bottleneck_severity = state.get("bottleneck_severity", 0.0)
        self.current_bias = dict(state.get("current_bias", {}))
        self.cycle_count = state.get("cycle_count", 0)
        self.reorient_count = state.get("reorient_count", 0)
        self.bottleneck_history = [
            (item["cycle"], item["dim"], item["val"])
            for item in state.get("bottleneck_history", [])
        ]
        self.frustration = state.get("frustration", 0.0)
        self._best_coherence = state.get("best_coherence", 0.0)
