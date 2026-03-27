# 2026-03-26 1334 - Hidden Regime Unique Outputs and Budget 8 Sweep

**Type:** Implementation trace  
**Author:** Codex  
**Model:** GPT-5 Codex

## Purpose

This pass addressed two follow-on needs in the hidden-regime forecasting
benchmark:

- ensure repeated benchmark runs do not overwrite prior experiment manifests
- rerun the hidden-regime A/B/C suite at a higher initial slice budget

The user specifically requested `budget=8` with `safety_limit=30` and asked
that each benchmark run create unique files under `docs/experiment_outputs`.

## What Changed

### 1. Unique output naming in the hidden-regime runner

File:

- `scripts/evaluate_hidden_regime_forecasting.py`

The runner's auto-generated per-run and suite-level filenames now include:

- a per-invocation timestamp stamp (`YYYYMMDD_HHMMSS_microseconds`)
- the initial slice budget
- the safety limit

This prevents same-day reruns with identical benchmark/task settings from
overwriting prior manifests.

### 2. Focused regression coverage

File:

- `tests/test_hidden_regime_forecasting.py`

Added a regression test asserting that the generated output path includes the
run stamp and safety limit.

## Validation

Focused tests:

- `python -m unittest tests.test_hidden_regime_forecasting tests.test_lamination tests.test_phase8_lamination`

Result:

- 14 tests passed

## Benchmark Run

Command:

- `python -m scripts.evaluate_hidden_regime_forecasting --sweep HR1,HR2,HR4 --all-tasks --observable hidden --reg real --budget 8 --safety-limit 30 --compact`

Saved outputs:

- `docs/experiment_outputs/20260326_133343_116940_hidden_regime_hr1_task_a_hidden_self_selected_b8_s30_seed13.json`
- `docs/experiment_outputs/20260326_133343_116940_hidden_regime_hr1_task_b_hidden_self_selected_b8_s30_seed13.json`
- `docs/experiment_outputs/20260326_133343_116940_hidden_regime_hr1_task_c_hidden_self_selected_b8_s30_seed13.json`
- `docs/experiment_outputs/20260326_133343_116940_hidden_regime_hr2_task_a_hidden_self_selected_b8_s30_seed13.json`
- `docs/experiment_outputs/20260326_133343_116940_hidden_regime_hr2_task_b_hidden_self_selected_b8_s30_seed13.json`
- `docs/experiment_outputs/20260326_133343_116940_hidden_regime_hr2_task_c_hidden_self_selected_b8_s30_seed13.json`
- `docs/experiment_outputs/20260326_133343_116940_hidden_regime_hr4_task_a_hidden_self_selected_b8_s30_seed13.json`
- `docs/experiment_outputs/20260326_133343_116940_hidden_regime_hr4_task_b_hidden_self_selected_b8_s30_seed13.json`
- `docs/experiment_outputs/20260326_133343_116940_hidden_regime_hr4_task_c_hidden_self_selected_b8_s30_seed13.json`
- `docs/experiment_outputs/20260326_133343_116940_hidden_regime_suite_hr1_hr2_hr4_all_tasks_hidden_self_selected_b8_s30_seed13.json`

Compact results:

- `HR1/task_a`: `0.562`, continue
- `HR1/task_b`: `0.688`, continue
- `HR1/task_c`: `0.375`, continue
- `HR2/task_a`: `0.625`, continue
- `HR2/task_b`: `0.688`, continue
- `HR2/task_c`: `0.625`, continue
- `HR4/task_a`: `0.750`, continue
- `HR4/task_b`: `0.750`, continue
- `HR4/task_c`: `0.500`, continue

## Working Interpretation

The higher initial slice budget did not improve the benchmark globally. In this
run it appears to have reduced the clean early-settlement behavior seen in some
of the `budget=4` runs.

Current read:

- more work per slice is not automatically better for the laminated controller
- some hidden-regime cases may benefit from more frequent slow-layer policy
  intervention rather than longer uninterrupted slices
- `HR4` remains comparatively strong on `task_a` and `task_b`, while `HR2`
  remains competitive but lost its earlier quick-settle behavior under the
  larger slice budget

This suggests the next step should likely be slice-level inspection rather than
continuing to scale the budget upward blindly.
