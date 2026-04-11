from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path

from scripts.compare_cold_warm import ROOT, build_system, run_workload
from scripts.compare_task_transfer import TRAIN_SCENARIO, TRANSFER_SCENARIO, transfer_metrics
from scripts.experiment_manifest import build_run_manifest, write_run_manifest


def _set_recognition_bias(system, *, enabled: bool) -> None:
    for agent in system.agents.values():
        agent.engine.selector.recognition_route_bonus = 0.12 if enabled else 0.0
        agent.engine.selector.recognition_route_penalty = 0.10 if enabled else 0.0
        agent.engine.selector.recognition_transform_bonus = 0.10 if enabled else 0.0


def _ordered_scored_packets(system) -> list[object]:
    return sorted(
        [
            packet
            for packet in system.environment.delivered_packets
            if packet.bit_match_ratio is not None
        ],
        key=lambda packet: (
            packet.delivered_cycle if packet.delivered_cycle is not None else system.global_cycle,
            packet.created_cycle,
            packet.packet_id,
        ),
    )


def _recognized_route_stats(
    system,
    *,
    carryover_entry_counts: dict[str, int] | None = None,
) -> dict[str, object]:
    route_entries = []
    source_id = system.environment.source_id
    source_route_entries = []
    recognized_route_cycles: list[int] = []
    recognized_source_route_cycles: list[int] = []
    recognized_source_actions: list[str] = []
    recognized_source_transform_cycles: list[int] = []
    recognized_source_transform_actions: list[str] = []
    recognized_route_entries = 0
    recognized_route_attractor_entries = 0
    recognized_source_transform_entries = 0
    recognized_source_transform_attractor_entries = 0
    confidence_total = 0.0
    for agent in system.agents.values():
        start_index = 0 if carryover_entry_counts is None else carryover_entry_counts.get(agent.node_id, 0)
        for entry in agent.engine.memory.entries[start_index:]:
            action = str(entry.action)
            if not action.startswith("route"):
                continue
            route_entries.append(entry)
            if agent.node_id == source_id:
                source_route_entries.append(entry)
            recognition = getattr(entry, "recognition", None)
            if recognition is None or not recognition.matches:
                continue
            recognized_route_entries += 1
            recognized_route_cycles.append(int(entry.cycle))
            confidence_total += float(recognition.confidence)
            if any(match.source == "route_attractor" for match in recognition.matches):
                recognized_route_attractor_entries += 1
            if agent.node_id == source_id:
                recognized_source_route_cycles.append(int(entry.cycle))
                recognized_source_actions.append(action)
                if any(
                    match.source in ("transform_attractor", "context_transform_attractor")
                    for match in recognition.matches
                ):
                    recognized_source_transform_entries += 1
                    recognized_source_transform_cycles.append(int(entry.cycle))
                    recognized_source_transform_actions.append(action)
                if any(
                    match.source == "context_transform_attractor"
                    for match in recognition.matches
                ):
                    recognized_source_transform_attractor_entries += 1

    packets = _ordered_scored_packets(system)
    wrong_delivery_cycles = [
        int(packet.delivered_cycle or system.global_cycle)
        for packet in packets
        if not packet.matched_target
    ]
    first_wrong_delivery_cycle = (
        min(wrong_delivery_cycles) if wrong_delivery_cycles else None
    )
    last_wrong_delivery_cycle = (
        max(wrong_delivery_cycles) if wrong_delivery_cycles else None
    )
    transfer_window_end = int(system.environment.transfer_adaptation_window)
    route_count = len(route_entries)
    return {
        "route_entry_count": route_count,
        "source_route_entry_count": len(source_route_entries),
        "recognized_route_entry_count": recognized_route_entries,
        "recognized_route_entry_rate": round(
            recognized_route_entries / max(route_count, 1),
        4,
        ),
        "recognized_route_attractor_entry_count": recognized_route_attractor_entries,
        "mean_recognition_confidence_on_recognized_routes": round(
            confidence_total / max(recognized_route_entries, 1),
            4,
        ),
        "recognized_route_cycles": recognized_route_cycles,
        "recognized_source_route_cycles": recognized_source_route_cycles,
        "recognized_source_actions_preview": recognized_source_actions[:8],
        "recognized_source_transform_entry_count": recognized_source_transform_entries,
        "recognized_source_transform_entry_rate": round(
            recognized_source_transform_entries / max(len(source_route_entries), 1),
            4,
        ),
        "recognized_source_transform_attractor_entry_count": (
            recognized_source_transform_attractor_entries
        ),
        "recognized_source_transform_cycles": recognized_source_transform_cycles,
        "recognized_source_transform_actions_preview": recognized_source_transform_actions[:8],
        "first_source_route_cycle": (
            min(int(entry.cycle) for entry in source_route_entries)
            if source_route_entries
            else None
        ),
        "first_recognized_route_cycle": (
            min(recognized_route_cycles) if recognized_route_cycles else None
        ),
        "first_recognized_source_route_cycle": (
            min(recognized_source_route_cycles) if recognized_source_route_cycles else None
        ),
        "first_recognized_source_transform_cycle": (
            min(recognized_source_transform_cycles)
            if recognized_source_transform_cycles
            else None
        ),
        "first_wrong_delivery_cycle": first_wrong_delivery_cycle,
        "last_wrong_delivery_cycle": last_wrong_delivery_cycle,
        "wrong_delivery_cycle_count": len(wrong_delivery_cycles),
        "wrong_delivery_cycles_preview": wrong_delivery_cycles[:8],
        "recognized_before_first_wrong_delivery_count": (
            0
            if first_wrong_delivery_cycle is None
            else sum(
                1 for cycle in recognized_route_cycles if cycle < first_wrong_delivery_cycle
            )
        ),
        "recognized_during_wrong_delivery_window_count": (
            0
            if first_wrong_delivery_cycle is None or last_wrong_delivery_cycle is None
            else sum(
                1
                for cycle in recognized_route_cycles
                if first_wrong_delivery_cycle <= cycle <= last_wrong_delivery_cycle
            )
        ),
        "recognized_after_last_wrong_delivery_count": (
            len(recognized_route_cycles)
            if last_wrong_delivery_cycle is None
            else sum(
                1 for cycle in recognized_route_cycles if cycle > last_wrong_delivery_cycle
            )
        ),
        "recognized_within_transfer_window_count": sum(
            1 for cycle in recognized_route_cycles if cycle <= transfer_window_end
        ),
        "recognized_after_transfer_window_count": sum(
            1 for cycle in recognized_route_cycles if cycle > transfer_window_end
        ),
        "recognized_source_transform_before_first_wrong_delivery_count": (
            0
            if first_wrong_delivery_cycle is None
            else sum(
                1
                for cycle in recognized_source_transform_cycles
                if cycle < first_wrong_delivery_cycle
            )
        ),
        "recognized_source_transform_on_first_source_route": (
            bool(source_route_entries)
            and bool(recognized_source_transform_cycles)
            and min(recognized_source_transform_cycles)
            <= min(int(entry.cycle) for entry in source_route_entries)
        ),
    }


