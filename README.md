# REAL Neural Substrate

REAL Neural Substrate is a standalone research prototype for native, local-learning neural-substrate experiments built on two layers:

- `real_core`: the generalized REAL engine and memory substrate contracts
- `phase8`: the multi-agent substrate where each node is a local REAL agent

The repo is intentionally focused on non-backprop, non-global-loss experiments around routing, carryover, transfer, and emergent local specialization. It is a clean spin-out from the broader umbrella workspace, not a full archive of every prior phase.

## Package Map

- `real_core/`: reusable allostatic engine, selector, mesh, substrate, carryover, and shared types
- `phase8/`: node agents, local routing environment, substrate mechanics, selectors, scenarios, and topology growth logic
- `tests/`: standalone `real_core` tests plus Phase 8 unit and integration coverage
- `docs/`: architecture notes, the cross-phase overview, the updated technical report, session synthesis, and selected trace documents

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
python -m unittest discover -s tests -p "test_*.py"
python run_phase8_demo.py --mode comparison --seed 13 --scenario cvt1_task_a_stage1
python compare_task_transfer.py
```

## Main Experiments

- `run_phase8_demo.py`: interactive demo entrypoint for comparison, stress, trace, and transfer views
- `compare_cold_warm.py`: cold vs warm carryover comparisons across Phase 8 scenarios
- `compare_task_transfer.py`: Task A to Task B transfer evaluation
- `compare_transfer_matrix.py`: directional transfer matrix across nearby task variants
- `analyze_transfer_timecourse.py`: latent/context timecourse analysis for transfer behavior
- `compare_large_topology.py`: cold and warm evaluation on the 10-node, 36-packet large topology
- `compare_morphogenesis_large.py`: large-topology morphogenesis benchmark
- `compare_sequential_transfer.py`: sequential `A -> B -> C` transfer evaluation
- `neural_baseline.py`: online MLP/RNN comparison harness for sample-efficiency checks

## Reference Artifacts

- `docs/technical_report.md`: current merged technical report
- `docs/20260317_phase8_session_synthesis.md`: March 17 consolidated progress summary
- `docs/traces/`: selected March 17 episodic traces for neural baselines and large-topology morphogenesis
- `phase8_dashboard.html`: static Phase 8 dashboard snapshot carried over from the source workspace

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
- the top-level comparison/demo scripts as the primary runnable interfaces
