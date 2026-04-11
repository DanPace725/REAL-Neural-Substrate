"""Surveyor sub-agent: a REAL agent that batch-reads traces and discovers clusters.

The surveyor is spawned by the organizer when contextual_fit is stuck.
It runs its own REAL loop with its own coherence model, reads a batch of
traces, computes all pairwise similarities, and deposits cluster
suggestions back into the shared environment.

The surveyor's six dimensions are tuned for its specialization:
  P1 Continuity     — stable similarity signal (not noisy)
  P2 Vitality       — traces read per cycle (throughput)
  P3 Contextual Fit — cluster quality (separation × cohesion)
  P4 Differentiation — clusters are distinct from each other
  P5 Accountability — coverage (what fraction of batch has been processed)
  P6 Reflexivity    — revises cluster boundaries when quality drops
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple

from real_core.engine import RealCoreEngine
from real_core.substrate import MemorySubstrate, SubstrateConfig
from real_core.consolidation import BasicConsolidationPipeline
from real_core.types import (
    ActionOutcome,
    CycleEntry,
    DimensionScores,
    GCOStatus,
)

from .environment import TraceEnvironment


# ---------------------------------------------------------------------------
# Survey results — the communication channel back to the organizer
# ---------------------------------------------------------------------------

@dataclass
class ClusterSuggestion:
    """A cluster discovered by the surveyor."""

    name: str
    member_ids: List[int]
    mean_similarity: float
    seed_keywords: List[str] = field(default_factory=list)


@dataclass
class SurveyResults:
    """Output deposited into the environment by the surveyor."""

    clusters: List[ClusterSuggestion] = field(default_factory=list)
    similarity_matrix: Dict[Tuple[int, int], float] = field(default_factory=dict)
    traces_surveyed: List[int] = field(default_factory=list)
    cycles_used: int = 0
    final_coherence: float = 0.0


# ---------------------------------------------------------------------------
# Surveyor adapters (its own perception/action/coherence, not the organizer's)
# ---------------------------------------------------------------------------

class SurveyorObserver:
    """The surveyor observes the state of its own survey work."""

    def __init__(self, state: _SurveyorState) -> None:
        self.state = state

    def observe(self, cycle: int) -> Dict[str, float]:
        s = self.state
        total = len(s.batch_ids)
        if total == 0:
            return {k: 0.0 for k in _SURVEYOR_OBS_KEYS}

        read_count = len(s.read_ids)
        pairs_computed = len(s.similarity_cache)
        max_pairs = total * (total - 1) // 2
        cluster_count = len(s.clusters)

        # Cluster quality metrics
        mean_intra = 0.0
        if s.clusters:
            intra_sims = []
            for cl in s.clusters:
                if len(cl) >= 2:
                    sims = [
                        s.similarity_cache.get(_pair_key(a, b), 0.0)
                        for i, a in enumerate(cl) for b in cl[i+1:]
                    ]
                    if sims:
                        intra_sims.append(sum(sims) / len(sims))
            mean_intra = sum(intra_sims) / len(intra_sims) if intra_sims else 0.0

        return {
            "read_ratio": read_count / total,
            "pair_coverage": pairs_computed / max(1, max_pairs),
            "cluster_count": min(1.0, cluster_count / 10.0),
            "mean_intra_similarity": mean_intra,
            "unread_count": (total - read_count) / total,
            "cycle": float(cycle),
        }


class SurveyorActions:
    """Actions the surveyor can take within its own loop."""

    def __init__(self, env: TraceEnvironment, state: _SurveyorState) -> None:
        self.env = env
        self.state = state

    def available_actions(self, history_size: int) -> List[str]:
        s = self.state
        actions = ["rest"]

        # Read next unread trace in batch
        unread = [tid for tid in s.batch_ids if tid not in s.read_ids]
        if unread:
            actions.append("read_batch_trace")

        # Compute similarities (once enough traces are read)
        if len(s.read_ids) >= 3:
            actions.append("compute_similarities")

        # Form clusters (once similarity matrix has data)
        if len(s.similarity_cache) >= 3:
            actions.append("form_clusters")

        # Refine clusters
        if s.clusters:
            actions.append("refine_clusters")

        return actions

    def execute(self, action: str) -> ActionOutcome:
        s = self.state
        t0 = time.perf_counter()

        if action == "read_batch_trace":
            unread = [tid for tid in s.batch_ids if tid not in s.read_ids]
            if not unread:
                return ActionOutcome(success=False, result={"reason": "batch complete"}, cost_secs=0.001)
            tid = unread[0]
            info = self.env.read_trace_content(tid)
            s.read_ids.add(tid)
            elapsed = time.perf_counter() - t0
            return ActionOutcome(
                success=True,
                result={"trace_id": tid, "batch_progress": len(s.read_ids) / len(s.batch_ids)},
                cost_secs=max(elapsed, info["elapsed_secs"]),
            )

        if action == "compute_similarities":
            # Compute all pairwise similarities for read traces
            read_list = sorted(s.read_ids)
            computed = 0
            for i, id_a in enumerate(read_list):
                for id_b in read_list[i + 1:]:
                    key = _pair_key(id_a, id_b)
                    if key not in s.similarity_cache:
                        sim = self.env.trace_similarity(id_a, id_b)
                        # Also include temporal proximity
                        temp = self.env.temporal_proximity(id_a, id_b)
                        combined = 0.75 * sim + 0.25 * temp
                        s.similarity_cache[key] = combined
                        computed += 1
            elapsed = time.perf_counter() - t0
            return ActionOutcome(
                success=True,
                result={"pairs_computed": computed, "total_cached": len(s.similarity_cache)},
                cost_secs=max(elapsed, 0.005),
            )

        if action == "form_clusters":
            # Simple agglomerative: start with most similar pair, grow clusters
            s.clusters = _agglomerative_cluster(
                sorted(s.read_ids),
                s.similarity_cache,
                threshold=0.08,
                max_clusters=12,
            )
            elapsed = time.perf_counter() - t0
            return ActionOutcome(
                success=True,
                result={"clusters_formed": len(s.clusters), "traces_clustered": sum(len(c) for c in s.clusters)},
                cost_secs=max(elapsed, 0.005),
            )

        if action == "refine_clusters":
            # Refine: move misplaced traces between clusters
            if len(s.clusters) < 2:
                return ActionOutcome(success=False, result={"reason": "need 2+ clusters"}, cost_secs=0.001)
            moves = _refine_clusters(s.clusters, s.similarity_cache)
            elapsed = time.perf_counter() - t0
            return ActionOutcome(
                success=True,
                result={"moves": moves},
                cost_secs=max(elapsed, 0.005),
            )

        if action == "rest":
            return ActionOutcome(success=True, result={"rested": True}, cost_secs=0.001)

        return ActionOutcome(success=False, result={"reason": f"unknown: {action}"}, cost_secs=0.001)


@dataclass
class SurveyorCoherence:
    """Coherence model for the surveyor's own loop."""

    dimension_names: tuple[str, ...] = (
        "continuity", "vitality", "contextual_fit",
        "differentiation", "accountability", "reflexivity",
    )

    def score(self, state_after: Dict[str, float], history: List[CycleEntry]) -> DimensionScores:
        read_ratio = state_after.get("read_ratio", 0.0)
        pair_cov = state_after.get("pair_coverage", 0.0)
        cluster_count = state_after.get("cluster_count", 0.0) * 10.0
        mean_intra = state_after.get("mean_intra_similarity", 0.0)

        # P1: signal stability
        continuity = 0.4 + 0.4 * pair_cov + 0.2 * read_ratio

        # P2: throughput
        vitality = 0.3 + 0.7 * read_ratio

        # P3: cluster quality
        contextual_fit = mean_intra  # directly from cluster cohesion

        # P4: cluster distinctness
        differentiation = 0.5 if cluster_count < 2 else min(1.0, 0.3 + 0.15 * cluster_count)

        # P5: coverage
        accountability = 0.2 + 0.6 * read_ratio + 0.2 * pair_cov

        # P6: refinement activity
        reflexivity = 0.3
        if len(history) >= 3:
            recent_refine = sum(1 for e in history[-5:] if e.action == "refine_clusters")
            reflexivity = 0.3 + 0.3 * min(1.0, recent_refine / 2.0)
            # Bonus if coherence improved after refine
            if any(e.action == "refine_clusters" and e.delta > 0 for e in history[-5:]):
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
# Surveyor internal state
# ---------------------------------------------------------------------------

