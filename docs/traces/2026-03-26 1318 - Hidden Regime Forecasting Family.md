# 2026-03-26 1318 - Hidden Regime Forecasting Family

**Type:** Implementation trace  
**Author:** Codex  
**Model:** GPT-5 Codex

## Purpose

This pass adds a dedicated symbolic hidden-regime forecasting family for
laminated Phase 8 benchmarking and testing.

The benchmark is meant to exercise the laminated stack in its normal operating
mode:

- the fast layer processes bounded slices of symbolic routing evidence
- the slow layer chooses a compound policy for the next slice
- forecasting is evaluated slice by slice through the explicit forecast readout
- fixed-mode runs remain available only as ablations, not as the default

## What Changed

### 1. Added hidden-regime task binding in `phase8/environment.py`

New task prefixes were introduced so Phase 8 can derive expected transforms from
symbolic sequence history for the hidden-regime family:

- `hidden_regime_hr1_*`: binary regime from a 1-step parity window
- `hidden_regime_hr2_*`: binary regime from a 3-step parity window
- `hidden_regime_hr3_*`: 4-regime state from the last two parities

This keeps the benchmark on the existing Phase 8 expectation path rather than
introducing a parallel evaluator.

### 2. Added a dedicated hidden-regime family in `phase8/hidden_regime.py`

The new family currently contains three benchmark points:

- `HR1`: binary hidden regime, short memory
- `HR2`: binary hidden regime, extended memory
- `HR3`: quad hidden regime from paired parity state

Each case provides:

- a visible-label scenario for ablation
- a hidden-label scenario for the actual benchmark
- `task_a`, `task_b`, and `task_c` variants

Signals are generated from symbolic 4-bit sequences with stable transform maps,
while the hidden regime is determined from recent parity history.

### 3. Added a dedicated laminated runner

New script:

- `scripts/evaluate_hidden_regime_forecasting.py`

This runner:

- defaults to `self-selected` capability policy
- defaults to `real` regulator mode
- uses `observable=hidden` by default
- reports compact forecasting-oriented slice summaries

The intent is to benchmark laminated policy selection directly instead of
pinning the run to a single capability mode.

### 4. Added focused tests

New test file:

- `tests/test_hidden_regime_forecasting.py`

Coverage includes:

- hidden-regime suite construction
- sequence-context / expected-transform binding for the new task IDs
- end-to-end laminated benchmark result shape and forecasting metadata

## Design Notes

- The hidden family stays inside the current Phase 8 transform-routing substrate.
  It does not create a second standalone symbolic simulator.
- The benchmark uses hidden-by-default scenarios by setting packet
  `context_bit=None`, so the regime must be inferred from sequence evidence.
- The benchmark still benefits from the explicit forecast readout added in the
  prior pass because `forecast_metrics` and `intervention_payoff_trend` are
  already emitted at the slice boundary.
- `visible` remains useful as an ablation because it separates hidden-regime
  inference difficulty from the rest of the routing substrate.

## Validation

Focused tests:

- `python -m unittest tests.test_lamination tests.test_hidden_regime_forecasting tests.test_phase8_lamination`

Result:

- 12 tests passed

Smoke check:

- `python -m scripts.evaluate_hidden_regime_forecasting -b HR1 -t task_a --observable hidden --reg real --budget 4 --safety-limit 8 --no-output --compact`

Observed compact output confirmed the new runner executes and reports laminated
slice results plus intervention payoff trend.

## Working Interpretation

This does not yet make REAL a general large-scale prediction system. What it
does provide is a dedicated benchmark family where the current laminated
architecture can be measured on:

- symbolic hidden-state inference
- explicit transform forecasting
- policy-conditioned slice adaptation
- interpretable slow-layer intervention effects

That makes it a better near-term research target than fixed-mode laminated runs
or prematurely broad next-token style tasks.
