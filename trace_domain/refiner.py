"""Refiner sub-agent: a REAL agent that improves existing organizational structure.

The refiner is spawned by the organizer when reflexivity or accountability
are stuck.  It runs its own REAL loop with its own coherence model, examines
existing groups for outliers and orphans, and deposits refinement suggestions
back into the shared environment.

The refiner's six dimensions are tuned for refinement work:
  P1 Continuity      — stable quality signal across groups examined
  P2 Vitality        — groups examined per cycle (throughput)
  P3 Contextual Fit  — placement quality (how well suggestions match)
  P4 Differentiation — distinct improvement suggestions (not redundant)
  P5 Accountability  — coverage (what fraction of groups/orphans has been examined)
  P6 Reflexivity     — revises own suggestions when quality drops
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple

from real_core.engine import RealCoreEngine
from real_core.substrate import MemorySubstrate, SubstrateConfig
from real_core.types import (
    ActionOutcome,
    CycleEntry,
    DimensionScores,
    GCOStatus,
)

from .environment import TraceEnvironment


# ---------------------------------------------------------------------------
# Refiner results — the communication channel back to the organizer
# ---------------------------------------------------------------------------

@dataclass
class RefinementSuggestion:
    """A single refinement action suggested by the refiner."""

    action_type: str  # "reassign", "place_orphan", "flag_outlier"
    trace_id: int
    from_group: str  # empty for orphan placement
    to_group: str
    confidence: float  # how sure the refiner is
    reason: str


@dataclass
class RefinerResults:
    """Output deposited into the environment by the refiner."""

    suggestions: List[RefinementSuggestion] = field(default_factory=list)
    group_quality: Dict[str, float] = field(default_factory=dict)
    orphans_examined: int = 0
    groups_examined: int = 0
    cycles_used: int = 0
    final_coherence: float = 0.0


# ---------------------------------------------------------------------------
# Refiner adapters (its own perception/action/coherence, not the organizer's)
# ---------------------------------------------------------------------------

class RefinerObserver:
    """The refiner observes the state of its own refinement work."""

    def __init__(self, state: _RefinerState) -> None:
        self.state = state

    def observe(self, cycle: int) -> Dict[str, float]:
        s = self.state
        total_groups = len(s.group_names)
        total_orphans = len(s.orphan_ids)

        groups_done = len(s.examined_groups)
        orphans_done = len(s.examined_orphans)
        suggestion_count = len(s.suggestions)
        outlier_count = len(s.outliers)

        # Coverage ratios
        group_coverage = groups_done / max(1, total_groups)
        orphan_coverage = orphans_done / max(1, total_orphans)

        # Quality signal: mean of computed group qualities
        mean_quality = 0.0
        if s.group_quality:
            mean_quality = sum(s.group_quality.values()) / len(s.group_quality)

        # Suggestion diversity: unique action types used
        action_types_used = len(set(sg.action_type for sg in s.suggestions)) if s.suggestions else 0
        diversity = min(1.0, action_types_used / 3.0)  # 3 possible types

        return {
            "group_coverage": group_coverage,
            "orphan_coverage": orphan_coverage,
            "mean_quality": mean_quality,
            "suggestion_count": min(1.0, suggestion_count / 20.0),
            "outlier_count": min(1.0, outlier_count / 10.0),
            "diversity": diversity,
            "cycle": float(cycle),
        }


class RefinerActions:
    """Actions the refiner can take within its own loop."""

    def __init__(self, env: TraceEnvironment, state: _RefinerState) -> None:
        self.env = env
        self.state = state

    def available_actions(self, history_size: int) -> List[str]:
        s = self.state
        actions = ["rest"]

        # Examine next unexamined group
        unexamined_groups = [g for g in s.group_names if g not in s.examined_groups]
        if unexamined_groups:
            actions.append("examine_group")

        # Examine next unexamined orphan (only after some groups examined)
        unexamined_orphans = [oid for oid in s.orphan_ids if oid not in s.examined_orphans]
        if unexamined_orphans and s.examined_groups:
            actions.append("examine_orphan")

        # Suggest reassignment for flagged outliers
        unreassigned = [
            (tid, grp, score) for tid, grp, score in s.outliers
            if not any(
                sg.trace_id == tid and sg.action_type == "reassign"
                for sg in s.suggestions
            )
        ]
        if unreassigned:
            actions.append("suggest_reassignment")

        return actions

    def execute(self, action: str) -> ActionOutcome:
        s = self.state
        t0 = time.perf_counter()

        if action == "examine_group":
            return self._examine_group(t0)

        if action == "examine_orphan":
            return self._examine_orphan(t0)

        if action == "suggest_reassignment":
            return self._suggest_reassignment(t0)

        if action == "rest":
            return ActionOutcome(success=True, result={"rested": True}, cost_secs=0.001)

        return ActionOutcome(success=False, result={"reason": f"unknown: {action}"}, cost_secs=0.001)

    # ---- action implementations ----

    def _examine_group(self, t0: float) -> ActionOutcome:
        s = self.state
        unexamined = [g for g in s.group_names if g not in s.examined_groups]
        if not unexamined:
            return ActionOutcome(success=False, result={"reason": "all groups examined"}, cost_secs=0.001)

        group_name = unexamined[0]
        s.examined_groups.add(group_name)

        group = self.env.org.groups.get(group_name)
        if not group or len(group.member_ids) < 2:
            # Trivial group, record quality = 1.0 (no outliers possible)
            s.group_quality[group_name] = 1.0 if group and group.member_ids else 0.0
            elapsed = time.perf_counter() - t0
            return ActionOutcome(
                success=True,
                result={"group": group_name, "quality": s.group_quality[group_name], "outliers": 0},
                cost_secs=max(elapsed, 0.002),
            )

        members = group.member_ids

        # Compute mean pairwise similarity (reuse cache where possible)
        pair_sims: List[float] = []
        for i, id_a in enumerate(members):
            for id_b in members[i + 1:]:
                key = _pair_key(id_a, id_b)
                if key not in s.similarity_cache:
                    s.similarity_cache[key] = self.env.trace_similarity(id_a, id_b)
                pair_sims.append(s.similarity_cache[key])

        group_mean = sum(pair_sims) / len(pair_sims) if pair_sims else 0.0
        s.group_quality[group_name] = group_mean

        # Find outliers: members whose mean similarity to groupmates is
        # significantly below the group mean
        for tid in members:
            sims_to_others = []
            for other in members:
                if other == tid:
                    continue
                key = _pair_key(tid, other)
                sims_to_others.append(s.similarity_cache.get(key, 0.0))

            member_mean = sum(sims_to_others) / len(sims_to_others) if sims_to_others else 0.0
            # Outlier if member's mean is < 60% of group mean (or absolute < 0.03)
            if group_mean > 0.0 and member_mean < group_mean * 0.6:
                outlier_score = 1.0 - (member_mean / group_mean) if group_mean > 0 else 1.0
                s.outliers.append((tid, group_name, outlier_score))
                s.suggestions.append(RefinementSuggestion(
                    action_type="flag_outlier",
                    trace_id=tid,
                    from_group=group_name,
                    to_group="",
                    confidence=min(1.0, outlier_score),
                    reason=f"mean sim {member_mean:.3f} vs group mean {group_mean:.3f}",
                ))
            elif member_mean < 0.03 and len(members) > 2:
                s.outliers.append((tid, group_name, 0.8))
                s.suggestions.append(RefinementSuggestion(
                    action_type="flag_outlier",
                    trace_id=tid,
                    from_group=group_name,
                    to_group="",
                    confidence=0.8,
                    reason=f"near-zero similarity to groupmates ({member_mean:.3f})",
                ))

        outlier_count = sum(1 for _, g, _ in s.outliers if g == group_name)
        elapsed = time.perf_counter() - t0
        return ActionOutcome(
            success=True,
            result={"group": group_name, "quality": group_mean, "outliers": outlier_count, "members": len(members)},
            cost_secs=max(elapsed, 0.005),
        )

    def _examine_orphan(self, t0: float) -> ActionOutcome:
        s = self.state
        unexamined = [oid for oid in s.orphan_ids if oid not in s.examined_orphans]
        if not unexamined:
            return ActionOutcome(success=False, result={"reason": "all orphans examined"}, cost_secs=0.001)

        orphan_id = unexamined[0]
        s.examined_orphans.add(orphan_id)

        # Compute similarity to each examined group
        best_group = ""
        best_sim = -1.0
        for group_name in s.examined_groups:
            group = self.env.org.groups.get(group_name)
            if not group or not group.member_ids:
                continue
            sims = []
            for mid in group.member_ids:
                key = _pair_key(orphan_id, mid)
                if key not in s.similarity_cache:
                    s.similarity_cache[key] = self.env.trace_similarity(orphan_id, mid)
                sims.append(s.similarity_cache[key])
            mean_sim = sum(sims) / len(sims) if sims else 0.0
            if mean_sim > best_sim:
                best_sim = mean_sim
                best_group = group_name

        # Suggest placement if the match is decent
        placed = False
        if best_group and best_sim > 0.04:
            confidence = min(1.0, best_sim / 0.15)  # full confidence at 0.15 similarity
            s.suggestions.append(RefinementSuggestion(
                action_type="place_orphan",
                trace_id=orphan_id,
                from_group="",
                to_group=best_group,
                confidence=confidence,
                reason=f"mean sim to {best_group}: {best_sim:.3f}",
            ))
            placed = True

        elapsed = time.perf_counter() - t0
        return ActionOutcome(
            success=True,
            result={"orphan_id": orphan_id, "best_group": best_group, "best_sim": best_sim, "placed": placed},
            cost_secs=max(elapsed, 0.005),
        )

    def _suggest_reassignment(self, t0: float) -> ActionOutcome:
        s = self.state

        # Find the first outlier without a reassignment suggestion yet
        target = None
        for tid, grp, score in s.outliers:
            if not any(sg.trace_id == tid and sg.action_type == "reassign" for sg in s.suggestions):
                target = (tid, grp, score)
                break

        if target is None:
            return ActionOutcome(success=False, result={"reason": "no outliers to reassign"}, cost_secs=0.001)

        tid, from_group, outlier_score = target

        # Find the best alternative group
        best_group = ""
        best_sim = -1.0
        for group_name in s.examined_groups:
            if group_name == from_group:
                continue
            group = self.env.org.groups.get(group_name)
            if not group or not group.member_ids:
                continue
            sims = []
            for mid in group.member_ids:
                key = _pair_key(tid, mid)
                if key not in s.similarity_cache:
                    s.similarity_cache[key] = self.env.trace_similarity(tid, mid)
                sims.append(s.similarity_cache[key])
            mean_sim = sum(sims) / len(sims) if sims else 0.0
            if mean_sim > best_sim:
                best_sim = mean_sim
                best_group = group_name

        # Only suggest reassignment if the alternative is actually better
        # Compare against current group similarity
        current_group = self.env.org.groups.get(from_group)
        current_sim = 0.0
        if current_group and current_group.member_ids:
            current_sims = []
            for mid in current_group.member_ids:
                if mid == tid:
                    continue
                key = _pair_key(tid, mid)
                current_sims.append(s.similarity_cache.get(key, 0.0))
            current_sim = sum(current_sims) / len(current_sims) if current_sims else 0.0

        if best_group and best_sim > current_sim + 0.02:
            improvement = best_sim - current_sim
            confidence = min(1.0, improvement / 0.10)  # full confidence at 0.10 improvement
            s.suggestions.append(RefinementSuggestion(
                action_type="reassign",
                trace_id=tid,
                from_group=from_group,
                to_group=best_group,
                confidence=confidence,
                reason=f"sim {current_sim:.3f} -> {best_sim:.3f} (improvement {improvement:.3f})",
            ))
            elapsed = time.perf_counter() - t0
            return ActionOutcome(
                success=True,
                result={"trace_id": tid, "from": from_group, "to": best_group, "improvement": improvement},
                cost_secs=max(elapsed, 0.005),
            )
        else:
            # No better group found — the outlier stays flagged but no reassignment
            elapsed = time.perf_counter() - t0
            return ActionOutcome(
                success=True,
                result={"trace_id": tid, "from": from_group, "no_better_group": True},
                cost_secs=max(elapsed, 0.003),
            )


@dataclass
class RefinerCoherence:
    """Coherence model for the refiner's own loop."""

    dimension_names: tuple[str, ...] = (
        "continuity", "vitality", "contextual_fit",
        "differentiation", "accountability", "reflexivity",
    )

    def score(self, state_after: Dict[str, float], history: List[CycleEntry]) -> DimensionScores:
        group_cov = state_after.get("group_coverage", 0.0)
        orphan_cov = state_after.get("orphan_coverage", 0.0)
        mean_quality = state_after.get("mean_quality", 0.0)
        suggestion_count = state_after.get("suggestion_count", 0.0) * 20.0
        diversity = state_after.get("diversity", 0.0)

        # P1: Continuity — stable quality signal across groups examined
        # Higher when mean group quality is consistent (not wildly varying)
        continuity = 0.3 + 0.5 * group_cov + 0.2 * mean_quality

        # P2: Vitality — throughput of examination
        vitality = 0.2 + 0.5 * group_cov + 0.3 * orphan_cov

        # P3: Contextual Fit — quality of suggestions (high confidence)
        if suggestion_count > 0:
            # Proxy: having suggestions at all means work is being done
            contextual_fit = 0.3 + 0.4 * min(1.0, suggestion_count / 10.0) + 0.3 * mean_quality
        else:
            contextual_fit = 0.2

        # P4: Differentiation — suggestions are distinct (multiple action types)
        differentiation = 0.3 + 0.7 * diversity

        # P5: Accountability — coverage of all groups and orphans
        accountability = 0.1 + 0.5 * group_cov + 0.4 * orphan_cov

        # P6: Reflexivity — revises own suggestions when quality drops
        reflexivity = 0.3
        if len(history) >= 3:
            recent_reassign = sum(
                1 for e in history[-5:]
                if e.action == "suggest_reassignment"
            )
            reflexivity = 0.3 + 0.3 * min(1.0, recent_reassign / 2.0)
            # Bonus if coherence improved after a reassignment suggestion
            if any(e.action == "suggest_reassignment" and e.delta > 0 for e in history[-5:]):
                reflexivity += 0.2

        return {
            "continuity": max(0.0, min(1.0, continuity)),
            "vitality": max(0.0, min(1.0, vitality)),
            "contextual_fit": max(0.0, min(1.0, contextual_fit)),
            "differentiation": max(0.0, min(1.0, differentiation)),
            "accountability": max(0.0, min(1.0, accountability)),
            "reflexivity": max(0.0, min(1.0, reflexivity)),
        }

    def composite(self, dimensions: DimensionScores) -> float:
        return sum(dimensions.values()) / max(1, len(dimensions))

    def gco_status(self, dimensions: DimensionScores, coherence: float, *, state_after=None) -> GCOStatus:
        if coherence < 0.35:
            return GCOStatus.CRITICAL
        if coherence < 0.55:
            return GCOStatus.DEGRADED
        if all(v >= 0.55 for v in dimensions.values()):
            return GCOStatus.STABLE
        return GCOStatus.PARTIAL


