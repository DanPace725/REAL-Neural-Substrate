# 2026-03-19 1054 - Prediction Coupled Capability Pressure Pass

## Context

The prediction-aware benchmark-node probe showed that Phase 8 prediction is active from cycle `1` on `B2` and `C3`, well before latent capability recruitment.

That narrowed the open question:

> if prediction already exists early, can the self-selected controller actually use it to shift latent recruitment timing?

This pass makes a narrow controller change only:

- no new global logic
- no harness-level chooser
- no removal of the existing contradiction / latent-summary pathways

The goal is just to let selected-action prediction contribute to latent pressure when it forecasts weak fit, weak delta, or unstable outcome.

## Code Changes

Updated [phase8/models.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/models.py):

- added lightweight runtime fields for the last selected-action prediction:
  - `last_prediction_confidence`
  - `last_prediction_expected_delta`
  - `last_prediction_expected_match_ratio`
  - `last_prediction_error_magnitude`

Updated [phase8/environment.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/environment.py):

- `NativeSubstrateSystem.run_global_cycle(...)` now records selected-action prediction and prediction-error values from each node's `CycleEntry` into local runtime state
- `observe_local(...)` now exposes the last prediction fields for inspection
- `tick(...)` now decays the prediction fields alongside the existing feedback traces
- `_update_capability_states(...)` now includes a narrow predictive contribution to latent recruitment:
  - more latent pressure when prediction forecasts weak fit / weak expected delta
  - more latent pressure when prediction error is elevated
  - damping when visible prediction is strong
- the predictive contribution uses its own `prediction_task_active` footing so a just-completed action can still influence capability pressure even if the post-action head packet is gone by the time capability updates run

Added lightweight focused tests in [tests/test_phase8_capability_prediction.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/tests/test_phase8_capability_prediction.py).

## Validation

```powershell
$env:PYTHONPATH='C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate;C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate\scripts;C:\Users\nscha\AppData\Roaming\Python\Python313\site-packages'; C:\Python313\python.exe -m unittest tests.test_phase8_capability_prediction tests.test_benchmark_node_probe
```

Result: `OK`

## Smoke Re-Baseline After The Change

Re-ran the same lightweight smoke slice:

- `A1`, `B2`, `C3`
- `task_a`
- seed `13`

### Self-selected vs current-code oracle

| Benchmark | Current oracle | Oracle exact | Self-selected exact | Oracle gap | Latent recruit |
|---|---|---:|---:|---:|---|
| A1 | `fixed-latent` | 0.5556 | 0.0556 | 0.5000 | `[]` |
| B2 | `fixed-latent` | 0.6944 | 0.5648 | 0.1296 | `[32]` |
| C3 | `growth-visible` | 0.3333 | 0.2222 | 0.1111 | `[45]` |

Aggregate mean oracle gap remained `0.2469`.

So the benchmark-level score picture did **not** improve on this slice.

## What Did Move

The source-side probe *did* move in the expected direction.

### A1

- mean latent recruitment pressure: `0.0 -> 0.00631`
- mean latent capability support: stayed `0.0`
- no latent recruitment cycle

Interpretation:

- the new predictive path is now visible even on A1
- but it remains too weak to push A1 into latent, which is good for now

### B2

- first latent capability cycle: stayed `32`
- mean latent recruitment pressure: `0.16545 -> 0.19062`
- mean latent capability support: `0.58959 -> 0.60521`

Interpretation:

- prediction is now adding some pressure on B2
- but not enough yet to change the recruitment timing or the smoke outcome

### C3

- first latent capability cycle: `47 -> 45`
- mean latent recruitment pressure: `0.1291 -> 0.16579`
- mean latent capability support: `0.41871 -> 0.45969`

Interpretation:

- this is the clearest sign that the prediction path is now actually participating in capability control
- the effect is small, but it is in the right direction for the ambiguity-heavy case

## Current Read

This pass was a **real control-path improvement**, but not yet a benchmark win.

What it established:

- prediction is no longer merely present beside the capability controller
- it now measurably nudges latent pressure and support
- on `C3`, it moved latent recruitment earlier

What it did **not** establish:

- a better `A1/B2/C3` smoke outcome
- a decisive self-selected capability gain

So the current bottleneck is likely not “prediction unused” anymore.
It is more likely one of:

- prediction influence still too weak relative to the older contradiction / latent-summary path
- the controller needs a better mapping from predicted weak fit to latent payoff
- or the benchmark gain is bottlenecked downstream of capability recruitment timing

## Best Next Step

The cleanest next move is probably **diagnostic before more tuning**:

1. inspect `C3` cycle-by-cycle around the new earlier latent activation window
2. check whether the earlier activation actually changes transform choice or route choice
3. only then decide whether to strengthen prediction-to-capability coupling again, or whether the next bottleneck is selector integration after capability activation
