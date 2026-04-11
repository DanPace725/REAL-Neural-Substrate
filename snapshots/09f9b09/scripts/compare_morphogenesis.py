from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import asdict
from pathlib import Path
from statistics import mean

from scripts.compare_cold_warm import ROOT, SCENARIOS, build_system, run_workload
from scripts.compare_latent_context import latent_signal_specs
from scripts.compare_task_transfer import transfer_metrics
from scripts.experiment_manifest import build_run_manifest, write_run_manifest
from phase8 import MorphogenesisConfig, NativeSubstrateSystem


DEFAULT_SEEDS = (13, 23, 37, 51, 79)
WORKLOAD_SCENARIOS = (
    "branch_pressure",
    "sustained_pressure",
    "cvt1_task_b_stage1",
)
TRAIN_SCENARIO = "cvt1_task_a_stage1"
TRANSFER_SCENARIO = "cvt1_task_b_stage1"
LATENT_WORKLOAD_SCENARIOS = (
    TRAIN_SCENARIO,
    TRANSFER_SCENARIO,
)


def benchmark_morphogenesis_config() -> MorphogenesisConfig:
    return MorphogenesisConfig(
        enabled=True,
        checkpoint_interval=6,
        max_dynamic_nodes=4,
        surplus_window=2,
        contradiction_threshold=0.2,
        overload_threshold=0.2,
        atp_surplus_threshold=0.4,
        probation_feedback_threshold=0.12,
        seed_edge_support=0.40,
        seed_action_support=0.34,
        # Gate budding until context confidence is resolved to prevent
        # premature growth into unrouted topology (Priority 1 fix).
        context_resolution_growth_gate=0.55,
        # Lower upkeep so newly budded nodes survive the slow-start window,
        # and allow growth when backlog builds before ATP surplus is reached.
        dynamic_node_upkeep=0.012,
        growth_grace_ticks=4,
        anticipatory_growth_backlog_threshold=0.55,
        # Require positive feedback signal before growth fires; prevents
        # branch_pressure premature budding (routing_feedback_gate fix).
        routing_feedback_gate=0.05,
    )


def _clone_config(config: MorphogenesisConfig | None) -> MorphogenesisConfig:
    baseline = config or benchmark_morphogenesis_config()
    return MorphogenesisConfig(**asdict(baseline))


def build_growth_system(
    seed: int,
    scenario_name: str,
    *,
    morphogenesis_config: MorphogenesisConfig | None = None,
    source_sequence_context_enabled: bool = True,
    latent_transfer_split_enabled: bool = True,
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
        morphogenesis_config=_clone_config(morphogenesis_config),
        source_sequence_context_enabled=source_sequence_context_enabled,
        latent_transfer_split_enabled=latent_transfer_split_enabled,
    )


def _run_growth_workload(
    system: NativeSubstrateSystem,
    scenario_name: str,
    *,
    latent_context: bool,
) -> dict[str, object]:
    if not latent_context:
        return run_workload(system, scenario_name)
    scenario = SCENARIOS[scenario_name]
    initial_specs, schedule_specs = latent_signal_specs(scenario_name)
    result = system.run_workload(
        cycles=scenario.cycles,
        initial_packets=scenario.initial_packets,
        packet_schedule=scenario.packet_schedule,
        initial_signal_specs=initial_specs,
        signal_schedule_specs=schedule_specs,
    )
    return result["summary"]


def growth_counts_as_earned(summary: dict[str, object]) -> bool:
    if int(summary.get("bud_successes", 0)) <= 0:
        return False
    dynamic_nodes = int(summary.get("dynamic_node_count", 0))
    if dynamic_nodes > 0:
        return (
            float(summary.get("new_node_utilization", 0.0)) > 0.0
            and summary.get("time_to_first_feedback") is not None
        )
    return (
        float(summary.get("mean_feedback_award", 0.0)) > 0.0
        and int(summary.get("prune_events", 0)) < int(summary.get("bud_successes", 0))
    )


