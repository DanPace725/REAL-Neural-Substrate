# 2026-03-18 2207 - Phase8 Transfer Recognition Probe

Author: GPT-5 Codex

## Why

After the synthetic route-bias probe succeeded, the next question was whether the same mechanism mattered at all in the older A->B warm-transfer path.

This probe kept the comparison intentionally narrow:

- same training carryover
- same warm transfer scenario
- same seed
- same system
- only difference: recognition route bias enabled vs. neutralized

## What Changed

Added:

- `scripts/probe_phase8_transfer_recognition.py`
- `tests/test_phase8_transfer_recognition_probe.py`

The probe:

1. trains on `cvt1_task_a_stage1`
2. saves memory carryover
3. runs warm transfer on `cvt1_task_b_stage1`
4. compares the transfer run with recognition route bias on vs. off
5. records both transfer metrics and route-recognition usage statistics

## Validation

Ran:

- `python -m unittest tests.test_phase8_transfer_recognition_probe tests.test_phase8_recognition_probe tests.test_phase8_recognition tests.test_real_core`
- `python -m scripts.probe_phase8_transfer_recognition --seed 13`

## Result

For seed `13`, the result was a clean null effect:

- with recognition bias:
  - `exact_matches = 12`
  - `mean_bit_accuracy = 0.75`
  - `best_rolling_exact_rate = 0.75`
  - `recognized_route_entry_count = 0`

- without recognition bias:
  - identical metrics
  - `recognized_route_entry_count = 0`

So the delta was effectively zero across all measured fields.

## Interpretation

This is a useful negative result.

It does **not** mean the recognition route bias is useless. It means that in this older warm-transfer path, the route recognizer is not yet activating on real transfer traffic, so there is nothing for the bias to act on.

In other words:

- the synthetic micro-case proved the path works
- the transfer probe shows the path is not yet ecologically engaged

That strongly suggests the next issue is **recognition availability**, not selector weighting.

## Likely Next Step

The next good move is to inspect why transfer routing is not producing recognized route-pattern matches.

The most likely places to check are:

- whether the promoted Phase 8 route patterns line up with the dimensions available at transfer-time recognition
- whether transfer-time route behavior is simply not revisiting the same route-pattern shapes strongly enough
- whether transform-heavy transfer errors need transform-aware pattern recognition before route-pattern recognition becomes relevant
