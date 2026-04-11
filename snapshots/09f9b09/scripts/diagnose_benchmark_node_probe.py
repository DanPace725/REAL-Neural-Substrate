from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Dict, List, Sequence

from phase8 import NativeSubstrateSystem
from phase8.environment import _expected_transform_for_task
from scripts.ceiling_benchmark_suite import benchmark_suite_by_id
from scripts.compare_morphogenesis import benchmark_morphogenesis_config
from scripts.experiment_manifest import build_run_manifest, write_run_manifest


def _route_neighbor(action: str | None) -> str | None:
    action = str(action or "")
    if action.startswith("route_transform:"):
        parts = action.split(":")
        if len(parts) == 3:
            return parts[1]
        return None
    if action.startswith("route:"):
        return action.split(":", 1)[1]
    return None


def _route_transform(action: str | None) -> str | None:
    action = str(action or "")
    if action.startswith("route_transform:"):
        parts = action.split(":")
        if len(parts) == 3:
            return parts[2]
    if action.startswith("route:"):
        return "identity"
    return None


def _method_flags(method_id: str) -> tuple[bool, bool]:
    latent = method_id in {"fixed-latent", "growth-latent"}
    morphogenesis = method_id in {"growth-visible", "growth-latent", "self-selected"}
    return latent, morphogenesis


def _task_spec(point, task_key: str, *, method_id: str):
    task = point.tasks[task_key]
    if method_id == "self-selected":
        return task.visible_scenario
    if method_id in {"fixed-latent", "growth-latent"}:
        return task.latent_scenario
    return task.visible_scenario


def _build_system_from_spec(seed: int, spec, *, method_id: str) -> NativeSubstrateSystem:
    _, morphogenesis = _method_flags(method_id)
    morphogenesis_config = benchmark_morphogenesis_config() if morphogenesis else None
    return NativeSubstrateSystem(
        adjacency=spec.adjacency,
        positions=spec.positions,
        source_id=spec.source_id,
        sink_id=spec.sink_id,
        selector_seed=seed,
        packet_ttl=spec.packet_ttl,
        source_admission_policy=spec.source_admission_policy,
        source_admission_rate=spec.source_admission_rate,
        source_admission_min_rate=spec.source_admission_min_rate,
        source_admission_max_rate=spec.source_admission_max_rate,
        morphogenesis_config=morphogenesis_config,
        capability_policy=method_id,
    )


def _inject_for_cycle(system: NativeSubstrateSystem, spec, cycle: int) -> None:
    scheduled_specs = dict(spec.signal_schedule_specs or {}).get(cycle)
    if scheduled_specs:
        system.inject_signal_specs(scheduled_specs)
        return
    scheduled = dict(spec.packet_schedule or {}).get(cycle, 0)
    if scheduled > 0:
        system.inject_signal(count=scheduled)


def _task_id_from_spec(spec, fallback_task_key: str) -> str:
    if spec.initial_signal_specs:
        first = spec.initial_signal_specs[0]
        if getattr(first, "task_id", None):
            return str(first.task_id)
    for scheduled_specs in dict(spec.signal_schedule_specs or {}).values():
        if scheduled_specs:
            first = scheduled_specs[0]
            if getattr(first, "task_id", None):
                return str(first.task_id)
    return str(fallback_task_key)


def _default_focus_nodes(system: NativeSubstrateSystem, *, max_downstream_nodes: int = 3) -> List[str]:
    env = system.environment
    source_id = env.source_id
    sink_id = env.sink_id
    downstream = [
        node_id
        for node_id in sorted(env.node_states, key=lambda current: env.positions[current])
        if node_id not in {source_id, sink_id}
    ]
    return [source_id] + downstream[:max_downstream_nodes]


