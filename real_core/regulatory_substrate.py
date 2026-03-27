from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class RegulatoryPrimitive(str, Enum):
    DIFFERENTIATE = "differentiate"
    HYGIENE = "hygiene"
    STABILIZE = "stabilize"
    EXPAND = "expand"
    SETTLE = "settle"
    EXPLORE = "explore"


@dataclass
class RegulatoryObservation:
    floor_accuracy: float
    final_accuracy: float
    floor_gap: float
    final_gap: float
    debt_mass: float
    debt_total: float
    open_context_mass: float
    spread: float
    uncertainty: float
    conflict: float
    ambiguity: float
    provisional_ambiguity: float
    hidden_ambiguity: float
    commitment_hardness: float
    progress_velocity: float
    stall: float
    failed_hygiene_persistence: float
    slice_efficiency: float
    growth_pressure: float
    growth_readiness: float
    active_growth: float
    pending_growth: float
    budget_saturation: float


@dataclass
class RegulatoryPrimitiveState:
    activation: float = 0.0
    provisional_support: float = 0.0
    durable_support: float = 0.0
    credit: float = 0.0
    debt: float = 0.0
    velocity: float = 0.0
    age: int = 0
    last_effect: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "activation": round(self.activation, 4),
            "provisional_support": round(self.provisional_support, 4),
            "durable_support": round(self.durable_support, 4),
            "credit": round(self.credit, 4),
            "debt": round(self.debt, 4),
            "velocity": round(self.velocity, 4),
            "age": float(self.age),
            "last_effect": round(self.last_effect, 4),
        }


@dataclass
class RegulatoryComposition:
    budget_target: float
    pressure_level: float
    hygiene_level: float
    growth_drive: float
    portfolio_drive: float
    settlement_confidence: float
    primitive_drives: Dict[str, float] = field(default_factory=dict)
    primitive_states: Dict[str, Dict[str, float]] = field(default_factory=dict)
    latent_states: Dict[str, float] = field(default_factory=dict)


@dataclass
class RegulatoryLatentState:
    poisoned: float = 0.0
    recoverable_branch: float = 0.0
    structural_need: float = 0.0
    confidently_wrong: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "poisoned": round(self.poisoned, 4),
            "recoverable_branch": round(self.recoverable_branch, 4),
            "structural_need": round(self.structural_need, 4),
            "confidently_wrong": round(self.confidently_wrong, 4),
        }


