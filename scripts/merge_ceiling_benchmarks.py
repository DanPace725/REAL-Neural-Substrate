from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Sequence

from scripts.compare_ceiling_benchmarks import _aggregate_point_methods
from scripts.ceiling_benchmark_metrics import aggregate_run_metrics, frontier_summary
from scripts.ceiling_benchmark_suite import benchmark_suite_by_id
from scripts.experiment_manifest import build_run_manifest, write_run_manifest


def _load_manifest(path: Path) -> Dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return dict(payload.get("result", payload))


def merge_ceiling_results(results: Sequence[Dict[str, object]]) -> Dict[str, object]:
    suite_map = benchmark_suite_by_id()
    merged_suite: Dict[str, Dict[str, object]] = {}
    methods: set[str] = set()
    seeds: set[int] = set()
    pilot_seeds: set[int] = set()
    cold_runs: List[Dict[str, object]] = []
    transfer_runs: List[Dict[str, object]] = []

    for result in results:
        for item in result.get("suite", []):
            merged_suite[item["benchmark_id"]] = item
        methods.update(result.get("methods", []))
        seeds.update(int(seed) for seed in result.get("seeds", []))
        pilot_seeds.update(int(seed) for seed in result.get("pilot_seeds", []))
        cold_runs.extend(result["cold_start"]["runs"])
        if result.get("transfer_slice"):
            transfer_runs.extend(result["transfer_slice"]["runs"])

    ordered_suite_ids = sorted(merged_suite, key=lambda benchmark_id: (suite_map[benchmark_id].family_order, suite_map[benchmark_id].difficulty_index))
    cold_aggregates: List[Dict[str, object]] = []
    point_summaries: List[Dict[str, object]] = []
    transfer_ids = sorted({run["benchmark_id"] for run in transfer_runs})

    for benchmark_id in ordered_suite_ids:
        point = suite_map[benchmark_id]
        aggregates, point_summary = _aggregate_point_methods(point, cold_runs)
        cold_aggregates.extend(aggregates)
        point_summaries.append(point_summary)
    for aggregate in cold_aggregates:
        aggregate["in_transfer_slice"] = aggregate["benchmark_id"] in transfer_ids

    frontier = frontier_summary(point_summaries)

    transfer_aggregates: List[Dict[str, object]] = []
    if transfer_runs:
        grouped = sorted({(run["benchmark_id"], run["method_id"], run["transfer_task_key"]) for run in transfer_runs})
        for benchmark_id, method_id, transfer_task_key in grouped:
            point = suite_map[benchmark_id]
            matching_runs = [
                run
                for run in transfer_runs
                if run["benchmark_id"] == benchmark_id
                and run["method_id"] == method_id
                and run["transfer_task_key"] == transfer_task_key
            ]
            aggregate = aggregate_run_metrics(matching_runs)
            aggregate.update(
                {
                    "benchmark_id": benchmark_id,
                    "family_id": point.family_id,
                    "family_order": point.family_order,
                    "difficulty_index": point.difficulty_index,
                    "method_id": method_id,
                    "transfer_task_key": transfer_task_key,
                    "in_transfer_slice": True,
                }
            )
            transfer_aggregates.append(aggregate)

    return {
        "suite": [merged_suite[benchmark_id] for benchmark_id in ordered_suite_ids],
        "methods": sorted(methods),
        "seeds": sorted(seeds),
        "pilot_seeds": sorted(pilot_seeds),
        "cold_start": {
            "runs": cold_runs,
            "aggregates": cold_aggregates,
            "points": point_summaries,
            "frontier": frontier,
            "transfer_point_ids": transfer_ids,
        },
        "transfer_slice": {
            "runs": transfer_runs,
            "aggregates": transfer_aggregates,
        }
        if transfer_runs
        else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge chunked ceiling benchmark manifests into one combined result")
    parser.add_argument("manifests", nargs="+", help="input manifest JSON files")
    parser.add_argument("--output", required=True, help="path to save the merged manifest")
    args = parser.parse_args()

    results = [_load_manifest(Path(path)) for path in args.manifests]
    merged = merge_ceiling_results(results)
    manifest = build_run_manifest(
        harness="ceiling_benchmark_merge",
        seeds=merged["seeds"],
        scenarios=[item["benchmark_id"] for item in merged["suite"]],
        result=merged,
        metadata={"source_manifest_count": len(results)},
    )
    write_run_manifest(args.output, manifest)
    frontier_path = Path(args.output).with_name(f"{Path(args.output).stem}_frontier.json")
    frontier_path.write_text(json.dumps(merged["cold_start"]["frontier"], indent=2), encoding="utf-8")
    print(f"Saved merged manifest to {args.output}")
    print(f"Saved merged frontier to {frontier_path}")


if __name__ == "__main__":
    main()
