"""
run_occupancy_real_v3_light.py
------------------------------
CLI entrypoint for the lightweight REAL-native occupancy runner.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .occupancy_real_v3_light import (
    OccupancyRealV3LightConfig,
    run_occupancy_real_v3_light,
)


def _git_sha() -> str | None:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return sha or None
    except Exception:
        return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_occupancy_real_v3_light",
        description="Lightweight REAL-native occupancy runner with warmup + rolling prediction.",
    )
    parser.add_argument("--csv", default="occupancy_baseline/data/occupancy_synth_v1.csv")
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--selector-seed", type=int, default=13)
    parser.add_argument("--warmup-sessions", type=int, default=8)
    parser.add_argument("--prediction-sessions", type=int, default=8)
    parser.add_argument("--rolling-window", type=int, default=3)
    parser.add_argument("--feedback-amount", type=float, default=0.18)
    parser.add_argument("--prediction-feedback-fraction", type=float, default=0.35)
    parser.add_argument("--packet-ttl", type=int, default=8)
    parser.add_argument("--topology-mode", default="multihop_routing")
    parser.add_argument("--context-mode", default="online_running_context")
    parser.add_argument("--ingress-mode", default="admission_source")
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--summary-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    started = time.perf_counter()
    config = OccupancyRealV3LightConfig(
        csv_path=args.csv,
        window_size=args.window_size,
        selector_seed=args.selector_seed,
        warmup_sessions=args.warmup_sessions,
        prediction_sessions=args.prediction_sessions,
        rolling_window=args.rolling_window,
        feedback_amount=args.feedback_amount,
        prediction_feedback_fraction=args.prediction_feedback_fraction,
        packet_ttl=args.packet_ttl,
        topology_mode=args.topology_mode,
        context_mode=args.context_mode,
        ingress_mode=args.ingress_mode,
        summary_only=args.summary_only,
    )
    result = run_occupancy_real_v3_light(config)

    manifest = {
        "run_id": (
            f"v3light_seed{config.selector_seed}_"
            f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
        ),
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": _git_sha(),
        "elapsed_seconds": round(time.perf_counter() - started, 2),
    }
    result["manifest"] = manifest

    output_json = args.output_json
    if output_json is None:
        output_json = (
            "docs/experiment_outputs/"
            f"occupancy_real_v3_light_seed{config.selector_seed}_"
            f"{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
        )
    output_path = Path(output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    prediction_summary = result["prediction_summary"]
    recent_window = result["recent_prediction_window"]
    print(f"wrote {output_path}")
    print(
        "prediction "
        f"acc={prediction_summary['metrics'].get('accuracy', 0.0):.4f} "
        f"f1={prediction_summary['metrics'].get('f1', 0.0):.4f} "
        f"delivery={prediction_summary.get('mean_delivery_ratio', 0.0):.4f}"
    )
    print(
        "recent "
        f"window_acc={recent_window.get('recent_session_accuracy')} "
        f"window_delivery={recent_window.get('recent_session_delivery_ratio')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
