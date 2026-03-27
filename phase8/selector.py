from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple

from real_core.types import SelectionContext

from .environment import RoutingEnvironment
from .substrate import ConnectionSubstrate

ROUTE_TRANSFORMS = ("identity", "rotate_left_1", "xor_mask_1010", "xor_mask_0101")


def _route_neighbor(action: str) -> str | None:
    if action.startswith("route_transform:"):
        parts = action.split(":")
        if len(parts) == 3:
            return parts[1]
        return None
    if action.startswith("route:"):
        return action.split(":", 1)[1]
    return None


def _route_transform(action: str) -> str:
    if action.startswith("route_transform:"):
        parts = action.split(":")
        if len(parts) == 3:
            return parts[2]
    return "identity"


@dataclass
class Phase8Selector:
    """Local selector tuned for routing pressure and substrate bias."""

    environment: RoutingEnvironment
    node_id: str
    substrate: ConnectionSubstrate
    rng: random.Random = field(default_factory=random.Random)
    exploration_rate: float = 0.10
    transfer_exploration_boost: float = 0.12
    recency_half_life: float = 6.0
    rest_atp_threshold: float = 0.12
    maintain_velocity_threshold: float = -0.015
    recognition_route_bonus: float = 0.12
    recognition_route_penalty: float = 0.10
    recognition_transform_bonus: float = 0.10
    prediction_delta_bonus: float = 0.12
    prediction_coherence_bonus: float = 0.08
    prediction_stale_family_penalty: float = 0.20
    partial_context_sequence_bonus: float = 0.14
    partial_context_sequence_penalty: float = 0.12
    # Bonus weight applied to task-affinity transforms when the node is in
    # hidden-context mode (head packet carries a task_id but no explicit or
    # latent context bit is resolved yet).  Gives an early-cycle push toward
    # the correct transform family based purely on the task label, without
    # relaxing the context-promotion gate in the consolidation pipeline.
    hidden_task_affinity_weight: float = 0.14
    capture_route_breakdowns: bool = False
    _current_selection_context: SelectionContext | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _last_route_score_breakdowns: dict[str, dict[str, float | int | str | None]] | None = field(
        default=None,
        init=False,
        repr=False,
    )

    def select(self, available: List[str], history: List[object]) -> Tuple[str, str]:
        if not available:
            raise ValueError("No available actions")

        route_actions = [action for action in available if _route_neighbor(action) is not None]
        invest_actions = [action for action in available if action.startswith("invest:")]
        maintain_actions = [action for action in available if action == "maintain_edges"]
        growth_actions = [
            action
            for action in available
            if action.startswith("bud_edge:") or action.startswith("bud_node:")
        ]
        prune_actions = [action for action in available if action.startswith("prune_edge:")]
        apoptosis_actions = [action for action in available if action == "apoptosis_request"]
        rest_available = "rest" in available

        local_inbox = len(self.environment.inboxes[self.node_id])
        state = self.environment.state_for(self.node_id)
        observation = self.environment.observe_local(self.node_id)
        urgency = max(
            observation.get("oldest_packet_age", 0.0),
            observation.get("queue_pressure", 0.0),
            observation.get("ingress_backlog", 0.0),
        )

        if growth_actions and self._can_interrupt_routing(growth_actions, local_inbox, urgency, observation, history):
            return self._best_growth_action(growth_actions), "guided"

        if local_inbox > 0 and route_actions:
            if self.rng.random() < self._local_exploration_rate(history, local_inbox, urgency, observation):
                return self._sample_routes(route_actions, history), "fluctuation"
            return self._best_route(route_actions, history), "guided"

        if state.atp <= self.rest_atp_threshold and rest_available:
            return "rest", "constraint"

        if growth_actions and self._should_prioritize_growth(growth_actions):
            return self._best_growth_action(growth_actions), "guided"

        if maintain_actions and self._needs_maintenance():
            return "maintain_edges", "guided"

        if prune_actions:
            return self._best_growth_action(prune_actions), "guided"

        if growth_actions:
            return self._best_growth_action(growth_actions), "guided"

        if apoptosis_actions:
            return apoptosis_actions[0], "constraint"

        if invest_actions:
            if self.rng.random() < 0.25:
                return self._best_invest(invest_actions, history), "guided"

        if rest_available:
            return "rest", "constraint"

        if invest_actions:
            return self._best_invest(invest_actions, history), "constraint"

        return available[0], "constraint"

    def select_with_context(
        self,
        available: List[str],
        history: List[object],
        context: SelectionContext,
    ) -> Tuple[str, str]:
        self._current_selection_context = context
        try:
            return self.select(available, history)
        finally:
            self._current_selection_context = None

    def _local_exploration_rate(
        self,
        history: List[object],
        local_inbox: int,
        urgency: float,
        observation: dict[str, float],
    ) -> float:
        maturity = min(1.0, len(history) / 24.0)
        pressure_discount = min(0.06, local_inbox * 0.02)
        urgency_discount = min(0.05, urgency * 0.08)
        ambiguity = max(
            0.0,
            min(1.0, observation.get("provisional_context_ambiguity", 0.0)),
        )
        commitment_margin = max(
            0.0,
            min(1.0, observation.get("transform_commitment_margin", 1.0)),
        )
        ambiguity_exploration = 0.14 * ambiguity + 0.10 * max(0.0, 1.0 - commitment_margin)
        transfer_exploration = 0.0
        if (
            self.node_id == self.environment.source_id
            and observation.get("transfer_hidden_unseen_task", 0.0) >= 0.5
        ):
            transfer_phase = max(
                0.0,
                min(1.0, observation.get("transfer_adaptation_phase", 0.0)),
            )
            transfer_exploration = self.transfer_exploration_boost * transfer_phase
        return max(
            0.01,
            min(
                0.35,
                self.exploration_rate * (1.0 - 0.7 * maturity)
                - pressure_discount
                - urgency_discount
                + ambiguity_exploration
                + transfer_exploration,
            ),
        )

    def _best_route(self, route_actions: List[str], history: List[object]) -> str:
        route_scores = self._score_routes(route_actions, history)
        scored = [(route_scores[action], action) for action in route_actions]
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    def _sample_routes(self, route_actions: List[str], history: List[object]) -> str:
        route_scores = self._score_routes(route_actions, history)
        observation = self.environment.observe_local(self.node_id)
        ambiguity = max(
            0.0,
            min(1.0, observation.get("provisional_context_ambiguity", 0.0)),
        )
        commitment_margin = max(
            0.0,
            min(1.0, observation.get("transform_commitment_margin", 1.0)),
        )
        temperature = 1.0 + 1.6 * ambiguity + 0.8 * max(0.0, 1.0 - commitment_margin)
        max_score = max(route_scores.values()) if route_scores else 0.0
        scores = [
            max(
                0.01,
                math.exp((route_scores[action] - max_score) / max(temperature, 1e-6)),
            )
            for action in route_actions
        ]
        return self.rng.choices(route_actions, weights=scores, k=1)[0]

    def _best_invest(self, invest_actions: List[str], history: List[object]) -> str:
        scored = [(self._score_invest(action, history), action) for action in invest_actions]
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    def _best_growth_action(self, actions: List[str]) -> str:
        scored = [(self._score_growth_action(action), action) for action in actions]
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    def _effective_context(self, observation: dict[str, float]) -> tuple[int | None, float]:
        if observation.get("effective_has_context", 0.0) < 0.5:
            if observation.get("packet_has_context", 0.0) >= 0.5:
                return int(observation.get("packet_context_bit", observation.get("head_context_bit", 0.0))), max(
                    0.0,
                    min(1.0, observation.get("packet_context_confidence", 0.0)),
                )
            return None, 0.0
        return int(observation.get("effective_context_bit", 0.0)), max(
            0.0,
            min(1.0, observation.get("effective_context_confidence", 0.0)),
        )

    def _entry_effective_context(self, entry: object) -> tuple[int | None, float]:
        state_before = getattr(entry, "state_before", {})
        if state_before.get("effective_has_context", 0.0) >= 0.5:
            return int(float(state_before.get("effective_context_bit", 0.0))), max(
                0.0,
                min(1.0, float(state_before.get("effective_context_confidence", 0.0))),
            )
        if state_before.get("packet_has_context", 0.0) >= 0.5:
            return int(float(state_before.get("packet_context_bit", state_before.get("head_context_bit", 0.0)))), max(
                0.0,
                min(1.0, float(state_before.get("packet_context_confidence", 0.0))),
            )
        if state_before.get("head_has_context", 0.0) >= 0.5:
            return int(float(state_before.get("head_context_bit", 0.0))), 1.0
        return None, 0.0

    def debug_route_score_breakdown(
        self,
        action: str,
        history: List[object],
    ) -> dict[str, float | int | str | None]:
        breakdown = self._score_route(action, history, return_breakdown=True)
        assert isinstance(breakdown, dict)
        return breakdown

    def latest_route_score_breakdowns(
        self,
    ) -> dict[str, dict[str, float | int | str | None]] | None:
        if self._last_route_score_breakdowns is None:
            return None
        return {
            action: dict(details)
            for action, details in self._last_route_score_breakdowns.items()
        }

    def _score_route(
        self,
        action: str,
        history: List[object],
        *,
        return_breakdown: bool = False,
    ) -> float | dict[str, float | int | str | None]:
        neighbor_id = _route_neighbor(action)
        if neighbor_id is None:
            return -1.0 if not return_breakdown else {"action": action, "total": -1.0}
        observation = self.environment.observe_local(self.node_id)

        recent_delta = self._recency_weighted_mean(history, action, field="delta", default=0.0)
        recent_coherence = self._recency_weighted_mean(history, action, field="coherence", default=0.5)
        context_bit, context_weight = self._effective_context(observation)
        context_delta = self._contextual_route_mean(
            history,
            action,
            context_bit=context_bit,
            context_weight=context_weight,
            field="delta",
            default=recent_delta,
        )
        support = self.substrate.support(neighbor_id)
        support_velocity = self.substrate.velocity(neighbor_id)
        recognition_bias = self._recognized_route_bias(neighbor_id)
        transform_name = _route_transform(action)
        transform_recognition_bias = self._recognized_transform_bias(
            neighbor_id,
            transform_name,
            context_bit,
        )
        generic_action_support = self.substrate.base_action_support(
            neighbor_id,
            transform_name,
        )
        raw_action_support = self.substrate.action_support(
            neighbor_id,
            transform_name,
            context_bit,
        )
        action_support = raw_action_support
        generic_action_velocity = self.substrate.action_velocity(
            neighbor_id,
            transform_name,
            None,
        )
        raw_action_velocity = self.substrate.action_velocity(
            neighbor_id,
            transform_name,
            context_bit,
        )
        action_velocity = raw_action_velocity
        history_transform_evidence = observation.get(
            f"history_transform_evidence_{transform_name}",
            0.0,
        )
        best_non_identity_history = max(
            (
                observation.get(f"history_transform_evidence_{candidate}", 0.0)
                for candidate in ROUTE_TRANSFORMS
                if candidate != "identity"
            ),
            default=0.0,
        )
        task_transform_affinity = observation.get(
            f"task_transform_affinity_{transform_name}",
            0.0,
        )
        source_sequence_hint = observation.get(
            f"source_sequence_transform_hint_{transform_name}",
            0.0,
        )
        source_sequence_available = observation.get("source_sequence_available", 0.0)
        source_sequence_change_ratio = observation.get("source_sequence_change_ratio", 0.0)
        source_sequence_repeat = observation.get("source_sequence_repeat_input", 0.0)
        latent_resolution_weight = observation.get("latent_resolution_weight", 1.0)
        latent_context_count = int(round(observation.get("latent_context_count", 2.0)))
        transfer_adaptation_phase = max(
            0.0,
            min(1.0, observation.get("transfer_adaptation_phase", 0.0)),
        )
        transfer_hidden_unseen_task = (
            self.node_id == self.environment.source_id
            and observation.get("transfer_hidden_unseen_task", 0.0) >= 0.5
        )
        hidden_task_commitment = (
            observation.get("head_has_task", 0.0) >= 0.5
            and observation.get("head_has_context", 0.0) < 0.5
            and observation.get("effective_has_context", 0.0) < 0.5
        )
        feedback_credit = observation.get(f"feedback_credit_{transform_name}", 0.0)
        provisional_feedback_credit = observation.get(
            f"provisional_feedback_credit_{transform_name}",
            0.0,
        )
        feedback_debt = observation.get(f"feedback_debt_{transform_name}", 0.0)
        context_feedback_credit = observation.get(
            f"context_feedback_credit_{transform_name}",
            0.0,
        )
        provisional_context_feedback_credit = observation.get(
            f"provisional_context_feedback_credit_{transform_name}",
            0.0,
        )
        context_feedback_debt = observation.get(
            f"context_feedback_debt_{transform_name}",
            0.0,
        )
        branch_feedback_debt = observation.get(
            f"branch_feedback_debt_{neighbor_id}_{transform_name}",
            0.0,
        )
        branch_feedback_credit = observation.get(
            f"branch_feedback_credit_{neighbor_id}_{transform_name}",
            0.0,
        )
        context_branch_feedback_debt = observation.get(
            f"context_branch_feedback_debt_{neighbor_id}_{transform_name}",
            0.0,
        )
        context_branch_feedback_credit = observation.get(
            f"context_branch_feedback_credit_{neighbor_id}_{transform_name}",
            0.0,
        )
        branch_context_feedback_debt = observation.get(
            f"branch_context_feedback_debt_{neighbor_id}",
            0.0,
        )
        branch_context_feedback_credit = observation.get(
            f"branch_context_feedback_credit_{neighbor_id}",
            0.0,
        )
        last_match_ratio = observation.get("last_match_ratio", 0.0)
        last_feedback_amount = observation.get("last_feedback_amount", 0.0)
        identity_penalty = 0.0
        task_transform_bonus = 0.0
        context_support_bonus = 0.0
        context_support_penalty = 0.0
        history_alignment = 1.0
        branch_context_pressure = 0.0
        branch_context_bonus = 0.0
        branch_transform_bonus = 0.0
        competition_penalty = 0.0
        competition_bonus = 0.0
        growth_novelty_bonus = 0.0
        source_pre_effective_route_drive = 0.0
        hidden_wrong_family_penalty = 0.0
        visible_task_compatibility_bonus = 0.0
        visible_task_incompatibility_penalty = 0.0
        partial_context_sequence_bonus = 0.0
        partial_context_sequence_penalty = 0.0
        transform_recognition_confirmation = 0.0
        if self.environment.topology_state is not None:
            neighbor_spec = self.environment.topology_state.node_specs.get(neighbor_id)
            if neighbor_spec is not None and neighbor_spec.dynamic:
                growth_novelty_bonus += self.environment.morphogenesis_config.growth_route_novelty_bonus
            if neighbor_spec is not None and neighbor_spec.probationary:
                growth_novelty_bonus += self.environment.morphogenesis_config.growth_route_probationary_bonus
        source_pre_effective = (
            hidden_task_commitment
            and self.node_id == self.environment.source_id
            and observation.get("has_packet", 0.0) >= 0.5
            and source_sequence_available >= 0.5
        )
        if hidden_task_commitment:
            sequence_hint_scale = (
                1.0 - 0.75 * transfer_adaptation_phase
                if transfer_hidden_unseen_task
                else 1.0
            )
            source_sequence_hint *= sequence_hint_scale
            sequence_bonus_scale = (
                0.18 * sequence_hint_scale
                if source_sequence_available >= 0.5
                else 0.0
            )
            sequence_repeat_penalty = 0.04 * source_sequence_repeat
            transfer_candidate_bonus = (
                0.04 * transfer_adaptation_phase
                if transfer_hidden_unseen_task and task_transform_affinity > 0.0
                else 0.0
            )
            if transform_name == "identity":
                identity_penalty += (
                    0.06
                    + 0.08 * min(1.0, best_non_identity_history)
                    + max(0.0, -source_sequence_hint) * sequence_bonus_scale
                    + sequence_repeat_penalty
                )
                if transfer_hidden_unseen_task:
                    identity_penalty += 0.05 * transfer_adaptation_phase
                if source_pre_effective:
                    identity_penalty += (
                        0.12
                        + 0.10 * max(0.0, -source_sequence_hint)
                        + 0.04 * source_sequence_change_ratio
                    )
            elif task_transform_affinity > 0.0:
                task_transform_bonus += (
                    0.05
                    + 0.08 * history_transform_evidence
                    + max(0.0, source_sequence_hint) * sequence_bonus_scale
                    + 0.03 * source_sequence_change_ratio
                    + transfer_candidate_bonus
                )
                if source_pre_effective:
                    pre_effective_drive_scale = (
                        1.0 - 0.55 * transfer_adaptation_phase
                        if transfer_hidden_unseen_task
                        else 1.0
                    )
                    source_pre_effective_route_drive += (
                        (
                            0.10
                            + 0.12 * max(0.0, source_sequence_hint)
                            + 0.05 * source_sequence_change_ratio
                            + 0.04 * observation.get("ingress_backlog", 0.0)
                            + 0.03 * observation.get("reward_buffer", 0.0)
                        )
                        * pre_effective_drive_scale
                    )
            elif task_transform_affinity < 0.0:
                hidden_wrong_family_penalty += 0.04 + max(0.0, source_sequence_hint) * 0.14
                if source_pre_effective:
                    hidden_wrong_family_penalty += 0.08 + 0.06 * source_sequence_change_ratio
        elif transform_name == "identity" and best_non_identity_history > 0.12:
            identity_penalty += 0.18 * min(1.0, best_non_identity_history)
        elif transform_name != "identity":
            task_transform_bonus += 0.12 * history_transform_evidence
        partial_multistate_context = (
            self.node_id == self.environment.source_id
            and source_sequence_available >= 0.5
            and latent_context_count > 2
            and (
                observation.get("effective_has_context", 0.0) >= 0.5
                or observation.get("latent_capability_enabled", 0.0) >= 0.5
            )
        )
        if partial_multistate_context and transform_name != "identity":
            uncertainty = max(0.0, 1.0 - latent_resolution_weight)
            confidence_softness = max(
                0.0,
                0.85 - observation.get("effective_context_confidence", 0.0),
            )
            sequence_persistence_weight = max(
                0.0,
                min(
                    1.0,
                    0.55 * uncertainty + 0.45 * confidence_softness,
                ),
            )
            if source_sequence_hint > 0.0:
                partial_context_sequence_bonus = (
                    self.partial_context_sequence_bonus
                    * sequence_persistence_weight
                    * source_sequence_hint
                )
                task_transform_bonus += partial_context_sequence_bonus
            elif source_sequence_hint < 0.0:
                partial_context_sequence_penalty = (
                    self.partial_context_sequence_penalty
                    * sequence_persistence_weight
                    * max(0.0, -source_sequence_hint)
                )
                hidden_wrong_family_penalty += partial_context_sequence_penalty
        if context_bit is not None:
            (
                raw_context_action_support,
                context_action_support,
                transfer_context_support_scale,
            ) = self._effective_context_action_support(
                neighbor_id=neighbor_id,
                transform_name=transform_name,
                context_bit=context_bit,
                observation=observation,
                task_transform_affinity=task_transform_affinity,
                history_transform_evidence=history_transform_evidence,
                feedback_credit=feedback_credit,
                context_feedback_credit=context_feedback_credit,
                branch_feedback_credit=branch_feedback_credit,
                context_branch_feedback_credit=context_branch_feedback_credit,
                branch_context_feedback_credit=branch_context_feedback_credit,
                feedback_debt=feedback_debt,
                context_feedback_debt=context_feedback_debt,
                branch_feedback_debt=branch_feedback_debt,
                context_branch_feedback_debt=context_branch_feedback_debt,
                branch_context_feedback_debt=branch_context_feedback_debt,
            )
            context_action_velocity = self.substrate.contextual_action_velocity(
                neighbor_id,
                transform_name,
                context_bit,
            )
            action_support = max(generic_action_support, context_action_support)
            action_velocity = max(
                generic_action_velocity,
                context_action_velocity * transfer_context_support_scale,
            )
            context_support_bonus = max(
                0.0,
                context_action_support - generic_action_support,
            ) * (0.18 * context_weight) + max(
                0.0,
                context_action_velocity * transfer_context_support_scale,
            ) * (0.08 * context_weight)
            context_support_penalty = max(
                0.0,
                generic_action_support - context_action_support,
            ) * (0.12 * context_weight)
            context_evidence = min(
                1.0,
                max(
                    0.0,
                    0.55 * history_transform_evidence
                    + context_action_support
                    + context_feedback_credit
                    + 0.35 * branch_feedback_credit
                    + 0.60 * context_branch_feedback_credit
                    + 0.55 * branch_context_feedback_credit
                    - 0.55 * context_feedback_debt
                    - 0.25 * context_branch_feedback_debt
                    + 0.35 * max(0.0, last_match_ratio - 0.5),
                ),
            )
            branch_context_pressure = max(
                0.0,
                branch_context_feedback_debt
                - 0.40 * branch_context_feedback_credit
                - 0.25 * context_feedback_credit
                - 0.20 * context_action_support,
            )
            branch_context_bonus = 0.20 * branch_context_feedback_credit * context_weight
            branch_transform_bonus = (
                0.10 * branch_feedback_credit + 0.22 * context_branch_feedback_credit
            ) * context_weight
            history_alignment = 0.55 + 0.45 * context_evidence
            history_alignment *= max(0.30, 1.0 - 0.40 * branch_context_pressure)
            if not hidden_task_commitment and transform_name != "identity":
                compatibility_resolution = max(
                    transfer_adaptation_phase,
                    1.0 - transfer_context_support_scale,
                )
                if task_transform_affinity > 0.0:
                    visible_task_compatibility_bonus = (
                        0.05 + 0.10 * compatibility_resolution
                    ) * context_weight
                elif task_transform_affinity < 0.0:
                    visible_task_incompatibility_penalty = (
                        0.04
                        + 0.10 * compatibility_resolution
                        + 0.18 * raw_context_action_support
                    ) * context_weight
            if (
                transform_name == "identity"
                and action_support < 0.35
                and feedback_credit < 0.35
                and context_feedback_credit < 0.30
            ):
                identity_penalty = 0.14 * context_weight
            elif transform_name != "identity" and context_feedback_debt < 0.45:
                task_transform_bonus = 0.08 * max(context_weight, min(1.0, 0.35 + history_transform_evidence))
            competition_penalty, competition_bonus = self._competition_adjustment(
                neighbor_id=neighbor_id,
                transform_name=transform_name,
                context_bit=context_bit,
                observation=observation,
                action_support=action_support,
                generic_action_support=generic_action_support,
                feedback_credit=feedback_credit,
                provisional_feedback_credit=provisional_feedback_credit,
                context_feedback_credit=context_feedback_credit,
                provisional_context_feedback_credit=provisional_context_feedback_credit,
                branch_feedback_credit=branch_feedback_credit,
                context_branch_feedback_credit=context_branch_feedback_credit,
                branch_context_feedback_credit=branch_context_feedback_credit,
                feedback_debt=feedback_debt,
                context_feedback_debt=context_feedback_debt,
                branch_feedback_debt=branch_feedback_debt,
                context_branch_feedback_debt=context_branch_feedback_debt,
                branch_context_feedback_debt=branch_context_feedback_debt,
            )
            competition_penalty *= context_weight
            competition_bonus *= context_weight
        branch_escape_bonus = 0.0
        if context_bit is not None:
            competing_branch_debt = max(
                (
                    observation.get(f"branch_context_feedback_debt_{candidate_neighbor}", 0.0)
                    for candidate_neighbor in self.environment.neighbors_of(self.node_id)
                    if candidate_neighbor != neighbor_id
                ),
                default=0.0,
            )
            branch_escape_bonus = 0.24 * max(
                0.0,
                competing_branch_debt - branch_context_pressure,
            ) * context_weight
        transform_recognition_confirmation = self._transform_recognition_confirmation(
            history_transform_evidence=history_transform_evidence,
            feedback_credit=feedback_credit,
            context_feedback_credit=context_feedback_credit,
            branch_feedback_credit=branch_feedback_credit,
            context_branch_feedback_credit=context_branch_feedback_credit,
            branch_context_feedback_credit=branch_context_feedback_credit,
            feedback_debt=feedback_debt,
            context_feedback_debt=context_feedback_debt,
            branch_feedback_debt=branch_feedback_debt,
            context_branch_feedback_debt=context_branch_feedback_debt,
            branch_context_pressure=branch_context_pressure,
            context_weight=context_weight,
        )
        transform_recognition_bias *= transform_recognition_confirmation
        (
            prediction_delta_bias,
            prediction_coherence_bias,
            prediction_effective_confidence,
            prediction_stale_family_penalty,
        ) = self._prediction_route_bias(action)
        progress = observation.get(f"progress_{neighbor_id}", 0.0)
        congestion = observation.get(f"congestion_{neighbor_id}", 0.0)
        inhibited = observation.get(f"inhibited_{neighbor_id}", 0.0)
        urgency = observation.get("oldest_packet_age", 0.0)
        queue_pressure = observation.get("queue_pressure", 0.0)
        ingress_backlog = observation.get("ingress_backlog", 0.0)
        provisional_ambiguity = max(
            0.0,
            min(1.0, observation.get("provisional_context_ambiguity", 0.0)),
        )
        commitment_margin = max(
            0.0,
            min(1.0, observation.get("transform_commitment_margin", 1.0)),
        )
        transform_cost = self.substrate.use_cost(
            neighbor_id,
            transform_name if action.startswith("route_transform:") else None,
            context_bit,
        )
        cost_ratio = transform_cost / max(self.substrate.config.fire_base_cost, 1e-9)
        stale_penalty = self._stale_bias_penalty(history, action)
        maintenance = self.substrate.maintenance_metrics()
        context_route_component = (
            (1.0 - context_weight) * recent_delta + context_weight * context_delta
        )

        raw_components = {
            "recent_delta_term": 0.32 * recent_delta * history_alignment,
            "context_route_term": 0.28 * context_route_component * history_alignment,
            "recent_coherence_term": 0.18 * recent_coherence * (0.55 + 0.45 * history_alignment),
            "support_term": 0.30 * support,
            "recognition_route_term": recognition_bias,
            "recognition_transform_term": transform_recognition_bias,
            "recognition_transform_confirmation_term": transform_recognition_confirmation,
            "prediction_delta_term": prediction_delta_bias,
            "prediction_coherence_term": prediction_coherence_bias,
            "prediction_effective_confidence_term": prediction_effective_confidence,
            "prediction_stale_family_penalty_term": prediction_stale_family_penalty,
            "action_support_term": 0.22 * action_support,
            "progress_term": 0.24 * progress,
            "support_velocity_term": 0.08 * support_velocity,
            "action_velocity_term": 0.06 * action_velocity,
            "feedback_credit_term": 0.18 * feedback_credit,
            "provisional_feedback_credit_term": 0.12 * provisional_feedback_credit,
            "context_feedback_credit_term": 0.34 * context_feedback_credit * context_weight,
            "provisional_context_feedback_credit_term": 0.20
            * provisional_context_feedback_credit
            * context_weight,
            "history_transform_term": 0.16 * history_transform_evidence,
            "match_ratio_term": 0.12 * last_match_ratio,
            "last_feedback_term": 0.08 * last_feedback_amount,
            "maintenance_term": 0.06 * maintenance["action_maintenance_ratio"],
            "growth_novelty_term": growth_novelty_bonus,
            "context_support_bonus_term": context_support_bonus,
            "task_transform_bonus_term": task_transform_bonus,
            "source_pre_effective_term": source_pre_effective_route_drive,
            "partial_context_sequence_bonus_term": partial_context_sequence_bonus,
            "visible_task_compatibility_term": visible_task_compatibility_bonus,
            "branch_context_bonus_term": branch_context_bonus,
            "branch_transform_bonus_term": branch_transform_bonus,
            "branch_escape_bonus_term": branch_escape_bonus,
            "urgency_term": 0.20 * urgency,
            "ingress_backlog_term": 0.10 * ingress_backlog,
            "congestion_penalty_term": -0.22 * congestion,
            "cost_penalty_term": -0.18 * cost_ratio,
            "inhibited_penalty_term": -0.35 * inhibited,
            "queue_congestion_penalty_term": -0.12 * queue_pressure * congestion,
            "context_support_penalty_term": -context_support_penalty,
            "feedback_debt_penalty_term": -0.18 * feedback_debt,
            "context_feedback_debt_penalty_term": -0.42 * context_feedback_debt * context_weight,
            "branch_feedback_debt_penalty_term": -0.20 * branch_feedback_debt,
            "context_branch_feedback_debt_penalty_term": -0.48 * context_branch_feedback_debt * context_weight,
            "branch_context_pressure_penalty_term": -0.26 * branch_context_pressure * context_weight,
            "identity_penalty_term": -identity_penalty,
            "hidden_wrong_family_penalty_term": -hidden_wrong_family_penalty,
            "partial_context_sequence_penalty_term": -partial_context_sequence_penalty,
            "visible_task_incompatibility_penalty_term": -visible_task_incompatibility_penalty,
            "competition_penalty_term": -competition_penalty,
            "stale_penalty_term": -stale_penalty,
            "competition_bonus_term": competition_bonus,
            "ambiguity_hold_bonus_term": 0.10
            * provisional_ambiguity
            * max(0.0, 1.0 - commitment_margin)
            * max(0.0, min(1.0, 0.35 + task_transform_affinity)),
        }
        components: dict[str, float | int | str | None] = {
            "action": action,
            "neighbor_id": neighbor_id,
            "transform_name": transform_name,
            "context_bit": context_bit,
            "context_weight": round(context_weight, 6),
            "history_alignment": round(history_alignment, 6),
            "transfer_hidden_unseen_task": 1.0 if transfer_hidden_unseen_task else 0.0,
            "raw_recent_delta": round(recent_delta, 6),
            "raw_context_delta": round(context_delta, 6),
            "raw_support": round(support, 6),
            "raw_action_support": round(raw_action_support, 6),
            "effective_action_support": round(action_support, 6),
            "raw_action_velocity": round(raw_action_velocity, 6),
            "effective_action_velocity": round(action_velocity, 6),
            "raw_task_transform_affinity": round(task_transform_affinity, 6),
            "raw_history_transform_evidence": round(history_transform_evidence, 6),
            "raw_latent_resolution_weight": round(float(latent_resolution_weight), 6),
            "raw_latent_context_count": int(latent_context_count),
            "raw_feedback_credit": round(feedback_credit, 6),
            "raw_provisional_feedback_credit": round(provisional_feedback_credit, 6),
            "raw_context_feedback_credit": round(context_feedback_credit, 6),
            "raw_provisional_context_feedback_credit": round(
                provisional_context_feedback_credit,
                6,
            ),
            "raw_feedback_debt": round(feedback_debt, 6),
            "raw_context_feedback_debt": round(context_feedback_debt, 6),
            "raw_provisional_context_ambiguity": round(provisional_ambiguity, 6),
            "raw_transform_commitment_margin": round(commitment_margin, 6),
            "raw_context_action_support": round(
                raw_context_action_support if context_bit is not None else 0.0,
                6,
            ),
            "effective_context_action_support": round(
                context_action_support if context_bit is not None else 0.0,
                6,
            ),
            "transfer_context_support_scale": round(
                transfer_context_support_scale if context_bit is not None else 1.0,
                6,
            ),
            "raw_last_match_ratio": round(last_match_ratio, 6),
            "raw_transfer_adaptation_phase": round(transfer_adaptation_phase, 6),
        }
        for key, value in raw_components.items():
            components[key] = round(value, 6)
        score = sum(raw_components.values())
        components["total"] = round(score, 6)
        if return_breakdown:
            return components
        return score

    def _recognized_route_bias(self, neighbor_id: str) -> float:
        context = self._current_selection_context
        recognition = None if context is None else context.recognition
        if recognition is None or recognition.confidence <= 0.0 or not recognition.matches:
            return 0.0

        novelty_scale = max(0.0, min(1.0, 1.0 - recognition.novelty))
        if novelty_scale <= 0.0:
            return 0.0

        total_bias = 0.0
        for match in recognition.matches:
            pattern = self._recognized_pattern(match.metadata.get("pattern_index"))
            if pattern is None:
                continue
            focus_neighbor = self._pattern_focus_neighbor(pattern, match.source)
            if focus_neighbor != neighbor_id:
                continue
            match_weight = max(
                0.0,
                min(
                    1.0,
                    recognition.confidence
                    * match.score
                    * max(0.25, float(pattern.strength)),
                ),
            )
            if match.source == "route_attractor" and pattern.valence >= 0.0:
                total_bias += self.recognition_route_bonus * novelty_scale * match_weight
            elif match.source == "route_trough" or pattern.valence < 0.0:
                total_bias -= self.recognition_route_penalty * novelty_scale * match_weight
        return total_bias

    def _prediction_route_bias(
        self,
        action: str,
    ) -> tuple[float, float, float, float]:
        context = self._current_selection_context
        if context is None:
            return 0.0, 0.0, 0.0, 0.0
        prediction = context.predictions.get(action)
        if prediction is None or prediction.confidence <= 0.0:
            return 0.0, 0.0, 0.0, 0.0
        effective_confidence = max(
            0.0,
            min(1.0, prediction.confidence * (1.0 - prediction.uncertainty)),
        )
        if effective_confidence <= 0.0:
            return 0.0, 0.0, 0.0, 0.0
        delta_term = (
            self.prediction_delta_bonus
            * float(prediction.expected_delta or 0.0)
            * effective_confidence
        )
        baseline = 0.5 if context.prior_coherence is None else float(context.prior_coherence)
        coherence_term = (
            self.prediction_coherence_bonus
            * (
                0.0
                if prediction.expected_coherence is None
                else float(prediction.expected_coherence) - baseline
            )
            * effective_confidence
        )
        stale_family_penalty = (
            -self.prediction_stale_family_penalty
            * float(prediction.metadata.get("stale_family_risk", 0.0))
            * effective_confidence
        )
        return (
            delta_term,
            coherence_term,
            effective_confidence,
            stale_family_penalty,
        )

    def _recognized_pattern(self, pattern_index: object):
        if not isinstance(pattern_index, int):
            return None
        patterns = self.substrate.constraint_patterns
        if pattern_index < 0 or pattern_index >= len(patterns):
            return None
        return patterns[pattern_index]

    def _pattern_focus_neighbor(self, pattern, source: str) -> str | None:
        scored_neighbors: list[tuple[float, str]] = []
        for neighbor_id in self.substrate.neighbor_ids:
            key = self.substrate.edge_key(neighbor_id)
            if key not in pattern.dim_scores:
                continue
            scored_neighbors.append((float(pattern.dim_scores[key]), neighbor_id))
        if not scored_neighbors:
            return None
        if source == "route_trough" or pattern.valence < 0.0:
            return min(scored_neighbors, key=lambda item: item[0])[1]
        return max(scored_neighbors, key=lambda item: item[0])[1]

    def _recognized_transform_bias(
        self,
        neighbor_id: str,
        transform_name: str,
        context_bit: int | None,
    ) -> float:
        if self.node_id != self.environment.source_id:
            return 0.0
        if self.recognition_transform_bonus <= 0.0:
            return 0.0
        context = self._current_selection_context
        recognition = None if context is None else context.recognition
        if recognition is None or recognition.confidence <= 0.0 or not recognition.matches:
            return 0.0

        target_action_key = self.substrate.action_key(neighbor_id, transform_name)
        target_signature = (neighbor_id, transform_name)
        target_context_key = None
        if context_bit is not None:
            try:
                target_context_key = self.substrate.context_action_key(
                    neighbor_id,
                    transform_name,
                    context_bit,
                )
            except KeyError:
                target_context_key = None

        total_bias = 0.0
        for match in recognition.matches:
            if match.source not in ("transform_attractor", "context_transform_attractor"):
                continue
            pattern = self._recognized_pattern(match.metadata.get("pattern_index"))
            if pattern is None:
                continue
            focused_key = self._pattern_focus_action_key(pattern, match.source)
            if focused_key is None:
                continue
            focused_signature = self._action_signature_from_key(focused_key)
            weight = max(
                0.0,
                min(
                    1.0,
                    recognition.confidence
                    * match.score
                    * max(0.25, float(pattern.strength)),
                ),
            )
            if focused_key == target_context_key or focused_key == target_action_key:
                total_bias += self.recognition_transform_bonus * weight
                continue
            if focused_signature == target_signature:
                # Allow context-specific transform attractors to bias the
                # underlying base transform action before the exact context key
                # is selectable at the source.
                total_bias += self.recognition_transform_bonus * 0.75 * weight
        return total_bias

    def _transform_recognition_confirmation(
        self,
        *,
        history_transform_evidence: float,
        feedback_credit: float,
        context_feedback_credit: float,
        branch_feedback_credit: float,
        context_branch_feedback_credit: float,
        branch_context_feedback_credit: float,
        feedback_debt: float,
        context_feedback_debt: float,
        branch_feedback_debt: float,
        context_branch_feedback_debt: float,
        branch_context_pressure: float,
        context_weight: float,
    ) -> float:
        positive_support = min(
            1.0,
            max(
                0.0,
                0.55 * history_transform_evidence
                + 0.70 * feedback_credit
                + 0.95 * context_feedback_credit * context_weight
                + 0.30 * branch_feedback_credit
                + 0.55 * context_branch_feedback_credit * context_weight
                + 0.45 * branch_context_feedback_credit * context_weight,
            ),
        )
        if positive_support <= 1e-9:
            return 0.0

        negative_pressure = min(
            1.0,
            max(
                0.0,
                0.55 * feedback_debt
                + 0.90 * context_feedback_debt * context_weight
                + 0.28 * branch_feedback_debt
                + 0.60 * context_branch_feedback_debt * context_weight
                + 0.45 * branch_context_pressure * context_weight,
            ),
        )
        confirmation = positive_support / (positive_support + negative_pressure + 0.20)
        return max(0.0, min(1.0, confirmation))

    def _pattern_focus_action_key(self, pattern, source: str) -> str | None:
        action_scores = [
            (float(value), str(key))
            for key, value in pattern.dim_scores.items()
            if str(key).startswith("action:") or str(key).startswith("context_action:")
        ]
        if not action_scores:
            return None
        if source == "transform_trough" or source == "context_transform_trough" or pattern.valence < 0.0:
            return min(action_scores, key=lambda item: item[0])[1]
        return max(action_scores, key=lambda item: item[0])[1]

    def _action_signature_from_key(
        self,
        key: str,
    ) -> tuple[str, str] | None:
        if key.startswith("action:"):
            parts = key.split(":")
            if len(parts) == 3:
                return parts[1], parts[2]
            return None
        if key.startswith("context_action:"):
            parts = key.split(":")
            if len(parts) == 4:
                return parts[1], parts[2]
            return None
        return None

    def _score_invest(self, action: str, history: List[object]) -> float:
        neighbor_id = action.split(":", 1)[1]
        observation = self.environment.observe_local(self.node_id)
        recent_route_delta = self._route_recency_weighted_mean(history, neighbor_id, field="delta", default=0.0)
        progress = observation.get(f"progress_{neighbor_id}", 0.0)
        congestion = observation.get(f"congestion_{neighbor_id}", 0.0)
        support_gap = 1.0 - self.substrate.support(neighbor_id)
        cost_ratio = self.substrate.write_cost(neighbor_id) / max(self.substrate.config.write_base_cost, 1e-9)
        return (
            0.30 * progress
            + 0.28 * support_gap
            + 0.22 * max(0.0, recent_route_delta)
            - 0.10 * congestion
            - 0.18 * cost_ratio
        )

    def _score_growth_action(self, action: str) -> float:
        observation = self.environment.observe_local(self.node_id)
        contradiction = observation.get("contradiction_pressure", 0.0)
        surplus = observation.get("growth_surplus_streak", 0.0)
        energy_surplus = observation.get("energy_surplus", 0.0)
        energy_balance = observation.get("energy_balance", 0.0)
        structural_value = observation.get("structural_value", 0.0)
        maintenance_load = observation.get("maintenance_load", 0.0)
        overload = max(
            observation.get("queue_pressure", 0.0),
            observation.get("oldest_packet_age", 0.0),
            observation.get("ingress_backlog", 0.0),
        )
        if action.startswith("bud_node:"):
            _, _, target_id = action.split(":", 2)
            progress = observation.get(f"progress_{target_id}", 0.0)
            return (
                0.20
                + 0.26 * contradiction
                + 0.18 * surplus
                + 0.18 * energy_surplus
                + 0.12 * max(0.0, energy_balance)
                + 0.08 * max(0.0, structural_value)
                + 0.10 * overload
                + 0.08 * progress
                - 0.10 * maintenance_load
            )
        if action.startswith("bud_edge:"):
            target_id = action.split(":", 1)[1]
            progress = observation.get(f"progress_{target_id}", 0.0)
            return (
                0.18
                + 0.24 * contradiction
                + 0.18 * surplus
                + 0.20 * energy_surplus
                + 0.14 * max(0.0, energy_balance)
                + 0.08 * max(0.0, structural_value)
                + 0.10 * overload
                + 0.10 * progress
                - 0.08 * maintenance_load
            )
        if action.startswith("prune_edge:"):
            target_id = action.split(":", 1)[1]
            congestion = observation.get(f"congestion_{target_id}", 0.0)
            return 0.22 + 0.28 * max(0.0, -energy_balance) + 0.18 * maintenance_load + 0.14 * congestion + 0.10 * overload
        if action == "apoptosis_request":
            return 0.55 + 0.35 * max(0.0, -structural_value) + 0.20 * maintenance_load
        return 0.0

    def _should_prioritize_growth(self, actions: List[str]) -> bool:
        if not actions:
            return False
        best_score = max(self._score_growth_action(action) for action in actions)
        return best_score >= 0.45

    def _can_interrupt_routing(
        self,
        actions: List[str],
        local_inbox: int,
        urgency: float,
        observation: dict[str, float],
        history: List[object],
    ) -> bool:
        if not self._should_prioritize_growth(actions):
            return False
        if local_inbox <= 0:
            return True
        if len(history) < 6:
            return False
        if local_inbox > self.environment.morphogenesis_config.growth_queue_tolerance:
            return False
        if urgency > self.environment.morphogenesis_config.growth_interrupt_urgency_threshold:
            return False
        if observation.get("feedback_pending", 0.0) > 0.6:
            return False
        if observation.get("atp_ratio", 0.0) < self.environment.morphogenesis_config.atp_surplus_threshold:
            return False
        contradiction = observation.get("contradiction_pressure", 0.0)
        overload = max(
            observation.get("queue_pressure", 0.0),
            observation.get("oldest_packet_age", 0.0),
            observation.get("ingress_backlog", 0.0),
        )
        if (
            observation.get("last_match_ratio", 0.0) >= 0.75
            and contradiction < self.environment.morphogenesis_config.contradiction_threshold + 0.15
        ):
            return False
        return contradiction >= self.environment.morphogenesis_config.contradiction_threshold or (
            overload >= self.environment.morphogenesis_config.overload_threshold
        )

    def _needs_maintenance(self) -> bool:
        maintenance = self.substrate.maintenance_metrics()
        if maintenance["active_action_count"] > 0 and maintenance["action_maintenance_ratio"] < 0.6:
            return True
        if maintenance["active_edge_count"] > 0 and maintenance["edge_maintenance_ratio"] < 0.6:
            return True
        for neighbor_id in self.substrate.active_neighbors():
            if self.substrate.velocity(neighbor_id) <= self.maintain_velocity_threshold:
                return True
        for neighbor_id, transform_name, context_bit in self.substrate.active_action_supports():
            if (
                self.substrate.action_velocity(neighbor_id, transform_name, context_bit)
                <= self.maintain_velocity_threshold
            ):
                return True
        return False

    def _recency_weighted_mean(
        self,
        history: List[object],
        action: str,
        *,
        field: str,
        default: float,
    ) -> float:
        # Use pre-indexed history when available (from _score_routes)
        if hasattr(self, "_history_by_action"):
            entries = self._history_by_action.get(action)
        else:
            entries = [entry for entry in history if entry.action == action]
        if not entries:
            return default

        current_cycle = getattr(self, "_history_current_cycle", None)
        if current_cycle is None:
            current_cycle = max(entry.cycle for entry in history)
        half_life = max(self.recency_half_life, 1e-9)
        weighted_total = 0.0
        total_weight = 0.0
        for entry in entries[-24:]:
            age = max(0, current_cycle - entry.cycle)
            weight = 0.5 ** (age / half_life)
            weighted_total += weight * float(getattr(entry, field))
            total_weight += weight
        if total_weight <= 0.0:
            return default
        return weighted_total / total_weight

    def _stale_bias_penalty(self, history: List[object], action: str) -> float:
        if hasattr(self, "_history_by_action"):
            entries = self._history_by_action.get(action)
        else:
            entries = [entry for entry in history if entry.action == action]
        if not entries:
            return 0.0
        current_cycle = getattr(self, "_history_current_cycle", None)
        if current_cycle is None:
            current_cycle = max(entry.cycle for entry in history)
        latest = max(entry.cycle for entry in entries)
        age = max(0, current_cycle - latest)
        if age <= self.recency_half_life:
            return 0.0
        return min(0.18, 0.02 * (age - self.recency_half_life))

    def _route_recency_weighted_mean(
        self,
        history: List[object],
        neighbor_id: str,
        *,
        field: str,
        default: float,
    ) -> float:
        if hasattr(self, "_history_by_neighbor"):
            entries = self._history_by_neighbor.get(neighbor_id)
        else:
            entries = [
                entry for entry in history if _route_neighbor(entry.action) == neighbor_id
            ]
        if not entries:
            return default

        current_cycle = getattr(self, "_history_current_cycle", None)
        if current_cycle is None:
            current_cycle = max(entry.cycle for entry in history)
        half_life = max(self.recency_half_life, 1e-9)
        weighted_total = 0.0
        total_weight = 0.0
        for entry in entries[-24:]:
            age = max(0, current_cycle - entry.cycle)
            weight = 0.5 ** (age / half_life)
            weighted_total += weight * float(getattr(entry, field))
            total_weight += weight
        if total_weight <= 0.0:
            return default
        return weighted_total / total_weight

    def _contextual_route_mean(
        self,
        history: List[object],
        action: str,
        *,
        context_bit: int | None,
        context_weight: float,
        field: str,
        default: float,
    ) -> float:
        if context_bit is None or context_weight <= 0.0:
            return default
        # Use pre-indexed action entries when available, then filter by context
        if hasattr(self, "_history_by_action"):
            action_entries = self._history_by_action.get(action)
        else:
            action_entries = [entry for entry in history if entry.action == action]
        if not action_entries:
            return default
        entries = [
            entry for entry in action_entries
            if self._entry_effective_context(entry)[0] == context_bit
        ]
        if not entries:
            return default

        current_cycle = getattr(self, "_history_current_cycle", None)
        if current_cycle is None:
            current_cycle = max(entry.cycle for entry in history)
        half_life = max(self.recency_half_life, 1e-9)
        weighted_total = 0.0
        total_weight = 0.0
        for entry in entries[-16:]:
            age = max(0, current_cycle - entry.cycle)
            _, entry_weight = self._entry_effective_context(entry)
            weight = (0.5 ** (age / half_life)) * max(0.15, entry_weight)
            weighted_total += weight * float(getattr(entry, field))
            total_weight += weight
        if total_weight <= 0.0:
            return default
        return weighted_total / total_weight

    def _score_routes(self, route_actions: List[str], history: List[object]) -> dict[str, float]:
        # Pre-compute history index: avoids O(N) scan per action per method call
        self._history_current_cycle = max((entry.cycle for entry in history), default=0)
        by_action: dict[str, list[object]] = {}
        by_neighbor: dict[str, list[object]] = {}
        for entry in history:
            by_action.setdefault(entry.action, []).append(entry)
            neighbor = _route_neighbor(entry.action)
            if neighbor is not None:
                by_neighbor.setdefault(neighbor, []).append(entry)
        self._history_by_action = by_action
        self._history_by_neighbor = by_neighbor
        try:
            return self._score_routes_inner(route_actions, history)
        finally:
            del self._history_by_action
            del self._history_by_neighbor
            del self._history_current_cycle

    def _score_routes_inner(self, route_actions: List[str], history: List[object]) -> dict[str, float]:
        breakdowns: dict[str, dict[str, float | int | str | None]] | None = (
            {} if self.capture_route_breakdowns else None
        )
        scores: dict[str, float] = {}
        for action in route_actions:
            if breakdowns is None:
                score = self._score_route(action, history)
                assert isinstance(score, float)
                scores[action] = score
                continue
            breakdown = self._score_route(action, history, return_breakdown=True)
            assert isinstance(breakdown, dict)
            breakdowns[action] = breakdown
            scores[action] = float(breakdown["total"])
        self._last_route_score_breakdowns = breakdowns
        observation = self.environment.observe_local(self.node_id)
        context_bit, context_weight = self._effective_context(observation)
        if context_bit is None or context_weight <= 0.0:
            return scores
        evidence = {
            action: self._candidate_evidence_from_local_state(
                neighbor_id=_route_neighbor(action) or "",
                transform_name=_route_transform(action),
                context_bit=context_bit,
                observation=observation,
            )
            for action in route_actions
            if _route_neighbor(action) is not None
        }
        if not evidence:
            return scores
        top_evidence = max(evidence.values())
        candidate_actions = [
            action
            for action in route_actions
            if _route_neighbor(action) is not None
            and evidence.get(action, -1.0) >= max(0.12, top_evidence - 0.18)
        ]
        candidate_branches = {_route_neighbor(action) for action in candidate_actions}
        candidate_transforms = {_route_transform(action) for action in candidate_actions}
        if (
            len(candidate_actions) < 3
            or len(candidate_branches) < 2
            or len(candidate_transforms) < 2
        ):
            return scores

        contradictions = {
            action: self._candidate_contradiction_from_local_state(
                neighbor_id=_route_neighbor(action) or "",
                transform_name=_route_transform(action),
                observation=observation,
            )
            for action in candidate_actions
        }
        dominant_action = max(
            candidate_actions,
            key=lambda action: (evidence[action], scores[action]),
        )
        dominant_evidence = evidence[dominant_action]
        for action in candidate_actions:
            contradiction = contradictions[action]
            if contradiction < 0.12:
                continue
            neighbor_id = _route_neighbor(action) or ""
            competitor_count = sum(
                1
                for other in candidate_actions
                if other != action and evidence[other] >= evidence[action] - 0.08
            )
            if action == dominant_action:
                scores[action] += min(
                    0.18,
                    contradiction * (0.08 + 0.03 * max(0, competitor_count - 1)),
                )
                continue
            closeness = max(
                0.0,
                1.0 - max(0.0, dominant_evidence - evidence[action]) / 0.25,
            )
            branch_debt = observation.get(f"branch_context_feedback_debt_{neighbor_id}", 0.0)
            scores[action] -= min(
                0.28,
                contradiction * (0.12 + 0.04 * competitor_count) * closeness
                + 0.05 * branch_debt,
            )
        return scores

    def _competition_adjustment(
        self,
        *,
        neighbor_id: str,
        transform_name: str,
        context_bit: int,
        observation: dict[str, float],
        action_support: float,
        generic_action_support: float,
        feedback_credit: float,
        provisional_feedback_credit: float,
        context_feedback_credit: float,
        provisional_context_feedback_credit: float,
        branch_feedback_credit: float,
        context_branch_feedback_credit: float,
        branch_context_feedback_credit: float,
        feedback_debt: float,
        context_feedback_debt: float,
        branch_feedback_debt: float,
        context_branch_feedback_debt: float,
        branch_context_feedback_debt: float,
    ) -> tuple[float, float]:
        current_evidence = self._candidate_evidence(
            neighbor_id=neighbor_id,
            transform_name=transform_name,
            context_bit=context_bit,
            observation=observation,
            action_support=action_support,
            generic_action_support=generic_action_support,
            feedback_credit=feedback_credit,
            provisional_feedback_credit=provisional_feedback_credit,
            context_feedback_credit=context_feedback_credit,
            provisional_context_feedback_credit=provisional_context_feedback_credit,
            branch_feedback_credit=branch_feedback_credit,
            context_branch_feedback_credit=context_branch_feedback_credit,
            branch_context_feedback_credit=branch_context_feedback_credit,
            feedback_debt=feedback_debt,
            context_feedback_debt=context_feedback_debt,
            branch_feedback_debt=branch_feedback_debt,
            context_branch_feedback_debt=context_branch_feedback_debt,
            branch_context_feedback_debt=branch_context_feedback_debt,
            transform_history_evidence=observation.get(
                f"history_transform_evidence_{transform_name}",
                0.0,
            ),
        )
        contradiction = max(
            0.0,
            0.35 * context_feedback_debt
            + 0.30 * context_branch_feedback_debt
            + 0.22 * branch_context_feedback_debt
            + 0.13 * feedback_debt
            - 0.10 * context_branch_feedback_credit
            - 0.08 * branch_context_feedback_credit,
        )
        if contradiction < 0.12:
            return 0.0, 0.0

        competing_evidences = []
        for candidate_neighbor in self.environment.neighbors_of(self.node_id):
            for candidate_transform in ROUTE_TRANSFORMS:
                if candidate_neighbor == neighbor_id and candidate_transform == transform_name:
                    continue
                candidate_evidence = self._candidate_evidence_from_local_state(
                    neighbor_id=candidate_neighbor,
                    transform_name=candidate_transform,
                    context_bit=context_bit,
                    observation=observation,
                )
                if candidate_evidence >= max(0.12, current_evidence - 0.10):
                    competing_evidences.append(candidate_evidence)

        if not competing_evidences:
            return 0.0, min(0.08, contradiction * 0.10)

        strongest_competitor = max(competing_evidences)
        competitor_count = len(competing_evidences)
        conflict_spread = min(
            1.0,
            0.35 * max(0, competitor_count - 1)
            + 0.65 * max(0.0, strongest_competitor - current_evidence + 0.05),
        )
        if strongest_competitor > current_evidence + 0.04:
            penalty = min(
                0.26,
                contradiction * (0.12 + 0.18 * conflict_spread),
            )
            return penalty, 0.0

        dominance = current_evidence - strongest_competitor
        bonus = min(0.10, contradiction * max(0.0, 0.08 + 0.18 * dominance))
        penalty = min(0.10, contradiction * max(0.0, 0.04 * competitor_count - 0.02))
        return penalty, bonus

    def _candidate_evidence_from_local_state(
        self,
        *,
        neighbor_id: str,
        transform_name: str,
        context_bit: int,
        observation: dict[str, float],
    ) -> float:
        raw_action_support = self.substrate.action_support(
            neighbor_id,
            transform_name,
            context_bit,
        )
        generic_action_support = self.substrate.base_action_support(
            neighbor_id,
            transform_name,
        )
        feedback_credit = observation.get(f"feedback_credit_{transform_name}", 0.0)
        provisional_feedback_credit = observation.get(
            f"provisional_feedback_credit_{transform_name}",
            0.0,
        )
        context_feedback_credit = observation.get(
            f"context_feedback_credit_{transform_name}",
            0.0,
        )
        provisional_context_feedback_credit = observation.get(
            f"provisional_context_feedback_credit_{transform_name}",
            0.0,
        )
        branch_feedback_credit = observation.get(
            f"branch_feedback_credit_{neighbor_id}_{transform_name}",
            0.0,
        )
        context_branch_feedback_credit = observation.get(
            f"context_branch_feedback_credit_{neighbor_id}_{transform_name}",
            0.0,
        )
        branch_context_feedback_credit = observation.get(
            f"branch_context_feedback_credit_{neighbor_id}",
            0.0,
        )
        feedback_debt = observation.get(f"feedback_debt_{transform_name}", 0.0)
        context_feedback_debt = observation.get(
            f"context_feedback_debt_{transform_name}",
            0.0,
        )
        branch_feedback_debt = observation.get(
            f"branch_feedback_debt_{neighbor_id}_{transform_name}",
            0.0,
        )
        context_branch_feedback_debt = observation.get(
            f"context_branch_feedback_debt_{neighbor_id}_{transform_name}",
            0.0,
        )
        branch_context_feedback_debt = observation.get(
            f"branch_context_feedback_debt_{neighbor_id}",
            0.0,
        )
        transform_history_evidence = observation.get(
            f"history_transform_evidence_{transform_name}",
            0.0,
        )
        action_support = raw_action_support
        if context_bit is not None:
            task_transform_affinity = observation.get(
                f"task_transform_affinity_{transform_name}",
                0.0,
            )
            (
                _raw_context_action_support,
                context_action_support,
                _transfer_context_support_scale,
            ) = self._effective_context_action_support(
                neighbor_id=neighbor_id,
                transform_name=transform_name,
                context_bit=context_bit,
                observation=observation,
                task_transform_affinity=task_transform_affinity,
                history_transform_evidence=transform_history_evidence,
                feedback_credit=feedback_credit,
                context_feedback_credit=context_feedback_credit,
                branch_feedback_credit=branch_feedback_credit,
                context_branch_feedback_credit=context_branch_feedback_credit,
                branch_context_feedback_credit=branch_context_feedback_credit,
                feedback_debt=feedback_debt,
                context_feedback_debt=context_feedback_debt,
                branch_feedback_debt=branch_feedback_debt,
                context_branch_feedback_debt=context_branch_feedback_debt,
                branch_context_feedback_debt=branch_context_feedback_debt,
            )
            action_support = max(generic_action_support, context_action_support)
        return self._candidate_evidence(
            neighbor_id=neighbor_id,
            transform_name=transform_name,
            context_bit=context_bit,
            observation=observation,
            action_support=action_support,
            generic_action_support=generic_action_support,
            feedback_credit=feedback_credit,
            provisional_feedback_credit=provisional_feedback_credit,
            context_feedback_credit=context_feedback_credit,
            provisional_context_feedback_credit=provisional_context_feedback_credit,
            branch_feedback_credit=branch_feedback_credit,
            context_branch_feedback_credit=context_branch_feedback_credit,
            branch_context_feedback_credit=branch_context_feedback_credit,
            feedback_debt=feedback_debt,
            context_feedback_debt=context_feedback_debt,
            branch_feedback_debt=branch_feedback_debt,
            context_branch_feedback_debt=context_branch_feedback_debt,
            branch_context_feedback_debt=branch_context_feedback_debt,
            transform_history_evidence=transform_history_evidence,
        )

    def _candidate_contradiction_from_local_state(
        self,
        *,
        neighbor_id: str,
        transform_name: str,
        observation: dict[str, float],
    ) -> float:
        feedback_credit = observation.get(f"feedback_credit_{transform_name}", 0.0)
        context_feedback_credit = observation.get(
            f"context_feedback_credit_{transform_name}",
            0.0,
        )
        context_branch_feedback_credit = observation.get(
            f"context_branch_feedback_credit_{neighbor_id}_{transform_name}",
            0.0,
        )
        branch_context_feedback_credit = observation.get(
            f"branch_context_feedback_credit_{neighbor_id}",
            0.0,
        )
        feedback_debt = observation.get(f"feedback_debt_{transform_name}", 0.0)
        context_feedback_debt = observation.get(
            f"context_feedback_debt_{transform_name}",
            0.0,
        )
        branch_feedback_debt = observation.get(
            f"branch_feedback_debt_{neighbor_id}_{transform_name}",
            0.0,
        )
        context_branch_feedback_debt = observation.get(
            f"context_branch_feedback_debt_{neighbor_id}_{transform_name}",
            0.0,
        )
        branch_context_feedback_debt = observation.get(
            f"branch_context_feedback_debt_{neighbor_id}",
            0.0,
        )
        return max(
            0.0,
            0.18 * feedback_debt
            + 0.28 * context_feedback_debt
            + 0.14 * branch_feedback_debt
            + 0.24 * context_branch_feedback_debt
            + 0.20 * branch_context_feedback_debt
            - 0.08 * feedback_credit
            - 0.12 * context_feedback_credit
            - 0.12 * context_branch_feedback_credit
            - 0.10 * branch_context_feedback_credit,
        )

    def _candidate_evidence(
        self,
        *,
        neighbor_id: str,
        transform_name: str,
        context_bit: int,
        observation: dict[str, float],
        action_support: float,
        generic_action_support: float,
        feedback_credit: float,
        provisional_feedback_credit: float,
        context_feedback_credit: float,
        provisional_context_feedback_credit: float,
        branch_feedback_credit: float,
        context_branch_feedback_credit: float,
        branch_context_feedback_credit: float,
        feedback_debt: float,
        context_feedback_debt: float,
        branch_feedback_debt: float,
        context_branch_feedback_debt: float,
        branch_context_feedback_debt: float,
        transform_history_evidence: float,
    ) -> float:
        task_transform_affinity = observation.get(
            f"task_transform_affinity_{transform_name}",
            0.0,
        )
        (
            _raw_context_action_support,
            context_action_support,
            _transfer_context_support_scale,
        ) = self._effective_context_action_support(
            neighbor_id=neighbor_id,
            transform_name=transform_name,
            context_bit=context_bit,
            observation=observation,
            task_transform_affinity=task_transform_affinity,
            history_transform_evidence=transform_history_evidence,
            feedback_credit=feedback_credit,
            context_feedback_credit=context_feedback_credit,
            branch_feedback_credit=branch_feedback_credit,
            context_branch_feedback_credit=context_branch_feedback_credit,
            branch_context_feedback_credit=branch_context_feedback_credit,
            feedback_debt=feedback_debt,
            context_feedback_debt=context_feedback_debt,
            branch_feedback_debt=branch_feedback_debt,
            context_branch_feedback_debt=context_branch_feedback_debt,
            branch_context_feedback_debt=branch_context_feedback_debt,
        )
        _, context_weight = self._effective_context(observation)
        return (
            0.20 * generic_action_support
            + 0.30 * action_support
            + 0.16 * context_action_support * context_weight
            + 0.16 * transform_history_evidence
            + 0.10 * feedback_credit
            + 0.10 * provisional_feedback_credit
            + 0.14 * context_feedback_credit * context_weight
            + 0.18 * provisional_context_feedback_credit * context_weight
            + 0.10 * branch_feedback_credit
            + 0.20 * context_branch_feedback_credit * context_weight
            + 0.16 * branch_context_feedback_credit * context_weight
            - 0.08 * feedback_debt
            - 0.16 * context_feedback_debt * context_weight
            - 0.08 * branch_feedback_debt
            - 0.22 * context_branch_feedback_debt * context_weight
            - 0.16 * branch_context_feedback_debt * context_weight
        )

    def _effective_context_action_support(
        self,
        *,
        neighbor_id: str,
        transform_name: str,
        context_bit: int,
        observation: dict[str, float],
        task_transform_affinity: float,
        history_transform_evidence: float,
        feedback_credit: float,
        context_feedback_credit: float,
        branch_feedback_credit: float,
        context_branch_feedback_credit: float,
        branch_context_feedback_credit: float,
        feedback_debt: float,
        context_feedback_debt: float,
        branch_feedback_debt: float,
        context_branch_feedback_debt: float,
        branch_context_feedback_debt: float,
    ) -> tuple[float, float, float]:
        raw_context_action_support = self.substrate.contextual_action_support(
            neighbor_id,
            transform_name,
            context_bit,
        )
        if raw_context_action_support <= 0.0:
            return raw_context_action_support, raw_context_action_support, 1.0
        transfer_adaptation_phase = max(
            0.0,
            min(1.0, observation.get("transfer_adaptation_phase", 0.0)),
        )
        local_confirmation = min(
            1.0,
            max(
                0.0,
                0.42 * history_transform_evidence
                + 0.24 * max(0.0, task_transform_affinity)
                + 0.44 * feedback_credit
                + 0.68 * context_feedback_credit
                + 0.26 * branch_feedback_credit
                + 0.40 * context_branch_feedback_credit
                + 0.34 * branch_context_feedback_credit
                - 0.18 * feedback_debt
                - 0.26 * branch_feedback_debt
                - 0.32 * context_feedback_debt
                - 0.26 * context_branch_feedback_debt
                - 0.22 * branch_context_feedback_debt,
            ),
        )
        task_mismatch = max(0.0, -task_transform_affinity)
        adaptation_pressure = max(
            transfer_adaptation_phase,
            0.55 * task_mismatch,
        )
        if adaptation_pressure <= 0.0:
            return raw_context_action_support, raw_context_action_support, 1.0
        stale_pressure = min(
            1.0,
            max(
                0.0,
                0.58 * task_mismatch
                + 0.32 * context_feedback_debt
                + 0.18 * feedback_debt
                + 0.18 * context_branch_feedback_debt
                + 0.16 * branch_context_feedback_debt
                - 0.24 * local_confirmation,
            ),
        )
        if stale_pressure <= 0.0:
            return raw_context_action_support, raw_context_action_support, 1.0
        suppression = adaptation_pressure * stale_pressure * (
            1.0 - 0.75 * local_confirmation
        )
        support_scale = max(0.15, 1.0 - 0.85 * suppression)
        return (
            raw_context_action_support,
            raw_context_action_support * support_scale,
            support_scale,
        )
