from __future__ import annotations

import argparse
import json
from pathlib import Path

from phase8.environment import NativeSubstrateSystem
from real_core.patterns import ConstraintPattern
from real_core.types import (
    CycleEntry,
    GCOStatus,
    RecognitionMatch,
    RecognitionState,
    SelectionContext,
)
from scripts.experiment_manifest import build_run_manifest, write_run_manifest


def _promotion_recognition_probe(*, seed: int) -> dict[str, object]:
    system = NativeSubstrateSystem(
        adjacency={
            "n0": ("n1",),
            "n1": ("sink",),
        },
        positions={"n0": 0, "n1": 1, "sink": 2},
        source_id="n0",
        sink_id="sink",
        selector_seed=seed,
    )
    agent = system.agents["n0"]
    edge_key = agent.substrate.edge_key("n1")

    for cycle in range(1, 9):
        agent.engine.memory.record(
            CycleEntry(
                cycle=cycle,
                action="route:n1",
                mode="constraint",
                state_before={"inbox_load": 1.0},
                state_after={edge_key: 0.8},
                dimensions={edge_key: 0.8},
                coherence=0.82,
                delta=0.05,
                gco=GCOStatus.PARTIAL,
                cost_secs=0.04,
            )
        )

    agent.engine._run_consolidation()
    entry = agent.engine.run_cycle(9)
    recognition = entry.recognition
    return {
        "pattern_count": len(agent.substrate.constraint_patterns),
        "recognized": recognition is not None and bool(recognition.matches),
        "recognition_confidence": round(
            0.0 if recognition is None else float(recognition.confidence),
            4,
        ),
        "recognition_novelty": round(
            1.0 if recognition is None else float(recognition.novelty),
            4,
        ),
        "recognition_sources": []
        if recognition is None
        else [match.source for match in recognition.matches],
        "recognition_labels": []
        if recognition is None
        else [match.label for match in recognition.matches],
        "dims_source": None
        if recognition is None
        else recognition.metadata.get("dims_source"),
    }


def _route_bias_probe(*, seed: int) -> dict[str, object]:
    system = NativeSubstrateSystem(
        adjacency={
            "n0": ("n1", "n2"),
            "n1": ("sink",),
            "n2": ("sink",),
        },
        positions={"n0": 0, "n1": 1, "n2": 1, "sink": 2},
        source_id="n0",
        sink_id="sink",
        selector_seed=seed,
    )
    system.environment.inject_signal(count=1)
    agent = system.agents["n0"]
    agent.substrate.seed_support(("n1", "n2"), value=0.6)
    agent.substrate.add_pattern(
        ConstraintPattern(
            dim_scores={
                agent.substrate.edge_key("n1"): 0.25,
                agent.substrate.edge_key("n2"): 0.85,
            },
            dim_trends={
                agent.substrate.edge_key("n1"): 0.0,
                agent.substrate.edge_key("n2"): 0.08,
            },
            valence=0.7,
            strength=0.9,
            coherence_level=0.8,
            source="route_attractor",
        )
    )
    available = agent.engine.actions.available_actions(history_size=0)
    action_without_context, mode_without_context = agent.engine.selector.select(
        available,
        history=[],
    )
    context = SelectionContext(
        cycle=1,
        recognition=RecognitionState(
            confidence=0.92,
            novelty=0.1,
            matches=[
                RecognitionMatch(
                    label="route_attractor:0",
                    score=0.94,
                    source="route_attractor",
                    strength=0.9,
                    metadata={"pattern_index": 0},
                )
            ],
        ),
    )
    action_with_context, mode_with_context = agent.engine.selector.select_with_context(
        available,
        history=[],
        context=context,
    )
    return {
        "available_actions": list(available),
        "action_without_context": action_without_context,
        "mode_without_context": mode_without_context,
        "action_with_context": action_with_context,
        "mode_with_context": mode_with_context,
        "route_flipped": action_without_context != action_with_context,
    }


def evaluate_phase8_recognition_bias_probe(
    *,
    seed: int = 17,
    output_path: Path | None = None,
) -> dict[str, object]:
    result = {
        "seed": int(seed),
        "promotion_recognition_probe": _promotion_recognition_probe(seed=seed),
        "route_bias_probe": _route_bias_probe(seed=seed),
    }
    if output_path is not None:
        manifest = build_run_manifest(
            harness="phase8_recognition_bias_probe",
            seeds=(seed,),
            scenarios=("phase8_route_pattern_probe",),
            metadata={},
            result=result,
        )
        write_run_manifest(output_path, manifest)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a tiny Phase 8 probe for pattern recognition and route bias."
    )
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--output", type=str)
    args = parser.parse_args()

    result = evaluate_phase8_recognition_bias_probe(
        seed=args.seed,
        output_path=Path(args.output) if args.output else None,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
