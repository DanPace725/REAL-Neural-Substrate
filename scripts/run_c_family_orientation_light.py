from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .c_family_orientation_light import (
    CFamilyOrientationLightConfig,
    run_c_family_orientation_light,
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
        prog="run_c_family_orientation_light",
        description="Lightweight C-family orientation -> challenge harness for REAL.",
    )
    parser.add_argument("--benchmark", default="C3S1")
    parser.add_argument("--challenge-task", default="task_c")
    parser.add_argument("--orientation-tasks", nargs="*", default=["task_a"])
    parser.add_argument("--mode", choices=("visible", "latent", "growth-visible", "growth-latent"), default="visible")
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--capability-policy", default="self-selected")
    parser.add_argument("--regulator-type", choices=("heuristic", "learning", "real", "gradient"), default="gradient")
    parser.add_argument("--budget", type=int, default=6)
    parser.add_argument("--orientation-safety", type=int, default=12)
    parser.add_argument("--challenge-safety", type=int, default=40)
    parser.add_argument("--thresh", type=float, default=0.8)
    parser.add_argument("--output-json", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    started = time.perf_counter()
    result = run_c_family_orientation_light(
        CFamilyOrientationLightConfig(
            benchmark_id=args.benchmark,
            challenge_task_key=args.challenge_task,
            orientation_task_keys=tuple(args.orientation_tasks),
            mode=args.mode,
            seed=args.seed,
            capability_policy=args.capability_policy,
            regulator_type=args.regulator_type,
            initial_cycle_budget=args.budget,
            orientation_safety_limit=args.orientation_safety,
            challenge_safety_limit=args.challenge_safety,
            challenge_accuracy_threshold=args.thresh,
        )
    )
    result["manifest"] = {
        "run_id": (
            f"c_orient_{args.benchmark.lower()}_{args.challenge_task}_"
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
            f"{datetime.now().strftime('%Y%m%d')}_corient_{args.benchmark.lower()}_{args.challenge_task}_{args.mode}_"
            f"b{args.budget}_t{str(args.thresh).replace('.', '')}_{args.regulator_type}_seed{args.seed}.json"
        )
    output_path = Path(output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    challenge = result["challenge_phase"]["result"]
    print(f"wrote {output_path}")
    print(
        f"challenge final={challenge['final_accuracy']:.4f} "
        f"floor={challenge['floor_accuracy']:.4f} "
        f"slices={challenge['slice_count']} "
        f"decision={challenge['final_decision']}"
    )
    if result["orientation_phases"]:
        print(
            "orientation "
            + ", ".join(
                f"{phase['task_key']}:{phase['result']['final_accuracy']:.4f}/{phase['result']['slice_count']}"
                for phase in result["orientation_phases"]
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
