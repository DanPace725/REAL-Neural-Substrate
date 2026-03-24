from __future__ import annotations

import argparse
import json
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Sequence

from phase8.environment import _expected_transform_for_task
from scripts.compare_cold_warm import ROOT, SCENARIOS, build_system, run_workload
from scripts.compare_task_transfer import transfer_metrics
from scripts.experiment_manifest import build_run_manifest, write_run_manifest
from scripts.repeated_signal_scenarios import ordered_signal_events

DEFAULT_TRAIN_SCENARIO = "cvt1_task_b_stage1"
DEFAULT_TRANSFER_SCENARIO = "cvt1_task_c_stage1"
DEFAULT_SEEDS = (13, 23, 37)

MODE_NONE = "none"
MODE_SUBSTRATE = "substrate"
MODE_SUBSTRATE_CONTEXT_ACTIONS_SCRUBBED = "substrate_context_actions_scrubbed"
MODE_SUBSTRATE_CONTEXT_PATTERNS_SCRUBBED = "substrate_context_patterns_scrubbed"
MODE_SUBSTRATE_CONTEXT_SCRUBBED = "substrate_context_scrubbed"
MODE_FULL = "full"
MODE_FULL_CONTEXT_ACTIONS_SCRUBBED = "full_context_actions_scrubbed"
MODE_FULL_CONTEXT_PATTERNS_SCRUBBED = "full_context_patterns_scrubbed"
MODE_FULL_CONTEXT_SCRUBBED = "full_context_scrubbed"

BRIDGE_PATTERN_SOURCE = "context_transform_attractor"
CONTEXT_ACTION_KEY_PREFIX = "context_action:"


@dataclass(frozen=True)
class _CarryoverModeSpec:
    load_mode: str | None
    root_dir: Path | None
    bridge_summary: dict[str, object]


@dataclass(frozen=True)
class _ScrubConfig:
    zero_context_action_keys: bool
    clear_context_credit_entries: bool
    remove_context_transform_patterns: bool


def _scenario_signal_for_context(
    scenario_name: str,
    *,
    context_bit: int,
):
    scenario = SCENARIOS[scenario_name]
    for _, signal_spec in ordered_signal_events(scenario):
        if signal_spec.task_id == "task_c" and int(signal_spec.context_bit or 0) == int(
            context_bit
        ):
            return signal_spec
    raise ValueError(
        f"No task_c signal found for context_{context_bit} in {scenario_name}"
    )


def _source_support_summary(agent) -> dict[str, object]:
    summary: dict[str, object] = {
        "episodic_entry_count": len(agent.engine.memory.entries),
        "dim_history_count": len(agent.substrate.dim_history),
        "pattern_count": len(agent.substrate.constraint_patterns),
        "pattern_sources": {},
        "active_neighbors": list(agent.substrate.active_neighbors()),
        "active_action_supports": list(agent.substrate.active_action_supports()),
        "edge_supports": {
            neighbor_id: round(agent.substrate.support(neighbor_id), 4)
            for neighbor_id in agent.neighbor_ids
        },
        "base_action_supports": {},
        "contextual_action_supports": {},
    }
    pattern_sources: dict[str, int] = {}
    for pattern in agent.substrate.constraint_patterns:
        source = str(getattr(pattern, "source", "unknown"))
        pattern_sources[source] = pattern_sources.get(source, 0) + 1
    summary["pattern_sources"] = pattern_sources
    for neighbor_id in agent.neighbor_ids:
        summary["base_action_supports"][neighbor_id] = {
            transform_name: round(
                agent.substrate.base_action_support(neighbor_id, transform_name),
                4,
            )
            for transform_name in ("rotate_left_1", "xor_mask_1010", "xor_mask_0101")
        }
        summary["contextual_action_supports"][neighbor_id] = {
            f"context_{context_bit}": {
                transform_name: round(
                    agent.substrate.contextual_action_support(
                        neighbor_id,
                        transform_name,
                        context_bit,
                    ),
                    4,
                )
                for transform_name in (
                    "rotate_left_1",
                    "xor_mask_1010",
                    "xor_mask_0101",
                )
            }
            for context_bit in getattr(agent.substrate, "supported_contexts", (0, 1))
        }
    return summary