def growth_counts_as_win(
    fixed_summary: dict[str, object],
    growth_summary: dict[str, object],
) -> bool:
    if not growth_counts_as_earned(growth_summary):
        return False
    exact_delta = int(growth_summary.get("exact_matches", 0)) - int(fixed_summary.get("exact_matches", 0))
    bit_delta = float(growth_summary.get("mean_bit_accuracy", 0.0)) - float(fixed_summary.get("mean_bit_accuracy", 0.0))
    route_delta = float(growth_summary.get("mean_route_cost", 0.0)) - float(fixed_summary.get("mean_route_cost", 0.0))
    action_delta = float(growth_summary.get("total_action_cost", 0.0)) - float(fixed_summary.get("total_action_cost", 0.0))
    task_improved = exact_delta > 0 or bit_delta > 0.01
    task_non_regressed = exact_delta >= 0 and bit_delta >= -0.01
    efficiency_improved = route_delta < -1e-6 or action_delta < -1e-6
    return (
        task_improved
        or (efficiency_improved and task_non_regressed)
    )


def _summary_delta(
    fixed_summary: dict[str, object],
    growth_summary: dict[str, object],
) -> dict[str, float]:
    return {
        "exact_matches": int(growth_summary["exact_matches"]) - int(fixed_summary["exact_matches"]),
        "mean_bit_accuracy": round(
            float(growth_summary["mean_bit_accuracy"]) - float(fixed_summary["mean_bit_accuracy"]),
            4,
        ),
        "mean_route_cost": round(
            float(growth_summary["mean_route_cost"]) - float(fixed_summary["mean_route_cost"]),
            5,
        ),
        "total_action_cost": round(
            float(growth_summary["total_action_cost"]) - float(fixed_summary["total_action_cost"]),
            5,
        ),
        "bud_successes": int(growth_summary["bud_successes"]) - int(fixed_summary.get("bud_successes", 0)),
        "dynamic_node_count": int(growth_summary["dynamic_node_count"]) - int(fixed_summary.get("dynamic_node_count", 0)),
        "edge_count": int(growth_summary["edge_count"]) - int(fixed_summary["edge_count"]),
        "node_count": int(growth_summary["node_count"]) - int(fixed_summary["node_count"]),
    }


def compare_growth_for_seed(
    seed: int,
    scenario_name: str,
    *,
    morphogenesis_config: MorphogenesisConfig | None = None,
    latent_context: bool = False,
    source_sequence_context_enabled: bool = True,
    latent_transfer_split_enabled: bool = True,
) -> dict[str, object]:
    fixed_system = build_system(
        seed,
        scenario_name,
        source_sequence_context_enabled=source_sequence_context_enabled,
        latent_transfer_split_enabled=latent_transfer_split_enabled,
    )
    fixed_summary = _run_growth_workload(
        fixed_system,
        scenario_name,
        latent_context=latent_context,
    )

    growth_system = build_growth_system(
        seed,
        scenario_name,
        morphogenesis_config=morphogenesis_config,
        source_sequence_context_enabled=source_sequence_context_enabled,
        latent_transfer_split_enabled=latent_transfer_split_enabled,
    )
    growth_summary = _run_growth_workload(
        growth_system,
        scenario_name,
        latent_context=latent_context,
    )

    return {
        "seed": seed,
        "scenario": scenario_name,
        "latent_context": latent_context,
        "fixed": {
            "summary": fixed_summary,
            "transfer_metrics": transfer_metrics(fixed_system),
        },
        "growth": {
            "summary": growth_summary,
            "transfer_metrics": transfer_metrics(growth_system),
            "earned_growth": growth_counts_as_earned(growth_summary),
            "growth_win": growth_counts_as_win(fixed_summary, growth_summary),
        },
        "delta": _summary_delta(fixed_summary, growth_summary),
    }


