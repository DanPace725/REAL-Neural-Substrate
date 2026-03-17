from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from real_core.substrate import MemorySubstrate, SubstrateConfig
from real_core.patterns import ConstraintPattern
from real_core.types import DimensionScores, SubstrateSnapshot

SUPPORTED_TRANSFORMS = (
    "identity",
    "rotate_left_1",
    "xor_mask_1010",
    "xor_mask_0101",
)
SUPPORTED_CONTEXTS = (0, 1)
RECENT_MAINTENANCE_AGE = 2


@dataclass
class ConnectionSubstrateConfig:
    fire_base_cost: float = 0.05
    fire_floor_cost: float = 0.01
    fire_discount_scale: float = 0.04
    transform_discount_scale: float = 0.015
    write_base_cost: float = 0.14
    maintain_base_cost: float = 0.03
    slow_decay: float = 0.025
    bistable_threshold: float = 0.25
    neighbor_discount: float = 0.08
    accelerated_decay_factor: float = 2.5
    velocity_alpha: float = 0.30
    context_credit_decay: float = 0.92
    context_credit_promotion_threshold: float = 0.95
    context_credit_gain_scale: float = 0.65
    context_credit_edge_seed: float = 0.32
    context_credit_match_floor: float = 0.75
    context_support_demote_scale: float = 0.22


