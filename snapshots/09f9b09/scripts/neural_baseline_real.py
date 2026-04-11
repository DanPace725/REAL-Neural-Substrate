from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Dict, Optional

from scripts.compare_cold_warm import SCENARIOS, build_system, run_workload
from scripts.compare_morphogenesis import benchmark_morphogenesis_config, build_growth_system
from scripts.neural_baseline_data import rolling_window_metrics


def run_real_for_comparison(
    task_id: str = "task_a",
    *,
    seed: int,
    scale_mode: bool = False,
    transfer_mode: bool = False,
    morphogenesis_enabled: bool = False,
) -> Optional[Dict[str, object]]:
    train_scenario_name = "cvt1_task_a_scale" if scale_mode else "cvt1_task_a_stage1"
    scenario_name = f"cvt1_{task_id}_{'scale' if scale_mode else 'stage1'}"
    if scenario_name not in SCENARIOS:
        return None

    morph_cfg = benchmark_morphogenesis_config() if morphogenesis_enabled else None

    def _create_system(scenario: str):
        if morphogenesis_enabled:
            return build_growth_system(seed, scenario, morphogenesis_config=morph_cfg)
        return build_system(seed, scenario)

    if transfer_mode:
        training_system = _create_system(train_scenario_name)
        run_workload(training_system, train_scenario_name)
        base_dir = Path(__file__).resolve().parent.parent / "tests_tmp" / f"baseline_transfer_{uuid.uuid4().hex}"
        full_dir = base_dir / "full"
        full_dir.mkdir(parents=True, exist_ok=True)
        try:
            training_system.save_memory_carryover(full_dir)
            system = _create_system(scenario_name)
            system.load_memory_carryover(full_dir)
            summary = run_workload(system, scenario_name)
        finally:
            shutil.rmtree(base_dir, ignore_errors=True)
    else:
        system = _create_system(scenario_name)
        summary = run_workload(system, scenario_name)

    scored_packets = sorted(
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
    exact_results = [bool(packet.matched_target) for packet in scored_packets]
    accuracy_results = [float(packet.bit_match_ratio or 0.0) for packet in scored_packets]
    metrics = rolling_window_metrics(exact_results, accuracy_results)
    return {
        "exact_matches": summary.get("exact_matches", 0),
        "mean_bit_accuracy": summary.get("mean_bit_accuracy", 0.0),
        "examples_to_criterion": metrics["examples_to_criterion"],
        "criterion_reached": bool(metrics["criterion_reached"]),
        "best_rolling_exact_rate": metrics["best_rolling_exact_rate"] or 0.0,
        "best_rolling_bit_accuracy": metrics["best_rolling_bit_accuracy"] or 0.0,
    }


__all__ = ["run_real_for_comparison"]
