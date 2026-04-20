from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Sequence

from phase8 import Phase8SliceRunner, build_system_for_scenario
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
class CFamilyTrainEvalLightConfig:
    benchmark_id: str = "C3S1"
    task_key: str = "task_c"
    mode: str = "visible"
    seed: int = 13
    capability_policy: str = "self-selected"
    regulator_type: str = "gradient"
    initial_cycle_budget: int = 6
    train_ratio: float = 0.6
    train_safety_limit: int = 12
    eval_safety_limit: int = 12
    eval_accuracy_threshold: float = 0.8
    eval_feedback_fraction: float = 0.0


def _make_regulator(regulator_type: str, *, accuracy_threshold: float):
    if regulator_type == "learning":
        return LearningSliceRegulator(accuracy_threshold=accuracy_threshold)
    if regulator_type == "gradient":
        return GradientSliceRegulator(accuracy_threshold=accuracy_threshold)
    if regulator_type == "real":
        return REALSliceRegulator(accuracy_threshold=accuracy_threshold)
    return HeuristicSliceRegulator(accuracy_threshold=accuracy_threshold)


def _select_scenario(case, task_key: str, mode: str):
    task = case.tasks[task_key]
    if mode in ("visible", "growth-visible"):
        return task.visible_scenario
    if mode in ("latent", "growth-latent"):
        return task.latent_scenario
    raise ValueError(f"Unsupported mode: {mode}")


def _ordered_signal_specs(scenario: ScenarioSpec):
    signals = list(scenario.initial_signal_specs)
    if scenario.signal_schedule_specs:
        for cycle in sorted(scenario.signal_schedule_specs):
            signals.extend(scenario.signal_schedule_specs[cycle])
    return tuple(signals)


def _scenario_from_signal_slice(
    base: ScenarioSpec,
    *,
    name_suffix: str,
    signals: Sequence,
) -> ScenarioSpec:
    signal_tuple = tuple(signals)
    if not signal_tuple:
        raise ValueError("signal slice must contain at least one signal")
    slack_cycles = max(base.cycles - len(_ordered_signal_specs(base)), 0)
    return replace(
        base,
        name=f"{base.name}_{name_suffix}",
        description=f"{base.description} ({name_suffix}).",
        cycles=len(signal_tuple) + slack_cycles,
        initial_signal_specs=(signal_tuple[0],),
        signal_schedule_specs={
            cycle: (signal_spec,)
            for cycle, signal_spec in enumerate(signal_tuple[1:], start=2)
        },
    )


def _summarize_phase(run: LaminatedRunResult) -> dict[str, object]:
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
        "slice_count": len(run.summaries),
        "final_cycle_budget": run.final_cycle_budget,
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
        initial_capability_mode=mode,
    )
    controller = LaminatedController(
        runner,
        _make_regulator(regulator_type, accuracy_threshold=accuracy_threshold),
        initial_cycle_budget=initial_cycle_budget,
        safety_limit=safety_limit,
    )
    return controller.run()


def run_c_family_train_eval_light(config: CFamilyTrainEvalLightConfig) -> dict[str, object]:
    case = c_scale_suite_by_id()[config.benchmark_id]
    base_scenario = _select_scenario(case, config.task_key, config.mode)
    all_signals = _ordered_signal_specs(base_scenario)
    split_index = max(1, min(len(all_signals) - 1, round(len(all_signals) * config.train_ratio)))
    train_signals = all_signals[:split_index]
    eval_signals = all_signals[split_index:]
    train_scenario = _scenario_from_signal_slice(base_scenario, name_suffix="train", signals=train_signals)
    eval_scenario = _scenario_from_signal_slice(base_scenario, name_suffix="eval", signals=eval_signals)

    resolved_capability_policy = (
        config.mode if config.mode.startswith("growth-") else config.capability_policy
    )
    system = build_system_for_scenario(
        train_scenario,
        seed=config.seed,
        capability_policy=resolved_capability_policy,
    )

    train_feedback = float(system.environment.feedback_amount)
    train_run = _run_phase(
        system,
        scenario=train_scenario,
        task_key=config.task_key,
        mode=resolved_capability_policy,
        seed=config.seed,
        regulator_type=config.regulator_type,
        initial_cycle_budget=config.initial_cycle_budget,
        safety_limit=config.train_safety_limit,
        accuracy_threshold=0.0,
    )

    system.environment.feedback_amount = train_feedback * max(0.0, min(1.0, config.eval_feedback_fraction))
    eval_run = _run_phase(
        system,
        scenario=eval_scenario,
        task_key=config.task_key,
        mode=resolved_capability_policy,
        seed=config.seed,
        regulator_type=config.regulator_type,
        initial_cycle_budget=config.initial_cycle_budget,
        safety_limit=config.eval_safety_limit,
        accuracy_threshold=config.eval_accuracy_threshold,
    )

    return {
        "light_config": asdict(config),
        "benchmark_id": config.benchmark_id,
        "task_key": config.task_key,
        "mode": config.mode,
        "seed": config.seed,
        "capability_policy": resolved_capability_policy,
        "train_signal_count": len(train_signals),
        "eval_signal_count": len(eval_signals),
        "train_phase": _summarize_phase(train_run),
        "eval_phase": _summarize_phase(eval_run),
        "final_system_summary": system.summarize(),
    }


__all__ = [
    "CFamilyTrainEvalLightConfig",
    "run_c_family_train_eval_light",
]
