# 2026-03-19 1036 - Distinct Prediction Stale Family Pass

## Summary

Tried to make Phase 8 prediction more distinct by adding a stale-family risk signal based on:

- recent transform commitment in local history
- current hidden-task transform alignment
- alternative transform alignment
- transform debt / context debt

The intent was to give prediction a job that the current selector does not already score directly: anticipating that the node is still committed to an older transform family even though local evidence has shifted.

## Code Changes

- Updated [phase8/expectation.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/expectation.py)
  - added `ROUTE_TRANSFORMS`
  - added `_recent_transform_commitment(...)`
  - added `_transform_alignment(...)`
  - added `_stale_family_risk(...)`
  - prediction metadata now includes `stale_family_risk`
  - expected delta now includes a small stale-family risk discount
- Updated [phase8/selector.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/selector.py)
  - added `prediction_stale_family_penalty`
  - route breakdowns now expose `prediction_stale_family_penalty_term`
- Updated [scripts/diagnose_phase8_transfer_prediction_interaction.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/scripts/diagnose_phase8_transfer_prediction_interaction.py)
  - includes the stale-family prediction term in compact breakdowns
- Updated tests:
  - [tests/test_phase8_expectation.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/tests/test_phase8_expectation.py)
  - [tests/test_phase8_transfer_prediction_interaction.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/tests/test_phase8_transfer_prediction_interaction.py)

## Results

### Validation

- `python -m unittest tests.test_phase8_expectation tests.test_phase8_transfer_prediction_interaction tests.test_phase8_recognition tests.test_transfer_adaptation_recognition tests.test_real_core`

### Unit-Level Result

The new stale-family risk signal works in the targeted unit case:

- repeated recent commitment to `xor_mask_1010`
- current hidden-task evidence favoring `rotate_left_1`
- added transform/context debt on the stale family

In that controlled case:

- preferred transform stale-family risk stays low
- stale transform stale-family risk rises above `0.5`

### Transfer Probe Result

On the real `A -> B` warm-transfer slice for seeds `13` and `23`, the stale-family penalty does **not** activate in the chosen or top-competitor source decisions.

Observed maxima:

- seed `13`: max absolute `prediction_stale_family_penalty_term = 0.0`
- seed `23`: max absolute `prediction_stale_family_penalty_term = 0.0`

So the broader probe behavior is unchanged from the prior diagnosis:

- prediction is active from the start of transfer
- source divergences still begin late on seed `13`
- seed `23` still shows no source divergence

## Interpretation

This is a useful negative result.

The architecture now supports a more distinct predictive signal, but this specific transfer slice does not actually instantiate the stale-family condition strongly enough for that signal to matter in the source choices we are inspecting.

That suggests either:

1. `A -> B` is not the right slice for stale-family-risk diagnostics
2. the more relevant distinct signal is not stale family per se, but something closer to branch-switch value or expected hidden-context resolution value

## Next Step

If we keep pushing on distinct prediction, the next better candidate is probably:

- expected branch-switch value under hidden-task ambiguity

That would be more likely to activate in the late near-tie branch decisions we already know prediction can influence.