def _compact_breakdown(
    breakdown: dict[str, float | int | str | None] | None,
) -> dict[str, object] | None:
    if breakdown is None:
        return None
    keys = (
        "action",
        "neighbor_id",
        "transform_name",
        "total",
        "task_transform_term",
        "history_transform_term",
        "prediction_delta_term",
        "prediction_coherence_term",
        "recognition_transform_term",
        "feedback_debt_term",
        "context_feedback_debt_term",
        "context_action_support_term",
        "context_action_mismatch_term",
        "raw_history_transform_evidence",
        "raw_context_action_support",
        "effective_context_action_support",
        "transfer_context_support_scale",
        "raw_context_action_mismatch",
    )
    return {key: breakdown.get(key) for key in keys}


def _load_mode(system, mode_spec: _CarryoverModeSpec) -> None:
    if mode_spec.load_mode is None or mode_spec.root_dir is None:
        return
    if mode_spec.load_mode == MODE_FULL:
        system.load_memory_carryover(mode_spec.root_dir)
        return
    if mode_spec.load_mode == MODE_SUBSTRATE:
        system.load_substrate_carryover(mode_spec.root_dir)
        return
    raise ValueError(f"Unsupported mode load path: {mode_spec.load_mode}")


def _scrub_node_payload(
    payload: dict[str, object],
    scrub_config: _ScrubConfig,
) -> dict[str, int]:
    substrate = dict(payload.get("substrate", {}))
    scrub_summary = {
        "zeroed_context_action_keys": 0,
        "cleared_context_credit_entries": 0,
        "removed_context_transform_patterns": 0,
    }

    if scrub_config.zero_context_action_keys:
        for store_name in ("fast", "slow", "slow_age", "slow_velocity"):
            store = dict(substrate.get(store_name, {}))
            for key in list(store):
                if not str(key).startswith(CONTEXT_ACTION_KEY_PREFIX):
                    continue
                scrub_summary["zeroed_context_action_keys"] += 1
                store[key] = 0 if store_name == "slow_age" else 0.0
            substrate[store_name] = store

    metadata = dict(substrate.get("metadata", {}))
    if scrub_config.remove_context_transform_patterns:
        patterns = list(metadata.get("patterns", []))
        kept_patterns = [
            pattern
            for pattern in patterns
            if str(pattern.get("source", "")) != BRIDGE_PATTERN_SOURCE
        ]
        scrub_summary["removed_context_transform_patterns"] = (
            len(patterns) - len(kept_patterns)
        )
        metadata["patterns"] = kept_patterns

    if scrub_config.clear_context_credit_entries:
        credit_accumulator = dict(metadata.get("context_credit_accumulator", {}))
        scrub_summary["cleared_context_credit_entries"] = len(credit_accumulator)
        metadata["context_credit_accumulator"] = {}

    substrate["metadata"] = metadata
    payload["substrate"] = substrate
    return scrub_summary


def _create_context_scrubbed_carryover(
    source_dir: Path,
    target_dir: Path,
    *,
    scrub_config: _ScrubConfig,
) -> dict[str, object]:
    shutil.copytree(source_dir, target_dir)
    node_summaries: dict[str, dict[str, int]] = {}
    total_zeroed = 0
    total_credits = 0
    total_patterns = 0
    for node_path in sorted((target_dir / "nodes").glob("*.json")):
        payload = json.loads(node_path.read_text(encoding="utf-8"))
        node_summary = _scrub_node_payload(payload, scrub_config)
        node_summaries[node_path.stem] = node_summary
        total_zeroed += int(node_summary["zeroed_context_action_keys"])
        total_credits += int(node_summary["cleared_context_credit_entries"])
        total_patterns += int(node_summary["removed_context_transform_patterns"])
        node_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "scrubbed": True,
        "scrub_config": {
            "zero_context_action_keys": scrub_config.zero_context_action_keys,
            "clear_context_credit_entries": scrub_config.clear_context_credit_entries,
            "remove_context_transform_patterns": scrub_config.remove_context_transform_patterns,
        },
        "node_count": len(node_summaries),
        "zeroed_context_action_keys": total_zeroed,
        "cleared_context_credit_entries": total_credits,
        "removed_context_transform_patterns": total_patterns,
        "nodes": node_summaries,
    }