def _mean_or_none(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return round(mean(present), 4)


def aggregate_growth_results(results: list[dict[str, object]]) -> dict[str, object]:
    return {
        "avg_fixed_exact_matches": round(mean(item["fixed"]["summary"]["exact_matches"] for item in results), 4),
        "avg_growth_exact_matches": round(mean(item["growth"]["summary"]["exact_matches"] for item in results), 4),
        "avg_delta_exact_matches": round(mean(item["delta"]["exact_matches"] for item in results), 4),
        "avg_fixed_bit_accuracy": round(mean(item["fixed"]["summary"]["mean_bit_accuracy"] for item in results), 4),
        "avg_growth_bit_accuracy": round(mean(item["growth"]["summary"]["mean_bit_accuracy"] for item in results), 4),
        "avg_delta_bit_accuracy": round(mean(item["delta"]["mean_bit_accuracy"] for item in results), 4),
        "avg_fixed_route_cost": round(mean(item["fixed"]["summary"]["mean_route_cost"] for item in results), 5),
        "avg_growth_route_cost": round(mean(item["growth"]["summary"]["mean_route_cost"] for item in results), 5),
        "avg_delta_route_cost": round(mean(item["delta"]["mean_route_cost"] for item in results), 5),
        "avg_fixed_total_action_cost": round(mean(item["fixed"]["summary"]["total_action_cost"] for item in results), 5),
        "avg_growth_total_action_cost": round(mean(item["growth"]["summary"]["total_action_cost"] for item in results), 5),
        "avg_delta_total_action_cost": round(mean(item["delta"]["total_action_cost"] for item in results), 5),
        "avg_growth_node_count": round(mean(item["growth"]["summary"]["node_count"] for item in results), 4),
        "avg_growth_edge_count": round(mean(item["growth"]["summary"]["edge_count"] for item in results), 4),
        "avg_growth_bud_successes": round(mean(item["growth"]["summary"]["bud_successes"] for item in results), 4),
        "avg_growth_prune_events": round(mean(item["growth"]["summary"]["prune_events"] for item in results), 4),
        "avg_growth_apoptosis_events": round(mean(item["growth"]["summary"]["apoptosis_events"] for item in results), 4),
        "avg_growth_dynamic_node_count": round(mean(item["growth"]["summary"]["dynamic_node_count"] for item in results), 4),
        "avg_growth_new_node_utilization": round(mean(item["growth"]["summary"]["new_node_utilization"] for item in results), 4),
        "avg_growth_dynamic_node_value": _mean_or_none(
            [item["growth"]["summary"].get("mean_dynamic_node_value") for item in results]
        ),
        "avg_growth_dynamic_net_energy": _mean_or_none(
            [item["growth"]["summary"].get("mean_dynamic_net_energy") for item in results]
        ),
        "avg_growth_dynamic_edge_value": _mean_or_none(
            [item["growth"]["summary"].get("mean_dynamic_edge_value") for item in results]
        ),
        "avg_growth_time_to_first_feedback": _mean_or_none(
            [item["growth"]["summary"]["time_to_first_feedback"] for item in results]
        ),
        "growth_realization_rate": round(
            mean(1.0 if item["growth"]["summary"]["bud_successes"] > 0 else 0.0 for item in results),
            4,
        ),
        "earned_growth_rate": round(
            mean(1.0 if item["growth"]["earned_growth"] else 0.0 for item in results),
            4,
        ),
        "growth_win_rate": round(
            mean(1.0 if item["growth"]["growth_win"] else 0.0 for item in results),
            4,
        ),
    }


def transfer_growth_for_seed(
    seed: int,
    *,
    train_scenario: str = TRAIN_SCENARIO,
    transfer_scenario: str = TRANSFER_SCENARIO,
    morphogenesis_config: MorphogenesisConfig | None = None,
    latent_context: bool = False,
    source_sequence_context_enabled: bool = True,
    latent_transfer_split_enabled: bool = True,
) -> dict[str, object]:
    fixed_training = build_system(
        seed,
        train_scenario,
        source_sequence_context_enabled=source_sequence_context_enabled,
        latent_transfer_split_enabled=latent_transfer_split_enabled,
    )
    fixed_training_summary = _run_growth_workload(
        fixed_training,
        train_scenario,
        latent_context=latent_context,
    )

    growth_training = build_growth_system(
        seed,
        train_scenario,
        morphogenesis_config=morphogenesis_config,
        source_sequence_context_enabled=source_sequence_context_enabled,
        latent_transfer_split_enabled=latent_transfer_split_enabled,
    )
    growth_training_summary = _run_growth_workload(
        growth_training,
        train_scenario,
        latent_context=latent_context,
    )

    base_dir = ROOT / "tests_tmp" / f"morphogenesis_compare_{uuid.uuid4().hex}"
    fixed_dir = base_dir / "fixed"
    growth_dir = base_dir / "growth"
    fixed_dir.mkdir(parents=True, exist_ok=True)
    growth_dir.mkdir(parents=True, exist_ok=True)
    try:
        fixed_training.save_memory_carryover(fixed_dir)
        growth_training.save_memory_carryover(growth_dir)

        fixed_transfer = build_system(
            seed,
            transfer_scenario,
            source_sequence_context_enabled=source_sequence_context_enabled,
            latent_transfer_split_enabled=latent_transfer_split_enabled,
        )
        fixed_transfer.load_memory_carryover(fixed_dir)
        fixed_transfer_summary = _run_growth_workload(
            fixed_transfer,
            transfer_scenario,
            latent_context=latent_context,
        )

        growth_transfer = build_growth_system(
            seed,
            transfer_scenario,
            morphogenesis_config=morphogenesis_config,
            source_sequence_context_enabled=source_sequence_context_enabled,
            latent_transfer_split_enabled=latent_transfer_split_enabled,
        )
        growth_transfer.load_memory_carryover(growth_dir)
        growth_transfer_summary = _run_growth_workload(
            growth_transfer,
            transfer_scenario,
            latent_context=latent_context,
        )
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)

    return {
        "seed": seed,
        "train_scenario": train_scenario,
        "transfer_scenario": transfer_scenario,
        "latent_context": latent_context,
        "fixed_training": fixed_training_summary,
        "growth_training": {
            "summary": growth_training_summary,
            "earned_growth": growth_counts_as_earned(growth_training_summary),
        },
        "fixed_transfer": {
            "summary": fixed_transfer_summary,
            "transfer_metrics": transfer_metrics(fixed_transfer),
        },
        "growth_transfer": {
            "summary": growth_transfer_summary,
            "transfer_metrics": transfer_metrics(growth_transfer),
            "earned_growth": growth_counts_as_earned(growth_transfer_summary),
            "growth_win": growth_counts_as_win(fixed_transfer_summary, growth_transfer_summary),
        },
        "delta": _summary_delta(fixed_transfer_summary, growth_transfer_summary),
    }


