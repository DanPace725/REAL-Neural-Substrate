from __future__ import annotations

import json
import shutil
import uuid
from statistics import mean

from scripts.compare_cold_warm import ROOT, SCENARIOS, build_system
from scripts.compare_latent_context import latent_signal_specs
from scripts.evaluate_transfer_asymmetry import DEFAULT_SEEDS, _runtime_commitment
from phase8.environment import (
    LATENT_CONTEXT_CONFIDENCE_THRESHOLD,
    LATENT_TRANSFER_EFFECTIVE_THRESHOLD_BOOST,
)


TASK_A = "cvt1_task_a_stage1"
TASK_B = "cvt1_task_b_stage1"
BALANCE_STRONG_MARGIN = 0.5
BALANCE_SUSTAIN_CYCLES = 3
LATENT_DIAGNOSTIC_FIELDS = (
    "wrong_transform_family",
    "route_wrong_transform_potentially_right",
    "route_right_transform_wrong",
    "transform_unstable_across_inferred_context_boundary",
    "delayed_correction",
    "stale_context_support_suspicions",
)


def _route_neighbor(action: str) -> str | None:
    if action.startswith("route_transform:"):
        parts = action.split(":")
        if len(parts) == 3:
            return parts[1]
        return None
    if action.startswith("route:"):
        return action.split(":", 1)[1]
    return None


def _route_transform(action: str) -> str:
    if action.startswith("route_transform:"):
        parts = action.split(":")
        if len(parts) == 3:
            return parts[2]
    if action.startswith("route:"):
        return "identity"
    return ""


def _overall_stat(summary: dict[str, object], field: str) -> float:
    return float(summary.get("task_diagnostics", {}).get("overall", {}).get(field, 0.0))


def _context_stat(summary: dict[str, object], context_key: str, field: str) -> float:
    return float(
        summary.get("task_diagnostics", {})
        .get("contexts", {})
        .get(context_key, {})
        .get(field, 0.0)
    )


def _run_training(seed: int, scenario_name: str):
    scenario = SCENARIOS[scenario_name]
    system = build_system(seed, scenario_name)
    system.run_workload(
        cycles=scenario.cycles,
        initial_packets=scenario.initial_packets,
        packet_schedule=scenario.packet_schedule,
        initial_signal_specs=scenario.initial_signal_specs,
        signal_schedule_specs=scenario.signal_schedule_specs,
    )
    return system


def _balance_signal(credit: float, debt: float) -> tuple[float, float]:
    total = credit + debt
    balance = credit - debt
    if total <= 1e-9:
        return round(balance, 5), 0.0
    return round(balance, 5), round(balance / total, 5)


def _first_sustained_cycle(
    records: list[dict[str, float]],
    field: str,
    *,
    threshold: float,
    sustain_cycles: int = BALANCE_SUSTAIN_CYCLES,
) -> int | None:
    if sustain_cycles <= 0:
        sustain_cycles = 1
    last_start = len(records) - sustain_cycles + 1
    for start_index in range(max(0, last_start)):
        window = records[start_index : start_index + sustain_cycles]
        if len(window) < sustain_cycles:
            continue
        if all(float(item[field]) >= threshold for item in window):
            return int(window[0]["cycle"])
    return None


def _selector_cycle_summary(entries: dict[str, object]) -> dict[str, object]:
    route_branch_counts: dict[str, int] = {}
    route_transform_counts: dict[str, int] = {}
    route_mode_counts: dict[str, int] = {}
    branch_transform_counts: dict[str, int] = {}
    route_coherence_total = 0.0
    route_delta_total = 0.0
    route_count = 0
    rest_count = 0
    invest_count = 0

    for entry in entries.values():
        if entry is None:
            continue
        action = str(entry.action)
        if action == "rest":
            rest_count += 1
            continue
        if action.startswith("invest:") or action == "maintain_edges":
            invest_count += 1
            continue
        neighbor_id = _route_neighbor(action)
        if neighbor_id is None:
            continue
        route_count += 1
        route_branch_counts[neighbor_id] = route_branch_counts.get(neighbor_id, 0) + 1
        transform_name = _route_transform(action)
        route_transform_counts[transform_name] = route_transform_counts.get(transform_name, 0) + 1
        branch_transform_key = f"{neighbor_id}:{transform_name}"
        branch_transform_counts[branch_transform_key] = (
            branch_transform_counts.get(branch_transform_key, 0) + 1
        )
        mode_name = str(entry.mode)
        route_mode_counts[mode_name] = route_mode_counts.get(mode_name, 0) + 1
        route_coherence_total += float(entry.coherence)
        route_delta_total += float(entry.delta)

    return {
        "route_count": route_count,
        "rest_count": rest_count,
        "invest_count": invest_count,
        "route_branch_counts": route_branch_counts,
        "route_transform_counts": route_transform_counts,
        "route_mode_counts": route_mode_counts,
        "branch_transform_counts": branch_transform_counts,
        "mean_route_coherence": round(route_coherence_total / max(route_count, 1), 5),
        "mean_route_delta": round(route_delta_total / max(route_count, 1), 5),
    }


def _aggregate_selector_window(cycle_records: list[dict[str, object]]) -> dict[str, object]:
    route_branch_counts: dict[str, int] = {}
    route_transform_counts: dict[str, int] = {}
    route_mode_counts: dict[str, int] = {}
    branch_transform_counts: dict[str, int] = {}
    total_route = 0
    total_rest = 0
    total_invest = 0
    coherence_values: list[float] = []
    delta_values: list[float] = []

    for record in cycle_records:
        total_route += int(record.get("route_count", 0))
        total_rest += int(record.get("rest_count", 0))
        total_invest += int(record.get("invest_count", 0))
        coherence_values.append(float(record.get("mean_route_coherence", 0.0)))
        delta_values.append(float(record.get("mean_route_delta", 0.0)))
        for key, value in dict(record.get("route_branch_counts", {})).items():
            route_branch_counts[key] = route_branch_counts.get(key, 0) + int(value)
        for key, value in dict(record.get("route_transform_counts", {})).items():
            route_transform_counts[key] = route_transform_counts.get(key, 0) + int(value)
        for key, value in dict(record.get("route_mode_counts", {})).items():
            route_mode_counts[key] = route_mode_counts.get(key, 0) + int(value)
        for key, value in dict(record.get("branch_transform_counts", {})).items():
            branch_transform_counts[key] = branch_transform_counts.get(key, 0) + int(value)

    def _shares(counts: dict[str, int], total: int) -> dict[str, float]:
        if total <= 0:
            return {}
        return {
            key: round(value / total, 5)
            for key, value in sorted(counts.items())
        }

    top_branch_transforms = sorted(
        branch_transform_counts.items(),
        key=lambda item: (-item[1], item[0]),
    )[:5]

    return {
        "cycles_in_window": len(cycle_records),
        "total_route_actions": total_route,
        "total_rest_actions": total_rest,
        "total_invest_actions": total_invest,
        "route_branch_counts": dict(sorted(route_branch_counts.items())),
        "route_branch_shares": _shares(route_branch_counts, total_route),
        "route_transform_counts": dict(sorted(route_transform_counts.items())),
        "route_transform_shares": _shares(route_transform_counts, total_route),
        "route_mode_counts": dict(sorted(route_mode_counts.items())),
        "route_mode_shares": _shares(route_mode_counts, total_route),
        "top_branch_transform_counts": [
            {"branch_transform": key, "count": value}
            for key, value in top_branch_transforms
        ],
        "mean_route_coherence": round(mean(coherence_values), 5) if coherence_values else 0.0,
        "mean_route_delta": round(mean(delta_values), 5) if delta_values else 0.0,
    }


