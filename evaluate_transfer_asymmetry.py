from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from statistics import mean

from compare_cold_warm import ROOT, SCENARIOS, build_system
from compare_task_transfer import transfer_metrics


DEFAULT_SEEDS = (5, 13, 17, 23, 29, 37, 43, 51, 61, 79, 87, 97)
TASK_A = "cvt1_task_a_stage1"
TASK_B = "cvt1_task_b_stage1"


def _mean_or_none(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return round(mean(present), 5)


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 5)


def _overall_stat(summary: dict[str, object], field: str) -> float:
    return float(summary.get("task_diagnostics", {}).get("overall", {}).get(field, 0.0))


def _runtime_commitment(system) -> dict[str, float]:
    branch_context_credit = 0.0
    branch_context_debt = 0.0
    context_branch_transform_credit = 0.0
    context_branch_transform_debt = 0.0
    transform_credit = 0.0
    transform_debt = 0.0
    context_transform_credit = 0.0
    context_transform_debt = 0.0
    for state in system.environment.node_states.values():
        branch_context_credit += sum(float(value) for value in state.branch_context_credit.values())
        branch_context_debt += sum(float(value) for value in state.branch_context_debt.values())
        context_branch_transform_credit += sum(
            float(value) for value in state.context_branch_transform_credit.values()
        )
        context_branch_transform_debt += sum(
            float(value) for value in state.context_branch_transform_debt.values()
        )
        transform_credit += sum(float(value) for value in state.transform_credit.values())
        transform_debt += sum(float(value) for value in state.transform_debt.values())
        context_transform_credit += sum(
            float(value) for value in state.context_transform_credit.values()
        )
        context_transform_debt += sum(
            float(value) for value in state.context_transform_debt.values()
        )
    return {
        "branch_context_credit_total": round(branch_context_credit, 5),
        "branch_context_debt_total": round(branch_context_debt, 5),
        "context_branch_transform_credit_total": round(
            context_branch_transform_credit,
            5,
        ),
        "context_branch_transform_debt_total": round(
            context_branch_transform_debt,
            5,
        ),
        "transform_credit_total": round(transform_credit, 5),
        "transform_debt_total": round(transform_debt, 5),
        "context_transform_credit_total": round(context_transform_credit, 5),
        "context_transform_debt_total": round(context_transform_debt, 5),
    }


def _run_scenario(seed: int, scenario_name: str):
    scenario = SCENARIOS[scenario_name]
    system = build_system(seed, scenario_name)
    result = system.run_workload(
        cycles=scenario.cycles,
        initial_packets=scenario.initial_packets,
        packet_schedule=scenario.packet_schedule,
        initial_signal_specs=scenario.initial_signal_specs,
        signal_schedule_specs=scenario.signal_schedule_specs,
    )
    summary = result["summary"]
    metrics = transfer_metrics(system)
    criterion_cycle = metrics.get("cycles_to_criterion")
    cost_to_criterion = None
    if criterion_cycle is not None:
        cost_to_criterion = sum(
            float(entry.cost_secs)
            for report in result["reports"]
            if int(report["cycle"]) <= int(criterion_cycle)
            for entry in report["entries"].values()
            if entry is not None
        )
    return system, summary, metrics, _round(cost_to_criterion)


def _training_record(seed: int, scenario_name: str) -> dict[str, object]:
    system, summary, metrics, cost_to_criterion = _run_scenario(seed, scenario_name)
    return {
        "seed": seed,
        "scenario": scenario_name,
        "summary": summary,
        "metrics": metrics,
        "cost_to_criterion": cost_to_criterion,
        "commitment": _runtime_commitment(system),
    }


