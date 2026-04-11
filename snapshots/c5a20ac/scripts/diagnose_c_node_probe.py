from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Sequence

from phase8.environment import _expected_transform_for_task
from scripts.ceiling_benchmark_suite import benchmark_suite_by_id
from scripts.diagnose_c_family_real import _build_system_from_spec, _method_flags, _task_spec
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


def _inject_for_cycle(system, spec, cycle: int) -> None:
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


def _default_focus_nodes(system, *, max_nodes: int = 4) -> List[str]:
    env = system.environment
    source_id = env.source_id
    sink_id = env.sink_id
    nodes = [
        node_id
        for node_id in sorted(env.node_states, key=lambda current: env.positions[current])
        if node_id not in {source_id, sink_id}
    ]
    return nodes[:max_nodes]


def _node_cycle_record(
    system,
    report: dict[str, object],
    *,
    cycle: int,
    node_id: str,
    task_id: str,
) -> dict[str, object]:
    observation = system.environment.observe_local(node_id)
    growth_specs = system.environment.growth_action_specs(node_id)
    bud_specs = [spec for spec in growth_specs if str(spec.get("action", "")).startswith("bud_")]
    entry = dict(report.get("entries", {})).get(node_id)
    action = str(entry.action) if entry is not None else ""
    state_before = dict(entry.state_before) if entry is not None else {}
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
    return {
        "cycle": cycle,
        "node_id": node_id,
        "has_packet": float(observation.get("has_packet", 0.0)),
        "head_has_task": float(observation.get("head_has_task", 0.0)),
        "head_has_context": float(observation.get("head_has_context", 0.0)),
        "pre_has_packet": float(state_before.get("has_packet", 0.0)),
        "pre_head_has_task": float(state_before.get("head_has_task", 0.0)),
        "pre_head_has_context": float(state_before.get("head_has_context", 0.0)),
        "latent_context_available": float(observation.get("latent_context_available", 0.0)),
        "latent_context_estimate": latent_estimate,
        "latent_context_confidence": round(float(observation.get("latent_context_confidence", 0.0)), 5),
        "pre_latent_context_available": float(state_before.get("latent_context_available", 0.0)),
        "pre_latent_context_confidence": round(float(state_before.get("latent_context_confidence", 0.0)), 5),
        "effective_has_context": float(observation.get("effective_has_context", 0.0)),
        "effective_context_bit": effective_context_bit,
        "effective_context_confidence": round(float(observation.get("effective_context_confidence", 0.0)), 5),
        "pre_effective_has_context": float(state_before.get("effective_has_context", 0.0)),
        "pre_effective_context_confidence": round(float(state_before.get("effective_context_confidence", 0.0)), 5),
        "context_promotion_ready": float(observation.get("context_promotion_ready", 0.0)),
        "context_growth_ready": float(observation.get("context_growth_ready", 0.0)),
        "pre_context_promotion_ready": float(state_before.get("context_promotion_ready", 0.0)),
        "pre_context_growth_ready": float(state_before.get("context_growth_ready", 0.0)),
        "recent_latent_task_active": float(observation.get("recent_latent_task_active", 0.0)),
        "recent_latent_task_age": round(float(observation.get("recent_latent_task_age", 0.0)), 5),
        "recent_latent_context_confidence": round(
            float(observation.get("recent_latent_context_confidence", 0.0)),
            5,
        ),
        "pre_recent_latent_task_active": float(state_before.get("recent_latent_task_active", 0.0)),
        "contradiction_pressure": round(float(observation.get("contradiction_pressure", 0.0)), 5),
        "pre_contradiction_pressure": round(float(state_before.get("contradiction_pressure", 0.0)), 5),
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
        "source_sequence_transform_hint": {
            name: round(float(observation.get(f"source_sequence_transform_hint_{name}", 0.0)), 5)
            for name in ("identity", "rotate_left_1", "xor_mask_1010", "xor_mask_0101")
        },
        "growth_candidate_action_count": len(growth_specs),
        "bud_action_available_count": len(bud_specs),
        "action": action,
        "mode": str(entry.mode) if entry is not None else "",
        "coherence": round(float(entry.coherence), 5) if entry is not None else 0.0,
        "delta": round(float(entry.delta), 5) if entry is not None else 0.0,
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


def _node_summary(records: Sequence[dict[str, object]]) -> dict[str, object]:
    action_counts = Counter(str(record.get("action", "")) for record in records if record.get("action"))
    route_records = [record for record in records if record.get("route_neighbor") is not None]
    route_branch_counts = Counter(str(record.get("route_neighbor")) for record in route_records)
    route_transform_counts = Counter(str(record.get("route_transform")) for record in route_records)
    route_mode_counts = Counter(str(record.get("mode", "")) for record in route_records if record.get("mode"))
    match_values = [
        float(record["route_transform_match"])
        for record in route_records
        if record.get("route_transform_match") is not None
    ]
    return {
        "first_packet_cycle": _first_cycle(records, "has_packet"),
        "first_task_cycle": _first_cycle(records, "head_has_task"),
        "first_latent_context_cycle": _first_cycle(records, "latent_context_available"),
        "first_effective_context_cycle": _first_cycle(records, "effective_has_context"),
        "first_context_promotion_ready_cycle": _first_cycle(records, "context_promotion_ready"),
        "first_context_growth_ready_cycle": _first_cycle(records, "context_growth_ready"),
        "first_bud_available_cycle": next(
            (
                int(record["cycle"])
                for record in records
                if int(record.get("bud_action_available_count", 0)) > 0
            ),
            None,
        ),
        "route_count": len(route_records),
        "route_branch_counts": dict(sorted(route_branch_counts.items())),
        "route_transform_counts": dict(sorted(route_transform_counts.items())),
        "route_mode_counts": dict(sorted(route_mode_counts.items())),
        "top_actions": dict(action_counts.most_common(5)),
        "route_expected_match_rate": round(mean(match_values), 5) if match_values else None,
        "route_expected_match_count": len(match_values),
        "idle_recent_latent_cycles": int(
            sum(
                1
                for record in records
                if float(record.get("recent_latent_task_active", 0.0)) >= 0.5
                and float(record.get("head_has_task", 0.0)) < 0.5
            )
        ),
        "bud_while_idle_recent_latent_cycles": int(
            sum(
                1
                for record in records
                if float(record.get("recent_latent_task_active", 0.0)) >= 0.5
                and float(record.get("head_has_task", 0.0)) < 0.5
                and int(record.get("bud_action_available_count", 0)) > 0
            )
        ),
        "mean_latent_context_confidence": round(
            mean(float(record.get("latent_context_confidence", 0.0)) for record in records),
            5,
        ),
        "mean_effective_context_confidence": round(
            mean(float(record.get("effective_context_confidence", 0.0)) for record in records),
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
        "max_bud_action_available_count": max(int(record.get("bud_action_available_count", 0)) for record in records),
    }


def evaluate_c_node_probe(
    *,
    seed: int = 13,
    benchmark_id: str = "C3",
    task_keys: Sequence[str] = ("task_b", "task_c"),
    method_id: str = "growth-latent",
    focus_nodes: Sequence[str] | None = None,
    cycle_limit: int | None = 32,
) -> Dict[str, object]:
    point = benchmark_suite_by_id()[benchmark_id]
    latent, morphogenesis = _method_flags(method_id)
    task_runs: Dict[str, dict[str, object]] = {}

    for task_key in task_keys:
        spec = _task_spec(point, task_key, latent=latent)
        system = _build_system_from_spec(
            seed,
            point,
            latent=latent,
            morphogenesis_enabled=morphogenesis,
            latent_transfer_split_enabled=True,
        )
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
                "bud_successes": int(system_summary.get("bud_successes", 0)),
                "dynamic_node_count": int(system_summary.get("dynamic_node_count", 0)),
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
    parser = argparse.ArgumentParser(description="Node-level probe for generated Family C tasks.")
    parser.add_argument("--output", type=str, help="path to save the JSON manifest")
    parser.add_argument("--benchmark", default="C3")
    parser.add_argument("--method", default="growth-latent")
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--tasks", nargs="+", default=["task_b", "task_c"])
    parser.add_argument("--nodes", nargs="*", default=None)
    parser.add_argument("--cycles", type=int, default=32)
    args = parser.parse_args()

    result = evaluate_c_node_probe(
        seed=args.seed,
        benchmark_id=args.benchmark,
        task_keys=tuple(args.tasks),
        method_id=args.method,
        focus_nodes=tuple(args.nodes) if args.nodes else None,
        cycle_limit=args.cycles,
    )
    if args.output:
        manifest = build_run_manifest(
            harness="c_node_probe",
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