def _timeline_summary(records: list[dict[str, float]]) -> dict[str, float | None]:
    branch_debt_values = [record["branch_context_debt_total"] for record in records]
    context_branch_debt_values = [
        record["context_branch_transform_debt_total"] for record in records
    ]
    combined_balance_values = [record["combined_context_balance_total"] for record in records]
    combined_margin_values = [record["combined_context_balance_margin"] for record in records]

    peak_branch_debt = max(branch_debt_values, default=0.0)
    peak_context_branch_debt = max(context_branch_debt_values, default=0.0)
    min_combined_balance = min(combined_balance_values, default=0.0)
    min_combined_margin = min(combined_margin_values, default=0.0)

    peak_branch_cycle = next(
        (
            record["cycle"]
            for record in records
            if record["branch_context_debt_total"] == peak_branch_debt
        ),
        None,
    )
    peak_context_branch_cycle = next(
        (
            record["cycle"]
            for record in records
            if record["context_branch_transform_debt_total"] == peak_context_branch_debt
        ),
        None,
    )
    min_combined_balance_cycle = next(
        (
            record["cycle"]
            for record in records
            if record["combined_context_balance_total"] == min_combined_balance
        ),
        None,
    )
    min_combined_margin_cycle = next(
        (
            record["cycle"]
            for record in records
            if record["combined_context_balance_margin"] == min_combined_margin
        ),
        None,
    )

    branch_half_relief_cycle = None
    if peak_branch_cycle is not None and peak_branch_debt > 0.0:
        half_level = peak_branch_debt * 0.5
        for record in records:
            if record["cycle"] <= peak_branch_cycle:
                continue
            if record["branch_context_debt_total"] <= half_level:
                branch_half_relief_cycle = record["cycle"]
                break

    context_branch_half_relief_cycle = None
    if peak_context_branch_cycle is not None and peak_context_branch_debt > 0.0:
        half_level = peak_context_branch_debt * 0.5
        for record in records:
            if record["cycle"] <= peak_context_branch_cycle:
                continue
            if record["context_branch_transform_debt_total"] <= half_level:
                context_branch_half_relief_cycle = record["cycle"]
                break

    negative_balance_cycles = [
        int(record["cycle"])
        for record in records
        if float(record["combined_context_balance_total"]) < 0.0
    ]

    final = records[-1] if records else {}
    return {
        "peak_branch_context_debt_total": round(peak_branch_debt, 5),
        "peak_branch_context_debt_cycle": peak_branch_cycle,
        "branch_context_debt_auc": round(sum(branch_debt_values), 5),
        "branch_context_half_relief_cycle": branch_half_relief_cycle,
        "peak_context_branch_transform_debt_total": round(peak_context_branch_debt, 5),
        "peak_context_branch_transform_debt_cycle": peak_context_branch_cycle,
        "context_branch_transform_debt_auc": round(sum(context_branch_debt_values), 5),
        "context_branch_transform_half_relief_cycle": context_branch_half_relief_cycle,
        "combined_context_balance_auc": round(sum(combined_balance_values), 5),
        "combined_context_balance_margin_auc": round(sum(combined_margin_values), 5),
        "min_combined_context_balance_total": round(min_combined_balance, 5),
        "min_combined_context_balance_cycle": min_combined_balance_cycle,
        "min_combined_context_balance_margin": round(min_combined_margin, 5),
        "min_combined_context_balance_margin_cycle": min_combined_margin_cycle,
        "negative_combined_balance_cycle_count": len(negative_balance_cycles),
        "first_negative_combined_balance_cycle": (
            negative_balance_cycles[0] if negative_balance_cycles else None
        ),
        "last_negative_combined_balance_cycle": (
            negative_balance_cycles[-1] if negative_balance_cycles else None
        ),
        "first_positive_combined_balance_cycle": _first_sustained_cycle(
            records,
            "combined_context_balance_total",
            threshold=0.0,
            sustain_cycles=1,
        ),
        "first_strong_combined_balance_cycle": _first_sustained_cycle(
            records,
            "combined_context_balance_margin",
            threshold=BALANCE_STRONG_MARGIN,
            sustain_cycles=BALANCE_SUSTAIN_CYCLES,
        ),
        "final_branch_context_debt_total": round(
            float(final.get("branch_context_debt_total", 0.0)),
            5,
        ),
        "final_context_branch_transform_debt_total": round(
            float(final.get("context_branch_transform_debt_total", 0.0)),
            5,
        ),
        "final_branch_context_credit_total": round(
            float(final.get("branch_context_credit_total", 0.0)),
            5,
        ),
        "final_context_branch_transform_credit_total": round(
            float(final.get("context_branch_transform_credit_total", 0.0)),
            5,
        ),
        "final_combined_context_balance_total": round(
            float(final.get("combined_context_balance_total", 0.0)),
            5,
        ),
        "final_combined_context_balance_margin": round(
            float(final.get("combined_context_balance_margin", 0.0)),
            5,
        ),
        "final_mean_bit_accuracy": round(float(final.get("mean_bit_accuracy", 0.0)), 5),
        "final_exact_matches": int(final.get("exact_matches", 0)),
    }


def _first_cycle_at_threshold(
    records: list[dict[str, object]],
    field: str,
    *,
    threshold: float,
) -> int | None:
    for record in records:
        if float(record.get(field, 0.0)) >= threshold:
            return int(record["cycle"])
    return None


def _task_id_hint(initial_specs, schedule_specs) -> str | None:
    task_ids = {
        str(spec.task_id)
        for spec in list(initial_specs or [])
        if getattr(spec, "task_id", None) is not None
    }
    for specs in dict(schedule_specs or {}).values():
        for spec in specs:
            if getattr(spec, "task_id", None) is not None:
                task_ids.add(str(spec.task_id))
    if len(task_ids) == 1:
        return next(iter(task_ids))
    return None


def _source_cycle_snapshot(system, *, task_id_hint: str | None = None) -> dict[str, float | int | None]:
    source_id = system.environment.source_id
    state = system.environment.state_for(source_id)
    head_packet = system.environment.inboxes[source_id][0] if system.environment.inboxes[source_id] else None
    head_task_id = head_packet.task_id if head_packet is not None else task_id_hint
    latent_snapshot = system.environment._latent_snapshot(source_id, head_task_id, observe=False)
    transfer_adaptation_phase = float(
        system.environment.transfer_adaptation_phase(head_task_id, node_id=source_id)
        if head_task_id is not None
        else 0.0
    )
    effective_threshold = (
        LATENT_CONTEXT_CONFIDENCE_THRESHOLD
        + transfer_adaptation_phase * LATENT_TRANSFER_EFFECTIVE_THRESHOLD_BOOST
    )
    channel_confidence = dict(latent_snapshot.get("channel_context_confidence", {}))
    channel_estimate = dict(latent_snapshot.get("channel_context_estimate", {}))
    channel_context_evidence = dict(latent_snapshot.get("channel_context_evidence", {}))
    channel_transform_evidence = dict(latent_snapshot.get("channel_transform_evidence", {}))
    return {
        "source_atp": round(float(state.atp), 5),
        "source_atp_ratio": round(state.atp / max(state.max_atp, 1e-9), 5),
        "source_reward_buffer": round(float(state.reward_buffer), 5),
        "source_last_feedback_amount": round(float(state.last_feedback_amount), 5),
        "source_last_match_ratio": round(float(state.last_match_ratio), 5),
        "latent_context_available": 1.0 if latent_snapshot.get("available") else 0.0,
        "latent_context_estimate": (
            float(latent_snapshot.get("estimate")) if latent_snapshot.get("estimate") is not None else 0.0
        ),
        "latent_context_confidence": round(float(latent_snapshot.get("confidence", 0.0)), 5),
        "transfer_adaptation_phase": round(transfer_adaptation_phase, 5),
        "effective_context_threshold": round(effective_threshold, 5),
        "source_sequence_available": 1.0 if latent_snapshot.get("sequence_available") else 0.0,
        "source_sequence_context_estimate": (
            float(latent_snapshot.get("sequence_context_estimate"))
            if latent_snapshot.get("sequence_context_estimate") is not None
            else 0.0
        ),
        "source_sequence_context_confidence": round(
            float(latent_snapshot.get("sequence_context_confidence", 0.0)),
            5,
        ),
        "source_sequence_channel_context_confidence": round(
            float(channel_confidence.get("source_sequence", 0.0)),
            5,
        ),
        "source_sequence_channel_context_estimate": (
            float(channel_estimate.get("source_sequence"))
            if channel_estimate.get("source_sequence") is not None
            else 0.0
        ),
        "source_sequence_prev_parity": (
            float(latent_snapshot.get("sequence_prev_parity"))
            if latent_snapshot.get("sequence_prev_parity") is not None
            else 0.0
        ),
        "source_sequence_change_ratio": round(float(latent_snapshot.get("sequence_change_ratio", 0.0)), 5),
        "source_sequence_repeat_input": round(float(latent_snapshot.get("sequence_repeat_input", 0.0)), 5),
        "effective_has_context": (
            1.0
            if head_packet is not None and head_packet.context_bit is not None
            else (
                1.0
                if latent_snapshot.get("available")
                and latent_snapshot.get("estimate") is not None
                and float(latent_snapshot.get("confidence", 0.0)) >= effective_threshold
                else 0.0
            )
        ),
        "effective_context_bit": (
            float(head_packet.context_bit)
            if head_packet is not None and head_packet.context_bit is not None
            else (
                float(latent_snapshot.get("estimate"))
                if latent_snapshot.get("available")
                and latent_snapshot.get("estimate") is not None
                and float(latent_snapshot.get("confidence", 0.0)) >= effective_threshold
                else 0.0
            )
        ),
        "effective_context_confidence": (
            1.0
            if head_packet is not None and head_packet.context_bit is not None
            else round(
                float(latent_snapshot.get("confidence", 0.0)),
                5,
            )
            if latent_snapshot.get("available")
            and latent_snapshot.get("estimate") is not None
            and float(latent_snapshot.get("confidence", 0.0)) >= effective_threshold
            else 0.0
        ),
        "context_promotion_ready": 1.0 if latent_snapshot.get("promotion_ready") else 0.0,
        "latent_observation_streak": int(latent_snapshot.get("observation_streak", 0)),
        "source_route_context_confidence": round(float(channel_confidence.get("source_route", 0.0)), 5),
        "source_feedback_context_confidence": round(float(channel_confidence.get("source_feedback", 0.0)), 5),
        "source_route_context_estimate": (
            float(channel_estimate.get("source_route"))
            if channel_estimate.get("source_route") is not None
            else 0.0
        ),
        "source_feedback_context_estimate": (
            float(channel_estimate.get("source_feedback"))
            if channel_estimate.get("source_feedback") is not None
            else 0.0
        ),
        "source_sequence_context0_evidence": round(
            float(dict(channel_context_evidence.get("source_sequence", {})).get(0, 0.0)),
            5,
        ),
        "source_sequence_context1_evidence": round(
            float(dict(channel_context_evidence.get("source_sequence", {})).get(1, 0.0)),
            5,
        ),
        "source_sequence_context2_evidence": round(
            float(dict(channel_context_evidence.get("source_sequence", {})).get(2, 0.0)),
            5,
        ),
        "source_sequence_context3_evidence": round(
            float(dict(channel_context_evidence.get("source_sequence", {})).get(3, 0.0)),
            5,
        ),
        "source_route_context0_evidence": round(
            float(dict(channel_context_evidence.get("source_route", {})).get(0, 0.0)),
            5,
        ),
        "source_route_context1_evidence": round(
            float(dict(channel_context_evidence.get("source_route", {})).get(1, 0.0)),
            5,
        ),
        "source_route_context2_evidence": round(
            float(dict(channel_context_evidence.get("source_route", {})).get(2, 0.0)),
            5,
        ),
        "source_route_context3_evidence": round(
            float(dict(channel_context_evidence.get("source_route", {})).get(3, 0.0)),
            5,
        ),
        "source_feedback_context0_evidence": round(
            float(dict(channel_context_evidence.get("source_feedback", {})).get(0, 0.0)),
            5,
        ),
        "source_feedback_context1_evidence": round(
            float(dict(channel_context_evidence.get("source_feedback", {})).get(1, 0.0)),
            5,
        ),
        "source_feedback_context2_evidence": round(
            float(dict(channel_context_evidence.get("source_feedback", {})).get(2, 0.0)),
            5,
        ),
        "source_feedback_context3_evidence": round(
            float(dict(channel_context_evidence.get("source_feedback", {})).get(3, 0.0)),
            5,
        ),
        "source_route_transform_evidence_rotate_left_1": round(
            float(dict(channel_transform_evidence.get("source_route", {})).get("rotate_left_1", 0.0)),
            5,
        ),
        "source_route_transform_evidence_xor_mask_1010": round(
            float(dict(channel_transform_evidence.get("source_route", {})).get("xor_mask_1010", 0.0)),
            5,
        ),
        "source_feedback_transform_evidence_rotate_left_1": round(
            float(dict(channel_transform_evidence.get("source_feedback", {})).get("rotate_left_1", 0.0)),
            5,
        ),
        "source_feedback_transform_evidence_xor_mask_1010": round(
            float(dict(channel_transform_evidence.get("source_feedback", {})).get("xor_mask_1010", 0.0)),
            5,
        ),
    }


