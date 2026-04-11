from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from .patterns import ConstraintPattern
from .types import DimensionScores, SubstrateSnapshot


@dataclass
class SubstrateConfig:
    """Neutral slow-memory substrate defaults for the generalized core."""

    keys: tuple[str, ...] = (
        "continuity",
        "vitality",
        "contextual_fit",
        "differentiation",
        "accountability",
        "reflexivity",
    )
    slow_decay: float = 0.03
    bistable_threshold: float = 0.25
    write_base_cost: float = 0.15
    maintain_base_cost: float = 0.03
    neighbor_discount: float = 0.12
    accelerated_decay_factor: float = 3.0
    velocity_alpha: float = 0.30
    max_patterns: int = 12


@dataclass
class MemorySubstrate:
    """Generalized two-layer memory scaffold for Phase 4.5."""

    config: SubstrateConfig = field(default_factory=SubstrateConfig)
    fast: Dict[str, float] = field(default_factory=dict)
    slow: Dict[str, float] = field(default_factory=dict)
    slow_age: Dict[str, int] = field(default_factory=dict)
    slow_velocity: Dict[str, float] = field(default_factory=dict)
    constraint_patterns: List[ConstraintPattern] = field(default_factory=list)
    dim_history: List[DimensionScores] = field(default_factory=list)
    _slow_prior: Dict[str, float] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        for key in self.config.keys:
            self.fast.setdefault(key, 0.0)
            self.slow.setdefault(key, 0.0)
            self.slow_age.setdefault(key, 0)
            self.slow_velocity.setdefault(key, 0.0)
            self._slow_prior.setdefault(key, 0.0)

    @property
    def keys(self) -> tuple[str, ...]:
        return self.config.keys

    def update_fast(self, observation: Dict[str, float]) -> None:
        for key in self.keys:
            if key in observation:
                self.fast[key] = observation[key]

    def update_dim_context(self, dim_scores: DimensionScores) -> None:
        self.dim_history.append(dict(dim_scores))
        if len(self.dim_history) > 20:
            self.dim_history.pop(0)

    def tick(self) -> None:
        for key in self.keys:
            value = self.slow.get(key, 0.0)
            if value <= 0.0:
                continue

            decay = self.config.slow_decay
            if value < self.config.bistable_threshold:
                decay *= self.config.accelerated_decay_factor

            self.slow[key] = max(0.0, value - decay)
            self.slow_age[key] += 1

        alpha = self.config.velocity_alpha
        for key in self.keys:
            delta = self.slow.get(key, 0.0) - self._slow_prior.get(key, 0.0)
            self.slow_velocity[key] = (
                alpha * delta
                + (1.0 - alpha) * self.slow_velocity.get(key, 0.0)
            )
            self._slow_prior[key] = self.slow.get(key, 0.0)

    def is_active(self, key: str) -> bool:
        return self.slow.get(key, 0.0) >= self.config.bistable_threshold

    def active_keys(self) -> List[str]:
        return [key for key in self.keys if self.is_active(key)]

    def active_count(self) -> int:
        return len(self.active_keys())

    def write_cost(self, key: str) -> float:
        base = self.config.write_base_cost
        neighbors = sum(
            1 for other in self.keys if other != key and self.is_active(other)
        )
        discount = min(neighbors * self.config.neighbor_discount, 0.60)
        return base * (1.0 - discount)

    def maintain_cost(self, key: str) -> float:
        base = self.config.maintain_base_cost
        neighbors = sum(
            1 for other in self.keys if other != key and self.is_active(other)
        )
        discount = min(neighbors * self.config.neighbor_discount, 0.50)
        return base * (1.0 - discount)

    def snapshot(self) -> SubstrateSnapshot:
        return SubstrateSnapshot(
            fast=dict(self.fast),
            slow=dict(self.slow),
            slow_age=dict(self.slow_age),
            slow_velocity=dict(self.slow_velocity),
            metadata={
                "active_keys": self.active_keys(),
                "active_count": self.active_count(),
                "pattern_count": len(self.constraint_patterns),
                "keys": list(self.keys),
            },
        )

    def save_state(self) -> SubstrateSnapshot:
        snapshot = self.snapshot()
        snapshot.metadata["patterns"] = [
            pattern.to_dict() for pattern in self.constraint_patterns
        ]
        snapshot.metadata["dim_history"] = list(self.dim_history)
        return snapshot

    def load_state(self, snapshot: SubstrateSnapshot) -> None:
        for key in self.keys:
            self.fast[key] = snapshot.fast.get(key, 0.0)
            self.slow[key] = snapshot.slow.get(key, 0.0)
            self.slow_age[key] = snapshot.slow_age.get(key, 0)
            self.slow_velocity[key] = snapshot.slow_velocity.get(key, 0.0)
            self._slow_prior[key] = self.slow[key]

        self.constraint_patterns = [
            ConstraintPattern.from_dict(data)
            for data in snapshot.metadata.get("patterns", [])
        ]
        self.dim_history = [
            dict(item) for item in snapshot.metadata.get("dim_history", [])
        ]

    def seed_support(self, keys: Iterable[str], value: float = 0.25) -> None:
        """Utility for later promotion logic and manual warm starts."""
        clamped = max(0.0, min(1.0, value))
        for key in keys:
            if key not in self.slow:
                continue
            self.slow[key] = clamped
            self.slow_age[key] = 0
            self._slow_prior[key] = clamped
