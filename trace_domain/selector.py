"""Regulated CFAR selector: the standard selector with slow-layer bias input.

This wraps the core CFARSelector and applies the DimensionActionRegulator's
bias signal to action scoring.  The bias is tilt-only — it shifts weights
without restructuring the action space.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

from real_core.selector import CFARSelector, SelectionMode
from real_core.types import CycleEntry, SelectionContext

from .regulator import DimensionActionRegulator


class RegulatedSelector(CFARSelector):
    """CFARSelector that accepts a bias signal from the DimensionActionRegulator.

    In CONSTRAINT and GUIDED modes, action scores are adjusted by the
    regulator's bias.  In FLUCTUATION mode, bias is still applied but
    more weakly (exploration shouldn't be fully suppressed).
    """

    def __init__(
        self,
        regulator: DimensionActionRegulator,
        exploration_rate: float = 0.40,
        stagnation_window: int = 5,
        stagnation_threshold: float = 0.005,
        guided_threshold: int = 12,
        budget_mode: bool = True,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__(
            exploration_rate=exploration_rate,
            stagnation_window=stagnation_window,
            stagnation_threshold=stagnation_threshold,
            guided_threshold=guided_threshold,
            budget_mode=budget_mode,
            rng=rng,
        )
        self.regulator = regulator

    def _action_type(self, action: str) -> str:
        """Normalize action to its type for bias lookup."""
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

    def _apply_bias(self, action: str, base_score: float, mode: SelectionMode) -> float:
        """Apply the regulator's bias to an action's score.

        Bias is stronger in CONSTRAINT/GUIDED modes, weaker in FLUCTUATION.
        """
        bias = self.regulator.get_bias()
        if not bias:
            return base_score

        action_type = self._action_type(action)
        bias_value = bias.get(action_type, 0.0)

        if abs(bias_value) < 0.001:
            return base_score

        # Scale bias by mode: full in constraint/guided, half in fluctuation
        if mode == SelectionMode.FLUCTUATION:
            bias_value *= 0.4
        elif mode == SelectionMode.GUIDED:
            bias_value *= 1.2  # slightly amplified in guided (targeting weakness)

        return base_score + bias_value

    def select(self, available: List[str], history: List[CycleEntry]) -> Tuple[str, str]:
        """Override select to apply bias to the scoring pipeline."""
        if not available:
            raise ValueError("No available actions")

        mode = self._choose_mode(history)

        if mode == SelectionMode.FLUCTUATION:
            # In fluctuation, still bias but through weighted random
            return self._biased_fluctuate(available, history, mode), mode.value

        if mode == SelectionMode.GUIDED:
            return self._biased_guided(available, history, mode), mode.value

        # CONSTRAINT mode: exploit with bias
        return self._biased_exploit(available, history, mode), mode.value

    def _biased_fluctuate(self, available: List[str], history: List[CycleEntry], mode: SelectionMode) -> str:
        """Fluctuation with bias: random, but bias-preferred actions weighted higher."""
        usage = {}
        for e in history:
            usage[e.action] = usage.get(e.action, 0) + 1
        max_used = max(usage.values()) if usage else 1

        weights = []
        for a in available:
            # Base weight: novelty (less-used actions get higher weight)
            base = max(1, max_used - usage.get(a, 0) + 1)
            # Apply bias (scaled down for fluctuation)
            biased = base + self._apply_bias(a, 0.0, mode) * 10.0
            weights.append(max(0.5, biased))  # floor at 0.5 (never fully suppress)

        return self.rng.choices(available, weights=weights, k=1)[0]

    def _biased_exploit(self, available: List[str], history: List[CycleEntry], mode: SelectionMode) -> str:
        """Exploit with bias applied to history-based scoring."""
        if not history:
            return self.rng.choice(available)

        mean_cost = self._mean_cost(history)

        best = available[0]
        best_score = -1e9
        for a in available:
            base = self._history_score(a, history, mean_cost)
            score = self._apply_bias(a, base, mode)
            if score > best_score:
                best_score = score
                best = a
        return best

    def _biased_guided(self, available: List[str], history: List[CycleEntry], mode: SelectionMode) -> str:
        """Guided mode: target weakest dimension, with regulator bias."""
        if len(history) < 4:
            return self._biased_exploit(available, history, mode)

        # Use regulator's bottleneck diagnosis if available, otherwise compute locally
        target_dim = self.regulator.bottleneck_dim
        if target_dim is None:
            # Fallback to standard guided behavior
            dims = list(history[-1].dimensions.keys())
            if not dims:
                return self._biased_exploit(available, history, mode)
            recent = history[-8:]
            target_dim = min(
                dims,
                key=lambda d: sum(e.dimensions.get(d, 0.0) for e in recent) / len(recent),
            )

        self.last_weakest_dimension = target_dim

        # Score actions by how much they improve the target dimension + bias
        improvements = {}
        for a in available:
            vals = [e.dimensions.get(target_dim, 0.0) for e in history if e.action == a]
            base = sum(vals) / len(vals) if vals else 0.0
            improvements[a] = self._apply_bias(a, base, mode)

        if not improvements:
            return self._biased_exploit(available, history, mode)

        return max(improvements, key=improvements.get)
