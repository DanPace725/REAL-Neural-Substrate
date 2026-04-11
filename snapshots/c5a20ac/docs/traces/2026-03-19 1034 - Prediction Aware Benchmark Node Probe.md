# 2026-03-19 1034 - Prediction Aware Benchmark Node Probe

## Context

The self-selected re-baseline established two things:

- `B2` and `C3` are now closer to the current-code local oracle than they were in the earlier March 18 checkpoint
- local sequence and latent evidence appears before latent capability recruitment on both tasks

But the previous benchmark-node probe was still mostly sequence/latent oriented. It could not directly answer:

> is the Phase 8 expectation path actually present before capability recruitment on these tasks?

This pass updates the existing node probe rather than creating a new diagnostic path.

## Change

Updated [scripts/diagnose_benchmark_node_probe.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/scripts/diagnose_benchmark_node_probe.py).

The probe now records selected-action prediction fields directly from each cycle's `CycleEntry`:

- `prediction_available`
- `prediction_confidence`
- `prediction_uncertainty`
- `prediction_expected_delta`
- `prediction_expected_coherence`
- `prediction_expected_progress`
- `prediction_expected_match_ratio`
- `prediction_error_magnitude`

The per-node summary now also reports:

- `first_prediction_cycle`
- `first_route_prediction_cycle`
- `predicted_entry_count`
- `predicted_route_entry_count`
- `predicted_route_before_latent_count`
- `predicted_route_before_latent_rate`
- `mean_prediction_confidence`
- `max_prediction_confidence`
- `mean_prediction_expected_delta`
- `mean_prediction_expected_match_ratio`
- `mean_prediction_error_magnitude`

Added a focused structural regression in [tests/test_benchmark_node_probe.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/tests/test_benchmark_node_probe.py) so the source summary now guarantees the probe exposes prediction fields as part of the standard benchmark-node inspection surface.

## Validation

```powershell
$env:PYTHONPATH='C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate;C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate\scripts;C:\Users\nscha\AppData\Roaming\Python\Python313\site-packages'; C:\Python313\python.exe -m unittest tests.test_benchmark_node_probe
```

Result: `OK`

## B2 / C3 Source Results

Ran the updated probe on `B2` and `C3`, seed `13`, `task_a`, `self-selected`, `80` cycles.

### B2 source summary

- first source-sequence cycle: `1`
- first latent-context cycle: `28`
- first latent-capability cycle: `32`
- first prediction cycle: `1`
- first route-prediction cycle: `1`
- predicted route entries: `80`
- predicted route entries before latent recruitment: `31` (`0.3875`)
- mean prediction confidence: `0.50926`
- max prediction confidence: `0.63137`
- mean predicted delta: `0.11628`
- mean predicted match ratio: `0.75753`
- mean prediction error magnitude: `0.3992`
- pre-sequence guidance match rate: `0.725`

### C3 source summary

- first source-sequence cycle: `3`
- first latent-context cycle: `28`
- first latent-capability cycle: `47`
- first prediction cycle: `1`
- first route-prediction cycle: `1`
- predicted route entries: `80`
- predicted route entries before latent recruitment: `46` (`0.575`)
- mean prediction confidence: `0.41635`
- max prediction confidence: `0.59315`
- mean predicted delta: `0.06698`
- mean predicted match ratio: `0.59191`
- mean prediction error magnitude: `0.33157`
- pre-sequence guidance match rate: `0.32051`

## Interpretation

This answers the immediate architectural question cleanly:

- the Phase 8 expectation path is not merely post hoc infrastructure
- it is present from cycle `1` on both `B2` and `C3`
- and it is active well before latent capability recruitment begins

So the current self-selected controller is now operating in a regime where:

- sequence evidence appears early
- prediction appears early
- latent-context estimation appears later
- latent capability recruitment happens later still

That means the remaining control question has become more specific:

- not "does prediction exist?"
- but "why is the controller not converting early prediction into a better earlier capability decision on the hard cases?"

There is also a useful task difference:

- `B2` has higher mean prediction confidence and stronger expected delta than `C3`
- `C3` spends more of its run with prediction active before latent recruitment
- yet `C3` still has much worse sequence-guidance alignment and later latent activation

That suggests the current bottleneck is likely not prediction availability alone. It is more likely one of:

- weak coupling from prediction to capability pressure
- insufficient ambiguity-weighting on `C3`
- or a controller path that still privileges contradiction and latent-summary accumulation more than forward expectation

## Best Next Step

The next targeted move should be inside the self-selected capability controller, not in the probe:

- inspect how prediction confidence / expected delta could contribute to latent recruitment pressure
- especially for ambiguity-heavy tasks like `C3`
- while keeping `A1` protected from indiscriminate latent recruitment
