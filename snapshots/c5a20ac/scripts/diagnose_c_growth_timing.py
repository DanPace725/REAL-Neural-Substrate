from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path
from typing import Dict, List

from scripts.analyze_transfer_timecourse import _latent_timeline_summary
from scripts.diagnose_c_family_real import _build_system_from_spec, _method_flags, _task_spec
from scripts.ceiling_benchmark_suite import benchmark_suite_by_id
from scripts.experiment_manifest import build_run_manifest, write_run_manifest


ROOT = Path(__file__).resolve().parents[1]


def _inject_for_cycle(system, spec, cycle: int) -> None:
    scheduled_specs = dict(spec.signal_schedule_specs or {}).get(cycle)
    if scheduled_specs:
        system.inject_signal_specs(scheduled_specs)
        return
    scheduled = dict(spec.packet_schedule or {}).get(cycle, 0)
    if scheduled > 0:
        system.inject_signal(count=scheduled)


def _source_growth_timing_record(system, *, cycle: int) -> dict[str, object]:
    source_id = system.environment.source_id
    observation = system.environment.observe_local(source_id)
    growth_specs = system.environment.growth_action_specs(source_id)
    bud_specs = [spec for spec in growth_specs if str(spec.get("action", "")).startswith("bud_")]
    summary = system.summarize()
    return {
        "cycle": cycle,
        "exact_matches": int(summary.get("exact_matches", 0)),
        "mean_bit_accuracy": round(float(summary.get("mean_bit_accuracy", 0.0)), 5),
        "latent_context_available": float(observation.get("latent_context_available", 0.0)),
        "latent_context_estimate": float(observation.get("latent_context_estimate", 0.0)),
        "latent_context_confidence": round(float(observation.get("latent_context_confidence", 0.0)), 5),
        "effective_has_context": float(observation.get("effective_has_context", 0.0)),
        "effective_context_bit": float(observation.get("effective_context_bit", 0.0)),
        "effective_context_confidence": round(float(observation.get("effective_context_confidence", 0.0)), 5),
        "effective_context_threshold": round(float(observation.get("effective_context_threshold", 0.0)), 5),
        "context_promotion_ready": float(observation.get("context_promotion_ready", 0.0)),
        "context_growth_ready": float(observation.get("context_growth_ready", 0.0)),
        "source_sequence_available": float(observation.get("source_sequence_available", 0.0)),
        "source_sequence_context_estimate": float(observation.get("source_sequence_context_estimate", 0.0)),
        "source_sequence_context_confidence": round(
            float(observation.get("source_sequence_context_confidence", 0.0)),
            5,
        ),
        "source_atp_ratio": round(float(observation.get("atp_ratio", 0.0)), 5),
        "growth_candidate_action_count": len(growth_specs),
        "bud_action_available_count": len(bud_specs),
        "bud_action_available": 1.0 if bud_specs else 0.0,
        "bud_action_labels": [str(spec.get("action")) for spec in bud_specs],
        "dynamic_node_count": int(summary.get("dynamic_node_count", 0)),
        "bud_successes": int(summary.get("bud_successes", 0)),
    }


def _summarize_growth_timing(records: List[dict[str, object]]) -> dict[str, object]:
    latent_summary = _latent_timeline_summary(records)

    def _first_cycle(field: str, *, threshold: float = 0.5) -> int | None:
        for record in records:
            if float(record.get(field, 0.0)) >= threshold:
                return int(record["cycle"])
        return None

    def _first_positive_cycle(field: str) -> int | None:
        for record in records:
            if int(record.get(field, 0)) > 0:
                return int(record["cycle"])
        return None

    promotion_before_growth_cycles = sum(
        1
        for record in records
        if float(record.get("context_promotion_ready", 0.0)) >= 0.5
        and float(record.get("context_growth_ready", 0.0)) < 0.5
    )

    return {
        **latent_summary,
        "first_bud_action_available_cycle": _first_cycle("bud_action_available"),
        "first_bud_success_cycle": _first_positive_cycle("bud_successes"),
        "first_dynamic_node_cycle": _first_positive_cycle("dynamic_node_count"),
        "promotion_before_growth_cycle_count": promotion_before_growth_cycles,
        "max_bud_action_available_count": max(
            (int(record.get("bud_action_available_count", 0)) for record in records),
            default=0,
        ),
        "max_dynamic_node_count": max(
            (int(record.get("dynamic_node_count", 0)) for record in records),
            default=0,
        ),
    }


