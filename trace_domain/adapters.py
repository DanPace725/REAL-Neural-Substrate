"""Domain adapters binding the trace-organizer environment to RealCoreEngine.

Implements the four adapter protocols:
  - TraceObservationAdapter  (ObservationAdapter)
  - TraceActionBackend       (ActionBackend)
  - TraceCoherenceModel      (CoherenceModel)
  - TraceMemoryBinding       (DomainMemoryBinding)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from real_core.types import (
    ActionOutcome,
    CycleEntry,
    DimensionScores,
    GCOStatus,
    MemoryActionSpec,
)

from .environment import TraceEnvironment
from .regulator import DimensionActionRegulator
from .surveyor import run_surveyor
from .refiner import run_refiner
from .cell_pool import CellPool, CellRole, CellState
from .cell_runners import run_surveyor_cell, run_refiner_cell


# ---------------------------------------------------------------------------
# Observation Adapter
# ---------------------------------------------------------------------------

class TraceObservationAdapter:
    """Reads the current organizational state as a numeric observation."""

    def __init__(self, environment: TraceEnvironment, pool: CellPool | None = None) -> None:
        self.environment = environment
        self.pool = pool

    def observe(self, cycle: int) -> Dict[str, float]:
        obs = self.environment.observe()
        obs["cycle"] = float(cycle)
        # Include pool observations if the organizer has cells
        if self.pool is not None:
            pool_obs = self.pool.observe()
            for k, v in pool_obs.items():
                obs[f"pool_{k}"] = v
        return obs


# ---------------------------------------------------------------------------
# Action Backend
# ---------------------------------------------------------------------------

_TAG_THRESHOLD = 0.12  # minimum similarity to offer a tag action
_LINK_THRESHOLD = 0.10  # minimum similarity to offer a link action


class TraceActionBackend:
    """Exposes organizational actions to the engine.

    Available actions depend on state:
      - read_trace         always (if unread traces remain)
      - create_group       always (if focus trace exists)
      - tag:<group>        for each existing group (if focus trace exists)
      - link               if focus trace is read and similar traces exist
      - split:<group>      for groups with 4+ members
      - merge_groups       if 2+ groups exist
      - organize:<group>   copy group's traces into a folder (filesystem action)
      - spawn_surveyor     when contextual_fit is stuck
      - spawn_refiner      when accountability/reflexivity stuck
      - reorient           when regulator cooldown allows (strategy shift)
      - introspect         always
      - rest               always
    """

    # Sub-agent spawn conditions
    _SURVEYOR_COOLDOWN = 30           # minimum cycles between surveys
    _SURVEYOR_MIN_READ_RATIO = 0.20   # need enough read traces to form a useful batch
    _SURVEYOR_CONTEXTUAL_FIT_CEIL = 0.30  # only spawn when contextual_fit is stuck low
    _SURVEYOR_BATCH_SIZE = 40         # traces per survey batch

    _REFINER_COOLDOWN = 25            # minimum cycles between refinements
    _REFINER_MIN_GROUPS = 2           # need groups to refine
    _REFINER_ACCOUNTABILITY_CEIL = 0.60   # spawn when accountability/reflexivity stuck
    _REFINER_REFLEXIVITY_CEIL = 0.60

    def __init__(
        self,
        environment: TraceEnvironment,
        regulator: DimensionActionRegulator | None = None,
        pool: CellPool | None = None,
    ) -> None:
        self.environment = environment
        self.regulator = regulator
        self.pool = pool
        # Internal monotonic cycle counter (not affected by history consolidation)
        self._cycle_counter: int = 0
        self._last_survey_cycle: int = -100
        self._survey_count: int = 0
        self._last_refiner_cycle: int = -100
        self._refiner_count: int = 0

    def available_actions(self, history_size: int) -> List[str]:
        env = self.environment
        self._cycle_counter += 1  # monotonic, unaffected by consolidation
        actions: List[str] = ["rest", "introspect"]

        has_unread = env.next_unread() is not None
        read_count = sum(1 for t in env.traces.values() if t.has_been_read)
        read_ratio = read_count / max(1, env.trace_count)

        # Reading strategies — not just "read next" but foraging behavior:
        #   read_trace    — sequential (the default, familiar)
        #   read_neighbor — follow a thread (similar to current focus)
        #   read_gap      — fill knowledge gaps (assigned but unread traces)
        #   read_surprise — seek novelty (maximally different from what we've seen)
        if has_unread:
            actions.append("read_trace")
            # Neighbor reading: only when we have a focus to follow from
            if env.focus_trace is not None:
                actions.append("read_neighbor")
            # Gap reading: only when there are assigned-but-unread traces
            assigned_unread = sum(
                1 for tid in env.org.assignments
                if not env.traces[tid].has_been_read
            )
            if assigned_unread > 0:
                actions.append("read_gap")
            # Surprise reading: after enough baseline reading to have context
            if read_ratio >= 0.10:
                actions.append("read_surprise")

        # Early phase: limit organizing options until enough has been read
        # The system needs to survey before it can organize meaningfully
        if read_ratio < 0.15 and has_unread:
            # Very early: only read, rest, introspect
            return actions

        focus = env.focus_trace
        if focus is not None:
            # Tag into existing groups
            for gname in env.org.groups:
                actions.append(f"tag:{gname}")
            # Create a new group from the focus trace
            actions.append("create_group")
            # Link to most similar known trace
            if focus.has_been_read:
                best_id, best_sim = env.find_most_similar(focus.trace_id)
                if best_id >= 0 and best_sim >= _LINK_THRESHOLD:
                    actions.append("link")

        # Structural actions on existing groups (only after enough reading)
        if read_ratio >= 0.2:
            for gname, group in env.org.groups.items():
                if len(group.member_ids) >= 4:
                    actions.append(f"split:{gname}")

            if len(env.org.groups) >= 2:
                actions.append("merge_groups")

        # Filesystem organization: copy traces into group folders
        # Available when a group has 2+ members and not all are already organized
        if read_ratio >= 0.25:
            for gname, group in env.org.groups.items():
                if len(group.member_ids) >= 2:
                    unorganized = [
                        tid for tid in group.member_ids
                        if tid not in env.org.organized_traces
                    ]
                    if unorganized:
                        actions.append(f"organize:{gname}")

        # --- Cell pool actions (if pool exists) ---
        if self.pool is not None:
            actions.extend(self._pool_actions())
        else:
            # Legacy fire-and-forget spawns (no pool)
            if self._can_spawn_surveyor():
                actions.append("spawn_surveyor")
            if self._can_spawn_refiner():
                actions.append("spawn_refiner")

        # Reorient: explicit strategy shift (respects cooldown)
        if self.regulator is not None and self.regulator.can_reorient():
            actions.append("reorient")

        return actions

    def _can_spawn_surveyor(self) -> bool:
        """Check whether conditions are right to spawn a surveyor sub-agent.

        Conditions:
          - Enough cycles since last survey (cooldown)
          - Enough traces have been read (need material for the batch)
          - Contextual fit is stuck low (the surveyor addresses this)
          - OR the regulator identifies contextual_fit as the bottleneck
        """
        env = self.environment

        # Cooldown (uses monotonic counter, not history_size which can shrink)
        if (self._cycle_counter - self._last_survey_cycle) < self._SURVEYOR_COOLDOWN:
            return False

        # Need enough read traces
        read_count = sum(1 for t in env.traces.values() if t.has_been_read)
        read_ratio = read_count / max(1, env.trace_count)
        if read_ratio < self._SURVEYOR_MIN_READ_RATIO:
            return False

        # Need enough read traces for a meaningful batch
        if read_count < 6:
            return False

        # Check: is contextual_fit the bottleneck or stuck low?
        if self.regulator is not None:
            if self.regulator.bottleneck_dim == "contextual_fit":
                return True
            # Also spawn if contextual_fit severity is notable even if not the #1 bottleneck
            if self.regulator._recent_entries:
                recent_cf = [
                    e.dimensions.get("contextual_fit", 0.5)
                    for e in self.regulator._recent_entries[-10:]
                ]
                mean_cf = sum(recent_cf) / len(recent_cf) if recent_cf else 0.5
                if mean_cf < self._SURVEYOR_CONTEXTUAL_FIT_CEIL:
                    return True

        return False

    def _pool_actions(self) -> List[str]:
        """Generate available actions for managing the cell pool.

        Actions:
          - grow:<role>         grow a new cell (if role has no living cells)
          - activate:<cell_id>  activate a dormant/exhausted cell
          - feed:<cell_id>      add budget to an exhausted cell
        """
        pool = self.pool
        actions: List[str] = []
        env = self.environment

        read_count = sum(1 for t in env.traces.values() if t.has_been_read)
        read_ratio = read_count / max(1, env.trace_count)

        # Growth: offer to grow roles that have no living cells
        # Only when the system has enough data to justify the investment
        if read_ratio >= 0.15:
            for role in pool.growth_candidates():
                # Role-specific preconditions
                if role == CellRole.SURVEYOR and read_ratio >= 0.20:
                    actions.append(f"grow:{role.value}")
                elif role == CellRole.REFINER and len(env.org.groups) >= 2:
                    actions.append(f"grow:{role.value}")
                elif role in (CellRole.READER, CellRole.LINKER) and read_ratio >= 0.25:
                    actions.append(f"grow:{role.value}")

        # Activation: offer to activate dormant or exhausted cells with budget
        for cell in pool.cells.values():
            if cell.is_activatable and cell.budget_remaining > 0.5:
                # Check cooldown — don't spam activations
                cycles_since = self._cycle_counter - cell.last_active_cycle
                if cycles_since >= 15 or cell.activations == 0:
                    actions.append(f"activate:{cell.cell_id}")

        # Feeding: offer to feed exhausted cells that have contributed
        for cell in pool.needs_feeding():
            actions.append(f"feed:{cell.cell_id}")

        return actions

    def execute(self, action: str) -> ActionOutcome:
        env = self.environment
        t0 = time.perf_counter()

        # --- reading actions (all variants) ---
        if action in ("read_trace", "read_neighbor", "read_gap", "read_surprise"):
            if action == "read_neighbor":
                tid = env.forage_neighbor()
            elif action == "read_gap":
                tid = env.forage_gap()
            elif action == "read_surprise":
                tid = env.forage_surprise()
            else:
                tid = env.pop_unread()

            if tid is None:
                return ActionOutcome(success=False, result={"reason": "no unread traces"}, cost_secs=0.001)
            info = env.read_trace_content(tid)
            elapsed = time.perf_counter() - t0
            return ActionOutcome(
                success=True,
                result={
                    "trace_id": tid,
                    "filename": env.traces[tid].filename,
                    "content_keywords": len(env.traces[tid].content_keywords),
                    "strategy": action,
                },
                cost_secs=max(elapsed, info["elapsed_secs"]),
            )

        # --- create_group ---
        if action == "create_group":
            focus = env.focus_trace
            if focus is None:
                return ActionOutcome(success=False, result={"reason": "no focus trace"}, cost_secs=0.001)
            name = env.suggest_group_name(focus.trace_id)
            env.create_group(name, seed_keywords=list(focus.keywords[:5]))
            env.assign_to_group(focus.trace_id, name, reason="seed member")
            elapsed = time.perf_counter() - t0
            return ActionOutcome(
                success=True,
                result={"group": name, "trace_id": focus.trace_id},
                cost_secs=max(elapsed, 0.005),
            )

        # --- tag:<group> ---
        if action.startswith("tag:"):
            group_name = action[4:]
            focus = env.focus_trace
            if focus is None:
                return ActionOutcome(success=False, result={"reason": "no focus trace"}, cost_secs=0.001)
            sim = 0.0
            group = env.org.groups.get(group_name)
            if group and group.member_ids:
                sims = [env.trace_similarity(focus.trace_id, mid) for mid in group.member_ids]
                sim = sum(sims) / len(sims)
            ok = env.assign_to_group(focus.trace_id, group_name, reason=f"tagged, sim={sim:.3f}")
            elapsed = time.perf_counter() - t0
            return ActionOutcome(
                success=ok,
                result={"group": group_name, "similarity": sim, "trace_id": focus.trace_id},
                cost_secs=max(elapsed, 0.003),
            )

        # --- link ---
        if action == "link":
            focus = env.focus_trace
            if focus is None:
                return ActionOutcome(success=False, result={"reason": "no focus trace"}, cost_secs=0.001)
            best_id, best_sim = env.find_most_similar(focus.trace_id)
            if best_id < 0:
                return ActionOutcome(success=False, result={"reason": "no similar trace found"}, cost_secs=0.002)
            link = env.link_traces(focus.trace_id, best_id, reason=f"auto-linked, sim={best_sim:.3f}")
            elapsed = time.perf_counter() - t0
            return ActionOutcome(
                success=True,
                result={
                    "linked_to": best_id,
                    "similarity": link.similarity,
                    "filename_a": env.traces[focus.trace_id].filename,
                    "filename_b": env.traces[best_id].filename,
                },
                cost_secs=max(elapsed, 0.005),
            )

        # --- split:<group> ---
        if action.startswith("split:"):
            group_name = action[6:]
            result = env.split_group(group_name)
            elapsed = time.perf_counter() - t0
            if result is None:
                return ActionOutcome(success=False, result={"reason": "group too small to split"}, cost_secs=0.002)
            return ActionOutcome(
                success=True,
                result={"kept": result[0], "new_group": result[1]},
                cost_secs=max(elapsed, 0.01),
            )

        # --- merge_groups ---
        if action == "merge_groups":
            result = env.merge_groups()
            elapsed = time.perf_counter() - t0
            if result is None:
                return ActionOutcome(success=False, result={"reason": "nothing to merge"}, cost_secs=0.002)
            return ActionOutcome(
                success=True,
                result={"kept": result[0], "absorbed": result[1]},
                cost_secs=max(elapsed, 0.01),
            )

        # --- organize:<group> ---
        if action.startswith("organize:"):
            group_name = action[9:]
            result = env.organize_group_batch(group_name)
            elapsed = time.perf_counter() - t0
            if not result.get("success"):
                return ActionOutcome(success=False, result=result, cost_secs=0.002)
            return ActionOutcome(
                success=True,
                result=result,
                cost_secs=max(elapsed, 0.02),
            )

        # --- introspect ---
        if action == "introspect":
            # Review: compute quality metrics and return them
            intra = env.mean_intra_group_similarity()
            inter = env.inter_group_distinction()
            orphan_ratio = max(0.0, 1.0 - len(env.org.assignments) / max(1, env.trace_count))
            elapsed = time.perf_counter() - t0
            return ActionOutcome(
                success=True,
                result={
                    "intra_group_sim": round(intra, 4),
                    "inter_group_dist": round(inter, 4),
                    "orphan_ratio": round(orphan_ratio, 4),
                    "group_count": len(env.org.groups),
                    "revision_count": env.org.revision_count,
                },
                cost_secs=max(elapsed, 0.01),
            )

        # --- pool: grow:<role> ---
        if action.startswith("grow:") and self.pool is not None:
            role_name = action[5:]
            try:
                role = CellRole(role_name)
            except ValueError:
                return ActionOutcome(success=False, result={"reason": f"unknown role: {role_name}"}, cost_secs=0.001)
            cell = self.pool.grow(role, budget=3.0)
            if cell is None:
                return ActionOutcome(success=False, result={"reason": "pool full"}, cost_secs=0.001)
            elapsed = time.perf_counter() - t0
            return ActionOutcome(
                success=True,
                result={"cell_id": cell.cell_id, "role": role.value, "budget": cell.budget_remaining},
                cost_secs=max(elapsed, 0.002),
            )

        # --- pool: activate:<cell_id> ---
        if action.startswith("activate:") and self.pool is not None:
            cell_id = action[9:]
            result = self.pool.activate(cell_id)
            elapsed = time.perf_counter() - t0
            return ActionOutcome(
                success=result.get("success", False),
                result=result,
                cost_secs=max(elapsed, 0.05),
            )

        # --- pool: feed:<cell_id> ---
        if action.startswith("feed:") and self.pool is not None:
            cell_id = action[5:]
            ok = self.pool.feed(cell_id, budget=2.0)
            elapsed = time.perf_counter() - t0
            return ActionOutcome(
                success=ok,
                result={"cell_id": cell_id, "fed": 2.0 if ok else 0.0},
                cost_secs=max(elapsed, 0.001),
            )

        # --- spawn_surveyor (legacy, no pool) ---
        if action == "spawn_surveyor":
            return self._execute_spawn_surveyor()

        # --- spawn_refiner (legacy, no pool) ---
        if action == "spawn_refiner":
            return self._execute_spawn_refiner()

        # --- reorient ---
        if action == "reorient":
            if self.regulator is None:
                return ActionOutcome(success=False, result={"reason": "no regulator"}, cost_secs=0.001)
            # Reorient uses the regulator's own accumulated history
            recent = self.regulator._recent_entries
            last_dims = recent[-1].dimensions if recent else {}
            diag = self.regulator.reorient(
                dimensions=last_dims,
                history=recent,
            )
            elapsed = time.perf_counter() - t0
            return ActionOutcome(
                success=True,
                result=diag,
                cost_secs=max(elapsed, 0.01),
            )

        # --- rest ---
        if action == "rest":
            return ActionOutcome(success=True, result={"rested": True}, cost_secs=0.001)

        return ActionOutcome(success=False, result={"reason": f"unknown action: {action}"}, cost_secs=0.001)

    def _execute_spawn_surveyor(self) -> ActionOutcome:
        """Spawn a surveyor sub-agent to batch-analyze traces and discover clusters.

        Selects a batch of read traces, runs the surveyor's own REAL loop,
        and absorbs the results back into the environment.
        """
        import time as _time
        env = self.environment
        t0 = _time.perf_counter()

        # Build batch: all read traces (up to batch size), prioritizing un-surveyed
        read_ids = [tid for tid, te in env.traces.items() if te.has_been_read]
        previously_surveyed = set()
        if env._survey_results is not None:
            previously_surveyed = set(env._survey_results.traces_surveyed)

        # Prefer traces not yet surveyed, then fill with previously surveyed
        unsurveyed = [tid for tid in read_ids if tid not in previously_surveyed]
        surveyed = [tid for tid in read_ids if tid in previously_surveyed]
        batch = (unsurveyed + surveyed)[:self._SURVEYOR_BATCH_SIZE]

        if len(batch) < 4:
            return ActionOutcome(
                success=False,
                result={"reason": f"batch too small ({len(batch)} traces)"},
                cost_secs=0.001,
            )

        # Run the surveyor sub-agent
        results = run_surveyor(
            env=env,
            batch_ids=batch,
            max_cycles=80,
            budget=5.0,  # sub-agent gets a limited budget
            seed=self._survey_count * 17 + 42,
        )

        # Absorb results into environment
        absorption = env.absorb_survey(results)

        # Update tracking
        self._survey_count += 1
        self._last_survey_cycle = self._cycle_counter

        elapsed = _time.perf_counter() - t0
        return ActionOutcome(
            success=True,
            result={
                "batch_size": len(batch),
                "survey_cycles": results.cycles_used,
                "survey_coherence": round(results.final_coherence, 3),
                "clusters_found": len(results.clusters),
                **absorption,
            },
            cost_secs=max(elapsed, 0.1),
        )

    def _can_spawn_refiner(self) -> bool:
        """Check whether conditions are right to spawn a refiner sub-agent.

        Conditions:
          - Enough cycles since last refiner (cooldown)
          - At least 2 groups exist (need structure to refine)
          - Accountability or reflexivity is stuck low
          - OR there are many orphans relative to assigned traces
        """
        env = self.environment

        # Cooldown
        if (self._cycle_counter - self._last_refiner_cycle) < self._REFINER_COOLDOWN:
            return False

        # Need groups to refine
        if len(env.org.groups) < self._REFINER_MIN_GROUPS:
            return False

        # Check dimension signals from the regulator
        if self.regulator is not None:
            # Spawn if accountability or reflexivity is the bottleneck
            if self.regulator.bottleneck_dim in ("accountability", "reflexivity"):
                return True

            # Also spawn if there are lots of orphans (coverage gap)
            assigned = len(env.org.assignments)
            total = env.trace_count
            if total > 0 and assigned / total < 0.5 and self.regulator._recent_entries:
                recent_acc = [
                    e.dimensions.get("accountability", 0.5)
                    for e in self.regulator._recent_entries[-10:]
                ]
                mean_acc = sum(recent_acc) / len(recent_acc) if recent_acc else 0.5
                if mean_acc < self._REFINER_ACCOUNTABILITY_CEIL:
                    return True

            # Or if reflexivity is stuck
            if self.regulator._recent_entries:
                recent_ref = [
                    e.dimensions.get("reflexivity", 0.5)
                    for e in self.regulator._recent_entries[-10:]
                ]
                mean_ref = sum(recent_ref) / len(recent_ref) if recent_ref else 0.5
                if mean_ref < self._REFINER_REFLEXIVITY_CEIL:
                    return True

        return False

    def _execute_spawn_refiner(self) -> ActionOutcome:
        """Spawn a refiner sub-agent to improve existing organizational structure.

        Examines groups for outliers, finds orphan placements, suggests
        reassignments, and absorbs results back into the environment.
        """
        import time as _time
        env = self.environment
        t0 = _time.perf_counter()

        if len(env.org.groups) < 2:
            return ActionOutcome(
                success=False,
                result={"reason": "not enough groups to refine"},
                cost_secs=0.001,
            )

        # Run the refiner sub-agent
        results = run_refiner(
            env=env,
            max_cycles=60,
            budget=5.0,
            seed=self._refiner_count * 31 + 7,
        )

        # Absorb results: apply high-confidence suggestions
        applied = 0
        orphans_placed = 0
        reassignments = 0
        for suggestion in results.suggestions:
            if suggestion.confidence < 0.3:
                continue  # too uncertain

            if suggestion.action_type == "place_orphan" and suggestion.to_group:
                if suggestion.trace_id not in env.org.assignments:
                    ok = env.assign_to_group(
                        suggestion.trace_id,
                        suggestion.to_group,
                        reason=f"refiner: {suggestion.reason}",
                    )
                    if ok:
                        orphans_placed += 1
                        applied += 1

            elif suggestion.action_type == "reassign" and suggestion.to_group:
                if suggestion.confidence >= 0.5:  # higher bar for reassignment
                    ok = env.assign_to_group(
                        suggestion.trace_id,
                        suggestion.to_group,
                        reason=f"refiner reassign: {suggestion.reason}",
                    )
                    if ok:
                        reassignments += 1
                        applied += 1

        # Store refiner results for observation
        env._refiner_results = results

        # Update tracking
        self._refiner_count += 1
        self._last_refiner_cycle = self._cycle_counter

        elapsed = _time.perf_counter() - t0
        return ActionOutcome(
            success=True,
            result={
                "refiner_cycles": results.cycles_used,
                "refiner_coherence": round(results.final_coherence, 3),
                "groups_examined": results.groups_examined,
                "orphans_examined": results.orphans_examined,
                "total_suggestions": len(results.suggestions),
                "applied": applied,
                "orphans_placed": orphans_placed,
                "reassignments": reassignments,
                "group_quality": {k: round(v, 3) for k, v in results.group_quality.items()},
            },
            cost_secs=max(elapsed, 0.1),
        )


# ---------------------------------------------------------------------------
# Coherence Model
# ---------------------------------------------------------------------------

@dataclass
class TraceCoherenceModel:
    """Six-dimensional coherence scoring for the trace-organizer domain.

    Maps the six relational primitives to organizational quality:
      P1 Continuity     — consistency of categorization scheme
      P2 Vitality       — productive organizing work per cycle
      P3 Contextual Fit — groupings match actual content similarity
      P4 Differentiation — groups are distinct from each other
      P5 Accountability — assignments are traceable (have reasons)
      P6 Reflexivity    — system revises bad placements after dips
    """

    dimension_names: tuple[str, ...] = (
        "continuity",
        "vitality",
        "contextual_fit",
        "differentiation",
        "accountability",
        "reflexivity",
    )
    gco_threshold: float = 0.65
    gco_critical: float = 0.40

    def score(
        self,
        state_after: Dict[str, float],
        history: List[CycleEntry],
    ) -> DimensionScores:
        return {
            "continuity": self._continuity(state_after, history),
            "vitality": self._vitality(state_after, history),
            "contextual_fit": self._contextual_fit(state_after, history),
            "differentiation": self._differentiation(state_after, history),
            "accountability": self._accountability(state_after, history),
            "reflexivity": self._reflexivity(state_after, history),
        }

    def composite(self, dimensions: DimensionScores) -> float:
        if not dimensions:
            return 0.0
        return sum(dimensions.values()) / len(dimensions)

    def gco_status(
        self,
        dimensions: DimensionScores,
        coherence: float,
        *,
        state_after: Dict[str, float] | None = None,
    ) -> GCOStatus:
        if coherence < self.gco_critical:
            return GCOStatus.CRITICAL
        if coherence < self.gco_threshold:
            return GCOStatus.DEGRADED
        if all(v >= self.gco_threshold for v in dimensions.values()):
            return GCOStatus.STABLE
        return GCOStatus.PARTIAL

    # --- Individual dimension scorers ---

    def _continuity(self, state: Dict[str, float], history: List[CycleEntry]) -> float:
        """P1: Is the categorization scheme consistent? Not flip-flopping."""
        if len(history) < 3:
            return 0.5  # neutral at start

        # Check recent action consistency — repeated create_group without reads = low continuity
        recent = history[-8:]
        action_types = set()
        for e in recent:
            if e.action.startswith("tag:"):
                action_types.add("tag")
            elif e.action.startswith("split:"):
                action_types.add("split")
            elif e.action.startswith("organize:"):
                action_types.add("organize")
            elif e.action.startswith("grow:"):
                action_types.add("grow")
            elif e.action.startswith("activate:"):
                action_types.add("activate")
            elif e.action.startswith("feed:"):
                action_types.add("feed")
            elif e.action.startswith("read_"):
                action_types.add("read")
            else:
                action_types.add(e.action)

        # Diverse but not chaotic: 2-4 action types is healthy
        diversity = len(action_types)
        if diversity <= 1:
            score = 0.4  # too repetitive
        elif diversity <= 4:
            score = 0.7 + 0.1 * (diversity - 2)  # 0.7 - 0.9
        else:
            score = max(0.3, 0.9 - 0.1 * (diversity - 4))  # declining

        # Penalize high revision ratio (flip-flopping)
        rev_ratio = state.get("revision_ratio", 0.0)
        score -= 0.3 * rev_ratio

        return max(0.0, min(1.0, score))

    def _vitality(self, state: Dict[str, float], history: List[CycleEntry]) -> float:
        """P2: Is the organizing work productive? Traces processed vs. effort.

        Relational goal: the system should feel a pull toward COVERAGE —
        reading more traces develops the lexicon, assigning more traces
        reduces orphans. But coverage without understanding is hollow,
        so reading and assigning are both weighted.
        """
        read_ratio = state.get("read_ratio", 0.0)
        orphan_ratio = state.get("orphan_ratio", 1.0)

        # Reading IS productive work — the system needs to read before it can organize
        # Weight reading more heavily early, organizing more heavily later
        read_weight = max(0.3, 0.7 - 0.4 * read_ratio)  # 0.7 early → 0.3 when most read
        organize_weight = 1.0 - read_weight
        progress = read_weight * read_ratio + organize_weight * (1.0 - orphan_ratio)

        # Penalize idleness: too many rests/introspects without productive work
        if len(history) >= 5:
            recent = history[-5:]
            idle = sum(1 for e in recent if e.action in ("rest", "introspect"))
            if idle >= 4:
                progress *= 0.5

        # Reading momentum bonus: recent reads (any strategy) boost vitality.
        # All foraging is productive reading — sequential, neighbor, gap, surprise.
        if len(history) >= 3:
            recent_reads = sum(1 for e in history[-5:] if e.action.startswith("read_"))
            progress += 0.08 * recent_reads

        # Directional pull: lexicon development creates vitality.
        # The more the agent has read and understood, the more alive
        # its language capacity is. This rewards sustained reading.
        lex_maturity = state.get("lexicon_maturity", 0.0)
        if lex_maturity > 0.0:
            progress += 0.12 * lex_maturity

        # Frontier-shifted optimal point: when there's lots of unexplored
        # territory, the system hasn't yet reached peak productivity.
        # The parabola peak slides rightward, so reading MORE still feels
        # like growth. As frontier shrinks, the peak settles back.
        frontier = state.get("frontier_pressure", 0.0)
        optimal = 0.55 + 0.20 * frontier  # 0.55 → 0.75 at max frontier
        vitality = 0.3 + 0.7 * (1.0 - (progress - optimal) ** 2 / 0.30)
        return max(0.0, min(1.0, vitality))

    def _contextual_fit(self, state: Dict[str, float], history: List[CycleEntry]) -> float:
        """P3: Do groupings match actual content similarity?"""
        intra = state.get("intra_group_similarity", 0.0)
        focus_sim = state.get("focus_sim_to_group", 0.0)

        # Blend group-level and focus-level fit
        score = 0.6 * intra + 0.4 * focus_sim
        # Baseline boost — some minimum even before groups form
        if state.get("group_count", 0.0) < 0.05:
            score = max(score, 0.3)

        # Survey boost: if a surveyor has run and produced quality clusters,
        # contextual_fit gets a lift proportional to cluster quality.
        # This is the payoff for spawning the sub-agent.
        survey_quality = state.get("survey_cluster_quality", 0.0)
        if survey_quality > 0.0:
            # Survey provides enriched similarity data — groups formed with
            # survey guidance have higher actual coherence
            score = score + 0.35 * survey_quality
            # Cap: survey can lift contextual_fit significantly but not to 1.0 alone
            score = min(0.85, score)

        # Lexicon boost: linguistic maturity improves contextual understanding.
        # The agent literally understands its traces better as it reads more.
        # This compounds with intra_group_similarity (which also improves via
        # the lexicon), but the direct boost rewards the developmental process.
        lex_maturity = state.get("lexicon_maturity", 0.0)
        if lex_maturity > 0.1:
            score = score + 0.20 * lex_maturity
            score = min(0.90, score)

        return max(0.0, min(1.0, score))

    def _differentiation(self, state: Dict[str, float], history: List[CycleEntry]) -> float:
        """P4: Are categories distinct from each other?"""
        inter = state.get("inter_group_distinction", 0.5)
        group_count = state.get("group_count", 0.0) * 20.0  # denormalize

        if group_count < 2:
            return 0.4  # can't assess with fewer than 2 groups

        # Too many groups is also bad (over-fragmentation)
        group_penalty = 0.0
        if group_count > 15:
            group_penalty = 0.2 * min(1.0, (group_count - 15) / 10.0)

        return max(0.0, min(1.0, inter - group_penalty))

    def _accountability(self, state: Dict[str, float], history: List[CycleEntry]) -> float:
        """P5: Are assignments traceable? Has the system read before assigning?

        Relational goal: the tension between COVERAGE and QUALITY.
        High orphan ratio = something to move away from (work undone).
        But assigning blindly is worse — accountability means the
        assignments are grounded in actual reading and understanding.
        """
        read_ratio = state.get("read_ratio", 0.0)
        has_focus = state.get("has_focus", 0.0)
        orphan_ratio = state.get("orphan_ratio", 1.0)

        # Accountability grows with how much has been read
        score = 0.2 + 0.4 * read_ratio

        # Penalize organizing without reading: if assigning but haven't read much
        if read_ratio < 0.3 and orphan_ratio < 0.8:
            score -= 0.15  # organizing blind

        # Bonus for having focus (knowing what you're working on)
        score += 0.15 * has_focus

        # History maturity bonus
        maturity = min(1.0, len(history) / 50.0)
        score += 0.10 * maturity

        # Directional pull: orphans are discomfort. Each unassigned trace
        # is a loose end the system should feel. But only after enough
        # reading — you can't responsibly assign what you haven't understood.
        grounded_coverage = min(read_ratio, 1.0 - orphan_ratio)
        score += 0.20 * grounded_coverage  # reward coverage that's backed by reading

        # Refiner boost: refiner examines groups and places orphans systematically
        refiner_coverage = state.get("refiner_coverage", 0.0)
        if refiner_coverage > 0.0:
            score += 0.12 * refiner_coverage

        # Filesystem organization bonus: manifesting organization into actual
        # folder structure is the ultimate accountability — the work is visible
        org_ratio = state.get("organization_ratio", 0.0)
        if org_ratio > 0.0:
            score += 0.12 * org_ratio

        # Frontier tension: unexplored territory is incomplete work.
        # Not a penalty for ignorance, but a felt sense of "there's more
        # out there that I haven't touched." Like a slime mold sensing
        # nutrients beyond its current reach — the incompleteness pulls.
        # Only applies once the system has read enough to know it's in
        # a larger world (read_ratio > 0.15).
        frontier = state.get("frontier_pressure", 0.0)
        frontier_novelty = state.get("frontier_novelty", 0.0)
        if frontier > 0.1 and read_ratio > 0.15:
            # Base tension from unexplored territory
            tension = 0.18 * frontier
            # Amplified when the frontier contains genuinely novel topics
            # (not just more of what we've already seen)
            tension += 0.08 * frontier_novelty
            score -= tension

        return max(0.0, min(1.0, score))

    def _reflexivity(self, state: Dict[str, float], history: List[CycleEntry]) -> float:
        """P6: Does the system revise its own organization when things aren't working?"""
        if len(history) < 5:
            return 0.3  # too early to assess

        # Look for revision behavior after coherence dips
        recent = history[-10:]
        dip_then_revise = 0
        dip_count = 0
        for i, entry in enumerate(recent):
            if entry.delta < -0.02:
                dip_count += 1
                # Check if any of the next 3 actions were structural (split, merge, re-tag)
                for j in range(i + 1, min(i + 4, len(recent))):
                    next_action = recent[j].action
                    if any(next_action.startswith(p) for p in ("split:", "merge", "tag:", "introspect")):
                        dip_then_revise += 1
                        break

        revision_rate = dip_then_revise / max(1, dip_count)

        # Also credit revision ratio from environment (actual reassignments)
        rev_ratio = state.get("revision_ratio", 0.0)

        # Blend: revision after dips + actual revisions happening
        score = 0.3 + 0.4 * revision_rate + 0.3 * min(1.0, rev_ratio * 3.0)

        # Refiner boost: spawning a refiner IS reflexive behavior
        # The system is growing a specialized organ to examine its own structure
        refiner_quality = state.get("refiner_mean_quality", 0.0)
        if refiner_quality > 0.0:
            score += 0.2 * refiner_quality

        return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Memory Binding
