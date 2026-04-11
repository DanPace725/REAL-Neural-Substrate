"""Cell runners: bridge between the CellPool and the existing surveyor/refiner.

Each runner wraps an existing sub-agent (surveyor, refiner) but adds:
  - Persistent state: restores from cell.persistent_state before running,
    saves back after. The cell *remembers* across activations.
  - Signal handling: reads incoming signals, posts outgoing ones.
  - Budget respect: uses the cell's remaining budget, not a fresh one.

Runner signature (matches CellPool.register_runner):
    runner(env, cell, incoming_signals) -> Dict[str, Any]
"""

from __future__ import annotations

from typing import Any, Dict, List

from .cell_pool import Cell, CellRole, Signal
from .environment import TraceEnvironment
from .surveyor import (
    SurveyResults,
    SurveyorObserver,
    SurveyorActions,
    SurveyorCoherence,
    _SurveyorState,
    _pair_key,
)
from .refiner import (
    RefinerResults,
    RefinerObserver,
    RefinerActions,
    RefinerCoherence,
    _RefinerState,
)
from real_core.engine import RealCoreEngine
from real_core.substrate import MemorySubstrate, SubstrateConfig


# ---------------------------------------------------------------------------
# Surveyor cell runner
# ---------------------------------------------------------------------------

def run_surveyor_cell(
    env: TraceEnvironment,
    cell: Cell,
    incoming_signals: List[Signal],
) -> Dict[str, Any]:
    """Run a surveyor cell with persistent state.

    On first activation, the cell starts fresh. On subsequent activations,
    it restores its similarity_cache, read_ids, and clusters — so it doesn't
    re-read traces it already processed. New traces in the batch get added.
    """
    ps = cell.persistent_state

    # Build batch: all read traces, prioritizing ones not yet surveyed
    read_ids = [tid for tid, te in env.traces.items() if te.has_been_read]
    previously_surveyed = set(ps.get("read_ids", []))

    unsurveyed = [tid for tid in read_ids if tid not in previously_surveyed]
    surveyed = [tid for tid in read_ids if tid in previously_surveyed]
    batch = (unsurveyed + surveyed)[:40]

    if len(batch) < 4:
        return {"cycles_used": 0, "final_coherence": 0.0, "reason": "batch too small"}

    # Restore persistent state into _SurveyorState
    state = _SurveyorState(batch_ids=batch)
    state.read_ids = set(ps.get("read_ids", []))
    state.similarity_cache = {
        (k[0], k[1]): v
        for k, v in ps.get("similarity_cache", {}).items()
    }
    state.clusters = ps.get("clusters", [])

    # Check incoming signals for hints
    for sig in incoming_signals:
        if sig.signal_type == "traces_to_survey" and "trace_ids" in sig.payload:
            # Prioritize these traces
            for tid in sig.payload["trace_ids"]:
                if tid not in state.batch_ids and tid < env.trace_count:
                    state.batch_ids.append(tid)

    observer = SurveyorObserver(state)
    actions = SurveyorActions(env, state)
    coherence = SurveyorCoherence()

    substrate = MemorySubstrate(config=SubstrateConfig(
        slow_decay=0.05,
        bistable_threshold=0.20,
        write_base_cost=0.05,
        maintain_base_cost=0.01,
    ))

    engine = RealCoreEngine(
        observer=observer,
        actions=actions,
        coherence=coherence,
        substrate=substrate,
        domain_name="surveyor-cell",
        session_budget=cell.budget_remaining,
        selector_seed=cell.activations * 17 + 42,
    )

    # Run
    consecutive_stable = 0
    entry = None
    cycle = 0
    for i in range(1, 81):
        entry = engine.run_cycle(i)
        cycle = i
        if entry.gco.value == "STABLE":
            consecutive_stable += 1
        else:
            consecutive_stable = 0
        if consecutive_stable >= 5:
            break
        if engine.budget_remaining <= 0.01:
            break

    # Package results
    results = SurveyResults(
        traces_surveyed=sorted(state.read_ids),
        similarity_matrix=dict(state.similarity_cache),
        cycles_used=cycle,
        final_coherence=entry.coherence if entry else 0.0,
    )

    # Convert clusters to suggestions
    for cluster in state.clusters:
        if len(cluster) < 2:
            continue
        sims = []
        for ci, a in enumerate(cluster):
            for b in cluster[ci + 1:]:
                sims.append(state.similarity_cache.get(_pair_key(a, b), 0.0))
        mean_sim = sum(sims) / len(sims) if sims else 0.0

        all_kw_sets = [env.keyword_set(tid) for tid in cluster]
        if all_kw_sets:
            shared = all_kw_sets[0]
            for kws in all_kw_sets[1:]:
                shared = shared & kws
            seed_kw = sorted(shared)[:3]
        else:
            seed_kw = []

        from .surveyor import ClusterSuggestion
        results.clusters.append(ClusterSuggestion(
            name="-".join(seed_kw[:2]) if seed_kw else f"survey-cluster-{len(results.clusters)}",
            member_ids=list(cluster),
            mean_similarity=mean_sim,
            seed_keywords=seed_kw,
        ))

    # Absorb results into environment
    absorption = env.absorb_survey(results)

    # Save persistent state back to cell
    # Keep tuple keys as-is (persistent_state is in-memory, not JSON)
    cell.persistent_state["read_ids"] = list(state.read_ids)
    cell.persistent_state["similarity_cache"] = dict(state.similarity_cache)
    cell.persistent_state["clusters"] = state.clusters
    cell.persistent_state["last_cluster_count"] = len(results.clusters)

    # Signal the refiner that clusters are ready
    if results.clusters:
        cell.outbox.append(Signal(
            source=cell.cell_id,
            target="*",  # broadcast
            signal_type="clusters_ready",
            payload={
                "cluster_count": len(results.clusters),
                "traces_surveyed": len(results.traces_surveyed),
                "mean_quality": sum(c.mean_similarity for c in results.clusters) / len(results.clusters),
            },
        ))

    return {
        "cycles_used": cycle,
        "final_coherence": entry.coherence if entry else 0.0,
        "clusters_found": len(results.clusters),
        "traces_surveyed": len(results.traces_surveyed),
        "new_similarities": len(state.similarity_cache) - len(ps.get("similarity_cache", {})),
        **absorption,
    }


