"""Evaluate laminated Phase 8 slices on B/C benchmarks.

Typical usage
-------------
# Single run with auto budget
python -m scripts.evaluate_laminated_phase8 -b B2S5 -m visible --thresh 0.8 --reg real

# Sweep all B scales, compact summary
python -m scripts.evaluate_laminated_phase8 --sweep B2S1,B2S3,B2S5 --reg real --compact

# All tasks on C3S5
python -m scripts.evaluate_laminated_phase8 -b C3S5 --all-tasks --reg real

# All B + C scales (large run)
python -m scripts.evaluate_laminated_phase8 --sweep all --reg real --compact
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from phase8 import evaluate_laminated_scenario
from scripts.compare_b_scale_suite import b_scale_suite_by_id
from scripts.compare_c_scale_suite import c_scale_suite_by_id
from scripts.experiment_manifest import build_run_manifest, write_run_manifest

EXPERIMENT_OUTPUTS_DIR = Path(__file__).parent.parent / "docs" / "experiment_outputs"

_B_IDS = ("B2S1", "B2S2", "B2S3", "B2S4", "B2S5", "B2S6")
_C_IDS = ("C3S1", "C3S2", "C3S3", "C3S4", "C3S5", "C3S6")
_ALL_TASKS = ("task_a", "task_b", "task_c")


# ---------------------------------------------------------------------------
# Budget auto-computation
# ---------------------------------------------------------------------------

def _resolve_budget(budget_arg: str | int, *, benchmark_id: str, task_key: str, mode: str, max_slices: int) -> int:
    """Return the cycle budget to use, auto-computing from scenario size if requested."""
    if str(budget_arg) != "auto":
        return int(budget_arg)

    if benchmark_id.startswith("B"):
        case = b_scale_suite_by_id()[benchmark_id]
    else:
        case = c_scale_suite_by_id()[benchmark_id]

    task = case.tasks[task_key]
    scenario = task.visible_scenario if mode in ("visible", "growth-visible") else task.latent_scenario
    return max(1, scenario.cycles // max_slices)


# ---------------------------------------------------------------------------
# Output path helpers
# ---------------------------------------------------------------------------

def _auto_output_path(
    *,
    benchmark_id: str,
    task_key: str,
    mode: str,
    seed: int,
    max_slices: int,
    initial_cycle_budget: int,
    accuracy_threshold: float,
    regulator_type: str,
) -> Path:
    date_str = datetime.now().strftime("%Y%m%d")
    mode_slug = mode.replace("-", "_")
    thresh_slug = f"_t{str(accuracy_threshold).replace('.', '')}" if accuracy_threshold > 0.0 else ""
    reg_slug = f"_{regulator_type}" if regulator_type != "heuristic" else ""
    filename = (
        f"{date_str}_laminated_{benchmark_id.lower()}_{task_key}_{mode_slug}"
        f"_s{max_slices}_b{initial_cycle_budget}{thresh_slug}{reg_slug}_seed{seed}.json"
    )
    return EXPERIMENT_OUTPUTS_DIR / filename


# ---------------------------------------------------------------------------
# Single run
# ---------------------------------------------------------------------------

def evaluate_laminated_benchmark(
    *,
    benchmark_id: str,
    task_key: str,
    mode: str,
    seed: int,
    capability_policy: str = "self-selected",
    max_slices: int = 5,
    initial_cycle_budget: int = 8,
    accuracy_threshold: float = 0.0,
    regulator_type: str = "heuristic",
    output_path: Path | None = None,
) -> dict[str, object]:
    if benchmark_id.startswith("B"):
        case = b_scale_suite_by_id()[benchmark_id]
        benchmark_family = "B"
    elif benchmark_id.startswith("C"):
        case = c_scale_suite_by_id()[benchmark_id]
        benchmark_family = "C"
    else:
        raise ValueError(f"Unsupported benchmark: {benchmark_id}")

    task = case.tasks[task_key]
    if mode in ("visible", "growth-visible"):
        scenario = task.visible_scenario
    elif mode in ("latent", "growth-latent"):
        scenario = task.latent_scenario
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    resolved_capability_policy = mode if mode.startswith("growth-") else capability_policy

    result = evaluate_laminated_scenario(
        scenario,
        benchmark_family=benchmark_family,
        task_key=task_key,
        seed=seed,
        capability_policy=resolved_capability_policy,
        max_slices=max_slices,
        initial_cycle_budget=initial_cycle_budget,
        accuracy_threshold=accuracy_threshold,
        regulator_type=regulator_type,
    )
    result.update({
        "benchmark_id": benchmark_id,
        "task_key": task_key,
        "mode": mode,
        "capability_policy": resolved_capability_policy,
        "seed": seed,
    })

    baseline_summary = result["baseline_summary"]
    laminated_summary = result["laminated_summary"]
    result["delta_vs_baseline"] = {
        "exact_matches": round(
            float(laminated_summary.get("exact_matches", 0.0))
            - float(baseline_summary.get("exact_matches", 0.0)), 4),
        "mean_bit_accuracy": round(
            float(laminated_summary.get("mean_bit_accuracy", 0.0))
            - float(baseline_summary.get("mean_bit_accuracy", 0.0)), 4),
        "total_action_cost": round(
            float(laminated_summary.get("total_action_cost", 0.0))
            - float(baseline_summary.get("total_action_cost", 0.0)), 5),
    }

    if output_path is not None:
        manifest = build_run_manifest(
            harness="laminated_phase8",
            seeds=[seed],
            scenarios=[benchmark_id],
            metadata={
                "task_key": task_key,
                "mode": mode,
                "capability_policy": resolved_capability_policy,
                "max_slices": max_slices,
                "initial_cycle_budget": initial_cycle_budget,
                "accuracy_threshold": accuracy_threshold,
                "regulator_type": regulator_type,
            },
            result=result,
        )
        write_run_manifest(output_path, manifest)

    return result


# ---------------------------------------------------------------------------
# Compact summary formatter
# ---------------------------------------------------------------------------

def _compact_row(benchmark_id: str, task_key: str, result: dict) -> str:
    lam = result.get("laminated_run", {})
    lam_sum = result.get("laminated_summary", {})
    base_sum = result.get("baseline_summary", {})
    slices = len(lam.get("slice_summaries", []))
    decision = lam.get("final_decision", "?")
    lam_acc = lam_sum.get("mean_bit_accuracy", 0.0)
    base_acc = base_sum.get("mean_bit_accuracy", 0.0)
    delta = result.get("delta_vs_baseline", {}).get("mean_bit_accuracy", 0.0)
    cost = lam_sum.get("total_action_cost", 0.0)
    base_cost = base_sum.get("total_action_cost", 0.0)
    cost_delta = result.get("delta_vs_baseline", {}).get("total_action_cost", 0.0)

    # Per-context accuracy from last slice
    ctx_str = ""
    slices_data = lam.get("slice_summaries", [])
    if slices_data:
        last = slices_data[-1]
        ca = last.get("context_accuracy", {})
        if ca:
            ctx_str = " | " + " ".join(f"{k}={v:.2f}" for k, v in sorted(ca.items()))

    return (
        f"  {benchmark_id:6s} {task_key:6s}  "
        f"base={base_acc:.3f}  lam={lam_acc:.3f}  d={delta:+.3f}  "
        f"cost={cost:.1f}({cost_delta:+.1f})  "
        f"slices={slices} [{decision}]{ctx_str}"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(
        description="Evaluate laminated Phase 8 on B/C benchmarks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Target selection
    p.add_argument("-b", "--benchmark", default="B2S1",
                   help="Benchmark ID (e.g. B2S5, C3S3). Use --sweep for multiple.")
    p.add_argument("-t", "--task", default="task_a",
                   help="Task key: task_a / task_b / task_c.")
    p.add_argument("--all-tasks", action="store_true",
                   help="Run all three tasks (task_a, task_b, task_c).")
    p.add_argument("--sweep", default=None,
                   help=(
                       "Comma-separated benchmark IDs, or shorthand: "
                       "'all-b' (all B scales), 'all-c' (all C scales), "
                       "'all' (all B+C). Runs each with current settings."
                   ))

    # Mode & policy
    p.add_argument("-m", "--mode",
                   choices=("visible", "latent", "growth-visible", "growth-latent"),
                   default="visible")
    p.add_argument("--cap", "--capability-policy", dest="capability_policy",
                   default="self-selected",
                   help="Capability policy for non-growth modes.")
    p.add_argument("--reg", "--regulator-type", dest="regulator_type",
                   choices=("heuristic", "learning", "real"), default="heuristic",
                   help="Regulator type: heuristic / learning / real.")

    # Run parameters
    p.add_argument("-s", "--seed", type=int, default=13)
    p.add_argument("--slices", "--max-slices", dest="max_slices", type=int, default=5,
                   help="Maximum slice count.")
    p.add_argument("--budget", "--initial-cycle-budget", dest="budget", default="auto",
                   help="Cycles per slice, or 'auto' to compute scenario.cycles // slices.")
    p.add_argument("--thresh", "--accuracy-threshold", dest="accuracy_threshold",
                   type=float, default=0.0,
                   help="Min-context accuracy threshold to trigger settle (0 = disabled).")

    # Output
    p.add_argument("--output", type=str, default=None,
                   help="Explicit output path. Default: auto-generate in docs/experiment_outputs/.")
    p.add_argument("--no-output", action="store_true",
                   help="Skip writing output file.")
    p.add_argument("--compact", action="store_true",
                   help="Print a compact summary table instead of full JSON.")

    args = p.parse_args()

    # Resolve benchmark list
    if args.sweep:
        raw = args.sweep.strip()
        if raw == "all-b":
            benchmark_ids = list(_B_IDS)
        elif raw == "all-c":
            benchmark_ids = list(_C_IDS)
        elif raw == "all":
            benchmark_ids = list(_B_IDS) + list(_C_IDS)
        else:
            benchmark_ids = [x.strip() for x in raw.split(",")]
    else:
        benchmark_ids = [args.benchmark]

    # Resolve task list
    task_keys = list(_ALL_TASKS) if args.all_tasks else [args.task]

    # Run all combinations
    results: list[tuple[str, str, dict]] = []
    for benchmark_id in benchmark_ids:
        for task_key in task_keys:
            # Resolve budget (auto per benchmark/task/mode)
            budget = _resolve_budget(
                args.budget,
                benchmark_id=benchmark_id,
                task_key=task_key,
                mode=args.mode,
                max_slices=args.max_slices,
            )

            # Resolve output path
            if args.no_output:
                output_path = None
            elif args.output and len(benchmark_ids) == 1 and len(task_keys) == 1:
                output_path = Path(args.output)
            else:
                output_path = None if args.compact else _auto_output_path(
                    benchmark_id=benchmark_id,
                    task_key=task_key,
                    mode=args.mode,
                    seed=args.seed,
                    max_slices=args.max_slices,
                    initial_cycle_budget=budget,
                    accuracy_threshold=args.accuracy_threshold,
                    regulator_type=args.regulator_type,
                )

            if args.sweep or args.all_tasks:
                print(
                    f"[laminated] {benchmark_id} {task_key} budget={budget} ...",
                    file=sys.stderr,
                    flush=True,
                )

            payload = evaluate_laminated_benchmark(
                benchmark_id=benchmark_id,
                task_key=task_key,
                mode=args.mode,
                seed=args.seed,
                capability_policy=args.capability_policy,
                max_slices=args.max_slices,
                initial_cycle_budget=budget,
                accuracy_threshold=args.accuracy_threshold,
                regulator_type=args.regulator_type,
                output_path=output_path,
            )
            results.append((benchmark_id, task_key, payload))

            if output_path is not None:
                print(f"[laminated] wrote {output_path}", file=sys.stderr)

    # Output
    if args.compact:
        print(
            f"{'benchmark':6s} {'task':6s}  "
            f"base      lam       delta   cost(delta)      slices"
        )
        print("-" * 75)
        for bid, tid, r in results:
            print(_compact_row(bid, tid, r))
    elif len(results) == 1:
        print(json.dumps(results[0][2], indent=2))
    else:
        print(json.dumps({f"{bid}/{tid}": r for bid, tid, r in results}, indent=2))


if __name__ == "__main__":
    main()