def aggregate_transfer_growth_results(results: list[dict[str, object]]) -> dict[str, object]:
    return {
        "avg_fixed_transfer_exact_matches": round(mean(item["fixed_transfer"]["summary"]["exact_matches"] for item in results), 4),
        "avg_growth_transfer_exact_matches": round(mean(item["growth_transfer"]["summary"]["exact_matches"] for item in results), 4),
        "avg_delta_transfer_exact_matches": round(mean(item["delta"]["exact_matches"] for item in results), 4),
        "avg_fixed_transfer_bit_accuracy": round(mean(item["fixed_transfer"]["summary"]["mean_bit_accuracy"] for item in results), 4),
        "avg_growth_transfer_bit_accuracy": round(mean(item["growth_transfer"]["summary"]["mean_bit_accuracy"] for item in results), 4),
        "avg_delta_transfer_bit_accuracy": round(mean(item["delta"]["mean_bit_accuracy"] for item in results), 4),
        "avg_fixed_transfer_route_cost": round(mean(item["fixed_transfer"]["summary"]["mean_route_cost"] for item in results), 5),
        "avg_growth_transfer_route_cost": round(mean(item["growth_transfer"]["summary"]["mean_route_cost"] for item in results), 5),
        "avg_delta_transfer_route_cost": round(mean(item["delta"]["mean_route_cost"] for item in results), 5),
        "avg_growth_transfer_bud_successes": round(mean(item["growth_transfer"]["summary"]["bud_successes"] for item in results), 4),
        "avg_growth_transfer_dynamic_node_count": round(mean(item["growth_transfer"]["summary"]["dynamic_node_count"] for item in results), 4),
        "avg_growth_transfer_new_node_utilization": round(mean(item["growth_transfer"]["summary"]["new_node_utilization"] for item in results), 4),
        "avg_growth_transfer_dynamic_node_value": _mean_or_none(
            [item["growth_transfer"]["summary"].get("mean_dynamic_node_value") for item in results]
        ),
        "avg_growth_transfer_dynamic_net_energy": _mean_or_none(
            [item["growth_transfer"]["summary"].get("mean_dynamic_net_energy") for item in results]
        ),
        "avg_growth_transfer_dynamic_edge_value": _mean_or_none(
            [item["growth_transfer"]["summary"].get("mean_dynamic_edge_value") for item in results]
        ),
        "avg_growth_transfer_time_to_first_feedback": _mean_or_none(
            [item["growth_transfer"]["summary"]["time_to_first_feedback"] for item in results]
        ),
        "earned_growth_transfer_rate": round(
            mean(1.0 if item["growth_transfer"]["earned_growth"] else 0.0 for item in results),
            4,
        ),
        "growth_transfer_win_rate": round(
            mean(1.0 if item["growth_transfer"]["growth_win"] else 0.0 for item in results),
            4,
        ),
    }