def _transfer_record(seed: int, train_scenario: str, transfer_scenario: str) -> dict[str, object]:
    training_system, training_summary, training_metrics, training_cost_to_criterion = _run_scenario(
        seed,
        train_scenario,
    )

    base_dir = ROOT / "tests_tmp" / f"asymmetry_{uuid.uuid4().hex}"
    full_dir = base_dir / "full"
    full_dir.mkdir(parents=True, exist_ok=True)
    try:
        training_system.save_memory_carryover(full_dir)

        cold_system, cold_summary, cold_metrics, cold_cost_to_criterion = _run_scenario(
            seed,
            transfer_scenario,
        )

        warm_system = build_system(seed, transfer_scenario)
        warm_system.load_memory_carryover(full_dir)
        scenario = SCENARIOS[transfer_scenario]
        warm_result = warm_system.run_workload(
            cycles=scenario.cycles,
            initial_packets=scenario.initial_packets,
            packet_schedule=scenario.packet_schedule,
            initial_signal_specs=scenario.initial_signal_specs,
            signal_schedule_specs=scenario.signal_schedule_specs,
        )
        warm_summary = warm_result["summary"]
        warm_metrics = transfer_metrics(warm_system)
        warm_cost_to_criterion = None
        if warm_metrics.get("cycles_to_criterion") is not None:
            warm_cost_to_criterion = sum(
                float(entry.cost_secs)
                for report in warm_result["reports"]
                if int(report["cycle"]) <= int(warm_metrics["cycles_to_criterion"])
                for entry in report["entries"].values()
                if entry is not None
            )
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)

    return {
        "seed": seed,
        "train_scenario": train_scenario,
        "transfer_scenario": transfer_scenario,
        "training": {
            "summary": training_summary,
            "metrics": training_metrics,
            "cost_to_criterion": training_cost_to_criterion,
            "commitment": _runtime_commitment(training_system),
        },
        "cold_transfer": {
            "summary": cold_summary,
            "metrics": cold_metrics,
            "cost_to_criterion": cold_cost_to_criterion,
            "commitment": _runtime_commitment(cold_system),
        },
        "warm_full_transfer": {
            "summary": warm_summary,
            "metrics": warm_metrics,
            "cost_to_criterion": _round(warm_cost_to_criterion),
            "commitment": _runtime_commitment(warm_system),
        },
    }


def _aggregate_training(records: list[dict[str, object]]) -> dict[str, object]:
    summaries = [record["summary"] for record in records]
    metrics = [record["metrics"] for record in records]
    commitments = [record["commitment"] for record in records]
    criterion_costs = [record["cost_to_criterion"] for record in records]
    return {
        "seeds": [record["seed"] for record in records],
        "criterion_hits": sum(
            1 for metric in metrics if bool(metric.get("criterion_reached"))
        ),
        "avg_examples_to_criterion": _mean_or_none(
            [metric.get("examples_to_criterion") for metric in metrics]
        ),
        "avg_cycles_to_criterion": _mean_or_none(
            [metric.get("cycles_to_criterion") for metric in metrics]
        ),
        "avg_cost_to_criterion": _mean_or_none(criterion_costs),
        "avg_cost_per_example_to_criterion": _mean_or_none(
            [
                (
                    float(record["cost_to_criterion"]) / float(record["metrics"]["examples_to_criterion"])
                    if record["cost_to_criterion"] is not None
                    and record["metrics"]["examples_to_criterion"] is not None
                    else None
                )
                for record in records
            ]
        ),
        "avg_total_action_cost": round(mean(summary["total_action_cost"] for summary in summaries), 5),
        "avg_action_cost_per_exact_match": round(
            mean(
                summary["total_action_cost"] / max(summary["exact_matches"], 1)
                for summary in summaries
            ),
            5,
        ),
        "avg_action_cost_per_bit_accuracy": round(
            mean(
                summary["total_action_cost"] / max(summary["mean_bit_accuracy"], 1e-9)
                for summary in summaries
            ),
            5,
        ),
        "avg_mean_route_cost": round(mean(summary["mean_route_cost"] for summary in summaries), 5),
        "avg_exact_matches": round(mean(summary["exact_matches"] for summary in summaries), 5),
        "avg_mean_bit_accuracy": round(mean(summary["mean_bit_accuracy"] for summary in summaries), 5),
        "avg_mean_feedback_award": round(
            mean(summary["mean_feedback_award"] for summary in summaries),
            5,
        ),
        "avg_best_rolling_exact_rate": round(
            mean(float(metric["best_rolling_exact_rate"]) for metric in metrics),
            5,
        ),
        "avg_best_rolling_bit_accuracy": round(
            mean(float(metric["best_rolling_bit_accuracy"]) for metric in metrics),
            5,
        ),
        "avg_source_efficiency": round(
            mean(summary["mean_source_efficiency"] for summary in summaries),
            5,
        ),
        "avg_branch_context_credit_total": round(
            mean(commitment["branch_context_credit_total"] for commitment in commitments),
            5,
        ),
        "avg_branch_context_debt_total": round(
            mean(commitment["branch_context_debt_total"] for commitment in commitments),
            5,
        ),
        "avg_context_branch_transform_credit_total": round(
            mean(
                commitment["context_branch_transform_credit_total"]
                for commitment in commitments
            ),
            5,
        ),
        "avg_context_branch_transform_debt_total": round(
            mean(
                commitment["context_branch_transform_debt_total"]
                for commitment in commitments
            ),
            5,
        ),
    }


