# 2026-03-19 0942 - Transfer Adaptation Metrics and Recognition Probe

## Summary

Extended the transfer harness to expose early adaptation and anticipation visibility directly, then added a small recognition-on vs recognition-off probe on top of it.

This was meant to answer the broader question:

- can we actually see recognition or prediction firing in transfer?
- and do the harder transfer slices show any early benefit from it?

## Code Changes

### `compare_task_transfer.py`

Extended `transfer_metrics(...)` with:

- `first_exact_match_example`
- `first_exact_match_cycle`
- `first_expected_transform_example`
- `first_expected_transform_cycle`
- `first_sustained_expected_transform_example`
- `first_sustained_expected_transform_cycle`
- `early_window_examples`
- `early_window_exact_rate`
- `early_window_bit_accuracy`
- `early_window_wrong_transform_family`
- `early_window_wrong_transform_family_rate`
- `anticipation`

The `anticipation` block currently reports:

- route entry count
- recognized route counts
- recognized source-route counts
- recognized source-transform counts
- predicted route counts
- first recognition / prediction cycles

It also extends `aggregate_transfer(...)` with compact averages for some of the new early-adaptation and anticipation fields.

### New probe

Added `scripts/probe_transfer_adaptation_recognition.py`.

It compares recognition bias enabled vs disabled for a given train/transfer pair and seed list, using the new early-adaptation metrics and anticipation visibility.

### Tests

Added:

- `tests/test_compare_task_transfer_metrics.py`
- `tests/test_transfer_adaptation_recognition.py`

## Validation

```text
python -m unittest tests.test_compare_task_transfer_metrics tests.test_transfer_adaptation_recognition tests.test_phase8_recognition tests.test_phase8_transfer_selector_interaction tests.test_phase8_transfer_recognition_probe tests.test_real_core
```

## Probe Readout

### A -> B over seeds 13 / 23 / 37

Command:

```text
python -m scripts.probe_transfer_adaptation_recognition --train-scenario cvt1_task_a_stage1 --transfer-scenario cvt1_task_b_stage1 --seeds 13 23 37
```

Observed:

- recognition clearly fires in transfer
  - seed `13`: `recognized_source_transform_entry_count = 14`, first source transform recognition at cycle `25`
  - seed `23`: `recognized_source_transform_entry_count = 4`, first source transform recognition at cycle `25`
  - seed `37`: `recognized_source_transform_entry_count = 15`, first source transform recognition at cycle `25`
- prediction does **not** fire in Phase 8 yet
  - `predicted_route_entry_count = 0` in all tested runs

Early-adaptation examples:

- seed `13`: first exact match at example `1`, first sustained expected-transform streak begins at example `7`
- seed `23`: first exact match at example `8`, no sustained expected-transform streak
- seed `37`: first exact match at example `1`, first sustained expected-transform streak begins at example `7`

But the enabled vs disabled comparison remained identical on all tested seeds:

- no change in final exact matches
- no change in early-window exact rate
- no change in early wrong-transform-family rate

### C -> A, seed 51

Command:

```text
python -m scripts.probe_transfer_adaptation_recognition --train-scenario cvt1_task_c_stage1 --transfer-scenario cvt1_task_a_stage1 --seeds 51
```

Observed:

- recognition again clearly fires:
  - `recognized_source_transform_entry_count = 17`
  - first source transform recognition at cycle `25`
- prediction still does not fire:
  - `predicted_route_entry_count = 0`
- early adaptation remained identical between enabled and disabled:
  - same first exact match example
  - same first expected-transform example
  - same early-window exact rate
  - same early wrong-family rate
- the small final dip from the widened sweep remained:
  - `delta_exact_matches = -1`
  - `delta_mean_bit_accuracy = -0.0556`

## Interpretation

This gives a cleaner broader-context read:

- recognition is now visible and measurably active in transfer
- prediction is still absent in Phase 8 because the expectation path is not wired into node behavior yet
- the new early metrics suggest recognition is not currently creating a strong early adaptation benefit on these transfer slices
- in the one residual negative case, the difference shows up later than the early adaptation window, which matches the earlier diagnosis that it is not a simple source-side recognition problem

## Practical Takeaway

We now have a better measurement surface for the broader architecture discussion:

- `real_core` supports recognition and prediction structurally
- Phase 8 currently demonstrates recognition firing
- Phase 8 does not yet demonstrate prediction firing
- and the harder transfer tests are now instrumented well enough to show whether a future predictive binding actually changes early adaptation