def evaluate_morphogenesis(
    *,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    morphogenesis_config: MorphogenesisConfig | None = None,
    latent_context: bool = False,
    source_sequence_context_enabled: bool = True,
    latent_transfer_split_enabled: bool = True,
    output_path: Path | None = None,
) -> dict[str, object]:
    workload_scenarios = LATENT_WORKLOAD_SCENARIOS if latent_context else WORKLOAD_SCENARIOS
    scenario_results = {}
    for scenario_name in workload_scenarios:
        results = [
            compare_growth_for_seed(
                seed,
                scenario_name,
                morphogenesis_config=morphogenesis_config,
                latent_context=latent_context,
                source_sequence_context_enabled=source_sequence_context_enabled,
                latent_transfer_split_enabled=latent_transfer_split_enabled,
            )
            for seed in seeds
        ]
        scenario_results[scenario_name] = {
            "description": SCENARIOS[scenario_name].description,
            "results": results,
            "aggregate": aggregate_growth_results(results),
        }

    transfer_results = [
        transfer_growth_for_seed(
            seed,
            morphogenesis_config=morphogenesis_config,
            latent_context=latent_context,
            source_sequence_context_enabled=source_sequence_context_enabled,
            latent_transfer_split_enabled=latent_transfer_split_enabled,
        )
        for seed in seeds
    ]

    cloned_config = _clone_config(morphogenesis_config)
    result = {
        "seeds": list(seeds),
        "latent_context": latent_context,
        "source_sequence_context_enabled": source_sequence_context_enabled,
        "latent_transfer_split_enabled": latent_transfer_split_enabled,
        "morphogenesis_config": asdict(cloned_config),
        "scenarios": scenario_results,
        "transfer": {
            "train_scenario": TRAIN_SCENARIO,
            "transfer_scenario": TRANSFER_SCENARIO,
            "results": transfer_results,
            "aggregate": aggregate_transfer_growth_results(transfer_results),
        },
    }
    if output_path is not None:
        manifest = build_run_manifest(
            harness="morphogenesis",
            seeds=seeds,
            scenarios=workload_scenarios,
            latent_context=latent_context,
            metadata={
                "source_sequence_context_enabled": source_sequence_context_enabled,
                "latent_transfer_split_enabled": latent_transfer_split_enabled,
                "train_scenario": TRAIN_SCENARIO,
                "transfer_scenario": TRANSFER_SCENARIO,
                "morphogenesis_config": result["morphogenesis_config"],
            },
            result=result,
        )
        write_run_manifest(output_path, manifest)
    return result


def main() -> None:
    print(json.dumps(evaluate_morphogenesis(), indent=2))


if __name__ == "__main__":
    main()

