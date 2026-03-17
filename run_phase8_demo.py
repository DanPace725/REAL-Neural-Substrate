from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path
from pprint import pprint

from compare_cold_warm import SCENARIOS, aggregate, build_system, compare_for_seed, run_workload
from compare_task_transfer import transfer_for_seed


ROOT = Path(__file__).resolve().parent


def _compact(summary: dict[str, object]) -> dict[str, object]:
    return {
        "delivered_packets": summary["delivered_packets"],
        "delivery_ratio": summary["delivery_ratio"],
        "dropped_packets": summary["dropped_packets"],
        "drop_ratio": summary["drop_ratio"],
        "exact_matches": summary["exact_matches"],
        "partial_matches": summary["partial_matches"],
        "mean_bit_accuracy": summary["mean_bit_accuracy"],
        "mean_feedback_award": summary["mean_feedback_award"],
        "source_buffer": summary["source_buffer"],
        "mean_latency": summary["mean_latency"],
        "mean_route_cost": summary["mean_route_cost"],
        "node_atp_total": summary["node_atp_total"],
        "admitted_packets": summary["admitted_packets"],
        "mean_source_admission": summary["mean_source_admission"],
        "last_source_admission": summary["last_source_admission"],
        "source_admission_support": summary["source_admission_support"],
        "source_admission_velocity": summary["source_admission_velocity"],
        "mean_source_efficiency": summary["mean_source_efficiency"],
        "last_source_efficiency": summary["last_source_efficiency"],
        "overload_events": summary["overload_events"],
        "max_inbox_depth": summary["max_inbox_depth"],
        "max_source_backlog": summary["max_source_backlog"],
    }


def _task_diagnostic_compact(summary: dict[str, object]) -> dict[str, object]:
    diagnostics = summary.get("task_diagnostics", {})
    return {
        "overall": diagnostics.get("overall", {}),
        "contexts": diagnostics.get("contexts", {}),
        "admission": diagnostics.get("admission", {}),
    }


def run_comparison_demo(seed: int, scenario_name: str) -> None:
    scenario = SCENARIOS[scenario_name]
    training = build_system(seed, scenario_name)
    training_summary = run_workload(training, scenario_name)

    base_dir = ROOT / "tests_tmp" / f"demo_{uuid.uuid4().hex}"
    full_dir = base_dir / "full"
    substrate_dir = base_dir / "substrate"
    full_dir.mkdir(parents=True, exist_ok=True)
    substrate_dir.mkdir(parents=True, exist_ok=True)
    try:
        training.save_memory_carryover(full_dir)
        training.save_substrate_carryover(substrate_dir)

        cold = build_system(seed, scenario_name)
        cold_summary = run_workload(cold, scenario_name)

        warm_full = build_system(seed, scenario_name)
        warm_full.load_memory_carryover(full_dir)
        warm_full_summary = run_workload(warm_full, scenario_name)

        warm_substrate = build_system(seed, scenario_name)
        warm_substrate.load_substrate_carryover(substrate_dir)
        warm_substrate_summary = run_workload(warm_substrate, scenario_name)
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)

    print("Phase 8 Scenario Comparison Demo")
    print(f"Seed: {seed}")
    print(f"Scenario: {scenario_name}")
    print(f"Description: {scenario.description}")
    print(
        "Workload: "
        f"{json.dumps({'cycles': scenario.cycles, 'initial_packets': scenario.initial_packets, 'packet_schedule': scenario.packet_schedule, 'initial_signal_specs': len(scenario.initial_signal_specs), 'signal_schedule_cycles': sorted((scenario.signal_schedule_specs or {}).keys()), 'packet_ttl': scenario.packet_ttl, 'source_admission_policy': scenario.source_admission_policy, 'source_admission_rate': scenario.source_admission_rate, 'source_admission_min_rate': scenario.source_admission_min_rate, 'source_admission_max_rate': scenario.source_admission_max_rate})}"
    )
    print()

    print("Training summary")
    pprint(_compact(training_summary))
    print("Training supports")
    pprint(training_summary["supports"])
    print("Training action supports")
    pprint(training_summary["action_supports"])
    print("Training context action supports")
    pprint(training_summary["context_action_supports"])
    print("Training substrate maintenance")
    pprint(training_summary["substrate_maintenance"])
    print("Training context breakdown")
    pprint(training_summary["context_breakdown"])
    print("Training final transforms")
    pprint(training_summary["final_transform_counts"])
    print()

    print("Evaluation summaries")
    print("Cold start")
    pprint(_compact(cold_summary))
    print("Warm full carryover")
    pprint(_compact(warm_full_summary))
    print("Warm substrate-only carryover")
    pprint(_compact(warm_substrate_summary))
    print()

    print("Interpretation")
    full_delta = {
        "delivered_packets": warm_full_summary["delivered_packets"] - cold_summary["delivered_packets"],
        "dropped_packets": warm_full_summary["dropped_packets"] - cold_summary["dropped_packets"],
        "mean_latency": round(warm_full_summary["mean_latency"] - cold_summary["mean_latency"], 4),
        "mean_route_cost": round(warm_full_summary["mean_route_cost"] - cold_summary["mean_route_cost"], 5),
    }
    substrate_delta = {
        "delivered_packets": warm_substrate_summary["delivered_packets"] - cold_summary["delivered_packets"],
        "dropped_packets": warm_substrate_summary["dropped_packets"] - cold_summary["dropped_packets"],
        "mean_latency": round(warm_substrate_summary["mean_latency"] - cold_summary["mean_latency"], 4),
        "mean_route_cost": round(warm_substrate_summary["mean_route_cost"] - cold_summary["mean_route_cost"], 5),
    }
    print(f"Full carryover delta: {full_delta}")
    print(f"Substrate-only delta: {substrate_delta}")


