from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .c_family_train_eval_light import (
    CFamilyTrainEvalLightConfig,
    run_c_family_train_eval_light,
)


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip() or None
    except Exception:
        return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_c_family_train_eval_light",
        description="Lightweight C-family train-then-held-out-eval harness for REAL.",
    )
    parser.add_argument("--benchmark", default="C3S1")
    parser.add_argument("--task", default="task_c")
    parser.add_argument("--mode", choices=("visible", "latent", "growth-visible", "growth-latent"), default="visible")
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--capability-policy", default="self-selected")
    parser.add_argument("--regulator-type", choices=("heuristic", "learning", "real", "gradient"), default="gradient")
    parser.add_argument("--budget", type=int, default=6)
    parser.add_argument("--train-ratio", type=float, default=0.6)
    parser.add_argument("--train-safety", type=int, default=12)
    parser.add_argument("--eval-safety", type=int, default=12)
    parser.add_argument("--eval-feedback-fraction", type=float, default=0.0)
    parser.add_argument("--thresh", type=float, default=0.8)
    parser.add_argument("--output-json", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    started = time.perf_counter()
    result = run_c_family_train_eval_light(
        CFamilyTrainEvalLightConfig(
            benchmark_id=args.benchmark,
            task_key=args.task,
            mode=args.mode,
            seed=args.seed,
            capability_policy=args.capability_policy,
            regulator_type=args.regulator_type,
            initial_cycle_budget=args.budget,
            train_ratio=args.train_ratio,
            train_safety_limit=args.train_safety,
            eval_safety_limit=args.eval_safety,
            eval_accuracy_threshold=args.thresh,
            eval_feedback_fraction=args.eval_feedback_fraction,
        )
    )
    result["manifest"] = {
        "run_id": (
            f"ctrain_{args.benchmark.lower()}_{args.task}_"
            f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
        ),
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": _git_sha(),
        "elapsed_seconds": round(time.perf_counter() - started, 2),
    }

    output_json = args.output_json
    if output_json is None:
        output_json = (
            "docs/experiment_outputs/"
            f"{datetime.now().strftime('%Y%m%d')}_ctrain_{args.benchmark.lower()}_{args.task}_{args.mode}_"
            f"b{args.budget}_r{str(args.train_ratio).replace('.', '')}_ef{str(args.eval_feedback_fraction).replace('.', '')}_"
            f"t{str(args.thresh).replace('.', '')}_{args.regulator_type}_seed{args.seed}.json"
        )
    output_path = Path(output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    train_phase = result["train_phase"]
    eval_phase = result["eval_phase"]
    print(f"wrote {output_path}")
    print(
        f"train final={train_phase['final_accuracy']:.4f} "
        f"floor={train_phase['floor_accuracy']:.4f} "
        f"slices={train_phase['slice_count']} "
        f"decision={train_phase['final_decision']}"
    )
    print(
        f"eval  final={eval_phase['final_accuracy']:.4f} "
        f"floor={eval_phase['floor_accuracy']:.4f} "
        f"slices={eval_phase['slice_count']} "
        f"decision={eval_phase['final_decision']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
