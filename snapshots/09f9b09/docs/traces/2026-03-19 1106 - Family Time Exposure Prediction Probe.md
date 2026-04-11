# 2026-03-19 1106 - Family Time Exposure Prediction Probe

## Summary

Ran a lightweight family-spanning probe over:

- `A1`
- `B2`
- `C3`

using `self-selected` on seed `13`, comparing:

- extra idle runtime (`1.0x / 1.5x / 2.0x`)
- repeated exposure (`1x / 2x / 3x`)

The goal was not a full benchmark sweep. It was to check whether the newer prediction path shows different behavior under more time vs more experience across representative A/B/C task shapes.

## Harness

Added:

- [scripts/benchmark_anticipation_metrics.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/scripts/benchmark_anticipation_metrics.py)
- [scripts/probe_time_exposure_prediction.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/scripts/probe_time_exposure_prediction.py)

Updated:

- [scripts/evaluate_runtime_slack.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/scripts/evaluate_runtime_slack.py)
- [scripts/evaluate_experience_extension.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/scripts/evaluate_experience_extension.py)

Key anticipation fields recorded:

- `predicted_route_entry_count`
- `predicted_source_route_entry_count`
- `first_predicted_route_cycle`
- `first_predicted_source_route_cycle`
- `mean_source_prediction_confidence`
- `mean_source_expected_delta`
- `mean_source_stale_family_risk`

## Validation

- `python -m unittest tests.test_runtime_slack tests.test_experience_extension tests.test_time_exposure_prediction_probe tests.test_phase8_expectation tests.test_transfer_adaptation_recognition tests.test_real_core`
- `python -m scripts.probe_time_exposure_prediction --benchmarks A1 B2 C3 --tasks task_a --methods self-selected --seeds 13 --cycle-multipliers 1.0 1.5 2.0 --repeat-counts 1 2 3`

## Results

### Runtime Slack

Across `A1`, `B2`, and `C3`, extra idle runtime produced no improvement in exact-match rate or best rolling exact rate.

- `A1`: unchanged at `0.0556`
- `B2`: unchanged at `0.5648`
- `C3`: unchanged at `0.2222`

Prediction remained present in all runtime-slack runs:

- source prediction entry rate stayed at `1.0`
- first source prediction cycle stayed at `1` or `2`
- confidence and expected-delta means stayed nearly unchanged

Interpretation:

- more empty time still does not help
- prediction is already active without extra slack
- extra slack does not seem to improve or deepen the current predictive process on these family points

### Repeated Exposure

Repeated exposure helped all three family representatives, but unevenly.

#### A1

- overall exact-match rate:
  - `1x`: `0.0556`
  - `2x`: `0.1944`
  - `3x`: `0.3333`
- final-pass exact-match rate:
  - `1x`: `0.0556`
  - `2x`: `0.3333`
  - `3x`: `0.6111`

Prediction also strengthened with exposure:

- mean source prediction confidence:
  - `1x`: `0.3361`
  - `2x`: `0.3810`
  - `3x`: `0.4726`
- mean source expected delta:
  - `1x`: `0.0164`
  - `2x`: `0.0388`
  - `3x`: `0.1016`

#### B2

- overall exact-match rate:
  - `1x`: `0.5648`
  - `2x`: `0.6296`
  - `3x`: `0.6512`
- final-pass exact-match rate:
  - `1x`: `0.5648`
  - `2x`: `0.6944`
  - `3x`: `0.6944`

Prediction also strengthened:

- mean source prediction confidence:
  - `1x`: `0.5347`
  - `2x`: `0.5758`
  - `3x`: `0.5818`
- mean source expected delta:
  - `1x`: `0.1325`
  - `2x`: `0.1572`
  - `3x`: `0.1620`

#### C3

- overall exact-match rate:
  - `1x`: `0.2222`
  - `2x`: `0.2546`
  - `3x`: `0.2500`
- final-pass exact-match rate:
  - `1x`: `0.2222`
  - `2x`: `0.2870`
  - `3x`: `0.2407`

Prediction strengthened somewhat:

- mean source prediction confidence:
  - `1x`: `0.4562`
  - `2x`: `0.5116`
  - `3x`: `0.5113`
- mean source expected delta:
  - `1x`: `0.0987`
  - `2x`: `0.1348`
  - `3x`: `0.1326`

Small stale-family risk did appear here:

- overall mean source stale-family risk:
  - `1x`: `0.0079`
  - `2x`: `0.0064`
  - `3x`: `0.0069`

Per-pass, it was highest in the earliest pass and often dropped back toward `0` later.

## Interpretation

The family-level pattern is consistent with the earlier single-benchmark results:

- extra idle time does not help
- repeated experience does help

What is new is that prediction now appears to co-vary with repeated exposure:

- prediction is already active from the start
- but with repeated exposure, source prediction confidence and expected-delta means generally rise
- the effect is strongest on `A1` and `B2`
- `C3` improves only modestly, suggesting ambiguous multi-context problems still need something beyond simple additional exposure plus the current predictive binding

## Takeaway

The current predictive layer behaves more like a confidence-amplified consequence estimate than a latent solver.

- it does not need more idle time
- it does benefit from more lived interaction
- it seems most useful where repeated experience sharpens transform expectations
- it is not yet sufficient to unlock strong `C3` adaptation on its own