def _aggregate_transfer(records: list[dict[str, object]]) -> dict[str, object]:
    cold = [record["cold_transfer"] for record in records]
    warm = [record["warm_full_transfer"] for record in records]
    return {
        "seeds": [record["seed"] for record in records],
        "avg_cold_exact_matches": round(
            mean(item["summary"]["exact_matches"] for item in cold),
            5,
        ),
        "avg_warm_full_exact_matches": round(
            mean(item["summary"]["exact_matches"] for item in warm),
            5,
        ),
        "avg_cold_action_cost_per_exact_match": round(
            mean(
                item["summary"]["total_action_cost"] / max(item["summary"]["exact_matches"], 1)
                for item in cold
            ),
            5,
        ),
        "avg_warm_full_action_cost_per_exact_match": round(
            mean(
                item["summary"]["total_action_cost"] / max(item["summary"]["exact_matches"], 1)
                for item in warm
            ),
            5,
        ),
        "avg_cold_mean_bit_accuracy": round(
            mean(item["summary"]["mean_bit_accuracy"] for item in cold),
            5,
        ),
        "avg_warm_full_mean_bit_accuracy": round(
            mean(item["summary"]["mean_bit_accuracy"] for item in warm),
            5,
        ),
        "avg_cold_action_cost_per_bit_accuracy": round(
            mean(
                item["summary"]["total_action_cost"] / max(item["summary"]["mean_bit_accuracy"], 1e-9)
                for item in cold
            ),
            5,
        ),
        "avg_warm_full_action_cost_per_bit_accuracy": round(
            mean(
                item["summary"]["total_action_cost"] / max(item["summary"]["mean_bit_accuracy"], 1e-9)
                for item in warm
            ),
            5,
        ),
        "avg_cold_cost_to_criterion": _mean_or_none(
            [item["cost_to_criterion"] for item in cold]
        ),
        "avg_warm_full_cost_to_criterion": _mean_or_none(
            [item["cost_to_criterion"] for item in warm]
        ),
        "avg_cold_stale_support": round(
            mean(_overall_stat(item["summary"], "stale_context_support_suspicions") for item in cold),
            5,
        ),
        "avg_warm_full_stale_support": round(
            mean(_overall_stat(item["summary"], "stale_context_support_suspicions") for item in warm),
            5,
        ),
        "avg_cold_wrong_transform_family": round(
            mean(_overall_stat(item["summary"], "wrong_transform_family") for item in cold),
            5,
        ),
        "avg_warm_full_wrong_transform_family": round(
            mean(_overall_stat(item["summary"], "wrong_transform_family") for item in warm),
            5,
        ),
        "avg_warm_full_branch_context_credit_total": round(
            mean(item["commitment"]["branch_context_credit_total"] for item in warm),
            5,
        ),
        "avg_warm_full_branch_context_debt_total": round(
            mean(item["commitment"]["branch_context_debt_total"] for item in warm),
            5,
        ),
        "avg_warm_full_context_branch_transform_credit_total": round(
            mean(
                item["commitment"]["context_branch_transform_credit_total"]
                for item in warm
            ),
            5,
        ),
        "avg_warm_full_context_branch_transform_debt_total": round(
            mean(
                item["commitment"]["context_branch_transform_debt_total"]
                for item in warm
            ),
            5,
        ),
    }


