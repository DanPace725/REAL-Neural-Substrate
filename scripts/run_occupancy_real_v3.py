"""
run_occupancy_real_v3.py
------------------------
CLI entrypoint for the v3 REAL occupancy experiment.

This runner uses session-structured evaluation with carryover efficiency
measurement.  It does NOT produce a direct accuracy-vs-MLP comparison — the
primary outputs are learning curves, carryover efficiency ratios, and context
transfer probe results.

Basic usage
-----------
    python -m scripts.run_occupancy_real_v3 \\
        --csv occupancy_baseline/data/occupancy_synth_v1.csv

With JSON output
----------------
    python -m scripts.run_occupancy_real_v3 \\
        --csv occupancy_baseline/data/occupancy_synth_v1.csv \\
        --output-json docs/experiment_outputs/occupancy_v3_seed13.json

Quiet summary-only run
-----------------------
    python -m scripts.run_occupancy_real_v3 \\
        --csv occupancy_baseline/data/occupancy_synth_v1.csv \\
        --summary-only
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_occupancy_real_v3",
        description="V3 REAL occupancy experiment: session-structured carryover test",
    )
    p.add_argument(
        "--csv",
        default="occupancy_baseline/data/occupancy_synth_v1.csv",
        help="Path to occupancy CSV (default: occupancy_baseline/data/occupancy_synth_v1.csv)",
    )
    p.add_argument(
        "--window-size", type=int, default=5,
        help="Rolling window size for episode construction (default: 5)",
    )
    p.add_argument(
        "--selector-seed", type=int, default=13,
        help="Selector seed for the NativeSubstrateSystem (default: 13)",
    )
    p.add_argument(
        "--feedback-amount", type=float, default=0.18,
        help="Feedback amount per matched packet (default: 0.18)",
    )
    p.add_argument(
        "--eval-feedback-fraction", type=float, default=1.0,
        help="Fraction of feedback_amount applied during eval (default: 1.0 = full)",
    )
    p.add_argument(
        "--train-session-fraction", type=float, default=0.70,
        help="Fraction of sessions (temporal order) used for training (default: 0.70)",
    )
    p.add_argument(
        "--packet-ttl", type=int, default=8,
        help="Packet TTL cycles (default: 8)",
    )
    p.add_argument(
        "--output-json", default=None,
        help="Write full result to this JSON file",
    )
    p.add_argument(
        "--workers", type=int, default=2,
        help="Worker processes for warm/cold eval (2=parallel, 1=sequential; default: 2)",
    )
    p.add_argument(
        "--max-train-sessions", type=int, default=None,
        help="Cap training sessions (default: all).  Use for quick smoke tests.",
    )
    p.add_argument(
        "--max-eval-sessions", type=int, default=None,
        help="Cap eval sessions (default: all).  Use for quick smoke tests.",
    )
    p.add_argument(
        "--summary-only", action="store_true",
        help="Omit per-session result lists from JSON output",
    )
    return p


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


def _build_manifest(args: argparse.Namespace, elapsed: float | None = None) -> dict:
    """
    Compact run record printed at start and written into the JSON output.

    elapsed is None when the manifest is first printed (before the run),
    then filled in and the manifest is updated in the result dict after.
    """
    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    seed = args.selector_seed
    ts = run_at.replace(":", "").replace("-", "")[:15]          # 20260319T170000Z style
    return {
        "run_id": f"v3_seed{seed}_{ts}",
        "run_at": run_at,
        "git_sha": _git_sha(),
        "csv": args.csv,
        "selector_seed": seed,
        "window_size": args.window_size,
        "train_session_fraction": args.train_session_fraction,
        "max_train_sessions": args.max_train_sessions,
        "max_eval_sessions": args.max_eval_sessions,
        "workers": args.workers,
        "feedback_amount": args.feedback_amount,
        "eval_feedback_fraction": args.eval_feedback_fraction,
        "packet_ttl": args.packet_ttl,
        "summary_only": args.summary_only,
        "output_json": args.output_json,
        "elapsed_seconds": elapsed,
    }


def _print_manifest(manifest: dict) -> None:
    sep = "-" * 60
    print(f"\n{sep}")
    print(f"  run_id:   {manifest['run_id']}")
    print(f"  run_at:   {manifest['run_at']}")
    if manifest["git_sha"]:
        print(f"  git_sha:  {manifest['git_sha']}")
    print(f"  csv:      {manifest['csv']}")
    print(f"  seed:     {manifest['selector_seed']}  "
          f"window: {manifest['window_size']}  "
          f"train_frac: {manifest['train_session_fraction']}")
    caps = []
    if manifest["max_train_sessions"] is not None:
        caps.append(f"train<={manifest['max_train_sessions']}")
    if manifest["max_eval_sessions"] is not None:
        caps.append(f"eval<={manifest['max_eval_sessions']}")
    if caps:
        print(f"  caps:     {', '.join(caps)}")
    print(f"  workers:  {manifest['workers']}")
    if manifest["elapsed_seconds"] is not None:
        print(f"  elapsed:  {manifest['elapsed_seconds']:.1f}s")
    print(sep)


def _print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _print_inventory(label: str, inv: dict) -> None:
    print(f"\n{label}")
    print(f"  sessions:       {inv['session_count']}")
    print(f"  by label:       {inv['by_label']}")
    print(f"  by context:     {inv['by_context_code']}")
    ep = inv["episode_lengths"]
    print(f"  episode length: min={ep['min']}  mean={ep['mean']}  max={ep['max']}")
    print(f"  ctx by label:   {inv['context_codes_by_label']}")


def _print_summary(label: str, summary: dict) -> None:
    m = summary.get("metrics", {})
    print(f"\n{label}")
    print(f"  episodes:     {summary['episode_count']}")
    print(f"  accuracy:     {m.get('accuracy', '—'):.4f}")
    print(f"  F1:           {m.get('f1', '—'):.4f}")
    print(f"  precision:    {m.get('precision', '—'):.4f}")
    print(f"  recall:       {m.get('recall', '—'):.4f}")
    print(f"  mean dropped: {summary['mean_dropped_packets']:.2f}")
    print(f"  mean fdbk ev: {summary['mean_feedback_events']:.2f}")


def _print_efficiency(eff: dict) -> None:
    print("\nCarryover efficiency")
    print(f"  mean efficiency ratio:       {eff['mean_efficiency_ratio']}")
    print(f"  warm sessions to 80% deliv:  {eff['warm_sessions_to_80pct']}")
    print(f"  cold sessions to 80% deliv:  {eff['cold_sessions_to_80pct']}")

    print("\n  Delivery ratio at session N:")
    print(f"  {'Session':>10}  {'Warm':>8}  {'Cold':>8}  {'Ratio':>8}")
    warm_at = eff["warm_delivery_at"]
    cold_at = eff["cold_delivery_at"]
    for key in ("session_1", "session_5", "session_10", "session_20"):
        w = warm_at.get(key)
        c = cold_at.get(key)
        ratio = (
            f"{w / c:.4f}" if (w is not None and c is not None and c > 0) else "—"
        )
        w_str = f"{w:.4f}" if w is not None else "—"
        c_str = f"{c:.4f}" if c is not None else "—"
        label = key.replace("session_", "session ")
        print(f"  {label:>10}  {w_str:>8}  {c_str:>8}  {ratio:>8}")


def _print_transfer(probe: dict) -> None:
    print("\nContext transfer probe")
    print(f"  training context codes: {probe['training_context_codes']}")
    print(f"  seen   contexts (warm): {probe['warm_seen_mean_delivery']}  "
          f"({probe['warm_seen_session_count']} sessions)")
    print(f"  unseen contexts (warm): {probe['warm_unseen_mean_delivery']}  "
          f"({probe['warm_unseen_session_count']} sessions)")
    print(f"  seen   contexts (cold): {probe['cold_seen_mean_delivery']}")
    print(f"  unseen contexts (cold): {probe['cold_unseen_mean_delivery']}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Import here to keep startup fast
    from scripts.occupancy_real_v3 import OccupancyRealV3Config, run_occupancy_real_v3_experiment

    config = OccupancyRealV3Config(
        csv_path=args.csv,
        window_size=args.window_size,
        selector_seed=args.selector_seed,
        feedback_amount=args.feedback_amount,
        eval_feedback_fraction=args.eval_feedback_fraction,
        train_session_fraction=args.train_session_fraction,
        packet_ttl=args.packet_ttl,
        max_train_sessions=args.max_train_sessions,
        max_eval_sessions=args.max_eval_sessions,
        summary_only=args.summary_only,
    )

    manifest = _build_manifest(args)
    print("REAL Occupancy v3 — session-structured carryover experiment")
    _print_manifest(manifest)

    t0 = time.monotonic()
    result = run_occupancy_real_v3_experiment(config, workers=args.workers)
    elapsed = time.monotonic() - t0

    manifest = _build_manifest(args, elapsed=elapsed)
    result["manifest"] = manifest

    _print_section("Session inventory")
    _print_inventory("Training sessions", result["train_inventory"])
    _print_inventory("Eval sessions", result["eval_inventory"])
    print(f"\n  CO2 training median:   {result['co2_training_median']:.6f}")
    print(f"  Light training median: {result['light_training_median']:.6f}")
    print(f"  Training context codes seen: {result['training_context_codes']}")

    _print_section("Phase 2 — Training run summary")
    _print_summary("Training (sequential)", result["train_summary"])

    _print_section("Phase 3 — Carryover efficiency")
    _print_summary("Warm eval (with carryover)", result["warm_eval_summary"])
    _print_summary("Cold eval (no carryover)", result["cold_eval_summary"])
    _print_efficiency(result["carryover_efficiency"])

    _print_section("Phase 4 — Context transfer probe")
    _print_transfer(result["context_transfer_probe"])

    print(f"\nFinal manifest:")
    _print_manifest(manifest)

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, default=str)
        print(f"Result written to: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
