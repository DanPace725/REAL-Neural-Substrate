from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path

from scripts.compare_cold_warm import ROOT, SCENARIOS, build_system, run_workload
from scripts.compare_task_transfer import TRAIN_SCENARIO, TRANSFER_SCENARIO, transfer_metrics
from scripts.experiment_manifest import build_run_manifest, write_run_manifest


def _set_recognition_bias(system, *, enabled: bool) -> None:
    for agent in system.agents.values():
        agent.engine.selector.recognition_route_bonus = 0.12 if enabled else 0.0
        agent.engine.selector.recognition_route_penalty = 0.10 if enabled else 0.0
        agent.engine.selector.recognition_transform_bonus = 0.10 if enabled else 0.0


def _apply_cycle_injections(system, scenario_name: str, cycle_index: int) -> None:
    scenario = SCENARIOS[scenario_name]
    signal_schedule = dict(scenario.signal_schedule_specs or {})
    packet_schedule = dict(scenario.packet_schedule or {})
    scheduled_specs = signal_schedule.get(cycle_index)
    if scheduled_specs:
        system.inject_signal_specs(scheduled_specs)
        return
    scheduled_packets = packet_schedule.get(cycle_index, 0)
    if scheduled_packets > 0:
        system.inject_signal(count=scheduled_packets)


def _initialize_workload(system, scenario_name: str) -> None:
    scenario = SCENARIOS[scenario_name]
    if scenario.initial_signal_specs:
        system.inject_signal_specs(scenario.initial_signal_specs)
    elif scenario.initial_packets > 0:
        system.inject_signal(count=scenario.initial_packets)


def _compact_breakdown(
    breakdown: dict[str, float | int | str | None] | None,
) -> dict[str, object]:
    if breakdown is None:
        return {}
    keys = (
        "total",
        "recognition_transform_term",
        "recognition_transform_confirmation_term",
        "recognition_route_term",
        "task_transform_bonus_term",
        "history_transform_term",
        "feedback_credit_term",
        "context_feedback_credit_term",
        "competition_penalty_term",
        "competition_bonus_term",
        "identity_penalty_term",
        "hidden_wrong_family_penalty_term",
        "cost_penalty_term",
        "context_bit",
        "transform_name",
        "neighbor_id",
    )
    return {key: breakdown.get(key) for key in keys}


def _run_transfer_with_selector_probe(
    *,
    seed: int,
    recognition_bias_enabled: bool,
) -> dict[str, object]:
    base_dir = ROOT / "tests_tmp" / f"selector_interaction_{uuid.uuid4().hex}"
    carryover_dir = base_dir / "carryover"
    carryover_dir.mkdir(parents=True, exist_ok=True)
    try:
        training = build_system(seed, TRAIN_SCENARIO)
        run_workload(training, TRAIN_SCENARIO)
        training.save_memory_carryover(carryover_dir)

        system = build_system(seed, TRANSFER_SCENARIO)
        _set_recognition_bias(system, enabled=recognition_bias_enabled)
        system.load_memory_carryover(carryover_dir)
        scenario = SCENARIOS[TRANSFER_SCENARIO]
        source_id = system.environment.source_id
        source_selector = system.agents[source_id].engine.selector
        source_selector.capture_route_breakdowns = True

        _initialize_workload(system, TRANSFER_SCENARIO)
        source_records: list[dict[str, object]] = []
        for cycle_index in range(1, scenario.cycles + 1):
            if cycle_index > 1:
                _apply_cycle_injections(system, TRANSFER_SCENARIO, cycle_index)
            report = system.run_global_cycle()
            source_entry = report["entries"][source_id]
            action = str(source_entry.action)
            if not action.startswith("route"):
                continue
            breakdowns = source_selector.latest_route_score_breakdowns() or {}
            ranked = sorted(
                (
                    (float(details.get("total", 0.0)), candidate_action)
                    for candidate_action, details in breakdowns.items()
                ),
                reverse=True,
            )
            top_competitor = next(
                (
                    {"action": candidate_action, "total": round(score, 6)}
                    for score, candidate_action in ranked
                    if candidate_action != action
                ),
                None,
            )
            recognition = getattr(source_entry, "recognition", None)
            source_records.append(
                {
                    "cycle": int(source_entry.cycle),
                    "chosen_action": action,
                    "mode": str(source_entry.mode),
                    "recognition_confidence": None
                    if recognition is None
                    else round(float(recognition.confidence), 6),
                    "recognition_sources": []
                    if recognition is None
                    else [match.source for match in recognition.matches],
                    "chosen_breakdown": _compact_breakdown(breakdowns.get(action)),
                    "top_competitor": top_competitor,
                    "top_competitor_breakdown": _compact_breakdown(
                        None
                        if top_competitor is None
                        else breakdowns.get(str(top_competitor["action"]))
                    ),
                }
            )

        summary = system.summarize()
        metrics = transfer_metrics(system)
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)

    return {
        "recognition_bias_enabled": bool(recognition_bias_enabled),
        "summary": {
            "exact_matches": int(summary["exact_matches"]),
            "mean_bit_accuracy": round(float(summary["mean_bit_accuracy"]), 4),
            "mean_route_cost": round(float(summary["mean_route_cost"]), 5),
        },
        "transfer_metrics": {
            "best_rolling_exact_rate": float(metrics["best_rolling_exact_rate"]),
            "best_rolling_bit_accuracy": float(metrics["best_rolling_bit_accuracy"]),
        },
        "source_route_decision_count": len(source_records),
        "source_route_decisions": source_records,
    }


def evaluate_phase8_transfer_selector_interaction(
    *,
    seed: int = 13,
    output_path: Path | None = None,
) -> dict[str, object]:
    enabled = _run_transfer_with_selector_probe(
        seed=seed,
        recognition_bias_enabled=True,
    )
    disabled = _run_transfer_with_selector_probe(
        seed=seed,
        recognition_bias_enabled=False,
    )
    result = {
        "seed": int(seed),
        "train_scenario": TRAIN_SCENARIO,
        "transfer_scenario": TRANSFER_SCENARIO,
        "recognition_bias_enabled": enabled,
        "recognition_bias_disabled": disabled,
    }
    if output_path is not None:
        manifest = build_run_manifest(
            harness="phase8_transfer_selector_interaction",
            seeds=(seed,),
            scenarios=(f"{TRAIN_SCENARIO}->{TRANSFER_SCENARIO}",),
            metadata={},
            result=result,
        )
        write_run_manifest(output_path, manifest)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnose source selector interaction terms during warm transfer."
    )
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--output", type=str)
    args = parser.parse_args()

    result = evaluate_phase8_transfer_selector_interaction(
        seed=args.seed,
        output_path=Path(args.output) if args.output else None,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