def evaluate_asymmetry(
    *,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
) -> dict[str, object]:
    task_a_training = [_training_record(seed, TASK_A) for seed in seeds]
    task_b_training = [_training_record(seed, TASK_B) for seed in seeds]
    a_to_b = [_transfer_record(seed, TASK_A, TASK_B) for seed in seeds]
    b_to_a = [_transfer_record(seed, TASK_B, TASK_A) for seed in seeds]

    aggregated_task_a = _aggregate_training(task_a_training)
    aggregated_task_b = _aggregate_training(task_b_training)
    aggregated_a_to_b = _aggregate_transfer(a_to_b)
    aggregated_b_to_a = _aggregate_transfer(b_to_a)

    return {
        "seeds": list(seeds),
        "training": {
            TASK_A: {
                "aggregate": aggregated_task_a,
                "results": task_a_training,
            },
            TASK_B: {
                "aggregate": aggregated_task_b,
                "results": task_b_training,
            },
            "delta_task_b_minus_task_a": {
                "avg_examples_to_criterion": _round(
                    (
                        aggregated_task_b["avg_examples_to_criterion"]
                        - aggregated_task_a["avg_examples_to_criterion"]
                    )
                    if aggregated_task_b["avg_examples_to_criterion"] is not None
                    and aggregated_task_a["avg_examples_to_criterion"] is not None
                    else None
                ),
                "avg_cycles_to_criterion": _round(
                    (
                        aggregated_task_b["avg_cycles_to_criterion"]
                        - aggregated_task_a["avg_cycles_to_criterion"]
                    )
                    if aggregated_task_b["avg_cycles_to_criterion"] is not None
                    and aggregated_task_a["avg_cycles_to_criterion"] is not None
                    else None
                ),
                "avg_cost_to_criterion": _round(
                    (
                        aggregated_task_b["avg_cost_to_criterion"]
                        - aggregated_task_a["avg_cost_to_criterion"]
                    )
                    if aggregated_task_b["avg_cost_to_criterion"] is not None
                    and aggregated_task_a["avg_cost_to_criterion"] is not None
                    else None
                ),
                "avg_total_action_cost": round(
                    aggregated_task_b["avg_total_action_cost"]
                    - aggregated_task_a["avg_total_action_cost"],
                    5,
                ),
                "avg_action_cost_per_exact_match": round(
                    aggregated_task_b["avg_action_cost_per_exact_match"]
                    - aggregated_task_a["avg_action_cost_per_exact_match"],
                    5,
                ),
                "avg_action_cost_per_bit_accuracy": round(
                    aggregated_task_b["avg_action_cost_per_bit_accuracy"]
                    - aggregated_task_a["avg_action_cost_per_bit_accuracy"],
                    5,
                ),
                "avg_branch_context_debt_total": round(
                    aggregated_task_b["avg_branch_context_debt_total"]
                    - aggregated_task_a["avg_branch_context_debt_total"],
                    5,
                ),
                "avg_context_branch_transform_debt_total": round(
                    aggregated_task_b["avg_context_branch_transform_debt_total"]
                    - aggregated_task_a["avg_context_branch_transform_debt_total"],
                    5,
                ),
            },
        },
        "transfer_pairs": {
            f"{TASK_A}->{TASK_B}": {
                "aggregate": aggregated_a_to_b,
                "results": a_to_b,
            },
            f"{TASK_B}->{TASK_A}": {
                "aggregate": aggregated_b_to_a,
                "results": b_to_a,
            },
            "delta_b_to_a_minus_a_to_b": {
                "avg_warm_full_exact_matches": round(
                    aggregated_b_to_a["avg_warm_full_exact_matches"]
                    - aggregated_a_to_b["avg_warm_full_exact_matches"],
                    5,
                ),
                "avg_warm_full_mean_bit_accuracy": round(
                    aggregated_b_to_a["avg_warm_full_mean_bit_accuracy"]
                    - aggregated_a_to_b["avg_warm_full_mean_bit_accuracy"],
                    5,
                ),
                "avg_warm_full_stale_support": round(
                    aggregated_b_to_a["avg_warm_full_stale_support"]
                    - aggregated_a_to_b["avg_warm_full_stale_support"],
                    5,
                ),
                "avg_warm_full_branch_context_debt_total": round(
                    aggregated_b_to_a["avg_warm_full_branch_context_debt_total"]
                    - aggregated_a_to_b["avg_warm_full_branch_context_debt_total"],
                    5,
                ),
                "avg_warm_full_context_branch_transform_debt_total": round(
                    aggregated_b_to_a["avg_warm_full_context_branch_transform_debt_total"]
                    - aggregated_a_to_b["avg_warm_full_context_branch_transform_debt_total"],
                    5,
                ),
            },
        },
    }


def main() -> None:
    print(json.dumps(evaluate_asymmetry(), indent=2))


if __name__ == "__main__":
    main()
