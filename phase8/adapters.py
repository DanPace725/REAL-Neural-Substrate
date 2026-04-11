from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .environment import RoutingEnvironment, _expected_transform_for_task
from .substrate import ConnectionSubstrate, SUPPORTED_TRANSFORMS

TRANSFORM_ACTIONS: Tuple[str, ...] = SUPPORTED_TRANSFORMS


def _route_neighbor(action: str) -> str | None:
    if action.startswith("route_transform:"):
        parts = action.split(":")
        if len(parts) == 3:
            return parts[1]
        return None
    if action.startswith("route:"):
        return action.split(":", 1)[1]
    return None


class LocalNodeObservationAdapter:
    def __init__(
        self,
        environment: RoutingEnvironment,
        node_id: str,
    ) -> None:
        self.environment = environment
        self.node_id = node_id

    def observe(self, cycle: int) -> Dict[str, float]:
        return self.environment.observe_local(self.node_id)


class LocalNodeActionBackend:
    def __init__(
        self,
        environment: RoutingEnvironment,
        node_id: str,
        neighbor_ids: Tuple[str, ...],
        substrate: ConnectionSubstrate,
    ) -> None:
        self.environment = environment
        self.node_id = node_id
        self.neighbor_ids = neighbor_ids
        self.substrate = substrate

    def _c_task_reopen_surcharge(
        self,
        observation: Dict[str, float],
        transform_name: str | None,
    ) -> float:
        if transform_name in (None, "identity"):
            return 0.0
        preserve_pressure = max(
            0.0,
            min(1.0, observation.get("c_task_preserve_pressure", 0.0)),
        )
        reopen_pressure = max(
            0.0,
            min(1.0, observation.get("c_task_reopen_pressure", 0.0)),
        )
        resolution_confidence = max(
            0.0,
            min(1.0, observation.get("c_task_resolution_confidence", 0.0)),
        )
        preserve_mode = observation.get("c_task_preserve_mode", 0.0) >= 0.5
        protection = max(
            0.0,
            preserve_pressure + 0.40 * resolution_confidence - 0.45 * reopen_pressure,
        )
        if protection <= 0.10 and not preserve_mode:
            return 0.0
        return min(
            0.07,
            0.012 + 0.045 * protection + (0.015 if preserve_mode else 0.0),
        )

    def _action_context(self, observation: Dict[str, float]) -> int | None:
        if observation.get("effective_has_context", 0.0) >= 0.5:
            return int(observation.get("effective_context_bit", 0.0))
        if (
            observation.get("packet_has_context", 0.0) >= 0.5
            and observation.get("packet_context_confidence", 0.0) > 0.0
        ):
            return int(observation.get("packet_context_bit", observation.get("head_context_bit", 0.0)))
        return None

    def available_actions(self, history_size: int) -> List[str]:
        actions = ["rest"]
        local_inbox = len(self.environment.inboxes[self.node_id])
        observation = self.environment.observe_local(self.node_id)
        head_packet = self.environment.inboxes[self.node_id][0] if local_inbox > 0 else None
        context_bit = self._action_context(observation)
        latent_downstream_transform_gate = (
            self.node_id != self.environment.source_id
            and observation.get("head_has_task", 0.0) >= 0.5
            and observation.get("head_has_context", 0.0) < 0.5
            and observation.get("latent_context_available", 0.0) >= 0.5
            and observation.get("context_promotion_ready", 0.0) < 0.5
        )
        packet_context_supported = (
            observation.get("packet_has_context", 0.0) >= 0.5
            and observation.get("packet_context_confidence", 0.0) > 0.0
            and observation.get("head_has_task", 0.0) >= 0.5
        )
        allowed_hidden_transforms: set[str] | None = None
        if latent_downstream_transform_gate and packet_context_supported:
            allowed_hidden_transforms = {
                transform_name
                for transform_name in TRANSFORM_ACTIONS
                if observation.get(f"expected_transform_{transform_name}", 0.0) >= 0.5
                or observation.get(f"task_transform_affinity_{transform_name}", 0.0) > 0.0
                or observation.get(f"source_sequence_transform_hint_{transform_name}", 0.0) > 0.0
            }
        c_task_active = (
            head_packet is not None
            and self.environment.c_task_layer1_mode != "legacy"
            and self.environment.c_task_layer1_enabled
        )
        c_task_source_expected_transform = (
            _expected_transform_for_task(head_packet.task_id, head_packet.context_bit)
            if c_task_active and head_packet is not None
            else None
        )
        c_task_mode = str(self.environment.c_task_layer1_mode or "legacy")
        node_source_hardening_shift = float(
            observation.get("slow_c_task_node_support_source_hardening_shift", 0.0)
        )
        node_weak_context_boost = float(
            observation.get("slow_c_task_node_support_weak_context_boost", 0.0)
        )
        source_hardening_score = max(
            0.0,
            min(
                1.0,
                0.50 * observation.get("packet_context_confidence", 0.0)
                + 0.30 * observation.get("transform_commitment_margin", 0.0)
                + 0.20 * observation.get("expected_transform_available", 0.0),
            ),
        )
        source_hardening_threshold = max(
            0.42,
            min(
                0.68,
                0.66 - 0.18 * observation.get("packet_context_confidence", 0.0),
            ),
        )
        source_hardening_threshold = max(
            0.25,
            min(
                0.78,
                source_hardening_threshold
                + float(observation.get("slow_c_task_source_hardening_shift", 0.0))
                + node_source_hardening_shift
                - 0.12
                * float(observation.get("slow_c_task_weak_context_boost", 0.0))
                * float(observation.get("slow_weak_context_match", 0.0))
                - 0.12
                * node_weak_context_boost
                * float(observation.get("slow_weak_context_match", 0.0)),
            ),
        )
        communicative_source_self_harden = (
            c_task_active
            and c_task_mode == "communicative"
            and self.node_id == self.environment.source_id
            and c_task_source_expected_transform not in {None, "identity"}
            and source_hardening_score >= source_hardening_threshold
        )
        preserve_advantage = (
            float(observation.get("c_task_preserve_pressure", 0.0))
            - float(observation.get("c_task_reopen_pressure", 0.0))
        )
        preserve_hardening_threshold = (
            max(
                0.28,
                min(
                    0.62,
                    0.58 - 0.24 * float(observation.get("c_task_resolution_confidence", 0.0)),
                ),
            )
        )
        preserve_hardening_threshold = max(
            0.18,
            min(
                0.82,
                preserve_hardening_threshold
                + float(observation.get("slow_c_task_preserve_hardening_shift", 0.0))
                + 0.10
                * float(observation.get("slow_c_task_weak_context_boost", 0.0))
                * float(observation.get("slow_weak_context_match", 0.0))
                + 0.08
                * node_weak_context_boost
                * float(observation.get("slow_weak_context_match", 0.0)),
            ),
        )
        communicative_preserve_self_harden = (
            c_task_active
            and c_task_mode == "communicative"
            and preserve_advantage >= preserve_hardening_threshold
            and float(observation.get("c_task_resolution_confidence", 0.0)) >= 0.35
        )
        preserve_identity_only = (
            c_task_active
            and head_packet is not None
            and (
                (
                    self.environment.c_task_layer1_mode == "stabilized"
                    and bool(head_packet.c_task_preserve_mode)
                )
                or communicative_preserve_self_harden
            )
        )
        for neighbor_id in self.neighbor_ids:
            route_cost = self.substrate.use_cost(neighbor_id)
            if self.environment.route_available(self.node_id, neighbor_id, route_cost):
                allow_plain_route = True
                if (
                    c_task_active
                    and self.node_id == self.environment.source_id
                    and c_task_source_expected_transform not in {None, "identity"}
                    and (
                        self.environment.c_task_layer1_mode == "stabilized"
                        or communicative_source_self_harden
                    )
                ):
                    allow_plain_route = False
                if allow_plain_route:
                    actions.append(f"route:{neighbor_id}")
                for transform_name in TRANSFORM_ACTIONS:
                    if preserve_identity_only and transform_name != "identity":
                        continue
                    if (
                        c_task_active
                        and not preserve_identity_only
                        and self.node_id == self.environment.source_id
                        and c_task_source_expected_transform not in {None, "identity"}
                        and (
                            self.environment.c_task_layer1_mode == "stabilized"
                            or communicative_source_self_harden
                        )
                        and transform_name != c_task_source_expected_transform
                    ):
                        continue
                    if latent_downstream_transform_gate:
                        if allowed_hidden_transforms is None:
                            if transform_name != "identity":
                                continue
                        elif transform_name != "identity" and transform_name not in allowed_hidden_transforms:
                            continue
                    transform_cost = self.substrate.use_cost(neighbor_id, transform_name, context_bit)
                    transform_cost += self._c_task_reopen_surcharge(observation, transform_name)
                    if self.environment.route_available(self.node_id, neighbor_id, transform_cost):
                        actions.append(f"route_transform:{neighbor_id}:{transform_name}")
            neighbor_congestion = len(self.environment.inboxes.get(neighbor_id, []))
            if (
                local_inbox > 0
                and neighbor_congestion >= self.environment.inbox_capacity
                and self.environment.inhibit_available(self.node_id)
                and neighbor_id != self.environment.sink_id
            ):
                actions.append(f"inhibit:{neighbor_id}")
        return actions

    def execute(self, action: str):
        from real_core.types import ActionOutcome

        if action == "rest":
            recovered = self.environment.rest_node(self.node_id)
            return ActionOutcome(
                success=True,
                result={"action": action, "recovered_atp": recovered},
                cost_secs=0.0,
            )

        if action.startswith("route:"):
            neighbor_id = action.split(":", 1)[1]
            cost = self.substrate.use_cost(neighbor_id)
            observation = self.environment.observe_local(self.node_id)
            pulse_gate = self.environment.evaluate_route_action(
                self.node_id,
                neighbor_id,
                observation=observation,
            )
            if not pulse_gate.get("allowed", True):
                return ActionOutcome(
                    success=False,
                    result={
                        "action": action,
                        "success": False,
                        "cost": 0.0,
                        "delivered": False,
                        "suppressed": True,
                        **pulse_gate,
                    },
                    cost_secs=0.0,
                )
            result = self.environment.route_signal(self.node_id, neighbor_id, cost)
            result.update({
                "pulse_reason": pulse_gate.get("reason", "legacy"),
                "pulse_forced_release": bool(pulse_gate.get("forced_release", False)),
                "pulse_release_ready": bool(pulse_gate.get("release_ready", True)),
                "pulse_delay_streak": int(pulse_gate.get("delay_streak", 0)),
                "pulse_delay_limit": int(pulse_gate.get("delay_limit", 0)),
            })
            return ActionOutcome(
                success=bool(result["success"]),
                result=result,
                cost_secs=float(result["cost"]),
            )

        if action.startswith("route_transform:"):
            _, neighbor_id, transform_name = action.split(":", 2)
            observation = self.environment.observe_local(self.node_id)
            pulse_gate = self.environment.evaluate_route_action(
                self.node_id,
                neighbor_id,
                transform_name=transform_name,
                observation=observation,
            )
            if not pulse_gate.get("allowed", True):
                return ActionOutcome(
                    success=False,
                    result={
                        "action": action,
                        "success": False,
                        "cost": 0.0,
                        "delivered": False,
                        "suppressed": True,
                        **pulse_gate,
                    },
                    cost_secs=0.0,
                )
            context_bit = self._action_context(observation)
            cost = self.substrate.use_cost(neighbor_id, transform_name, context_bit)
            cost += self._c_task_reopen_surcharge(observation, transform_name)
            result = self.environment.route_signal(
                self.node_id,
                neighbor_id,
                cost,
                transform_name=transform_name,
            )
            result.update({
                "pulse_reason": pulse_gate.get("reason", "legacy"),
                "pulse_forced_release": bool(pulse_gate.get("forced_release", False)),
                "pulse_release_ready": bool(pulse_gate.get("release_ready", True)),
                "pulse_delay_streak": int(pulse_gate.get("delay_streak", 0)),
                "pulse_delay_limit": int(pulse_gate.get("delay_limit", 0)),
            })
            return ActionOutcome(
                success=bool(result["success"]),
                result=result,
                cost_secs=float(result["cost"]),
            )

        if action.startswith("inhibit:"):
            neighbor_id = action.split(":", 1)[1]
            result = self.environment.inhibit_neighbor(self.node_id, neighbor_id)
            return ActionOutcome(
                success=bool(result["success"]),
                result=result,
                cost_secs=float(result["cost"]),
            )

        return ActionOutcome(success=False, result={"action": action}, cost_secs=0.0)


