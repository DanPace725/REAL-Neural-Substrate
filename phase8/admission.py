from __future__ import annotations

from dataclasses import asdict, dataclass


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


@dataclass
class AdmissionSubstrate:
    """Slow local controller for source-boundary packet admission."""

    support: float = 0.5
    velocity: float = 0.0
    learning_rate: float = 0.10
    baseline_decay: float = 0.05
    velocity_alpha: float = 0.35

    def allowance(
        self,
        *,
        available_slots: int,
        backlog_pressure: float,
        atp_ratio: float,
        reward_ratio: float,
        inbox_load: float,
        oldest_age: float,
        feedback_pending: float,
        min_rate: int,
        max_rate: int,
    ) -> int:
        if available_slots <= 0 or max_rate <= 0:
            return 0

        score = (
            0.20
            + 0.28 * self.support
            + 0.18 * atp_ratio
            + 0.14 * reward_ratio
            + 0.20 * backlog_pressure
            + 0.10 * feedback_pending
            - 0.18 * inbox_load
            - 0.12 * oldest_age
        )
        normalized = _clamp(score)
        span = max(0, max_rate - max(0, min_rate))
        allowance = max(0, min_rate) + int(round(span * normalized))
        return max(0, min(allowance, available_slots, max_rate))

    def update(
        self,
        *,
        backlog_before: int,
        backlog_after: int,
        admitted: int,
        routed_packets: int,
        feedback_gained: int,
        action_cost: float,
        feedback_energy: float,
        net_energy: float,
        inbox_load: float,
        oldest_age: float,
        atp_ratio: float,
    ) -> dict[str, float]:
        efficiency_signal = self._efficiency_signal(
            feedback_energy=feedback_energy,
            action_cost=action_cost,
        )
        balance_signal = _clamp((net_energy / 0.18) * 0.5 + 0.5) * 2.0 - 1.0
        signal = 0.0

        signal += 0.22 * efficiency_signal
        signal += 0.16 * balance_signal
        if feedback_gained > 0 and backlog_after < backlog_before:
            signal += 0.12
        if admitted > 0 and routed_packets > 0 and efficiency_signal > 0.0:
            signal += 0.06

        if oldest_age >= 0.60:
            signal -= 0.16
        if inbox_load >= 0.75:
            signal -= 0.12
        if backlog_after > backlog_before:
            signal -= 0.10
        if atp_ratio <= 0.25:
            signal -= 0.12
        if action_cost > 0.0 and feedback_energy <= 0.0:
            signal -= 0.14
        if admitted > routed_packets and efficiency_signal < 0.0:
            signal -= 0.08

        delta = self.learning_rate * signal - self.baseline_decay * (self.support - 0.5)
        next_support = _clamp(self.support + delta)
        actual_delta = next_support - self.support
        self.support = next_support
        self.velocity = (1.0 - self.velocity_alpha) * self.velocity + self.velocity_alpha * actual_delta
        return {
            "delta": actual_delta,
            "efficiency_signal": efficiency_signal,
            "balance_signal": balance_signal,
        }

    @staticmethod
    def _efficiency_signal(*, feedback_energy: float, action_cost: float) -> float:
        if action_cost <= 1e-9 and feedback_energy <= 1e-9:
            return 0.0
        if feedback_energy <= 1e-9:
            return -0.7
        if action_cost <= 1e-9:
            return 1.0
        ratio = feedback_energy / max(action_cost, 1e-9)
        return _clamp((ratio - 1.0) / 1.5, -1.0, 1.0)

    def export_state(self) -> dict[str, float]:
        return asdict(self)

    @classmethod
    def from_state(cls, payload: dict[str, float] | None) -> "AdmissionSubstrate":
        if not payload:
            return cls()
        return cls(**payload)
