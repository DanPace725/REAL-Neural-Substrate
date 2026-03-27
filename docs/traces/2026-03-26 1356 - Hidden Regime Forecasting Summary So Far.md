# 2026-03-26 1356 - Hidden Regime Forecasting Summary So Far

**Type:** Summary trace  
**Author:** Codex  
**Model:** GPT-5 Codex

## Purpose

This trace summarizes the hidden-regime forecasting work completed so far,
including:

- laminated forecasting support added to the REAL stack
- the dedicated hidden-regime benchmark family
- benchmark runner and output persistence updates
- key benchmark sweeps and saved experiment artifacts
- the current diagnosis of where the architecture is working and where it is failing

## Architectural Changes

### 1. Laminated forecasting support

The laminated stack was extended to support explicit forecasting as a first-class
 output rather than only action-level anticipation.

Key additions:

- explicit forecast types and interfaces in `real_core`
- compact slow-layer intervention payoff/regret summaries
- slice-level `forecast_metrics` and `intervention_payoff_trend` in Phase 8

Relevant trace:

- `2026-03-26 1303 - Laminated Forecast Readout and Intervention Summary`

### 2. Hidden-regime symbolic benchmark family

A dedicated symbolic hidden-regime benchmark family was added in `phase8` to
test the laminated controller on prediction-oriented tasks that fit the current
architecture.

Implemented cases:

- `HR1`: binary hidden regime, short memory
- `HR2`: binary hidden regime, extended memory
- `HR3`: quad hidden regime from paired parity state
- `HR4`: binary hidden regime with a mid-run rule shift

Each case provides:

- a hidden scenario for the main benchmark
- a visible-label scenario as an ablation
- `task_a`, `task_b`, and `task_c` variants

Relevant traces:

- `2026-03-26 1318 - Hidden Regime Forecasting Family`
- `2026-03-26 1323 - Hidden Regime Shift Case and Saved Sweep Outputs`

### 3. Hidden-regime runner and output persistence

A dedicated runner was added:

- `scripts/evaluate_hidden_regime_forecasting.py`

Key behavior:

- defaults to laminated, policy-selecting control
- defaults to `self-selected` capability policy
- defaults to `real` regulator mode
- writes per-run manifests to `docs/experiment_outputs`
- now also writes suite manifests for multi-run sweeps
- now uses unique timestamped filenames so reruns do not overwrite prior outputs

Relevant trace:

- `2026-03-26 1334 - Hidden Regime Unique Outputs and Budget 8 Sweep`

## Benchmark Sweeps Run So Far

### Hidden-regime targeted sweeps

Completed saved sweeps include:

- `HR1, HR2, HR4` on `task_a`, hidden mode, `budget=4`, `safety_limit=8`
- `HR1, HR2, HR4` on `task_a`, hidden mode, `budget=4`, `safety_limit=30`
- `HR1, HR2, HR4` on `task_b`, hidden mode, `budget=4`, `safety_limit=30`
- `HR1, HR2, HR4` on `task_c`, hidden mode, `budget=4`, `safety_limit=30`
- `HR1, HR2, HR4` on all tasks, hidden mode, `budget=8`, `safety_limit=30`
- `HR1, HR2, HR4` on all tasks, hidden mode, `budget=4`, `safety_limit=100`

Representative suite manifests:

- `docs/experiment_outputs/20260326_hidden_regime_suite_hr1_hr2_hr4_task_a_hidden_self_selected_b4_seed13.json`
- `docs/experiment_outputs/20260326_hidden_regime_suite_hr1_hr2_hr4_task_b_hidden_self_selected_b4_seed13.json`
- `docs/experiment_outputs/20260326_hidden_regime_suite_hr1_hr2_hr4_task_c_hidden_self_selected_b4_seed13.json`
- `docs/experiment_outputs/20260326_133343_116940_hidden_regime_suite_hr1_hr2_hr4_all_tasks_hidden_self_selected_b8_s30_seed13.json`
- `docs/experiment_outputs/20260326_133714_141319_hidden_regime_suite_hr1_hr2_hr4_all_tasks_hidden_self_selected_b4_s100_seed13.json`

Relevant traces:

- `2026-03-26 1323 - Hidden Regime Shift Case and Saved Sweep Outputs`
- `2026-03-26 1334 - Hidden Regime Unique Outputs and Budget 8 Sweep`
- `2026-03-26 1338 - Hidden Regime Budget 4 Safety 100 Sweep`

