from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from statistics import mean

from phase8 import (
    NativeSubstrateSystem,
    phase8_scenarios,
)


ROOT = Path(__file__).resolve().parent
SCENARIOS = phase8_scenarios()


def build_system(
    seed: int,
    scenario_name: str = "branch_pressure",
    **system_kwargs,
) -> NativeSubstrateSystem:
    scenario = SCENARIOS[scenario_name]
    return NativeSubstrateSystem(
        adjacency=scenario.adjacency,
        positions=scenario.positions,
        source_id=scenario.source_id,
        sink_id=scenario.sink_id,
        selector_seed=seed,
        packet_ttl=scenario.packet_ttl,
        source_admission_policy=scenario.source_admission_policy,
        source_admission_rate=scenario.source_admission_rate,
        source_admission_min_rate=scenario.source_admission_min_rate,
        source_admission_max_rate=scenario.source_admission_max_rate,
        **system_kwargs,
    )


def run_workload(
    system: NativeSubstrateSystem,
    scenario_name: str = "branch_pressure",
) -> dict[str, object]:
    scenario = SCENARIOS[scenario_name]
    result = system.run_workload(
        cycles=scenario.cycles,
        initial_packets=scenario.initial_packets,
        packet_schedule=scenario.packet_schedule,
        initial_signal_specs=scenario.initial_signal_specs,
        signal_schedule_specs=scenario.signal_schedule_specs,
    )
    return result["summary"]


def compare_for_seed(seed: int, scenario_name: str = "branch_pressure") -> dict[str, object]:
    training = build_system(seed, scenario_name)
    training_summary = run_workload(training, scenario_name)

    base_dir = ROOT / "tests_tmp" / f"comparison_{uuid.uuid4().hex}"
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

    return {
        "scenario": scenario_name,
        "seed": seed,
        "training": training_summary,
        "cold": cold_summary,
        "warm_full": warm_full_summary,
        "warm_substrate": warm_substrate_summary,
        "delta_full": {
            "delivered_packets": warm_full_summary["delivered_packets"] - cold_summary["delivered_packets"],
            "delivery_ratio": round(warm_full_summary["delivery_ratio"] - cold_summary["delivery_ratio"], 4),
            "mean_latency": round(warm_full_summary["mean_latency"] - cold_summary["mean_latency"], 4),
            "mean_route_cost": round(warm_full_summary["mean_route_cost"] - cold_summary["mean_route_cost"], 5),
            "node_atp_total": round(warm_full_summary["node_atp_total"] - cold_summary["node_atp_total"], 4),
            "dropped_packets": warm_full_summary["dropped_packets"] - cold_summary["dropped_packets"],
            "exact_matches": warm_full_summary["exact_matches"] - cold_summary["exact_matches"],
            "mean_bit_accuracy": round(warm_full_summary["mean_bit_accuracy"] - cold_summary["mean_bit_accuracy"], 4),
        },
        "delta_substrate": {
            "delivered_packets": warm_substrate_summary["delivered_packets"] - cold_summary["delivered_packets"],
            "delivery_ratio": round(warm_substrate_summary["delivery_ratio"] - cold_summary["delivery_ratio"], 4),
            "mean_latency": round(warm_substrate_summary["mean_latency"] - cold_summary["mean_latency"], 4),
            "mean_route_cost": round(warm_substrate_summary["mean_route_cost"] - cold_summary["mean_route_cost"], 5),
            "node_atp_total": round(warm_substrate_summary["node_atp_total"] - cold_summary["node_atp_total"], 4),
            "dropped_packets": warm_substrate_summary["dropped_packets"] - cold_summary["dropped_packets"],
            "exact_matches": warm_substrate_summary["exact_matches"] - cold_summary["exact_matches"],
            "mean_bit_accuracy": round(
                warm_substrate_summary["mean_bit_accuracy"] - cold_summary["mean_bit_accuracy"],
                4,
            ),
        },
    }


