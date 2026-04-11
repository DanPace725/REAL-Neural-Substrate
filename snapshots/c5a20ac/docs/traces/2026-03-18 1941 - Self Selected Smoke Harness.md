# 2026-03-18 1941 - Self Selected Smoke Harness

**Author:** GPT-5 Codex

## Why This Change

The new self-selected capability runtime is architecturally important, but the full ceiling suite is expensive enough that it slows down the first feedback loop.

A smaller probe was needed to answer a narrower question first:

- does `self-selected` recruit latent capability on ambiguity-heavy points at all
- does it stay quiet or mostly quiet on an easy visible point
- does it land anywhere near the current fixed-policy oracle on a tiny representative set

## Code Changes

Added a lightweight harness in `scripts/compare_self_selected_smoke.py`.

It runs only REAL methods:

- `fixed-visible`
- `fixed-latent`
- `growth-visible`
- `growth-latent`
- `self-selected`

on a small selected subset of ceiling points, defaulting to:

- `A1`
- `B2`
- `C3`

for `task_a` and seed `13`.

The harness reports:

- per-point fixed-policy oracle
- `self-selected` oracle gap
- source capability timeline preview/tail
- source latent and growth recruitment cycles

This gives a much faster read than the full ceiling sweep while still grounding the result in the same benchmark family structure.

`pyproject.toml` now exposes this as `real-self-selected-smoke`.

## Validation

Focused test:

- `python -m unittest tests.test_ceiling_benchmarks.TestCeilingBenchmarkSuite.test_self_selected_lightweight_harness_returns_oracle_gap`

Smoke run:

- `python -m scripts.compare_self_selected_smoke --benchmarks A1 B2 C3 --tasks task_a --seeds 13`

## First Read

Compact result from the smoke run:

- `A1`: oracle `fixed-visible`, self-selected gap `0.2778`, self-selected exact rate `0.3889`, latent recruited at cycle `6`, growth recruited at cycle `13`
- `B2`: oracle `fixed-visible`, self-selected gap `0.0370`, self-selected exact rate `0.6852`, latent recruited at cycle `11`, growth recruited at cycle `19`
- `C3`: oracle `fixed-latent`, self-selected gap `0.3519`, self-selected exact rate `0.2500`, latent recruited at cycle `8`, growth recruited at cycles `18, 112, 119`

Aggregate:

- mean self-selected oracle gap: `0.2222`
- by family:
  - `A`: `0.2778`
  - `B`: `0.0370`
  - `C`: `0.3519`

## Current Interpretation

This is a useful first signal even though the performance is not yet good enough.

- The self-selected controller is not dead; it is visibly recruiting latent capability without external family labels.
- The `B2` result is encouraging because the gap to the fixed-policy oracle is already small.
- `A1` suggests over-recruitment or mistimed recruitment on an easy visible problem.
- `C3` suggests the controller is discovering that latent is needed, but too late or too noisily, and growth pressure may still be mistimed once ambiguity is already hurting throughput.

So the next tuning target should not be "make the benchmark bigger." It should be:

1. suppress earlier latent recruitment on easy visible points
2. accelerate latent commitment or reduce its startup drag on `C3`
3. delay growth until latent stabilization is actually useful on ambiguous points