## Working Results Summary

### 1. `budget=4` is healthier than `budget=8`

The hidden-regime family consistently looked better with shorter slices and more
slow-layer intervention opportunities.

Observed pattern:

- `budget=8 / safety_limit=30` removed earlier clean-settle behavior
- `budget=4 / safety_limit=100` restored better performance on several tasks
- longer slices do not appear to improve the laminated controller globally

Current read:

- more work per slice is not automatically better
- some tasks benefit more from frequent slow-layer intervention than from longer slices

### 2. `HR4/task_c` is the clearest success case

Strongest observed run:

- `HR4/task_c`, hidden mode, `budget=4`, `safety_limit=100`
- settled in 4 slices
- reached `1.000` final bit accuracy

Behavioral pattern:

- early forecast signal present
- quick productive move into growth
- immediate jump to high accuracy
- stable enough to settle

### 3. `HR2/task_c` is the clearest failure case

Strongest degradation case:

- `HR2/task_c`, hidden mode, `budget=4`, `safety_limit=100`
- ran the full 100 slices without settling
- ended at `0.250` final bit accuracy

Observed pattern:

- resolved forecast signal only in slice 1
- almost no resolved forecast supervision afterward
- controller keeps cycling growth policies
- intervention payoff falls back to plain bit-accuracy deltas once forecast resolution disappears
- performance oscillates around mediocre or poor values instead of finding a stable productive attractor

### 4. Better runs are often “good but noisy,” not fully converged

Examples:

- `HR2/task_a`
- `HR1/task_b`

These runs:

- get useful early signal
- reach fairly high bit accuracy
- remain mostly inside growth policy families
- do not truly stabilize enough to settle

So they are better understood as productive attractor cases rather than clean
long-horizon controller successes.

## Current Diagnosis

The current hidden-regime behavior appears to be shaped by three interacting facts:

### 1. Forecast supervision is sparse and short-lived

For several runs, `resolved_forecast_count` is nonzero only in the first one or
two slices. After that, the laminated controller no longer has sustained
forecast-level supervision.

### 2. The slow layer upgrades into growth early and tends to stay there

The controller can choose non-growth policies initially, but once in
`growth-visible` it is restricted to growth-family policies.

That was introduced to prevent mode thrashing and destructive reversion after
growth state had accumulated.

Concrete rationale from prior trace:

- `2026-03-25 1600 - REAL Slow Layer Regulator Debugging and B Family Sweep`

That trace records a failure where the regulator switched from
`growth-visible` back to plain `visible`, which discarded accumulated
morphogenetic state and sharply damaged performance. The fix was to keep growth
families isolated so the engine could not casually step back out once growth
had begun.

### 3. Once forecast resolution disappears, regulation falls back to bit accuracy

`phase8/lamination.py` uses forecast accuracy as the primary intervention metric
when available, but falls back to mean bit accuracy when forecast resolution is
absent.

That means some later slices are still being regulated, but not on direct
forecasting success. This likely contributes to noisy growth-policy cycling in
cases like `HR2/task_c`.

## Focused Validation Completed

Focused test sets were run after the main implementation steps, including:

- `tests.test_lamination`
- `tests.test_phase8_lamination`
- `tests.test_hidden_regime_forecasting`

Most recent focused result:

- 14 tests passed

## Working Interpretation

The hidden-regime family is already useful. It is revealing:

- that laminated forecasting can work on some symbolic hidden-state tasks
- that early slice evidence and early policy choice matter heavily
- that the controller is not yet reliably stabilizing after entering growth
- that some failures are not just budget problems, but regulator/diagnostic problems

The strongest current pair for contrast is:

- success: `HR4/task_c`
- failure: `HR2/task_c`

The strongest “good but noisy” comparison case is:

- `HR2/task_a`

## Most Likely Next Directions

1. Add a compact analysis script that extracts per-slice:
   - `chosen_policy`
   - `forecast_metrics`
   - `intervention_payoff_trend`

2. Add a diagnostic guard such as:
   - do not enter growth until forecast resolution is present for N consecutive slices

3. Compare successful quick-settle behavior against high-but-non-settling behavior:
   - `HR4/task_c` vs `HR2/task_a`

4. Revisit whether the current growth hysteresis should be softened for hidden-regime
   forecasting once forecast resolution collapses, rather than applying the same
   lock assumptions used to protect morphogenetic state in the earlier B-family work