@dataclass
class LocalNodeCoherenceModel:
    dimension_names: Tuple[str, ...] = (
        "continuity",
        "vitality",
        "contextual_fit",
        "differentiation",
        "accountability",
        "reflexivity",
    )
    homeostatic_weight: float = 0.35

    def score(self, state_after: Dict[str, float], history: List[object]) -> Dict[str, float]:
        atp_ratio = state_after.get("atp_ratio", 0.0)
        inbox_load = state_after.get("inbox_load", 0.0)
        reward_buffer = state_after.get("reward_buffer", 0.0)
        oldest_packet_age = state_after.get("oldest_packet_age", 0.0)
        queue_pressure = state_after.get("queue_pressure", 0.0)
        ingress_backlog = state_after.get("ingress_backlog", 0.0)
        last_match_ratio = state_after.get("last_match_ratio", 0.0)
        last_feedback_amount = state_after.get("last_feedback_amount", 0.0)

        continuity = 0.4 + 0.6 * atp_ratio - 0.12 * queue_pressure
        vitality = max(
            0.0,
            min(
                1.0,
                0.25
                + 0.45 * inbox_load
                + 0.35 * reward_buffer
                + 0.10 * last_feedback_amount
                - 0.18 * oldest_packet_age
                - 0.10 * ingress_backlog,
            ),
        )

        progress_values = [
            value
            for key, value in state_after.items()
            if key.startswith("progress_")
        ]
        contextual_fit = max(progress_values) if progress_values else 0.5
        contextual_fit = max(0.0, min(1.0, contextual_fit + 0.18 * last_match_ratio))

        route_actions = []
        for entry in history[-10:]:
            neighbor_id = _route_neighbor(entry.action)
            if neighbor_id is not None:
                route_actions.append(neighbor_id)
        if not route_actions:
            differentiation = 0.35
        else:
            counts = {}
            for neighbor_id in route_actions:
                counts[neighbor_id] = counts.get(neighbor_id, 0) + 1
            specialization = max(counts.values()) / max(len(route_actions), 1)
            differentiation = max(0.2, min(1.0, specialization))

        accountability = min(
            1.0,
            0.2 + 0.07 * len(history) - 0.15 * queue_pressure - 0.08 * ingress_backlog,
        )

        if len(history) < 4:
            reflexivity = 0.30
        else:
            recent = history[-8:]
            revision_attempts = 0
            recoveries = 0
            for index in range(1, len(recent)):
                prior = recent[index - 1]
                current = recent[index]
                if prior.delta < -0.02:
                    revision_attempts += 1
                    if current.action != prior.action and current.delta > 0:
                        recoveries += 1
            reflexivity = (
                recoveries / revision_attempts
                if revision_attempts > 0
                else 0.45
            )
        reflexivity = max(
            0.0,
            min(1.0, reflexivity + 0.12 * last_match_ratio + 0.08 * last_feedback_amount),
        )

        return {
            "continuity": max(0.0, min(1.0, continuity)),
            "vitality": vitality,
            "contextual_fit": max(0.0, min(1.0, contextual_fit)),
            "differentiation": max(0.0, min(1.0, differentiation)),
            "accountability": max(0.0, min(1.0, accountability)),
            "reflexivity": max(0.0, min(1.0, reflexivity)),
        }

    def composite(self, dimensions: Dict[str, float]) -> float:
        values = [max(0.0, min(1.0, float(value))) for value in dimensions.values()]
        if not values:
            return 0.0

        arithmetic_mean = sum(values) / len(values)
        if min(values) <= 0.0:
            harmonic_mean = 0.0
        else:
            harmonic_mean = len(values) / sum(1.0 / value for value in values)

        # Homeostatic coherence is partly bottleneck-limited: a collapsed
        # primitive should hurt more than a plain arithmetic mean would allow.
        weight = max(0.0, min(1.0, self.homeostatic_weight))
        coherence = (1.0 - weight) * arithmetic_mean + weight * harmonic_mean
        return max(0.0, min(1.0, coherence))

    def gco_status(self, dimensions: Dict[str, float], coherence: float, *, state_after: Dict[str, float] | None = None):
        from real_core.types import GCOStatus

        if coherence < 0.35:
            return GCOStatus.CRITICAL
        if coherence < 0.60:
            return GCOStatus.DEGRADED
        if all(value >= 0.60 for value in dimensions.values()):
            return GCOStatus.STABLE
        return GCOStatus.PARTIAL