def evaluate_c_growth_timing(
    *,
    seed: int = 13,
    benchmark_id: str = "C3",
    task_key: str = "task_b",
    method_id: str = "growth-latent",
    train_task_key: str | None = None,
    latent_transfer_split_enabled: bool = True,
) -> Dict[str, object]:
    suite_lookup = benchmark_suite_by_id()
    point = suite_lookup[benchmark_id]
    latent, morphogenesis = _method_flags(method_id)
    spec = _task_spec(point, task_key, latent=latent)

    system = _build_system_from_spec(
        seed,
        point,
        latent=latent,
        morphogenesis_enabled=morphogenesis,
        latent_transfer_split_enabled=latent_transfer_split_enabled,
    )

    carryover_mode = "cold"
    if train_task_key is not None:
        carryover_mode = f"{train_task_key}_carryover"
        train_spec = _task_spec(point, train_task_key, latent=latent)
        base_dir = ROOT / "tests_tmp" / f"c_growth_timing_{uuid.uuid4().hex}"
        carryover_dir = base_dir / "memory"
        carryover_dir.mkdir(parents=True, exist_ok=True)
        try:
            train_system = _build_system_from_spec(
                seed,
                point,
                latent=latent,
                morphogenesis_enabled=morphogenesis,
                latent_transfer_split_enabled=latent_transfer_split_enabled,
            )
            train_system.run_workload(
                cycles=train_spec.cycles,
                initial_packets=train_spec.initial_packets,
                packet_schedule=train_spec.packet_schedule,
                initial_signal_specs=train_spec.initial_signal_specs,
                signal_schedule_specs=train_spec.signal_schedule_specs,
            )
            train_system.save_memory_carryover(carryover_dir)
            system.load_memory_carryover(carryover_dir)
        finally:
            shutil.rmtree(base_dir, ignore_errors=True)

    if spec.initial_signal_specs:
        system.inject_signal_specs(spec.initial_signal_specs)
    elif spec.initial_packets > 0:
        system.inject_signal(count=spec.initial_packets)

    records: List[dict[str, object]] = []
    topology_records: List[dict[str, object]] = []
    for cycle in range(1, spec.cycles + 1):
        _inject_for_cycle(system, spec, cycle)
        report = system.run_global_cycle()
        record = _source_growth_timing_record(system, cycle=cycle)
        records.append(record)
        topology_records.append(
            {
                "cycle": cycle,
                "topology_events": list(report.get("topology_events", [])),
                "bud_event_count": sum(
                    1
                    for event in report.get("topology_events", [])
                    if str(event.get("event_type", "")).startswith("bud_")
                ),
            }
        )

    return {
        "benchmark_id": benchmark_id,
        "task_key": task_key,
        "method_id": method_id,
        "seed": seed,
        "latent_context": latent,
        "morphogenesis_enabled": morphogenesis,
        "carryover_mode": carryover_mode,
        "train_task_key": train_task_key,
        "timeline": records,
        "topology_timeline": topology_records,
        "summary": _summarize_growth_timing(records),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe latent promotion-vs-growth timing on generated C-family tasks."
    )
    parser.add_argument("--output", type=str, help="path to save the JSON manifest")
    parser.add_argument("--benchmark", default="C3")
    parser.add_argument("--task", default="task_b")
    parser.add_argument("--method", default="growth-latent")
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--train-task", default=None, help="optional carryover task, e.g. task_a")
    args = parser.parse_args()

    result = evaluate_c_growth_timing(
        seed=args.seed,
        benchmark_id=args.benchmark,
        task_key=args.task,
        method_id=args.method,
        train_task_key=args.train_task,
    )
    if args.output:
        manifest = build_run_manifest(
            harness="c_growth_timing",
            seeds=[args.seed],
            scenarios=[f"{args.benchmark}:{args.task}:{args.method}"],
            result=result,
            metadata={
                "benchmark_id": args.benchmark,
                "task_key": args.task,
                "method_id": args.method,
                "train_task_key": args.train_task,
            },
        )
        write_run_manifest(args.output, manifest)
        print(f"Saved run manifest to {args.output}")
        return

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
