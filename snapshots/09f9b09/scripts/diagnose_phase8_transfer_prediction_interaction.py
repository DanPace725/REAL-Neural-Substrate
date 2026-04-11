from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path

from scripts.compare_cold_warm import ROOT, SCENARIOS, build_system, run_workload
from scripts.compare_task_transfer import TRAIN_SCENARIO, TRANSFER_SCENARIO, transfer_metrics
from scripts.experiment_manifest import build_run_manifest, write_run_manifest


def _set_selector_biases(
    system,
    *,
    recognition_enabled: bool,
    prediction_enabled: bool,
) -> None:
    for agent in system.agents.values():
        selector = agent.engine.selector
        selector.recognition_route_bonus = 0.12 if recognition_enabled else 0.0
        selector.recognition_route_penalty = 0.10 if recognition_enabled else 0.0
        selector.recognition_transform_bonus = 0.10 if recognition_enabled else 0.0
        selector.prediction_delta_bonus = 0.12 if prediction_enabled else 0.0
        selector.prediction_coherence_bonus = 0.08 if prediction_enabled else 0.0


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
        "prediction_delta_term",
        "prediction_coherence_term",
        "prediction_effective_confidence_term",
        "prediction_stale_family_penalty_term",
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


def _run_transfer_with_prediction_probe(
    *,
    seed: int,
    recognition_enabled: bool,
    prediction_enabled: bool,
) -> dict[str, object]:
    base_dir = ROOT / "tests_tmp" / f"prediction_interaction_{uuid.uuid4().hex}"
    carryover_dir = base_dir / "carryover"
    carryover_dir.mkdir(parents=True, exist_ok=True)
    try:
        training = build_system(seed, TRAIN_SCENARIO)
        run_workload(training, TRAIN_SCENARIO)
        training.save_memory_carryover(carryover_dir)

        system = build_system(seed, TRANSFER_SCENARIO)
        _set_selector_biases(
            system,
            recognition_enabled=recognition_enabled,
            prediction_enabled=prediction_enabled,
        )
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
            prediction = getattr(source_entry, "prediction", None)
            source_records.append(
                {
                    "cycle": int(source_entry.cycle),
                    "chosen_action": action,
                    "mode": str(source_entry.mode),
                    "prediction_confidence": None
                    if prediction is None
                    else round(float(prediction.confidence), 6),
                    "prediction_expected_delta": None
                    if prediction is None or prediction.expected_delta is None
                    else round(float(prediction.expected_delta), 6),
                    "prediction_expected_coherence": None
                    if prediction is None or prediction.expected_coherence is None
                    else round(float(prediction.expected_coherence), 6),
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
        "recognition_enabled": bool(recognition_enabled),
        "prediction_enabled": bool(prediction_enabled),
        "summary": {
            "exact_matches": int(summary["exact_matches"]),
            "mean_bit_accuracy": round(float(summary["mean_bit_accuracy"]), 4),
            "mean_route_cost": round(float(summary["mean_route_cost"]), 5),
        },
        "transfer_metrics": {
            "best_rolling_exact_rate": float(metrics["best_rolling_exact_rate"]),
            "best_rolling_bit_accuracy": float(metrics["best_rolling_bit_accuracy"]),
            "early_window_exact_rate": float(metrics["early_window_exact_rate"]),
            "early_window_wrong_transform_family_rate": float(
                metrics["early_window_wrong_transform_family_rate"]
            ),
            "anticipation": dict(metrics["anticipation"]),
        },
        "source_route_decision_count": len(source_records),
        "source_route_decisions": source_records,
    }


def _decision_deltas(
    prediction_on: dict[str, object],
    prediction_off: dict[str, object],
) -> dict[str, object]:
    on_decisions = prediction_on["source_route_decisions"]
    off_decisions = prediction_off["source_route_decisions"]
    divergence_cycles: list[int] = []
    prediction_active_cycles: list[int] = []
    limit = min(len(on_decisions), len(off_decisions))
    for index in range(limit):
        on_record = on_decisions[index]
        off_record = off_decisions[index]
        cycle = int(on_record["cycle"])
        if on_record["chosen_action"] != off_record["chosen_action"]:
            divergence_cycles.append(cycle)
        chosen_breakdown = on_record.get("chosen_breakdown", {})
        if float(chosen_breakdown.get("prediction_delta_term") or 0.0) != 0.0 or float(
            chosen_breakdown.get("prediction_coherence_term") or 0.0
        ) != 0.0:
            prediction_active_cycles.append(cycle)
    return {
        "divergence_cycles": divergence_cycles,
        "prediction_active_cycles": prediction_active_cycles,
        "first_divergence_cycle": None if not divergence_cycles else divergence_cycles[0],
        "first_prediction_active_cycle": (
            None if not prediction_active_cycles else prediction_active_cycles[0]
        ),
        "divergence_count": len(divergence_cycles),
    }


def evaluate_phase8_transfer_prediction_interaction(
    *,
    seed: int = 13,
    output_path: Path | None = None,
) -> dict[str, object]:
    prediction_on = _run_transfer_with_prediction_probe(
        seed=seed,
        recognition_enabled=True,
        prediction_enabled=True,
    )
    prediction_off = _run_transfer_with_prediction_probe(
        seed=seed,
        recognition_enabled=True,
        prediction_enabled=False,
    )
    result = {
        "seed": int(seed),
        "train_scenario": TRAIN_SCENARIO,
        "transfer_scenario": TRANSFER_SCENARIO,
        "prediction_enabled": prediction_on,
        "prediction_disabled": prediction_off,
        "decision_deltas": _decision_deltas(prediction_on, prediction_off),
    }
    if output_path is not None:
        manifest = build_run_manifest(
            harness="phase8_transfer_prediction_interaction",
            seeds=(seed,),
            scenarios=(f"{TRAIN_SCENARIO}->{TRANSFER_SCENARIO}",),
            metadata={},
            result=result,
        )
        write_run_manifest(output_path, manifest)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnose source selector prediction terms during warm transfer."
    )
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--output", type=str)
    args = parser.parse_args()

    result = evaluate_phase8_transfer_prediction_interaction(
        seed=args.seed,
        output_path=Path(args.output) if args.output else None,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
