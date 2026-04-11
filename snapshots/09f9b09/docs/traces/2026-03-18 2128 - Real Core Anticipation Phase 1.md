# 2026-03-18 2128 - Real Core Anticipation Phase 1

Author: GPT-5 Codex

## Why

The current generalized REAL loop records retrospective adaptation well, but it does not make local recognition and prediction first-class parts of the reusable core. Phase 8 has accumulated several predictive-ish signals, yet they live as domain-specific observation features rather than as an explicit generalized anticipation mechanism.

This first implementation pass is intentionally narrow. The goal is to make anticipation representable, serializable, and inspectable inside `real_core` without forcing all selectors or domains to adopt new behavior immediately.

## What Changed

### New core anticipation types

Added two optional reusable types in `real_core/types.py`:

- `LocalPrediction`
- `PredictionError`

`CycleEntry` now carries optional:

- `prediction`
- `prediction_error`

This keeps anticipation attached to the same inspectable episodic trace already used for coherence, delta, and carryover.

### New optional core protocol

Added `ExpectationModel` to `real_core/interfaces.py`.

It provides two hooks:

- `predict(...)` for action-local expectations before selection/execution
- `compare(...)` for local prediction error after outcome is observed

This protocol is optional. Existing domains and experiments continue to run unchanged when no expectation model is supplied.

### Engine integration

`RealCoreEngine` now accepts an optional `expectation_model`.

When present, the engine:

1. computes local action expectations before selection
2. stores a compact anticipation summary in `CycleEntry.state_before`
3. records the selected action's `prediction`
4. records post-action `prediction_error`

When absent, engine behavior remains effectively unchanged.

### Carryover / persistence

Session-state serialization now preserves optional anticipation fields, so predictive traces can survive export/import and become part of broader carryover analysis.

## What Did Not Change

This pass does **not** yet:

- alter the selector protocol
- let current-cycle predictions directly bias action selection
- introduce a generalized recognition interface
- change Phase 8 behavior by default

That boundary is deliberate. The repo now has a reusable place to put anticipatory state before we decide how strongly anticipation should influence control.

## Validation

Ran:

- `python -m unittest tests.test_real_core`

Added focused tests for:

- engine recording of optional predictions and prediction errors
- session-state round-trip of anticipation fields

## Interpretation

This is a representational foundation, not a finished predictive REAL loop.

The main result is that `real_core` can now express:

- what was expected
- what actually happened
- how wrong the expectation was

without forcing a new control policy onto every existing experiment.

## Likely Next Step

The next clean architectural step is to add an optional selector-facing anticipation path, probably in one of two forms:

- a selector context input that exposes current-cycle predictions directly
- a lightweight anticipatory selector that can combine historical delta, expected delta, uncertainty, and cost

That should happen only after we decide how much of `recognize -> predict -> select` belongs in reusable core interfaces versus domain bindings.
