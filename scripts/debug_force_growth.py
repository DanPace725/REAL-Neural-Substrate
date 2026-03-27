"""Debug-only laminated benchmark runner with forced growth authorization.

This script exists specifically for ad hoc experiments where we want to
override slow-layer growth policy selection without wiring that capability
into the main evaluation harness or the core controller.

Typical usage
-------------
python -m scripts.debug_force_growth -b B2S2 -t task_c -m visible --reg gradient --force-growth initiate
python -m scripts.debug_force_growth -b C3S1 -t task_c -m visible --reg gradient --force-growth authorize --safety-limit 50
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from phase8.lamination import (
    Phase8SliceRunner,
    build_system_for_scenario,
)
from real_core import (
    GradientSliceRegulator,
    HeuristicSliceRegulator,
    LaminatedController,
    LearningSliceRegulator,
    REALSliceRegulator,
    RegulatorySignal,
    SliceRegulator,
)
from scripts.compare_a_scale_suite import a_scale_suite_by_id
from scripts.compare_b_scale_suite import b_scale_suite_by_id
from scripts.compare_c_scale_suite import c_scale_suite_by_id
from scripts.experiment_manifest import build_run_manifest, write_run_manifest

EXPERIMENT_OUTPUTS_DIR = Path(__file__).parent.parent / "docs" / "experiment_outputs"


class ForcedGrowthRegulator:
    """Debug wrapper that rewrites growth authorization on outgoing signals."""

    def __init__(self, base: SliceRegulator, forced_growth: str) -> None:
        self._base = base
        self._forced_growth = str(forced_growth)

    def regulate(self, history):
        signal = self._base.regulate(history)
        base_metadata = dict(signal.metadata)
        base_metadata["debug_forced_growth_authorization"] = self._forced_growth
        base_metadata["debug_original_growth_authorization"] = signal.growth_authorization
        return replace(
            signal,
            growth_authorization=self._forced_growth,
            metadata=base_metadata,
        )

    def __getattr__(self, name: str):
        return getattr(self._base, name)


def _auto_output_path(
    *,
    benchmark_id: str,
    task_key: str,
    mode: str,
    seed: int,
    initial_cycle_budget: int,
    accuracy_threshold: float,
    regulator_type: str,
    forced_growth: str,
) -> Path:
    date_str = datetime.now().strftime("%Y%m%d")
    mode_slug = mode.replace("-", "_")
    thresh_slug = f"_t{str(accuracy_threshold).replace('.', '')}" if accuracy_threshold > 0.0 else ""
    reg_slug = f"_{regulator_type}" if regulator_type != "heuristic" else ""
    force_slug = f"_dbgfg_{forced_growth}"
    filename = (
        f"{date_str}_laminated_{benchmark_id.lower()}_{task_key}_{mode_slug}"
        f"_b{initial_cycle_budget}{thresh_slug}{reg_slug}{force_slug}_seed{seed}.json"
    )
    return EXPERIMENT_OUTPUTS_DIR / filename


def _resolve_case(benchmark_id: str):
    if benchmark_id.startswith("A"):
        return a_scale_suite_by_id()[benchmark_id], "A"
    if benchmark_id.startswith("B"):
        return b_scale_suite_by_id()[benchmark_id], "B"
    if benchmark_id.startswith("C"):
        return c_scale_suite_by_id()[benchmark_id], "C"
    raise ValueError(f"Unsupported benchmark: {benchmark_id}")


def _build_regulator(regulator_type: str, accuracy_threshold: float):
    if regulator_type == "learning":
        return LearningSliceRegulator(accuracy_threshold=accuracy_threshold)
    if regulator_type == "gradient":
        return GradientSliceRegulator(accuracy_threshold=accuracy_threshold)
    if regulator_type == "real":
        return REALSliceRegulator(accuracy_threshold=accuracy_threshold)
    return HeuristicSliceRegulator(accuracy_threshold=accuracy_threshold)


def evaluate_debug_growth_benchmark(
    *,
    benchmark_id: str,
    task_key: str,
    mode: str,
    seed: int,
    capability_policy: str = "self-selected",
    initial_cycle_budget: int = 8,
    accuracy_threshold: float = 0.0,
    regulator_type: str = "heuristic",
    safety_limit: int = 200,
    forced_growth: str = "authorize",
    output_path: Path | None = None,
) -> dict[str, object]:
    case, benchmark_family = _resolve_case(benchmark_id)
    task = case.tasks[task_key]
    if mode in ("visible", "growth-visible"):
        scenario = task.visible_scenario
    elif mode in ("latent", "growth-latent"):
        scenario = task.latent_scenario
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    resolved_capability_policy = mode if mode.startswith("growth-") else capability_policy
    system = build_system_for_scenario(
        scenario,
        seed=seed,
        capability_policy=resolved_capability_policy,
    )
    runner = Phase8SliceRunner(
        system,
        scenario,
        benchmark_family=benchmark_family,
        task_key=task_key,
        seed=seed,
        initial_capability_mode=resolved_capability_policy,
    )
    base_regulator = _build_regulator(regulator_type, accuracy_threshold)
    regulator = ForcedGrowthRegulator(base_regulator, forced_growth)
    controller = LaminatedController(
        runner,
        regulator,
        initial_cycle_budget=initial_cycle_budget,
        safety_limit=safety_limit,
    )
    laminated_result = controller.run()

    experience_log = []
    if isinstance(base_regulator, LearningSliceRegulator):
        for exp in base_regulator.experiences:
            experience_log.append(
                {
                    "mode": exp.mode,
                    "features": dict(exp.features),
                    "predicted_delta": exp.predicted_delta,
                    "observed_delta": round(exp.observed_delta, 4),
                    "prediction_error": round(exp.prediction_error, 4)
                    if exp.prediction_error is not None
                    else None,
                }
            )
    elif isinstance(base_regulator, REALSliceRegulator):
        experience_log = base_regulator.engine_history()

    result = {
        "laminated_summary": runner.system.summarize(),
        "experience_log": experience_log,
        "laminated_run": {
            "final_decision": laminated_result.final_decision.value,
            "final_cycle_budget": laminated_result.final_cycle_budget,
            "final_signal": None
            if laminated_result.final_signal is None
            else {
                "next_slice_budget": laminated_result.final_signal.next_slice_budget,
                "budget_target": laminated_result.final_signal.budget_target,
                "pressure_level": laminated_result.final_signal.pressure_level,
                "hygiene_level": laminated_result.final_signal.hygiene_level,
                "growth_drive": laminated_result.final_signal.growth_drive,
                "portfolio_drive": laminated_result.final_signal.portfolio_drive,
                "settlement_confidence": laminated_result.final_signal.settlement_confidence,
                "carryover_filter_mode": laminated_result.final_signal.carryover_filter_mode,
                "context_pressure": laminated_result.final_signal.context_pressure,
                "growth_authorization": laminated_result.final_signal.growth_authorization,
                "decision_hint": laminated_result.final_signal.decision_hint.value,
                "execution_plan": None
                if laminated_result.final_signal.execution_plan is None
                else {
                    "initial_budget": laminated_result.final_signal.execution_plan.initial_budget,
                    "extend_step": laminated_result.final_signal.execution_plan.extend_step,
                    "soft_cap": laminated_result.final_signal.execution_plan.soft_cap,
                    "hard_cap": laminated_result.final_signal.execution_plan.hard_cap,
                    "early_stop_patience": laminated_result.final_signal.execution_plan.early_stop_patience,
                    "metadata": dict(laminated_result.final_signal.execution_plan.metadata),
                },
                "reset_flags": dict(laminated_result.final_signal.reset_flags),
                "reframe_flags": dict(laminated_result.final_signal.reframe_flags),
                "stop_reason": laminated_result.final_signal.stop_reason,
                "metadata": dict(laminated_result.final_signal.metadata),
            },
            "slice_summaries": [
                {
                    "slice_id": summary.slice_id,
                    "slice_budget": summary.slice_budget,
                    "cycles_used": summary.cycles_used,
                    "examples_seen": summary.examples_seen,
                    "mean_coherence": summary.mean_coherence,
                    "final_coherence": summary.final_coherence,
                    "coherence_delta": summary.coherence_delta,
                    "mean_uncertainty": summary.mean_uncertainty,
                    "ambiguity_level": summary.ambiguity_level,
                    "conflict_level": summary.conflict_level,
                    "guidance_alignment": summary.guidance_alignment,
                    "candidate_carryover_labels": list(summary.candidate_carryover_labels),
                    "candidate_carryover_count": summary.candidate_carryover_count,
                    "cost_summary": dict(summary.cost_summary),
                    "settlement_hint": summary.settlement_hint,
                    "context_accuracy": dict(summary.context_accuracy),
                    "mode_used": summary.mode_used,
                    "metadata": dict(summary.metadata),
                }
                for summary in laminated_result.summaries
            ],
        },
        "benchmark_id": benchmark_id,
        "task_key": task_key,
        "mode": mode,
        "capability_policy": resolved_capability_policy,
        "seed": seed,
        "debug_overrides": {
            "forced_growth_authorization": forced_growth,
            "wrapped_regulator_type": regulator_type,
        },
    }

    if output_path is not None:
        manifest = build_run_manifest(
            harness="laminated_phase8_debug_force_growth",
            seeds=[seed],
            scenarios=[benchmark_id],
            metadata={
                "task_key": task_key,
                "mode": mode,
                "capability_policy": resolved_capability_policy,
                "initial_cycle_budget": initial_cycle_budget,
                "accuracy_threshold": accuracy_threshold,
                "regulator_type": regulator_type,
                "safety_limit": safety_limit,
                "forced_growth_authorization": forced_growth,
            },
            result=result,
        )
        write_run_manifest(output_path, manifest)

    return result


def _compact_row(result: dict[str, object]) -> str:
    lam = result.get("laminated_run", {})
    slices_data = lam.get("slice_summaries", [])
    slices = len(slices_data)
    decision = lam.get("final_decision", "?")
    final_acc = 0.0
    ctx_str = ""
    if slices_data:
        last = slices_data[-1]
        final_acc = last.get("metadata", {}).get(
            "final_accuracy",
            last.get("metadata", {}).get("mean_bit_accuracy", 0.0),
        )
        ca = last.get("context_accuracy", {})
        if ca:
            ctx_str = " | " + " ".join(f"{k}={v:.2f}" for k, v in sorted(ca.items()))
    return (
        f"  {str(result['benchmark_id']):6s} {str(result['task_key']):6s} "
        f"final={float(final_acc):.3f} slices={slices} [{decision}]"
        f" forced_growth={result['debug_overrides']['forced_growth_authorization']}{ctx_str}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug laminated benchmarks with forced growth authorization.")
    parser.add_argument("-b", "--benchmark", default="B2S2")
    parser.add_argument("-t", "--task", default="task_c")
    parser.add_argument(
        "-m",
        "--mode",
        choices=("visible", "latent", "growth-visible", "growth-latent"),
        default="visible",
    )
    parser.add_argument("--cap", "--capability-policy", dest="capability_policy", default="self-selected")
    parser.add_argument(
        "--reg",
        "--regulator-type",
        dest="regulator_type",
        choices=("heuristic", "learning", "real", "gradient"),
        default="gradient",
    )
    parser.add_argument("--force-growth", choices=("hold", "authorize", "initiate"), default="authorize")
    parser.add_argument("-s", "--seed", type=int, default=13)
    parser.add_argument("--budget", type=int, default=8)
    parser.add_argument("--safety-limit", type=int, default=200)
    parser.add_argument("--thresh", dest="accuracy_threshold", type=float, default=0.0)
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--no-output", action="store_true")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()

    output_path: Path | None = None
    if not args.no_output:
        output_path = (
            Path(args.output)
            if args.output
            else _auto_output_path(
                benchmark_id=args.benchmark,
                task_key=args.task,
                mode=args.mode,
                seed=args.seed,
                initial_cycle_budget=args.budget,
                accuracy_threshold=args.accuracy_threshold,
                regulator_type=args.regulator_type,
                forced_growth=args.force_growth,
            )
        )

    result = evaluate_debug_growth_benchmark(
        benchmark_id=args.benchmark,
        task_key=args.task,
        mode=args.mode,
        seed=args.seed,
        capability_policy=args.capability_policy,
        initial_cycle_budget=args.budget,
        accuracy_threshold=args.accuracy_threshold,
        regulator_type=args.regulator_type,
        safety_limit=args.safety_limit,
        forced_growth=args.force_growth,
        output_path=output_path,
    )
    if args.compact:
        print(_compact_row(result))
    else:
        print(json.dumps(result, indent=2))
    if output_path is not None:
        print(f"\n[debug manifest written to] {output_path}")


if __name__ == "__main__":
    main()
