from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from statistics import mean

from phase8.environment import _expected_transform_for_task
from scripts.compare_cold_warm import ROOT, SCENARIOS, build_system, run_workload


TRAIN_SCENARIO = "cvt1_task_a_stage1"
TRANSFER_SCENARIO = "cvt1_task_b_stage1"
CRITERION_WINDOW = 8
EXACT_THRESHOLD = 0.85
BIT_ACCURACY_THRESHOLD = 0.95
ADAPTATION_STREAK = 3


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


def _final_transform(packet: object) -> str:
    trace = getattr(packet, "transform_trace", None) or []
    if trace:
        return str(trace[-1])
    return "identity"


def _mean_or_none(values: list[float | int | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    if not present:
        return None
    return round(mean(present), 4)


def _first_sustained_index(
    values: list[bool],
    *,
    streak: int,
) -> int | None:
    if streak <= 1:
        for index, matched in enumerate(values):
            if matched:
                return index
        return None
    for start in range(0, len(values) - streak + 1):
        window = values[start : start + streak]
        if all(window):
            return start
    return None


def _anticipation_metrics(system) -> dict[str, object]:
    source_id = system.environment.source_id
    route_entry_count = 0
    recognized_route_entry_count = 0
    recognized_source_route_entry_count = 0
    recognized_source_transform_entry_count = 0
    predicted_route_entry_count = 0
    predicted_source_route_entry_count = 0
    first_recognized_route_cycle = None
    first_recognized_source_route_cycle = None
    first_recognized_source_transform_cycle = None
    first_predicted_route_cycle = None
    first_predicted_source_route_cycle = None

    for agent in system.agents.values():
        is_source = agent.node_id == source_id
        for entry in agent.engine.memory.entries:
            action = str(entry.action)
            if not action.startswith("route"):
                continue
            route_entry_count += 1
            recognition = getattr(entry, "recognition", None)
            if recognition is not None and recognition.matches:
                recognized_route_entry_count += 1
                if first_recognized_route_cycle is None:
                    first_recognized_route_cycle = int(entry.cycle)
                if is_source:
                    recognized_source_route_entry_count += 1
                    if first_recognized_source_route_cycle is None:
                        first_recognized_source_route_cycle = int(entry.cycle)
                    if any(
                        match.source in ("transform_attractor", "context_transform_attractor")
                        for match in recognition.matches
                    ):
                        recognized_source_transform_entry_count += 1
                        if first_recognized_source_transform_cycle is None:
                            first_recognized_source_transform_cycle = int(entry.cycle)
            prediction = getattr(entry, "prediction", None)
            if prediction is not None:
                predicted_route_entry_count += 1
                if first_predicted_route_cycle is None:
                    first_predicted_route_cycle = int(entry.cycle)
                if is_source:
                    predicted_source_route_entry_count += 1
                    if first_predicted_source_route_cycle is None:
                        first_predicted_source_route_cycle = int(entry.cycle)

    return {
        "route_entry_count": route_entry_count,
        "recognized_route_entry_count": recognized_route_entry_count,
        "recognized_source_route_entry_count": recognized_source_route_entry_count,
        "recognized_source_transform_entry_count": recognized_source_transform_entry_count,
        "predicted_route_entry_count": predicted_route_entry_count,
        "predicted_source_route_entry_count": predicted_source_route_entry_count,
        "first_recognized_route_cycle": first_recognized_route_cycle,
        "first_recognized_source_route_cycle": first_recognized_source_route_cycle,
        "first_recognized_source_transform_cycle": first_recognized_source_transform_cycle,
        "first_predicted_route_cycle": first_predicted_route_cycle,
        "first_predicted_source_route_cycle": first_predicted_source_route_cycle,
    }


def transfer_metrics(system) -> dict[str, object]:
    packets = _ordered_scored_packets(system)
    if not packets:
        return {
            "packets_evaluated": 0,
            "criterion_window": CRITERION_WINDOW,
            "criterion_reached": False,
            "examples_to_criterion": None,
            "cycles_to_criterion": None,
            "best_rolling_exact_rate": 0.0,
            "best_rolling_bit_accuracy": 0.0,
            "first_exact_match_example": None,
            "first_exact_match_cycle": None,
            "first_expected_transform_example": None,
            "first_expected_transform_cycle": None,
            "first_sustained_expected_transform_example": None,
            "first_sustained_expected_transform_cycle": None,
            "early_window_examples": 0,
            "early_window_exact_rate": 0.0,
            "early_window_bit_accuracy": 0.0,
            "early_window_wrong_transform_family": 0,
            "early_window_wrong_transform_family_rate": 0.0,
            "anticipation": _anticipation_metrics(system),
        }

    best_exact = 0.0
    best_accuracy = 0.0
    examples_to_criterion = None
    cycles_to_criterion = None
    first_exact_match_example = None
    first_exact_match_cycle = None
    first_expected_transform_example = None
    first_expected_transform_cycle = None
    expected_transform_matches: list[bool] = []
    early_window = packets[:CRITERION_WINDOW]
    early_wrong_transform_family = 0
    for example_index, packet in enumerate(packets, start=1):
        expected_transform = _expected_transform_for_task(
            getattr(packet, "task_id", None),
            getattr(packet, "context_bit", None),
        )
        final_transform = _final_transform(packet)
        expected_match = (
            expected_transform is not None and final_transform == expected_transform
        )
        expected_transform_matches.append(expected_match)
        if expected_match and first_expected_transform_example is None:
            first_expected_transform_example = example_index
            first_expected_transform_cycle = getattr(packet, "delivered_cycle", None)
        if bool(getattr(packet, "matched_target", False)) and first_exact_match_example is None:
            first_exact_match_example = example_index
            first_exact_match_cycle = getattr(packet, "delivered_cycle", None)
    sustained_index = _first_sustained_index(
        expected_transform_matches,
        streak=ADAPTATION_STREAK,
    )
    first_sustained_expected_transform_example = (
        None if sustained_index is None else sustained_index + 1
    )
    first_sustained_expected_transform_cycle = (
        None
        if sustained_index is None
        else getattr(packets[sustained_index], "delivered_cycle", None)
    )
    for end in range(CRITERION_WINDOW, len(packets) + 1):
        window = packets[end - CRITERION_WINDOW : end]
        exact_rate = sum(1 for packet in window if packet.matched_target) / CRITERION_WINDOW
        bit_accuracy = sum(float(packet.bit_match_ratio or 0.0) for packet in window) / CRITERION_WINDOW
        best_exact = max(best_exact, exact_rate)
        best_accuracy = max(best_accuracy, bit_accuracy)
        if (
            examples_to_criterion is None
            and exact_rate >= EXACT_THRESHOLD
            and bit_accuracy >= BIT_ACCURACY_THRESHOLD
        ):
            examples_to_criterion = end
            cycles_to_criterion = window[-1].delivered_cycle
    for packet in early_window:
        expected_transform = _expected_transform_for_task(
            getattr(packet, "task_id", None),
            getattr(packet, "context_bit", None),
        )
        final_transform = _final_transform(packet)
        if expected_transform is not None and final_transform != expected_transform:
            early_wrong_transform_family += 1

    return {
        "packets_evaluated": len(packets),
        "criterion_window": CRITERION_WINDOW,
        "criterion_reached": examples_to_criterion is not None,
        "examples_to_criterion": examples_to_criterion,
        "cycles_to_criterion": cycles_to_criterion,
        "best_rolling_exact_rate": round(best_exact, 4),
        "best_rolling_bit_accuracy": round(best_accuracy, 4),
        "first_exact_match_example": first_exact_match_example,
        "first_exact_match_cycle": first_exact_match_cycle,
        "first_expected_transform_example": first_expected_transform_example,
        "first_expected_transform_cycle": first_expected_transform_cycle,
        "first_sustained_expected_transform_example": (
            first_sustained_expected_transform_example
        ),
        "first_sustained_expected_transform_cycle": (
            first_sustained_expected_transform_cycle
        ),
        "early_window_examples": len(early_window),
        "early_window_exact_rate": round(
            sum(1 for packet in early_window if packet.matched_target)
            / max(1, len(early_window)),
            4,
        ),
        "early_window_bit_accuracy": round(
            sum(float(packet.bit_match_ratio or 0.0) for packet in early_window)
            / max(1, len(early_window)),
            4,
        ),
        "early_window_wrong_transform_family": early_wrong_transform_family,
        "early_window_wrong_transform_family_rate": round(
            early_wrong_transform_family / max(1, len(early_window)),
            4,
        ),
        "anticipation": _anticipation_metrics(system),
    }


def _context_stat(summary: dict[str, object], context_key: str, field: str) -> float:
    return float(summary.get("task_diagnostics", {}).get("contexts", {}).get(context_key, {}).get(field, 0.0))


def _overall_stat(summary: dict[str, object], field: str) -> float:
    return float(summary.get("task_diagnostics", {}).get("overall", {}).get(field, 0.0))


def _run_transfer_system(seed: int, scenario_name: str):
    system = build_system(seed, scenario_name)
    summary = run_workload(system, scenario_name)
    metrics = transfer_metrics(system)
    return system, summary, metrics


def transfer_for_seed(seed: int) -> dict[str, object]:
    training, training_summary, training_metrics = _run_transfer_system(seed, TRAIN_SCENARIO)

    base_dir = ROOT / "tests_tmp" / f"transfer_{uuid.uuid4().hex}"
    full_dir = base_dir / "full"
    substrate_dir = base_dir / "substrate"
    full_dir.mkdir(parents=True, exist_ok=True)
    substrate_dir.mkdir(parents=True, exist_ok=True)
    try:
        training.save_memory_carryover(full_dir)
        training.save_substrate_carryover(substrate_dir)

        cold_task_b, cold_summary, cold_metrics = _run_transfer_system(seed, TRANSFER_SCENARIO)

        warm_full = build_system(seed, TRANSFER_SCENARIO)
        warm_full.load_memory_carryover(full_dir)
        warm_full_summary = run_workload(warm_full, TRANSFER_SCENARIO)
        warm_full_metrics = transfer_metrics(warm_full)

        warm_substrate = build_system(seed, TRANSFER_SCENARIO)
        warm_substrate.load_substrate_carryover(substrate_dir)
        warm_substrate_summary = run_workload(warm_substrate, TRANSFER_SCENARIO)
        warm_substrate_metrics = transfer_metrics(warm_substrate)
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)

    return {
        "seed": seed,
        "train_scenario": TRAIN_SCENARIO,
        "transfer_scenario": TRANSFER_SCENARIO,
        "training_task_a": {
            "summary": training_summary,
            "transfer_metrics": training_metrics,
        },
        "cold_task_b": {
            "summary": cold_summary,
            "transfer_metrics": cold_metrics,
        },
        "warm_full_task_b": {
            "summary": warm_full_summary,
            "transfer_metrics": warm_full_metrics,
        },
        "warm_substrate_task_b": {
            "summary": warm_substrate_summary,
            "transfer_metrics": warm_substrate_metrics,
        },
        "delta_full_task_b": {
            "exact_matches": warm_full_summary["exact_matches"] - cold_summary["exact_matches"],
            "mean_bit_accuracy": round(
                warm_full_summary["mean_bit_accuracy"] - cold_summary["mean_bit_accuracy"],
                4,
            ),
            "mean_route_cost": round(
                warm_full_summary["mean_route_cost"] - cold_summary["mean_route_cost"],
                5,
            ),
            "best_rolling_exact_rate": round(
                warm_full_metrics["best_rolling_exact_rate"] - cold_metrics["best_rolling_exact_rate"],
                4,
            ),
            "best_rolling_bit_accuracy": round(
                warm_full_metrics["best_rolling_bit_accuracy"] - cold_metrics["best_rolling_bit_accuracy"],
                4,
            ),
        },
        "delta_substrate_task_b": {
            "exact_matches": warm_substrate_summary["exact_matches"] - cold_summary["exact_matches"],
            "mean_bit_accuracy": round(
                warm_substrate_summary["mean_bit_accuracy"] - cold_summary["mean_bit_accuracy"],
                4,
            ),
            "mean_route_cost": round(
                warm_substrate_summary["mean_route_cost"] - cold_summary["mean_route_cost"],
                5,
            ),
            "best_rolling_exact_rate": round(
                warm_substrate_metrics["best_rolling_exact_rate"] - cold_metrics["best_rolling_exact_rate"],
                4,
            ),
            "best_rolling_bit_accuracy": round(
                warm_substrate_metrics["best_rolling_bit_accuracy"] - cold_metrics["best_rolling_bit_accuracy"],
                4,
            ),
        },
    }


def aggregate_transfer(results: list[dict[str, object]]) -> dict[str, float]:
    return {
        "avg_cold_task_b_exact_matches": round(mean(item["cold_task_b"]["summary"]["exact_matches"] for item in results), 4),
        "avg_warm_full_task_b_exact_matches": round(mean(item["warm_full_task_b"]["summary"]["exact_matches"] for item in results), 4),
        "avg_warm_substrate_task_b_exact_matches": round(mean(item["warm_substrate_task_b"]["summary"]["exact_matches"] for item in results), 4),
        "avg_cold_task_b_bit_accuracy": round(mean(item["cold_task_b"]["summary"]["mean_bit_accuracy"] for item in results), 4),
        "avg_warm_full_task_b_bit_accuracy": round(mean(item["warm_full_task_b"]["summary"]["mean_bit_accuracy"] for item in results), 4),
        "avg_warm_substrate_task_b_bit_accuracy": round(mean(item["warm_substrate_task_b"]["summary"]["mean_bit_accuracy"] for item in results), 4),
        "avg_cold_task_b_route_cost": round(mean(item["cold_task_b"]["summary"]["mean_route_cost"] for item in results), 5),
        "avg_warm_full_task_b_route_cost": round(mean(item["warm_full_task_b"]["summary"]["mean_route_cost"] for item in results), 5),
        "avg_warm_substrate_task_b_route_cost": round(mean(item["warm_substrate_task_b"]["summary"]["mean_route_cost"] for item in results), 5),
        "avg_delta_full_task_b_exact_matches": round(mean(item["delta_full_task_b"]["exact_matches"] for item in results), 4),
        "avg_delta_substrate_task_b_exact_matches": round(mean(item["delta_substrate_task_b"]["exact_matches"] for item in results), 4),
        "avg_delta_full_task_b_bit_accuracy": round(mean(item["delta_full_task_b"]["mean_bit_accuracy"] for item in results), 4),
        "avg_delta_substrate_task_b_bit_accuracy": round(mean(item["delta_substrate_task_b"]["mean_bit_accuracy"] for item in results), 4),
        "avg_delta_full_task_b_best_exact_rate": round(mean(item["delta_full_task_b"]["best_rolling_exact_rate"] for item in results), 4),
        "avg_delta_substrate_task_b_best_exact_rate": round(mean(item["delta_substrate_task_b"]["best_rolling_exact_rate"] for item in results), 4),
        "avg_delta_full_task_b_best_bit_accuracy": round(mean(item["delta_full_task_b"]["best_rolling_bit_accuracy"] for item in results), 4),
        "avg_delta_substrate_task_b_best_bit_accuracy": round(mean(item["delta_substrate_task_b"]["best_rolling_bit_accuracy"] for item in results), 4),
        "avg_cold_task_b_early_exact_rate": round(mean(item["cold_task_b"]["transfer_metrics"]["early_window_exact_rate"] for item in results), 4),
        "avg_warm_full_task_b_early_exact_rate": round(mean(item["warm_full_task_b"]["transfer_metrics"]["early_window_exact_rate"] for item in results), 4),
        "avg_warm_substrate_task_b_early_exact_rate": round(mean(item["warm_substrate_task_b"]["transfer_metrics"]["early_window_exact_rate"] for item in results), 4),
        "avg_cold_task_b_early_wrong_transform_family_rate": round(mean(item["cold_task_b"]["transfer_metrics"]["early_window_wrong_transform_family_rate"] for item in results), 4),
        "avg_warm_full_task_b_early_wrong_transform_family_rate": round(mean(item["warm_full_task_b"]["transfer_metrics"]["early_window_wrong_transform_family_rate"] for item in results), 4),
        "avg_warm_substrate_task_b_early_wrong_transform_family_rate": round(mean(item["warm_substrate_task_b"]["transfer_metrics"]["early_window_wrong_transform_family_rate"] for item in results), 4),
        "avg_warm_full_task_b_first_expected_transform_example": _mean_or_none([item["warm_full_task_b"]["transfer_metrics"]["first_expected_transform_example"] for item in results]),
        "avg_cold_task_b_first_expected_transform_example": _mean_or_none([item["cold_task_b"]["transfer_metrics"]["first_expected_transform_example"] for item in results]),
        "avg_warm_full_task_b_recognized_source_transform_entries": round(mean(float(item["warm_full_task_b"]["transfer_metrics"]["anticipation"]["recognized_source_transform_entry_count"]) for item in results), 4),
        "avg_warm_full_task_b_predicted_route_entries": round(mean(float(item["warm_full_task_b"]["transfer_metrics"]["anticipation"]["predicted_route_entry_count"]) for item in results), 4),
        "avg_cold_task_b_context_1_bit_accuracy": round(mean(_context_stat(item["cold_task_b"]["summary"], "context_1", "mean_bit_accuracy") for item in results), 4),
        "avg_warm_full_task_b_context_1_bit_accuracy": round(mean(_context_stat(item["warm_full_task_b"]["summary"], "context_1", "mean_bit_accuracy") for item in results), 4),
        "avg_warm_substrate_task_b_context_1_bit_accuracy": round(mean(_context_stat(item["warm_substrate_task_b"]["summary"], "context_1", "mean_bit_accuracy") for item in results), 4),
        "avg_cold_task_b_wrong_transform_family": round(mean(_overall_stat(item["cold_task_b"]["summary"], "wrong_transform_family") for item in results), 4),
        "avg_warm_full_task_b_wrong_transform_family": round(mean(_overall_stat(item["warm_full_task_b"]["summary"], "wrong_transform_family") for item in results), 4),
        "avg_warm_substrate_task_b_wrong_transform_family": round(mean(_overall_stat(item["warm_substrate_task_b"]["summary"], "wrong_transform_family") for item in results), 4),
        "avg_cold_task_b_identity_fallbacks": round(mean(_overall_stat(item["cold_task_b"]["summary"], "identity_fallbacks") for item in results), 4),
        "avg_warm_full_task_b_identity_fallbacks": round(mean(_overall_stat(item["warm_full_task_b"]["summary"], "identity_fallbacks") for item in results), 4),
        "avg_warm_substrate_task_b_identity_fallbacks": round(mean(_overall_stat(item["warm_substrate_task_b"]["summary"], "identity_fallbacks") for item in results), 4),
        "avg_cold_task_b_stale_support_suspicions": round(mean(_overall_stat(item["cold_task_b"]["summary"], "stale_context_support_suspicions") for item in results), 4),
        "avg_warm_full_task_b_stale_support_suspicions": round(mean(_overall_stat(item["warm_full_task_b"]["summary"], "stale_context_support_suspicions") for item in results), 4),
        "avg_warm_substrate_task_b_stale_support_suspicions": round(mean(_overall_stat(item["warm_substrate_task_b"]["summary"], "stale_context_support_suspicions") for item in results), 4),
    }


def main() -> None:
    seeds = [13, 23, 37, 51, 79]
    results = [transfer_for_seed(seed) for seed in seeds]
    summary = {
        "train_scenario": TRAIN_SCENARIO,
        "transfer_scenario": TRANSFER_SCENARIO,
        "criterion_window": CRITERION_WINDOW,
        "exact_threshold": EXACT_THRESHOLD,
        "bit_accuracy_threshold": BIT_ACCURACY_THRESHOLD,
        "results": results,
        "aggregate": aggregate_transfer(results),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

