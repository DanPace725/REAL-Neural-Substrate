## 2026-03-30 1348 - General Growth Threshold Relaxation and Persistence Tuning

### Why

The earlier growth-intent latch fixed one specific failure mode: hidden-regime runs could reach `authorize` and `initiate` instead of looping forever at authorization with no action. But visible C-family runs still showed a broader persistence failure:

- node-level growth request pressure often rose into the `0.25-0.40` range and then washed out
- slow-layer summaries frequently reported `authorization_missing` even when the system had recently been under structural strain
- the topology manager could only apply one event per checkpoint, which limited expression even when growth did get through

This pass treats that as a general growth-contract problem rather than a benchmark-specific bug.

### Changes

#### Capability-side persistence and thresholds

In `phase8/environment.py`:

- `CapabilityControlConfig` growth defaults were relaxed:
  - `growth_support_decay`: `0.90 -> 0.94`
  - `growth_support_gain`: `0.10 -> 0.14`
  - `growth_activation_threshold`: `0.62 -> 0.52`
  - `growth_stability_threshold`: `0.48 -> 0.40`
- Added explicit growth-request controls:
  - `growth_request_threshold = 0.35`
  - `growth_request_soft_threshold = 0.22`
  - `growth_request_retention_cycles = 12`
- `_refresh_growth_intent(...)` now latches request pressure/readiness instead of replacing them with only current-cycle values.
- The local-unit growth request decay was softened from `0.94` to `0.97`.

#### Morphogenesis-side thresholds

In `phase8/topology.py`, defaults were relaxed so structural growth can happen under less restrictive conditions:

- `max_events_per_checkpoint`: `1 -> 2`
- `max_dynamic_nodes`: `4 -> 6`
- `atp_surplus_threshold`: `0.75 -> 0.62`
- `surplus_window`: `3 -> 2`
- `contradiction_threshold`: `0.55 -> 0.35`
- `overload_threshold`: `0.60 -> 0.40`
- `growth_energy_threshold`: `0.03 -> 0.015`
- `growth_queue_tolerance`: `1 -> 2`

#### Authorization alignment

- `growth_action_specs(...)` now uses the new request thresholds instead of hard-coded `0.45` and `0.25` cutoffs.
- `phase8/lamination.py` now counts requesting nodes using the same relaxed request threshold.
- `real_core/lamination.py` slow-layer authorization thresholds were lowered so the regulator is less likely to ignore moderate but persistent growth need.

### Validation

Focused tests passed:

- `python -m unittest tests.test_latent_growth_gate tests.test_phase8_lamination tests.test_lamination`

Added/updated test coverage:

- `tests/test_latent_growth_gate.py`
  - authorization now works at lower request pressure
  - growth intent persists across short dips instead of dropping immediately

### First runtime read

Using the combined C/HR pilot setup:

- overlap topology: `bounded_overlap_13715`
- local unit mode: `pulse_local_unit`
- preset: `c_hr_overlap_tuned_v1`
- seed `13`
- budget `6`
- safety limit `40`

Observed:

- `C3S2 task_a`
  - still no active growth nodes
  - but now reaches `max_pending_proposals = 2`
  - `max_requesting_nodes = 1`
  - `max_pressure = 0.4482`
  - blocked reasons now include `authorized_without_viable_target`, meaning the request is surviving long enough to reach proposal generation
- `HR2 task_a hidden`
  - still reaches active growth with `max_active_growth_nodes = 1`
  - `max_pending_proposals = 2`
  - `max_requesting_nodes = 7`
  - `max_pressure = 0.4918`

### Interpretation

This tuning did not magically solve visible C-family growth, but it did move the bottleneck:

- before this pass, C-family growth pressure mostly evaporated before it became a sustained request
- after this pass, C-family runs can at least accumulate pending proposals

That suggests the remaining C-family blocker is no longer just persistence. It is now more likely a viability/target-selection issue inside `growth_action_specs(...)`, especially around `authorized_without_viable_target`, `insufficient_structural_motivation`, or queue-window timing.