@dataclass
class LocalNodeMemoryBinding:
    environment: RoutingEnvironment
    node_id: str
    neighbor_ids: Tuple[str, ...]
    substrate: ConnectionSubstrate
    noise_scale: float = 0.14
    rng: random.Random = field(default_factory=random.Random)

    def modulate_observation(
        self,
        raw_obs: Dict[str, float],
        substrate,
        cycle: int,
    ) -> Dict[str, float]:
        modulated = dict(raw_obs)
        for neighbor_id in self.neighbor_ids:
            support = self.substrate.support(neighbor_id)
            clarity = max(0.15, min(0.95, 0.20 + support * 0.75))
            modulated[self.substrate.edge_key(neighbor_id)] = support
            for prefix in ("progress", "congestion"):
                key = f"{prefix}_{neighbor_id}"
                if key not in modulated:
                    continue
                jitter = self.rng.gauss(0.0, self.noise_scale * (1.0 - clarity))
                modulated[key] = max(0.0, min(1.0, modulated[key] + jitter))
            modulated[f"support_{neighbor_id}"] = support
            modulated[f"support_velocity_{neighbor_id}"] = self.substrate.velocity(neighbor_id)
            for transform_name in TRANSFORM_ACTIONS:
                action_support = self.substrate.action_support(
                    neighbor_id,
                    transform_name,
                )
                modulated[f"action_support_{neighbor_id}_{transform_name}"] = action_support
                modulated[self.substrate.action_key(neighbor_id, transform_name)] = (
                    action_support
                )
                if modulated.get("effective_has_context", 0.0) >= 0.5:
                    context_bit = int(modulated.get("effective_context_bit", 0.0))
                    context_action_support = self.substrate.action_support(
                        neighbor_id,
                        transform_name,
                        context_bit,
                    )
                    modulated[f"context_action_support_{neighbor_id}_{transform_name}"] = (
                        context_action_support
                    )
                    try:
                        context_action_key = self.substrate.context_action_key(
                            neighbor_id,
                            transform_name,
                            context_bit,
                        )
                    except KeyError:
                        context_action_key = None
                    if context_action_key is not None:
                        modulated[context_action_key] = context_action_support
        maintenance = self.substrate.maintenance_metrics()
        modulated["edge_maintenance_ratio"] = maintenance["edge_maintenance_ratio"]
        modulated["action_maintenance_ratio"] = maintenance["action_maintenance_ratio"]
        modulated["substrate_maintenance_ratio"] = maintenance["maintenance_ratio"]
        modulated["mean_active_support"] = maintenance["mean_active_support"]
        return modulated

    def extra_actions(self, substrate, history: List[object]):
        from real_core.types import MemoryActionSpec

        actions = []
        state = self.environment.state_for(self.node_id)
        local_inbox = len(self.environment.inboxes[self.node_id])
        growth_window_open = local_inbox <= self.environment.morphogenesis_config.growth_queue_tolerance
        if state.atp > 0.0 and local_inbox == 0:
            for neighbor_id in self.neighbor_ids:
                cost = self.substrate.write_cost(neighbor_id)
                if cost <= state.atp + 1e-9:
                    actions.append(
                        MemoryActionSpec(
                            action=f"invest:{neighbor_id}",
                            estimated_cost=cost,
                        )
                    )
            maintain_cost = self.substrate.estimate_maintenance_cost()
            if maintain_cost > 0.0 and maintain_cost <= state.atp + 1e-9:
                    actions.append(
                        MemoryActionSpec(
                            action="maintain_edges",
                            estimated_cost=maintain_cost,
                        )
                    )
        if state.atp > 0.0 and growth_window_open:
            for spec in self.environment.growth_action_specs(self.node_id):
                cost = float(spec["cost"])
                if cost <= state.atp + 1e-9:
                    actions.append(
                        MemoryActionSpec(
                            action=str(spec["action"]),
                            estimated_cost=cost,
                        )
                    )
        return actions

    def estimate_memory_action_cost(self, action: str, substrate) -> float | None:
        if action == "maintain_edges":
            return self.substrate.estimate_maintenance_cost()
        if action.startswith("invest:"):
            neighbor_id = action.split(":", 1)[1]
            return self.substrate.write_cost(neighbor_id)
        for spec in self.environment.growth_action_specs(self.node_id):
            if spec["action"] == action:
                return float(spec["cost"])
        return None

    def execute_memory_action(self, action: str, substrate):
        from real_core.types import ActionOutcome

        state = self.environment.state_for(self.node_id)
        if action == "maintain_edges":
            observation = self.environment.observe_local(self.node_id)
            context_bit = None
            if observation.get("context_promotion_ready", 0.0) >= 0.5 and observation.get("effective_has_context", 0.0) >= 0.5:
                context_bit = int(observation.get("effective_context_bit", 0.0))
            maintenance = self.substrate.maintain_supports(
                state.atp,
                transform_credit=dict(state.transform_credit),
                context_transform_credit=dict(state.context_transform_credit),
                branch_transform_credit=dict(state.branch_transform_credit),
                context_branch_transform_credit=dict(state.context_branch_transform_credit),
                transform_debt=dict(state.transform_debt),
                context_transform_debt=dict(state.context_transform_debt),
                branch_context_credit=dict(state.branch_context_credit),
                branch_context_debt=dict(state.branch_context_debt),
                context_bit=context_bit,
            )
            spent = float(maintenance["spent"])
            if spent <= 0.0:
                return ActionOutcome(success=False, cost_secs=0.0)
            state.atp = max(0.0, state.atp - spent)
            if self.environment.topology_state is not None:
                maintained_neighbors = list(maintenance.get("maintained_edges", []))
                maintained_neighbors.extend(
                    label.split(":", 1)[0]
                    for label in maintenance.get("maintained_actions", [])
                )
                self.environment.topology_state.record_maintenance(
                    self.node_id,
                    spent,
                    maintained_neighbors=maintained_neighbors,
                )
            return ActionOutcome(
                success=True,
                result=maintenance,
                cost_secs=spent,
            )

        if action.startswith("invest:"):
            neighbor_id = action.split(":", 1)[1]
            spent = self.substrate.invest_connection(neighbor_id, state.atp)
            if spent is None:
                return ActionOutcome(success=False, cost_secs=0.0)
            state.atp = max(0.0, state.atp - spent)
            return ActionOutcome(
                success=True,
                result={"invested_neighbor": neighbor_id},
                cost_secs=spent,
            )

        growth_specs = {
            str(spec["action"]): spec
            for spec in self.environment.growth_action_specs(self.node_id)
        }
        if action in growth_specs:
            spec = growth_specs[action]
            spent = float(spec["cost"])
            if spent > state.atp + 1e-9:
                return ActionOutcome(success=False, cost_secs=0.0)
            state.atp = max(0.0, state.atp - spent)
            if self.environment.topology_state is not None:
                self.environment.topology_state.record_growth_spend(self.node_id, spent)
            proposal = self.environment.queue_growth_proposal(
                self.node_id,
                action,
                score=float(spec.get("score", 0.0)),
                cost=spent,
            )
            proposal.reason = str(spec.get("reason", "queued_locally"))
            return ActionOutcome(
                success=True,
                result={"queued_growth_action": action},
                cost_secs=spent,
            )

        return None

    def substrate_health_signal(
        self,
        substrate,
        state_after: Dict[str, float],
        history: List[object],
    ) -> Dict[str, float]:
        total = max(len(self.neighbor_ids), 1)
        active_ratio = len(self.substrate.active_neighbors()) / total
        mean_support = sum(
            self.substrate.support(neighbor_id)
            for neighbor_id in self.neighbor_ids
        ) / total
        maintenance = self.substrate.maintenance_metrics()
        return {
            "continuity": 0.35 + 0.45 * active_ratio + 0.20 * maintenance["maintenance_ratio"],
            "contextual_fit": 0.25 + 0.45 * mean_support + 0.30 * maintenance["mean_active_support"],
            "reflexivity": 0.20 + 0.40 * active_ratio + 0.40 * maintenance["action_maintenance_ratio"],
        }
