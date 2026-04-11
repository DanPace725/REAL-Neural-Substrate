# 2026-03-18 2231 - Source Transform Recognition Transfer Probe

## Summary

Narrow Phase 8 follow-up to the earlier transfer-recognition work:

- kept the route-recognition path unchanged
- strengthened source-side transform-pattern use in `Phase8Selector`
- updated the warm-transfer probe so it measures transfer-only entries instead of mixing carryover history with the live transfer run
- added explicit source-transform timing stats

The main result is mixed but useful:

- source-side transform recognition is present on the first source route decision of the transfer phase
- but enabling the current recognition bias still does not improve the old `cvt1_task_a_stage1 -> cvt1_task_b_stage1` warm-transfer slice

## Code Changes

### Phase 8 selector

In `phase8/selector.py`:

- added `recognition_transform_bonus` as an explicit selector knob
- extended `_recognized_transform_bias(...)` so a recognized `context_transform_attractor` can bias the underlying base `(neighbor, transform)` action signature, not only an exact context key match

This keeps the change narrow and source-local:

- no change to latent capability control
- no change to topology growth logic
- no new global controller

### Transfer probe

In `scripts/probe_phase8_transfer_recognition.py`:

- bias toggling now covers both route and transform recognition bonuses
- recognition stats now inspect transfer-only entries by skipping loaded carryover entries
- added source-transform timing metrics:
  - `recognized_source_transform_entry_count`
  - `recognized_source_transform_cycles`
  - `first_source_route_cycle`
  - `first_recognized_source_transform_cycle`
  - `recognized_source_transform_on_first_source_route`

### Tests

- added a focused selector regression showing that `context_transform_attractor` recognition can bias the base transform action even when no exact context-specific action key is being targeted
- updated the transfer probe regression to check source-transform timing against the first source route cycle

## Probe Result

Command:

```text
python -m scripts.probe_phase8_transfer_recognition --seed 13
```

Key result for the enabled variant:

- `source_route_entry_count = 5`
- `recognized_source_transform_entry_count = 5`
- `first_source_route_cycle = 34`
- `first_recognized_source_transform_cycle = 34`
- `recognized_source_transform_on_first_source_route = true`

So the source-transform recognition seam is now active immediately when the source begins transfer routing.

However, the same probe still shows worse task performance with the current recognition bias enabled:

- bias on: `exact_matches = 9`, `mean_bit_accuracy = 0.5833`
- bias off: `exact_matches = 12`, `mean_bit_accuracy = 0.75`

## Interpretation

This is a useful narrowing result.

The bottleneck for this older transfer slice is no longer:

- "does the source have access to transform-pattern recognition at transfer time?"

The answer there is now yes.

The remaining question is:

- "is the current transform-recognition bias too blunt, too strong, or coupled to the wrong selector competition dynamics?"

In other words, recognition availability is no longer the limiting issue in this probe; policy integration quality is.

## Validation

```text
python -m unittest tests.test_phase8_recognition tests.test_phase8_transfer_recognition_probe tests.test_real_core
python -m scripts.probe_phase8_transfer_recognition --seed 13
```