def _downstream_tracker_snapshot(system, *, task_id_hint: str | None = None) -> dict[str, float | None]:
    source_id = system.environment.source_id
    sink_id = system.environment.sink_id
    estimates: list[int] = []
    confidences: list[float] = []
    route_confidences: list[float] = []
    feedback_confidences: list[float] = []
    route_context0: list[float] = []
    route_context1: list[float] = []
    feedback_context0: list[float] = []
    feedback_context1: list[float] = []
    for node_id in system.environment.node_states:
        if node_id in {source_id, sink_id}:
            continue
        snapshot = system.environment._latent_snapshot(node_id, task_id_hint, observe=False)
        if snapshot.get("estimate") is not None:
            estimates.append(int(snapshot.get("estimate")))
        confidences.append(float(snapshot.get("confidence", 0.0)))
        channel_confidence = dict(snapshot.get("channel_context_confidence", {}))
        route_confidences.append(float(channel_confidence.get("downstream_route", 0.0)))
        feedback_confidences.append(float(channel_confidence.get("downstream_feedback", 0.0)))
        channel_context = dict(snapshot.get("channel_context_evidence", {}))
        route_context = dict(channel_context.get("downstream_route", {}))
        feedback_context = dict(channel_context.get("downstream_feedback", {}))
        route_context0.append(float(route_context.get(0, 0.0)))
        route_context1.append(float(route_context.get(1, 0.0)))
        feedback_context0.append(float(feedback_context.get(0, 0.0)))
        feedback_context1.append(float(feedback_context.get(1, 0.0)))
    return {
        "downstream_tracker_count": float(len(confidences)),
        "downstream_mean_latent_confidence": round(mean(confidences), 5) if confidences else 0.0,
        "downstream_mean_route_context_confidence": round(mean(route_confidences), 5) if route_confidences else 0.0,
        "downstream_mean_feedback_context_confidence": round(mean(feedback_confidences), 5) if feedback_confidences else 0.0,
        "downstream_route_context0_evidence_mean": round(mean(route_context0), 5) if route_context0 else 0.0,
        "downstream_route_context1_evidence_mean": round(mean(route_context1), 5) if route_context1 else 0.0,
        "downstream_feedback_context0_evidence_mean": round(mean(feedback_context0), 5) if feedback_context0 else 0.0,
        "downstream_feedback_context1_evidence_mean": round(mean(feedback_context1), 5) if feedback_context1 else 0.0,
        "downstream_estimate_context0_fraction": (
            round(sum(1 for value in estimates if value == 0) / max(len(estimates), 1), 5)
            if estimates
            else 0.0
        ),
        "downstream_estimate_context1_fraction": (
            round(sum(1 for value in estimates if value == 1) / max(len(estimates), 1), 5)
            if estimates
            else 0.0
        ),
    }


