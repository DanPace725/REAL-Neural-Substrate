from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, Iterable, List

from real_core import (
    GradientSliceRegulator,
    HeuristicSliceRegulator,
    LaminatedController,
    LaminatedRunResult,
    LearningSliceRegulator,
    REALSliceRegulator,
    RegulatorySignal,
    SliceExecutionPlan,
    SliceSummary,
)

from .environment import NativeSubstrateSystem, _expected_transform_for_task
from .scenarios import ScenarioSpec


@dataclass
class Phase8SliceRunnerConfig:
    soften_history_keep: int = 8
    substrate_soften_scale: float = 0.65
    substrate_drop_scale: float = 0.30


class Phase8SliceRunner:
    """Thin Phase 8 adapter exposing bounded slices to the laminated controller."""

    def __init__(
        self,
        system: NativeSubstrateSystem,
        scenario: ScenarioSpec,
        *,
        benchmark_family: str,
        task_key: str,
        seed: int = 0,
        initial_capability_mode: str = "visible",
        config: Phase8SliceRunnerConfig | None = None,
    ) -> None:
        self.system = system
        self.scenario = scenario
        self.benchmark_family = benchmark_family
        self.task_key = task_key
        self._seed = seed
        self._current_mode = initial_capability_mode
        self.config = config or Phase8SliceRunnerConfig()
        self._scenario_primed = False
        self._scheduled_cycles_run = 0
        self._context_pressure = "medium"
        self._applied_signal_meta: dict[str, object] = {}
        self._last_slice_primary_metric: float | None = None
        self._skip_slice_end_consolidation = False
        self.system.environment.slow_growth_authorization = "auto"

    def run_slice(
        self,
        *,
        slice_id: int,
        cycle_budget: int,
        regulatory_signal: RegulatorySignal | None = None,
    ) -> SliceSummary:
        self._applied_signal_meta = {}
        self._skip_slice_end_consolidation = False
        self._apply_regulatory_signal(regulatory_signal)
        start_cycle = self.system.global_cycle
        start_summary = self.system.summarize()

        if not self._scenario_primed:
            if self.scenario.initial_signal_specs:
                self.system.inject_signal_specs(self.scenario.initial_signal_specs)
            elif self.scenario.initial_packets > 0:
                self.system.inject_signal(count=self.scenario.initial_packets)
            self._scenario_primed = True

        cycles_to_run = max(int(cycle_budget), 0)
        for _ in range(cycles_to_run):
            absolute_cycle = self._scheduled_cycles_run + 1
            injected = self._inject_for_cycle(absolute_cycle)
            if not injected:
                # Past the original schedule — wrap around so the system
                # keeps receiving examples to learn from.
                wrapped = self._wrap_cycle(absolute_cycle)
                if wrapped is not None:
                    self._inject_for_cycle(wrapped)
            self.system.run_global_cycle()
            self._scheduled_cycles_run += 1

        # Strong reset/drop slices should not immediately re-promote freshly
        # destabilized state back into the substrate.
        if not self._skip_slice_end_consolidation:
            self._consolidate_agents()
        self._applied_signal_meta["applied_slice_end_consolidation"] = (
            not self._skip_slice_end_consolidation
        )

        end_summary = self.system.summarize()
        return self._build_slice_summary(
            slice_id=slice_id,
            slice_budget=int(cycle_budget),
            start_cycle=start_cycle,
            end_cycle=self.system.global_cycle,
            start_summary=start_summary,
            end_summary=end_summary,
        )

    def run_slice_plan(
        self,
        *,
        slice_id: int,
        execution_plan: SliceExecutionPlan,
        regulatory_signal: RegulatorySignal | None = None,
    ) -> SliceSummary:
        self._applied_signal_meta = {}
        self._skip_slice_end_consolidation = False
        self._apply_regulatory_signal(regulatory_signal)
        start_cycle = self.system.global_cycle
        start_summary = self.system.summarize()

        if not self._scenario_primed:
            if self.scenario.initial_signal_specs:
                self.system.inject_signal_specs(self.scenario.initial_signal_specs)
            elif self.scenario.initial_packets > 0:
                self.system.inject_signal(count=self.scenario.initial_packets)
            self._scenario_primed = True

        cycles_used = 0
        chunk_index = 0
        previous_primary = (
            float(self._last_slice_primary_metric)
            if self._last_slice_primary_metric is not None
            else 0.0
        )
        previous_floor: float | None = None
        idle_streak = 0
        soft_cap = max(int(execution_plan.soft_cap), int(execution_plan.initial_budget))
        hard_cap = max(int(execution_plan.hard_cap), soft_cap)
        while cycles_used < hard_cap:
            remaining = soft_cap - cycles_used if cycles_used < soft_cap else hard_cap - cycles_used
            if remaining <= 0:
                break
            if chunk_index == 0:
                chunk_budget = min(max(int(execution_plan.initial_budget), 1), remaining)
            else:
                chunk_budget = min(max(int(execution_plan.extend_step), 1), remaining)
            if chunk_budget <= 0:
                break
            for _ in range(chunk_budget):
                absolute_cycle = self._scheduled_cycles_run + 1
                injected = self._inject_for_cycle(absolute_cycle)
                if not injected:
                    wrapped = self._wrap_cycle(absolute_cycle)
                    if wrapped is not None:
                        self._inject_for_cycle(wrapped)
                self.system.run_global_cycle()
                self._scheduled_cycles_run += 1
                cycles_used += 1

            interim = self._build_slice_summary(
                slice_id=slice_id,
                slice_budget=cycles_used,
                start_cycle=start_cycle,
                end_cycle=self.system.global_cycle,
                start_summary=start_summary,
                end_summary=self.system.summarize(),
            )
            current_primary = self._slice_primary_metric(interim)
            current_floor = float(
                interim.metadata.get(
                    "floor_accuracy",
                    interim.metadata.get("final_accuracy", current_primary),
                )
            )
            progress = current_primary - previous_primary
            floor_progress = (
                current_floor - previous_floor
                if previous_floor is not None
                else current_floor - float(
                    self._last_slice_primary_metric
                    if self._last_slice_primary_metric is not None
                    else 0.0
                )
            )
            if self._should_stop_slice_early(
                interim,
                regulatory_signal=regulatory_signal,
                cycles_used=cycles_used,
                execution_plan=execution_plan,
                progress=progress,
                floor_progress=floor_progress,
                idle_streak=idle_streak,
            ):
                break
            if progress <= 0.01 and floor_progress <= 0.01:
                idle_streak += 1
            else:
                idle_streak = 0
            previous_primary = current_primary
            previous_floor = current_floor
            chunk_index += 1
            if cycles_used >= soft_cap and not self._should_extend_slice(
                interim,
                regulatory_signal=regulatory_signal,
                cycles_used=cycles_used,
                execution_plan=execution_plan,
                progress=progress,
                floor_progress=floor_progress,
                idle_streak=idle_streak,
            ):
                break

        if not self._skip_slice_end_consolidation:
            self._consolidate_agents()
        self._applied_signal_meta["applied_slice_end_consolidation"] = (
            not self._skip_slice_end_consolidation
        )

        end_summary = self.system.summarize()
        summary = self._build_slice_summary(
            slice_id=slice_id,
            slice_budget=int(cycles_used),
            start_cycle=start_cycle,
            end_cycle=self.system.global_cycle,
            start_summary=start_summary,
            end_summary=end_summary,
        )
        summary.metadata["execution_plan"] = {
            "initial_budget": int(execution_plan.initial_budget),
            "extend_step": int(execution_plan.extend_step),
            "soft_cap": int(execution_plan.soft_cap),
            "hard_cap": int(execution_plan.hard_cap),
            "early_stop_patience": int(execution_plan.early_stop_patience),
            **dict(execution_plan.metadata),
        }
        summary.metadata["adaptive_cycles_used"] = int(cycles_used)
        summary.metadata["adaptive_soft_cap"] = int(soft_cap)
        summary.metadata["adaptive_hard_cap"] = int(hard_cap)
        return summary

    def snapshot_fast_state(self) -> Dict[str, Any]:
        carryovers: dict[str, object] = {}
        for node_id, agent in self.system.agents.items():
            carryovers[node_id] = agent.engine.export_carryover()
        return {
            "runtime_state": self.system.environment.export_runtime_state(),
            "global_cycle": self.system.global_cycle,
            "session_start_cycle": self.system.session_start_cycle,
            "capability_timeline": list(self.system.capability_timeline),
            "current_mode": self._current_mode,
            "scheduled_cycles_run": self._scheduled_cycles_run,
            "context_pressure": self._context_pressure,
            "applied_signal_meta": dict(self._applied_signal_meta),
            "last_slice_primary_metric": self._last_slice_primary_metric,
            "scenario_primed": self._scenario_primed,
            "carryovers": carryovers,
            "capability_policy": self.system.capability_policy,
        }

    def restore_fast_state(self, snapshot: Dict[str, Any]) -> None:
        runtime_state = dict(snapshot.get("runtime_state", {}))
        capability_policy = str(
            snapshot.get(
                "capability_policy",
                runtime_state.get("capability_policy", self.system.capability_policy),
            )
        )
        rebuilt = build_system_for_scenario(
            self.scenario,
            seed=self._seed,
            capability_policy=capability_policy,
        )
        rebuilt.global_cycle = int(snapshot.get("global_cycle", rebuilt.global_cycle))
        rebuilt.session_start_cycle = int(
            snapshot.get("session_start_cycle", rebuilt.session_start_cycle),
        )
        rebuilt.environment.load_runtime_state(runtime_state)
        rebuilt.capability_policy = capability_policy
        rebuilt.environment.capability_policy = capability_policy
        rebuilt.topology_state = rebuilt.environment.topology_state
        rebuilt.capability_timeline = list(snapshot.get("capability_timeline", []))
        rebuilt.rebuild_agents_from_topology()
        for node_id, carryover in dict(snapshot.get("carryovers", {})).items():
            agent = rebuilt.agents.get(node_id)
            if agent is not None:
                agent.engine.load_carryover(carryover)
        self.system = rebuilt
        self._current_mode = str(snapshot.get("current_mode", self._current_mode))
        self._scheduled_cycles_run = int(
            snapshot.get("scheduled_cycles_run", self._scheduled_cycles_run),
        )
        self._context_pressure = str(snapshot.get("context_pressure", self._context_pressure))
        self._applied_signal_meta = dict(snapshot.get("applied_signal_meta", {}))
        self._last_slice_primary_metric = snapshot.get(
            "last_slice_primary_metric",
            self._last_slice_primary_metric,
        )
        self._scenario_primed = bool(snapshot.get("scenario_primed", self._scenario_primed))

    def _slice_primary_metric(self, summary: SliceSummary) -> float:
        floor_accuracy = float(
            summary.metadata.get(
                "floor_accuracy",
                summary.metadata.get("final_accuracy", 0.0),
            )
        )
        final_accuracy = float(summary.metadata.get("final_accuracy", floor_accuracy))
        return 0.65 * floor_accuracy + 0.35 * final_accuracy

    def _should_stop_slice_early(
        self,
        summary: SliceSummary,
        *,
        regulatory_signal: RegulatorySignal | None,
        cycles_used: int,
        execution_plan: SliceExecutionPlan,
        progress: float,
        floor_progress: float,
        idle_streak: int,
    ) -> bool:
        if cycles_used < max(1, int(execution_plan.initial_budget)):
            return False
        settlement_confidence = float(
            0.0 if regulatory_signal is None else regulatory_signal.settlement_confidence
        )
        commitment = float(summary.metadata.get("mean_transform_commitment_margin", 0.0))
        ambiguity = float(summary.metadata.get("mean_provisional_context_ambiguity", 0.0))
        floor_accuracy = float(
            summary.metadata.get(
                "floor_accuracy",
                summary.metadata.get("final_accuracy", 0.0),
            )
        )
        if settlement_confidence >= 0.92 and floor_accuracy >= 0.80:
            return True
        if (
            idle_streak >= max(1, int(execution_plan.early_stop_patience))
            and progress <= 0.005
            and floor_progress <= 0.005
            and commitment >= 0.72
            and ambiguity <= 0.05
        ):
            return True
        return False

    def _should_extend_slice(
        self,
        summary: SliceSummary,
        *,
        regulatory_signal: RegulatorySignal | None,
        cycles_used: int,
        execution_plan: SliceExecutionPlan,
        progress: float,
        floor_progress: float,
        idle_streak: int,
    ) -> bool:
        if cycles_used >= int(execution_plan.hard_cap):
            return False
        commitment = float(summary.metadata.get("mean_transform_commitment_margin", 0.0))
        ambiguity = float(summary.metadata.get("mean_provisional_context_ambiguity", 0.0))
        floor_accuracy = float(
            summary.metadata.get(
                "floor_accuracy",
                summary.metadata.get("final_accuracy", 0.0),
            )
        )
        growth_drive = float(0.0 if regulatory_signal is None else regulatory_signal.growth_drive)
        pressure_level = float(0.0 if regulatory_signal is None else regulatory_signal.pressure_level)
        if floor_progress > 0.015 or progress > 0.015:
            return True
        if floor_accuracy < 0.80 and ambiguity >= 0.05 and commitment <= 0.78:
            return True
        if growth_drive >= 0.55 and pressure_level >= 0.45 and idle_streak < 2:
            return True
        return False

    def _consolidate_agents(self) -> None:
        """Run consolidation on each agent, promoting episodic patterns into substrate."""
        for agent in self.system.agents.values():
            if len(agent.engine.memory.entries) > 20:
                agent.engine._run_consolidation()

    def _inject_for_cycle(self, cycle: int) -> bool:
        """Inject signals/packets scheduled for *cycle*. Return True if anything was injected."""
        scheduled_specs = (self.scenario.signal_schedule_specs or {}).get(cycle)
        if scheduled_specs:
            self.system.inject_signal_specs(scheduled_specs)
            return True
        scheduled_packets = self.scenario.packet_schedule.get(cycle, 0)
        if scheduled_packets > 0:
            self.system.inject_signal(count=scheduled_packets)
            return True
        return False

    def _wrap_cycle(self, absolute_cycle: int) -> int | None:
        """Map an absolute cycle past the schedule into the repeating range.

        For signal_schedule_specs: wraps into [first_key .. last_key].
        For packet_schedule: wraps into [first_key .. last_key].
        Returns None if the schedule is empty.
        """
        schedule = self.scenario.signal_schedule_specs or self.scenario.packet_schedule
        if not schedule:
            return None
        keys = sorted(schedule.keys())
        first, last = keys[0], keys[-1]
        span = last - first + 1
        if span <= 0:
            return first
        return first + (absolute_cycle - first) % span

    def _apply_regulatory_signal(self, signal: RegulatorySignal | None) -> None:
        if signal is None:
            return
        signal_meta = dict(signal.metadata) if signal.metadata else {}
        gradient_mode = str(signal_meta.get("regulator_mode", "")) == "gradient"
        carryover_mode = signal.carryover_filter_mode
        if gradient_mode:
            hygiene = float(signal.hygiene_level)
            if hygiene >= 0.68:
                carryover_mode = "drop"
            elif hygiene >= 0.28:
                carryover_mode = "soften"
            else:
                carryover_mode = "keep"
        self._context_pressure = signal.context_pressure
        if gradient_mode:
            pressure = float(signal.pressure_level)
            if pressure >= 0.66:
                self._context_pressure = "high"
            elif pressure >= 0.36:
                self._context_pressure = "medium"
            else:
                self._context_pressure = "low"
        growth_authorization = str(signal.growth_authorization or "auto")
        if gradient_mode:
            if signal.growth_authorization is None:
                growth_drive = float(signal.growth_drive)
                if growth_drive >= 0.64:
                    growth_authorization = "initiate"
                elif growth_drive <= 0.12:
                    growth_authorization = "hold"
        self.system.environment.slow_growth_authorization = growth_authorization
        weak_context_bit = signal.bias_updates.get("weak_context_bit")
        self.system.environment.slow_weak_context_bit = (
            int(weak_context_bit) if weak_context_bit is not None else None
        )
        self.system.environment.slow_weak_context_gap = float(
            signal.bias_updates.get("weak_context_gap", 0.0),
        )

        # Store the signal's metadata so _build_slice_summary can record what was applied.
        self._applied_signal_meta = signal_meta
        self._applied_signal_meta.update({
            "applied_growth_authorization": growth_authorization,
            "applied_carryover_filter_mode": carryover_mode,
            "applied_context_pressure": self._context_pressure,
            "applied_reset_flags": dict(signal.reset_flags),
            "applied_reframe_flags": dict(signal.reframe_flags),
        })

        # Mode switch: rebuild the system but preserve learned substrate state
        # and consolidated memories from the previous mode.
        if signal.capability_mode is not None and signal.capability_mode != self._current_mode:
            self._switch_mode(signal.capability_mode)
        # Apply guidance bias BEFORE carryover filter so we can read full entry history.
        accuracy_gap = float(signal.bias_updates.get("accuracy_gap", 0.0))
        guidance_weight = float(signal.bias_updates.get("guidance_weight", 1.0))
        weak_context_bit = signal.bias_updates.get("weak_context_bit")
        weak_context_gap = float(signal.bias_updates.get("weak_context_gap", 0.0))
        differentiation_reframe = float(
            signal.reframe_flags.get("context_differentiation", 0.0),
        ) > 0.0
        mode = carryover_mode
        episodic_reset = float(signal.reset_flags.get("episodic", 0.0)) > 0.0
        hard_reset = mode == "drop" or episodic_reset
        self._skip_slice_end_consolidation = hard_reset
        self._applied_signal_meta["applied_fast_layer_hygiene"] = (
            "drop" if hard_reset else mode
        )
        self._applied_signal_meta["applied_guidance_bias_skipped"] = bool(hard_reset)
        if (accuracy_gap > 0.0 or differentiation_reframe) and not hard_reset:
            scale = min(2.0, 1.0 + accuracy_gap * 4.0 + max(0.0, 0.6 - guidance_weight))
            if differentiation_reframe:
                scale = min(2.5, scale * 1.35)
            self._apply_guidance_bias(
                scale,
                weak_context_bit=int(weak_context_bit) if weak_context_bit is not None else None,
                weak_context_gap=weak_context_gap,
            )
        for agent in self.system.agents.values():
            entries = list(agent.engine.memory.entries)
            if mode == "drop":
                agent.engine.memory.entries = []
            elif mode == "soften" and len(entries) > self.config.soften_history_keep:
                agent.engine.memory.entries = entries[-self.config.soften_history_keep :]
            if episodic_reset:
                # Clear episodic memory but preserve substrate — the learned
                # routing patterns in the substrate are still valuable even
                # when the episodic narrative needs a fresh start.
                agent.engine.memory.entries = []
        if mode in {"drop", "soften"} or episodic_reset:
            target_context = int(weak_context_bit) if weak_context_bit is not None else None
            intensity = "drop" if hard_reset else "soften"
            self.system.environment.scrub_poisoned_runtime_state(
                context_bit=target_context,
                intensity=intensity,
            )
            substrate_scale = (
                self.config.substrate_drop_scale
                if hard_reset
                else self.config.substrate_soften_scale
            )
            for agent in self.system.agents.values():
                agent.substrate.scrub_contextual_support(
                    context_bit=target_context,
                    scale=substrate_scale,
                )

    # Maps the mode-family names used by the policy layer to valid capability
    # policy strings accepted by NativeSubstrateSystem.
    _MODE_TO_CAPABILITY_POLICY: dict[str, str] = {
        "visible":       "self-selected",
        "latent":        "fixed-latent",
        "self-selected": "self-selected",
        "growth-visible":"growth-visible",
        "growth-latent": "growth-latent",
    }

    def _switch_mode(self, new_mode: str) -> None:
        """Rebuild the system under a new capability policy, preserving learned state.

        Scenario position (_scheduled_cycles_run) is preserved so the runner
        continues from the right point in the packet schedule. Full fast-layer
        runtime continuity is preserved internally across the rebuild, while the
        slow layer still sees only compact slice summaries.
        """
        # Preserve the full Phase 8 runtime layer across the rebuild: topology,
        # packet/runtime state, pending growth work, latent trackers, and
        # capability state all belong to fast-layer continuity, not to the
        # slow-layer summary interface.
        saved_runtime_state = self.system.environment.export_runtime_state()
        saved_runtime_state["capability_policy"] = self._MODE_TO_CAPABILITY_POLICY.get(
            new_mode,
            new_mode,
        )
        saved_global_cycle = self.system.global_cycle
        saved_session_start_cycle = self.system.session_start_cycle
        saved_capability_timeline = list(self.system.capability_timeline)

        # Preserve per-node REAL carryover on top of the environment runtime
        # state so substrate and episodic memory survive agent reconstruction.
        saved_carryovers: dict[str, object] = {}
        for node_id, agent in self.system.agents.items():
            saved_carryovers[node_id] = agent.engine.export_carryover()

        capability_policy = self._MODE_TO_CAPABILITY_POLICY.get(new_mode, new_mode)
        rebuilt = build_system_for_scenario(
            self.scenario,
            seed=self._seed,
            capability_policy=capability_policy,
        )
        rebuilt.global_cycle = saved_global_cycle
        rebuilt.session_start_cycle = saved_session_start_cycle
        rebuilt.environment.load_runtime_state(saved_runtime_state)
        rebuilt.capability_policy = capability_policy
        rebuilt.environment.capability_policy = capability_policy
        rebuilt.topology_state = rebuilt.environment.topology_state
        rebuilt.capability_timeline = saved_capability_timeline
        rebuilt.rebuild_agents_from_topology()

        self.system = rebuilt
        self._current_mode = new_mode
        # Mark as primed so we don't re-inject the initial signal burst into the new system.
        self._scenario_primed = True

        # Restore learned state into agents that exist in the new system.
        for node_id, carryover in saved_carryovers.items():
            agent = self.system.agents.get(node_id)
            if agent is not None:
                agent.engine.load_carryover(carryover)

    def _apply_guidance_bias(
        self,
        scale: float,
        *,
        weak_context_bit: int | None = None,
        weak_context_gap: float = 0.0,
    ) -> None:
        """Seed source node substrate toward its top-hinted transforms.

        For the weak context (identified by the regulator), also seeds all
        non-dominant transforms so the fast layer can explore alternatives
        rather than defaulting to the already-tried dominant route.

        Notes:
        - context_bit is read from ``head_context_bit`` in state_before.
        - neighbor and transform are parsed from the action string
          ``route_transform:{neighbor_id}:{transform_name}``.
        - Only transforms with positive hint weight are seeded.
        - Must be called BEFORE the carryover filter to read the full history.
        """
        source_id = self.system.environment.source_id
        source_agent = self.system.agents.get(source_id)
        if source_agent is None:
            return

        # Accumulate (context_bit, neighbor, transform) → hint weight
        hint_totals: dict[tuple[int | None, str, str], float] = {}
        # Track which transforms were actually chosen per (context, neighbor)
        chosen_counts: dict[tuple[int | None, str, str], int] = {}
        entry_count = 0
        for entry in source_agent.engine.memory.entries[-30:]:
            if not entry.action.startswith("route_transform:"):
                continue
            hints = {
                key.removeprefix("source_sequence_transform_hint_"): float(value)
                for key, value in entry.state_before.items()
                if key.startswith("source_sequence_transform_hint_")
            }
            if not hints:
                continue
            raw_ctx = entry.state_before.get("head_context_bit")
            context_bit: int | None = int(raw_ctx) if raw_ctx is not None else None
            # action format: route_transform:{neighbor_id}:{transform_name}
            parts = entry.action.split(":")
            neighbor_id = parts[1] if len(parts) >= 3 else None
            chosen_transform = parts[2] if len(parts) >= 3 else None
            for transform, weight in hints.items():
                if weight <= 0.0:
                    continue
                k = (context_bit, neighbor_id or "", transform)
                hint_totals[k] = hint_totals.get(k, 0.0) + weight
            if chosen_transform and neighbor_id:
                ck = (context_bit, neighbor_id, chosen_transform)
                chosen_counts[ck] = chosen_counts.get(ck, 0) + 1
            entry_count += 1

        if not hint_totals or entry_count == 0:
            return

        # Find strongest-hinted (neighbor, transform) per context
        by_context: dict[int | None, tuple[str, str, float]] = {}
        for (ctx, neighbor, transform), total in hint_totals.items():
            normalized = total / entry_count
            if ctx not in by_context or normalized > by_context[ctx][2]:
                by_context[ctx] = (neighbor, transform, normalized)

        seed_value = min(0.45, max(0.25, 0.25 * scale))
        for context_bit, (neighbor_id, transform, strength) in by_context.items():
            if strength < 0.05 or not neighbor_id:
                continue
            source_agent.substrate.seed_action_support(
                neighbor_id,
                transform,
                value=seed_value,
                context_bit=context_bit,
            )

        # For the weak context: seed all non-dominant transforms to encourage exploration
        if weak_context_bit is not None and weak_context_gap > 0.0:
            dominant = by_context.get(weak_context_bit)
            dominant_transform = dominant[1] if dominant else None
            # Find the most-used neighbor for this context from hint_totals
            neighbor_totals: dict[str, float] = {}
            for (ctx, neighbor, transform), total in hint_totals.items():
                if ctx == weak_context_bit and neighbor:
                    neighbor_totals[neighbor] = neighbor_totals.get(neighbor, 0.0) + total
            if not neighbor_totals:
                return
            best_neighbor = max(neighbor_totals, key=lambda n: neighbor_totals[n])
            # Collect all hinted transforms for this context
            hinted_transforms = {
                transform
                for (ctx, neighbor, transform) in hint_totals
                if ctx == weak_context_bit and neighbor == best_neighbor
            }
            # Seed each non-dominant transform with boosted support
            alt_seed = min(0.5, seed_value * (1.0 + weak_context_gap * 3.0))
            for transform in hinted_transforms:
                if transform == dominant_transform:
                    continue
                source_agent.substrate.seed_action_support(
                    best_neighbor,
                    transform,
                    value=alt_seed,
                    context_bit=weak_context_bit,
                )

    def _build_slice_summary(
        self,
        *,
        slice_id: int,
        slice_budget: int,
        start_cycle: int,
        end_cycle: int,
        start_summary: dict[str, object],
        end_summary: dict[str, object],
    ) -> SliceSummary:
        cycle_entries = self._entries_for_cycle_window(start_cycle, end_cycle)
        route_entries = [
            entry
            for entry in cycle_entries
            if entry.action.startswith("route:") or entry.action.startswith("route_transform:")
        ]
        delivered_packets = [
            packet
            for packet in self.system.environment.delivered_packets
            if packet.delivered_cycle is not None and start_cycle < packet.delivered_cycle <= end_cycle
        ]

        packets_evaluated = len(delivered_packets)
        exact_matches = sum(1 for packet in delivered_packets if packet.matched_target)
        partial_matches = sum(
            1
            for packet in delivered_packets
            if packet.bit_match_ratio is not None and 0.0 < float(packet.bit_match_ratio) < 1.0
        )
        mean_bit_accuracy = (
            mean(float(packet.bit_match_ratio or 0.0) for packet in delivered_packets)
            if delivered_packets
            else 0.0
        )
        mean_uncertainty = (
            mean(
                float(entry.prediction.uncertainty)
                for entry in cycle_entries
                if entry.prediction is not None
            )
            if any(entry.prediction is not None for entry in cycle_entries)
            else 1.0
        )
        mean_coherence = (
            mean(float(entry.coherence) for entry in cycle_entries)
            if cycle_entries
            else 0.0
        )
        coherence_delta = (
            mean(float(entry.delta) for entry in cycle_entries)
            if cycle_entries
            else 0.0
        )
        final_coherence = self._final_coherence_for_slice(cycle_entries)

        ambiguity_samples = [
            float(entry.state_before.get("provisional_context_ambiguity", 0.0))
            for entry in route_entries
            if isinstance(entry.state_before, dict)
            and "provisional_context_ambiguity" in entry.state_before
        ]
        commitment_margin_samples = [
            float(entry.state_before.get("transform_commitment_margin", 0.0))
            for entry in route_entries
            if isinstance(entry.state_before, dict)
            and "transform_commitment_margin" in entry.state_before
        ]
        hidden_packet_route_entries = [
            entry
            for entry in route_entries
            if isinstance(entry.state_before, dict)
            and float(entry.state_before.get("packet_has_context", 0.0)) >= 0.5
            and float(entry.state_before.get("effective_has_context", 0.0)) < 0.5
        ]
        hidden_packet_ambiguity_samples = [
            float(entry.state_before.get("provisional_context_ambiguity", 0.0))
            for entry in hidden_packet_route_entries
            if "provisional_context_ambiguity" in entry.state_before
        ]
        hidden_packet_commitment_margin_samples = [
            float(entry.state_before.get("transform_commitment_margin", 0.0))
            for entry in hidden_packet_route_entries
            if "transform_commitment_margin" in entry.state_before
        ]
        mean_provisional_ambiguity = (
            mean(ambiguity_samples)
            if ambiguity_samples
            else 0.0
        )
        max_provisional_ambiguity = (
            max(ambiguity_samples)
            if ambiguity_samples
            else 0.0
        )
        mean_commitment_margin = (
            mean(commitment_margin_samples)
            if commitment_margin_samples
            else 0.0
        )
        min_commitment_margin = (
            min(commitment_margin_samples)
            if commitment_margin_samples
            else 0.0
        )
        hidden_packet_mean_ambiguity = (
            mean(hidden_packet_ambiguity_samples)
            if hidden_packet_ambiguity_samples
            else 0.0
        )
        hidden_packet_max_ambiguity = (
            max(hidden_packet_ambiguity_samples)
            if hidden_packet_ambiguity_samples
            else 0.0
        )
        hidden_packet_mean_commitment_margin = (
            mean(hidden_packet_commitment_margin_samples)
            if hidden_packet_commitment_margin_samples
            else 0.0
        )
        hidden_packet_min_commitment_margin = (
            min(hidden_packet_commitment_margin_samples)
            if hidden_packet_commitment_margin_samples
            else 0.0
        )

        # Per-context accuracy
        context_accuracy: dict[str, float] = {}
        ctx_packets: dict[str | None, list[object]] = {}
        for packet in delivered_packets:
            key = str(packet.context_bit) if packet.context_bit is not None else "none"
            ctx_packets.setdefault(key, []).append(packet)
        for ctx_key, pkts in ctx_packets.items():
            ctx_acc = mean(float(p.bit_match_ratio or 0.0) for p in pkts)
            context_accuracy[f"context_{ctx_key}"] = round(ctx_acc, 4)
        worst_context_accuracy = (
            min(context_accuracy.values())
            if context_accuracy
            else round(mean_bit_accuracy, 4)
        )
        best_context_accuracy = (
            max(context_accuracy.values())
            if context_accuracy
            else round(mean_bit_accuracy, 4)
        )

        ambiguity_level, conflict_level = self._slice_diagnostics(delivered_packets)
        pressure_scale = {"low": 0.9, "medium": 1.0, "high": 1.1}.get(self._context_pressure, 1.0)
        ambiguity_level = min(1.0, ambiguity_level * pressure_scale)
        conflict_level = min(1.0, conflict_level * pressure_scale)
        guidance_alignment = self._source_guidance_alignment(start_cycle, end_cycle)
        if guidance_alignment is None:
            guidance_alignment = round(mean_bit_accuracy, 4)

        candidate_labels: list[str] = []
        if exact_matches > 0:
            candidate_labels.append("productive_route_support")
        if guidance_alignment >= 0.6:
            candidate_labels.append("sequence_guidance")
        if conflict_level > 0.0:
            candidate_labels.append("stale_context_support")
        if packets_evaluated > 0 and ambiguity_level <= 0.25 and mean_uncertainty <= 0.4:
            candidate_labels.append("stable_transform_support")

        total_action_cost = max(
            0.0,
            float(end_summary.get("total_action_cost", 0.0))
            - float(start_summary.get("total_action_cost", 0.0)),
        )
        mean_route_cost = (
            mean(float(entry.cost_secs) for entry in route_entries)
            if route_entries
            else 0.0
        )
        examples_seen = max(
            0,
            int(end_summary.get("injected_packets", 0)) - int(start_summary.get("injected_packets", 0)),
        )
        cycles_used = max(0, end_cycle - start_cycle)
        settlement_hint = "continue"
        if cycles_used == 0:
            settlement_hint = "settle"
        elif abs(coherence_delta) <= 0.02 and ambiguity_level <= 0.2 and conflict_level <= 0.2:
            settlement_hint = "settle"
        elif abs(coherence_delta) <= 0.02 and (ambiguity_level >= 0.5 or conflict_level >= 0.5):
            settlement_hint = "escalate"

        forecast_metrics = self._forecast_metrics(cycle_entries)
        growth_request = self._growth_request_summary()
        intervention_payoff_trend = self._intervention_payoff_trend(
            forecast_metrics=forecast_metrics,
            fallback_metric=mean_bit_accuracy,
        )
        self._last_slice_primary_metric = self._primary_forecast_metric(
            forecast_metrics,
            fallback_metric=mean_bit_accuracy,
        )
        summary = SliceSummary(
            slice_id=slice_id,
            slice_budget=slice_budget,
            cycles_used=cycles_used,
            examples_seen=examples_seen,
            benchmark_family=self.benchmark_family,
            task_key=self.task_key,
            mean_coherence=round(mean_coherence, 4),
            final_coherence=round(final_coherence, 4),
            coherence_delta=round(coherence_delta, 4),
            mean_uncertainty=round(mean_uncertainty, 4),
            ambiguity_level=round(ambiguity_level, 4),
            conflict_level=round(conflict_level, 4),
            guidance_alignment=round(float(guidance_alignment), 4),
            candidate_carryover_labels=candidate_labels,
            cost_summary={
                "total_action_cost": round(total_action_cost, 5),
                "mean_route_cost": round(mean_route_cost, 5),
                "bit_accuracy_per_cost": round(
                    mean_bit_accuracy / max(total_action_cost, 1e-9),
                    5,
                ),
                "exact_matches": float(exact_matches),
                "partial_matches": float(partial_matches),
            },
            settlement_hint=settlement_hint,
            context_accuracy=context_accuracy,
            mode_used=self._current_mode,
            metadata={
                "packets_evaluated": packets_evaluated,
                "final_accuracy": round(mean_bit_accuracy, 4),
                "mean_bit_accuracy": round(mean_bit_accuracy, 4),
                "floor_accuracy": round(float(worst_context_accuracy), 4),
                "worst_context_accuracy": round(float(worst_context_accuracy), 4),
                "best_context_accuracy": round(float(best_context_accuracy), 4),
                "route_entry_count": len(route_entries),
                "mean_provisional_context_ambiguity": round(float(mean_provisional_ambiguity), 4),
                "max_provisional_context_ambiguity": round(float(max_provisional_ambiguity), 4),
                "mean_transform_commitment_margin": round(float(mean_commitment_margin), 4),
                "min_transform_commitment_margin": round(float(min_commitment_margin), 4),
                "hidden_packet_route_count": len(hidden_packet_route_entries),
                "hidden_packet_mean_provisional_context_ambiguity": round(
                    float(hidden_packet_mean_ambiguity),
                    4,
                ),
                "hidden_packet_max_provisional_context_ambiguity": round(
                    float(hidden_packet_max_ambiguity),
                    4,
                ),
                "hidden_packet_mean_transform_commitment_margin": round(
                    float(hidden_packet_mean_commitment_margin),
                    4,
                ),
                "hidden_packet_min_transform_commitment_margin": round(
                    float(hidden_packet_min_commitment_margin),
                    4,
                ),
                "capability_policy": self.system.capability_policy,
                "context_pressure": self._context_pressure,
                "growth_request": growth_request,
                "forecast_metrics": forecast_metrics,
                "intervention_payoff_trend": intervention_payoff_trend,
                **self._applied_signal_meta,
            },
        )
        return summary

    def _entries_for_cycle_window(self, start_cycle: int, end_cycle: int) -> list[object]:
        entries = []
        for agent in self.system.agents.values():
            for entry in agent.engine.memory.entries:
                if start_cycle < entry.cycle <= end_cycle:
                    entries.append(entry)
        return entries

    def _final_coherence_for_slice(self, cycle_entries: list[object]) -> float:
        latest_by_agent: Dict[str, float] = {}
        for node_id, agent in self.system.agents.items():
            relevant = [entry for entry in agent.engine.memory.entries if entry in cycle_entries]
            if relevant:
                latest_by_agent[node_id] = float(relevant[-1].coherence)
        if latest_by_agent:
            return mean(latest_by_agent.values())
        return 0.0

    def _forecast_metrics(self, cycle_entries: list[object]) -> dict[str, object]:
        forecast_entries = [
            entry for entry in cycle_entries if getattr(entry, "forecast", None) is not None
        ]
        resolved_errors = [
            entry.forecast_error
            for entry in forecast_entries
            if getattr(entry, "forecast_error", None) is not None
            and entry.forecast_error.resolved
        ]
        entry_count = len(forecast_entries)
        resolved_count = len(resolved_errors)
        if entry_count <= 0:
            return {
                "forecast_entry_count": 0,
                "resolved_forecast_count": 0,
                "forecast_accuracy": None,
                "forecast_mean_confidence": None,
                "forecast_calibration_error": None,
                "forecast_mean_error": None,
                "forecast_regime_accuracy": {},
            }

        confidences = [
            float(entry.forecast.confidence)
            for entry in forecast_entries
            if entry.forecast is not None
        ]
        regime_stats: dict[str, dict[str, float]] = {}
        correct_total = 0
        calibration_errors: list[float] = []
        for error in resolved_errors:
            if error is None:
                continue
            label = str(error.actual_label or "unknown")
            stats = regime_stats.setdefault(label, {"count": 0.0, "correct": 0.0})
            stats["count"] += 1.0
            if error.correct:
                correct_total += 1
                stats["correct"] += 1.0
            if error.confidence_error is not None:
                calibration_errors.append(abs(float(error.confidence_error)))
        regime_accuracy = {
            label: round(values["correct"] / max(values["count"], 1.0), 4)
            for label, values in regime_stats.items()
        }
        return {
            "forecast_entry_count": entry_count,
            "resolved_forecast_count": resolved_count,
            "forecast_accuracy": (
                round(correct_total / max(resolved_count, 1), 4)
                if resolved_count > 0
                else None
            ),
            "forecast_mean_confidence": (
                round(mean(confidences), 4) if confidences else None
            ),
            "forecast_calibration_error": (
                round(mean(calibration_errors), 4)
                if calibration_errors
                else None
            ),
            "forecast_mean_error": (
                round(
                    mean(float(error.magnitude) for error in resolved_errors if error is not None),
                    4,
                )
                if resolved_errors
                else None
            ),
            "forecast_regime_accuracy": regime_accuracy,
        }

    def _growth_request_summary(self) -> dict[str, object]:
        capability_states = list(self.system.environment.capability_states.values())
        if not capability_states:
            return {
                "authorization": str(self.system.environment.slow_growth_authorization),
                "requesting_nodes": 0,
                "active_growth_nodes": 0,
                "pending_proposals": 0,
                "max_pressure": 0.0,
                "mean_pressure": 0.0,
                "max_readiness": 0.0,
                "mean_readiness": 0.0,
            }
        pressures = [
            float(state.growth_recruitment_pressure)
            for state in capability_states
        ]
        readiness = [
            float(state.growth_stabilization_readiness)
            for state in capability_states
        ]
        requesting_nodes = sum(
            1
            for state in capability_states
            if state.growth_recruitment_pressure >= 0.45
            or state.growth_enabled
        )
        active_growth_nodes = sum(
            1
            for state in capability_states
            if state.growth_enabled
        )
        return {
            "authorization": str(self.system.environment.slow_growth_authorization),
            "requesting_nodes": requesting_nodes,
            "active_growth_nodes": active_growth_nodes,
            "pending_proposals": len(self.system.environment.pending_growth_proposals),
            "max_pressure": round(max(pressures), 4),
            "mean_pressure": round(mean(pressures), 4),
            "max_readiness": round(max(readiness), 4),
            "mean_readiness": round(mean(readiness), 4),
        }

    def _primary_forecast_metric(
        self,
        forecast_metrics: dict[str, object],
        *,
        fallback_metric: float,
    ) -> float:
        forecast_accuracy = forecast_metrics.get("forecast_accuracy")
        if isinstance(forecast_accuracy, (int, float)):
            return float(forecast_accuracy)
        return float(fallback_metric)

    def _intervention_payoff_trend(
        self,
        *,
        forecast_metrics: dict[str, object],
        fallback_metric: float,
    ) -> dict[str, object]:
        current_metric = self._primary_forecast_metric(
            forecast_metrics,
            fallback_metric=fallback_metric,
        )
        applied_policy = self._applied_signal_meta.get("chosen_policy")
        if self._last_slice_primary_metric is None or applied_policy is None:
            return {
                "target_metric": "forecast_accuracy",
                "status": "unavailable",
                "signed_delta": None,
                "payoff": None,
                "regret": None,
                "policy": applied_policy,
            }

        observed_delta = current_metric - self._last_slice_primary_metric
        if observed_delta > 0.01:
            status = "improved"
        elif observed_delta < -0.01:
            status = "worsened"
        else:
            status = "flat"

        chosen_mode = self._applied_signal_meta.get("chosen_mode")
        predicted_delta = None
        if chosen_mode is not None:
            predicted_key = f"predicted_delta_{chosen_mode}"
            predicted_value = self._applied_signal_meta.get(predicted_key)
            if isinstance(predicted_value, (int, float)):
                predicted_delta = float(predicted_value)
        regret = (
            None if predicted_delta is None else abs(predicted_delta - observed_delta)
        )
        return {
            "target_metric": "forecast_accuracy",
            "status": status,
            "signed_delta": round(float(observed_delta), 4),
            "payoff": round(float(observed_delta), 4),
            "regret": None if regret is None else round(float(regret), 4),
            "policy": applied_policy,
            "mode": chosen_mode,
        }

    def _source_guidance_alignment(self, start_cycle: int, end_cycle: int) -> float | None:
        source_agent = self.system.agents.get(self.system.environment.source_id)
        if source_agent is None:
            return None
        matches = 0
        total = 0
        for entry in source_agent.engine.memory.entries:
            if not (start_cycle < entry.cycle <= end_cycle):
                continue
            if not entry.action.startswith("route_transform:"):
                continue
            hints = {
                key.removeprefix("source_sequence_transform_hint_"): float(value)
                for key, value in entry.state_before.items()
                if key.startswith("source_sequence_transform_hint_")
            }
            if not hints:
                continue
            strongest = max(hints.items(), key=lambda item: item[1])[0]
            chosen = entry.action.rsplit(":", 1)[-1]
            total += 1
            if chosen == strongest:
                matches += 1
        if total == 0:
            return None
        return matches / total

    def _slice_diagnostics(self, delivered_packets: Iterable[object]) -> tuple[float, float]:
        packets = list(delivered_packets)
        if not packets:
            return 0.0, 0.0
        successful_branches = self.system._successful_branches_by_group(packets)
        wrong_transform = 0
        stale_support = 0
        unstable = 0
        delayed = 0
        for packet in packets:
            final_transform = packet.transform_trace[-1] if packet.transform_trace else "identity"
            first_hop = self.system._packet_first_hop(packet)
            expected_transform = _expected_transform_for_task(packet.task_id, packet.context_bit)
            if expected_transform is not None and final_transform != expected_transform:
                wrong_transform += 1
                if self.system._suspect_stale_context_support(
                    packet,
                    expected_transform=expected_transform,
                    final_transform=final_transform,
                    first_hop=first_hop,
                ):
                    stale_support += 1
            if self.system._route_right_transform_wrong(
                packet,
                expected_transform=expected_transform,
                final_transform=final_transform,
                first_hop=first_hop,
                successful_branches=successful_branches,
            ):
                unstable += 1
            if self.system._delayed_correction(
                packets,
                packet=packet,
                first_hop=first_hop,
                final_transform=final_transform,
            ):
                delayed += 1
        ambiguity = (unstable + delayed + wrong_transform) / max(len(packets), 1)
        conflict = (stale_support + 0.5 * wrong_transform) / max(len(packets), 1)
        return min(1.0, ambiguity), min(1.0, conflict)


