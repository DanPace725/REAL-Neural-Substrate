#!/usr/bin/env python3
"""REAL Trace Organizer — the system organizes its own development traces.

This is REAL doing something useful: reading its own trace corpus and
discovering meaningful organizational structure through allostatic
regulation.  No clustering algorithm, no supervised labels — just
a REAL agent under metabolic pressure figuring out how its own
history fits together.

Usage:
    python scripts/run_trace_organizer.py [--cycles N] [--budget SECS] [--seed S] [--quiet]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is importable
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from real_core.engine import RealCoreEngine
from real_core.substrate import MemorySubstrate, SubstrateConfig
from real_core.recognition import PatternRecognitionModel
from real_core.consolidation import BasicConsolidationPipeline

from trace_domain.environment import TraceEnvironment
from trace_domain.regulator import DimensionActionRegulator
from trace_domain.selector import RegulatedSelector
from trace_domain.adapters import (
    TraceObservationAdapter,
    TraceActionBackend,
    TraceCoherenceModel,
    TraceMemoryBinding,
)
from trace_domain.cell_pool import CellPool, CellRole
from trace_domain.cell_runners import run_surveyor_cell, run_refiner_cell


def build_engine(
    repo_root: Path,
    *,
    seed: int | None = None,
    session_budget: float = 30.0,
) -> tuple[RealCoreEngine, TraceEnvironment, DimensionActionRegulator, CellPool]:
    """Construct the REAL engine wired to the trace-organizer domain."""

    env = TraceEnvironment(repo_root=repo_root)
    print(f"[init] Loaded {env.trace_count} traces from {env.index_path}")

    # Cell pool: the organizer's living workforce
    pool = CellPool(environment=env)
    pool.register_runner(CellRole.SURVEYOR, run_surveyor_cell)
    pool.register_runner(CellRole.REFINER, run_refiner_cell)
    print(f"[init] Cell pool ready (roles: {[r.value for r in CellRole]})")

    regulator = DimensionActionRegulator()

    # Load workspace guidance from real_system — the downward signal
    # from the integrative layer.  If guidance exists, the regulator
    # will blend workspace-level primitive tensions into its local
    # bias computation.  This is the reflexive loop closing.
    _workspace_root = repo_root.parent  # REAL workspace root (one level up from REAL-Neural-Substrate)
    _guidance_path = _workspace_root / "real_system" / "guidance" / "trace_organizer.json"
    if regulator.load_workspace_guidance(_guidance_path):
        ws = regulator._workspace_guidance
        print(f"[init] Workspace guidance loaded: "
              f"top_bottleneck={ws.get('top_bottleneck_primitive')}, "
              f"integration_pressure={ws.get('integration_pressure', 0):.3f}, "
              f"cycle={ws.get('cycle_count', 0)}")
    else:
        print(f"[init] No workspace guidance found (real_system may not have run yet)")

    observer = TraceObservationAdapter(env, pool=pool)
    actions = TraceActionBackend(env, regulator=regulator, pool=pool)
    coherence = TraceCoherenceModel()
    memory_binding = TraceMemoryBinding(environment=env)

    substrate = MemorySubstrate(config=SubstrateConfig(
        keys=(
            "continuity", "vitality", "contextual_fit",
            "differentiation", "accountability", "reflexivity",
        ),
        slow_decay=0.02,        # slower decay — organization is a long game
        bistable_threshold=0.20,
        write_base_cost=0.10,
        maintain_base_cost=0.02,
    ))

    selector = RegulatedSelector(
        regulator=regulator,
        rng=__import__("random").Random(seed) if seed is not None else None,
    )

    recognition = PatternRecognitionModel(min_match_score=0.40)
    consolidation = BasicConsolidationPipeline(
        keep_attractors=20,
        keep_surprises=15,
        keep_boundaries=10,
    )

    engine = RealCoreEngine(
        observer=observer,
        actions=actions,
        coherence=coherence,
        selector=selector,
        substrate=substrate,
        memory_binding=memory_binding,
        recognition_model=recognition,
        consolidation_pipeline=consolidation,
        domain_name="trace-organizer",
        session_budget=session_budget,
        selector_seed=seed,
    )

    return engine, env, regulator, pool


def print_cycle(cycle: int, entry, env: TraceEnvironment, regulator=None, *, quiet: bool = False) -> None:
    """Print a compact one-line cycle summary."""
    dims = entry.dimensions
    dim_str = " ".join(f"{k[:4]}={v:.2f}" for k, v in dims.items())
    focus = env.focus_trace
    focus_name = focus.filename[:40] if focus else "—"

    groups = len(env.org.groups)
    assigned = len(env.org.assignments)
    links = len(env.org.links)

    # Frontier indicator: how much unexplored territory
    fp = env.frontier_pressure()
    frontier_str = f" [{fp:.0%}]" if fp > 0.05 else ""

    # Frustration indicator
    frust_str = ""
    if regulator and regulator.frustration >= 0.1:
        level = int(regulator.frustration * 5)  # 0-5 scale
        frust_str = f" F={'!' * level}"

    if quiet and cycle % 10 != 0:
        return

    # Sub-agent spawns get special multi-line printouts
    if entry.action == "spawn_surveyor":
        print(
            f"  [{cycle:3d}] {'spawn_surveyor':25s} "
            f"mode={entry.mode:13s} "
            f"coh={entry.coherence:.3f} d={entry.delta:+.3f} "
            f"gco={entry.gco.value:8s} | "
            f"g={groups} a={assigned} l={links}"
        )
        if env.has_survey_results:
            sr = env._survey_results
            print(
                f"         >>> SURVEYOR: "
                f"surveyed={len(sr.traces_surveyed)} "
                f"cycles={sr.cycles_used} "
                f"coh={sr.final_coherence:.3f} "
                f"clusters={len(sr.clusters)} "
                f"quality={env.survey_cluster_quality:.3f}"
            )
        return

    if entry.action == "spawn_refiner":
        print(
            f"  [{cycle:3d}] {'spawn_refiner':25s} "
            f"mode={entry.mode:13s} "
            f"coh={entry.coherence:.3f} d={entry.delta:+.3f} "
            f"gco={entry.gco.value:8s} | "
            f"g={groups} a={assigned} l={links}"
        )
        if env._refiner_results is not None:
            rr = env._refiner_results
            print(
                f"         >>> REFINER:  "
                f"groups={rr.groups_examined} "
                f"orphans={rr.orphans_examined} "
                f"cycles={rr.cycles_used} "
                f"coh={rr.final_coherence:.3f} "
                f"suggestions={len(rr.suggestions)}"
            )
        return

    # Cell pool actions get annotated printouts
    if entry.action.startswith("grow:"):
        print(
            f"  [{cycle:3d}] {entry.action:25s} "
            f"mode={entry.mode:13s} "
            f"coh={entry.coherence:.3f} d={entry.delta:+.3f} "
            f"gco={entry.gco.value:8s} | "
            f"g={groups} a={assigned} l={links} | "
            f"CELL GROWN"
        )
        return

    if entry.action.startswith("activate:"):
        cell_id = entry.action[9:]
        print(
            f"  [{cycle:3d}] {entry.action:25s} "
            f"mode={entry.mode:13s} "
            f"coh={entry.coherence:.3f} d={entry.delta:+.3f} "
            f"gco={entry.gco.value:8s} | "
            f"g={groups} a={assigned} l={links}"
        )
        # Check environment for results
        if env.has_survey_results:
            sr = env._survey_results
            print(
                f"         >>> CELL {cell_id}: "
                f"surveyed={len(sr.traces_surveyed)} "
                f"clusters={len(sr.clusters)} "
                f"quality={env.survey_cluster_quality:.3f}"
            )
        elif env._refiner_results is not None:
            rr = env._refiner_results
            print(
                f"         >>> CELL {cell_id}: "
                f"groups={rr.groups_examined} "
                f"orphans={rr.orphans_examined} "
                f"suggestions={len(rr.suggestions)}"
            )
        return

    if entry.action.startswith("feed:"):
        print(
            f"  [{cycle:3d}] {entry.action:25s} "
            f"mode={entry.mode:13s} "
            f"coh={entry.coherence:.3f} d={entry.delta:+.3f} "
            f"gco={entry.gco.value:8s} | "
            f"g={groups} a={assigned} l={links} | "
            f"CELL FED"
        )
        return

    print(
        f"  [{cycle:3d}] {entry.action:25s} "
        f"mode={entry.mode:13s} "
        f"coh={entry.coherence:.3f} d={entry.delta:+.3f} "
        f"gco={entry.gco.value:8s} | "
        f"g={groups} a={assigned} l={links} | "
        f"{dim_str}{frust_str}{frontier_str}"
    )


def print_summary(engine: RealCoreEngine, env: TraceEnvironment) -> None:
    """Print session summary and organizational results."""
    print("\n" + "=" * 80)
    print("SESSION SUMMARY")
    print("=" * 80)

    entries = engine.memory.entries
    if not entries:
        print("  No cycles recorded.")
        return

    coherences = [e.coherence for e in entries]
    print(f"  Cycles:          {len(entries)}")
    print(f"  Mean coherence:  {sum(coherences)/len(coherences):.3f}")
    print(f"  Final coherence: {coherences[-1]:.3f}")
    print(f"  Budget used:     {engine.session_budget - engine.budget_remaining:.2f}s")

    # GCO distribution
    gco_counts = {}
    for e in entries:
        gco_counts[e.gco.value] = gco_counts.get(e.gco.value, 0) + 1
    print(f"  GCO states:      {gco_counts}")

    # Action distribution
    action_counts = {}
    for e in entries:
        a = e.action.split(":")[0] if ":" in e.action else e.action
        action_counts[a] = action_counts.get(a, 0) + 1
    print(f"  Action types:    {action_counts}")

    # Mode distribution
    mode_counts = {}
    for e in entries:
        mode_counts[e.mode] = mode_counts.get(e.mode, 0) + 1
    print(f"  Modes:           {mode_counts}")

    # Organization results
    print(f"\n  ORGANIZATIONAL RESULTS")
    print(f"  Groups created:  {len(env.org.groups)}")
    print(f"  Traces assigned: {len(env.org.assignments)} / {env.trace_count}")
    print(f"  Links created:   {len(env.org.links)}")
    print(f"  Revisions:       {env.org.revision_count}")
    print(f"  Intra-group sim: {env.mean_intra_group_similarity():.3f}")
    print(f"  Inter-group dst: {env.inter_group_distinction():.3f}")

    # Filesystem organization
    organized = len(env.org.organized_traces)
    folders = len(env.org.organized_folders)
    if organized > 0 or folders > 0:
        print(f"\n  FILESYSTEM ORGANIZATION")
        print(f"  Traces copied:   {organized} / {len(env.org.assignments)} assigned")
        print(f"  Folders created: {folders}")
        print(f"  Organization:    {env.organization_ratio:.1%}")
        org_root = env._organized_root
        if org_root.exists():
            print(f"  Output dir:      {org_root}")
            for folder in sorted(org_root.iterdir()):
                if folder.is_dir():
                    file_count = len(list(folder.glob("*.md")))
                    print(f"    {folder.name:35s}  {file_count} files")

    # List groups
    print(f"\n  GROUPS:")
    for name, group in sorted(env.org.groups.items(), key=lambda x: -len(x[1].member_ids)):
        member_count = len(group.member_ids)
        intra = env.intra_group_similarity(name)
        print(f"    {name:40s}  members={member_count:3d}  intra_sim={intra:.3f}")
        # Show first few members
        for tid in group.member_ids[:3]:
            te = env.traces[tid]
            print(f"      - {te.filename[:70]}")
        if member_count > 3:
            print(f"      ... and {member_count - 3} more")

    # Survey results
    if env.has_survey_results:
        sr = env._survey_results
        print(f"\n  SURVEY RESULTS:")
        print(f"    Surveys run:       {env._survey_clusters_absorbed}")
        print(f"    Traces surveyed:   {len(sr.traces_surveyed)}")
        print(f"    Clusters found:    {len(sr.clusters)}")
        print(f"    Cluster quality:   {env.survey_cluster_quality:.3f}")
        print(f"    Similarity pairs:  {len(env._survey_similarity_boost)}")
        for cl in sr.clusters:
            print(f"      {cl.name:30s}  members={len(cl.member_ids):3d}  sim={cl.mean_similarity:.3f}  kw={cl.seed_keywords}")

    # Refiner results
    if env._refiner_results is not None:
        rr = env._refiner_results
        print(f"\n  REFINER RESULTS:")
        print(f"    Groups examined:   {rr.groups_examined}")
        print(f"    Orphans examined:  {rr.orphans_examined}")
        print(f"    Total suggestions: {len(rr.suggestions)}")
        by_type = {}
        for s in rr.suggestions:
            by_type[s.action_type] = by_type.get(s.action_type, 0) + 1
        print(f"    By type:           {by_type}")
        if rr.group_quality:
            print(f"    Group quality:")
            for gname, quality in sorted(rr.group_quality.items()):
                print(f"      {gname:30s}  quality={quality:.3f}")

    # Lexicon development
    lex = env.lexicon
    if lex.traces_ingested > 0:
        stats = lex.stats()
        print(f"\n  LEXICON (language development):")
        print(f"    Traces ingested:   {stats.traces_ingested}")
        print(f"    Vocabulary size:   {stats.vocabulary_size}")
        print(f"    Total tokens:      {stats.total_tokens}")
        print(f"    Mean salience:     {stats.mean_salience:.4f}")
        print(f"    Top salient words:")
        for word, sal in stats.top_salient[:15]:
            neighbors = lex.word_neighbors(word, top_n=5)
            neighbor_str = ", ".join(f"{w}" for w, _ in neighbors)
            print(f"      {word:25s}  sal={sal:.3f}  neighbors=[{neighbor_str}]")

    # Unassigned
    unassigned = [tid for tid in range(env.trace_count) if tid not in env.org.assignments]
    if unassigned:
        print(f"\n  UNASSIGNED ({len(unassigned)}):")
        for tid in unassigned[:5]:
            print(f"    - {env.traces[tid].filename[:70]}")
        if len(unassigned) > 5:
            print(f"    ... and {len(unassigned) - 5} more")


def run_attempt(
    repo_root: Path,
    args,
    attempt: int,
    adjustments: dict,
    lexicon_path: Path,
) -> dict:
    """Run one attempt of the organizer. Returns outcome metrics for the slow layer.

    The slow layer evaluates these outcomes and decides whether another
    attempt is warranted with adjusted parameters.  Lexicon persists
    across attempts (it's the accumulated understanding), but the engine
    and organization are rebuilt fresh each time.
    """
    import shutil

    # Clean organized folder — each attempt starts structural work fresh
    organized_dir = repo_root / "docs" / "traces" / "organized"
    if organized_dir.exists():
        shutil.rmtree(organized_dir)
        if attempt > 1:
            print(f"[attempt {attempt}] Cleaned organized folder for fresh start")

    seed = args.seed + (attempt - 1) * 7  # different trajectory each attempt
    session_budget = adjustments.get("budget", args.budget)

    engine, env, regulator, pool = build_engine(
        repo_root, seed=seed, session_budget=session_budget,
    )

    # Apply slow-layer adjustments from prior attempt diagnosis
    if "exploration_rate" in adjustments:
        engine.selector.exploration_rate = adjustments["exploration_rate"]
    if "frustration_floor" in adjustments:
        regulator.frustration = adjustments["frustration_floor"]

    # Restore lexicon — vocabulary accumulates across ALL attempts
    if env.lexicon.load_state(lexicon_path):
        stats = env.lexicon.stats()
        print(f"[attempt {attempt}] Lexicon restored: {stats.vocabulary_size} words, {stats.traces_ingested} traces")
    else:
        print(f"[attempt {attempt}] Lexicon starting fresh")

    print(f"\n{'=' * 80}")
    print(f"REAL TRACE ORGANIZER — attempt {attempt}")
    adj_str = ", ".join(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}"
                        for k, v in adjustments.items() if k != "budget")
    if adj_str:
        print(f"  Slow-layer adjustments: {adj_str}")
    print(f"  {env.trace_count} traces | max {args.max_cycles} cycles | budget={session_budget:.0f}s | seed={seed}")
    print(f"{'=' * 80}\n")

    # --- Inner loop: run until closure, failure, or resource exhaustion ---
    total_cycles = 0
    consecutive_stable = 0
    total_critical = 0
    best_coherence = 0.0
    cycles_since_improvement = 0
    stop_reason = "max_cycles"
    last_entry = None

    for i in range(1, args.max_cycles + 1):
        entry = engine.run_cycle(i)
        last_entry = entry
        total_cycles += 1

        regulator.after_cycle(entry)
        pool.tick(i)
        pool.update_contributions(entry.coherence, entry.delta)
        print_cycle(i, entry, env, regulator, quiet=args.quiet)

        if entry.action == "rest" and len(engine.memory.entries) > 40:
            engine._run_consolidation()

        if entry.gco.value == "STABLE":
            consecutive_stable += 1
        else:
            consecutive_stable = 0

        if entry.gco.value == "CRITICAL":
            total_critical += 1

        if entry.coherence > best_coherence + 0.005:
            best_coherence = entry.coherence
            cycles_since_improvement = 0
        else:
            cycles_since_improvement += 1

        if consecutive_stable >= args.stable_window:
            stop_reason = "CLOSURE"
            if not args.quiet:
                print(f"\n  >>> CLOSURE: GCO STABLE for {args.stable_window} consecutive cycles")
            break

        if total_critical >= args.critical_limit:
            stop_reason = "CRITICAL_KILL"
            if not args.quiet:
                print(f"\n  >>> KILL: {total_critical} CRITICAL cycles")
            break

        # Frontier-aware stagnation: when there's unexplored territory,
        # the system gets more patience.  Like a slime mold — you don't
        # give up while there's still petri dish to explore.
        fp = env.frontier_pressure()
        effective_stagnation = args.stagnation_window
        if fp > 0.2:
            # Up to 2x patience when most of the world is unexplored
            effective_stagnation = int(args.stagnation_window * (1.0 + fp))

        if cycles_since_improvement >= effective_stagnation:
            stop_reason = "STAGNATION"
            if not args.quiet:
                print(f"\n  >>> STAGNATION: no improvement for {effective_stagnation} cycles "
                      f"(best={best_coherence:.3f}, frontier={fp:.0%})")
            break

        if engine.budget_remaining <= 0.01:
            stop_reason = "BUDGET_EXHAUSTED"
            if not args.quiet:
                print(f"\n  >>> BUDGET EXHAUSTED")
            break

    # --- Print attempt results ---
    print(f"\n  Attempt {attempt} complete: {total_cycles} cycles, {stop_reason}")
    print(f"  Best coherence: {best_coherence:.3f}")
    print(f"  Consecutive STABLE at end: {consecutive_stable}")
    print(f"  Total CRITICAL: {total_critical}")

    # Regulator diagnostics (compact for multi-attempt)
    diag = regulator.get_diagnosis()
    print(f"  Regulator: bottleneck={diag['bottleneck_dim']} "
          f"frustration={diag['frustration']:.3f} "
          f"frontier={diag.get('frontier_pressure', 0):.3f} "
          f"reorients={diag['reorient_count']}")

    # Pool diagnostics
    alive_cells = [c for c in pool.cells.values() if c.is_alive]
    if alive_cells:
        print(f"  Cells alive: {len(alive_cells)} / {len(pool.cells)}")

    # Full summary on final attempt (or closure)
    print_summary(engine, env)

    # --- Save state (lexicon always, others on final) ---
    env.lexicon.save_state(lexicon_path)
    lex_stats = env.lexicon.stats()
    print(f"  Lexicon saved: {lex_stats.vocabulary_size} words, {lex_stats.traces_ingested} traces")

    # Build outcome for slow-layer evaluation
    dims = last_entry.dimensions if last_entry else {}
    assigned_ratio = len(env.org.assignments) / max(1, env.trace_count)
    read_count = sum(1 for t in env.traces.values() if t.has_been_read)
    read_ratio = read_count / max(1, env.trace_count)

    outcome = {
        "stop_reason": stop_reason,
        "best_coherence": best_coherence,
        "final_coherence": last_entry.coherence if last_entry else 0.0,
        "total_cycles": total_cycles,
        "consecutive_stable": consecutive_stable,
        "total_critical": total_critical,
        "groups": len(env.org.groups),
        "assigned_ratio": assigned_ratio,
        "read_ratio": read_ratio,
        "frustration": regulator.frustration,
        "bottleneck_dim": diag["bottleneck_dim"],
        "bottleneck_severity": diag["bottleneck_severity"],
        "dimensions": dims,
        # Pass through for final save
        "_engine": engine,
        "_env": env,
        "_regulator": regulator,
    }
    return outcome


def slow_layer_evaluate(attempt: int, outcome: dict) -> dict | None:
    """The slow layer: evaluate attempt outcome and propose adjustments.

    This is the meta-regulatory layer — it looks at what happened and
    shifts parameters for the next attempt.  It doesn't restructure
    the action space, just tilts the landscape.

    Returns adjustments dict for next attempt, or None if satisfied.
    """
    stop = outcome["stop_reason"]
    coh = outcome["best_coherence"]
    groups = outcome["groups"]
    assigned = outcome["assigned_ratio"]
    read = outcome["read_ratio"]
    dims = outcome["dimensions"]
    frustration = outcome["frustration"]
    bottleneck = outcome["bottleneck_dim"]
    severity = outcome["bottleneck_severity"]

    # --- CLOSURE achieved: we're done ---
    if stop == "CLOSURE":
        print(f"\n  [slow layer] Attempt {attempt} reached closure. Satisfied.")
        return None

    # --- Good enough: coherence above viability floor with decent organization ---
    if coh >= 0.757 and groups >= 3 and assigned >= 0.5:
        print(f"\n  [slow layer] Attempt {attempt} above viability floor "
              f"(coh={coh:.3f}, groups={groups}, assigned={assigned:.0%}). Satisfied.")
        return None

    print(f"\n  [slow layer] Attempt {attempt} fell short "
          f"(coh={coh:.3f}, groups={groups}, assigned={assigned:.0%}, stop={stop})")

    adjustments = {}

    # --- Diagnose and adjust ---

    # Problem: never got started (too many CRITICALs early on)
    if stop == "CRITICAL_KILL":
        print(f"  [slow layer] Too many CRITICAL states — boosting exploration to find footing")
        adjustments["exploration_rate"] = 0.55  # more exploration to escape cold start
        return adjustments

    # Problem: stagnated — the system got stuck
    if stop == "STAGNATION":
        # What's the bottleneck?
        if bottleneck and severity > 0.15:
            print(f"  [slow layer] Stagnation bottleneck: {bottleneck} (severity={severity:.3f})")

        # Low read ratio: system isn't reading enough, needs more exploration
        if read < 0.25:
            print(f"  [slow layer] Low read ratio ({read:.0%}) — more exploration needed")
            adjustments["exploration_rate"] = 0.50
            adjustments["frustration_floor"] = 0.15  # start slightly restless

        # Read a lot but not organizing: needs more exploitation
        elif assigned < 0.3 and read > 0.3:
            print(f"  [slow layer] Reading but not organizing — shifting to exploitation")
            adjustments["exploration_rate"] = 0.30
            adjustments["frustration_floor"] = 0.10

        # Organized but coherence stuck: differentiation problem
        elif groups >= 2 and coh < 0.65:
            print(f"  [slow layer] Organized but incoherent — moderate exploration, fresh start")
            adjustments["exploration_rate"] = 0.45
            adjustments["frustration_floor"] = 0.20  # push harder for novelty

        # Generic stagnation: just shake things up
        else:
            print(f"  [slow layer] General stagnation — slight parameter shift")
            adjustments["exploration_rate"] = 0.45
            adjustments["frustration_floor"] = 0.10

        return adjustments

    # Problem: ran out of budget (was making progress, just needs more time)
    if stop == "BUDGET_EXHAUSTED":
        # If coherence was still climbing, the system was doing well
        if outcome["final_coherence"] > coh - 0.02:
            print(f"  [slow layer] Budget ran out while still improving — continuing with same params")
            return {}  # empty adjustments = try again with defaults
        else:
            print(f"  [slow layer] Budget ran out and declining — adjusting exploration")
            adjustments["exploration_rate"] = 0.45
            return adjustments

    # Fallback: generic retry
    print(f"  [slow layer] Retrying with slight exploration boost")
    adjustments["exploration_rate"] = 0.45
    return adjustments


def main() -> None:
    parser = argparse.ArgumentParser(description="REAL Trace Organizer")
    parser.add_argument("--max-cycles", type=int, default=2000, help="Hard ceiling on cycles per attempt (safety)")
    parser.add_argument("--budget", type=float, default=300.0, help="Session budget in seconds per attempt")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (shifted per attempt)")
    parser.add_argument("--quiet", action="store_true", help="Only print every 10th cycle")
    parser.add_argument("--output", type=str, default=None, help="Path to write organization JSON")
    parser.add_argument("--stable-window", type=int, default=20, help="Consecutive STABLE cycles to declare closure")
    parser.add_argument("--critical-limit", type=int, default=30, help="Total CRITICAL cycles before kill switch")
    parser.add_argument("--stagnation-window", type=int, default=50, help="Cycles without coherence improvement before stopping")
    parser.add_argument("--max-attempts", type=int, default=3, help="Maximum slow-layer retry attempts")
    parser.add_argument("--wall-clock", type=float, default=60.0, help="Total wall-clock time limit in seconds")
    args = parser.parse_args()

    repo_root = _project_root
    lexicon_path = repo_root / "trace_domain" / "lexicon_state.json"

    import time
    wall_start = time.monotonic()

    # Clean organized folder once at the start
    organized_dir = repo_root / "docs" / "traces" / "organized"
    if organized_dir.exists():
        import shutil
        shutil.rmtree(organized_dir)
        print(f"[init] Cleaned prior organized folder")

    adjustments = {}  # first attempt: no adjustments
    best_outcome = None

    for attempt in range(1, args.max_attempts + 1):
        # Check wall-clock budget
        elapsed = time.monotonic() - wall_start
        remaining = args.wall_clock - elapsed
        if remaining < 5.0:
            print(f"\n[slow layer] Wall-clock limit reached ({elapsed:.0f}s elapsed). Stopping.")
            break

        # Cap per-attempt budget to remaining wall-clock time
        attempt_budget = min(args.budget, remaining - 1.0)
        adjustments["budget"] = attempt_budget

        outcome = run_attempt(repo_root, args, attempt, adjustments, lexicon_path)

        # Track best outcome across attempts
        if best_outcome is None or outcome["best_coherence"] > best_outcome["best_coherence"]:
            best_outcome = outcome

        # Slow layer evaluates and decides
        next_adjustments = slow_layer_evaluate(attempt, outcome)

        if next_adjustments is None:
            # Satisfied — use this outcome
            best_outcome = outcome
            break

        adjustments = next_adjustments

    # --- Final saves using the best outcome ---
    if best_outcome is None:
        print("No successful attempts.")
        return

    engine = best_outcome["_engine"]
    env = best_outcome["_env"]
    regulator = best_outcome["_regulator"]

    elapsed = time.monotonic() - wall_start
    print(f"\n{'=' * 80}")
    print(f"SLOW LAYER COMPLETE — {elapsed:.1f}s wall-clock")
    print(f"{'=' * 80}")

    # Export organization
    output_path = args.output or str(repo_root / "docs" / "traces" / "organization.json")
    env.export_organization(output_path)
    print(f"\n  Organization exported to: {output_path}")

    # Export substrate state
    substrate_path = str(repo_root / "trace_domain" / "substrate_state.json")
    if engine.substrate is not None:
        snapshot = engine.substrate.save_state()
        with open(substrate_path, "w") as fh:
            json.dump({
                "fast": snapshot.fast,
                "slow": snapshot.slow,
                "slow_age": snapshot.slow_age,
                "slow_velocity": snapshot.slow_velocity,
                "metadata": {
                    k: v for k, v in snapshot.metadata.items()
                    if k not in ("patterns",)
                },
            }, fh, indent=2)
        print(f"  Substrate state saved to: {substrate_path}")

    # Save regulator state
    regulator_path = str(repo_root / "trace_domain" / "regulator_state.json")
    with open(regulator_path, "w") as fh:
        json.dump(regulator.save_state(), fh, indent=2)
    print(f"  Regulator state saved to: {regulator_path}")

    # Lexicon already saved by run_attempt — report final stats
    lex_stats = env.lexicon.stats()
    print(f"  Lexicon: {lex_stats.vocabulary_size} words, {lex_stats.traces_ingested} traces")
    print(f"\n  Best coherence across all attempts: {best_outcome['best_coherence']:.3f}")


if __name__ == "__main__":
    main()