def _latent_timeline_summary(records: list[dict[str, object]]) -> dict[str, float | int | None]:
    final = records[-1] if records else {}
    latent_confidences = [float(record.get("latent_context_confidence", 0.0)) for record in records]
    effective_confidences = [float(record.get("effective_context_confidence", 0.0)) for record in records]
    source_sequence_confidences = [
        float(record.get("source_sequence_context_confidence", 0.0)) for record in records
    ]
    source_sequence_channel_confidences = [
        float(record.get("source_sequence_channel_context_confidence", 0.0)) for record in records
    ]
    source_route_confidences = [
        float(record.get("source_route_context_confidence", 0.0)) for record in records
    ]
    source_feedback_confidences = [
        float(record.get("source_feedback_context_confidence", 0.0)) for record in records
    ]
    downstream_route_confidences = [
        float(record.get("downstream_mean_route_context_confidence", 0.0)) for record in records
    ]
    downstream_feedback_confidences = [
        float(record.get("downstream_mean_feedback_context_confidence", 0.0)) for record in records
    ]
    peak_latent_confidence = max(latent_confidences, default=0.0)
    peak_latent_confidence_cycle = next(
        (record["cycle"] for record in records if float(record.get("latent_context_confidence", 0.0)) == peak_latent_confidence),
        None,
    )
    low_confidence_cycles = [
        record
        for record in records
        if float(record.get("latent_context_available", 0.0)) >= 0.5
        and float(record.get("effective_has_context", 0.0)) < 0.5
    ]
    pre_effective_cycles = [
        record for record in records if float(record.get("effective_has_context", 0.0)) < 0.5
    ]
    return {
        "first_latent_context_available_cycle": _first_cycle_at_threshold(
            records,
            "latent_context_available",
            threshold=0.5,
        ),
        "first_effective_context_cycle": _first_cycle_at_threshold(
            records,
            "effective_has_context",
            threshold=0.5,
        ),
        "first_context_promotion_ready_cycle": _first_cycle_at_threshold(
            records,
            "context_promotion_ready",
            threshold=0.5,
        ),
        "first_context_growth_ready_cycle": _first_cycle_at_threshold(
            records,
            "context_growth_ready",
            threshold=0.5,
        ),
        "peak_latent_context_confidence": round(peak_latent_confidence, 5),
        "peak_latent_context_confidence_cycle": peak_latent_confidence_cycle,
        "avg_latent_context_confidence": round(mean(latent_confidences), 5) if latent_confidences else 0.0,
        "avg_effective_context_confidence": round(mean(effective_confidences), 5) if effective_confidences else 0.0,
        "avg_source_sequence_context_confidence": (
            round(mean(source_sequence_confidences), 5) if source_sequence_confidences else 0.0
        ),
        "avg_source_sequence_channel_context_confidence": (
            round(mean(source_sequence_channel_confidences), 5)
            if source_sequence_channel_confidences
            else 0.0
        ),
        "avg_source_route_context_confidence": (
            round(mean(source_route_confidences), 5) if source_route_confidences else 0.0
        ),
        "avg_source_feedback_context_confidence": (
            round(mean(source_feedback_confidences), 5) if source_feedback_confidences else 0.0
        ),
        "avg_downstream_route_context_confidence": (
            round(mean(downstream_route_confidences), 5) if downstream_route_confidences else 0.0
        ),
        "avg_downstream_feedback_context_confidence": (
            round(mean(downstream_feedback_confidences), 5) if downstream_feedback_confidences else 0.0
        ),
        "avg_source_atp_ratio": round(
            mean(float(record.get("source_atp_ratio", 0.0)) for record in records),
            5,
        ) if records else 0.0,
        "low_confidence_cycle_count": len(low_confidence_cycles),
        "pre_effective_context_cycle_count": len(pre_effective_cycles),
        "pre_effective_wrong_transform_events": int(
            sum(float(record.get("delta_wrong_transform_family", 0.0)) for record in pre_effective_cycles)
        ),
        "pre_effective_instability_events": int(
            sum(
                float(record.get("delta_transform_unstable_across_inferred_context_boundary", 0.0))
                for record in pre_effective_cycles
            )
        ),
        "instability_event_count": int(
            sum(float(record.get("delta_transform_unstable_across_inferred_context_boundary", 0.0)) for record in records)
        ),
        "wrong_transform_event_count": int(
            sum(float(record.get("delta_wrong_transform_family", 0.0)) for record in records)
        ),
        "delayed_correction_event_count": int(
            sum(float(record.get("delta_delayed_correction", 0.0)) for record in records)
        ),
        "route_wrong_transform_potentially_right_event_count": int(
            sum(float(record.get("delta_route_wrong_transform_potentially_right", 0.0)) for record in records)
        ),
        "route_right_transform_wrong_event_count": int(
            sum(float(record.get("delta_route_right_transform_wrong", 0.0)) for record in records)
        ),
        "final_latent_context_confidence": round(float(final.get("latent_context_confidence", 0.0)), 5),
        "final_effective_context_confidence": round(float(final.get("effective_context_confidence", 0.0)), 5),
        "final_source_sequence_context_confidence": round(
            float(final.get("source_sequence_context_confidence", 0.0)),
            5,
        ),
        "final_source_sequence_channel_context_confidence": round(
            float(final.get("source_sequence_channel_context_confidence", 0.0)),
            5,
        ),
        "final_source_route_context_confidence": round(
            float(final.get("source_route_context_confidence", 0.0)),
            5,
        ),
        "final_source_feedback_context_confidence": round(
            float(final.get("source_feedback_context_confidence", 0.0)),
            5,
        ),
        "final_downstream_route_context_confidence": round(
            float(final.get("downstream_mean_route_context_confidence", 0.0)),
            5,
        ),
        "final_downstream_feedback_context_confidence": round(
            float(final.get("downstream_mean_feedback_context_confidence", 0.0)),
            5,
        ),
        "final_source_atp_ratio": round(float(final.get("source_atp_ratio", 0.0)), 5),
        "final_mean_bit_accuracy": round(float(final.get("mean_bit_accuracy", 0.0)), 5),
        "final_exact_matches": int(final.get("exact_matches", 0)),
    }


def _run_transfer_timeline(seed: int, train_scenario: str, transfer_scenario: str) -> dict[str, object]:
    training_system = _run_training(seed, train_scenario)

    base_dir = ROOT / "tests_tmp" / f"timecourse_{uuid.uuid4().hex}"
    full_dir = base_dir / "full"
    full_dir.mkdir(parents=True, exist_ok=True)
    try:
        training_system.save_memory_carryover(full_dir)

        variants = {}
        for label, warm in (("cold", False), ("warm_full", True)):
            system = build_system(seed, transfer_scenario)
            if warm:
                system.load_memory_carryover(full_dir)

            scenario = SCENARIOS[transfer_scenario]
            if scenario.initial_signal_specs:
                system.inject_signal_specs(scenario.initial_signal_specs)
            elif scenario.initial_packets > 0:
                system.inject_signal(count=scenario.initial_packets)

            records = []
            for cycle in range(1, scenario.cycles + 1):
                scheduled_specs = (scenario.signal_schedule_specs or {}).get(cycle)
                if scheduled_specs:
                    system.inject_signal_specs(scheduled_specs)
                else:
                    scheduled = scenario.packet_schedule.get(cycle, 0)
                    if scheduled > 0:
                        system.inject_signal(count=scheduled)
                report = system.run_global_cycle()
                summary = system.summarize()
                commitment = _runtime_commitment(system)
                branch_balance, branch_margin = _balance_signal(
                    commitment["branch_context_credit_total"],
                    commitment["branch_context_debt_total"],
                )
                context_branch_balance, context_branch_margin = _balance_signal(
                    commitment["context_branch_transform_credit_total"],
                    commitment["context_branch_transform_debt_total"],
                )
                combined_credit = (
                    commitment["branch_context_credit_total"]
                    + commitment["context_branch_transform_credit_total"]
                )
                combined_debt = (
                    commitment["branch_context_debt_total"]
                    + commitment["context_branch_transform_debt_total"]
                )
                combined_balance, combined_margin = _balance_signal(
                    combined_credit,
                    combined_debt,
                )
                selector_summary = _selector_cycle_summary(report["entries"])
                records.append(
                    {
                        "cycle": cycle,
                        "exact_matches": int(summary["exact_matches"]),
                        "mean_bit_accuracy": round(float(summary["mean_bit_accuracy"]), 5),
                        "wrong_transform_family": round(
                            _overall_stat(summary, "wrong_transform_family"),
                            5,
                        ),
                        "stale_context_support_suspicions": round(
                            _overall_stat(summary, "stale_context_support_suspicions"),
                            5,
                        ),
                        "context_1_mean_bit_accuracy": round(
                            _context_stat(summary, "context_1", "mean_bit_accuracy"),
                            5,
                        ),
                        "branch_context_credit_total": commitment["branch_context_credit_total"],
                        "branch_context_debt_total": commitment["branch_context_debt_total"],
                        "branch_context_balance_total": branch_balance,
                        "branch_context_balance_margin": branch_margin,
                        "context_branch_transform_credit_total": commitment[
                            "context_branch_transform_credit_total"
                        ],
                        "context_branch_transform_debt_total": commitment[
                            "context_branch_transform_debt_total"
                        ],
                        "context_branch_transform_balance_total": context_branch_balance,
                        "context_branch_transform_balance_margin": context_branch_margin,
                        "combined_context_balance_total": combined_balance,
                        "combined_context_balance_margin": combined_margin,
                        "route_count": selector_summary["route_count"],
                        "rest_count": selector_summary["rest_count"],
                        "invest_count": selector_summary["invest_count"],
                        "route_branch_counts": selector_summary["route_branch_counts"],
                        "route_transform_counts": selector_summary["route_transform_counts"],
                        "route_mode_counts": selector_summary["route_mode_counts"],
                        "branch_transform_counts": selector_summary["branch_transform_counts"],
                        "mean_route_coherence": selector_summary["mean_route_coherence"],
                        "mean_route_delta": selector_summary["mean_route_delta"],
                    }
                )
            variants[label] = {
                "timeline": records,
                "summary": _timeline_summary(records),
            }
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)

    return {
        "seed": seed,
        "train_scenario": train_scenario,
        "transfer_scenario": transfer_scenario,
        "cold": variants["cold"],
        "warm_full": variants["warm_full"],
    }


