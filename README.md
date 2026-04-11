# REAL Neural Substrate

REAL stands for **Relationally Embedded Allostatic Learning**.

REAL Neural Substrate is a standalone research prototype exploring whether useful computation can emerge from many local agents adapting under metabolic pressure rather than from a single model trained by global gradient descent. In this repo, learning is supposed to show up as durable changes in substrate, carryover state, routing bias, and structural support, not as opaque end-to-end weight updates.

The project is organized around two layers:

- `real_core`: the reusable REAL engine, anticipation contracts, recognition and prediction interfaces, carryover, and shared substrate types
- `phase8`: the native multi-agent substrate where each node is a local REAL agent embedded in a routing environment

This repo is intentionally focused on non-backprop, non-global-loss experiments around routing, carryover, transfer, latent context, occupancy, emergent local specialization, and topology growth. It is a clean spin-out from a larger workspace, but this repository is meant to stand on its own.

At the current architecture, the generalized REAL loop is:

`observe -> recognize -> predict -> select -> execute -> score -> compare -> consolidate`

`real_core` owns the reusable loop and contracts. `phase8` binds those concepts to routing-specific substrate state, selector pressure, capability recruitment, admission, morphogenesis, and prediction-aware environment dynamics.

## Why This Repo Exists

Most modern AI systems rely on a global objective, a centralized training pass, and parameter updates pushed through the whole model. REAL is testing a different hypothesis:

- useful behavior can emerge from local allostatic adaptation
- persistent learning can live in maintained substrate and carryover state
- transfer can come from structurally conserved support rather than retraining from scratch
- new capacity can appear through local growth pressure rather than fixed architecture alone

The point of this repo is not to reproduce standard deep learning with unfamiliar vocabulary. The point is to test whether a genuinely different learning architecture can still become competitive on concrete tasks.

## Current Status

The repo is an active research prototype, not a polished library. The most notable recent result is the REAL-native occupancy harness, where the current V3 configuration reached near-parity with the existing MLP benchmark on a real sensor dataset while still using local substrate dynamics rather than backpropagation. The transfer, latent-context, and morphogenesis experiments remain central parts of the project as well.

If you are arriving from the ALIFE paper, treat the occupancy result in the paper as a historical March 2026 result rather than a claim about current `main`. The paper-aligned occupancy behavior is represented more closely by the March V3 artifacts in `docs/experiment_outputs/` and by a checkout or snapshot around commit `09f9b09` than by the evolving current codebase. Current `main` has continued to change after the paper-facing runs, so re-running the same command today may not reproduce the paper F1 exactly.

## For AI Coding Agents

Before making changes, read `AGENTS.md`, then cross-reference the docs and trace files using the task's keywords so you understand the repo's scope, vision, current experimental state, and recent decisions. Do not jump straight into edits from surface-level code patterns alone; review the relevant synthesis notes, technical report sections, March 17 traces, and the March 19 anticipation/recognition/prediction synthesis when the change touches transfer, neural baselines, morphogenesis, topology scaling, latent-context behavior, or the REAL loop itself.

## Package Map