class RegulatorySubstrate:
    """Small slow-memory learner over abstract regulatory primitives."""

    _COUPLINGS: Dict[RegulatoryPrimitive, Dict[RegulatoryPrimitive, float]] = {
        RegulatoryPrimitive.DIFFERENTIATE: {
            RegulatoryPrimitive.EXPLORE: 0.18,
            RegulatoryPrimitive.SETTLE: -0.10,
        },
        RegulatoryPrimitive.HYGIENE: {
            RegulatoryPrimitive.SETTLE: -0.18,
            RegulatoryPrimitive.STABILIZE: -0.08,
        },
        RegulatoryPrimitive.STABILIZE: {
            RegulatoryPrimitive.SETTLE: 0.18,
            RegulatoryPrimitive.EXPAND: -0.14,
            RegulatoryPrimitive.EXPLORE: -0.10,
        },
        RegulatoryPrimitive.EXPAND: {
            RegulatoryPrimitive.DIFFERENTIATE: 0.16,
            RegulatoryPrimitive.EXPLORE: 0.10,
        },
        RegulatoryPrimitive.SETTLE: {
            RegulatoryPrimitive.STABILIZE: 0.16,
            RegulatoryPrimitive.EXPLORE: -0.16,
        },
        RegulatoryPrimitive.EXPLORE: {
            RegulatoryPrimitive.DIFFERENTIATE: 0.14,
            RegulatoryPrimitive.SETTLE: -0.14,
        },
    }

    def __init__(self) -> None:
        self.states: Dict[RegulatoryPrimitive, RegulatoryPrimitiveState] = {
            primitive: RegulatoryPrimitiveState()
            for primitive in RegulatoryPrimitive
        }
        self.latents = RegulatoryLatentState()
        self._last_observation: RegulatoryObservation | None = None
        self._last_composition: RegulatoryComposition | None = None

    def reset(self) -> None:
        for primitive in RegulatoryPrimitive:
            self.states[primitive] = RegulatoryPrimitiveState()
        self.latents = RegulatoryLatentState()
        self._last_observation = None
        self._last_composition = None

    def step(
        self,
        observation: RegulatoryObservation,
        *,
        current_budget: int,
    ) -> RegulatoryComposition:
        if self._last_observation is not None and self._last_composition is not None:
            self._apply_feedback(self._last_observation, observation, self._last_composition)
        self._observe(observation)
        composition = self._compose(observation, current_budget=current_budget)
        self._last_observation = observation
        self._last_composition = composition
        return composition

    def _observe(self, observation: RegulatoryObservation) -> None:
        self._update_latents(observation)
        base_targets: Dict[RegulatoryPrimitive, float] = {}
        for primitive, state in self.states.items():
            demand = self._primitive_demand(primitive, observation)
            base_targets[primitive] = _clamp01(
                0.55 * demand
                + 0.25 * state.provisional_support
                + 0.20 * state.durable_support
            )
        coupled_targets = self._apply_couplings(base_targets)
        for primitive, state in self.states.items():
            target = coupled_targets[primitive]
            previous_activation = state.activation
            state.activation = _clamp01(0.55 * state.activation + 0.45 * target)
            state.velocity = 0.60 * state.velocity + 0.40 * (state.activation - previous_activation)
            state.age = state.age + 1 if state.activation >= 0.08 else 0

    def _apply_feedback(
        self,
        previous: RegulatoryObservation,
        current: RegulatoryObservation,
        composition: RegulatoryComposition,
    ) -> None:
        for primitive, state in self.states.items():
            drive = float(composition.primitive_drives.get(primitive.value, 0.0))
            if drive <= 0.02:
                state.credit *= 0.96
                state.debt *= 0.97
                state.provisional_support *= 0.98
                state.durable_support *= 0.995
                state.last_effect = 0.0
                continue

            effect = self._feedback_signal(primitive, previous, current)
            state.last_effect = effect
            if effect >= 0.0:
                credit_target = effect * max(0.15, drive)
                debt_target = 0.0
            else:
                credit_target = 0.0
                debt_target = (-effect) * max(0.15, drive)

            state.credit = _clamp01(0.80 * state.credit + 0.35 * credit_target)
            state.debt = _clamp01(0.84 * state.debt + 0.35 * debt_target)

            provisional_target = _clamp01(
                state.activation + 0.40 * state.credit - 0.28 * state.debt
            )
            state.provisional_support = _clamp01(
                0.72 * state.provisional_support + 0.28 * provisional_target
            )

            durable_target = _clamp01(
                state.provisional_support * max(0.0, state.credit - 0.45 * state.debt)
            )
            state.durable_support = _clamp01(
                0.88 * state.durable_support + 0.12 * durable_target
            )
            if effect < 0.0 and state.debt > 0.55:
                state.durable_support *= 0.94

    def _compose(
        self,
        observation: RegulatoryObservation,
        *,
        current_budget: int,
    ) -> RegulatoryComposition:
        drives = {
            primitive.value: _clamp01(
                0.50 * state.activation
                + 0.30 * state.provisional_support
                + 0.20 * state.durable_support
                + 0.12 * state.credit
                - 0.10 * state.debt
            )
            for primitive, state in self.states.items()
        }

        pressure_level = _clamp01(
            0.42 * drives[RegulatoryPrimitive.DIFFERENTIATE.value]
            + 0.22 * drives[RegulatoryPrimitive.HYGIENE.value]
            + 0.20 * drives[RegulatoryPrimitive.EXPLORE.value]
            + 0.08 * drives[RegulatoryPrimitive.EXPAND.value]
            + 0.08 * observation.conflict
            + 0.10 * self.latents.structural_need
            + 0.08 * self.latents.confidently_wrong
            - 0.12 * drives[RegulatoryPrimitive.STABILIZE.value]
            - 0.14 * drives[RegulatoryPrimitive.SETTLE.value]
        )
        hygiene_level = _clamp01(
            0.48 * drives[RegulatoryPrimitive.HYGIENE.value]
            + 0.16 * drives[RegulatoryPrimitive.DIFFERENTIATE.value]
            + 0.08 * drives[RegulatoryPrimitive.EXPLORE.value]
            + 0.10 * observation.failed_hygiene_persistence
            + 0.08 * observation.conflict
            + 0.22 * self.latents.poisoned
            + 0.08 * self.latents.confidently_wrong
            - 0.08 * drives[RegulatoryPrimitive.STABILIZE.value]
        )
        growth_drive = _clamp01(
            0.42 * drives[RegulatoryPrimitive.EXPAND.value]
            + 0.12 * drives[RegulatoryPrimitive.DIFFERENTIATE.value]
            + 0.10 * drives[RegulatoryPrimitive.EXPLORE.value]
            + 0.12 * observation.growth_pressure
            + 0.12 * observation.growth_readiness
            + 0.22 * self.latents.structural_need
            + 0.06 * self.latents.recoverable_branch
        )
        portfolio_drive = _clamp01(
            0.42 * drives[RegulatoryPrimitive.EXPLORE.value]
            + 0.18 * drives[RegulatoryPrimitive.DIFFERENTIATE.value]
            + 0.10 * drives[RegulatoryPrimitive.EXPAND.value]
            + 0.08 * observation.failed_hygiene_persistence
            + 0.08 * observation.budget_saturation
            + 0.06 * observation.stall
            + 0.16 * self.latents.confidently_wrong
            + 0.08 * self.latents.recoverable_branch
            - 0.08 * drives[RegulatoryPrimitive.STABILIZE.value]
        )
        settlement_confidence = _clamp01(
            0.50 * drives[RegulatoryPrimitive.SETTLE.value]
            + 0.18 * drives[RegulatoryPrimitive.STABILIZE.value]
            + 0.16 * observation.final_accuracy
            + 0.16 * observation.floor_accuracy
            - 0.18 * drives[RegulatoryPrimitive.HYGIENE.value]
            - 0.14 * drives[RegulatoryPrimitive.EXPLORE.value]
        )

        budget_scale = (
            0.82
            + 0.26 * drives[RegulatoryPrimitive.DIFFERENTIATE.value]
            + 0.22 * drives[RegulatoryPrimitive.EXPLORE.value]
            + 0.16 * drives[RegulatoryPrimitive.EXPAND.value]
            + 0.18 * self.latents.structural_need
            - 0.26 * drives[RegulatoryPrimitive.SETTLE.value]
            - 0.10 * drives[RegulatoryPrimitive.STABILIZE.value]
        )
        budget_scale = max(0.70, min(1.55, budget_scale))
        budget_target = max(1.0, round(float(current_budget) * budget_scale))

        return RegulatoryComposition(
            budget_target=float(budget_target),
            pressure_level=pressure_level,
            hygiene_level=hygiene_level,
            growth_drive=growth_drive,
            portfolio_drive=portfolio_drive,
            settlement_confidence=settlement_confidence,
            primitive_drives={key: round(value, 4) for key, value in drives.items()},
            primitive_states={
                primitive.value: state.to_dict()
                for primitive, state in self.states.items()
            },
            latent_states=self.latents.to_dict(),
        )

    def _update_latents(self, observation: RegulatoryObservation) -> None:
        poisoned_target = _clamp01(
            0.34 * observation.conflict
            + 0.26 * observation.failed_hygiene_persistence
            + 0.22 * observation.debt_mass
            + 0.18 * max(0.0, observation.commitment_hardness - observation.provisional_ambiguity)
        )
        recoverable_target = _clamp01(
            0.30 * observation.spread
            + 0.24 * observation.debt_mass
            + 0.18 * observation.provisional_ambiguity
            + 0.16 * observation.hidden_ambiguity
            + 0.12 * (1.0 - observation.stall)
        )
        structural_need_target = _clamp01(
            0.34 * max(observation.debt_mass, observation.floor_gap)
            + 0.22 * observation.stall
            + 0.20 * observation.growth_readiness
            + 0.14 * observation.growth_pressure
            + 0.10 * observation.open_context_mass
        )
        confidently_wrong_target = _clamp01(
            0.34 * max(0.0, observation.commitment_hardness - observation.provisional_ambiguity)
            + 0.24 * observation.floor_gap
            + 0.18 * observation.spread
            + 0.14 * observation.failed_hygiene_persistence
            + 0.10 * observation.stall
        )
        self.latents.poisoned = _clamp01(0.72 * self.latents.poisoned + 0.28 * poisoned_target)
        self.latents.recoverable_branch = _clamp01(
            0.70 * self.latents.recoverable_branch + 0.30 * recoverable_target
        )
        self.latents.structural_need = _clamp01(
            0.72 * self.latents.structural_need + 0.28 * structural_need_target
        )
        self.latents.confidently_wrong = _clamp01(
            0.72 * self.latents.confidently_wrong + 0.28 * confidently_wrong_target
        )

    def _apply_couplings(
        self,
        base_targets: Dict[RegulatoryPrimitive, float],
    ) -> Dict[RegulatoryPrimitive, float]:
        adjusted = dict(base_targets)
        for source, targets in self._COUPLINGS.items():
            source_state = self.states[source]
            source_signal = _clamp01(
                0.50 * source_state.activation
                + 0.30 * source_state.provisional_support
                + 0.20 * source_state.durable_support
            )
            for target, weight in targets.items():
                adjusted[target] = _clamp01(adjusted[target] + weight * source_signal)
        return adjusted

    def _primitive_demand(
        self,
        primitive: RegulatoryPrimitive,
        observation: RegulatoryObservation,
    ) -> float:
        if primitive is RegulatoryPrimitive.DIFFERENTIATE:
            return _clamp01(
                0.38 * observation.debt_mass
                + 0.20 * observation.debt_total
                + 0.18 * observation.spread
                + 0.14 * observation.floor_gap
                + 0.10 * max(0.0, observation.commitment_hardness - observation.provisional_ambiguity)
                + 0.10 * self.latents.recoverable_branch
                + 0.08 * self.latents.confidently_wrong
            )
        if primitive is RegulatoryPrimitive.HYGIENE:
            return _clamp01(
                0.42 * observation.conflict
                + 0.22 * observation.failed_hygiene_persistence
                + 0.16 * observation.spread
                + 0.12 * observation.debt_mass
                + 0.08 * max(0.0, observation.commitment_hardness - observation.provisional_ambiguity)
                + 0.12 * self.latents.poisoned
            )
        if primitive is RegulatoryPrimitive.STABILIZE:
            return _clamp01(
                0.34 * observation.slice_efficiency
                + 0.24 * observation.progress_velocity
                + 0.18 * (1.0 - observation.conflict)
                + 0.12 * observation.final_accuracy
                + 0.12 * observation.floor_accuracy
                + 0.08 * (1.0 - self.latents.confidently_wrong)
            )
        if primitive is RegulatoryPrimitive.EXPAND:
            return _clamp01(
                0.30 * max(observation.debt_mass, 0.7 * observation.floor_gap + 0.3 * observation.final_gap)
                + 0.22 * observation.growth_pressure
                + 0.18 * observation.growth_readiness
                + 0.16 * observation.failed_hygiene_persistence
                + 0.14 * observation.open_context_mass
                + 0.12 * self.latents.structural_need
            )
        if primitive is RegulatoryPrimitive.SETTLE:
            return _clamp01(
                0.32 * observation.floor_accuracy
                + 0.28 * observation.final_accuracy
                + 0.16 * (1.0 - observation.conflict)
                + 0.12 * (1.0 - observation.ambiguity)
                + 0.12 * observation.slice_efficiency
                - 0.16 * observation.debt_mass
                - 0.12 * observation.spread
                - 0.12 * self.latents.poisoned
                - 0.12 * self.latents.confidently_wrong
            )
        if primitive is RegulatoryPrimitive.EXPLORE:
            return _clamp01(
                0.24 * observation.debt_mass
                + 0.18 * observation.failed_hygiene_persistence
                + 0.16 * observation.stall
                + 0.14 * observation.spread
                + 0.14 * max(0.0, observation.commitment_hardness - observation.provisional_ambiguity)
                + 0.14 * observation.budget_saturation
                + 0.10 * self.latents.recoverable_branch
                + 0.10 * self.latents.confidently_wrong
            )
        return 0.0

    def _feedback_signal(
        self,
        primitive: RegulatoryPrimitive,
        previous: RegulatoryObservation,
        current: RegulatoryObservation,
    ) -> float:
        floor_delta = current.floor_accuracy - previous.floor_accuracy
        final_delta = current.final_accuracy - previous.final_accuracy
        spread_reduction = previous.spread - current.spread
        debt_reduction = previous.debt_mass - current.debt_mass
        conflict_reduction = previous.conflict - current.conflict
        ambiguity_retention = current.provisional_ambiguity - previous.provisional_ambiguity
        commitment_softening = (
            previous.commitment_hardness - current.commitment_hardness
        )
        growth_activation = (
            current.active_growth
            + current.pending_growth
            - previous.active_growth
            - previous.pending_growth
        )
        efficiency_delta = current.slice_efficiency - previous.slice_efficiency
        if primitive is RegulatoryPrimitive.DIFFERENTIATE:
            raw = 0.55 * floor_delta + 0.30 * spread_reduction + 0.20 * debt_reduction
        elif primitive is RegulatoryPrimitive.HYGIENE:
            raw = 0.40 * conflict_reduction + 0.35 * debt_reduction + 0.15 * spread_reduction
        elif primitive is RegulatoryPrimitive.STABILIZE:
            raw = 0.35 * final_delta + 0.30 * floor_delta + 0.25 * efficiency_delta - 0.15 * current.spread
        elif primitive is RegulatoryPrimitive.EXPAND:
            raw = 0.30 * floor_delta + 0.25 * growth_activation + 0.20 * debt_reduction + 0.15 * efficiency_delta
        elif primitive is RegulatoryPrimitive.SETTLE:
            raw = 0.45 * floor_delta + 0.35 * final_delta + 0.20 * conflict_reduction - 0.25 * current.debt_mass
        else:
            raw = 0.28 * floor_delta + 0.22 * ambiguity_retention + 0.18 * commitment_softening + 0.16 * debt_reduction
        return max(-1.0, min(1.0, raw))
