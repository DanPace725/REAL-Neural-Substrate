# 2026-03-18 2243 - Transfer Selector Interaction Diagnosis

## Summary

Added a read-only selector breakdown path and a narrow warm-transfer diagnostic so we can inspect how recognition interacts with existing source transform-selection terms in the old `cvt1_task_a_stage1 -> cvt1_task_b_stage1` transfer slice.

This was not a tuning pass. The goal was to answer:

- when recognition changes the source decision, what other terms is it competing with?
- is recognition being drowned out, or is it winning the wrong comparisons?

## Code Changes

### Selector instrumentation

In `phase8/selector.py`:

- added `capture_route_breakdowns`
- added `latest_route_score_breakdowns()`
- added `debug_route_score_breakdown(...)`
- extended `_score_route(...)` with an optional breakdown path that records compact per-term contributions while preserving the original scoring behavior

The breakdown includes the terms that matter most for transfer debugging:

- `recognition_transform_term`
- `task_transform_bonus_term`
- `history_transform_term`
- `feedback_credit_term`
- `context_feedback_credit_term`
- `competition_penalty_term`
- `competition_bonus_term`
- `identity_penalty_term`
- `hidden_wrong_family_penalty_term`
- `cost_penalty_term`

### New probe

Added `scripts/diagnose_phase8_transfer_selector_interaction.py`.

It:

- runs the warm `A -> B` transfer slice with recognition bias on and off
- captures the source selector's live route-score breakdowns during transfer cycles
- records the chosen action, the top competitor, and the key terms for each source route decision

### Test

Added `tests/test_phase8_transfer_selector_interaction.py` to keep the diagnostic runnable.

## Result

Command:

```text
python -m scripts.diagnose_phase8_transfer_selector_interaction --seed 13
```

High-level findings:

- source route decisions compared across enabled/disabled variants: `18`
- cycles where the chosen source action changed: `30, 39, 40, 41`
- cycles where the enabled variant had a nonzero `recognition_transform_term`: `15`
- average nonzero `recognition_transform_term`: about `0.0299`
- maximum observed `recognition_transform_term`: about `0.0356`

The important pattern is that recognition is not huge, but it is large enough to win close comparisons.

Example at cycle `30`:

- recognition on chose `route_transform:n1:xor_mask_1010`
- recognition off chose `route_transform:n2:rotate_left_1`
- enabled chosen total: `0.5726`
- disabled chosen alternative total: `0.5661`
- enabled `recognition_transform_term`: `0.0331`

So on that cycle, the recognition term is roughly the whole decision margin.

Late-run cycles `39-41` show a similar shape:

- recognition on stays with an XOR family action on `n1`
- recognition off chooses `xor_mask_0101`
- the recognition term remains positive on the enabled side while feedback/context-credit terms are basically absent

## Interpretation

The current transform-recognition path is not being ignored.

Instead, it is doing exactly enough to tip near-tie source decisions toward recognized transform families, including stale carried families. In this transfer slice that appears harmful.

So the problem is less:

- "recognition is too weak to matter"

and more:

- "recognition currently has no freshness or contradiction discount when transform evidence is ambiguous but local feedback has not yet strongly disconfirmed the old family"

This also explains why the probe showed:

- source transform recognition is available on the first source route decision
- transfer performance still gets worse with the current bias

Recognition is arriving in time, but the selector is integrating it too bluntly in a few decisive cycles.

## Likely Next Step

The next narrow tuning step should probably not remove transform recognition. Instead it should make the bias conditional, for example:

- discount transform recognition when no positive feedback/context-credit supports the recognized family yet
- discount transform recognition when its advantage over the top competitor is mostly recognition-only
- decay recognition influence faster during transfer-hidden adaptation unless local feedback starts to align

## Validation

```text
python -m unittest tests.test_phase8_transfer_selector_interaction tests.test_phase8_recognition tests.test_phase8_transfer_recognition_probe tests.test_real_core
python -m scripts.diagnose_phase8_transfer_selector_interaction --seed 13
```
