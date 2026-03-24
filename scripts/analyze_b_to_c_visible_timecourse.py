from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path
from statistics import mean
from typing import Sequence

from phase8.environment import _expected_transform_for_task
from scripts.analyze_transfer_timecourse import (
    _aggregate_selector_window,
    _downstream_tracker_snapshot,
    _selector_cycle_summary,
    _source_cycle_snapshot,
    _task_id_hint,
)
from scripts.compare_cold_warm import ROOT, SCENARIOS, build_system, run_workload
from scripts.diagnose_b_to_c_carryover_bridge import (
    DEFAULT_SEEDS,
    DEFAULT_TRAIN_SCENARIO,
    DEFAULT_TRANSFER_SCENARIO,
    MODE_FULL,
    MODE_FULL_CONTEXT_ACTIONS_SCRUBBED,
    MODE_FULL_CONTEXT_SCRUBBED,
    MODE_NONE,
    _bridge_mode_specs,
    _compact_breakdown,
    _load_mode,
)
from scripts.experiment_manifest import build_run_manifest, write_run_manifest


DEFAULT_MODES = (
    MODE_NONE,
    MODE_FULL,
    MODE_FULL_CONTEXT_ACTIONS_SCRUBBED,
    MODE_FULL_CONTEXT_SCRUBBED,
)
TRANSFORM_NAMES = ("identity", "rotate_left_1", "xor_mask_1010", "xor_mask_0101")
VISIBLE_DIAGNOSTIC_FIELDS = (
    "wrong_transform_family",
    "route_wrong_transform_potentially_right",
    "route_right_transform_wrong",
    "delayed_correction",
    "stale_context_support_suspicions",
)


