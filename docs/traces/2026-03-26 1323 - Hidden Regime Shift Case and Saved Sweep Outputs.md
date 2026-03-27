# 2026-03-26 1323 - Hidden Regime Shift Case and Saved Sweep Outputs

**Type:** Implementation trace  
**Author:** Codex  
**Model:** GPT-5 Codex

## Purpose

This pass extends the hidden-regime forecasting family with an explicit
mid-run rule-shift case and tightens benchmark persistence so multi-run sweeps
also leave a saved aggregate manifest in `docs/experiment_outputs`.

The goal is to move the family beyond steady-state hidden inference and start
testing laminated adaptation under changing symbolic rule bindings.

## What Changed

### 1. Added hidden-regime shift support in `phase8/environment.py`

New support was added for `hidden_regime_hr4_*` task IDs:

- `hidden_regime_hr4_phase1_*` uses the normal binary task transform maps
- `hidden_regime_hr4_phase2_*` uses swapped binary transform maps

This makes the mid-run shift visible to the existing expectation and forecast
machinery without introducing a new evaluator.

### 2. Added `HR4` to the hidden-regime benchmark family

File:

- `phase8/hidden_regime.py`

`HR4` is a binary hidden-regime benchmark with:

- 3-step sequence memory
- 4 passes of the symbolic sequence
- a phase transition halfway through the run
- branch-pressure topology

The first half uses one regime-to-transform binding and the second half uses a
swapped binding, forcing the slow layer to respond to a genuine shift in the
forecasting environment.

### 3. Added sweep-level output persistence

File:

- `scripts/evaluate_hidden_regime_forecasting.py`

The runner already wrote per-run manifests by default. This pass adds a saved
suite manifest when multiple benchmarks/tasks are run in one command, so sweep
output is also persisted under `docs/experiment_outputs` rather than existing
only in terminal output.

### 4. Extended focused tests

File:

- `tests/test_hidden_regime_forecasting.py`

Added coverage for:

- `HR4` presence in the suite
- mixed `phase1` / `phase2` task IDs in the visible schedule
- end-to-end laminated result shape for the regime-shift case

## Validation

Focused tests:

- `python -m unittest tests.test_lamination tests.test_hidden_regime_forecasting tests.test_phase8_lamination`

Result:

- 13 tests passed

Saved benchmark sweep:

- `python -m scripts.evaluate_hidden_regime_forecasting --sweep HR1,HR2,HR4 -t task_a --observable hidden --reg real --budget 4 --safety-limit 8 --compact`

Saved outputs:

- `docs/experiment_outputs/20260326_hidden_regime_hr1_task_a_hidden_self_selected_b4_seed13.json`
- `docs/experiment_outputs/20260326_hidden_regime_hr2_task_a_hidden_self_selected_b4_seed13.json`
- `docs/experiment_outputs/20260326_hidden_regime_hr4_task_a_hidden_self_selected_b4_seed13.json`
- `docs/experiment_outputs/20260326_hidden_regime_suite_hr1_hr2_hr4_task_a_hidden_self_selected_b4_seed13.json`

Observed compact summary:

- `HR1`: continued after 8 slices, final bit accuracy `0.875`
- `HR2`: settled after 4 slices, final bit accuracy `1.000`
- `HR4`: continued after 8 slices, final bit accuracy `0.500`

## Working Interpretation

`HR4` is already doing useful work as a benchmark even before tuning:

- `HR2` settling quickly suggests the hidden-regime forecasting path is capable
  on the steady-state 3-step-memory binary case.
- `HR4` failing to settle under the same budget suggests the mid-run remapping
  is genuinely harder and is exposing an adaptation problem rather than merely
  a hidden-state inference problem.

That is the right direction for laminated evaluation: benchmark cases that can
separate steady-state competence from policy-mediated adaptation under change.
