"""
run_occupancy_real_v2.py
------------------------
CLI runner for the redesigned REAL occupancy experiment. Runs all conditions
in PARALLEL using ProcessPoolExecutor (one process per condition).

Conditions run by default:
  v2_live      — eval feedback on (1.0), continuous system, no context
  v2_carryover — eval feedback on (1.0), fresh_eval substrate carryover, no context

Optional (via --context co2_high|class):
  v2_live_ctx_<name>  — v2_live + context bit
  v2_carry_ctx_<name> — v2_carryover + context bit

Optional (via --v1-baseline):
  v1_baseline  — original protocol (feedback off in eval) for comparison

Default episode caps: 500 train / 250 eval (~37% of dataset, ~2-3 min with 2 conditions).
Use --max-train-episodes / --max-eval-episodes to override.

Usage:
  python -m scripts.run_occupancy_real_v2 --preset synth_v1_default --selector-seed 13
  python -m scripts.run_occupancy_real_v2 --selector-seed 13 --context co2_high
  python -m scripts.run_occupancy_real_v2 --selector-seed 13 --max-train-episodes 800 --max-eval-episodes 300
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from occupancy_baseline import get_preset
from scripts.occupancy_real import OccupancyRealConfig, run_occupancy_real_experiment
from scripts.occupancy_real_v2 import OccupancyRealV2Config, run_occupancy_real_v2_experiment


# ---------------------------------------------------------------------------
# Condition spec — plain data so it is picklable across processes
# ---------------------------------------------------------------------------

class ConditionSpec(NamedTuple):
    name: str
    description: str
    kind: str          # "v1" or "v2"
    v1_config: OccupancyRealConfig | None
    v2_config: OccupancyRealV2Config | None


def _run_condition(spec: ConditionSpec) -> dict[str, object]:
    """Top-level function so ProcessPoolExecutor can pickle it."""
    if spec.kind == "v1":
        result = run_occupancy_real_experiment(spec.v1_config)
    else:
        result = run_occupancy_real_v2_experiment(spec.v2_config)
    return {
        "name": spec.name,
        "description": spec.description,
        "result": result,
    }


# ---------------------------------------------------------------------------
# Condition builder
# ---------------------------------------------------------------------------

def build_conditions(
    *,
    preset_name: str,
    selector_seed: int,
    max_train_episodes: int | None,
    max_eval_episodes: int | None,
    summary_only: bool,
    context_bit_source: str,
    include_v1_baseline: bool,
) -> list[ConditionSpec]:
    preset = get_preset(preset_name)
    cfg = preset.config
    specs: list[ConditionSpec] = []

    if include_v1_baseline:
        specs.append(ConditionSpec(
            name="v1_baseline",
            description="Original protocol: no feedback in eval, continuous, no context",
            kind="v1",
            v1_config=OccupancyRealConfig(
                csv_path=cfg.csv_path,
                window_size=cfg.window_size,
                train_fraction=cfg.train_fraction,
                normalize=cfg.normalize,
                selector_seed=selector_seed,
                max_train_episodes=max_train_episodes,
                max_eval_episodes=max_eval_episodes,
                summary_only=summary_only,
            ),
            v2_config=None,
        ))

    def v2(name: str, desc: str, carryover_mode: str, ctx: str) -> ConditionSpec:
        return ConditionSpec(
            name=name,
            description=desc,
            kind="v2",
            v1_config=None,
            v2_config=OccupancyRealV2Config(
                csv_path=cfg.csv_path,
                window_size=cfg.window_size,
                train_fraction=cfg.train_fraction,
                normalize=cfg.normalize,
                selector_seed=selector_seed,
                eval_feedback_fraction=1.0,
                carryover_mode=carryover_mode,
                context_bit_source=ctx,
                max_train_episodes=max_train_episodes,
                max_eval_episodes=max_eval_episodes,
                summary_only=summary_only,
            ),
        )

    specs.append(v2("v2_live", "Eval feedback on, continuous, no context", "continuous", "none"))
    specs.append(v2("v2_carryover", "Eval feedback on, fresh substrate carryover, no context", "fresh_eval", "none"))

    if context_bit_source != "none":
        specs.append(v2(
            f"v2_live_ctx_{context_bit_source}",
            f"Eval feedback on, continuous, context={context_bit_source}",
            "continuous", context_bit_source,
        ))
        specs.append(v2(
            f"v2_carry_ctx_{context_bit_source}",
            f"Eval feedback on, fresh carryover, context={context_bit_source}",
            "fresh_eval", context_bit_source,
        ))

    return specs


# ---------------------------------------------------------------------------
# Parallel runner
# ---------------------------------------------------------------------------

def run_all_conditions_parallel(
    specs: list[ConditionSpec],
    *,
    workers: int,
) -> list[dict[str, object]]:
    """
    Run each condition in a separate process. All REAL systems are fully
    independent so there is no shared mutable state.
    Falls back to sequential if workers=1 or spawn is unavailable.
    """
    n = len(specs)
    effective_workers = min(workers, n)

    if effective_workers <= 1:
        return [_run_condition(spec) for spec in specs]

    conditions: list[dict[str, object]] = [{}] * n
    name_to_index = {spec.name: i for i, spec in enumerate(specs)}

    with ProcessPoolExecutor(max_workers=effective_workers) as ex:
        futures = {ex.submit(_run_condition, spec): spec.name for spec in specs}
        for future in as_completed(futures):
            cond_name = futures[future]
            idx = name_to_index[cond_name]
            try:
                conditions[idx] = future.result()
            except Exception as exc:
                print(f"[ERROR] Condition '{cond_name}' failed: {exc}", file=sys.stderr)
                conditions[idx] = {"name": cond_name, "description": "", "result": {}, "error": str(exc)}

    return conditions


# ---------------------------------------------------------------------------
# Aggregate table
# ---------------------------------------------------------------------------

def build_aggregate(conditions: list[dict[str, object]]) -> dict[str, object]:
    metrics_keys = ("accuracy", "precision", "recall", "f1")
    aggregate: dict[str, object] = {}
    for cond in conditions:
        if not cond or "result" not in cond:
            continue
        cond_name = str(cond["name"])
        result = cond["result"]
        if not result:
            continue
        train_summary = dict(result.get("train_summary", {}))
        eval_summary = dict(result.get("eval_summary", {}))
        agg: dict[str, object] = {}
        for mk in metrics_keys:
            agg[f"train_{mk}"] = float(train_summary.get("metrics", {}).get(mk, 0.0))
            agg[f"eval_{mk}"] = float(eval_summary.get("metrics", {}).get(mk, 0.0))
        agg["train_mean_delivered"] = float(train_summary.get("mean_delivered_packets", 0.0))
        agg["eval_mean_delivered"] = float(eval_summary.get("mean_delivered_packets", 0.0))
        agg["train_mean_dropped"] = float(train_summary.get("mean_dropped_packets", 0.0))
        agg["eval_mean_dropped"] = float(eval_summary.get("mean_dropped_packets", 0.0))
        agg["eval_mean_feedback_events"] = float(eval_summary.get("mean_feedback_events", 0.0))
        aggregate[cond_name] = agg
    return aggregate


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _default_output_path(selector_seed: int) -> Path:
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    return Path("docs/experiment_outputs") / f"occupancy_real_v2_seed{selector_seed}_{date_str}.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run redesigned REAL occupancy conditions in parallel."
    )
    parser.add_argument("--preset", default="synth_v1_default")
    parser.add_argument("--selector-seed", type=int, default=13)
    parser.add_argument(
        "--max-train-episodes", type=int, default=500,
        help="Training episode cap per condition (default: 500, ~37%% of dataset)",
    )
    parser.add_argument(
        "--max-eval-episodes", type=int, default=250,
        help="Eval episode cap per condition (default: 250)",
    )
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument(
        "--context", default="none", choices=["none", "class", "co2_high"],
        help="Optional context bit source (adds 2 extra conditions)",
    )
    parser.add_argument(
        "--v1-baseline", action="store_true",
        help="Include v1 baseline condition (feedback off in eval)",
    )
    parser.add_argument(
        "--workers", type=int, default=4,
        help="Number of parallel worker processes (default: 4)",
    )
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(
        f"Building conditions: seed={args.selector_seed}, "
        f"train={args.max_train_episodes}, eval={args.max_eval_episodes}, "
        f"context={args.context}, workers={args.workers}"
    )

    specs = build_conditions(
        preset_name=args.preset,
        selector_seed=args.selector_seed,
        max_train_episodes=args.max_train_episodes,
        max_eval_episodes=args.max_eval_episodes,
        summary_only=args.summary_only,
        context_bit_source=args.context,
        include_v1_baseline=args.v1_baseline,
    )
    print(f"Running {len(specs)} conditions in parallel (workers={args.workers})...")

    t0 = datetime.now(timezone.utc)
    conditions = run_all_conditions_parallel(specs, workers=args.workers)
    elapsed = (datetime.now(timezone.utc) - t0).total_seconds()

    aggregate = build_aggregate(conditions)
    result = {
        "title": f"REAL Occupancy v2 — seed {args.selector_seed}",
        "timestamp": t0.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "preset": args.preset,
        "selector_seed": args.selector_seed,
        "elapsed_seconds": round(elapsed, 1),
        "conditions": conditions,
        "aggregate": aggregate,
    }

    output_path = Path(args.output) if args.output else _default_output_path(args.selector_seed)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    # Console summary table
    print(f"\nDone in {elapsed:.1f}s  →  {output_path}\n")
    print(f"{'Condition':<35} {'Tr Acc':>8} {'Ev Acc':>8} {'Ev F1':>8} {'Ev Drop':>9} {'Ev Fdbk':>9}")
    print("-" * 82)
    for cond_name, agg in aggregate.items():
        print(
            f"{cond_name:<35}"
            f" {float(agg['train_accuracy']):>8.4f}"
            f" {float(agg['eval_accuracy']):>8.4f}"
            f" {float(agg['eval_f1']):>8.4f}"
            f" {float(agg['eval_mean_dropped']):>9.2f}"
            f" {float(agg['eval_mean_feedback_events']):>9.2f}"
        )
    print()


if __name__ == "__main__":
    main()
