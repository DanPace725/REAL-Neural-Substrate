from __future__ import annotations

from dataclasses import asdict, dataclass, replace

from phase8 import Phase8SliceRunner, build_system_for_scenario
from phase8.models import SignalSpec
from phase8.scenarios import ScenarioSpec
from real_core import (
    GradientSliceRegulator,
    HeuristicSliceRegulator,
    LaminatedController,
    LaminatedRunResult,
    LearningSliceRegulator,
    REALSliceRegulator,
)
from scripts.compare_c_scale_suite import c_scale_suite_by_id


@dataclass(frozen=True)
class CFamilyOrientationLightConfig:
    benchmark_id: str = "C3S1"
    challenge_task_key: str = "task_c"
    orientation_task_keys: tuple[str, ...] = ("task_a",)
    mode: str = "visible"
    seed: int = 13
    capability_policy: str = "self-selected"
    regulator_type: str = "gradient"
    initial_cycle_budget: int = 6
    orientation_safety_limit: int = 12
    challenge_safety_limit: int = 40
    challenge_accuracy_threshold: float = 0.8


def _make_regulator(regulator_type: str, *, accuracy_threshold: float):
    if regulator_type == "learning":
        return LearningSliceRegulator(accuracy_threshold=accuracy_threshold)
    if regulator_type == "gradient":
        return GradientSliceRegulator(accuracy_threshold=accuracy_threshold)
    if regulator_type == "real":
        return REALSliceRegulator(accuracy_threshold=accuracy_threshold)
    return HeuristicSliceRegulator(accuracy_threshold=accuracy_threshold)


def _select_scenario(case, task_key: str, mode: str):
    if task_key.endswith("_masked"):
        base_task_key = task_key.removesuffix("_masked")
        base_scenario = _select_scenario(case, base_task_key, mode)
        return _masked_orientation_scenario(base_scenario, base_task_key=base_task_key)
    task = case.tasks[task_key]
    if mode in ("visible", "growth-visible"):
        return task.visible_scenario
    if mode in ("latent", "growth-latent"):
        return task.latent_scenario
    raise ValueError(f"Unsupported mode: {mode}")


def _masked_orientation_signal(spec: SignalSpec) -> SignalSpec:
    return SignalSpec(
        input_bits=list(spec.input_bits),
        payload_bits=list(spec.payload_bits) if spec.payload_bits is not None else None,
        context_bit=spec.context_bit,
        task_id="masked_orientation",
        target_bits=None,
        origin=spec.origin,
    )


def _masked_orientation_scenario(base_scenario: ScenarioSpec, *, base_task_key: str) -> ScenarioSpec:
    initial_specs = tuple(_masked_orientation_signal(spec) for spec in base_scenario.initial_signal_specs)
    schedule_specs = None
    if base_scenario.signal_schedule_specs is not None:
        schedule_specs = {
            int(cycle): tuple(_masked_orientation_signal(spec) for spec in specs)
            for cycle, specs in base_scenario.signal_schedule_specs.items()
        }
    return replace(
        base_scenario,
        name=f"{base_scenario.name}_masked",
        description=f"{base_scenario.description} Masked orientation for {base_task_key}.",
        initial_signal_specs=initial_specs,
        signal_schedule_specs=schedule_specs,
    )