class ConnectionSubstrate:
    """Edge-local memory substrate for a single node agent."""

    def __init__(
        self,
        neighbor_ids: Iterable[str],
        config: ConnectionSubstrateConfig | None = None,
    ) -> None:
        self.neighbor_ids = tuple(neighbor_ids)
        self.config = config or ConnectionSubstrateConfig()
        self._context_credit_accumulator: Dict[str, float] = {}
        self._edge_keys = {
            neighbor_id: self._edge_key(neighbor_id)
            for neighbor_id in self.neighbor_ids
        }
        self._action_keys = {
            (neighbor_id, transform_name): self._action_key(neighbor_id, transform_name)
            for neighbor_id in self.neighbor_ids
            for transform_name in SUPPORTED_TRANSFORMS
        }
        self._context_action_keys = {
            (neighbor_id, transform_name, context_bit): self._context_action_key(
                neighbor_id,
                transform_name,
                context_bit,
            )
            for neighbor_id in self.neighbor_ids
            for transform_name in SUPPORTED_TRANSFORMS
            for context_bit in SUPPORTED_CONTEXTS
        }
        self._inner = MemorySubstrate(
            config=SubstrateConfig(
                keys=tuple(self._edge_keys.values())
                + tuple(self._action_keys.values())
                + tuple(self._context_action_keys.values()),
                slow_decay=self.config.slow_decay,
                bistable_threshold=self.config.bistable_threshold,
                write_base_cost=self.config.write_base_cost,
                maintain_base_cost=self.config.maintain_base_cost,
                neighbor_discount=self.config.neighbor_discount,
                accelerated_decay_factor=self.config.accelerated_decay_factor,
                velocity_alpha=self.config.velocity_alpha,
            )
        )

    @staticmethod
    def _edge_key(neighbor_id: str) -> str:
        return f"edge:{neighbor_id}"

    @staticmethod
    def _action_key(neighbor_id: str, transform_name: str) -> str:
        return f"action:{neighbor_id}:{transform_name}"

    @staticmethod
    def _context_action_key(
        neighbor_id: str,
        transform_name: str,
        context_bit: int,
    ) -> str:
        return f"context_action:{neighbor_id}:{transform_name}:{context_bit}"

    @staticmethod
    def _credit_key(
        neighbor_id: str,
        transform_name: str,
        context_bit: int,
    ) -> str:
        return f"{neighbor_id}:{transform_name}:context_{context_bit}"

    def support(self, neighbor_id: str) -> float:
        return self._inner.slow.get(self._edge_keys[neighbor_id], 0.0)

    def velocity(self, neighbor_id: str) -> float:
        return self._inner.slow_velocity.get(self._edge_keys[neighbor_id], 0.0)

    def support_age(self, neighbor_id: str) -> int:
        return self._inner.slow_age.get(self._edge_keys[neighbor_id], 0)

    def action_support(
        self,
        neighbor_id: str,
        transform_name: str,
        context_bit: int | None = None,
    ) -> float:
        key = self._action_keys[(neighbor_id, transform_name)]
        support = self._inner.slow.get(key, 0.0)
        if context_bit in SUPPORTED_CONTEXTS:
            context_key = self._context_action_keys[(neighbor_id, transform_name, context_bit)]
            support = max(support, self._inner.slow.get(context_key, 0.0))
        return support

    def base_action_support(self, neighbor_id: str, transform_name: str) -> float:
        return self._inner.slow.get(self._action_keys[(neighbor_id, transform_name)], 0.0)

    def contextual_action_support(
        self,
        neighbor_id: str,
        transform_name: str,
        context_bit: int,
    ) -> float:
        return self._inner.slow.get(
            self._context_action_keys[(neighbor_id, transform_name, context_bit)],
            0.0,
        )

    def action_velocity(
        self,
        neighbor_id: str,
        transform_name: str,
        context_bit: int | None = None,
    ) -> float:
        key = self._action_keys[(neighbor_id, transform_name)]
        velocity = self._inner.slow_velocity.get(key, 0.0)
        if context_bit in SUPPORTED_CONTEXTS:
            context_key = self._context_action_keys[(neighbor_id, transform_name, context_bit)]
            velocity = max(velocity, self._inner.slow_velocity.get(context_key, 0.0))
        return velocity

    def contextual_action_velocity(
        self,
        neighbor_id: str,
        transform_name: str,
        context_bit: int,
    ) -> float:
        return self._inner.slow_velocity.get(
            self._context_action_keys[(neighbor_id, transform_name, context_bit)],
            0.0,
        )

    def action_support_age(
        self,
        neighbor_id: str,
        transform_name: str,
        context_bit: int | None = None,
    ) -> int:
        key = self._action_keys[(neighbor_id, transform_name)]
        age = self._inner.slow_age.get(key, 0)
        if context_bit in SUPPORTED_CONTEXTS:
            context_key = self._context_action_keys[(neighbor_id, transform_name, context_bit)]
            if self._inner.slow.get(context_key, 0.0) > 0.0:
                return self._inner.slow_age.get(context_key, 0)
        return age

    @property
    def dim_history(self) -> List[DimensionScores]:
        return self._inner.dim_history

    @dim_history.setter
    def dim_history(self, value: List[DimensionScores]) -> None:
        self._inner.dim_history = value

    @property
    def constraint_patterns(self) -> List[ConstraintPattern]:
        return self._inner.constraint_patterns

    def use_cost(
        self,
        neighbor_id: str,
        transform_name: str | None = None,
        context_bit: int | None = None,
    ) -> float:
        support = self.support(neighbor_id)
        action_support = 0.0
        if transform_name is not None and (neighbor_id, transform_name) in self._action_keys:
            action_support = self.action_support(neighbor_id, transform_name, context_bit)
        discounted = (
            self.config.fire_base_cost
            - self.config.fire_discount_scale * support
            - self.config.transform_discount_scale * action_support
        )
        return max(self.config.fire_floor_cost, discounted)

    def edge_key(self, neighbor_id: str) -> str:
        return self._edge_keys[neighbor_id]

    def edge_scores(self) -> Dict[str, float]:
        return {
            neighbor_id: self.support(neighbor_id)
            for neighbor_id in self.neighbor_ids
        }

    def action_scores(self) -> Dict[str, Dict[str, float]]:
        return {
            neighbor_id: {
                transform_name: self.action_support(neighbor_id, transform_name)
                for transform_name in SUPPORTED_TRANSFORMS
            }
            for neighbor_id in self.neighbor_ids
        }

    def is_active_connection(self, neighbor_id: str) -> bool:
        return self._inner.is_active(self._edge_keys[neighbor_id])

    def active_neighbors(self) -> List[str]:
        return [
            neighbor_id
            for neighbor_id in self.neighbor_ids
            if self.is_active_connection(neighbor_id)
        ]

    def active_action_supports(self) -> List[tuple[str, str, int | None]]:
        active: List[tuple[str, str, int | None]] = []
        for (neighbor_id, transform_name), key in self._action_keys.items():
            if self._inner.is_active(key):
                active.append((neighbor_id, transform_name, None))
        for (neighbor_id, transform_name, context_bit), key in self._context_action_keys.items():
            if self._inner.is_active(key):
                active.append((neighbor_id, transform_name, context_bit))
        return active

    def write_cost(self, neighbor_id: str) -> float:
        return self._inner.write_cost(self._edge_keys[neighbor_id])

    def maintain_cost(self, neighbor_id: str) -> float:
        return self._inner.maintain_cost(self._edge_keys[neighbor_id])

    def invest_connection(self, neighbor_id: str, atp_budget: float) -> float | None:
        key = self._edge_keys[neighbor_id]
        cost = self._inner.write_cost(key)
        if atp_budget < cost:
            return None
        self._inner.slow[key] = min(1.0, self._inner.slow[key] + 0.20)
        self._inner.slow_age[key] = 0
        return cost

    def maintain_connections(self, atp_budget: float) -> float:
        total = 0.0
        for neighbor_id in self.active_neighbors():
            key = self._edge_keys[neighbor_id]
            cost = self._maintain_key(key, atp_budget - total)
            if cost is not None:
                total += cost
        return total

    def estimate_maintenance_cost(self) -> float:
        total = 0.0
        for neighbor_id in self.active_neighbors():
            total += self._inner.maintain_cost(self._edge_keys[neighbor_id])
        for neighbor_id, transform_name, context_bit in self.active_action_supports():
            if context_bit in SUPPORTED_CONTEXTS:
                key = self._context_action_keys[(neighbor_id, transform_name, context_bit)]
            else:
                key = self._action_keys[(neighbor_id, transform_name)]
            total += self._inner.maintain_cost(key)
        return total

    def maintain_supports(
        self,
        atp_budget: float,
        *,
        transform_credit: Dict[str, float] | None = None,
        context_transform_credit: Dict[str, float] | None = None,
        branch_transform_credit: Dict[str, float] | None = None,
        context_branch_transform_credit: Dict[str, float] | None = None,
        transform_debt: Dict[str, float] | None = None,
        context_transform_debt: Dict[str, float] | None = None,
        branch_context_credit: Dict[str, float] | None = None,
        branch_context_debt: Dict[str, float] | None = None,
        context_bit: int | None = None,
    ) -> dict[str, object]:
        total = 0.0
        maintained_edges: List[str] = []
        maintained_actions: List[str] = []
        credit = transform_credit or {}
        context_credit = context_transform_credit or {}
        branch_transform = branch_transform_credit or {}
        context_branch_transform = context_branch_transform_credit or {}
        debt = transform_debt or {}
        context_debt = context_transform_debt or {}
        branch_credit = branch_context_credit or {}
        branch_debt = branch_context_debt or {}
        candidates: List[tuple[float, str, str, str, str | None, int | None]] = []

        for neighbor_id in self.active_neighbors():
            key = self._edge_keys[neighbor_id]
            priority = (
                1.0
                + self.support(neighbor_id)
                + 0.05 * min(self.support_age(neighbor_id), 6)
                + max(0.0, -self.velocity(neighbor_id)) * 4.0
            )
            if context_bit in SUPPORTED_CONTEXTS:
                priority += 0.40 * max(
                    0.0,
                    branch_credit.get(f"{neighbor_id}:context_{context_bit}", 0.0),
                )
                priority -= 0.35 * max(
                    0.0,
                    branch_debt.get(f"{neighbor_id}:context_{context_bit}", 0.0),
                )
            candidates.append((priority, key, "edge", neighbor_id, None, None))

        for neighbor_id, transform_name, action_context in self.active_action_supports():
            if action_context in SUPPORTED_CONTEXTS:
                key = self._context_action_keys[(neighbor_id, transform_name, action_context)]
            else:
                key = self._action_keys[(neighbor_id, transform_name)]
            support = self._inner.slow.get(key, 0.0)
            velocity = self._inner.slow_velocity.get(key, 0.0)
            age = self._inner.slow_age.get(key, 0)
            priority = 0.8 + support + 0.05 * min(age, 6) + max(0.0, -velocity) * 4.0
            priority += 0.50 * max(0.0, credit.get(transform_name, 0.0))
            priority += 0.24 * max(
                0.0,
                branch_transform.get(f"{neighbor_id}:{transform_name}", 0.0),
            )
            priority -= 0.40 * max(0.0, debt.get(transform_name, 0.0))
            if (
                action_context in SUPPORTED_CONTEXTS
                and context_bit in SUPPORTED_CONTEXTS
                and action_context == context_bit
            ):
                priority += 0.15
                priority += 0.75 * max(
                    0.0,
                    context_credit.get(f"{transform_name}:context_{action_context}", 0.0),
                )
                priority += 0.28 * max(
                    0.0,
                    branch_credit.get(f"{neighbor_id}:context_{action_context}", 0.0),
                )
                priority += 0.42 * max(
                    0.0,
                    context_branch_transform.get(
                        f"{neighbor_id}:{transform_name}:context_{action_context}",
                        0.0,
                    ),
                )
                priority -= 0.28 * max(
                    0.0,
                    branch_debt.get(f"{neighbor_id}:context_{action_context}", 0.0),
                )
                priority -= 0.90 * max(
                    0.0,
                    context_debt.get(f"{transform_name}:context_{action_context}", 0.0),
                )
            candidates.append(
                (priority, key, "action", neighbor_id, transform_name, action_context)
            )

        candidates.sort(key=lambda item: item[0], reverse=True)

        for _, key, kind, neighbor_id, transform_name, action_context in candidates:
            cost = self._maintain_key(key, atp_budget - total)
            if cost is None:
                continue
            total += cost
            if kind == "edge":
                maintained_edges.append(neighbor_id)
                continue
            label = f"{neighbor_id}:{transform_name}"
            if action_context in SUPPORTED_CONTEXTS:
                label = f"{label}:context_{action_context}"
            maintained_actions.append(label)

        return {
            "spent": total,
            "maintained_edges": maintained_edges,
            "maintained_actions": maintained_actions,
        }

    def maintenance_metrics(self) -> Dict[str, float]:
        edge_active = self.active_neighbors()
        action_active = self.active_action_supports()
        edge_recent = [
            neighbor_id
            for neighbor_id in edge_active
            if self.support_age(neighbor_id) <= RECENT_MAINTENANCE_AGE
        ]
        action_recent = [
            (neighbor_id, transform_name, context_bit)
            for neighbor_id, transform_name, context_bit in action_active
            if self.action_support_age(neighbor_id, transform_name, context_bit) <= RECENT_MAINTENANCE_AGE
        ]
        active_count = len(edge_active) + len(action_active)
        recent_count = len(edge_recent) + len(action_recent)
        support_total = sum(self.support(neighbor_id) for neighbor_id in edge_active)
        for neighbor_id, transform_name, context_bit in action_active:
            if context_bit in SUPPORTED_CONTEXTS:
                key = self._context_action_keys[(neighbor_id, transform_name, context_bit)]
            else:
                key = self._action_keys[(neighbor_id, transform_name)]
            support_total += self._inner.slow.get(key, 0.0)
        return {
            "active_edge_count": float(len(edge_active)),
            "active_action_count": float(len(action_active)),
            "recently_maintained_edge_count": float(len(edge_recent)),
            "recently_maintained_action_count": float(len(action_recent)),
            "edge_maintenance_ratio": len(edge_recent) / max(len(edge_active), 1),
            "action_maintenance_ratio": len(action_recent) / max(len(action_active), 1),
            "maintenance_ratio": recent_count / max(active_count, 1),
            "mean_active_support": support_total / max(active_count, 1),
        }

    def update_fast(self, observation: dict[str, float]) -> None:
        self._inner.update_fast(observation)

    def update_dim_context(self, dim_scores: DimensionScores) -> None:
        self._inner.update_dim_context(dim_scores)

    def current_dim_trends(self) -> Dict[str, float]:
        if len(self._inner.dim_history) < 4:
            return {key: 0.0 for key in self._edge_keys.values()}

        recent = self._inner.dim_history[-6:]
        half = len(recent) // 2
        first_half = recent[:half]
        second_half = recent[half:]

        trends = {}
        for key in (
            tuple(self._edge_keys.values())
            + tuple(self._action_keys.values())
            + tuple(self._context_action_keys.values())
        ):
            early = sum(item.get(key, 0.0) for item in first_half) / max(len(first_half), 1)
            late = sum(item.get(key, 0.0) for item in second_half) / max(len(second_half), 1)
            trends[key] = late - early
        return trends

    def seed_support(self, neighbor_ids: Iterable[str], value: float = 0.25) -> None:
        self._inner.seed_support(
            [self._edge_keys[neighbor_id] for neighbor_id in neighbor_ids if neighbor_id in self._edge_keys],
            value=value,
        )

    def seed_action_support(
        self,
        neighbor_id: str,
        transform_name: str,
        value: float = 0.25,
        context_bit: int | None = None,
    ) -> None:
        keys: List[str] = []
        if context_bit in SUPPORTED_CONTEXTS:
            context_key = self._context_action_keys.get((neighbor_id, transform_name, context_bit))
            if context_key is not None:
                keys.append(context_key)
        else:
            key = self._action_keys.get((neighbor_id, transform_name))
            if key is not None:
                keys.append(key)
        for key in keys:
            current = self._inner.slow.get(key, 0.0)
            self._inner.seed_support((key,), value=max(current, value))

    def record_context_feedback(
        self,
        neighbor_id: str,
        transform_name: str,
        context_bit: int | None,
        *,
        credit_signal: float,
        bit_match_ratio: float,
    ) -> bool:
        if context_bit not in SUPPORTED_CONTEXTS:
            return False
        if neighbor_id not in self.neighbor_ids:
            return False
        key = self._credit_key(neighbor_id, transform_name, context_bit)
        if bit_match_ratio < self.config.context_credit_match_floor:
            mismatch = self.config.context_credit_match_floor - max(0.0, bit_match_ratio)
            mismatch_ratio = mismatch / max(self.config.context_credit_match_floor, 1e-9)
            demotion = min(
                0.85,
                self.config.context_support_demote_scale + 0.45 * mismatch_ratio,
            )
            context_support_key = self._context_action_keys[(neighbor_id, transform_name, context_bit)]
            current_support = self._inner.slow.get(context_support_key, 0.0)
            reduced = max(0.0, current_support * (1.0 - demotion))
            self._inner.slow[context_support_key] = reduced
            self._context_credit_accumulator[key] = self._context_credit_accumulator.get(key, 0.0) * 0.2
            if reduced <= 1e-4:
                self._inner.slow_age[context_support_key] = max(
                    self._inner.slow_age.get(context_support_key, 0),
                    1,
                )
            return False
        prior = self._context_credit_accumulator.get(key, 0.0)
        gain = self.config.context_credit_gain_scale * max(0.0, credit_signal) * max(0.0, bit_match_ratio)
        updated = min(2.0, prior * 0.75 + gain)
        self._context_credit_accumulator[key] = updated
        if updated < self.config.context_credit_promotion_threshold:
            return False

        if self.support(neighbor_id) < self.config.context_credit_edge_seed:
            self.seed_support((neighbor_id,), value=self.config.context_credit_edge_seed)
        existing = self.contextual_action_support(neighbor_id, transform_name, context_bit)
        promoted_value = min(1.0, max(existing, 0.24 + 0.18 * min(updated, 1.5)))
        self.seed_action_support(
            neighbor_id,
            transform_name,
            value=promoted_value,
            context_bit=context_bit,
        )
        self._context_credit_accumulator[key] = max(
            0.0,
            updated - self.config.context_credit_promotion_threshold * 0.6,
        )
        return True

    def add_pattern(self, pattern: ConstraintPattern) -> None:
        self._inner.constraint_patterns.append(pattern)

    def tick(self) -> None:
        self._inner.tick()
        for key in list(self._context_credit_accumulator.keys()):
            self._context_credit_accumulator[key] *= self.config.context_credit_decay
            if self._context_credit_accumulator[key] < 1e-4:
                del self._context_credit_accumulator[key]

    def snapshot(self) -> SubstrateSnapshot:
        snapshot = self._inner.snapshot()
        snapshot.metadata["neighbor_ids"] = list(self.neighbor_ids)
        snapshot.metadata["active_neighbors"] = self.active_neighbors()
        snapshot.metadata["maintenance_metrics"] = self.maintenance_metrics()
        snapshot.metadata["context_credit_accumulator"] = dict(self._context_credit_accumulator)
        return snapshot

    def save_state(self) -> SubstrateSnapshot:
        snapshot = self._inner.save_state()
        snapshot.metadata["neighbor_ids"] = list(self.neighbor_ids)
        snapshot.metadata["active_neighbors"] = self.active_neighbors()
        snapshot.metadata["maintenance_metrics"] = self.maintenance_metrics()
        snapshot.metadata["context_credit_accumulator"] = dict(self._context_credit_accumulator)
        return snapshot

    def load_state(self, snapshot: SubstrateSnapshot) -> None:
        self._inner.load_state(snapshot)
        self._context_credit_accumulator = {
            str(key): float(value)
            for key, value in snapshot.metadata.get("context_credit_accumulator", {}).items()
        }

    def copy_overlap_from(self, other: "ConnectionSubstrate") -> None:
        for neighbor_id in self.neighbor_ids:
            if neighbor_id in other.neighbor_ids:
                edge_key = self._edge_keys[neighbor_id]
                other_edge_key = other._edge_keys[neighbor_id]
                self._inner.slow[edge_key] = other._inner.slow.get(other_edge_key, 0.0)
                self._inner.slow_age[edge_key] = other._inner.slow_age.get(other_edge_key, 0)
                self._inner.slow_velocity[edge_key] = other._inner.slow_velocity.get(other_edge_key, 0.0)
            for transform_name in SUPPORTED_TRANSFORMS:
                action_key = self._action_keys[(neighbor_id, transform_name)]
                other_action_key = other._action_keys.get((neighbor_id, transform_name))
                if other_action_key is not None:
                    self._inner.slow[action_key] = other._inner.slow.get(other_action_key, 0.0)
                    self._inner.slow_age[action_key] = other._inner.slow_age.get(other_action_key, 0)
                    self._inner.slow_velocity[action_key] = other._inner.slow_velocity.get(other_action_key, 0.0)
                for context_bit in SUPPORTED_CONTEXTS:
                    context_key = self._context_action_keys[(neighbor_id, transform_name, context_bit)]
                    other_context_key = other._context_action_keys.get((neighbor_id, transform_name, context_bit))
                    if other_context_key is None:
                        continue
                    self._inner.slow[context_key] = other._inner.slow.get(other_context_key, 0.0)
                    self._inner.slow_age[context_key] = other._inner.slow_age.get(other_context_key, 0)
                    self._inner.slow_velocity[context_key] = other._inner.slow_velocity.get(other_context_key, 0.0)
                    credit_key = self._credit_key(neighbor_id, transform_name, context_bit)
                    other_credit_key = other._credit_key(neighbor_id, transform_name, context_bit)
                    if other_credit_key in other._context_credit_accumulator:
                        self._context_credit_accumulator[credit_key] = other._context_credit_accumulator[other_credit_key]
        self._inner.dim_history = list(other._inner.dim_history)
        self._inner.constraint_patterns = list(other._inner.constraint_patterns)

    def _maintain_key(self, key: str, atp_budget: float) -> float | None:
        if self._inner.slow.get(key, 0.0) <= 0.0:
            return None
        cost = self._inner.maintain_cost(key)
        if atp_budget < cost:
            return None
        self._inner.slow[key] = min(
            1.0,
            self._inner.slow[key] + self._inner.config.slow_decay * 2.0,
        )
        self._inner.slow_age[key] = 0
        return cost