def _node_cycle_record(
    system: NativeSubstrateSystem,
    report: dict[str, object],
    *,
    cycle: int,
    node_id: str,
    task_id: str,
) -> dict[str, object]:
    env = system.environment
    observation = env.observe_local(node_id)
    focus_packet = env._capability_focus_packet(node_id)
    focus_task_id = focus_packet.task_id if focus_packet is not None else task_id
    focus_latent_snapshot = env._latent_snapshot(
        node_id,
        focus_task_id,
        observe=False,
        packet_id=focus_packet.packet_id if focus_packet is not None else None,
        input_bits=focus_packet.input_bits if focus_packet is not None else None,
    )
    growth_specs = system.environment.growth_action_specs(node_id)
    bud_specs = [spec for spec in growth_specs if str(spec.get("action", "")).startswith("bud_")]
    entry = dict(report.get("entries", {})).get(node_id)
    action = str(entry.action) if entry is not None else ""
    state_before = dict(entry.state_before) if entry is not None else {}
    prediction = entry.prediction if entry is not None else None
    prediction_error = entry.prediction_error if entry is not None else None
    chosen_transform = _route_transform(action)
    chosen_neighbor = _route_neighbor(action)
    effective_context_bit = (
        int(observation.get("effective_context_bit", 0.0))
        if float(observation.get("effective_has_context", 0.0)) >= 0.5
        else None
    )
    latent_estimate = (
        int(observation.get("latent_context_estimate", 0.0))
        if float(observation.get("latent_context_available", 0.0)) >= 0.5
        else None
    )
    expected_context = effective_context_bit if effective_context_bit is not None else latent_estimate
    expected_transform = _expected_transform_for_task(task_id, expected_context)
    route_transform_match = None
    if chosen_transform is not None and expected_transform is not None:
        route_transform_match = 1.0 if chosen_transform == expected_transform else 0.0
    prediction_expected_outcome = (
        dict(prediction.expected_outcome)
        if prediction is not None
        else {}
    )
    if node_id == env.source_id:
        has_packet = 1.0 if focus_packet is not None else 0.0
        head_has_task = 1.0 if focus_packet is not None and focus_packet.task_id is not None else 0.0
        head_has_context = (
            1.0
            if focus_packet is not None
            and focus_packet.context_bit is not None
            and env._visible_context_exposed(node_id, focus_packet)
            else 0.0
        )
        latent_context_available = 1.0 if focus_latent_snapshot.get("available") else 0.0
        latent_context_estimate = focus_latent_snapshot.get("estimate")
        latent_context_confidence = round(float(focus_latent_snapshot.get("confidence", 0.0)), 5)
        source_sequence_available = 1.0 if focus_latent_snapshot.get("sequence_available") else 0.0
        source_sequence_context_estimate = focus_latent_snapshot.get("sequence_context_estimate")
        source_sequence_context_confidence = round(
            float(focus_latent_snapshot.get("sequence_context_confidence", 0.0)),
            5,
        )
    else:
        has_packet = float(observation.get("has_packet", 0.0))
        head_has_task = float(observation.get("head_has_task", 0.0))
        head_has_context = float(observation.get("head_has_context", 0.0))
        latent_context_available = float(observation.get("latent_context_available", 0.0))
        latent_context_estimate = latent_estimate
        latent_context_confidence = round(float(observation.get("latent_context_confidence", 0.0)), 5)
        source_sequence_available = float(observation.get("source_sequence_available", 0.0))
        source_sequence_context_estimate = (
            int(observation.get("source_sequence_context_estimate", 0.0))
            if float(observation.get("source_sequence_available", 0.0)) >= 0.5
            else None
        )
        source_sequence_context_confidence = round(
            float(observation.get("source_sequence_context_confidence", 0.0)),
            5,
        )
    return {
        "cycle": cycle,
        "node_id": node_id,
        "has_packet": has_packet,
        "head_has_task": head_has_task,
        "head_has_context": head_has_context,
        "pre_has_packet": float(state_before.get("has_packet", 0.0)),
        "pre_head_has_task": float(state_before.get("head_has_task", 0.0)),
        "pre_head_has_context": float(state_before.get("head_has_context", 0.0)),
        "latent_context_available": latent_context_available,
        "latent_context_estimate": latent_context_estimate,
        "latent_context_confidence": latent_context_confidence,
        "pre_latent_context_available": float(state_before.get("latent_context_available", 0.0)),
        "pre_latent_context_confidence": round(float(state_before.get("latent_context_confidence", 0.0)), 5),
        "pre_latent_context_estimate": (
            int(state_before.get("latent_context_estimate", 0.0))
            if float(state_before.get("latent_context_available", 0.0)) >= 0.5
            else None
        ),
        "effective_has_context": float(observation.get("effective_has_context", 0.0)),
        "effective_context_bit": effective_context_bit,
        "effective_context_confidence": round(float(observation.get("effective_context_confidence", 0.0)), 5),
        "pre_effective_has_context": float(state_before.get("effective_has_context", 0.0)),
        "pre_effective_context_confidence": round(float(state_before.get("effective_context_confidence", 0.0)), 5),
        "context_promotion_ready": float(observation.get("context_promotion_ready", 0.0)),
        "context_growth_ready": float(observation.get("context_growth_ready", 0.0)),
        "recent_latent_task_active": float(observation.get("recent_latent_task_active", 0.0)),
        "recent_latent_task_age": round(float(observation.get("recent_latent_task_age", 0.0)), 5),
        "recent_latent_context_confidence": round(
            float(observation.get("recent_latent_context_confidence", 0.0)),
            5,
        ),
        "visible_context_trust": round(float(observation.get("visible_context_trust", 0.0)), 5),
        "latent_recruitment_pressure": round(float(observation.get("latent_recruitment_pressure", 0.0)), 5),
        "latent_capability_support": round(float(observation.get("latent_capability_support", 0.0)), 5),
        "latent_capability_enabled": float(observation.get("latent_capability_enabled", 0.0)),
        "growth_recruitment_pressure": round(float(observation.get("growth_recruitment_pressure", 0.0)), 5),
        "growth_capability_support": round(float(observation.get("growth_capability_support", 0.0)), 5),
        "growth_capability_enabled": float(observation.get("growth_capability_enabled", 0.0)),
        "growth_stabilization_readiness": round(float(observation.get("growth_stabilization_readiness", 0.0)), 5),
        "source_sequence_available": source_sequence_available,
        "source_sequence_context_estimate": source_sequence_context_estimate,
        "source_sequence_context_confidence": source_sequence_context_confidence,
        "pre_source_sequence_available": float(state_before.get("source_sequence_available", 0.0)),
        "pre_source_sequence_context_estimate": (
            int(state_before.get("source_sequence_context_estimate", 0.0))
            if float(state_before.get("source_sequence_available", 0.0)) >= 0.5
            else None
        ),
        "pre_source_sequence_context_confidence": round(
            float(state_before.get("source_sequence_context_confidence", 0.0)),
            5,
        ),
        "source_sequence_change_ratio": round(float(observation.get("source_sequence_change_ratio", 0.0)), 5),
        "source_sequence_repeat_input": round(float(observation.get("source_sequence_repeat_input", 0.0)), 5),
        "contradiction_pressure": round(float(observation.get("contradiction_pressure", 0.0)), 5),
        "queue_pressure": round(float(observation.get("queue_pressure", 0.0)), 5),
        "ingress_backlog": round(float(observation.get("ingress_backlog", 0.0)), 5),
        "oldest_packet_age": round(float(observation.get("oldest_packet_age", 0.0)), 5),
        "atp_ratio": round(float(observation.get("atp_ratio", 0.0)), 5),
        "reward_buffer": round(float(observation.get("reward_buffer", 0.0)), 5),
        "history_transform_evidence": {
            name: round(float(observation.get(f"history_transform_evidence_{name}", 0.0)), 5)
            for name in ("identity", "rotate_left_1", "xor_mask_1010", "xor_mask_0101")
        },
        "task_transform_affinity": {
            name: round(float(observation.get(f"task_transform_affinity_{name}", 0.0)), 5)
            for name in ("identity", "rotate_left_1", "xor_mask_1010", "xor_mask_0101")
        },
        "pre_task_transform_affinity": {
            name: round(float(state_before.get(f"task_transform_affinity_{name}", 0.0)), 5)
            for name in ("identity", "rotate_left_1", "xor_mask_1010", "xor_mask_0101")
        },
        "source_sequence_transform_hint": {
            name: round(float(observation.get(f"source_sequence_transform_hint_{name}", 0.0)), 5)
            for name in ("identity", "rotate_left_1", "xor_mask_1010", "xor_mask_0101")
        },
        "pre_source_sequence_transform_hint": {
            name: round(float(state_before.get(f"source_sequence_transform_hint_{name}", 0.0)), 5)
            for name in ("identity", "rotate_left_1", "xor_mask_1010", "xor_mask_0101")
        },
        "growth_candidate_action_count": len(growth_specs),
        "bud_action_available_count": len(bud_specs),
        "action": action,
        "mode": str(entry.mode) if entry is not None else "",
        "coherence": round(float(entry.coherence), 5) if entry is not None else 0.0,
        "delta": round(float(entry.delta), 5) if entry is not None else 0.0,
        "prediction_available": 1.0 if prediction is not None else 0.0,
        "prediction_confidence": round(float(prediction.confidence), 5) if prediction is not None else 0.0,
        "prediction_uncertainty": round(float(prediction.uncertainty), 5) if prediction is not None else 0.0,
        "prediction_expected_delta": round(float(prediction.expected_delta), 5)
        if prediction is not None and prediction.expected_delta is not None
        else None,
        "prediction_expected_coherence": round(float(prediction.expected_coherence), 5)
        if prediction is not None and prediction.expected_coherence is not None
        else None,
        "prediction_expected_progress": round(float(prediction_expected_outcome.get("progress", 0.0)), 5)
        if prediction is not None and "progress" in prediction_expected_outcome
        else None,
        "prediction_expected_match_ratio": round(float(prediction_expected_outcome.get("match_ratio", 0.0)), 5)
        if prediction is not None and "match_ratio" in prediction_expected_outcome
        else None,
        "prediction_error_magnitude": round(float(prediction_error.magnitude), 5)
        if prediction_error is not None
        else None,
        "route_neighbor": chosen_neighbor,
        "route_transform": chosen_transform,
        "expected_context": expected_context,
        "expected_transform": expected_transform,
        "route_transform_match": route_transform_match,
    }


