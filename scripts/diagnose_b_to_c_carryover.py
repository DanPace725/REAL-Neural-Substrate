from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path
from typing import Dict, Sequence

from phase8.environment import _expected_transform_for_task
from scripts.compare_cold_warm import ROOT, SCENARIOS, build_system, run_workload
from scripts.repeated_signal_scenarios import ordered_signal_events

DEFAULT_TRAIN_SCENARIO = "cvt1_task_b_stage1"
DEFAULT_TRANSFER_SCENARIO = "cvt1_task_c_stage1"
DEFAULT_SEEDS = (13,)


def _load_carryover(
    system,
    *,
    carryover_mode: str,
    full_dir: Path,
    substrate_dir: Path,
) -> None:
    if carryover_mode == "full":
        system.load_memory_carryover(full_dir)
        return
    if carryover_mode == "substrate":
        system.load_substrate_carryover(substrate_dir)


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
    summary: Dict[str, object] = {
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


def _first_decision_probe(
    *,
    train_scenario: str,
    transfer_scenario: str,
    seed: int,
    carryover_mode: str,
    context_bit: int,
    full_dir: Path,
    substrate_dir: Path,
) -> dict[str, object]:
    system = build_system(seed, transfer_scenario)
    _load_carryover(
        system,
        carryover_mode=carryover_mode,
        full_dir=full_dir,
        substrate_dir=substrate_dir,
    )
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
    return {
        "seed": seed,
        "train_scenario": train_scenario,
        "transfer_scenario": transfer_scenario,
        "carryover_mode": carryover_mode,
        "context_bit": int(context_bit),
        "expected_transform": _expected_transform_for_task("task_c", context_bit),
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
        "chosen_action": source_entry.action,
        "chosen_breakdown": _compact_breakdown(breakdowns.get(source_entry.action)),
        "top_competitor_breakdown": _compact_breakdown(top_competitor),
    }


def diagnose_b_to_c_carryover(
    *,
    train_scenario: str = DEFAULT_TRAIN_SCENARIO,
    transfer_scenario: str = DEFAULT_TRANSFER_SCENARIO,
    seeds: Sequence[int] = DEFAULT_SEEDS,
) -> dict[str, object]:
    results = []
    for seed in seeds:
        training = build_system(seed, train_scenario)
        training_summary = run_workload(training, train_scenario)
        base_dir = ROOT / "tests_tmp" / f"btc_carryover_{uuid.uuid4().hex}"
        full_dir = base_dir / "full"
        substrate_dir = base_dir / "substrate"
        full_dir.mkdir(parents=True, exist_ok=True)
        substrate_dir.mkdir(parents=True, exist_ok=True)
        try:
            training.save_memory_carryover(full_dir)
            training.save_substrate_carryover(substrate_dir)
            modes = {}
            for carryover_mode in ("none", "substrate", "full"):
                modes[carryover_mode] = {
                    f"context_{context_bit}": _first_decision_probe(
                        train_scenario=train_scenario,
                        transfer_scenario=transfer_scenario,
                        seed=seed,
                        carryover_mode=carryover_mode,
                        context_bit=context_bit,
                        full_dir=full_dir,
                        substrate_dir=substrate_dir,
                    )
                    for context_bit in (0, 1)
                }
        finally:
            shutil.rmtree(base_dir, ignore_errors=True)
        results.append(
            {
                "seed": seed,
                "train_scenario": train_scenario,
                "transfer_scenario": transfer_scenario,
                "training_summary": training_summary,
                "carryover_modes": modes,
            }
        )
    return {
        "train_scenario": train_scenario,
        "transfer_scenario": transfer_scenario,
        "seeds": [int(seed) for seed in seeds],
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnose early B->C carryover signals across none/substrate/full modes.",
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
    args = parser.parse_args()
    print(
        json.dumps(
            diagnose_b_to_c_carryover(
                train_scenario=args.train_scenario,
                transfer_scenario=args.transfer_scenario,
                seeds=tuple(args.seeds),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
