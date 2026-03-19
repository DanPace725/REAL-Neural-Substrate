from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from real_core.consolidation import BasicConsolidationPipeline
from real_core.patterns import ConstraintPattern
from real_core.types import CycleEntry

from .substrate import ConnectionSubstrate


def _route_neighbor(action: str) -> str | None:
    if action.startswith("route_transform:"):
        parts = action.split(":")
        if len(parts) == 3:
            return parts[1]
        return None
    if action.startswith("route:"):
        return action.split(":", 1)[1]
    return None


@dataclass
class Phase8ConsolidationPipeline(BasicConsolidationPipeline):
    """Promotes routing attractors into edge-local maintained substrate."""

    support_seed_value: float = 0.32
    action_support_seed_value: float = 0.24
    pattern_strength: float = 0.45
    min_route_uses: int = 2
    positive_delta_floor: float = 0.0
    negative_delta_floor: float = -0.02

    def consolidate(
        self,
        entries: List[CycleEntry],
        substrate=None,
    ) -> List[CycleEntry]:
        retained = super().consolidate(entries, substrate)
        if isinstance(substrate, ConnectionSubstrate):
            self._promote_route_patterns(entries, substrate)
            self._promote_transform_patterns(entries, substrate)
        return retained

    def _promote_route_patterns(
        self,
        entries: List[CycleEntry],
        substrate: ConnectionSubstrate,
    ) -> None:
        route_entries = [entry for entry in entries if _route_neighbor(entry.action) is not None]
        if len(route_entries) < self.min_route_uses:
            return

        grouped: Dict[str, List[CycleEntry]] = {}
        for entry in route_entries:
            neighbor_id = _route_neighbor(entry.action)
            if neighbor_id is None:
                continue
            if neighbor_id not in substrate.neighbor_ids:
                continue
            grouped.setdefault(neighbor_id, []).append(entry)

        if not grouped:
            return

        promoted_positive: List[str] = []
        for neighbor_id, neighbor_entries in grouped.items():
            if len(neighbor_entries) < self.min_route_uses:
                continue

            mean_delta = sum(entry.delta for entry in neighbor_entries) / len(neighbor_entries)
            mean_coherence = sum(entry.coherence for entry in neighbor_entries) / len(neighbor_entries)
            support_bias = 0.85 if mean_delta >= self.positive_delta_floor else 0.25
            if mean_delta >= self.positive_delta_floor:
                promoted_positive.append(neighbor_id)
                if substrate.support(neighbor_id) < self.support_seed_value:
                    substrate.seed_support((neighbor_id,), value=self.support_seed_value)
                pattern = self._build_pattern(
                    substrate=substrate,
                    focus_neighbor=neighbor_id,
                    valence=min(1.0, 0.4 + max(0.0, mean_delta) * 8.0),
                    strength=self.pattern_strength,
                    coherence_level=mean_coherence,
                    focus_value=support_bias,
                    source="route_attractor",
                )
                self._merge_or_append_pattern(substrate, pattern)
            elif mean_delta <= self.negative_delta_floor:
                pattern = self._build_pattern(
                    substrate=substrate,
                    focus_neighbor=neighbor_id,
                    valence=-0.55,
                    strength=self.pattern_strength * 0.8,
                    coherence_level=mean_coherence,
                    focus_value=0.10,
                    source="route_trough",
                )
                self._merge_or_append_pattern(substrate, pattern)

        if len(promoted_positive) > 1:
            substrate.seed_support(promoted_positive, value=self.support_seed_value)

    def _promote_transform_patterns(
        self,
        entries: List[CycleEntry],
        substrate: ConnectionSubstrate,
    ) -> None:
        grouped: Dict[tuple[str, str], List[CycleEntry]] = {}
        for entry in entries:
            if not entry.action.startswith("route_transform:"):
                continue
            _, neighbor_id, transform_name = entry.action.split(":", 2)
            if neighbor_id not in substrate.neighbor_ids:
                continue
            grouped.setdefault((neighbor_id, transform_name), []).append(entry)

        for (neighbor_id, transform_name), action_entries in grouped.items():
            if len(action_entries) < self.min_route_uses:
                continue
            mean_delta = sum(entry.delta for entry in action_entries) / len(action_entries)
            if mean_delta < self.positive_delta_floor:
                continue
            context_groups: Dict[int | None, List[CycleEntry]] = {}
            for entry in action_entries:
                if entry.state_before.get("effective_has_context", 0.0) >= 0.5:
                    context_value = entry.state_before.get("effective_context_bit")
                    context_confidence = float(entry.state_before.get("effective_context_confidence", 0.0))
                    promotion_ready = entry.state_before.get("context_promotion_ready", 0.0) >= 0.5
                    if not promotion_ready or context_confidence < 0.75:
                        context_value = None
                    elif context_value is not None:
                        context_value = int(float(context_value))
                else:
                    context_value = entry.state_before.get("head_context_bit")
                    if entry.state_before.get("head_has_context", 0.0) < 0.5:
                        context_value = None
                    elif context_value is not None:
                        context_value = int(float(context_value))
                context_groups.setdefault(context_value, []).append(entry)

            for context_bit, context_entries in context_groups.items():
                context_delta = sum(entry.delta for entry in context_entries) / len(context_entries)
                if context_delta < self.positive_delta_floor:
                    continue
                if substrate.action_support(neighbor_id, transform_name, context_bit) < self.action_support_seed_value:
                    substrate.seed_action_support(
                        neighbor_id,
                        transform_name,
                        value=self.action_support_seed_value,
                        context_bit=context_bit,
                    )
                pattern = self._build_transform_pattern(
                    substrate=substrate,
                    focus_neighbor=neighbor_id,
                    focus_transform=transform_name,
                    context_bit=context_bit,
                    valence=min(1.0, 0.4 + max(0.0, context_delta) * 8.0),
                    strength=self.pattern_strength,
                    coherence_level=sum(entry.coherence for entry in context_entries) / len(context_entries),
                    focus_value=0.85,
                    source=(
                        "context_transform_attractor"
                        if context_bit is not None
                        else "transform_attractor"
                    ),
                )
                self._merge_or_append_pattern(substrate, pattern)

    def _build_pattern(
        self,
        substrate: ConnectionSubstrate,
        focus_neighbor: str,
        *,
        valence: float,
        strength: float,
        coherence_level: float,
        focus_value: float,
        source: str,
    ) -> ConstraintPattern:
        dim_scores = {}
        dim_trends = substrate.current_dim_trends()
        for neighbor_id in substrate.neighbor_ids:
            key = substrate.edge_key(neighbor_id)
            if neighbor_id == focus_neighbor:
                dim_scores[key] = focus_value
                dim_trends[key] = max(dim_trends.get(key, 0.0), 0.08 if valence > 0 else -0.08)
            else:
                dim_scores[key] = 0.25 if valence > 0 else 0.55
                dim_trends[key] = dim_trends.get(key, 0.0)
        return ConstraintPattern(
            dim_scores=dim_scores,
            dim_trends=dim_trends,
            valence=valence,
            strength=strength,
            coherence_level=coherence_level,
            source=source,
        )

    def _build_transform_pattern(
        self,
        substrate: ConnectionSubstrate,
        *,
        focus_neighbor: str,
        focus_transform: str,
        context_bit: int | None,
        valence: float,
        strength: float,
        coherence_level: float,
        focus_value: float,
        source: str,
    ) -> ConstraintPattern:
        dim_scores = {}
        dim_trends = substrate.current_dim_trends()
        base_value = 0.25 if valence > 0 else 0.55
        for neighbor_id in substrate.neighbor_ids:
            for transform_name in substrate.action_scores().get(neighbor_id, {}).keys():
                key = substrate.action_key(neighbor_id, transform_name)
                if neighbor_id == focus_neighbor and transform_name == focus_transform:
                    dim_scores[key] = focus_value
                    dim_trends[key] = max(
                        dim_trends.get(key, 0.0),
                        0.08 if valence > 0 else -0.08,
                    )
                else:
                    dim_scores[key] = base_value
                    dim_trends[key] = dim_trends.get(key, 0.0)
                if context_bit is not None:
                    try:
                        context_key = substrate.context_action_key(
                            neighbor_id,
                            transform_name,
                            context_bit,
                        )
                    except KeyError:
                        continue
                    if neighbor_id == focus_neighbor and transform_name == focus_transform:
                        dim_scores[context_key] = focus_value
                        dim_trends[context_key] = max(
                            dim_trends.get(context_key, 0.0),
                            0.08 if valence > 0 else -0.08,
                        )
                    else:
                        dim_scores[context_key] = base_value
                        dim_trends[context_key] = dim_trends.get(context_key, 0.0)
        return ConstraintPattern(
            dim_scores=dim_scores,
            dim_trends=dim_trends,
            valence=valence,
            strength=strength,
            coherence_level=coherence_level,
            source=source,
        )

    def _merge_or_append_pattern(
        self,
        substrate: ConnectionSubstrate,
        pattern: ConstraintPattern,
    ) -> None:
        for existing in substrate.constraint_patterns:
            if existing.valence * pattern.valence <= 0:
                continue
            similarity = existing.match_score(pattern.dim_scores, pattern.dim_trends)
            if similarity >= 0.75:
                existing.match_count += 1
                existing.strength = min(1.0, existing.strength + 0.08)
                existing.coherence_level = (
                    existing.coherence_level * 0.7 + pattern.coherence_level * 0.3
                )
                return
        substrate.add_pattern(pattern)
