# 2026-03-18 2254 - Evidence Confirmed Transform Recognition

## Summary

Implemented a narrow evidence-confirmation gate on Phase 8 source transform recognition.

The intent was to keep recognition available as a local prior while preventing it from steering source decisions when there is no current local evidence supporting the recognized transform family.

## Change

In `phase8/selector.py`:

- added `_transform_recognition_confirmation(...)`
- scaled `recognition_transform_term` by local confirming evidence instead of letting recognition act as a flat bonus
- exposed `recognition_transform_confirmation_term` in the selector breakdown diagnostic

The confirmation signal is built only from already-local evidence:

- positive:
  - `history_transform_evidence`
  - `feedback_credit`
  - `context_feedback_credit`
  - branch/context credit signals
- negative:
  - `feedback_debt`
  - `context_feedback_debt`
  - branch/context debt pressure

This keeps the selector grounded in local confirmation rather than recency alone.

## Regression Coverage

Added a focused test in `tests/test_phase8_recognition.py`:

- without confirming evidence, transform recognition contributes `0.0`
- with confirming evidence, transform recognition becomes positive

## Result

Validation commands:

```text
python -m unittest tests.test_phase8_recognition tests.test_phase8_transfer_selector_interaction tests.test_phase8_transfer_recognition_probe tests.test_real_core
python -m scripts.diagnose_phase8_transfer_selector_interaction --seed 13
python -m scripts.probe_phase8_transfer_recognition --seed 13
```

Observed behavior on seed `13`:

- cycles where enabled and disabled source actions differed: none
- early source transfer cycles `25-27`: `recognition_transform_term = 0.0`, `recognition_transform_confirmation_term = 0.0`
- recognition becomes active only once local evidence appears:
  - cycle `28`: confirmation about `0.6206`, recognition term about `0.0234`
  - cycle `29`: confirmation about `0.8333`, recognition term about `0.0337`

Warm-transfer probe outcome:

- recognition bias on: `exact_matches = 13`, `mean_bit_accuracy = 0.8056`
- recognition bias off: `exact_matches = 13`, `mean_bit_accuracy = 0.8056`

So the evidence-confirmation gate removed the harmful recognition-only divergence from the previous probe without suppressing recognition entirely.

## Interpretation

This is a better integration shape than a flat recognition bonus.

Recognition now behaves more like:

- "I recognize this family"
- "but I only get influence if current local evidence begins to confirm it"

That is closer to the biological intuition we were aiming for and avoids a simple recency-style stale-memory bias.

## Next Step

The next useful check is whether the same confirmation-gated recognition helps or stays neutral on a second transfer seed or a slightly different transfer slice, before we propagate the pattern into broader Phase 8 capability logic.