def _bridge_mode_specs(
    *,
    full_dir: Path,
    substrate_dir: Path,
    bridge_root: Path,
) -> dict[str, _CarryoverModeSpec]:
    context_actions_scrub = _ScrubConfig(
        zero_context_action_keys=True,
        clear_context_credit_entries=True,
        remove_context_transform_patterns=False,
    )
    context_patterns_scrub = _ScrubConfig(
        zero_context_action_keys=False,
        clear_context_credit_entries=False,
        remove_context_transform_patterns=True,
    )
    combined_scrub = _ScrubConfig(
        zero_context_action_keys=True,
        clear_context_credit_entries=True,
        remove_context_transform_patterns=True,
    )
    substrate_action_scrubbed_dir = bridge_root / MODE_SUBSTRATE_CONTEXT_ACTIONS_SCRUBBED
    substrate_pattern_scrubbed_dir = bridge_root / MODE_SUBSTRATE_CONTEXT_PATTERNS_SCRUBBED
    substrate_scrubbed_dir = bridge_root / MODE_SUBSTRATE_CONTEXT_SCRUBBED
    full_action_scrubbed_dir = bridge_root / MODE_FULL_CONTEXT_ACTIONS_SCRUBBED
    full_pattern_scrubbed_dir = bridge_root / MODE_FULL_CONTEXT_PATTERNS_SCRUBBED
    full_scrubbed_dir = bridge_root / MODE_FULL_CONTEXT_SCRUBBED
    substrate_action_scrubbed_summary = _create_context_scrubbed_carryover(
        substrate_dir,
        substrate_action_scrubbed_dir,
        scrub_config=context_actions_scrub,
    )
    substrate_pattern_scrubbed_summary = _create_context_scrubbed_carryover(
        substrate_dir,
        substrate_pattern_scrubbed_dir,
        scrub_config=context_patterns_scrub,
    )
    substrate_scrubbed_summary = _create_context_scrubbed_carryover(
        substrate_dir,
        substrate_scrubbed_dir,
        scrub_config=combined_scrub,
    )
    full_action_scrubbed_summary = _create_context_scrubbed_carryover(
        full_dir,
        full_action_scrubbed_dir,
        scrub_config=context_actions_scrub,
    )
    full_pattern_scrubbed_summary = _create_context_scrubbed_carryover(
        full_dir,
        full_pattern_scrubbed_dir,
        scrub_config=context_patterns_scrub,
    )
    full_scrubbed_summary = _create_context_scrubbed_carryover(
        full_dir,
        full_scrubbed_dir,
        scrub_config=combined_scrub,
    )
    return {
        MODE_NONE: _CarryoverModeSpec(
            load_mode=None,
            root_dir=None,
            bridge_summary={"scrubbed": False, "source": "cold_start"},
        ),
        MODE_SUBSTRATE: _CarryoverModeSpec(
            load_mode=MODE_SUBSTRATE,
            root_dir=substrate_dir,
            bridge_summary={"scrubbed": False, "source": "substrate_snapshot"},
        ),
        MODE_SUBSTRATE_CONTEXT_ACTIONS_SCRUBBED: _CarryoverModeSpec(
            load_mode=MODE_SUBSTRATE,
            root_dir=substrate_action_scrubbed_dir,
            bridge_summary=substrate_action_scrubbed_summary,
        ),
        MODE_SUBSTRATE_CONTEXT_PATTERNS_SCRUBBED: _CarryoverModeSpec(
            load_mode=MODE_SUBSTRATE,
            root_dir=substrate_pattern_scrubbed_dir,
            bridge_summary=substrate_pattern_scrubbed_summary,
        ),
        MODE_SUBSTRATE_CONTEXT_SCRUBBED: _CarryoverModeSpec(
            load_mode=MODE_SUBSTRATE,
            root_dir=substrate_scrubbed_dir,
            bridge_summary=substrate_scrubbed_summary,
        ),
        MODE_FULL: _CarryoverModeSpec(
            load_mode=MODE_FULL,
            root_dir=full_dir,
            bridge_summary={"scrubbed": False, "source": "full_memory_snapshot"},
        ),
        MODE_FULL_CONTEXT_ACTIONS_SCRUBBED: _CarryoverModeSpec(
            load_mode=MODE_FULL,
            root_dir=full_action_scrubbed_dir,
            bridge_summary=full_action_scrubbed_summary,
        ),
        MODE_FULL_CONTEXT_PATTERNS_SCRUBBED: _CarryoverModeSpec(
            load_mode=MODE_FULL,
            root_dir=full_pattern_scrubbed_dir,
            bridge_summary=full_pattern_scrubbed_summary,
        ),
        MODE_FULL_CONTEXT_SCRUBBED: _CarryoverModeSpec(
            load_mode=MODE_FULL,
            root_dir=full_scrubbed_dir,
            bridge_summary=full_scrubbed_summary,
        ),
    }


