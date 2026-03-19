# 2026-03-18 2204 - Phase8 Recognition Bias Probe

Author: GPT-5 Codex

## Why

After adding a small recognition-driven route bias to `Phase8Selector`, the next question was whether that path could be demonstrated in a lightweight way without running the larger benchmark harnesses.

This probe was intentionally tiny:

- one route-pattern recognition case
- one route-choice bias case

The goal was not task performance, but proof that the new local chain is live:

- substrate pattern
- recognition
- control bias

## What Changed

Added:

- `scripts/probe_phase8_recognition_bias.py`
- `tests/test_phase8_recognition_probe.py`

The probe runs two scenarios:

1. **promotion recognition probe**
   Seeds route history, consolidates it into a substrate pattern, then checks whether a later cycle records recognition.

2. **route bias probe**
   Seeds a route-attractor pattern favoring one neighbor, compares selector choice without recognition context vs. with explicit recognition context, and reports whether the route flips.

## Validation

Ran:

- `python -m unittest tests.test_phase8_recognition_probe tests.test_phase8_recognition tests.test_real_core`
- `python -m scripts.probe_phase8_recognition_bias --seed 17`

## Result

Probe output for seed `17`:

- promotion recognition probe:
  - `pattern_count = 1`
  - `recognized = true`
  - `recognition_confidence = 0.4875`
  - `dims_source = history`
  - matched source: `route_attractor`

- route bias probe:
  - baseline action: `route:n1`
  - recognition-context action: `route:n2`
  - `route_flipped = true`

## Interpretation

This is a useful result even though it is small and synthetic.

It shows that Phase 8 now has a functioning local anticipatory chain:

- consolidation leaves behind durable route structure
- the recognizer can read that structure later
- the selector can use the recognition as a small route prior

The recognition confidence in the promotion probe is moderate rather than high, which is probably the right outcome for this early implementation. It is enough to demonstrate recognition without pretending the system already has a mature broad-scope familiarity signal.

## Likely Next Step

The next best move is a slightly more ecological probe:

- repeated-experience or transfer-adaptation setting
- compare one narrow metric with recognition bias on vs. effectively absent

That would tell us whether this new route prior helps outside the hand-seeded micro-case.