# ---------------------------------------------------------------------------

@dataclass
class TraceMemoryBinding:
    """Domain-specific memory bridge for the trace organizer.

    Enriches observations with substrate signals and exposes
    memory-side actions (consolidation, substrate maintenance).
    """

    environment: TraceEnvironment

    def modulate_observation(
        self,
        raw_obs: Dict[str, float],
        substrate: Any,
        cycle: int,
    ) -> Dict[str, float]:
        """Enrich observation with substrate-derived signals."""
        modulated = dict(raw_obs)

        # Add substrate activity signals if available
        if hasattr(substrate, "slow"):
            slow = substrate.slow
            modulated["substrate_continuity"] = slow.get("continuity", 0.0)
            modulated["substrate_vitality"] = slow.get("vitality", 0.0)
            modulated["substrate_contextual_fit"] = slow.get("contextual_fit", 0.0)

        if hasattr(substrate, "active_count"):
            modulated["substrate_active_count"] = float(substrate.active_count()) / 6.0

        return modulated

    def extra_actions(
        self,
        substrate: Any,
        history: List[CycleEntry],
    ) -> List[MemoryActionSpec]:
        """Expose memory-side actions: auto_organize uses substrate to pick best action."""
        actions = []
        env = self.environment

        # Auto-organize: if substrate has learned patterns, suggest the best group
        focus = env.focus_trace
        if focus is not None and env.org.groups:
            best_group, best_sim = env.best_matching_group(focus.trace_id)
            if best_group and best_sim > _TAG_THRESHOLD:
                actions.append(MemoryActionSpec(
                    action=f"auto_tag",
                    estimated_cost=0.003,
                    metadata={"group": best_group, "similarity": best_sim},
                ))

        return actions

    def estimate_memory_action_cost(
        self,
        action: str,
        substrate: Any,
    ) -> float | None:
        if action == "auto_tag":
            return 0.003
        return None

    def execute_memory_action(
        self,
        action: str,
        substrate: Any,
    ) -> ActionOutcome | None:
        if action != "auto_tag":
            return None

        env = self.environment
        focus = env.focus_trace
        if focus is None:
            return ActionOutcome(success=False, result={"reason": "no focus"}, cost_secs=0.001)

        best_group, best_sim = env.best_matching_group(focus.trace_id)
        if not best_group:
            return ActionOutcome(success=False, result={"reason": "no groups"}, cost_secs=0.001)

        env.assign_to_group(focus.trace_id, best_group, reason=f"auto_tag, sim={best_sim:.3f}")
        return ActionOutcome(
            success=True,
            result={"group": best_group, "similarity": best_sim, "trace_id": focus.trace_id},
            cost_secs=0.003,
        )

    def substrate_health_signal(
        self,
        substrate: Any,
        state_after: Dict[str, float],
        history: List[CycleEntry],
    ) -> Dict[str, float]:
        """Return substrate-derived health modulations."""
        signals: Dict[str, float] = {}

        if not hasattr(substrate, "slow"):
            return signals

        slow = substrate.slow
        active = substrate.active_count() if hasattr(substrate, "active_count") else 0

        # Substrate health influences continuity and contextual_fit
        signals["continuity"] = 0.35 + 0.45 * slow.get("continuity", 0.0) + 0.20 * (active / 6.0)
        signals["contextual_fit"] = 0.30 + 0.40 * slow.get("contextual_fit", 0.0) + 0.30 * state_after.get("intra_group_similarity", 0.0)

        return signals