def aggregate(results: list[dict[str, object]]) -> dict[str, float]:
    return {
        "avg_cold_delivered": round(mean(item["cold"]["delivered_packets"] for item in results), 4),
        "avg_warm_full_delivered": round(mean(item["warm_full"]["delivered_packets"] for item in results), 4),
        "avg_warm_substrate_delivered": round(mean(item["warm_substrate"]["delivered_packets"] for item in results), 4),
        "avg_delta_full_delivered": round(mean(item["delta_full"]["delivered_packets"] for item in results), 4),
        "avg_delta_substrate_delivered": round(mean(item["delta_substrate"]["delivered_packets"] for item in results), 4),
        "avg_cold_latency": round(mean(item["cold"]["mean_latency"] for item in results), 4),
        "avg_warm_full_latency": round(mean(item["warm_full"]["mean_latency"] for item in results), 4),
        "avg_warm_substrate_latency": round(mean(item["warm_substrate"]["mean_latency"] for item in results), 4),
        "avg_delta_full_latency": round(mean(item["delta_full"]["mean_latency"] for item in results), 4),
        "avg_delta_substrate_latency": round(mean(item["delta_substrate"]["mean_latency"] for item in results), 4),
        "avg_cold_route_cost": round(mean(item["cold"]["mean_route_cost"] for item in results), 5),
        "avg_warm_full_route_cost": round(mean(item["warm_full"]["mean_route_cost"] for item in results), 5),
        "avg_warm_substrate_route_cost": round(mean(item["warm_substrate"]["mean_route_cost"] for item in results), 5),
        "avg_delta_full_route_cost": round(mean(item["delta_full"]["mean_route_cost"] for item in results), 5),
        "avg_delta_substrate_route_cost": round(mean(item["delta_substrate"]["mean_route_cost"] for item in results), 5),
        "avg_cold_dropped": round(mean(item["cold"]["dropped_packets"] for item in results), 4),
        "avg_warm_full_dropped": round(mean(item["warm_full"]["dropped_packets"] for item in results), 4),
        "avg_warm_substrate_dropped": round(mean(item["warm_substrate"]["dropped_packets"] for item in results), 4),
        "avg_delta_full_dropped": round(mean(item["delta_full"]["dropped_packets"] for item in results), 4),
        "avg_delta_substrate_dropped": round(mean(item["delta_substrate"]["dropped_packets"] for item in results), 4),
        "avg_cold_atp": round(mean(item["cold"]["node_atp_total"] for item in results), 4),
        "avg_warm_full_atp": round(mean(item["warm_full"]["node_atp_total"] for item in results), 4),
        "avg_warm_substrate_atp": round(mean(item["warm_substrate"]["node_atp_total"] for item in results), 4),
        "avg_delta_full_atp": round(mean(item["delta_full"]["node_atp_total"] for item in results), 4),
        "avg_delta_substrate_atp": round(mean(item["delta_substrate"]["node_atp_total"] for item in results), 4),
        "avg_cold_source_admission": round(mean(item["cold"]["mean_source_admission"] for item in results), 4),
        "avg_warm_full_source_admission": round(mean(item["warm_full"]["mean_source_admission"] for item in results), 4),
        "avg_warm_substrate_source_admission": round(mean(item["warm_substrate"]["mean_source_admission"] for item in results), 4),
        "avg_cold_admission_support": round(mean(item["cold"]["source_admission_support"] for item in results), 4),
        "avg_warm_full_admission_support": round(mean(item["warm_full"]["source_admission_support"] for item in results), 4),
        "avg_warm_substrate_admission_support": round(mean(item["warm_substrate"]["source_admission_support"] for item in results), 4),
        "avg_cold_source_efficiency": round(mean(item["cold"]["mean_source_efficiency"] for item in results), 4),
        "avg_warm_full_source_efficiency": round(mean(item["warm_full"]["mean_source_efficiency"] for item in results), 4),
        "avg_warm_substrate_source_efficiency": round(mean(item["warm_substrate"]["mean_source_efficiency"] for item in results), 4),
        "avg_cold_overload_events": round(mean(item["cold"]["overload_events"] for item in results), 4),
        "avg_warm_full_overload_events": round(mean(item["warm_full"]["overload_events"] for item in results), 4),
        "avg_warm_substrate_overload_events": round(mean(item["warm_substrate"]["overload_events"] for item in results), 4),
        "avg_cold_exact_matches": round(mean(item["cold"]["exact_matches"] for item in results), 4),
        "avg_warm_full_exact_matches": round(mean(item["warm_full"]["exact_matches"] for item in results), 4),
        "avg_warm_substrate_exact_matches": round(mean(item["warm_substrate"]["exact_matches"] for item in results), 4),
        "avg_cold_bit_accuracy": round(mean(item["cold"]["mean_bit_accuracy"] for item in results), 4),
        "avg_warm_full_bit_accuracy": round(mean(item["warm_full"]["mean_bit_accuracy"] for item in results), 4),
        "avg_warm_substrate_bit_accuracy": round(mean(item["warm_substrate"]["mean_bit_accuracy"] for item in results), 4),
        "avg_cold_feedback_award": round(mean(item["cold"]["mean_feedback_award"] for item in results), 4),
        "avg_warm_full_feedback_award": round(mean(item["warm_full"]["mean_feedback_award"] for item in results), 4),
        "avg_warm_substrate_feedback_award": round(mean(item["warm_substrate"]["mean_feedback_award"] for item in results), 4),
    }


def main() -> None:
    seeds = [13, 23, 37, 51, 79]
    scenario_results = {}
    for scenario_name in (
        "branch_pressure",
        "sustained_pressure",
        "detour_resilience",
        "cvt1_task_a_stage1",
    ):
        results = [compare_for_seed(seed, scenario_name) for seed in seeds]
        scenario_results[scenario_name] = {
            "description": SCENARIOS[scenario_name].description,
            "workload": {
                "cycles": SCENARIOS[scenario_name].cycles,
                "initial_packets": SCENARIOS[scenario_name].initial_packets,
                "packet_schedule": SCENARIOS[scenario_name].packet_schedule,
                "initial_signal_specs": len(SCENARIOS[scenario_name].initial_signal_specs),
                "signal_schedule_cycles": sorted((SCENARIOS[scenario_name].signal_schedule_specs or {}).keys()),
                "packet_ttl": SCENARIOS[scenario_name].packet_ttl,
                "source_admission_policy": SCENARIOS[scenario_name].source_admission_policy,
                "source_admission_rate": SCENARIOS[scenario_name].source_admission_rate,
                "source_admission_min_rate": SCENARIOS[scenario_name].source_admission_min_rate,
                "source_admission_max_rate": SCENARIOS[scenario_name].source_admission_max_rate,
            },
            "results": results,
            "aggregate": aggregate(results),
        }

    all_results = [
        result
        for scenario in scenario_results.values()
        for result in scenario["results"]
    ]
    summary = {
        "scenarios": scenario_results,
        "overall_aggregate": aggregate(all_results),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

