from __future__ import annotations

import json
import shutil
import uuid
from statistics import mean

from compare_cold_warm import ROOT, SCENARIOS, build_system
from compare_task_transfer import transfer_metrics
from phase8 import SignalSpec


DEFAULT_SEEDS = (13, 23, 37, 51, 79)
TRAIN_SCENARIO = "cvt1_task_a_stage1"
TRANSFER_SCENARIO = "cvt1_task_b_stage1"


def _mean(values: list[float]) -> float:
    return round(mean(values), 4)


def _expected_target_bits(
    input_bits: list[int],
    *,
    task_id: str | None,
    context_bit: int | None,
) -> list[int]:
    if task_id is None or context_bit is None:
        return []
    if task_id == "task_a":
        transform = "rotate_left_1" if context_bit == 0 else "xor_mask_1010"
    elif task_id == "task_b":
        transform = "rotate_left_1" if context_bit == 0 else "xor_mask_0101"
    elif task_id == "task_c":
        transform = "xor_mask_1010" if context_bit == 0 else "xor_mask_0101"
    else:
        return []
    if transform == "rotate_left_1":
        if not input_bits:
            return []
        return list(input_bits[1:]) + [input_bits[0]]
    if transform == "xor_mask_1010":
        mask = [1, 0, 1, 0]
    else:
        mask = [0, 1, 0, 1]
    return [int(bit) ^ mask[index] for index, bit in enumerate(input_bits)]


def latent_signal_specs(scenario_name: str) -> tuple[tuple[SignalSpec, ...], dict[int, tuple[SignalSpec, ...]] | None]:
    scenario = SCENARIOS[scenario_name]

    def convert(spec: SignalSpec) -> SignalSpec:
        bits = list(spec.input_bits)
        payload = list(spec.payload_bits) if spec.payload_bits is not None else None
        return SignalSpec(
            input_bits=bits,
            payload_bits=payload,
            context_bit=None,
            task_id=spec.task_id,
            target_bits=_expected_target_bits(bits, task_id=spec.task_id, context_bit=spec.context_bit),
        )

    initial = tuple(convert(spec) for spec in scenario.initial_signal_specs)
    schedule = None
    if scenario.signal_schedule_specs is not None:
        schedule = {
            cycle: tuple(convert(spec) for spec in specs)
            for cycle, specs in scenario.signal_schedule_specs.items()
        }
    return initial, schedule


def run_scenario(
    seed: int,
    scenario_name: str,
    *,
    latent_context: bool,
    source_sequence_context_enabled: bool = True,
) -> tuple[object, dict[str, object]]:
    scenario = SCENARIOS[scenario_name]
    system = build_system(
        seed,
        scenario_name,
        source_sequence_context_enabled=source_sequence_context_enabled,
    )
    initial = scenario.initial_signal_specs
    schedule = scenario.signal_schedule_specs
    if latent_context:
        initial, schedule = latent_signal_specs(scenario_name)
    result = system.run_workload(
        cycles=scenario.cycles,
        initial_packets=scenario.initial_packets,
        packet_schedule=scenario.packet_schedule,
        initial_signal_specs=initial,
        signal_schedule_specs=schedule,
    )
    return system, result["summary"]


def compare_latent_for_seed(
    seed: int,
    scenario_name: str,
    *,
    source_sequence_context_enabled: bool = True,
) -> dict[str, object]:
    visible_system, visible_summary = run_scenario(seed, scenario_name, latent_context=False)
    latent_system, latent_summary = run_scenario(
        seed,
        scenario_name,
        latent_context=True,
        source_sequence_context_enabled=source_sequence_context_enabled,
    )
    return {
        "seed": seed,
        "scenario": scenario_name,
        "visible": {
            "summary": visible_summary,
            "transfer_metrics": transfer_metrics(visible_system),
        },
        "latent": {
            "summary": latent_summary,
            "transfer_metrics": transfer_metrics(latent_system),
        },
        "delta": {
            "exact_matches": latent_summary["exact_matches"] - visible_summary["exact_matches"],
            "mean_bit_accuracy": round(latent_summary["mean_bit_accuracy"] - visible_summary["mean_bit_accuracy"], 4),
            "mean_route_cost": round(latent_summary["mean_route_cost"] - visible_summary["mean_route_cost"], 5),
        },
    }


