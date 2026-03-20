"""
run_occupancy_real_v3.py
------------------------
CLI entrypoint for the REAL-native occupancy harness.
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
    from scripts.occupancy_real_v3 import (
        AUTO_CPU_TARGET_FRACTION,
        CONTEXT_LATENT,
        CONTEXT_OFFLINE,
        CONTEXT_ONLINE,
        EVAL_BOTH,
        EVAL_FRESH,
        EVAL_PERSISTENT,
        INGRESS_ADMISSION,
        INGRESS_DIRECT,
        TOPOLOGY_FIXED,
        TOPOLOGY_MULTIHOP,
    )

    parser = argparse.ArgumentParser(
        prog="run_occupancy_real_v3",
        description="V3 REAL occupancy experiment: REAL-native carryover harness",
    )
    parser.add_argument("--csv", default="occupancy_baseline/data/occupancy_synth_v1.csv")
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--selector-seed", type=int, default=13)
    parser.add_argument(
        "--selector-seeds",
        nargs="*",
        type=int,
        default=None,
        help="Optional multi-seed sweep. When provided, this takes precedence over --selector-seed.",
    )
    parser.add_argument("--feedback-amount", type=float, default=0.18)
    parser.add_argument("--eval-feedback-fraction", type=float, default=1.0)
    parser.add_argument("--train-session-fraction", type=float, default=0.70)
    parser.add_argument(
        "--eval-mode",
        choices=[EVAL_PERSISTENT, EVAL_FRESH, EVAL_BOTH],
        default=EVAL_FRESH,
    )
    parser.add_argument(
        "--topology-mode",
        choices=[TOPOLOGY_FIXED, TOPOLOGY_MULTIHOP],
        default=TOPOLOGY_MULTIHOP,
    )
    parser.add_argument(
        "--context-mode",
        choices=[CONTEXT_OFFLINE, CONTEXT_ONLINE, CONTEXT_LATENT],
        default=CONTEXT_ONLINE,
    )
    parser.add_argument(
        "--ingress-mode",
        choices=[INGRESS_ADMISSION, INGRESS_DIRECT],
        default=INGRESS_ADMISSION,
    )
    parser.add_argument("--packet-ttl", type=int, default=8)
    parser.add_argument("--output-json", default=None)
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help=(
            f"Eval workers. Omit to auto-use about {int(AUTO_CPU_TARGET_FRACTION * 100)}% "
            "of visible CPU capacity."
        ),
    )
    parser.add_argument("--max-train-sessions", type=int, default=None)
    parser.add_argument("--max-eval-sessions", type=int, default=None)
    parser.add_argument("--summary-only", action="store_true")
    return parser


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


def _selected_seeds(args: argparse.Namespace) -> list[int]:
    if args.selector_seeds:
        return list(dict.fromkeys(int(seed) for seed in args.selector_seeds))
    return [int(args.selector_seed)]


def _build_manifest(
    args: argparse.Namespace,
    *,
    selector_seeds: list[int],
    elapsed: float | None = None,
) -> dict[str, object]:
    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    timestamp = run_at.replace(":", "").replace("-", "")[:15]
    seed_fragment = (
        f"seed{selector_seeds[0]}"
        if len(selector_seeds) == 1
        else f"sweep{len(selector_seeds)}seeds"
    )
    return {
        "run_id": f"v3_{seed_fragment}_{timestamp}",
        "run_at": run_at,
        "git_sha": _git_sha(),
        "csv": args.csv,
        "selector_seeds": list(selector_seeds),
        "window_size": args.window_size,
        "train_session_fraction": args.train_session_fraction,
        "eval_mode": args.eval_mode,
        "topology_mode": args.topology_mode,
        "context_mode": args.context_mode,
        "ingress_mode": args.ingress_mode,
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


def _print_manifest(manifest: dict[str, object]) -> None:
    separator = "-" * 60
    print(f"\n{separator}")
    print(f"  run_id:   {manifest['run_id']}")
    print(f"  run_at:   {manifest['run_at']}")
    if manifest["git_sha"]:
        print(f"  git_sha:  {manifest['git_sha']}")
    print(f"  csv:      {manifest['csv']}")
    selector_seeds = list(manifest["selector_seeds"])
    if len(selector_seeds) == 1:
        print(
            f"  seed:     {selector_seeds[0]}  "
            f"window: {manifest['window_size']}  "
            f"train_frac: {manifest['train_session_fraction']}"
        )
    else:
        print(
            f"  seeds:    {selector_seeds}  "
            f"window: {manifest['window_size']}  "
            f"train_frac: {manifest['train_session_fraction']}"
        )
    print(
        f"  modes:    eval={manifest['eval_mode']}  "
        f"topology={manifest['topology_mode']}  "
        f"context={manifest['context_mode']}  "
        f"ingress={manifest['ingress_mode']}"
    )
    if manifest["max_train_sessions"] is not None or manifest["max_eval_sessions"] is not None:
        print(
            f"  caps:     train<={manifest['max_train_sessions']}  "
            f"eval<={manifest['max_eval_sessions']}"
        )
    worker_label = manifest["workers"] if manifest["workers"] is not None else "auto"
    print(f"  workers:  {worker_label}")
    if manifest["elapsed_seconds"] is not None:
        print(f"  elapsed:  {float(manifest['elapsed_seconds']):.1f}s")
    print(separator)


def _print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _print_inventory(label: str, inventory: dict[str, object]) -> None:
    print(f"\n{label}")
    print(f"  sessions:       {inventory['session_count']}")
    print(f"  by label:       {inventory['by_label']}")
    print(f"  by context:     {inventory['by_context_code']}")
    lengths = inventory["episode_lengths"]
    print(f"  episode length: min={lengths['min']}  mean={lengths['mean']}  max={lengths['max']}")
    print(f"  ctx by label:   {inventory['context_codes_by_label']}")


def _print_summary(label: str, summary: dict[str, object]) -> None:
    metrics = summary.get("metrics", {})
    print(f"\n{label}")
    print(f"  episodes:     {summary['episode_count']}")
    print(f"  accuracy:     {metrics.get('accuracy', 0.0):.4f}")
    print(f"  F1:           {metrics.get('f1', 0.0):.4f}")
    print(f"  precision:    {metrics.get('precision', 0.0):.4f}")
    print(f"  recall:       {metrics.get('recall', 0.0):.4f}")
    print(f"  mean deliv:   {summary.get('mean_delivery_ratio', 0.0):.4f}")
    print(f"  mean dropped: {summary['mean_dropped_packets']:.2f}")
    print(f"  mean fdbk ev: {summary['mean_feedback_events']:.2f}")


def _print_efficiency(efficiency: dict[str, object]) -> None:
    print("\nCarryover efficiency")
    print(f"  mean efficiency ratio:       {efficiency['mean_efficiency_ratio']}")
    print(f"  session 1 delivery delta:    {efficiency['session_1_delivery_delta']}")
    print(f"  session 1 efficiency ratio:  {efficiency['session_1_efficiency_ratio']}")
    print(f"  mean first-episode delta:    {efficiency['mean_first_episode_delivery_delta']}")
    print(f"  mean first-3-episode delta:  {efficiency['mean_first_three_episode_delivery_delta']}")
    print(f"  warm sessions to 80% deliv:  {efficiency['warm_sessions_to_80pct']}")
    print(f"  cold sessions to 80% deliv:  {efficiency['cold_sessions_to_80pct']}")


def _print_transfer(probe: dict[str, object]) -> None:
    print("\nContext transfer probe")
    print(f"  status: {probe['status']}")
    print(f"  training context codes: {probe['training_context_codes']}")
    print(f"  eval context codes: {probe.get('eval_context_codes')}")
    print(f"  seen   contexts (warm): {probe['warm_seen_mean_delivery']}  ({probe['warm_seen_session_count']} sessions)")
    print(f"  unseen contexts (warm): {probe['warm_unseen_mean_delivery']}  ({probe['warm_unseen_session_count']} sessions)")
    print(f"  seen   contexts (cold): {probe['cold_seen_mean_delivery']}")
    print(f"  unseen contexts (cold): {probe['cold_unseen_mean_delivery']}")


def _print_protocol(label: str, payload: dict[str, object]) -> None:
    print(f"\n{label}")
    _print_summary("Warm eval (with carryover)", payload["warm_summary"])
    _print_summary("Cold eval (no carryover)", payload["cold_summary"])
    print(f"\n  warm reset count: {payload['warm_reset_count']}")
    print(f"  cold reset count: {payload['cold_reset_count']}")
    print(f"  workers used:     {payload['workers_used']}")
    print(f"  parallel status:  {payload['parallelism_status']}")
    print(f"  warm admitted:    {payload['warm_system_summary'].get('admitted_packets')}")
    print(f"  cold admitted:    {payload['cold_system_summary'].get('admitted_packets')}")
    _print_efficiency(payload["efficiency"])
    _print_transfer(payload["context_transfer_probe"])


def _print_sweep_summary(result: dict[str, object]) -> None:
    aggregate = result["aggregate"]
    worker_policy = result["worker_policy"]
    _print_section("Sweep aggregate")
    print(f"\n  seeds:                {result['v3_sweep_config']['selector_seeds']}")
    print(f"  primary eval mode:    {aggregate['primary_eval_mode']}")
    print(f"  worker budget:        {worker_policy['worker_budget']}")
    print(f"  seed workers:         {worker_policy['seed_workers']}")
    print(f"  eval workers/seed:    {worker_policy['eval_workers_per_seed']}")
    print(f"  total planned workers:{worker_policy['effective_total_workers']}")
    print(f"  parallel status:      {worker_policy['parallelism_status']}")
    print(f"  mean train accuracy:  {aggregate['mean_train_accuracy']}")
    print(f"  mean warm accuracy:   {aggregate['mean_warm_accuracy']}")
    print(f"  mean cold accuracy:   {aggregate['mean_cold_accuracy']}")
    print(f"  mean warm delivery:   {aggregate['mean_warm_delivery_ratio']}")
    print(f"  mean cold delivery:   {aggregate['mean_cold_delivery_ratio']}")
    print(f"  mean efficiency:      {aggregate['mean_efficiency_ratio']}")
    print(f"  mean s1 delta:        {aggregate['mean_session_1_delivery_delta']}")
    print(f"  mean ep1 delta:       {aggregate['mean_first_episode_delivery_delta']}")
    print(f"  mean ep3 delta:       {aggregate['mean_first_three_episode_delivery_delta']}")
    print(f"  best efficiency seed: {aggregate['best_seed_by_efficiency_ratio']}")

    _print_section("Per-seed summary")
    for summary in result["seed_summaries"]:
        print(f"\nSeed {summary['selector_seed']}")
        print(f"  train accuracy:   {summary['train_accuracy']}")
        print(f"  warm accuracy:    {summary['warm_accuracy']}")
        print(f"  cold accuracy:    {summary['cold_accuracy']}")
        print(f"  warm delivery:    {summary['warm_mean_delivery_ratio']}")
        print(f"  cold delivery:    {summary['cold_mean_delivery_ratio']}")
        print(f"  efficiency ratio: {summary['mean_efficiency_ratio']}")
        print(f"  session 1 delta:  {summary['session_1_delivery_delta']}")
        print(f"  eval workers:     {summary['eval_workers_by_protocol']}")
        print(f"  protocol status:  {summary['protocol_parallelism']}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    from scripts.occupancy_real_v3 import (
        OccupancyRealV3Config,
        run_occupancy_real_v3_experiment,
        run_occupancy_real_v3_sweep,
    )

    selector_seeds = _selected_seeds(args)
    config = OccupancyRealV3Config(
        csv_path=args.csv,
        window_size=args.window_size,
        selector_seed=selector_seeds[0],
        feedback_amount=args.feedback_amount,
        eval_feedback_fraction=args.eval_feedback_fraction,
        train_session_fraction=args.train_session_fraction,
        eval_mode=args.eval_mode,
        topology_mode=args.topology_mode,
        context_mode=args.context_mode,
        ingress_mode=args.ingress_mode,
        packet_ttl=args.packet_ttl,
        max_train_sessions=args.max_train_sessions,
        max_eval_sessions=args.max_eval_sessions,
        summary_only=args.summary_only,
    )

    manifest = _build_manifest(args, selector_seeds=selector_seeds)
    print("REAL Occupancy v3 - REAL-native carryover harness")
    _print_manifest(manifest)

    start = time.monotonic()
    if len(selector_seeds) == 1:
        result = run_occupancy_real_v3_experiment(config, workers=args.workers)
    else:
        result = run_occupancy_real_v3_sweep(
            config,
            selector_seeds=selector_seeds,
            workers=args.workers,
        )
    elapsed = time.monotonic() - start

    manifest = _build_manifest(args, selector_seeds=selector_seeds, elapsed=elapsed)
    result["manifest"] = manifest

    if len(selector_seeds) == 1:
        _print_section("Session inventory")
        _print_inventory("Training sessions", result["train_inventory"])
        _print_inventory("Eval sessions", result["eval_inventory"])
        print(f"\n  CO2 training median:   {result['co2_training_median']:.6f}")
        print(f"  Light training median: {result['light_training_median']:.6f}")
        print(f"  Training context codes seen: {result['training_context_codes']}")
        print(f"  Eval workers by protocol: {result['worker_policy']['eval_workers_by_protocol']}")

        _print_section("Phase 2 - Training run summary")
        _print_summary("Training (sequential)", result["train_summary"])

        _print_section("Phase 3 - Primary eval")
        print(f"\nPrimary eval mode: {result['primary_eval_mode']}")
        _print_protocol("Primary protocol", result["primary_eval"])

        secondary_protocols = {
            name: payload
            for name, payload in result["eval_protocols"].items()
            if name != result["primary_eval_mode"]
        }
        if secondary_protocols:
            _print_section("Secondary eval protocols")
            for name, payload in secondary_protocols.items():
                _print_protocol(name, payload)
    else:
        _print_sweep_summary(result)

    print("\nFinal manifest:")
    _print_manifest(manifest)

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, default=str)
        print(f"Result written to: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