def _first_decision_probe(
    *,
    train_scenario: str,
    transfer_scenario: str,
    seed: int,
    mode_name: str,
    mode_spec: _CarryoverModeSpec,
    context_bit: int,
) -> dict[str, object]:
    system = build_system(seed, transfer_scenario)
    _load_mode(system, mode_spec)
    source_id = system.environment.source_id
    source_agent = system.agents[source_id]
    source_selector = source_agent.engine.selector
    source_selector.capture_route_breakdowns = True
    carryover_summary = _source_support_summary(source_agent)
    signal_spec = _scenario_signal_for_context(
        transfer_scenario,
        context_bit=context_bit,
    )
    system.inject_signal_specs((signal_spec,))
    cycle_result = system.run_global_cycle()
    source_entry = cycle_result["entries"][source_id]
    state_before = dict(source_entry.state_before)
    breakdowns = source_selector.latest_route_score_breakdowns() or {}
    top_competitor = None
    for action, details in sorted(
        breakdowns.items(),
        key=lambda item: float(item[1].get("total", 0.0)),
        reverse=True,
    ):
        if action != source_entry.action:
            top_competitor = details
            break
    transform_fields = {
        transform_name: {
            "task_transform_affinity": round(
                float(state_before.get(f"task_transform_affinity_{transform_name}", 0.0)),
                4,
            ),
            "history_transform_evidence": round(
                float(
                    state_before.get(
                        f"history_transform_evidence_{transform_name}",
                        0.0,
                    )
                ),
                4,
            ),
            "source_sequence_transform_hint": round(
                float(
                    state_before.get(
                        f"source_sequence_transform_hint_{transform_name}",
                        0.0,
                    )
                ),
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
                float(
                    state_before.get(
                        f"context_feedback_credit_{transform_name}",
                        0.0,
                    )
                ),
                4,
            ),
            "context_feedback_debt": round(
                float(
                    state_before.get(
                        f"context_feedback_debt_{transform_name}",
                        0.0,
                    )
                ),
                4,
            ),
        }
        for transform_name in ("rotate_left_1", "xor_mask_1010", "xor_mask_0101")
    }
    context_action_supports = {
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
        for neighbor_id in source_agent.neighbor_ids
    }
    expected_transform = _expected_transform_for_task("task_c", context_bit)
    chosen_action = str(source_entry.action)
    chosen_transform = ""
    if chosen_action.startswith("route_transform:"):
        parts = chosen_action.split(":")
        if len(parts) == 3:
            chosen_transform = parts[2]
    elif chosen_action.startswith("route:"):
        chosen_transform = "identity"
    return {
        "seed": seed,
        "train_scenario": train_scenario,
        "transfer_scenario": transfer_scenario,
        "carryover_mode": mode_name,
        "context_bit": int(context_bit),
        "expected_transform": expected_transform,
        "transform_match": bool(expected_transform is not None and chosen_transform == expected_transform),
        "carryover_summary": carryover_summary,
        "state_before": {
            "effective_context_bit": state_before.get("effective_context_bit"),
            "effective_context_confidence": state_before.get(
                "effective_context_confidence"
            ),
            "context_promotion_ready": state_before.get("context_promotion_ready"),
            "transfer_adaptation_phase": state_before.get(
                "transfer_adaptation_phase"
            ),
            "latent_context_available": state_before.get("latent_context_available"),
            "latent_context_confidence": state_before.get(
                "latent_context_confidence"
            ),
            "context_action_supports": context_action_supports,
            "transform_fields": transform_fields,
        },
        "chosen_action": chosen_action,
        "chosen_breakdown": _compact_breakdown(breakdowns.get(chosen_action)),
        "top_competitor_breakdown": _compact_breakdown(top_competitor),
    }


