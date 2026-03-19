from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .environment import RoutingEnvironment
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

    def available_actions(self, history_size: int) -> List[str]:
        actions = ["rest"]
        local_inbox = len(self.environment.inboxes[self.node_id])
        observation = self.environment.observe_local(self.node_id)
        context_bit = None
        latent_downstream_transform_gate = (
            self.node_id != self.environment.source_id
            and observation.get("head_has_task", 0.0) >= 0.5
            and observation.get("head_has_context", 0.0) < 0.5
            and observation.get("latent_context_available", 0.0) >= 0.5
            and observation.get("context_promotion_ready", 0.0) < 0.5
        )
        if observation.get("effective_has_context", 0.0) >= 0.5:
            context_bit = int(observation.get("effective_context_bit", 0.0))
        for neighbor_id in self.neighbor_ids:
            route_cost = self.substrate.use_cost(neighbor_id)
            if self.environment.route_available(self.node_id, neighbor_id, route_cost):
                actions.append(f"route:{neighbor_id}")
                for transform_name in TRANSFORM_ACTIONS:
                    if latent_downstream_transform_gate and transform_name != "identity":
                        continue
                    transform_cost = self.substrate.use_cost(neighbor_id, transform_name, context_bit)
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
            result = self.environment.route_signal(self.node_id, neighbor_id, cost)
            return ActionOutcome(
                success=bool(result["success"]),
                result=result,
                cost_secs=float(result["cost"]),
            )

        if action.startswith("route_transform:"):
            _, neighbor_id, transform_name = action.split(":", 2)
            observation = self.environment.observe_local(self.node_id)
            context_bit = None
            if observation.get("effective_has_context", 0.0) >= 0.5:
                context_bit = int(observation.get("effective_context_bit", 0.0))
            cost = self.substrate.use_cost(neighbor_id, transform_name, context_bit)
            result = self.environment.route_signal(
                self.node_id,
                neighbor_id,
                cost,
                transform_name=transform_name,
            )
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
        return sum(dimensions.values()) / max(1, len(dimensions))

    def gco_status(self, dimensions: Dict[str, float], coherence: float):
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
            for prefix in ("progress", "congestion"):
                key = f"{prefix}_{neighbor_id}"
                if key not in modulated:
                    continue
                jitter = self.rng.gauss(0.0, self.noise_scale * (1.0 - clarity))
                modulated[key] = max(0.0, min(1.0, modulated[key] + jitter))
            modulated[f"support_{neighbor_id}"] = support
            modulated[f"support_velocity_{neighbor_id}"] = self.substrate.velocity(neighbor_id)
            for transform_name in TRANSFORM_ACTIONS:
                modulated[f"action_support_{neighbor_id}_{transform_name}"] = (
                    self.substrate.action_support(
                        neighbor_id,
                        transform_name,
                    )
                )
                if modulated.get("effective_has_context", 0.0) >= 0.5:
                    modulated[f"context_action_support_{neighbor_id}_{transform_name}"] = (
                        self.substrate.action_support(
                            neighbor_id,
                            transform_name,
                            int(modulated.get("effective_context_bit", 0.0)),
                        )
                    )
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