# ---------------------------------------------------------------------------
# Refiner cell runner
# ---------------------------------------------------------------------------

def run_refiner_cell(
    env: TraceEnvironment,
    cell: Cell,
    incoming_signals: List[Signal],
) -> Dict[str, Any]:
    """Run a refiner cell with persistent state.

    Restores previously computed group_quality and similarity_cache,
    so the refiner builds on prior knowledge rather than starting over.
    """
    ps = cell.persistent_state

    group_names = list(env.org.groups.keys())
    all_ids = set(range(env.trace_count))
    assigned_ids = set(env.org.assignments.keys())
    orphan_ids = sorted(all_ids - assigned_ids)

    # Restore persistent state
    initial_cache = {}
    if hasattr(env, "_survey_similarity_boost"):
        initial_cache.update(env._survey_similarity_boost)
    # Layer on previously computed similarities
    for k, v in ps.get("similarity_cache", {}).items():
        initial_cache[(k[0], k[1])] = v

    state = _RefinerState(
        group_names=group_names,
        orphan_ids=orphan_ids,
        similarity_cache=initial_cache,
    )

    # Restore which groups were already examined (they may have changed,
    # so only keep ones that still exist)
    prev_examined = ps.get("examined_groups", [])
    state.examined_groups = set(g for g in prev_examined if g in env.org.groups)

    # Restore group quality for groups that still exist
    prev_quality = ps.get("group_quality", {})
    state.group_quality = {g: q for g, q in prev_quality.items() if g in env.org.groups}

    # Check signals — if surveyor sent clusters_ready, prioritize those groups
    priority_groups = []
    for sig in incoming_signals:
        if sig.signal_type == "clusters_ready":
            # New clusters might have created new groups — re-examine everything
            state.examined_groups.clear()
            state.group_quality.clear()

    observer = RefinerObserver(state)
    actions = RefinerActions(env, state)
    coherence = RefinerCoherence()

    substrate = MemorySubstrate(config=SubstrateConfig(
        slow_decay=0.06,
        bistable_threshold=0.20,
        write_base_cost=0.04,
        maintain_base_cost=0.01,
    ))

    engine = RealCoreEngine(
        observer=observer,
        actions=actions,
        coherence=coherence,
        substrate=substrate,
        domain_name="refiner-cell",
        session_budget=cell.budget_remaining,
        selector_seed=cell.activations * 31 + 7,
    )

    # Run
    consecutive_stable = 0
    entry = None
    cycle = 0
    for i in range(1, 61):
        entry = engine.run_cycle(i)
        cycle = i
        if entry.gco.value == "STABLE":
            consecutive_stable += 1
        else:
            consecutive_stable = 0
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
        final_coherence=entry.coherence if entry else 0.0,
    )

    # Apply high-confidence suggestions
    applied = 0
    for suggestion in results.suggestions:
        if suggestion.confidence < 0.3:
            continue
        if suggestion.action_type == "place_orphan" and suggestion.to_group:
            if suggestion.trace_id not in env.org.assignments:
                ok = env.assign_to_group(
                    suggestion.trace_id, suggestion.to_group,
                    reason=f"refiner-cell: {suggestion.reason}",
                )
                if ok:
                    applied += 1
        elif suggestion.action_type == "reassign" and suggestion.to_group:
            if suggestion.confidence >= 0.5:
                ok = env.assign_to_group(
                    suggestion.trace_id, suggestion.to_group,
                    reason=f"refiner-cell reassign: {suggestion.reason}",
                )
                if ok:
                    applied += 1

    env._refiner_results = results

    # Save persistent state
    cell.persistent_state["examined_groups"] = list(state.examined_groups)
    cell.persistent_state["group_quality"] = dict(state.group_quality)
    cell.persistent_state["similarity_cache"] = dict(state.similarity_cache)
    cell.persistent_state["total_suggestions"] = len(state.suggestions)

    # Signal outlier findings
    outlier_flags = [s for s in results.suggestions if s.action_type == "flag_outlier"]
    if outlier_flags:
        cell.outbox.append(Signal(
            source=cell.cell_id,
            target="*",
            signal_type="outliers_found",
            payload={
                "count": len(outlier_flags),
                "trace_ids": [s.trace_id for s in outlier_flags],
                "groups": list(set(s.from_group for s in outlier_flags)),
            },
        ))

    return {
        "cycles_used": cycle,
        "final_coherence": entry.coherence if entry else 0.0,
        "groups_examined": results.groups_examined,
        "orphans_examined": results.orphans_examined,
        "suggestions": len(results.suggestions),
        "applied": applied,
    }


# Convenience import for the refiner results dataclass
from .refiner import RefinerResults
