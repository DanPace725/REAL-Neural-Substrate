# 2026-03-18 2138 - Real Core Recognition Phase 3

Author: GPT-5 Codex

## Why

After Phase 2, `real_core` could use prediction proactively, but prediction was still doing too much conceptual work. It implicitly carried both:

- recognition of the current local problem shape
- forward expectation about the consequence of action

Those should be separable in the generalized algorithm.

This pass introduces recognition as its own first-class reusable seam so the core can express:

- "what does this resemble?"
- separately from
- "what do I expect will happen if I do this?"

## What Changed

### New recognition types

Added to `real_core/types.py`:

- `RecognitionMatch`
- `RecognitionState`

`CycleEntry` now carries optional `recognition`, and `SelectionContext` now carries optional `recognition` as well.

This means recognition is now inspectable in the same generalized trace structure as prediction and prediction error.

### New recognition protocol

Added `RecognitionModel` to `real_core/interfaces.py`.

It provides:

- `recognize(state_before, history, prior_coherence, substrate)`

This is optional and non-breaking. Domains that do not provide recognition continue to run unchanged.

### Prediction can now consume recognition

`ExpectationModel.predict(...)` now supports an optional `recognition` input.

The engine inspects the expectation model signature and only passes `recognition` when the model accepts it, preserving backward compatibility with older expectation-model implementations.

### Engine integration

`RealCoreEngine` now:

1. computes optional recognition before prediction
2. records a recognition summary in `state_before`
3. passes recognition into prediction when supported
4. includes recognition in `SelectionContext`
5. records recognition directly in `CycleEntry`

This is the first version of a generalized:

- `sense -> recognize -> predict -> select -> execute -> compare -> consolidate`

pipeline in code rather than only in docs.

### Persistence

Session-state serialization now preserves recognition fields, including matched labels and recognition metadata.

## What Did Not Change

This still does **not** add a canonical built-in recognizer for all domains.

That is intentional. The core now has a reusable place for recognition, but we have not yet declared one universal recognition mechanism to be correct for every REAL instantiation.

Phase 8 also does not automatically consume this path yet.

## Validation

Ran:

- `python -m unittest tests.test_real_core`

Added focused tests for:

- engine recording recognition
- recognition flowing into prediction
- selection context carrying recognition
- session-state round-trip of recognition fields

## Interpretation

This pass matters more conceptually than it does in line count.

Before:

- prediction implicitly stood in for problem-shape sensing

After:

- recognition can identify resemblance or familiarity
- prediction can estimate consequences conditioned on that recognition
- selectors can see both

That is a better generalization of how memory should shape action in REAL.

## Likely Next Step

The next strong move is to add one modest reusable recognizer implementation in `real_core`, probably pattern- or substrate-based, so the new interface is not only structural but also runnable outside tests.