# ---------------------------------------------------------------------------
# Refiner internal state
# ---------------------------------------------------------------------------

@dataclass
class _RefinerState:
    """Mutable state for one refiner run."""

    group_names: List[str] = field(default_factory=list)
    orphan_ids: List[int] = field(default_factory=list)
    examined_groups: Set[str] = field(default_factory=set)
    examined_orphans: Set[int] = field(default_factory=set)
    group_quality: Dict[str, float] = field(default_factory=dict)
    outliers: List[Tuple[int, str, float]] = field(default_factory=list)  # (trace_id, group, outlier_score)
    suggestions: List[RefinementSuggestion] = field(default_factory=list)
    similarity_cache: Dict[Tuple[int, int], float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pair_key(a: int, b: int) -> Tuple[int, int]:
    return (min(a, b), max(a, b))


# ---------------------------------------------------------------------------
# Refiner entry point
# ---------------------------------------------------------------------------

_REFINER_OBS_KEYS = [
    "group_coverage", "orphan_coverage", "mean_quality",
    "suggestion_count", "outlier_count", "diversity", "cycle",
]


def run_refiner(
    env: TraceEnvironment,
    *,
    max_cycles: int = 60,
    budget: float = 5.0,
    seed: int | None = None,
) -> RefinerResults:
    """Spawn and run a refiner sub-agent. Returns its results.

    The refiner runs its own REAL loop, examines existing groups for
    outliers and orphans, and returns structured refinement suggestions
    for the organizer.
    """
    # Gather current group names and orphan trace ids from the environment
    group_names = list(env.org.groups.keys())
    all_ids = set(range(env.trace_count))
    assigned_ids = set(env.org.assignments.keys())
    orphan_ids = sorted(all_ids - assigned_ids)

    # Seed the similarity cache with any survey-computed similarities
    initial_cache: Dict[Tuple[int, int], float] = {}
    if hasattr(env, "_survey_similarity_boost"):
        initial_cache.update(env._survey_similarity_boost)

    state = _RefinerState(
        group_names=group_names,
        orphan_ids=orphan_ids,
        similarity_cache=initial_cache,
    )

    observer = RefinerObserver(state)
    actions = RefinerActions(env, state)
    coherence = RefinerCoherence()

    substrate = MemorySubstrate(config=SubstrateConfig(
        slow_decay=0.06,       # faster decay — short-lived agent
        bistable_threshold=0.20,
        write_base_cost=0.04,
        maintain_base_cost=0.01,
    ))

    engine = RealCoreEngine(
        observer=observer,
        actions=actions,
        coherence=coherence,
        substrate=substrate,
        domain_name="refiner",
        session_budget=budget,
        selector_seed=seed,
    )

    # Run until stable or exhausted
    consecutive_stable = 0
    entry = None
    cycle = 0
    for i in range(1, max_cycles + 1):
        entry = engine.run_cycle(i)
        cycle = i

        if entry.gco.value == "STABLE":
            consecutive_stable += 1
        else:
            consecutive_stable = 0

        # Refiner reaches closure once it has covered the space
        if consecutive_stable >= 5:
            break

        if engine.budget_remaining <= 0.01:
            break

    # Package results
    results = RefinerResults(
        suggestions=list(state.suggestions),
        group_quality=dict(state.group_quality),
        orphans_examined=len(state.examined_orphans),
        groups_examined=len(state.examined_groups),
        cycles_used=cycle,
        final_coherence=entry.coherence if entry is not None else 0.0,
    )

    return results