def run_detailed_trace(seed: int, scenario_name: str) -> None:
    scenario = SCENARIOS[scenario_name]
    system = build_system(seed, scenario_name)
    if scenario.initial_signal_specs:
        system.inject_signal_specs(scenario.initial_signal_specs)
    elif scenario.initial_packets > 0:
        system.inject_signal(count=scenario.initial_packets)
    print("Detailed trace")
    print(f"Seed: {seed}")
    print(f"Scenario: {scenario_name}")
    for cycle in range(1, scenario.cycles + 1):
        scheduled_specs = (scenario.signal_schedule_specs or {}).get(cycle)
        if scheduled_specs:
            system.inject_signal_specs(scheduled_specs)
        else:
            scheduled = scenario.packet_schedule.get(cycle, 0)
            if scheduled > 0:
                system.inject_signal(count=scheduled)
        report = system.run_global_cycle()
        if cycle == 1 or cycle % 4 == 0 or cycle == scenario.cycles:
            print(f"Cycle {cycle}")
            pprint(report["snapshot"])
            print("Supports")
            pprint(system.summarize()["supports"])
            print("Context action supports")
            pprint(system.summarize()["context_action_supports"])
            print("-" * 60)

    print("Detailed summary")
    pprint(system.summarize())


def run_stress_demo() -> None:
    seeds = [13, 23, 37, 51, 79]
    print("Phase 8 Stress Demo")
    print(f"Seeds: {seeds}")
    print()
    for scenario_name in ("branch_pressure", "sustained_pressure", "detour_resilience", "cvt1_task_a_stage1"):
        scenario = SCENARIOS[scenario_name]
        results = [compare_for_seed(seed, scenario_name) for seed in seeds]
        scenario_aggregate = aggregate(results)
        print(f"Scenario: {scenario_name}")
        print(f"Description: {scenario.description}")
        pprint(
            {
                "workload": {
                    "cycles": scenario.cycles,
                    "initial_packets": scenario.initial_packets,
                    "packet_schedule": scenario.packet_schedule,
                    "initial_signal_specs": len(scenario.initial_signal_specs),
                    "signal_schedule_cycles": sorted((scenario.signal_schedule_specs or {}).keys()),
                    "packet_ttl": scenario.packet_ttl,
                    "source_admission_policy": scenario.source_admission_policy,
                    "source_admission_rate": scenario.source_admission_rate,
                    "source_admission_min_rate": scenario.source_admission_min_rate,
                    "source_admission_max_rate": scenario.source_admission_max_rate,
                },
                "aggregate": scenario_aggregate,
            }
        )
        print("-" * 60)


def run_transfer_demo(seed: int) -> None:
    result = transfer_for_seed(seed)
    print("Phase 8 Task Transfer Demo")
    print(f"Seed: {seed}")
    print(f"Train scenario: {result['train_scenario']}")
    print(f"Transfer scenario: {result['transfer_scenario']}")
    print()
    print("Training Task A")
    pprint(_compact(result["training_task_a"]["summary"]))
    print("Training transfer metrics")
    pprint(result["training_task_a"]["transfer_metrics"])
    print()
    print("Task B evaluation")
    print("Cold Task B")
    pprint(_compact(result["cold_task_b"]["summary"]))
    pprint(result["cold_task_b"]["transfer_metrics"])
    pprint(_task_diagnostic_compact(result["cold_task_b"]["summary"]))
    print("Warm full Task B")
    pprint(_compact(result["warm_full_task_b"]["summary"]))
    pprint(result["warm_full_task_b"]["transfer_metrics"])
    pprint(_task_diagnostic_compact(result["warm_full_task_b"]["summary"]))
    print("Warm substrate-only Task B")
    pprint(_compact(result["warm_substrate_task_b"]["summary"]))
    pprint(result["warm_substrate_task_b"]["transfer_metrics"])
    pprint(_task_diagnostic_compact(result["warm_substrate_task_b"]["summary"]))
    print()
    print("Transfer deltas")
    print(f"Full carryover Task B delta: {result['delta_full_task_b']}")
    print(f"Substrate-only Task B delta: {result['delta_substrate_task_b']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 8 multi-agent substrate demo")
    parser.add_argument("--seed", type=int, default=51, help="Deterministic demo seed")
    parser.add_argument(
        "--mode",
        choices=("comparison", "detailed", "stress", "transfer"),
        default="stress",
        help="Stress runs all comparison scenarios; comparison and detailed use a single scenario; transfer runs the first Task A -> Task B transfer check.",
    )
    parser.add_argument(
        "--scenario",
        choices=tuple(SCENARIOS.keys()),
        default="branch_pressure",
        help="Scenario to use for comparison or detailed mode.",
    )
    args = parser.parse_args()

    if args.mode == "comparison":
        run_comparison_demo(args.seed, args.scenario)
    elif args.mode == "detailed":
        run_detailed_trace(args.seed, args.scenario)
    elif args.mode == "transfer":
        run_transfer_demo(args.seed)
    else:
        run_stress_demo()


if __name__ == "__main__":
    main()
