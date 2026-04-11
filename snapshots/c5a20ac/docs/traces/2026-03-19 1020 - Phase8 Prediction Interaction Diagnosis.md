# 2026-03-19 1020 - Phase8 Prediction Interaction Diagnosis

## Summary

Added a dedicated prediction-interaction probe to compare warm transfer with the selector's prediction term enabled vs disabled while leaving recognition enabled. The goal was to answer a specific question left open by the first expectation-binding pass:

- are prediction terms merely present in traces?
- or do they actually alter source decisions?

The answer is: **yes, prediction can alter source decisions, but not in a clean early-adaptation way yet.**

## Code Changes

- Updated [phase8/selector.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/selector.py)
  - made prediction weights explicit with:
    - `prediction_delta_bonus`
    - `prediction_coherence_bonus`
- Added [scripts/diagnose_phase8_transfer_prediction_interaction.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/scripts/diagnose_phase8_transfer_prediction_interaction.py)
  - compares prediction-enabled vs prediction-disabled warm transfer
  - records earliest source-route decisions
  - records chosen and competitor breakdowns including:
    - `prediction_delta_term`
    - `prediction_coherence_term`
    - `prediction_effective_confidence_term`
- Added [tests/test_phase8_transfer_prediction_interaction.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/tests/test_phase8_transfer_prediction_interaction.py)

## Results

### Validation

- `python -m unittest tests.test_phase8_transfer_prediction_interaction tests.test_phase8_expectation tests.test_phase8_recognition tests.test_transfer_adaptation_recognition tests.test_phase8_transfer_selector_interaction tests.test_phase8_transfer_recognition_probe tests.test_real_core`

### Warm A -> B Transfer

#### Seed 13

- prediction is active on every source-route cycle in the transfer window
  - first active source cycle: `25`
  - active cycles: `25-42`
- prediction vs no-prediction diverges only later
  - first divergence cycle: `34`
  - divergence cycles: `34-42`
- early prediction terms are very small
  - usually around `1e-4` to `1e-3` in score contribution
- effect on outcome is mixed:
  - prediction enabled: `4` exact, `0.5278` mean bit accuracy
  - prediction disabled: `3` exact, `0.4444` mean bit accuracy
  - but early-window exact rate is slightly worse with prediction enabled:
    - enabled: `0.25`
    - disabled: `0.375`

#### Seed 23

- prediction is again active on every source-route cycle in the transfer window
  - first active source cycle: `25`
  - active cycles: `25-42`
- no source decision divergence at all
  - divergence count: `0`
- outcome is slightly better with prediction enabled:
  - prediction enabled: `3` exact, `0.5` mean bit accuracy
  - prediction disabled: `2` exact, `0.4444` mean bit accuracy
- early-window adaptation metrics are unchanged

## Interpretation

This narrows the current Phase 8 prediction story:

- prediction is not merely decorative anymore
- it can influence source decisions
- but its influence is currently:
  - very small
  - late when it matters on seed `13`
  - absent on some seeds even though prediction remains active

So the bottleneck is no longer "does prediction exist?" The new bottleneck is closer to:

- prediction terms are too weak or too redundant to reliably reshape the early transfer window
- when they do matter, they currently matter mostly in later near-tie branch decisions

## Next Step

The best next move is not to make prediction globally stronger. It is to make it **more distinct** from the existing selector evidence.

The cleanest candidate is to let prediction express something the current selector does not already score directly, such as:

- expected branch-switch value under hidden-task uncertainty
- expected stale-family risk
- expected mismatch cost over the next few routed packets rather than only the current local action
