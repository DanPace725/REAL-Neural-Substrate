"""Evaluate laminated REAL on symbolic hidden-regime forecasting benchmarks.

The default path uses the laminated controller in its normal policy-selecting
mode with `self-selected` capability policy, so the slow layer can switch
policies over slices instead of being pinned to a single fixed capability mode.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from phase8 import evaluate_laminated_scenario, hidden_regime_suite_by_id
from scripts.experiment_manifest import build_run_manifest, write_run_manifest

EXPERIMENT_OUTPUTS_DIR = Path(__file__).parent.parent / "docs" / "experiment_outputs"
_DEFAULT_BENCHMARK_IDS = ("HR1", "HR2", "HR3", "HR4")
_DEFAULT_TASK_KEYS = ("task_a", "task_b", "task_c")
_DEFAULT_SLICE_BUDGET = 8


def _auto_output_path(
    *,
    benchmark_id: str,
    task_key: str,
    observable: str,
    capability_policy: str,
    seed: int,
    initial_cycle_budget: int,
    safety_limit: int,
    accuracy_threshold: float,
    regulator_type: str,
    run_stamp: str,
) -> Path:
    policy_slug = capability_policy.replace("-", "_")
    thresh_slug = f"_t{str(accuracy_threshold).replace('.', '')}" if accuracy_threshold > 0.0 else ""
    reg_slug = f"_{regulator_type}" if regulator_type != "real" else ""
    filename = (
        f"{run_stamp}_hidden_regime_{benchmark_id.lower()}_{task_key}_{observable}"
        f"_{policy_slug}_b{initial_cycle_budget}_s{safety_limit}{thresh_slug}{reg_slug}_seed{seed}.json"
    )
    return EXPERIMENT_OUTPUTS_DIR / filename


def _auto_suite_output_path(
    *,
    benchmark_ids: list[str],
    task_keys: list[str],
    observable: str,
    capability_policy: str,
    seed: int,
    initial_cycle_budget: int,
    safety_limit: int,
    accuracy_threshold: float,
    regulator_type: str,
    run_stamp: str,
) -> Path:
    bench_slug = "all" if len(benchmark_ids) > 3 else "_".join(item.lower() for item in benchmark_ids)
    task_slug = "all_tasks" if len(task_keys) > 1 else task_keys[0]
    policy_slug = capability_policy.replace("-", "_")
    thresh_slug = f"_t{str(accuracy_threshold).replace('.', '')}" if accuracy_threshold > 0.0 else ""
    reg_slug = f"_{regulator_type}" if regulator_type != "real" else ""
    filename = (
        f"{run_stamp}_hidden_regime_suite_{bench_slug}_{task_slug}_{observable}"
        f"_{policy_slug}_b{initial_cycle_budget}_s{safety_limit}{thresh_slug}{reg_slug}_seed{seed}.json"
    )
    return EXPERIMENT_OUTPUTS_DIR / filename


def evaluate_hidden_regime_benchmark(
    *,
    benchmark_id: str,
    task_key: str,
    observable: str = "hidden",
    seed: int = 13,
    capability_policy: str = "self-selected",
    initial_cycle_budget: int = _DEFAULT_SLICE_BUDGET,
    accuracy_threshold: float = 0.0,
    regulator_type: str = "real",
    safety_limit: int = 200,
    output_path: Path | None = None,
) -> dict[str, object]:
    suite = hidden_regime_suite_by_id()
    if benchmark_id not in suite:
        raise ValueError(f"Unsupported hidden-regime benchmark: {benchmark_id}")
    case = suite[benchmark_id]
    if task_key not in case.tasks:
        raise ValueError(f"Unsupported task key for {benchmark_id}: {task_key}")
    if observable not in {"hidden", "visible"}:
        raise ValueError(f"Unsupported observable mode: {observable}")

    task = case.tasks[task_key]
    scenario = task.hidden_scenario if observable == "hidden" else task.visible_scenario
    result = evaluate_laminated_scenario(
        scenario,
        benchmark_family="HR",
        task_key=task_key,
        seed=seed,
        capability_policy=capability_policy,
        initial_cycle_budget=initial_cycle_budget,
        safety_limit=safety_limit,
        accuracy_threshold=accuracy_threshold,
        regulator_type=regulator_type,
    )
    result.update(
        {
            "benchmark_id": benchmark_id,
            "task_key": task_key,
            "observable": observable,
            "capability_policy": capability_policy,
            "seed": seed,
            "case": {
                "label": case.label,
                "description": case.description,
                "regime_cardinality": case.regime_cardinality,
                "sequence_memory_window": case.sequence_memory_window,
                "pass_count": case.pass_count,
                "expected_examples": case.expected_examples,
                "topology_name": case.topology_name,
                "task_id": task.task_id,
            },
        }
    )

    if output_path is not None:
        manifest = build_run_manifest(
            harness="hidden_regime_forecasting",
            seeds=[seed],
            scenarios=[benchmark_id],
            metadata={
                "task_key": task_key,
                "observable": observable,
                "capability_policy": capability_policy,
                "initial_cycle_budget": initial_cycle_budget,
                "accuracy_threshold": accuracy_threshold,
                "regulator_type": regulator_type,
                "safety_limit": safety_limit,
            },
            result=result,
        )
        write_run_manifest(output_path, manifest)

    return result


def _compact_row(benchmark_id: str, task_key: str, result: dict[str, object]) -> str:
    lam = result.get("laminated_run", {})
    slices_data = lam.get("slice_summaries", [])
    decision = lam.get("final_decision", "?")
    observable = result.get("observable", "?")
    regime_count = result.get("case", {}).get("regime_cardinality", "?")

    final_acc = 0.0
    forecast_str = ""
    payoff_str = ""
    if slices_data:
        last = slices_data[-1]
        metadata = last.get("metadata", {})
        final_acc = float(metadata.get("mean_bit_accuracy", 0.0))
        forecast_metrics = metadata.get("forecast_metrics", {})
        forecast_acc = forecast_metrics.get("forecast_accuracy")
        resolved_count = forecast_metrics.get("resolved_forecast_count", 0)
        if isinstance(forecast_acc, (int, float)):
            forecast_str = f" forecast={forecast_acc:.3f}/{resolved_count}"
        payoff = metadata.get("intervention_payoff_trend", {})
        if isinstance(payoff, dict):
            status = payoff.get("status")
            delta = payoff.get("signed_delta")
            if isinstance(delta, (int, float)) and isinstance(status, str):
                payoff_str = f" payoff={status}:{delta:+.3f}"

    return (
        f"  {benchmark_id:4s} {task_key:6s} {observable:7s} regimes={regime_count} "
        f"final={final_acc:.3f} slices={len(slices_data)} [{decision}]"
        f"{forecast_str}{payoff_str}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate laminated REAL on symbolic hidden-regime forecasting benchmarks."
    )
    parser.add_argument(
        "-b",
        "--benchmark",
        default="HR1",
        help="Benchmark ID (HR1 / HR2 / HR3 / HR4). Use --sweep for multiple.",
    )
    parser.add_argument(
        "-t",
        "--task",
        default="task_a",
        help="Task key: task_a / task_b / task_c.",
    )
    parser.add_argument(
        "--all-tasks",
        action="store_true",
        help="Run all three tasks.",
    )
    parser.add_argument(
        "--observable",
        choices=("hidden", "visible"),
        default="hidden",
        help="Run the hidden benchmark or the visible-label ablation.",
    )
    parser.add_argument(
        "--sweep",
        default=None,
        help="Comma-separated benchmark IDs or 'all' for HR1,HR2,HR3.",
    )
    parser.add_argument(
        "--capability-policy",
        default="self-selected",
        choices=("self-selected", "fixed-latent", "growth-visible", "growth-latent"),
        help="Initial capability policy. self-selected keeps the slow layer free to switch policies over slices.",
    )
    parser.add_argument(
        "--reg",
        "--regulator-type",
        dest="regulator_type",
        choices=("heuristic", "learning", "real", "gradient"),
        default="real",
        help="Slow-layer regulator type.",
    )
    parser.add_argument("-s", "--seed", type=int, default=13)
    parser.add_argument(
        "--budget",
        dest="budget",
        type=int,
        default=_DEFAULT_SLICE_BUDGET,
        help="Initial cycles per slice.",
    )
    parser.add_argument(
        "--safety-limit",
        dest="safety_limit",
        type=int,
        default=200,
        help="Maximum number of slices before forced stop.",
    )
    parser.add_argument(
        "--thresh",
        "--accuracy-threshold",
        dest="accuracy_threshold",
        type=float,
        default=0.0,
        help="Optional settlement threshold.",
    )
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--no-output", action="store_true")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    if args.sweep:
        raw = args.sweep.strip()
        benchmark_ids = list(_DEFAULT_BENCHMARK_IDS) if raw == "all" else [item.strip() for item in raw.split(",")]
    else:
        benchmark_ids = [args.benchmark]
    task_keys = list(_DEFAULT_TASK_KEYS) if args.all_tasks else [args.task]

    run_results: list[dict[str, object]] = []
    for benchmark_id in benchmark_ids:
        for task_key in task_keys:
            output_path = None
            if not args.no_output:
                output_path = (
                    Path(args.output)
                    if args.output and len(benchmark_ids) == 1 and len(task_keys) == 1
                    else _auto_output_path(
                        benchmark_id=benchmark_id,
                        task_key=task_key,
                        observable=args.observable,
                        capability_policy=args.capability_policy,
                        seed=args.seed,
                        initial_cycle_budget=args.budget,
                        safety_limit=args.safety_limit,
                        accuracy_threshold=args.accuracy_threshold,
                        regulator_type=args.regulator_type,
                        run_stamp=run_stamp,
                    )
                )
            run_results.append(
                evaluate_hidden_regime_benchmark(
                    benchmark_id=benchmark_id,
                    task_key=task_key,
                    observable=args.observable,
                    seed=args.seed,
                    capability_policy=args.capability_policy,
                    initial_cycle_budget=args.budget,
                    accuracy_threshold=args.accuracy_threshold,
                    regulator_type=args.regulator_type,
                    safety_limit=args.safety_limit,
                    output_path=output_path,
                )
            )

    if not args.no_output and (len(run_results) > 1 or (args.output and len(run_results) > 1)):
        suite_output_path = (
            _auto_suite_output_path(
                benchmark_ids=benchmark_ids,
                task_keys=task_keys,
                observable=args.observable,
                capability_policy=args.capability_policy,
                seed=args.seed,
                initial_cycle_budget=args.budget,
                safety_limit=args.safety_limit,
                accuracy_threshold=args.accuracy_threshold,
                regulator_type=args.regulator_type,
                run_stamp=run_stamp,
            )
            if not args.output or len(run_results) == 1
            else Path(args.output)
        )
        suite_manifest = build_run_manifest(
            harness="hidden_regime_forecasting_suite",
            seeds=[args.seed],
            scenarios=benchmark_ids,
            metadata={
                "task_keys": task_keys,
                "observable": args.observable,
                "capability_policy": args.capability_policy,
                "initial_cycle_budget": args.budget,
                "accuracy_threshold": args.accuracy_threshold,
                "regulator_type": args.regulator_type,
                "safety_limit": args.safety_limit,
                "run_count": len(run_results),
            },
            result={"runs": run_results},
        )
        write_run_manifest(suite_output_path, suite_manifest)

    if args.compact:
        print("Hidden-regime laminated forecasting")
        for result in run_results:
            print(_compact_row(result["benchmark_id"], result["task_key"], result))
        return

    payload = run_results[0] if len(run_results) == 1 else run_results
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