def _first_cycle(records: Sequence[dict[str, object]], field: str, *, threshold: float = 0.5) -> int | None:
    for record in records:
        if float(record.get(field, 0.0)) >= threshold:
            return int(record["cycle"])
    return None


def _best_positive_transform(transform_scores: dict[str, object] | None) -> str | None:
    scores = {
        str(name): float(value)
        for name, value in dict(transform_scores or {}).items()
        if float(value) > 0.0
    }
    if not scores:
        return None
    return max(scores.items(), key=lambda item: (item[1], item[0]))[0]


def _node_summary(records: Sequence[dict[str, object]]) -> dict[str, object]:
    action_counts = Counter(str(record.get("action", "")) for record in records if record.get("action"))
    route_records = [record for record in records if record.get("route_neighbor") is not None]
    predicted_records = [record for record in records if float(record.get("prediction_available", 0.0)) >= 0.5]
    predicted_route_records = [
        record for record in route_records if float(record.get("prediction_available", 0.0)) >= 0.5
    ]
    route_branch_counts = Counter(str(record.get("route_neighbor")) for record in route_records)
    route_transform_counts = Counter(str(record.get("route_transform")) for record in route_records)
    route_mode_counts = Counter(str(record.get("mode", "")) for record in route_records if record.get("mode"))
    match_values = [
        float(record["route_transform_match"])
        for record in route_records
        if record.get("route_transform_match") is not None
    ]
    pre_sequence_guidance_records = [
        record
        for record in route_records
        if _best_positive_transform(record.get("pre_source_sequence_transform_hint")) is not None
    ]
    pre_sequence_guidance_match_count = sum(
        1
        for record in pre_sequence_guidance_records
        if record.get("route_transform") == _best_positive_transform(record.get("pre_source_sequence_transform_hint"))
    )
    pre_latent_guidance_records = [
        record
        for record in route_records
        if record.get("pre_latent_context_estimate") is not None
        and record.get("expected_transform") is not None
    ]
    pre_latent_guidance_match_count = sum(
        1
        for record in pre_latent_guidance_records
        if record.get("route_transform") == record.get("expected_transform")
    )
    prediction_confidences = [
        float(record["prediction_confidence"])
        for record in predicted_records
        if record.get("prediction_confidence") is not None
    ]
    prediction_expected_deltas = [
        float(record["prediction_expected_delta"])
        for record in predicted_records
        if record.get("prediction_expected_delta") is not None
    ]
    prediction_expected_match_ratios = [
        float(record["prediction_expected_match_ratio"])
        for record in predicted_records
        if record.get("prediction_expected_match_ratio") is not None
    ]
    prediction_error_magnitudes = [
        float(record["prediction_error_magnitude"])
        for record in predicted_records
        if record.get("prediction_error_magnitude") is not None
    ]
    first_latent_capability_cycle = _first_cycle(records, "latent_capability_enabled")
    predicted_before_latent_records = [
        record
        for record in predicted_route_records
        if first_latent_capability_cycle is None or int(record["cycle"]) < first_latent_capability_cycle
    ]
    return {
        "first_packet_cycle": _first_cycle(records, "has_packet"),
        "first_task_cycle": _first_cycle(records, "head_has_task"),
        "first_latent_context_cycle": _first_cycle(records, "latent_context_available"),
        "first_effective_context_cycle": _first_cycle(records, "effective_has_context"),
        "first_context_promotion_ready_cycle": _first_cycle(records, "context_promotion_ready"),
        "first_latent_capability_cycle": first_latent_capability_cycle,
        "first_growth_capability_cycle": _first_cycle(records, "growth_capability_enabled"),
        "first_source_sequence_cycle": _first_cycle(records, "source_sequence_available"),
        "first_prediction_cycle": _first_cycle(records, "prediction_available"),
        "first_route_prediction_cycle": _first_cycle(route_records, "prediction_available"),
        "route_count": len(route_records),
        "predicted_entry_count": len(predicted_records),
        "predicted_route_entry_count": len(predicted_route_records),
        "predicted_route_before_latent_count": len(predicted_before_latent_records),
        "predicted_route_before_latent_rate": round(
            len(predicted_before_latent_records) / max(len(predicted_route_records), 1),
            5,
        ) if predicted_route_records else None,
        "route_branch_counts": dict(sorted(route_branch_counts.items())),
        "route_transform_counts": dict(sorted(route_transform_counts.items())),
        "route_mode_counts": dict(sorted(route_mode_counts.items())),
        "top_actions": dict(action_counts.most_common(5)),
        "route_expected_match_rate": round(mean(match_values), 5) if match_values else None,
        "route_expected_match_count": len(match_values),
        "pre_sequence_guidance_match_rate": round(
            pre_sequence_guidance_match_count / max(len(pre_sequence_guidance_records), 1),
            5,
        ) if pre_sequence_guidance_records else None,
        "pre_sequence_guidance_match_count": pre_sequence_guidance_match_count,
        "pre_sequence_guidance_count": len(pre_sequence_guidance_records),
        "pre_latent_guidance_match_rate": round(
            pre_latent_guidance_match_count / max(len(pre_latent_guidance_records), 1),
            5,
        ) if pre_latent_guidance_records else None,
        "pre_latent_guidance_match_count": pre_latent_guidance_match_count,
        "pre_latent_guidance_count": len(pre_latent_guidance_records),
        "mean_latent_context_confidence": round(
            mean(float(record.get("latent_context_confidence", 0.0)) for record in records),
            5,
        ),
        "mean_recent_latent_context_confidence": round(
            mean(float(record.get("recent_latent_context_confidence", 0.0)) for record in records),
            5,
        ),
        "mean_source_sequence_context_confidence": round(
            mean(float(record.get("source_sequence_context_confidence", 0.0)) for record in records),
            5,
        ),
        "mean_prediction_confidence": round(mean(prediction_confidences), 5) if prediction_confidences else None,
        "max_prediction_confidence": round(max(prediction_confidences), 5) if prediction_confidences else None,
        "mean_prediction_expected_delta": round(mean(prediction_expected_deltas), 5)
        if prediction_expected_deltas
        else None,
        "mean_prediction_expected_match_ratio": round(mean(prediction_expected_match_ratios), 5)
        if prediction_expected_match_ratios
        else None,
        "mean_prediction_error_magnitude": round(mean(prediction_error_magnitudes), 5)
        if prediction_error_magnitudes
        else None,
        "mean_latent_recruitment_pressure": round(
            mean(float(record.get("latent_recruitment_pressure", 0.0)) for record in records),
            5,
        ),
        "max_latent_capability_support": round(
            max(float(record.get("latent_capability_support", 0.0)) for record in records),
            5,
        ),
        "mean_latent_capability_support": round(
            mean(float(record.get("latent_capability_support", 0.0)) for record in records),
            5,
        ),
        "peak_contradiction_pressure": round(
            max(float(record.get("contradiction_pressure", 0.0)) for record in records),
            5,
        ),
        "mean_contradiction_pressure": round(
            mean(float(record.get("contradiction_pressure", 0.0)) for record in records),
            5,
        ),
        "min_visible_context_trust": round(
            min(float(record.get("visible_context_trust", 0.0)) for record in records),
            5,
        ),
        "mean_visible_context_trust": round(
            mean(float(record.get("visible_context_trust", 0.0)) for record in records),
            5,
        ),
    }


