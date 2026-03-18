# REAL Neural Substrate

REAL Neural Substrate is a standalone research prototype for native, local-learning neural-substrate experiments built on two layers:

- `real_core`: the generalized REAL engine and memory substrate contracts
- `phase8`: the multi-agent substrate where each node is a local REAL agent

The repo is intentionally focused on non-backprop, non-global-loss experiments around routing, carryover, transfer, and emergent local specialization. It is a clean spin-out from the broader umbrella workspace, not a full archive of every prior phase.

## For AI Coding Agents

Before making changes, read `AGENTS.md`, then cross-reference the docs and trace files using the task's keywords so you understand the repo's scope, vision, current experimental state, and recent decisions. Do not jump straight into edits from surface-level code patterns alone; review the relevant synthesis notes, technical report sections, and March 17 traces first when the change touches transfer, neural baselines, morphogenesis, topology scaling, or latent-context behavior.

## Package Map

- `real_core/`: reusable allostatic engine, selector, mesh, substrate, carryover, and shared types
- `phase8/`: node agents, local routing environment, substrate mechanics, selectors, scenarios, and topology growth logic
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

## Reference Artifacts

- `docs/technical_report.md`: current merged technical report
- `docs/20260317_phase8_session_synthesis.md`: March 17 consolidated progress summary
- `docs/experiment_outputs/`: timestamped JSON experiment manifests
- `docs/traces/`: selected March 17 episodic traces for neural baselines and large-topology morphogenesis
- `docs/phase8_dashboard.html`: static Phase 8 dashboard snapshot carried over from the source workspace
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