def _mean_or_none(values: list[float | int | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    if not present:
        return None
    return round(mean(present), 5)


def _scenario_specs(scenario_name: str, *, latent_context: bool):
    scenario = SCENARIOS[scenario_name]
    if latent_context:
        initial, schedule = latent_signal_specs(scenario_name)
        return scenario, initial, schedule
    return scenario, scenario.initial_signal_specs, scenario.signal_schedule_specs


def _run_task_timeline(
    seed: int,
    scenario_name: str,
    *,
    latent_context: bool,
    source_sequence_context_enabled: bool,
) -> dict[str, object]:
    scenario, initial_specs, schedule_specs = _scenario_specs(scenario_name, latent_context=latent_context)
    task_id_hint = _task_id_hint(initial_specs, schedule_specs)
    system = build_system(
        seed,
        scenario_name,
        source_sequence_context_enabled=source_sequence_context_enabled,
    )
    if initial_specs:
        system.inject_signal_specs(initial_specs)
    elif scenario.initial_packets > 0:
        system.inject_signal(count=scenario.initial_packets)

    records: list[dict[str, object]] = []
    prior_overall = {field: 0.0 for field in LATENT_DIAGNOSTIC_FIELDS}
    for cycle in range(1, scenario.cycles + 1):
        scheduled_specs = (schedule_specs or {}).get(cycle)
        if scheduled_specs:
            system.inject_signal_specs(scheduled_specs)
        else:
            scheduled = scenario.packet_schedule.get(cycle, 0)
            if scheduled > 0:
                system.inject_signal(count=scheduled)
        report = system.run_global_cycle()
        summary = system.summarize()
        selector_summary = _selector_cycle_summary(report["entries"])
        source_snapshot = _source_cycle_snapshot(system, task_id_hint=task_id_hint)
        downstream_snapshot = _downstream_tracker_snapshot(system, task_id_hint=task_id_hint)
        overall = dict(summary.get("task_diagnostics", {}).get("overall", {}))
        record: dict[str, object] = {
            "cycle": cycle,
            "exact_matches": int(summary["exact_matches"]),
            "mean_bit_accuracy": round(float(summary["mean_bit_accuracy"]), 5),
            "context_1_mean_bit_accuracy": round(
                _context_stat(summary, "context_1", "mean_bit_accuracy"),
                5,
            ),
            **source_snapshot,
            **downstream_snapshot,
            "route_count": selector_summary["route_count"],
            "rest_count": selector_summary["rest_count"],
            "invest_count": selector_summary["invest_count"],
            "route_branch_counts": selector_summary["route_branch_counts"],
            "route_transform_counts": selector_summary["route_transform_counts"],
            "route_mode_counts": selector_summary["route_mode_counts"],
            "branch_transform_counts": selector_summary["branch_transform_counts"],
            "mean_route_coherence": selector_summary["mean_route_coherence"],
            "mean_route_delta": selector_summary["mean_route_delta"],
        }
        for field in LATENT_DIAGNOSTIC_FIELDS:
            current_value = float(overall.get(field, 0.0))
            record[field] = round(current_value, 5)
            record[f"delta_{field}"] = round(max(0.0, current_value - prior_overall[field]), 5)
            prior_overall[field] = current_value
        records.append(record)

    return {
        "seed": seed,
        "scenario": scenario_name,
        "latent_context": latent_context,
        "source_sequence_context_enabled": source_sequence_context_enabled,
        "timeline": records,
        "summary": _latent_timeline_summary(records),
    }


def _run_latent_transfer_timeline(
    seed: int,
    train_scenario: str,
    transfer_scenario: str,
    *,
    source_sequence_context_enabled: bool,
    latent_transfer_split_enabled: bool,
) -> dict[str, object]:
    train_specs, train_schedule = latent_signal_specs(train_scenario)
    training = build_system(
        seed,
        train_scenario,
        source_sequence_context_enabled=source_sequence_context_enabled,
        latent_transfer_split_enabled=latent_transfer_split_enabled,
    )
    training_scenario = SCENARIOS[train_scenario]
    training.run_workload(
        cycles=training_scenario.cycles,
        initial_packets=training_scenario.initial_packets,
        packet_schedule=training_scenario.packet_schedule,
        initial_signal_specs=train_specs,
        signal_schedule_specs=train_schedule,
    )

    base_dir = ROOT / "tests_tmp" / f"latent_transfer_timecourse_{uuid.uuid4().hex}"
    carryover_dir = base_dir / "carryover"
    carryover_dir.mkdir(parents=True, exist_ok=True)
    try:
        training.save_memory_carryover(carryover_dir)

        transfer_specs, transfer_schedule = latent_signal_specs(transfer_scenario)
        transfer_task_id = _task_id_hint(transfer_specs, transfer_schedule)
        system = build_system(
            seed,
            transfer_scenario,
            source_sequence_context_enabled=source_sequence_context_enabled,
            latent_transfer_split_enabled=latent_transfer_split_enabled,
        )
        system.load_memory_carryover(carryover_dir)
        scenario = SCENARIOS[transfer_scenario]
        if transfer_specs:
            system.inject_signal_specs(transfer_specs)
        elif scenario.initial_packets > 0:
            system.inject_signal(count=scenario.initial_packets)

        records: list[dict[str, object]] = []
        prior_overall = {field: 0.0 for field in LATENT_DIAGNOSTIC_FIELDS}
        for cycle in range(1, scenario.cycles + 1):
            scheduled_specs = (transfer_schedule or {}).get(cycle)
            if scheduled_specs:
                system.inject_signal_specs(scheduled_specs)
            else:
                scheduled = scenario.packet_schedule.get(cycle, 0)
                if scheduled > 0:
                    system.inject_signal(count=scheduled)
            report = system.run_global_cycle()
            summary = system.summarize()
            selector_summary = _selector_cycle_summary(report["entries"])
            source_snapshot = _source_cycle_snapshot(system, task_id_hint=transfer_task_id)
            downstream_snapshot = _downstream_tracker_snapshot(system, task_id_hint=transfer_task_id)
            overall = dict(summary.get("task_diagnostics", {}).get("overall", {}))
            record: dict[str, object] = {
                "cycle": cycle,
                "exact_matches": int(summary["exact_matches"]),
                "mean_bit_accuracy": round(float(summary["mean_bit_accuracy"]), 5),
                "context_1_mean_bit_accuracy": round(
                    _context_stat(summary, "context_1", "mean_bit_accuracy"),
                    5,
                ),
                **source_snapshot,
                **downstream_snapshot,
                "route_count": selector_summary["route_count"],
                "rest_count": selector_summary["rest_count"],
                "invest_count": selector_summary["invest_count"],
                "route_branch_counts": selector_summary["route_branch_counts"],
                "route_transform_counts": selector_summary["route_transform_counts"],
                "route_mode_counts": selector_summary["route_mode_counts"],
                "branch_transform_counts": selector_summary["branch_transform_counts"],
                "mean_route_coherence": selector_summary["mean_route_coherence"],
                "mean_route_delta": selector_summary["mean_route_delta"],
            }
            for field in LATENT_DIAGNOSTIC_FIELDS:
                current_value = float(overall.get(field, 0.0))
                record[field] = round(current_value, 5)
                record[f"delta_{field}"] = round(max(0.0, current_value - prior_overall[field]), 5)
                prior_overall[field] = current_value
            records.append(record)
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)

    return {
        "seed": seed,
        "train_scenario": train_scenario,
        "transfer_scenario": transfer_scenario,
        "source_sequence_context_enabled": source_sequence_context_enabled,
        "latent_transfer_split_enabled": latent_transfer_split_enabled,
        "timeline": records,
        "summary": _latent_timeline_summary(records),
    }


def _aggregate_variant(records: list[dict[str, object]], label: str) -> dict[str, object]:
    per_cycle = []
    cycle_count = len(records[0][label]["timeline"]) if records else 0
    for index in range(cycle_count):
        cycle_records = [record[label]["timeline"][index] for record in records]
        per_cycle.append(
            {
                "cycle": int(cycle_records[0]["cycle"]),
                "mean_exact_matches": round(mean(item["exact_matches"] for item in cycle_records), 5),
                "mean_bit_accuracy": round(mean(item["mean_bit_accuracy"] for item in cycle_records), 5),
                "mean_context_1_bit_accuracy": round(
                    mean(item["context_1_mean_bit_accuracy"] for item in cycle_records),
                    5,
                ),
                "mean_wrong_transform_family": round(
                    mean(item["wrong_transform_family"] for item in cycle_records),
                    5,
                ),
                "mean_stale_context_support_suspicions": round(
                    mean(item["stale_context_support_suspicions"] for item in cycle_records),
                    5,
                ),
                "mean_branch_context_credit_total": round(
                    mean(item["branch_context_credit_total"] for item in cycle_records),
                    5,
                ),
                "mean_branch_context_debt_total": round(
                    mean(item["branch_context_debt_total"] for item in cycle_records),
                    5,
                ),
                "mean_branch_context_balance_total": round(
                    mean(item["branch_context_balance_total"] for item in cycle_records),
                    5,
                ),
                "mean_branch_context_balance_margin": round(
                    mean(item["branch_context_balance_margin"] for item in cycle_records),
                    5,
                ),
                "mean_context_branch_transform_credit_total": round(
                    mean(item["context_branch_transform_credit_total"] for item in cycle_records),
                    5,
                ),
                "mean_context_branch_transform_debt_total": round(
                    mean(item["context_branch_transform_debt_total"] for item in cycle_records),
                    5,
                ),
                "mean_context_branch_transform_balance_total": round(
                    mean(item["context_branch_transform_balance_total"] for item in cycle_records),
                    5,
                ),
                "mean_context_branch_transform_balance_margin": round(
                    mean(item["context_branch_transform_balance_margin"] for item in cycle_records),
                    5,
                ),
                "mean_combined_context_balance_total": round(
                    mean(item["combined_context_balance_total"] for item in cycle_records),
                    5,
                ),
                "mean_combined_context_balance_margin": round(
                    mean(item["combined_context_balance_margin"] for item in cycle_records),
                    5,
                ),
            }
        )

    summaries = [record[label]["summary"] for record in records]
    negative_cycle_records = [
        cycle_record
        for record in records
        for cycle_record in record[label]["timeline"]
        if float(cycle_record["combined_context_balance_total"]) < 0.0
    ]
    return {
        "timeline": per_cycle,
        "aggregate_summary": {
            "avg_peak_branch_context_debt_total": round(
                mean(item["peak_branch_context_debt_total"] for item in summaries),
                5,
            ),
            "avg_peak_branch_context_debt_cycle": _mean_or_none(
                [item["peak_branch_context_debt_cycle"] for item in summaries]
            ),
            "avg_branch_context_debt_auc": round(
                mean(item["branch_context_debt_auc"] for item in summaries),
                5,
            ),
            "avg_branch_context_half_relief_cycle": _mean_or_none(
                [item["branch_context_half_relief_cycle"] for item in summaries]
            ),
            "avg_peak_context_branch_transform_debt_total": round(
                mean(item["peak_context_branch_transform_debt_total"] for item in summaries),
                5,
            ),
            "avg_peak_context_branch_transform_debt_cycle": _mean_or_none(
                [item["peak_context_branch_transform_debt_cycle"] for item in summaries]
            ),
            "avg_context_branch_transform_debt_auc": round(
                mean(item["context_branch_transform_debt_auc"] for item in summaries),
                5,
            ),
            "avg_context_branch_transform_half_relief_cycle": _mean_or_none(
                [item["context_branch_transform_half_relief_cycle"] for item in summaries]
            ),
            "avg_combined_context_balance_auc": round(
                mean(item["combined_context_balance_auc"] for item in summaries),
                5,
            ),
            "avg_combined_context_balance_margin_auc": round(
                mean(item["combined_context_balance_margin_auc"] for item in summaries),
                5,
            ),
            "avg_min_combined_context_balance_total": round(
                mean(item["min_combined_context_balance_total"] for item in summaries),
                5,
            ),
            "avg_min_combined_context_balance_cycle": _mean_or_none(
                [item["min_combined_context_balance_cycle"] for item in summaries]
            ),
            "avg_min_combined_context_balance_margin": round(
                mean(item["min_combined_context_balance_margin"] for item in summaries),
                5,
            ),
            "avg_min_combined_context_balance_margin_cycle": _mean_or_none(
                [item["min_combined_context_balance_margin_cycle"] for item in summaries]
            ),
            "avg_negative_combined_balance_cycle_count": round(
                mean(item["negative_combined_balance_cycle_count"] for item in summaries),
                5,
            ),
            "avg_first_negative_combined_balance_cycle": _mean_or_none(
                [item["first_negative_combined_balance_cycle"] for item in summaries]
            ),
            "avg_last_negative_combined_balance_cycle": _mean_or_none(
                [item["last_negative_combined_balance_cycle"] for item in summaries]
            ),
            "avg_first_positive_combined_balance_cycle": _mean_or_none(
                [item["first_positive_combined_balance_cycle"] for item in summaries]
            ),
            "avg_first_strong_combined_balance_cycle": _mean_or_none(
                [item["first_strong_combined_balance_cycle"] for item in summaries]
            ),
            "avg_final_branch_context_debt_total": round(
                mean(item["final_branch_context_debt_total"] for item in summaries),
                5,
            ),
            "avg_final_context_branch_transform_debt_total": round(
                mean(item["final_context_branch_transform_debt_total"] for item in summaries),
                5,
            ),
            "avg_final_branch_context_credit_total": round(
                mean(item["final_branch_context_credit_total"] for item in summaries),
                5,
            ),
            "avg_final_context_branch_transform_credit_total": round(
                mean(item["final_context_branch_transform_credit_total"] for item in summaries),
                5,
            ),
            "avg_final_combined_context_balance_total": round(
                mean(item["final_combined_context_balance_total"] for item in summaries),
                5,
            ),
            "avg_final_combined_context_balance_margin": round(
                mean(item["final_combined_context_balance_margin"] for item in summaries),
                5,
            ),
            "avg_final_mean_bit_accuracy": round(
                mean(item["final_mean_bit_accuracy"] for item in summaries),
                5,
            ),
            "avg_final_exact_matches": round(
                mean(item["final_exact_matches"] for item in summaries),
                5,
            ),
        },
        "negative_balance_selector_summary": _aggregate_selector_window(negative_cycle_records),
    }


def _aggregate_latent_variant(records: list[dict[str, object]]) -> dict[str, object]:
    per_cycle = []
    cycle_count = len(records[0]["timeline"]) if records else 0
    for index in range(cycle_count):
        cycle_records = [record["timeline"][index] for record in records]
        per_cycle.append(
            {
                "cycle": int(cycle_records[0]["cycle"]),
                "mean_exact_matches": round(mean(float(item["exact_matches"]) for item in cycle_records), 5),
                "mean_bit_accuracy": round(mean(float(item["mean_bit_accuracy"]) for item in cycle_records), 5),
                "mean_latent_context_confidence": round(
                    mean(float(item["latent_context_confidence"]) for item in cycle_records),
                    5,
                ),
                "mean_effective_context_confidence": round(
                    mean(float(item["effective_context_confidence"]) for item in cycle_records),
                    5,
                ),
                "mean_effective_has_context": round(
                    mean(float(item["effective_has_context"]) for item in cycle_records),
                    5,
                ),
                "mean_source_sequence_context_confidence": round(
                    mean(float(item["source_sequence_context_confidence"]) for item in cycle_records),
                    5,
                ),
                "mean_source_route_context_confidence": round(
                    mean(float(item["source_route_context_confidence"]) for item in cycle_records),
                    5,
                ),
                "mean_source_feedback_context_confidence": round(
                    mean(float(item["source_feedback_context_confidence"]) for item in cycle_records),
                    5,
                ),
                "mean_downstream_route_context_confidence": round(
                    mean(float(item["downstream_mean_route_context_confidence"]) for item in cycle_records),
                    5,
                ),
                "mean_downstream_feedback_context_confidence": round(
                    mean(float(item["downstream_mean_feedback_context_confidence"]) for item in cycle_records),
                    5,
                ),
                "mean_source_atp_ratio": round(
                    mean(float(item["source_atp_ratio"]) for item in cycle_records),
                    5,
                ),
                "mean_wrong_transform_family": round(
                    mean(float(item["wrong_transform_family"]) for item in cycle_records),
                    5,
                ),
                "mean_delta_wrong_transform_family": round(
                    mean(float(item["delta_wrong_transform_family"]) for item in cycle_records),
                    5,
                ),
                "mean_delta_transform_unstable": round(
                    mean(
                        float(
                            item["delta_transform_unstable_across_inferred_context_boundary"]
                        )
                        for item in cycle_records
                    ),
                    5,
                ),
                "mean_delta_delayed_correction": round(
                    mean(float(item["delta_delayed_correction"]) for item in cycle_records),
                    5,
                ),
            }
        )

    summaries = [record["summary"] for record in records]
    low_confidence_cycle_records = [
        cycle_record
        for record in records
        for cycle_record in record["timeline"]
        if float(cycle_record["latent_context_available"]) >= 0.5
        and float(cycle_record["effective_has_context"]) < 0.5
    ]
    instability_cycle_records = [
        cycle_record
        for record in records
        for cycle_record in record["timeline"]
        if float(cycle_record["delta_transform_unstable_across_inferred_context_boundary"]) > 0.0
    ]
    pre_effective_cycle_records = [
        cycle_record
        for record in records
        for cycle_record in record["timeline"]
        if float(cycle_record["effective_has_context"]) < 0.5
    ]
    return {
        "timeline": per_cycle,
        "aggregate_summary": {
            "avg_first_latent_context_available_cycle": _mean_or_none(
                [item["first_latent_context_available_cycle"] for item in summaries]
            ),
            "avg_first_effective_context_cycle": _mean_or_none(
                [item["first_effective_context_cycle"] for item in summaries]
            ),
            "avg_first_context_promotion_ready_cycle": _mean_or_none(
                [item["first_context_promotion_ready_cycle"] for item in summaries]
            ),
            "avg_peak_latent_context_confidence": round(
                mean(float(item["peak_latent_context_confidence"]) for item in summaries),
                5,
            ),
            "avg_peak_latent_context_confidence_cycle": _mean_or_none(
                [item["peak_latent_context_confidence_cycle"] for item in summaries]
            ),
            "avg_latent_context_confidence": round(
                mean(float(item["avg_latent_context_confidence"]) for item in summaries),
                5,
            ),
            "avg_effective_context_confidence": round(
                mean(float(item["avg_effective_context_confidence"]) for item in summaries),
                5,
            ),
            "avg_source_sequence_context_confidence": round(
                mean(float(item["avg_source_sequence_context_confidence"]) for item in summaries),
                5,
            ),
            "avg_source_route_context_confidence": round(
                mean(float(item["avg_source_route_context_confidence"]) for item in summaries),
                5,
            ),
            "avg_source_feedback_context_confidence": round(
                mean(float(item["avg_source_feedback_context_confidence"]) for item in summaries),
                5,
            ),
            "avg_downstream_route_context_confidence": round(
                mean(float(item["avg_downstream_route_context_confidence"]) for item in summaries),
                5,
            ),
            "avg_downstream_feedback_context_confidence": round(
                mean(float(item["avg_downstream_feedback_context_confidence"]) for item in summaries),
                5,
            ),
            "avg_source_atp_ratio": round(
                mean(float(item["avg_source_atp_ratio"]) for item in summaries),
                5,
            ),
            "avg_low_confidence_cycle_count": round(
                mean(float(item["low_confidence_cycle_count"]) for item in summaries),
                5,
            ),
            "avg_pre_effective_context_cycle_count": round(
                mean(float(item["pre_effective_context_cycle_count"]) for item in summaries),
                5,
            ),
            "avg_pre_effective_wrong_transform_events": round(
                mean(float(item["pre_effective_wrong_transform_events"]) for item in summaries),
                5,
            ),
            "avg_pre_effective_instability_events": round(
                mean(float(item["pre_effective_instability_events"]) for item in summaries),
                5,
            ),
            "avg_instability_event_count": round(
                mean(float(item["instability_event_count"]) for item in summaries),
                5,
            ),
            "avg_wrong_transform_event_count": round(
                mean(float(item["wrong_transform_event_count"]) for item in summaries),
                5,
            ),
            "avg_delayed_correction_event_count": round(
                mean(float(item["delayed_correction_event_count"]) for item in summaries),
                5,
            ),
            "avg_route_wrong_transform_potentially_right_event_count": round(
                mean(float(item["route_wrong_transform_potentially_right_event_count"]) for item in summaries),
                5,
            ),
            "avg_route_right_transform_wrong_event_count": round(
                mean(float(item["route_right_transform_wrong_event_count"]) for item in summaries),
                5,
            ),
            "avg_final_latent_context_confidence": round(
                mean(float(item["final_latent_context_confidence"]) for item in summaries),
                5,
            ),
            "avg_final_effective_context_confidence": round(
                mean(float(item["final_effective_context_confidence"]) for item in summaries),
                5,
            ),
            "avg_final_source_sequence_context_confidence": round(
                mean(float(item["final_source_sequence_context_confidence"]) for item in summaries),
                5,
            ),
            "avg_final_source_route_context_confidence": round(
                mean(float(item["final_source_route_context_confidence"]) for item in summaries),
                5,
            ),
            "avg_final_source_feedback_context_confidence": round(
                mean(float(item["final_source_feedback_context_confidence"]) for item in summaries),
                5,
            ),
            "avg_final_downstream_route_context_confidence": round(
                mean(float(item["final_downstream_route_context_confidence"]) for item in summaries),
                5,
            ),
            "avg_final_downstream_feedback_context_confidence": round(
                mean(float(item["final_downstream_feedback_context_confidence"]) for item in summaries),
                5,
            ),
            "avg_final_source_atp_ratio": round(
                mean(float(item["final_source_atp_ratio"]) for item in summaries),
                5,
            ),
            "avg_final_mean_bit_accuracy": round(
                mean(float(item["final_mean_bit_accuracy"]) for item in summaries),
                5,
            ),
            "avg_final_exact_matches": round(
                mean(float(item["final_exact_matches"]) for item in summaries),
                5,
            ),
        },
        "low_confidence_selector_summary": _aggregate_selector_window(low_confidence_cycle_records),
        "instability_selector_summary": _aggregate_selector_window(instability_cycle_records),
        "pre_effective_selector_summary": _aggregate_selector_window(pre_effective_cycle_records),
    }


def analyze_transfer_timecourse(*, seeds: tuple[int, ...] = DEFAULT_SEEDS) -> dict[str, object]:
    a_to_b = [_run_transfer_timeline(seed, TASK_A, TASK_B) for seed in seeds]
    b_to_a = [_run_transfer_timeline(seed, TASK_B, TASK_A) for seed in seeds]

    aggregate_a_to_b_cold = _aggregate_variant(a_to_b, "cold")
    aggregate_a_to_b_warm = _aggregate_variant(a_to_b, "warm_full")
    aggregate_b_to_a_cold = _aggregate_variant(b_to_a, "cold")
    aggregate_b_to_a_warm = _aggregate_variant(b_to_a, "warm_full")

    return {
        "seeds": list(seeds),
        "pairs": {
            f"{TASK_A}->{TASK_B}": {
                "cold": aggregate_a_to_b_cold,
                "warm_full": aggregate_a_to_b_warm,
                "results": a_to_b,
            },
            f"{TASK_B}->{TASK_A}": {
                "cold": aggregate_b_to_a_cold,
                "warm_full": aggregate_b_to_a_warm,
                "results": b_to_a,
            },
        },
        "warm_full_delta_b_to_a_minus_a_to_b": {
            "avg_peak_branch_context_debt_total": round(
                aggregate_b_to_a_warm["aggregate_summary"]["avg_peak_branch_context_debt_total"]
                - aggregate_a_to_b_warm["aggregate_summary"]["avg_peak_branch_context_debt_total"],
                5,
            ),
            "avg_branch_context_debt_auc": round(
                aggregate_b_to_a_warm["aggregate_summary"]["avg_branch_context_debt_auc"]
                - aggregate_a_to_b_warm["aggregate_summary"]["avg_branch_context_debt_auc"],
                5,
            ),
            "avg_branch_context_half_relief_cycle": (
                None
                if aggregate_b_to_a_warm["aggregate_summary"]["avg_branch_context_half_relief_cycle"] is None
                or aggregate_a_to_b_warm["aggregate_summary"]["avg_branch_context_half_relief_cycle"] is None
                else round(
                    aggregate_b_to_a_warm["aggregate_summary"]["avg_branch_context_half_relief_cycle"]
                    - aggregate_a_to_b_warm["aggregate_summary"]["avg_branch_context_half_relief_cycle"],
                    5,
                )
            ),
            "avg_peak_context_branch_transform_debt_total": round(
                aggregate_b_to_a_warm["aggregate_summary"]["avg_peak_context_branch_transform_debt_total"]
                - aggregate_a_to_b_warm["aggregate_summary"]["avg_peak_context_branch_transform_debt_total"],
                5,
            ),
            "avg_context_branch_transform_debt_auc": round(
                aggregate_b_to_a_warm["aggregate_summary"]["avg_context_branch_transform_debt_auc"]
                - aggregate_a_to_b_warm["aggregate_summary"]["avg_context_branch_transform_debt_auc"],
                5,
            ),
            "avg_context_branch_transform_half_relief_cycle": (
                None
                if aggregate_b_to_a_warm["aggregate_summary"]["avg_context_branch_transform_half_relief_cycle"] is None
                or aggregate_a_to_b_warm["aggregate_summary"]["avg_context_branch_transform_half_relief_cycle"] is None
                else round(
                    aggregate_b_to_a_warm["aggregate_summary"]["avg_context_branch_transform_half_relief_cycle"]
                    - aggregate_a_to_b_warm["aggregate_summary"]["avg_context_branch_transform_half_relief_cycle"],
                    5,
                )
            ),
            "avg_combined_context_balance_auc": round(
                aggregate_b_to_a_warm["aggregate_summary"]["avg_combined_context_balance_auc"]
                - aggregate_a_to_b_warm["aggregate_summary"]["avg_combined_context_balance_auc"],
                5,
            ),
            "avg_combined_context_balance_margin_auc": round(
                aggregate_b_to_a_warm["aggregate_summary"]["avg_combined_context_balance_margin_auc"]
                - aggregate_a_to_b_warm["aggregate_summary"]["avg_combined_context_balance_margin_auc"],
                5,
            ),
            "avg_negative_combined_balance_cycle_count": round(
                aggregate_b_to_a_warm["aggregate_summary"]["avg_negative_combined_balance_cycle_count"]
                - aggregate_a_to_b_warm["aggregate_summary"]["avg_negative_combined_balance_cycle_count"],
                5,
            ),
            "avg_first_strong_combined_balance_cycle": (
                None
                if aggregate_b_to_a_warm["aggregate_summary"]["avg_first_strong_combined_balance_cycle"] is None
                or aggregate_a_to_b_warm["aggregate_summary"]["avg_first_strong_combined_balance_cycle"] is None
                else round(
                    aggregate_b_to_a_warm["aggregate_summary"]["avg_first_strong_combined_balance_cycle"]
                    - aggregate_a_to_b_warm["aggregate_summary"]["avg_first_strong_combined_balance_cycle"],
                    5,
                )
            ),
            "avg_final_combined_context_balance_total": round(
                aggregate_b_to_a_warm["aggregate_summary"]["avg_final_combined_context_balance_total"]
                - aggregate_a_to_b_warm["aggregate_summary"]["avg_final_combined_context_balance_total"],
                5,
            ),
            "avg_final_combined_context_balance_margin": round(
                aggregate_b_to_a_warm["aggregate_summary"]["avg_final_combined_context_balance_margin"]
                - aggregate_a_to_b_warm["aggregate_summary"]["avg_final_combined_context_balance_margin"],
                5,
            ),
            "avg_final_mean_bit_accuracy": round(
                aggregate_b_to_a_warm["aggregate_summary"]["avg_final_mean_bit_accuracy"]
                - aggregate_a_to_b_warm["aggregate_summary"]["avg_final_mean_bit_accuracy"],
                5,
            ),
            "avg_final_exact_matches": round(
                aggregate_b_to_a_warm["aggregate_summary"]["avg_final_exact_matches"]
                - aggregate_a_to_b_warm["aggregate_summary"]["avg_final_exact_matches"],
                5,
            ),
        },
    }


def analyze_latent_context_timecourse(
    *,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    scenario_names: tuple[str, ...] = (TASK_A, TASK_B),
) -> dict[str, object]:
    scenarios: dict[str, object] = {}
    for scenario_name in scenario_names:
        visible = [
            _run_task_timeline(
                seed,
                scenario_name,
                latent_context=False,
                source_sequence_context_enabled=True,
            )
            for seed in seeds
        ]
        latent_no_source = [
            _run_task_timeline(
                seed,
                scenario_name,
                latent_context=True,
                source_sequence_context_enabled=False,
            )
            for seed in seeds
        ]
        latent_with_source = [
            _run_task_timeline(
                seed,
                scenario_name,
                latent_context=True,
                source_sequence_context_enabled=True,
            )
            for seed in seeds
        ]
        visible_aggregate = _aggregate_latent_variant(visible)
        latent_no_source_aggregate = _aggregate_latent_variant(latent_no_source)
        latent_with_source_aggregate = _aggregate_latent_variant(latent_with_source)
        scenarios[scenario_name] = {
            "visible": visible_aggregate,
            "latent_no_source_sequence": latent_no_source_aggregate,
            "latent_with_source_sequence": latent_with_source_aggregate,
            "latent_source_sequence_delta": {
                "avg_final_mean_bit_accuracy": round(
                    latent_with_source_aggregate["aggregate_summary"]["avg_final_mean_bit_accuracy"]
                    - latent_no_source_aggregate["aggregate_summary"]["avg_final_mean_bit_accuracy"],
                    5,
                ),
                "avg_final_exact_matches": round(
                    latent_with_source_aggregate["aggregate_summary"]["avg_final_exact_matches"]
                    - latent_no_source_aggregate["aggregate_summary"]["avg_final_exact_matches"],
                    5,
                ),
                "avg_first_effective_context_cycle": (
                    None
                    if latent_with_source_aggregate["aggregate_summary"]["avg_first_effective_context_cycle"] is None
                    or latent_no_source_aggregate["aggregate_summary"]["avg_first_effective_context_cycle"] is None
                    else round(
                        latent_with_source_aggregate["aggregate_summary"]["avg_first_effective_context_cycle"]
                        - latent_no_source_aggregate["aggregate_summary"]["avg_first_effective_context_cycle"],
                        5,
                    )
                ),
                "avg_low_confidence_cycle_count": round(
                    latent_with_source_aggregate["aggregate_summary"]["avg_low_confidence_cycle_count"]
                    - latent_no_source_aggregate["aggregate_summary"]["avg_low_confidence_cycle_count"],
                    5,
                ),
                "avg_pre_effective_instability_events": round(
                    latent_with_source_aggregate["aggregate_summary"]["avg_pre_effective_instability_events"]
                    - latent_no_source_aggregate["aggregate_summary"]["avg_pre_effective_instability_events"],
                    5,
                ),
                "avg_instability_event_count": round(
                    latent_with_source_aggregate["aggregate_summary"]["avg_instability_event_count"]
                    - latent_no_source_aggregate["aggregate_summary"]["avg_instability_event_count"],
                    5,
                ),
                "avg_wrong_transform_event_count": round(
                    latent_with_source_aggregate["aggregate_summary"]["avg_wrong_transform_event_count"]
                    - latent_no_source_aggregate["aggregate_summary"]["avg_wrong_transform_event_count"],
                    5,
                ),
            },
            "results": {
                "visible": visible,
                "latent_no_source_sequence": latent_no_source,
                "latent_with_source_sequence": latent_with_source,
            },
        }
    return {
        "seeds": list(seeds),
        "scenarios": scenarios,
    }


def analyze_latent_transfer_split_timecourse(
    *,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    train_scenario: str = TASK_A,
    transfer_scenario: str = TASK_B,
    source_sequence_context_enabled: bool = True,
) -> dict[str, object]:
    split_disabled = [
        _run_latent_transfer_timeline(
            seed,
            train_scenario,
            transfer_scenario,
            source_sequence_context_enabled=source_sequence_context_enabled,
            latent_transfer_split_enabled=False,
        )
        for seed in seeds
    ]
    split_enabled = [
        _run_latent_transfer_timeline(
            seed,
            train_scenario,
            transfer_scenario,
            source_sequence_context_enabled=source_sequence_context_enabled,
            latent_transfer_split_enabled=True,
        )
        for seed in seeds
    ]
    disabled_aggregate = _aggregate_latent_variant(split_disabled)
    enabled_aggregate = _aggregate_latent_variant(split_enabled)
    disabled_summary = disabled_aggregate["aggregate_summary"]
    enabled_summary = enabled_aggregate["aggregate_summary"]
    return {
        "seeds": list(seeds),
        "train_scenario": train_scenario,
        "transfer_scenario": transfer_scenario,
        "source_sequence_context_enabled": source_sequence_context_enabled,
        "split_disabled": disabled_aggregate,
        "split_enabled": enabled_aggregate,
        "split_delta_enabled_minus_disabled": {
            "avg_final_mean_bit_accuracy": round(
                enabled_summary["avg_final_mean_bit_accuracy"]
                - disabled_summary["avg_final_mean_bit_accuracy"],
                5,
            ),
            "avg_final_exact_matches": round(
                enabled_summary["avg_final_exact_matches"]
                - disabled_summary["avg_final_exact_matches"],
                5,
            ),
            "avg_first_effective_context_cycle": (
                None
                if enabled_summary["avg_first_effective_context_cycle"] is None
                or disabled_summary["avg_first_effective_context_cycle"] is None
                else round(
                    enabled_summary["avg_first_effective_context_cycle"]
                    - disabled_summary["avg_first_effective_context_cycle"],
                    5,
                )
            ),
            "avg_low_confidence_cycle_count": round(
                enabled_summary["avg_low_confidence_cycle_count"]
                - disabled_summary["avg_low_confidence_cycle_count"],
                5,
            ),
            "avg_pre_effective_context_cycle_count": round(
                enabled_summary["avg_pre_effective_context_cycle_count"]
                - disabled_summary["avg_pre_effective_context_cycle_count"],
                5,
            ),
            "avg_pre_effective_instability_events": round(
                enabled_summary["avg_pre_effective_instability_events"]
                - disabled_summary["avg_pre_effective_instability_events"],
                5,
            ),
            "avg_final_effective_context_confidence": round(
                enabled_summary["avg_final_effective_context_confidence"]
                - disabled_summary["avg_final_effective_context_confidence"],
                5,
            ),
            "avg_final_source_route_context_confidence": round(
                enabled_summary["avg_final_source_route_context_confidence"]
                - disabled_summary["avg_final_source_route_context_confidence"],
                5,
            ),
            "avg_final_source_feedback_context_confidence": round(
                enabled_summary["avg_final_source_feedback_context_confidence"]
                - disabled_summary["avg_final_source_feedback_context_confidence"],
                5,
            ),
        },
        "results": {
            "split_disabled": split_disabled,
            "split_enabled": split_enabled,
        },
    }


def main() -> None:
    print(
        json.dumps(
            {
                "transfer_timecourse": analyze_transfer_timecourse(),
                "latent_context_timecourse": analyze_latent_context_timecourse(),
                "latent_transfer_split_timecourse": analyze_latent_transfer_split_timecourse(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

