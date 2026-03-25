from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Dict, Iterable, List

from real_core import (
    HeuristicSliceRegulator,
    LaminatedController,
    LaminatedRunResult,
    LearningSliceRegulator,
    REALSliceRegulator,
    RegulatorySignal,
    SliceSummary,
)

from .environment import NativeSubstrateSystem, _expected_transform_for_task
from .scenarios import ScenarioSpec


@dataclass
class Phase8SliceRunnerConfig:
    soften_history_keep: int = 8


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

    def run_slice(
        self,
        *,
        slice_id: int,
        cycle_budget: int,
        regulatory_signal: RegulatorySignal | None = None,
    ) -> SliceSummary:
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

        # Consolidate at slice boundary: promote learned patterns into
        # substrate before the next slice's carryover filter runs.
        self._consolidate_agents()

        end_summary = self.system.summarize()
        return self._build_slice_summary(
            slice_id=slice_id,
            slice_budget=int(cycle_budget),
            start_cycle=start_cycle,
            end_cycle=self.system.global_cycle,
            start_summary=start_summary,
            end_summary=end_summary,
        )

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
        self._context_pressure = signal.context_pressure

        # Store the signal's metadata so _build_slice_summary can record what was applied.
        self._applied_signal_meta = dict(signal.metadata) if signal.metadata else {}

        # Mode switch: rebuild the system but preserve learned substrate state
        # and consolidated memories from the previous mode.
        if signal.capability_mode is not None and signal.capability_mode != self._current_mode:
            self._switch_mode(signal.capability_mode)
        # Apply guidance bias BEFORE carryover filter so we can read full entry history.
        accuracy_gap = float(signal.bias_updates.get("accuracy_gap", 0.0))
        guidance_weight = float(signal.bias_updates.get("guidance_weight", 1.0))
        weak_context_bit = signal.bias_updates.get("weak_context_bit")
        weak_context_gap = float(signal.bias_updates.get("weak_context_gap", 0.0))
        if accuracy_gap > 0.0:
            scale = min(2.0, 1.0 + accuracy_gap * 4.0 + max(0.0, 0.6 - guidance_weight))
            self._apply_guidance_bias(
                scale,
                weak_context_bit=int(weak_context_bit) if weak_context_bit is not None else None,
                weak_context_gap=weak_context_gap,
            )
        mode = signal.carryover_filter_mode
        episodic_reset = float(signal.reset_flags.get("episodic", 0.0)) > 0.0
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
        continues from the right point in the packet schedule.  Substrate state
        and consolidated episodic memories are carried over into the new system
        via export_carryover / load_carryover so prior learning is not lost.
        """
        # Export carryover from each agent before rebuilding.
        saved_carryovers: dict[str, object] = {}
        for node_id, agent in self.system.agents.items():
            saved_carryovers[node_id] = agent.engine.export_carryover()

        capability_policy = self._MODE_TO_CAPABILITY_POLICY.get(new_mode, new_mode)
        self.system = build_system_for_scenario(
            self.scenario,
            seed=self._seed,
            capability_policy=capability_policy,
        )
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
            dominant_transform = dominant[0] if dominant else None
            neighbor_id_for_weak = dominant[0] if dominant else None
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

        # Per-context accuracy
        context_accuracy: dict[str, float] = {}
        ctx_packets: dict[str | None, list[object]] = {}
        for packet in delivered_packets:
            key = str(packet.context_bit) if packet.context_bit is not None else "none"
            ctx_packets.setdefault(key, []).append(packet)
        for ctx_key, pkts in ctx_packets.items():
            ctx_acc = mean(float(p.bit_match_ratio or 0.0) for p in pkts)
            context_accuracy[f"context_{ctx_key}"] = round(ctx_acc, 4)

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

        return SliceSummary(
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
                "mean_bit_accuracy": round(mean_bit_accuracy, 4),
                "capability_policy": self.system.capability_policy,
                "context_pressure": self._context_pressure,
                **self._applied_signal_meta,
            },
        )

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
        regulator: HeuristicSliceRegulator | LearningSliceRegulator | REALSliceRegulator = LearningSliceRegulator(accuracy_threshold=accuracy_threshold)
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
                "carryover_filter_mode": laminated_result.final_signal.carryover_filter_mode,
                "context_pressure": laminated_result.final_signal.context_pressure,
                "decision_hint": laminated_result.final_signal.decision_hint.value,
                "stop_reason": laminated_result.final_signal.stop_reason,
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