def build_system_for_scenario(
    scenario: ScenarioSpec,
    *,
    seed: int,
    capability_policy: str = "self-selected",
) -> NativeSubstrateSystem:
    return NativeSubstrateSystem(
        adjacency=scenario.adjacency,
        positions=scenario.positions,
        source_id=scenario.source_id,
        sink_id=scenario.sink_id,
        selector_seed=seed,
        packet_ttl=scenario.packet_ttl,
        source_admission_policy=scenario.source_admission_policy,
        source_admission_rate=scenario.source_admission_rate,
        source_admission_min_rate=scenario.source_admission_min_rate,
        source_admission_max_rate=scenario.source_admission_max_rate,
        capability_policy=capability_policy,
    )


def evaluate_laminated_scenario(
    scenario: ScenarioSpec,
    *,
    benchmark_family: str,
    task_key: str,
    seed: int,
    capability_policy: str = "self-selected",
    initial_cycle_budget: int = 8,
    safety_limit: int = 200,
    accuracy_threshold: float = 0.0,
    regulator_type: str = "heuristic",
) -> dict[str, object]:
    laminated_system = build_system_for_scenario(
        scenario,
        seed=seed,
        capability_policy=capability_policy,
    )
    runner = Phase8SliceRunner(
        laminated_system,
        scenario,
        benchmark_family=benchmark_family,
        task_key=task_key,
        seed=seed,
        initial_capability_mode=capability_policy,
    )
    if regulator_type == "learning":
        regulator: HeuristicSliceRegulator | LearningSliceRegulator | REALSliceRegulator | GradientSliceRegulator = LearningSliceRegulator(accuracy_threshold=accuracy_threshold)
    elif regulator_type == "gradient":
        regulator = GradientSliceRegulator(accuracy_threshold=accuracy_threshold)
    elif regulator_type == "real":
        regulator = REALSliceRegulator(accuracy_threshold=accuracy_threshold)
    else:
        regulator = HeuristicSliceRegulator(accuracy_threshold=accuracy_threshold)
    controller = LaminatedController(
        runner,
        regulator,
        initial_cycle_budget=initial_cycle_budget,
        safety_limit=safety_limit,
    )
    laminated_result: LaminatedRunResult = controller.run()

    experience_log = []
    if isinstance(regulator, LearningSliceRegulator):
        for exp in regulator.experiences:
            experience_log.append({
                "mode": exp.mode,
                "features": dict(exp.features),
                "predicted_delta": exp.predicted_delta,
                "observed_delta": round(exp.observed_delta, 4),
                "prediction_error": round(exp.prediction_error, 4) if exp.prediction_error is not None else None,
            })
    elif isinstance(regulator, REALSliceRegulator):
        experience_log = regulator.engine_history()

    return {
        "laminated_summary": runner.system.summarize(),
        "experience_log": experience_log,
        "laminated_run": {
            "final_decision": laminated_result.final_decision.value,
            "final_cycle_budget": laminated_result.final_cycle_budget,
            "final_signal": None
            if laminated_result.final_signal is None
            else {
                "next_slice_budget": laminated_result.final_signal.next_slice_budget,
                "budget_target": laminated_result.final_signal.budget_target,
                "pressure_level": laminated_result.final_signal.pressure_level,
                "hygiene_level": laminated_result.final_signal.hygiene_level,
                "growth_drive": laminated_result.final_signal.growth_drive,
                "portfolio_drive": laminated_result.final_signal.portfolio_drive,
                "settlement_confidence": laminated_result.final_signal.settlement_confidence,
                "carryover_filter_mode": laminated_result.final_signal.carryover_filter_mode,
                "context_pressure": laminated_result.final_signal.context_pressure,
                "growth_authorization": laminated_result.final_signal.growth_authorization,
                "decision_hint": laminated_result.final_signal.decision_hint.value,
                "execution_plan": None
                if laminated_result.final_signal.execution_plan is None
                else {
                    "initial_budget": laminated_result.final_signal.execution_plan.initial_budget,
                    "extend_step": laminated_result.final_signal.execution_plan.extend_step,
                    "soft_cap": laminated_result.final_signal.execution_plan.soft_cap,
                    "hard_cap": laminated_result.final_signal.execution_plan.hard_cap,
                    "early_stop_patience": laminated_result.final_signal.execution_plan.early_stop_patience,
                    "metadata": dict(laminated_result.final_signal.execution_plan.metadata),
                },
                "reset_flags": dict(laminated_result.final_signal.reset_flags),
                "reframe_flags": dict(laminated_result.final_signal.reframe_flags),
                "stop_reason": laminated_result.final_signal.stop_reason,
                "metadata": dict(laminated_result.final_signal.metadata),
            },
            "slice_summaries": [
                {
                    "slice_id": summary.slice_id,
                    "slice_budget": summary.slice_budget,
                    "cycles_used": summary.cycles_used,
                    "examples_seen": summary.examples_seen,
                    "mean_coherence": summary.mean_coherence,
                    "final_coherence": summary.final_coherence,
                    "coherence_delta": summary.coherence_delta,
                    "mean_uncertainty": summary.mean_uncertainty,
                    "ambiguity_level": summary.ambiguity_level,
                    "conflict_level": summary.conflict_level,
                    "guidance_alignment": summary.guidance_alignment,
                    "candidate_carryover_labels": list(summary.candidate_carryover_labels),
                    "candidate_carryover_count": summary.candidate_carryover_count,
                    "cost_summary": dict(summary.cost_summary),
                    "settlement_hint": summary.settlement_hint,
                    "context_accuracy": dict(summary.context_accuracy),
                    "mode_used": summary.mode_used,
                    "metadata": dict(summary.metadata),
                }
                for summary in laminated_result.summaries
            ],
        },
    }
