# 2026-03-30 0947 - C HR Bounded Overlap Topology Pilot Scaffold

## Why

The redesign discussion identified two different candidate interventions:

- improve local-unit commitment behavior through pulse/context/plasticity separation
- improve the graph geometry itself through a bounded overlapping ternary topology

This pass starts the second path in a narrow way: add an opt-in overlap topology for C-family and hidden-regime evaluation without changing A/B/occupancy or the default Phase 8 topology behavior.

## What Changed

- Added `bounded_ternary_overlap_topology()` to `phase8/scenarios.py`.
- Added `scenario_with_topology_mode(...)` so an existing `ScenarioSpec` can be cloned onto the bounded overlap graph without touching its signal schedule.
- Added `topology_mode = "legacy" | "bounded_overlap_13715"` to:
  - `scripts/evaluate_laminated_phase8.py`
  - `scripts/evaluate_hidden_regime_forecasting.py`
- Scoped the topology override to the C and HR evaluation entrypoints rather than globally rewriting the benchmark suites.

## Geometry Implemented

The overlap topology is the bounded pattern discussed in the redesign note:

- source layer: `1`
- layer 1: `3`
- layer 2: `7`
- layer 3: `15`
- sink layer: `1`

Parents connect to up to 3 children, and adjacent parents share downstream children.
The implemented overlap rule uses sliding 3-child windows across the next layer, which produces a bounded partially shared forward graph rather than a fully branching tree.

## Why This Scope

This is intentionally narrow:

- C-family laminated runs can now be evaluated on the overlap graph
- hidden-regime laminated runs can now be evaluated on the overlap graph
- A/B and occupancy stay on their existing topologies
- default behavior remains `legacy`

That gives a clean comparison path without conflating topology exploration with repo-wide substrate changes.

## Tests

Added `tests/test_c_hr_overlap_topology.py` covering:

- layer widths and fanout of the overlap topology
- scenario cloning while preserving signal schedule
- C laminated evaluator recording `topology_mode`
- hidden-regime evaluator recording `topology_mode`
- legacy hidden-regime suite metadata remaining unchanged

## Smoke Read

Small execution smoke with the new topology mode:

- `C3S1 task_a visible`, budget `4`, safety `2`
  - final accuracy `0.438`
  - forecast accuracy `0.375`
- `HR1 task_a hidden`, budget `4`, safety `2`
  - final accuracy `0.600`
  - forecast accuracy `0.400`

The important result from this pass is not performance yet, but that the new graph mode runs end-to-end through the laminated C and HR paths without breaking the legacy mode.

## Files

- `phase8/scenarios.py`
- `phase8/__init__.py`
- `scripts/evaluate_laminated_phase8.py`
- `scripts/evaluate_hidden_regime_forecasting.py`
- `tests/test_c_hr_overlap_topology.py`