- `real_core/`: reusable allostatic engine, recognition and expectation interfaces, selectors, mesh, substrate, carryover, and shared types
- `phase8/`: node agents, local routing environment, substrate mechanics, routing-specific expectation binding, selectors, scenarios, and topology growth logic
- `scripts/`: experiment runners, comparison harnesses, and manifest-writing utilities
- `tests/`: standalone `real_core` tests plus Phase 8 unit and integration coverage
- `docs/`: architecture notes, the cross-phase overview, the updated technical report, session synthesis, and selected trace documents

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
python -m unittest discover -s tests -p "test_*.py"
python -m scripts.run_phase8_demo --mode comparison --seed 13 --scenario cvt1_task_a_stage1
python -m scripts.compare_task_transfer
```

After `pip install -e .`, the same runners are also available as console scripts such as `real-phase8-demo`, `real-task-transfer`, and `real-morphogenesis-large`.

## Where To Start

- If you want to understand how the code actually runs, start with `docs/CODE_TOUR.md`.
- If you want the architecture overview, start with `docs/summaries/architecture_notes.md`.
- If you want the repo/package map, read `docs/summaries/project_overview_cross_phase.md`.
- If you want the broad current state in prose, read `docs/reports/SYNTHESIS.md`.
- If you want the interpretability and diagnostics overview, read `docs/reports/INTERPRETABILITY.md`.
- If you want a non-technical version, read `docs/reports/PLAIN_ENGLISH_OVERVIEW.md`.
- If you want the occupancy harness CLI, read `docs/running_occupancy_v3.md`.
- If you need recent implementation history, use `docs/traces/INDEX.md`.

## Main Experiments

- `scripts/run_phase8_demo.py`: interactive demo entrypoint for comparison, stress, trace, and transfer views
- `scripts/compare_cold_warm.py`: cold vs warm carryover comparisons across Phase 8 scenarios
- `scripts/compare_task_transfer.py`: Task A to Task B transfer evaluation
- `scripts/compare_transfer_matrix.py`: directional transfer matrix across nearby task variants
- `scripts/analyze_transfer_timecourse.py`: latent/context timecourse analysis for transfer behavior
- `scripts/compare_large_topology.py`: cold and warm evaluation on the 10-node, 36-packet large topology
- `scripts/compare_morphogenesis_large.py`: large-topology morphogenesis benchmark
- `scripts/compare_morphogenesis_large_paired.py`: paired visible-vs-latent large-topology morphogenesis comparison
- `scripts/compare_morphogenesis_large_mode_switched.py`: visible-to-latent curriculum handoff benchmark
- `scripts/compare_morphogenesis_large_carryover_bridge.py`: full-vs-substrate carryover bridge diagnostic
- `scripts/compare_sequential_transfer.py`: sequential `A -> B -> C` transfer evaluation
- `scripts/compare_cyclic_transfer.py`: cyclic `A -> B -> C -> A` transfer evaluation
- `scripts/diagnose_c_family_real.py`: REAL-only full-capability diagnostic for the generated `C` ambiguity ladder
- `scripts/neural_baseline.py`: online MLP/RNN comparison harness for sample-efficiency checks
- `scripts/compare_occupancy_baseline.py`: occupancy bridge comparison between the frozen MLP baseline and a Phase 8 packetized REAL slice
- `scripts/run_occupancy_real_v3.py`: REAL-native occupancy harness with fresh-session vs persistent eval, admission-source ingress, and multi-seed sweep support. See `docs/running_occupancy_v3.md` for CLI usage.

## Reference Artifacts

- `docs/reports/technical_report.md`: current merged technical report
- `docs/summaries/20260317_phase8_session_synthesis.md`: March 17 consolidated progress summary
- `docs/reports/SYNTHESIS.md`: current high-level project synthesis
- `docs/reports/INTERPRETABILITY.md`: how node-level and selector-level analysis has been used to debug and shape the architecture
- `docs/reports/PLAIN_ENGLISH_OVERVIEW.md`: non-technical overview
- `docs/traces/2026-03-19 1151 - Session Synthesis Anticipation Self Selection and Carryover.md`: March 19 synthesis covering anticipation, recognition, prediction, self-selection, and carryover hygiene
- `docs/experiment_outputs/`: timestamped JSON experiment manifests
- `docs/experiment_outputs/v3_best_real_seed13_summary.md`: March 2026 saved summary for the high-F1 occupancy run referenced during the paper-writing period
- `docs/experiment_outputs/v3_best_real_seed13.json`: saved JSON manifest for that paper-aligned occupancy run
- `docs/traces/`: implementation and decision traces, with `docs/traces/INDEX.md` as the entrypoint
- `docs/visualizations/phase8_dashboard.html`: static Phase 8 dashboard snapshot carried over from the source workspace
- `docs/visualizations/real_cycle.html`: saved cyclic-transfer visualization artifact

## What Stayed In The Umbrella Repo

This standalone repo intentionally leaves behind:

- older phase packages and legacy `real/` implementations
- heavyweight experiment outputs, temporary carryover snapshots, and scratch traces
- editor-specific folders and generated caches
- broader research context that is useful historically but not required to run the neural substrate work

## Positioning

This repo is a research prototype, not yet a stabilized public library. The supported boundaries are:

- `real_core` as the reusable engine layer
- `phase8` as the native substrate experiment layer
- `scripts/` as the primary runnable experiment interface