def evaluate_benchmark_node_probe(
    *,
    seed: int = 13,
    benchmark_id: str = "B2",
    task_keys: Sequence[str] = ("task_a",),
    method_id: str = "self-selected",
    focus_nodes: Sequence[str] | None = None,
    cycle_limit: int | None = 40,
) -> Dict[str, object]:
    point = benchmark_suite_by_id()[benchmark_id]
    latent, morphogenesis = _method_flags(method_id)
    task_runs: Dict[str, dict[str, object]] = {}

    for task_key in task_keys:
        spec = _task_spec(point, task_key, method_id=method_id)
        system = _build_system_from_spec(seed, spec, method_id=method_id)
        selected_nodes = list(focus_nodes) if focus_nodes is not None else _default_focus_nodes(system)
        total_cycles = spec.cycles if cycle_limit is None else min(spec.cycles, int(cycle_limit))
        task_id = _task_id_from_spec(spec, task_key)
        if spec.initial_signal_specs:
            system.inject_signal_specs(spec.initial_signal_specs)
        elif spec.initial_packets > 0:
            system.inject_signal(count=spec.initial_packets)

        node_records: Dict[str, List[dict[str, object]]] = {node_id: [] for node_id in selected_nodes}
        for cycle in range(1, total_cycles + 1):
            _inject_for_cycle(system, spec, cycle)
            report = system.run_global_cycle()
            for node_id in selected_nodes:
                node_records[node_id].append(
                    _node_cycle_record(system, report, cycle=cycle, node_id=node_id, task_id=task_id)
                )

        system_summary = system.summarize()
        exact_matches = int(system_summary.get("exact_matches", 0))
        task_runs[task_key] = {
            "task_id": task_id,
            "cycle_limit": total_cycles,
            "focus_nodes": selected_nodes,
            "summary": {
                "exact_matches": exact_matches,
                "exact_match_rate": round(exact_matches / max(point.expected_examples, 1), 5),
                "mean_bit_accuracy": round(float(system_summary.get("mean_bit_accuracy", 0.0)), 5),
                "latent_recruitment_cycles": list(
                    system_summary.get("latent_recruitment_cycles", {}).get(spec.source_id, [])
                ),
                "growth_recruitment_cycles": list(
                    system_summary.get("growth_recruitment_cycles", {}).get(spec.source_id, [])
                ),
                "wrong_transform_family": round(
                    float(system_summary.get("task_diagnostics", {}).get("overall", {}).get("wrong_transform_family", 0.0)),
                    5,
                ),
                "route_right_transform_wrong": round(
                    float(system_summary.get("task_diagnostics", {}).get("overall", {}).get("route_right_transform_wrong", 0.0)),
                    5,
                ),
                "route_wrong_transform_potentially_right": round(
                    float(system_summary.get("task_diagnostics", {}).get("overall", {}).get("route_wrong_transform_potentially_right", 0.0)),
                    5,
                ),
            },
            "nodes": {
                node_id: {
                    "timeline": records,
                    "summary": _node_summary(records),
                }
                for node_id, records in node_records.items()
            },
        }

    return {
        "benchmark_id": benchmark_id,
        "method_id": method_id,
        "seed": seed,
        "latent_context": latent,
        "morphogenesis_enabled": morphogenesis,
        "task_runs": task_runs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Node-level probe for benchmark tasks, including self-selected REAL.")
    parser.add_argument("--output", type=str, help="path to save the JSON manifest")
    parser.add_argument("--benchmark", default="B2")
    parser.add_argument("--method", default="self-selected")
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--tasks", nargs="+", default=["task_a"])
    parser.add_argument("--nodes", nargs="*", default=None)
    parser.add_argument("--cycles", type=int, default=40)
    args = parser.parse_args()

    result = evaluate_benchmark_node_probe(
        seed=args.seed,
        benchmark_id=args.benchmark,
        task_keys=tuple(args.tasks),
        method_id=args.method,
        focus_nodes=tuple(args.nodes) if args.nodes else None,
        cycle_limit=args.cycles,
    )
    if args.output:
        manifest = build_run_manifest(
            harness="benchmark_node_probe",
            seeds=[args.seed],
            scenarios=[f"{args.benchmark}:{task_key}:{args.method}" for task_key in args.tasks],
            result=result,
            metadata={
                "benchmark_id": args.benchmark,
                "method_id": args.method,
                "task_keys": list(args.tasks),
                "focus_nodes": list(args.nodes or []),
                "cycle_limit": args.cycles,
            },
        )
        write_run_manifest(args.output, manifest)
        print(f"Saved run manifest to {args.output}")
        return

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