def _run_warm_transfer_variant(
    *,
    seed: int,
    recognition_bias_enabled: bool,
) -> dict[str, object]:
    base_dir = ROOT / "tests_tmp" / f"recognition_transfer_probe_{uuid.uuid4().hex}"
    carryover_dir = base_dir / "carryover"
    carryover_dir.mkdir(parents=True, exist_ok=True)
    try:
        training = build_system(seed, TRAIN_SCENARIO)
        run_workload(training, TRAIN_SCENARIO)
        training.save_memory_carryover(carryover_dir)

        system = build_system(seed, TRANSFER_SCENARIO)
        _set_recognition_bias(system, enabled=recognition_bias_enabled)
        system.load_memory_carryover(carryover_dir)
        carryover_entry_counts = {
            agent.node_id: len(agent.engine.memory.entries)
            for agent in system.agents.values()
        }
        summary = run_workload(system, TRANSFER_SCENARIO)
        metrics = transfer_metrics(system)
        recognition = _recognized_route_stats(
            system,
            carryover_entry_counts=carryover_entry_counts,
        )
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)

    return {
        "recognition_bias_enabled": bool(recognition_bias_enabled),
        "summary": {
            "exact_matches": int(summary["exact_matches"]),
            "mean_bit_accuracy": round(float(summary["mean_bit_accuracy"]), 4),
            "mean_route_cost": round(float(summary["mean_route_cost"]), 5),
            "delivery_ratio": round(float(summary["delivery_ratio"]), 4),
        },
        "transfer_metrics": {
            "criterion_reached": bool(metrics["criterion_reached"]),
            "examples_to_criterion": metrics["examples_to_criterion"],
            "cycles_to_criterion": metrics["cycles_to_criterion"],
            "best_rolling_exact_rate": float(metrics["best_rolling_exact_rate"]),
            "best_rolling_bit_accuracy": float(metrics["best_rolling_bit_accuracy"]),
        },
        "recognition": recognition,
    }


def evaluate_phase8_transfer_recognition_probe(
    *,
    seed: int = 13,
    output_path: Path | None = None,
) -> dict[str, object]:
    enabled = _run_warm_transfer_variant(seed=seed, recognition_bias_enabled=True)
    disabled = _run_warm_transfer_variant(seed=seed, recognition_bias_enabled=False)
    result = {
        "seed": int(seed),
        "train_scenario": TRAIN_SCENARIO,
        "transfer_scenario": TRANSFER_SCENARIO,
        "warm_transfer_with_recognition_bias": enabled,
        "warm_transfer_without_recognition_bias": disabled,
        "delta_enabled_minus_disabled": {
            "exact_matches": int(enabled["summary"]["exact_matches"]) - int(disabled["summary"]["exact_matches"]),
            "mean_bit_accuracy": round(
                float(enabled["summary"]["mean_bit_accuracy"])
                - float(disabled["summary"]["mean_bit_accuracy"]),
                4,
            ),
            "mean_route_cost": round(
                float(enabled["summary"]["mean_route_cost"])
                - float(disabled["summary"]["mean_route_cost"]),
                5,
            ),
            "best_rolling_exact_rate": round(
                float(enabled["transfer_metrics"]["best_rolling_exact_rate"])
                - float(disabled["transfer_metrics"]["best_rolling_exact_rate"]),
                4,
            ),
            "recognized_route_entry_rate": round(
                float(enabled["recognition"]["recognized_route_entry_rate"])
                - float(disabled["recognition"]["recognized_route_entry_rate"]),
                4,
            ),
            "recognized_source_transform_entry_rate": round(
                float(enabled["recognition"]["recognized_source_transform_entry_rate"])
                - float(disabled["recognition"]["recognized_source_transform_entry_rate"]),
                4,
            ),
        },
    }
    if output_path is not None:
        manifest = build_run_manifest(
            harness="phase8_transfer_recognition_probe",
            seeds=(seed,),
            scenarios=(f"{TRAIN_SCENARIO}->{TRANSFER_SCENARIO}",),
            metadata={},
            result=result,
        )
        write_run_manifest(output_path, manifest)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a tiny warm-transfer probe comparing Phase 8 recognition route bias on vs off."
    )
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--output", type=str)
    args = parser.parse_args()

    result = evaluate_phase8_transfer_recognition_probe(
        seed=args.seed,
        output_path=Path(args.output) if args.output else None,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