def _transfer_run_probe(
    *,
    transfer_scenario: str,
    seed: int,
    mode_name: str,
    mode_spec: _CarryoverModeSpec,
) -> dict[str, object]:
    system = build_system(seed, transfer_scenario)
    _load_mode(system, mode_spec)
    summary = run_workload(system, transfer_scenario)
    return {
        "carryover_mode": mode_name,
        "summary": summary,
        "transfer_metrics": transfer_metrics(system),
    }


def _context_stat(summary: dict[str, object], context_key: str, field: str) -> float:
    return float(
        summary.get("task_diagnostics", {})
        .get("contexts", {})
        .get(context_key, {})
        .get(field, 0.0)
    )


def _mode_delta(mode_summary: dict[str, object], none_summary: dict[str, object]) -> dict[str, float]:
    return {
        "exact_matches": int(mode_summary["exact_matches"]) - int(none_summary["exact_matches"]),
        "mean_bit_accuracy": round(
            float(mode_summary["mean_bit_accuracy"]) - float(none_summary["mean_bit_accuracy"]),
            4,
        ),
        "ctx0_bit_accuracy": round(
            _context_stat(mode_summary, "context_0", "mean_bit_accuracy")
            - _context_stat(none_summary, "context_0", "mean_bit_accuracy"),
            4,
        ),
        "ctx1_bit_accuracy": round(
            _context_stat(mode_summary, "context_1", "mean_bit_accuracy")
            - _context_stat(none_summary, "context_1", "mean_bit_accuracy"),
            4,
        ),
    }