def _mean_or_none(values: list[float | int | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    if not present:
        return None
    return round(mean(present), 5)


def _context_stat(summary: dict[str, object], context_key: str, field: str) -> float:
    return float(
        summary.get("task_diagnostics", {})
        .get("contexts", {})
        .get(context_key, {})
        .get(field, 0.0)
    )


def _overall_stat(summary: dict[str, object], field: str) -> float:
    return float(summary.get("task_diagnostics", {}).get("overall", {}).get(field, 0.0))


def _route_neighbor(action: str) -> str | None:
    if action.startswith("route_transform:"):
        parts = action.split(":")
        if len(parts) == 3:
            return parts[1]
        return None
    if action.startswith("route:"):
        return action.split(":", 1)[1]
    return None


def _route_transform(action: str) -> str:
    if action.startswith("route_transform:"):
        parts = action.split(":")
        if len(parts) == 3:
            return parts[2]
    if action.startswith("route:"):
        return "identity"
    return ""


def _state_before_snapshot(agent, state_before: dict[str, object]) -> dict[str, object]:
    return {
        "effective_context_bit": state_before.get("effective_context_bit"),
        "effective_context_confidence": state_before.get("effective_context_confidence"),
        "context_promotion_ready": state_before.get("context_promotion_ready"),
        "transfer_adaptation_phase": state_before.get("transfer_adaptation_phase"),
        "latent_context_available": state_before.get("latent_context_available"),
        "latent_context_confidence": state_before.get("latent_context_confidence"),
        "context_action_supports": {
            neighbor_id: {
                transform_name: round(
                    float(
                        state_before.get(
                            f"context_action_support_{neighbor_id}_{transform_name}",
                            0.0,
                        )
                    ),
                    4,
                )
                for transform_name in ("rotate_left_1", "xor_mask_1010", "xor_mask_0101")
            }
            for neighbor_id in agent.neighbor_ids
        },
        "transform_fields": {
            transform_name: {
                "task_transform_affinity": round(
                    float(state_before.get(f"task_transform_affinity_{transform_name}", 0.0)),
                    4,
                ),
                "history_transform_evidence": round(
                    float(state_before.get(f"history_transform_evidence_{transform_name}", 0.0)),
                    4,
                ),
                "source_sequence_transform_hint": round(
                    float(state_before.get(f"source_sequence_transform_hint_{transform_name}", 0.0)),
                    4,
                ),
                "feedback_credit": round(
                    float(state_before.get(f"feedback_credit_{transform_name}", 0.0)),
                    4,
                ),
                "feedback_debt": round(
                    float(state_before.get(f"feedback_debt_{transform_name}", 0.0)),
                    4,
                ),
                "context_feedback_credit": round(
                    float(state_before.get(f"context_feedback_credit_{transform_name}", 0.0)),
                    4,
                ),
                "context_feedback_debt": round(
                    float(state_before.get(f"context_feedback_debt_{transform_name}", 0.0)),
                    4,
                ),
            }
            for transform_name in ("rotate_left_1", "xor_mask_1010", "xor_mask_0101")
        },
    }


def _selector_choice_snapshot(system, report: dict[str, object], *, node_id: str) -> dict[str, object]:
    agent = system.agents[node_id]
    source_entry = report["entries"][node_id]
    action = str(source_entry.action)
    breakdowns = agent.engine.selector.latest_route_score_breakdowns() or {}
    top_competitor = None
    for candidate_action, details in sorted(
        breakdowns.items(),
        key=lambda item: float(item[1].get("total", 0.0)),
        reverse=True,
    ):
        if candidate_action != action:
            top_competitor = details
            break

    state_before = dict(source_entry.state_before)
    chosen_breakdown = _compact_breakdown(breakdowns.get(action))
    top_competitor_breakdown = _compact_breakdown(top_competitor)
    return {
        "node_id": node_id,
        "chosen_action": action,
        "chosen_neighbor": _route_neighbor(action),
        "chosen_transform": _route_transform(action),
        "chosen_breakdown": chosen_breakdown,
        "top_competitor_breakdown": top_competitor_breakdown,
        "state_before": _state_before_snapshot(agent, state_before),
    }


def _node_snapshot(agent) -> dict[str, object]:
    runtime = agent.environment.state_for(agent.node_id)
    pattern_sources: dict[str, int] = {}
    for pattern in agent.substrate.constraint_patterns:
        source = str(getattr(pattern, "source", "unknown"))
        pattern_sources[source] = pattern_sources.get(source, 0) + 1

    return {
        "atp": round(float(runtime.atp), 5),
        "atp_ratio": round(runtime.atp / max(runtime.max_atp, 1e-9), 5),
        "reward_buffer": round(float(runtime.reward_buffer), 5),
        "last_feedback_amount": round(float(runtime.last_feedback_amount), 5),
        "last_match_ratio": round(float(runtime.last_match_ratio), 5),
        "pattern_sources": dict(sorted(pattern_sources.items())),
        "active_neighbors": list(agent.substrate.active_neighbors()),
        "edge_supports": {
            neighbor_id: round(agent.substrate.support(neighbor_id), 4)
            for neighbor_id in agent.neighbor_ids
        },
        "action_supports": {
            neighbor_id: {
                transform_name: round(
                    agent.substrate.action_support(neighbor_id, transform_name),
                    4,
                )
                for transform_name in TRANSFORM_NAMES
            }
            for neighbor_id in agent.neighbor_ids
        },
        "context_action_supports": {
            neighbor_id: {
                f"context_{context_bit}": {
                    transform_name: round(
                        agent.substrate.action_support(
                            neighbor_id,
                            transform_name,
                            context_bit,
                        ),
                        4,
                    )
                    for transform_name in TRANSFORM_NAMES
                }
                for context_bit in agent.substrate.supported_contexts
            }
            for neighbor_id in agent.neighbor_ids
        },
    }


def _focused_node_snapshots(system) -> dict[str, object]:
    source_id = system.environment.source_id
    focus_nodes = [source_id, *system.agents[source_id].neighbor_ids]
    return {
        node_id: _node_snapshot(system.agents[node_id])
        for node_id in focus_nodes
        if node_id in system.agents
    }


def _focused_selector_snapshots(system, report: dict[str, object]) -> dict[str, object]:
    source_id = system.environment.source_id
    focus_nodes = [source_id, *system.agents[source_id].neighbor_ids]
    return {
        node_id: _selector_choice_snapshot(system, report, node_id=node_id)
        for node_id in focus_nodes
        if node_id in report["entries"]
    }


def _first_cycle_at_threshold(
    records: list[dict[str, object]],
    field: str,
    *,
    threshold: float,
) -> int | None:
    for record in records:
        if float(record.get(field, 0.0)) >= threshold:
            return int(record["cycle"])
    return None


def _peak_cycle(records: list[dict[str, object]], field: str) -> tuple[float, int | None]:
    if not records:
        return 0.0, None
    peak = max(float(record.get(field, 0.0)) for record in records)
    cycle = next(
        (int(record["cycle"]) for record in records if float(record.get(field, 0.0)) == peak),
        None,
    )
    return round(peak, 5), cycle


def _visible_timecourse_summary(records: list[dict[str, object]]) -> dict[str, object]:
    final = records[-1] if records else {}
    selector_records = [dict(record.get("selector_cycle", {})) for record in records]
    summary: dict[str, object] = {
        "final_exact_matches": int(final.get("exact_matches", 0)),
        "final_mean_bit_accuracy": round(float(final.get("mean_bit_accuracy", 0.0)), 5),
        "final_context_0_mean_bit_accuracy": round(
            float(final.get("context_0_mean_bit_accuracy", 0.0)),
            5,
        ),
        "final_context_1_mean_bit_accuracy": round(
            float(final.get("context_1_mean_bit_accuracy", 0.0)),
            5,
        ),
        "first_context_1_perfect_cycle": _first_cycle_at_threshold(
            records,
            "context_1_mean_bit_accuracy",
            threshold=1.0,
        ),
        "first_exact_match_cycle": _first_cycle_at_threshold(
            records,
            "exact_matches",
            threshold=1.0,
        ),
        "early_selector_window": _aggregate_selector_window(selector_records[:3]),
        "full_selector_window": _aggregate_selector_window(selector_records),
    }
    for field in VISIBLE_DIAGNOSTIC_FIELDS:
        peak, cycle = _peak_cycle(records, field)
        summary[f"peak_{field}"] = peak
        summary[f"peak_{field}_cycle"] = cycle
        summary[f"final_{field}"] = round(float(final.get(field, 0.0)), 5)
    return summary


def _run_mode_timecourse(
    *,
    seed: int,
    transfer_scenario: str,
    mode_name: str,
    mode_spec,
) -> dict[str, object]:
    system = build_system(seed, transfer_scenario)
    _load_mode(system, mode_spec)

    source_id = system.environment.source_id
    for node_id in [source_id, *system.agents[source_id].neighbor_ids]:
        if node_id in system.agents:
            system.agents[node_id].engine.selector.capture_route_breakdowns = True
    scenario = SCENARIOS[transfer_scenario]
    task_id_hint = _task_id_hint(scenario.initial_signal_specs, scenario.signal_schedule_specs)
    if scenario.initial_signal_specs:
        system.inject_signal_specs(scenario.initial_signal_specs)
    elif scenario.initial_packets > 0:
        system.inject_signal(count=scenario.initial_packets)

    records: list[dict[str, object]] = []
    prior_overall = {field: 0.0 for field in VISIBLE_DIAGNOSTIC_FIELDS}
    for cycle in range(1, scenario.cycles + 1):
        scheduled_specs = (scenario.signal_schedule_specs or {}).get(cycle)
        if scheduled_specs:
            system.inject_signal_specs(scheduled_specs)
        else:
            scheduled = scenario.packet_schedule.get(cycle, 0)
            if scheduled > 0:
                system.inject_signal(count=scheduled)

        report = system.run_global_cycle()
        summary = system.summarize()
        overall = dict(summary.get("task_diagnostics", {}).get("overall", {}))
        selector_summary = _selector_cycle_summary(report["entries"])
        source_snapshot = _source_cycle_snapshot(system, task_id_hint=task_id_hint)
        downstream_snapshot = _downstream_tracker_snapshot(system, task_id_hint=task_id_hint)
        selector_choice = _selector_choice_snapshot(system, report, node_id=source_id)

        record: dict[str, object] = {
            "cycle": cycle,
            "exact_matches": int(summary["exact_matches"]),
            "mean_bit_accuracy": round(float(summary["mean_bit_accuracy"]), 5),
            "context_0_mean_bit_accuracy": round(
                _context_stat(summary, "context_0", "mean_bit_accuracy"),
                5,
            ),
            "context_1_mean_bit_accuracy": round(
                _context_stat(summary, "context_1", "mean_bit_accuracy"),
                5,
            ),
            "context_0_exact_matches": int(
                _context_stat(summary, "context_0", "exact_matches")
            ),
            "context_1_exact_matches": int(
                _context_stat(summary, "context_1", "exact_matches")
            ),
            "overall_branch_counts": dict(overall.get("branch_counts", {})),
            "overall_mismatch_branch_counts": dict(overall.get("mismatch_branch_counts", {})),
            "overall_final_transform_counts": dict(overall.get("final_transform_counts", {})),
            "overall_mismatch_transform_counts": dict(overall.get("mismatch_transform_counts", {})),
            "context_1_branch_counts": dict(
                summary.get("task_diagnostics", {})
                .get("contexts", {})
                .get("context_1", {})
                .get("branch_counts", {})
            ),
            "context_1_mismatch_branch_counts": dict(
                summary.get("task_diagnostics", {})
                .get("contexts", {})
                .get("context_1", {})
                .get("mismatch_branch_counts", {})
            ),
            "context_1_final_transform_counts": dict(
                summary.get("task_diagnostics", {})
                .get("contexts", {})
                .get("context_1", {})
                .get("final_transform_counts", {})
            ),
            "context_1_mismatch_transform_counts": dict(
                summary.get("task_diagnostics", {})
                .get("contexts", {})
                .get("context_1", {})
                .get("mismatch_transform_counts", {})
            ),
            "expected_context_1_transform": _expected_transform_for_task("task_c", 1),
            **source_snapshot,
            **downstream_snapshot,
            "selector_cycle": {
                "route_count": selector_summary["route_count"],
                "rest_count": selector_summary["rest_count"],
                "invest_count": selector_summary["invest_count"],
                "route_branch_counts": selector_summary["route_branch_counts"],
                "route_transform_counts": selector_summary["route_transform_counts"],
                "route_mode_counts": selector_summary["route_mode_counts"],
                "branch_transform_counts": selector_summary["branch_transform_counts"],
                "mean_route_coherence": selector_summary["mean_route_coherence"],
                "mean_route_delta": selector_summary["mean_route_delta"],
            },
            "source_selector": selector_choice,
            "focused_selector_snapshots": _focused_selector_snapshots(system, report),
            "focused_node_snapshots": _focused_node_snapshots(system),
        }
        for field in VISIBLE_DIAGNOSTIC_FIELDS:
            current_value = round(_overall_stat(summary, field), 5)
            record[field] = current_value
            record[f"delta_{field}"] = round(max(0.0, current_value - prior_overall[field]), 5)
            prior_overall[field] = current_value
        records.append(record)

    return {
        "carryover_mode": mode_name,
        "timeline": records,
        "summary": _visible_timecourse_summary(records),
    }


def _aggregate_mode(records: list[dict[str, object]], mode_name: str) -> dict[str, object]:
    cycle_count = len(records[0]["carryover_modes"][mode_name]["timeline"]) if records else 0
    per_cycle: list[dict[str, object]] = []
    for index in range(cycle_count):
        cycle_records = [record["carryover_modes"][mode_name]["timeline"][index] for record in records]
        aggregate_record: dict[str, object] = {
            "cycle": int(cycle_records[0]["cycle"]),
            "mean_exact_matches": round(mean(item["exact_matches"] for item in cycle_records), 5),
            "mean_bit_accuracy": round(mean(item["mean_bit_accuracy"] for item in cycle_records), 5),
            "mean_context_0_bit_accuracy": round(
                mean(item["context_0_mean_bit_accuracy"] for item in cycle_records),
                5,
            ),
            "mean_context_1_bit_accuracy": round(
                mean(item["context_1_mean_bit_accuracy"] for item in cycle_records),
                5,
            ),
            "mean_source_route_context_confidence": round(
                mean(float(item["source_route_context_confidence"]) for item in cycle_records),
                5,
            ),
            "mean_source_feedback_context_confidence": round(
                mean(float(item["source_feedback_context_confidence"]) for item in cycle_records),
                5,
            ),
            "mean_effective_context_confidence": round(
                mean(float(item["effective_context_confidence"]) for item in cycle_records),
                5,
            ),
        }
        for field in VISIBLE_DIAGNOSTIC_FIELDS:
            aggregate_record[f"mean_{field}"] = round(
                mean(float(item[field]) for item in cycle_records),
                5,
            )
            aggregate_record[f"mean_delta_{field}"] = round(
                mean(float(item[f"delta_{field}"]) for item in cycle_records),
                5,
            )
        per_cycle.append(aggregate_record)

    mode_summaries = [record["carryover_modes"][mode_name]["summary"] for record in records]
    return {
        "per_cycle": per_cycle,
        "summary": {
            "avg_final_exact_matches": round(
                mean(int(item["final_exact_matches"]) for item in mode_summaries),
                5,
            ),
            "avg_final_mean_bit_accuracy": round(
                mean(float(item["final_mean_bit_accuracy"]) for item in mode_summaries),
                5,
            ),
            "avg_final_context_1_mean_bit_accuracy": round(
                mean(float(item["final_context_1_mean_bit_accuracy"]) for item in mode_summaries),
                5,
            ),
            "avg_first_context_1_perfect_cycle": _mean_or_none(
                [item["first_context_1_perfect_cycle"] for item in mode_summaries]
            ),
            "avg_first_exact_match_cycle": _mean_or_none(
                [item["first_exact_match_cycle"] for item in mode_summaries]
            ),
            **{
                f"avg_peak_{field}": round(
                    mean(float(item[f"peak_{field}"]) for item in mode_summaries),
                    5,
                )
                for field in VISIBLE_DIAGNOSTIC_FIELDS
            },
        },
    }


def _aggregate_timecourse_results(
    results: list[dict[str, object]],
    mode_order: Sequence[str],
) -> dict[str, object]:
    modes = {
        mode_name: _aggregate_mode(results, mode_name)
        for mode_name in mode_order
    }
    full_summary = modes.get(MODE_FULL, {}).get("summary", {})
    delta_vs_full = {}
    for mode_name, mode_payload in modes.items():
        if mode_name == MODE_FULL:
            continue
        summary = mode_payload["summary"]
        delta_vs_full[mode_name] = {
            "avg_final_exact_matches": round(
                float(summary["avg_final_exact_matches"])
                - float(full_summary.get("avg_final_exact_matches", 0.0)),
                5,
            ),
            "avg_final_mean_bit_accuracy": round(
                float(summary["avg_final_mean_bit_accuracy"])
                - float(full_summary.get("avg_final_mean_bit_accuracy", 0.0)),
                5,
            ),
            "avg_final_context_1_mean_bit_accuracy": round(
                float(summary["avg_final_context_1_mean_bit_accuracy"])
                - float(full_summary.get("avg_final_context_1_mean_bit_accuracy", 0.0)),
                5,
            ),
        }
    return {
        "mode_order": list(mode_order),
        "modes": modes,
        "delta_vs_full": delta_vs_full,
    }


def analyze_b_to_c_visible_timecourse(
    *,
    train_scenario: str = DEFAULT_TRAIN_SCENARIO,
    transfer_scenario: str = DEFAULT_TRANSFER_SCENARIO,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    modes: Sequence[str] = DEFAULT_MODES,
    output_path: Path | None = None,
) -> dict[str, object]:
    if not modes:
        raise ValueError("At least one carryover mode is required")

    results: list[dict[str, object]] = []
    for seed in seeds:
        training = build_system(seed, train_scenario)
        training_summary = run_workload(training, train_scenario)
        base_dir = ROOT / "tests_tmp" / f"btc_visible_timecourse_{uuid.uuid4().hex}"
        full_dir = base_dir / "full"
        substrate_dir = base_dir / "substrate"
        bridge_root = base_dir / "bridges"
        full_dir.mkdir(parents=True, exist_ok=True)
        substrate_dir.mkdir(parents=True, exist_ok=True)
        bridge_root.mkdir(parents=True, exist_ok=True)
        try:
            training.save_memory_carryover(full_dir)
            training.save_substrate_carryover(substrate_dir)
            mode_specs = _bridge_mode_specs(
                full_dir=full_dir,
                substrate_dir=substrate_dir,
                bridge_root=bridge_root,
            )
            carryover_modes: dict[str, object] = {}
            for mode_name in modes:
                if mode_name not in mode_specs:
                    raise ValueError(f"Unsupported carryover mode: {mode_name}")
                mode_spec = mode_specs[mode_name]
                carryover_modes[mode_name] = {
                    "bridge_summary": dict(mode_spec.bridge_summary),
                    **_run_mode_timecourse(
                        seed=seed,
                        transfer_scenario=transfer_scenario,
                        mode_name=mode_name,
                        mode_spec=mode_spec,
                    ),
                }
        finally:
            shutil.rmtree(base_dir, ignore_errors=True)

        results.append(
            {
                "seed": seed,
                "train_scenario": train_scenario,
                "transfer_scenario": transfer_scenario,
                "training_summary": training_summary,
                "carryover_modes": carryover_modes,
            }
        )

    result = {
        "train_scenario": train_scenario,
        "transfer_scenario": transfer_scenario,
        "seeds": [int(seed) for seed in seeds],
        "mode_order": list(modes),
        "results": results,
        "aggregate": _aggregate_timecourse_results(results, modes),
    }
    if output_path is not None:
        manifest = build_run_manifest(
            harness="analyze_b_to_c_visible_timecourse",
            seeds=seeds,
            scenarios=(train_scenario, transfer_scenario),
            metadata={
                "train_scenario": train_scenario,
                "transfer_scenario": transfer_scenario,
                "mode_order": list(modes),
            },
            result=result,
        )
        write_run_manifest(output_path, manifest)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a cycle-by-cycle visible B->C carryover diagnostic.",
    )
    parser.add_argument("--train-scenario", default=DEFAULT_TRAIN_SCENARIO)
    parser.add_argument("--transfer-scenario", default=DEFAULT_TRANSFER_SCENARIO)
    parser.add_argument("--seeds", nargs="+", type=int, default=list(DEFAULT_SEEDS))
    parser.add_argument("--modes", nargs="+", default=list(DEFAULT_MODES))
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    print(
        json.dumps(
            analyze_b_to_c_visible_timecourse(
                train_scenario=args.train_scenario,
                transfer_scenario=args.transfer_scenario,
                seeds=tuple(args.seeds),
                modes=tuple(args.modes),
                output_path=args.output,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
