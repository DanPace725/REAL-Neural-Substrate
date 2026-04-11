"""Evaluate laminated Phase 8 slices on A/B/C benchmarks.

The loop is criteria-driven: the slow layer decides when to stop (GCO).
There is no pre-allocated cycle/slice budget.  The --budget flag sets the
*initial* cycles-per-slice; the regulator adjusts from there.

Typical usage
-------------
# Single run
python -m scripts.evaluate_laminated_phase8 -b B2S5 -m visible --thresh 0.8 --reg real

# Sweep all B scales, compact summary
python -m scripts.evaluate_laminated_phase8 --sweep B2S1,B2S3,B2S5 --reg real --compact

# All tasks on C3S5
python -m scripts.evaluate_laminated_phase8 -b C3S5 --all-tasks --reg real

# All A scales through S4
python -m scripts.evaluate_laminated_phase8 --sweep A1,A2,A3,A4 --reg real --compact

# All A + B + C scales (large run)
python -m scripts.evaluate_laminated_phase8 --sweep all --reg real --compact
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from phase8 import (
    DEFAULT_LOCAL_UNIT_PRESET,
    evaluate_laminated_scenario,
    pulse_local_unit_preset_names,
    scenario_with_topology_mode,
)
from real_core import WORLD_MODEL_ASSISTANCE_MODES
from scripts.compare_a_scale_suite import a_scale_suite_by_id
from scripts.compare_b_scale_suite import b_scale_suite_by_id
from scripts.compare_c_scale_suite import c_scale_suite_by_id
from scripts.experiment_manifest import build_run_manifest, write_run_manifest

EXPERIMENT_OUTPUTS_DIR = Path(__file__).parent.parent / "docs" / "experiment_outputs"

_A_IDS = ("A1", "A2", "A3", "A4", "A5", "A6")
_B_IDS = ("B2S1", "B2S2", "B2S3", "B2S4", "B2S5", "B2S6")
_C_IDS = ("C3S1", "C3S2", "C3S3", "C3S4", "C3S5", "C3S6")
_ALL_TASKS = ("task_a", "task_b", "task_c")


# ---------------------------------------------------------------------------
# Budget helpers
# ---------------------------------------------------------------------------

_DEFAULT_SLICE_BUDGET = 8


# ---------------------------------------------------------------------------
# Output path helpers
# ---------------------------------------------------------------------------

def _auto_output_path(
    *,
    benchmark_id: str,
    task_key: str,
    mode: str,
    seed: int,
    initial_cycle_budget: int,
    accuracy_threshold: float,
    regulator_type: str,
    local_unit_mode: str,
    local_unit_preset: str,
    topology_mode: str,
    max_atp: float,
    world_model_assistance_mode: str,
) -> Path:
    date_str = datetime.now().strftime("%Y%m%d")
    mode_slug = mode.replace("-", "_")
    local_unit_slug = "" if local_unit_mode == "legacy" else f"_{local_unit_mode}"
    local_unit_preset_slug = "" if local_unit_preset == DEFAULT_LOCAL_UNIT_PRESET else f"_{local_unit_preset}"
    topology_slug = "" if topology_mode == "legacy" else f"_{topology_mode}"
    atp_slug = "" if abs(float(max_atp) - 1.0) < 1e-9 else f"_atp{str(float(max_atp)).replace('.', 'p')}"
    thresh_slug = f"_t{str(accuracy_threshold).replace('.', '')}" if accuracy_threshold > 0.0 else ""
    reg_slug = f"_{regulator_type}" if regulator_type != "heuristic" else ""
    assist_slug = "" if world_model_assistance_mode == "off" else f"_wm{world_model_assistance_mode}"
    filename = (
        f"{date_str}_laminated_{benchmark_id.lower()}_{task_key}_{mode_slug}"
        f"{local_unit_slug}{local_unit_preset_slug}{topology_slug}{atp_slug}{assist_slug}_b{initial_cycle_budget}{thresh_slug}{reg_slug}_seed{seed}.json"
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
    initial_cycle_budget: int = 8,
    accuracy_threshold: float = 0.0,
    regulator_type: str = "heuristic",
    safety_limit: int = 200,
    output_path: Path | None = None,
    local_unit_mode: str = "legacy",
    local_unit_preset: str = DEFAULT_LOCAL_UNIT_PRESET,
    topology_mode: str = "legacy",
    max_atp: float = 1.0,
    force_expected_transform_at_sink: bool = False,
    teacher_trace_mode: str = "off",
    teacher_transform_policy: str = "source_then_identity",
    teacher_force_nodes: list[str] | None = None,
    c_task_layer1_mode: str = "legacy",
    world_model_enabled: bool = True,
    world_model_assistance_mode: str = "off",
    world_model_assistance_confidence_threshold: float = 0.45,
) -> dict[str, object]:
    if benchmark_id.startswith("A"):
        if topology_mode != "legacy":
            raise ValueError("Topology mode overrides are currently limited to C-family benchmarks.")
        case = a_scale_suite_by_id()[benchmark_id]
        benchmark_family = "A"
    elif benchmark_id.startswith("B"):
        if topology_mode != "legacy":
            raise ValueError("Topology mode overrides are currently limited to C-family benchmarks.")
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
    if benchmark_family == "C":
        scenario = scenario_with_topology_mode(scenario, topology_mode)

    resolved_capability_policy = mode if mode.startswith("growth-") else capability_policy

    result = evaluate_laminated_scenario(
        scenario,
        benchmark_family=benchmark_family,
        task_key=task_key,
        seed=seed,
        capability_policy=resolved_capability_policy,
        local_unit_mode=local_unit_mode,
        local_unit_preset=local_unit_preset,
        max_atp=max_atp,
        force_expected_transform_at_sink=force_expected_transform_at_sink,
        teacher_trace_mode=teacher_trace_mode,
        teacher_transform_policy=teacher_transform_policy,
        teacher_force_nodes=teacher_force_nodes,
        c_task_layer1_mode=c_task_layer1_mode,
        initial_cycle_budget=initial_cycle_budget,
        accuracy_threshold=accuracy_threshold,
        regulator_type=regulator_type,
        safety_limit=safety_limit,
        world_model_enabled=world_model_enabled,
        world_model_assistance_mode=world_model_assistance_mode,
        world_model_assistance_confidence_threshold=world_model_assistance_confidence_threshold,
    )
    result.update({
        "benchmark_id": benchmark_id,
        "task_key": task_key,
        "mode": mode,
        "capability_policy": resolved_capability_policy,
        "local_unit_mode": local_unit_mode,
        "local_unit_preset": local_unit_preset,
        "topology_mode": topology_mode,
        "max_atp": max_atp,
        "force_expected_transform_at_sink": bool(force_expected_transform_at_sink),
        "teacher_trace_mode": teacher_trace_mode,
        "teacher_transform_policy": teacher_transform_policy,
        "teacher_force_nodes": list(teacher_force_nodes or []),
        "c_task_layer1_mode": c_task_layer1_mode,
        "world_model_enabled": bool(world_model_enabled),
        "world_model_assistance_mode": world_model_assistance_mode,
        "world_model_assistance_confidence_threshold": world_model_assistance_confidence_threshold,
        "topology_node_count": len(scenario.positions),
        "topology_depth": max(int(position) for position in scenario.positions.values()),
        "seed": seed,
    })

    if output_path is not None:
        manifest = build_run_manifest(
            harness="laminated_phase8",
            seeds=[seed],
            scenarios=[benchmark_id],
            metadata={
                "task_key": task_key,
                "mode": mode,
                "capability_policy": resolved_capability_policy,
                "local_unit_mode": local_unit_mode,
                "local_unit_preset": local_unit_preset,
                "topology_mode": topology_mode,
                "max_atp": max_atp,
                "force_expected_transform_at_sink": force_expected_transform_at_sink,
                "teacher_trace_mode": teacher_trace_mode,
                "teacher_transform_policy": teacher_transform_policy,
                "teacher_force_nodes": list(teacher_force_nodes or []),
                "c_task_layer1_mode": c_task_layer1_mode,
                "world_model_enabled": world_model_enabled,
                "world_model_assistance_mode": world_model_assistance_mode,
                "world_model_assistance_confidence_threshold": world_model_assistance_confidence_threshold,
                "initial_cycle_budget": initial_cycle_budget,
                "accuracy_threshold": accuracy_threshold,
                "regulator_type": regulator_type,
                "safety_limit": safety_limit,
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
    slices_data = lam.get("slice_summaries", [])
    slices = len(slices_data)
    decision = lam.get("final_decision", "?")

    final_acc = 0.0
    floor_acc = 0.0
    ctx_str = ""
    forecast_str = ""
    if slices_data:
        last = slices_data[-1]
        metadata = last.get("metadata", {})
        final_acc = metadata.get(
            "final_accuracy",
            metadata.get("mean_bit_accuracy", 0.0),
        )
        floor_acc = metadata.get("floor_accuracy", 0.0)
        forecast_metrics = last.get("metadata", {}).get("forecast_metrics", {})
        forecast_acc = forecast_metrics.get("forecast_accuracy")
        if isinstance(forecast_acc, (int, float)):
            forecast_str = f"  forecast={forecast_acc:.3f}"
        ca = last.get("context_accuracy", {})
        if ca:
            ctx_str = " | " + " ".join(f"{k}={v:.2f}" for k, v in sorted(ca.items()))

    return (
        f"  {benchmark_id:6s} {task_key:6s}  "
        f"final={final_acc:.3f} floor={floor_acc:.3f}  "
        f"slices={slices} [{decision}]{forecast_str}{ctx_str}"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(
        description="Evaluate laminated Phase 8 on A/B/C benchmarks.",
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
                       "'all-a' (all A scales), 'all-b' (all B scales), "
                       "'all-c' (all C scales), "
                       "'all' (all A+B+C). Runs each with current settings."
                   ))

    # Mode & policy
    p.add_argument("-m", "--mode",
                   choices=("visible", "latent", "growth-visible", "growth-latent"),
                   default="visible")
    p.add_argument("--cap", "--capability-policy", dest="capability_policy",
                   default="self-selected",
                   help="Capability policy for non-growth modes.")
    p.add_argument("--reg", "--regulator-type", dest="regulator_type",
                   choices=("heuristic", "learning", "real", "gradient"), default="heuristic",
                   help="Regulator type: heuristic / learning / real / gradient.")
    p.add_argument(
        "--local-unit-mode",
        choices=("legacy", "pulse_local_unit"),
        default="legacy",
        help="Opt-in Phase 8 local-unit runtime mode. Use pulse_local_unit for the C/HR pilot.",
    )
    p.add_argument(
        "--local-unit-preset",
        choices=pulse_local_unit_preset_names(),
        default=DEFAULT_LOCAL_UNIT_PRESET,
        help="Named pulse-local-unit preset. Only affects pulse_local_unit mode.",
    )
    p.add_argument(
        "--topology-mode",
        choices=("legacy", "bounded_overlap_13715"),
        default="legacy",
        help="Opt-in topology override. Currently applied only to C-family laminated runs.",
    )
    p.add_argument(
        "--max-atp",
        dest="max_atp",
        type=float,
        default=1.0,
        help="Per-node ATP capacity for this run. Values above 1.0 give nodes more energy headroom.",
    )
    p.add_argument(
        "--force-expected-transform-at-sink",
        action="store_true",
        help="Diagnostic mode: override the last-hop transform with the task-correct transform at sink delivery.",
    )
    p.add_argument(
        "--teacher-trace-mode",
        choices=("off", "observe", "force"),
        default="off",
        help="Packet-level teacher trace mode. 'force' can override transforms on selected nodes.",
    )
    p.add_argument(
        "--teacher-transform-policy",
        choices=("source_then_identity", "source_only", "sink_only"),
        default="source_then_identity",
        help="Canonical answer-key transform policy used by teacher trace.",
    )
    p.add_argument(
        "--teacher-force-nodes",
        default="",
        help="Comma-separated node ids to force under teacher-trace force mode. Empty means force all nodes.",
    )
    p.add_argument(
        "--c-task-layer1-mode",
        choices=("legacy", "stabilized", "communicative"),
        default="legacy",
        help="Dedicated C-family Layer 1 mode. 'stabilized' is hard-guided; 'communicative' uses packet-level preserve/reopen signals without hard pruning.",
    )
    p.add_argument(
        "--world-model",
        dest="world_model_enabled",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable or disable the Layer 3 world model.",
    )
    p.add_argument(
        "--wm-assist",
        choices=WORLD_MODEL_ASSISTANCE_MODES,
        default="off",
        help="Assisted Layer 3 mode: off, hinted, guided, or teacher.",
    )
    p.add_argument(
        "--wm-assist-threshold",
        dest="world_model_assistance_confidence_threshold",
        type=float,
        default=0.45,
        help="Minimum assistance confidence required before the assist activates.",
    )

    # Run parameters
    p.add_argument("-s", "--seed", type=int, default=13)
    p.add_argument("--budget", "--initial-cycle-budget", dest="budget", type=int,
                   default=_DEFAULT_SLICE_BUDGET,
                   help="Cycles per slice (initial; slow layer regulates from here).")
    p.add_argument("--safety-limit", dest="safety_limit", type=int, default=200,
                   help="Safety guard on max slices to prevent runaway loops (not a budget).")
    p.add_argument("--thresh", "--accuracy-threshold", dest="accuracy_threshold",
                   type=float, default=0.0,
                   help="Final overall accuracy threshold to trigger settle (0 = disabled).")

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
        if raw == "all-a":
            benchmark_ids = list(_A_IDS)
        elif raw == "all-b":
            benchmark_ids = list(_B_IDS)
        elif raw == "all-c":
            benchmark_ids = list(_C_IDS)
        elif raw == "all":
            benchmark_ids = list(_A_IDS) + list(_B_IDS) + list(_C_IDS)
        else:
            benchmark_ids = [x.strip() for x in raw.split(",")]
    else:
        benchmark_ids = [args.benchmark]

    # Resolve task list
    task_keys = list(_ALL_TASKS) if args.all_tasks else [args.task]

    # Run all combinations
    results: list[tuple[str, str, dict]] = []
    teacher_force_nodes = [
        node_id.strip()
        for node_id in str(args.teacher_force_nodes or "").split(",")
        if node_id.strip()
    ]
    for benchmark_id in benchmark_ids:
        for task_key in task_keys:
            budget = args.budget

            # Resolve output path
            if args.no_output:
                output_path = None
            elif args.output and len(benchmark_ids) == 1 and len(task_keys) == 1:
                output_path = Path(args.output)
            else:
                output_path = _auto_output_path(
                    benchmark_id=benchmark_id,
                    task_key=task_key,
                    mode=args.mode,
                    seed=args.seed,
                    initial_cycle_budget=budget,
                    accuracy_threshold=args.accuracy_threshold,
                    regulator_type=args.regulator_type,
                    local_unit_mode=args.local_unit_mode,
                    local_unit_preset=args.local_unit_preset,
                    topology_mode=args.topology_mode,
                    max_atp=args.max_atp,
                    world_model_assistance_mode=args.wm_assist,
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
                initial_cycle_budget=budget,
                accuracy_threshold=args.accuracy_threshold,
                regulator_type=args.regulator_type,
                safety_limit=args.safety_limit,
                output_path=output_path,
                local_unit_mode=args.local_unit_mode,
                local_unit_preset=args.local_unit_preset,
                topology_mode=args.topology_mode,
                max_atp=args.max_atp,
                force_expected_transform_at_sink=args.force_expected_transform_at_sink,
                teacher_trace_mode=args.teacher_trace_mode,
                teacher_transform_policy=args.teacher_transform_policy,
                teacher_force_nodes=teacher_force_nodes,
                c_task_layer1_mode=args.c_task_layer1_mode,
                world_model_enabled=args.world_model_enabled,
                world_model_assistance_mode=args.wm_assist,
                world_model_assistance_confidence_threshold=args.world_model_assistance_confidence_threshold,
            )
            results.append((benchmark_id, task_key, payload))

            if output_path is not None:
                print(f"[laminated] wrote {output_path}", file=sys.stderr)

    # Output
    if args.compact:
        print(
            f"{'benchmark':6s} {'task':6s}  "
            f"final     slices"
        )
        print("-" * 55)
        for bid, tid, r in results:
            print(_compact_row(bid, tid, r))
    elif len(results) == 1:
        print(json.dumps(results[0][2], indent=2))
    else:
        print(json.dumps({f"{bid}/{tid}": r for bid, tid, r in results}, indent=2))


if __name__ == "__main__":
    main()