def transfer_latent_for_seed(
    seed: int,
    *,
    source_sequence_context_enabled: bool = True,
) -> dict[str, object]:
    visible_train_system, visible_train_summary = run_scenario(seed, TRAIN_SCENARIO, latent_context=False)
    latent_train_system, latent_train_summary = run_scenario(
        seed,
        TRAIN_SCENARIO,
        latent_context=True,
        source_sequence_context_enabled=source_sequence_context_enabled,
    )

    base_dir = ROOT / "tests_tmp" / f"latent_context_{uuid.uuid4().hex}"
    visible_dir = base_dir / "visible"
    latent_dir = base_dir / "latent"
    visible_dir.mkdir(parents=True, exist_ok=True)
    latent_dir.mkdir(parents=True, exist_ok=True)
    try:
        visible_train_system.save_memory_carryover(visible_dir)
        latent_train_system.save_memory_carryover(latent_dir)

        visible_transfer = build_system(seed, TRANSFER_SCENARIO)
        visible_transfer.load_memory_carryover(visible_dir)
        visible_scenario = SCENARIOS[TRANSFER_SCENARIO]
        visible_result = visible_transfer.run_workload(
            cycles=visible_scenario.cycles,
            initial_packets=visible_scenario.initial_packets,
            packet_schedule=visible_scenario.packet_schedule,
            initial_signal_specs=visible_scenario.initial_signal_specs,
            signal_schedule_specs=visible_scenario.signal_schedule_specs,
        )
        visible_transfer_summary = visible_result["summary"]

        latent_transfer = build_system(
            seed,
            TRANSFER_SCENARIO,
            source_sequence_context_enabled=source_sequence_context_enabled,
        )
        latent_transfer.load_memory_carryover(latent_dir)
        latent_initial, latent_schedule = latent_signal_specs(TRANSFER_SCENARIO)
        latent_result = latent_transfer.run_workload(
            cycles=visible_scenario.cycles,
            initial_packets=visible_scenario.initial_packets,
            packet_schedule=visible_scenario.packet_schedule,
            initial_signal_specs=latent_initial,
            signal_schedule_specs=latent_schedule,
        )
        latent_transfer_summary = latent_result["summary"]
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)

    return {
        "seed": seed,
        "visible_training": visible_train_summary,
        "latent_training": latent_train_summary,
        "visible_transfer": visible_transfer_summary,
        "latent_transfer": latent_transfer_summary,
        "delta_transfer": {
            "exact_matches": latent_transfer_summary["exact_matches"] - visible_transfer_summary["exact_matches"],
            "mean_bit_accuracy": round(
                latent_transfer_summary["mean_bit_accuracy"] - visible_transfer_summary["mean_bit_accuracy"],
                4,
            ),
            "mean_route_cost": round(
                latent_transfer_summary["mean_route_cost"] - visible_transfer_summary["mean_route_cost"],
                5,
            ),
        },
    }


def evaluate_latent_context(
    *,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    source_sequence_context_enabled: bool = True,
) -> dict[str, object]:
    task_a = [
        compare_latent_for_seed(
            seed,
            TRAIN_SCENARIO,
            source_sequence_context_enabled=source_sequence_context_enabled,
        )
        for seed in seeds
    ]
    task_b = [
        compare_latent_for_seed(
            seed,
            TRANSFER_SCENARIO,
            source_sequence_context_enabled=source_sequence_context_enabled,
        )
        for seed in seeds
    ]
    transfer = [
        transfer_latent_for_seed(
            seed,
            source_sequence_context_enabled=source_sequence_context_enabled,
        )
        for seed in seeds
    ]
    return {
        "seeds": list(seeds),
        "source_sequence_context_enabled": source_sequence_context_enabled,
        "scenarios": {
            TRAIN_SCENARIO: {
                "results": task_a,
                "aggregate": {
                    "visible_exact_matches": _mean([item["visible"]["summary"]["exact_matches"] for item in task_a]),
                    "latent_exact_matches": _mean([item["latent"]["summary"]["exact_matches"] for item in task_a]),
                    "visible_bit_accuracy": _mean([item["visible"]["summary"]["mean_bit_accuracy"] for item in task_a]),
                    "latent_bit_accuracy": _mean([item["latent"]["summary"]["mean_bit_accuracy"] for item in task_a]),
                },
            },
            TRANSFER_SCENARIO: {
                "results": task_b,
                "aggregate": {
                    "visible_exact_matches": _mean([item["visible"]["summary"]["exact_matches"] for item in task_b]),
                    "latent_exact_matches": _mean([item["latent"]["summary"]["exact_matches"] for item in task_b]),
                    "visible_bit_accuracy": _mean([item["visible"]["summary"]["mean_bit_accuracy"] for item in task_b]),
                    "latent_bit_accuracy": _mean([item["latent"]["summary"]["mean_bit_accuracy"] for item in task_b]),
                },
            },
        },
        "transfer": {
            "results": transfer,
            "aggregate": {
                "visible_exact_matches": _mean([item["visible_transfer"]["exact_matches"] for item in transfer]),
                "latent_exact_matches": _mean([item["latent_transfer"]["exact_matches"] for item in transfer]),
                "visible_bit_accuracy": _mean([item["visible_transfer"]["mean_bit_accuracy"] for item in transfer]),
                "latent_bit_accuracy": _mean([item["latent_transfer"]["mean_bit_accuracy"] for item in transfer]),
            },
        },
    }


def main() -> None:
    print(json.dumps(evaluate_latent_context(), indent=2))


if __name__ == "__main__":
    main()