@dataclass
class _SurveyorState:
    """Mutable state for one surveyor run."""

    batch_ids: List[int] = field(default_factory=list)
    read_ids: Set[int] = field(default_factory=set)
    similarity_cache: Dict[Tuple[int, int], float] = field(default_factory=dict)
    clusters: List[List[int]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Clustering algorithms (simple, no dependencies)
# ---------------------------------------------------------------------------

def _pair_key(a: int, b: int) -> Tuple[int, int]:
    return (min(a, b), max(a, b))


def _agglomerative_cluster(
    trace_ids: List[int],
    sim_cache: Dict[Tuple[int, int], float],
    threshold: float = 0.08,
    max_clusters: int = 12,
) -> List[List[int]]:
    """Simple agglomerative clustering from pairwise similarities."""
    # Start: each trace is its own cluster
    clusters: List[List[int]] = [[tid] for tid in trace_ids]

    while len(clusters) > max_clusters or True:
        # Find most similar pair of clusters
        best_sim = -1.0
        best_i = -1
        best_j = -1
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                # Average linkage
                total = 0.0
                count = 0
                for a in clusters[i]:
                    for b in clusters[j]:
                        total += sim_cache.get(_pair_key(a, b), 0.0)
                        count += 1
                sim = total / count if count > 0 else 0.0
                if sim > best_sim:
                    best_sim = sim
                    best_i = i
                    best_j = j

        if best_sim < threshold or best_i < 0:
            break

        # Merge
        clusters[best_i] = clusters[best_i] + clusters[best_j]
        clusters.pop(best_j)

    # Filter out singletons
    return [c for c in clusters if len(c) >= 2]


def _refine_clusters(
    clusters: List[List[int]],
    sim_cache: Dict[Tuple[int, int], float],
) -> int:
    """Move misplaced traces between clusters. Returns number of moves."""
    moves = 0
    for ci, cluster in enumerate(clusters):
        for tid in list(cluster):
            # Mean similarity to own cluster
            own_sims = [sim_cache.get(_pair_key(tid, other), 0.0) for other in cluster if other != tid]
            own_mean = sum(own_sims) / len(own_sims) if own_sims else 0.0

            # Check if better fit in another cluster
            best_other_ci = -1
            best_other_mean = own_mean
            for cj, other_cluster in enumerate(clusters):
                if cj == ci:
                    continue
                other_sims = [sim_cache.get(_pair_key(tid, other), 0.0) for other in other_cluster]
                other_mean = sum(other_sims) / len(other_sims) if other_sims else 0.0
                if other_mean > best_other_mean + 0.02:  # threshold to avoid thrashing
                    best_other_mean = other_mean
                    best_other_ci = cj

            if best_other_ci >= 0 and len(cluster) > 2:
                cluster.remove(tid)
                clusters[best_other_ci].append(tid)
                moves += 1

    return moves


# ---------------------------------------------------------------------------
# Surveyor entry point
# ---------------------------------------------------------------------------

_SURVEYOR_OBS_KEYS = [
    "read_ratio", "pair_coverage", "cluster_count",
    "mean_intra_similarity", "unread_count", "cycle",
]


def run_surveyor(
    env: TraceEnvironment,
    batch_ids: List[int],
    *,
    max_cycles: int = 80,
    budget: float = 10.0,
    seed: int | None = None,
) -> SurveyResults:
    """Spawn and run a surveyor sub-agent. Returns its results.

    The surveyor runs its own REAL loop, reads the batch, discovers
    clusters, and returns structured results for the organizer.
    """
    state = _SurveyorState(batch_ids=list(batch_ids))

    observer = SurveyorObserver(state)
    actions = SurveyorActions(env, state)
    coherence = SurveyorCoherence()

    substrate = MemorySubstrate(config=SubstrateConfig(
        slow_decay=0.05,       # faster decay — short-lived agent
        bistable_threshold=0.20,
        write_base_cost=0.05,
        maintain_base_cost=0.01,
    ))

    engine = RealCoreEngine(
        observer=observer,
        actions=actions,
        coherence=coherence,
        substrate=substrate,
        domain_name="surveyor",
        session_budget=budget,
        selector_seed=seed,
    )

    # Run until stable or exhausted
    consecutive_stable = 0
    for i in range(1, max_cycles + 1):
        entry = engine.run_cycle(i)

        if entry.gco.value == "STABLE":
            consecutive_stable += 1
        else:
            consecutive_stable = 0

        # Surveyor reaches closure faster (smaller task)
        if consecutive_stable >= 5:
            break

        if engine.budget_remaining <= 0.01:
            break

    # Package results
    results = SurveyResults(
        traces_surveyed=sorted(state.read_ids),
        similarity_matrix=dict(state.similarity_cache),
        cycles_used=i,
        final_coherence=entry.coherence if engine.memory.entries else 0.0,
    )

    # Convert internal clusters to suggestions with names and keywords
    for cluster in state.clusters:
        if len(cluster) < 2:
            continue
        # Compute mean similarity
        sims = []
        for ci, a in enumerate(cluster):
            for b in cluster[ci + 1:]:
                sims.append(state.similarity_cache.get(_pair_key(a, b), 0.0))
        mean_sim = sum(sims) / len(sims) if sims else 0.0

        # Generate name from shared keywords
        all_kw_sets = [env.keyword_set(tid) for tid in cluster]
        if all_kw_sets:
            shared = all_kw_sets[0]
            for kws in all_kw_sets[1:]:
                shared = shared & kws
            seed_kw = sorted(shared)[:3]
        else:
            seed_kw = []

        name = "-".join(seed_kw[:2]) if seed_kw else f"survey-cluster-{len(results.clusters)}"
        results.clusters.append(ClusterSuggestion(
            name=name,
            member_ids=list(cluster),
            mean_similarity=mean_sim,
            seed_keywords=seed_kw,
        ))

    return results