def _aggregate_bridge_results(results: Sequence[dict[str, object]]) -> dict[str, object]:
    mode_names = tuple(results[0]["carryover_modes"].keys()) if results else ()

    def _mean_for_mode(mode_name: str, path: Sequence[str]) -> float | None:
        if not results:
            return None
        values: list[float] = []
        for result in results:
            current: object = result["carryover_modes"][mode_name]
            for key in path:
                current = current[key]  # type: ignore[index]
            values.append(float(current))
        return round(mean(values), 4)

    aggregate_modes: dict[str, object] = {}
    for mode_name in mode_names:
        aggregate_modes[mode_name] = {
            "mean_exact_matches": _mean_for_mode(mode_name, ("transfer_run", "summary", "exact_matches")),
            "mean_bit_accuracy": _mean_for_mode(mode_name, ("transfer_run", "summary", "mean_bit_accuracy")),
            "mean_delta_vs_none_exact": _mean_for_mode(mode_name, ("delta_vs_none", "exact_matches")),
            "mean_delta_vs_none_bit_accuracy": _mean_for_mode(mode_name, ("delta_vs_none", "mean_bit_accuracy")),
            "context_0_first_decision_match_rate": _mean_for_mode(mode_name, ("first_decisions", "context_0", "transform_match")),
            "context_1_first_decision_match_rate": _mean_for_mode(mode_name, ("first_decisions", "context_1", "transform_match")),
            "mean_early_wrong_transform_family_rate": _mean_for_mode(
                mode_name,
                ("transfer_run", "transfer_metrics", "early_window_wrong_transform_family_rate"),
            ),
        }
    return {
        "mode_order": list(mode_names),
        "modes": aggregate_modes,
    }


def diagnose_b_to_c_carryover_bridge(
    *,
    train_scenario: str = DEFAULT_TRAIN_SCENARIO,
    transfer_scenario: str = DEFAULT_TRANSFER_SCENARIO,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    output_path: Path | None = None,
) -> dict[str, object]:
    results = []
    for seed in seeds:
        training = build_system(seed, train_scenario)
        training_summary = run_workload(training, train_scenario)
        base_dir = ROOT / "tests_tmp" / f"btc_carryover_bridge_{uuid.uuid4().hex}"
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
            none_summary: dict[str, object] | None = None
            for mode_name, mode_spec in mode_specs.items():
                first_decisions = {
                    f"context_{context_bit}": _first_decision_probe(
                        train_scenario=train_scenario,
                        transfer_scenario=transfer_scenario,
                        seed=seed,
                        mode_name=mode_name,
                        mode_spec=mode_spec,
                        context_bit=context_bit,
                    )
                    for context_bit in (0, 1)
                }
                transfer_run = _transfer_run_probe(
                    transfer_scenario=transfer_scenario,
                    seed=seed,
                    mode_name=mode_name,
                    mode_spec=mode_spec,
                )
                mode_payload = {
                    "bridge_summary": dict(mode_spec.bridge_summary),
                    "first_decisions": first_decisions,
                    "transfer_run": transfer_run,
                }
                if mode_name == MODE_NONE:
                    none_summary = dict(transfer_run["summary"])
                carryover_modes[mode_name] = mode_payload
            if none_summary is None:
                raise RuntimeError("Cold-start mode missing from B->C bridge diagnostic")
            for mode_name, mode_payload in carryover_modes.items():
                mode_payload["delta_vs_none"] = _mode_delta(
                    mode_payload["transfer_run"]["summary"],
                    none_summary,
                )
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
        "results": results,
        "aggregate": _aggregate_bridge_results(results),
    }

    if output_path is not None:
        manifest = build_run_manifest(
            harness="diagnose_b_to_c_carryover_bridge",
            seeds=seeds,
            scenarios=(train_scenario, transfer_scenario),
            metadata={
                "train_scenario": train_scenario,
                "transfer_scenario": transfer_scenario,
                "mode_order": result["aggregate"]["mode_order"],
            },
            result=result,
        )
        write_run_manifest(output_path, manifest)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnose B->C carryover composition with selective context-support scrubbing.",
    )
    parser.add_argument(
        "--train-scenario",
        default=DEFAULT_TRAIN_SCENARIO,
    )
    parser.add_argument(
        "--transfer-scenario",
        default=DEFAULT_TRANSFER_SCENARIO,
    )
    parser.add_argument(
        "--seeds",
        nargs="+",
        type=int,
        default=list(DEFAULT_SEEDS),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    args = parser.parse_args()
    print(
        json.dumps(
            diagnose_b_to_c_carryover_bridge(
                train_scenario=args.train_scenario,
                transfer_scenario=args.transfer_scenario,
                seeds=tuple(args.seeds),
                output_path=args.output,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
