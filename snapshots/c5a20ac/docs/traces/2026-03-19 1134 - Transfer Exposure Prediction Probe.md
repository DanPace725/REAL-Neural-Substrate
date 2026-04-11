# 2026-03-19 1134 - Transfer Exposure Prediction Probe

## Context

We already had:

- transfer-oriented early-adaptation metrics in `compare_task_transfer.py`
- repeated-experience probes for ceiling benchmarks
- lightweight anticipation summaries for runtime slack and repeated exposure

What we did not yet have was a small transfer-focused exposure probe that could ask:

- if the transfer stream itself is repeated, does prediction strengthen?
- do those changes show up before exact-match improvements?

This was also a good place to broaden transfer reporting without touching Phase 8 mechanics or regressing C-family context handling.

## Changes

Added a small reusable helper in `scripts/repeated_signal_scenarios.py` for:

- ordered signal events
- repeated signal-schedule expansion
- pass-span calculation
- expected-example counting for explicit signal scenarios

Updated `scripts/evaluate_experience_extension.py` to use that helper instead of carrying its own private repeat logic.

Updated `scripts/compare_transfer_matrix.py` aggregate output to surface a few prediction-facing summary fields:

- average predicted route entry counts
- average predicted source-route entry counts
- average first predicted source-route cycle

Added `scripts/probe_transfer_exposure_prediction.py`, which:

- trains on one transfer source scenario
- applies configurable carryover into a transfer scenario
- repeats only the transfer stream
- reports overall transfer metrics, anticipation summaries, and per-pass adaptation/prediction summaries

Added focused structural tests:

- `tests/test_compare_transfer_matrix.py`
- `tests/test_transfer_exposure_prediction.py`

## Probe Result

Ran:

`python -m scripts.probe_transfer_exposure_prediction --train-scenario cvt1_task_a_stage1 --transfer-scenario cvt1_task_b_stage1 --seeds 13 --repeat-counts 1 2 --carryover-mode full`

Key result for warm `A -> B`, seed `13`, full carryover:

- repeat `1x`: exact-match rate `0.2222`, mean bit accuracy `0.5278`
- repeat `2x`: exact-match rate `0.2222`, mean bit accuracy `0.5139`
- final-pass exact-match rate stayed flat at `0.2222`

Prediction did move:

- mean source prediction confidence: `0.2479 -> 0.2735`
- delta mean source prediction confidence: `+0.0256`
- mean source expected delta: `0.0390 -> 0.0579`
- predicted source-route entry count: `20 -> 23`

So on this slice, repeated transfer exposure increased predictive confidence without yet producing an exact-match gain.

## Interpretation

This is a useful intermediate result:

- prediction is not inert during repeated transfer exposure
- extra transfer experience can deepen predictive commitment even when task accuracy is still stuck
- that makes transfer exposure a better place to look for anticipatory benefit than idle runtime

It also gives us a better diagnostic ladder for future checks:

1. does exposure change prediction?
2. does changed prediction alter early adaptation?
3. does early adaptation eventually change final accuracy?

At least on this first probe, step 1 is now clearly yes.