def _summarize_phase(run: LaminatedRunResult) -> dict[str, object]:
    slices = [
        {
            "slice_id": summary.slice_id,
            "slice_budget": summary.slice_budget,
            "cycles_used": summary.cycles_used,
            "context_accuracy": dict(summary.context_accuracy),
            "metadata": dict(summary.metadata),
        }
        for summary in run.summaries
    ]
    final_summary = run.summaries[-1] if run.summaries else None
    final_accuracy = 0.0
    floor_accuracy = 0.0
    if final_summary is not None:
        final_accuracy = float(
            final_summary.metadata.get(
                "final_accuracy",
                final_summary.metadata.get("mean_bit_accuracy", 0.0),
            )
        )
        if final_summary.context_accuracy:
            floor_accuracy = min(float(value) for value in final_summary.context_accuracy.values())
        else:
            floor_accuracy = float(
                final_summary.metadata.get(
                    "floor_accuracy",
                    final_accuracy,
                )
            )
    return {
        "final_decision": run.final_decision.value,
        "final_cycle_budget": run.final_cycle_budget,
        "slice_count": len(run.summaries),
        "final_accuracy": round(final_accuracy, 4),
        "floor_accuracy": round(floor_accuracy, 4),
        "final_signal": None
        if run.final_signal is None
        else {
            "budget_target": run.final_signal.budget_target,
            "pressure_level": run.final_signal.pressure_level,
            "hygiene_level": run.final_signal.hygiene_level,
            "growth_drive": run.final_signal.growth_drive,
            "portfolio_drive": run.final_signal.portfolio_drive,
            "settlement_confidence": run.final_signal.settlement_confidence,
            "carryover_filter_mode": run.final_signal.carryover_filter_mode,
            "context_pressure": run.final_signal.context_pressure,
            "growth_authorization": run.final_signal.growth_authorization,
            "stop_reason": run.final_signal.stop_reason,
            "metadata": dict(run.final_signal.metadata),
        },
        "slice_summaries": slices,
    }


def _run_phase(
    system,
    *,
    scenario,
    task_key: str,
    mode: str,
    seed: int,
    regulator_type: str,
    initial_cycle_budget: int,
    safety_limit: int,
    accuracy_threshold: float,
) -> LaminatedRunResult:
    runner = Phase8SliceRunner(
        system,
        scenario,
        benchmark_family="C",
        task_key=task_key,
        seed=seed,
        initial_capability_mode=mode if mode.startswith("growth-") else "self-selected",
    )
    controller = LaminatedController(
        runner,
        _make_regulator(regulator_type, accuracy_threshold=accuracy_threshold),
        initial_cycle_budget=initial_cycle_budget,
        safety_limit=safety_limit,
    )
    return controller.run()


def run_c_family_orientation_light(
    config: CFamilyOrientationLightConfig,
) -> dict[str, object]:
    case = c_scale_suite_by_id()[config.benchmark_id]
    challenge_scenario = _select_scenario(case, config.challenge_task_key, config.mode)
    resolved_capability_policy = (
        config.mode if config.mode.startswith("growth-") else config.capability_policy
    )
    system = build_system_for_scenario(
        challenge_scenario,
        seed=config.seed,
        capability_policy=resolved_capability_policy,
    )

    orientation_results: list[dict[str, object]] = []
    for task_key in config.orientation_task_keys:
        orientation_scenario = _select_scenario(case, task_key, config.mode)
        run = _run_phase(
            system,
            scenario=orientation_scenario,
            task_key=task_key,
            mode=resolved_capability_policy,
            seed=config.seed,
            regulator_type=config.regulator_type,
            initial_cycle_budget=config.initial_cycle_budget,
            safety_limit=config.orientation_safety_limit,
            accuracy_threshold=0.0,
        )
        orientation_results.append(
            {
                "task_key": task_key,
                "result": _summarize_phase(run),
            }
        )

    challenge_run = _run_phase(
        system,
        scenario=challenge_scenario,
        task_key=config.challenge_task_key,
        mode=resolved_capability_policy,
        seed=config.seed,
        regulator_type=config.regulator_type,
        initial_cycle_budget=config.initial_cycle_budget,
        safety_limit=config.challenge_safety_limit,
        accuracy_threshold=config.challenge_accuracy_threshold,
    )

    return {
        "light_config": asdict(config),
        "benchmark_id": config.benchmark_id,
        "mode": config.mode,
        "seed": config.seed,
        "capability_policy": resolved_capability_policy,
        "orientation_phases": orientation_results,
        "challenge_phase": {
            "task_key": config.challenge_task_key,
            "result": _summarize_phase(challenge_run),
        },
        "final_system_summary": system.summarize(),
    }


__all__ = [
    "CFamilyOrientationLightConfig",
    "run_c_family_orientation_light",
]
