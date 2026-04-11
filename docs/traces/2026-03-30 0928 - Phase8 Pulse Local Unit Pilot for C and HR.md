# 2026-03-30 0928 - Phase8 Pulse Local Unit Pilot for C and HR

## Why

Implemented a narrow Phase 8 pilot of the `pulse_local_unit` idea from `docs/20260330 Redesign.md` without rewriting `real_core` or changing graph topology semantics.

The goal of this pass was to answer a small question first:

- can we add explicit per-node signal/context/plasticity state
- can we gate route execution through pulse accumulation and short refractory behavior
- can we expose bottom-up growth-request telemetry cleanly through the laminated C/HR evaluation paths
- can we do all of that while leaving the legacy path unchanged by default

## What Changed

### Runtime

- Added explicit Phase 8-only local-unit runtime state in `phase8/models.py`:
  - `SignalState`
  - `ContextState`
  - `PlasticityState`
  - `LocalUnitState`
- Added `local_unit_mode = "legacy" | "pulse_local_unit"` to `RoutingEnvironment` and `NativeSubstrateSystem`.
- Stored local-unit state as a separate environment-owned map rather than embedding it into `NodeRuntimeState`, so the pilot remains inspectable and easy to remove or expand later.

### Pulse gating

- Added route-attempt evaluation in `RoutingEnvironment.evaluate_route_action(...)`.
- Kept graph topology and route action names unchanged.
- Enforced pulse gating in `LocalNodeActionBackend.execute(...)` so the REAL loop stays intact and the packet remains local when a route attempt is suppressed.
- The current pulse gate:
  - accumulates route evidence across repeated attempts
  - fires only after threshold crossing
  - applies a short per-channel cooldown
  - retains ambiguity/plasticity/growth-request state locally

### Plasticity and growth

- Added local ambiguity reservoir, plasticity gate, unresolved streak, and growth-request pressure updates on route attempts.
- Blended local growth-request pressure into existing self-selected growth recruitment pressure rather than replacing the current capability controller.
- Damped durable feedback promotion when the plasticity gate is low while keeping provisional credit updates alive.

### Lamination and scripts

- Added `local_unit_mode` plumbing to:
  - `phase8/lamination.py`
  - `scripts/evaluate_laminated_phase8.py`
  - `scripts/evaluate_hidden_regime_forecasting.py`
- Added new slice metadata only, keeping `SliceSummary` and `RegulatorySignal` schemas unchanged:
  - `pulse_fire_count`
  - `suppressed_route_attempts`
  - `mean_accumulator_level`
  - `refractory_occupancy`
  - `mean_ambiguity_reservoir`
  - `mean_plasticity_gate`
  - `requesting_growth_nodes`
  - `max_growth_request_pressure`

## Tests Added

- `tests/test_phase8_pulse_local_unit.py`

Coverage in this pass:

- accumulator threshold crossing
- cooldown suppression
- ambiguity keeping plasticity closed
- growth-request pressure rising under unresolved ambiguity
- durable feedback promotion damped by low plasticity gate
- laminated C summary metadata includes the new pulse telemetry
- hidden-regime runner records `local_unit_mode`

## Pilot Read

Small comparison run, seed `13`, budget `4`, safety limit `3`:

- `C3S1 task_a`
  - legacy final/floor: `0.55 / 0.50`
  - pulse final/floor: `0.4286 / 0.3333`
  - pulse telemetry: fires `7`, suppressed attempts `13`, max growth request `0.1854`
- `C3S2 task_a`
  - legacy final/floor: `0.60 / 0.5833`
  - pulse final/floor: `0.3333 / 0.0`
  - pulse telemetry: fires `11`, suppressed attempts `29`, max growth request `0.3494`
- `HR1 task_a hidden`
  - legacy final/floor: `0.75 / 0.75`
  - pulse final/floor: `0.0 / 0.0`
  - pulse telemetry: fires `0`, suppressed attempts `16`, max growth request `0.3258`
- `HR2 task_a hidden`
  - legacy final/floor: `0.75 / 0.75`
  - pulse final/floor: `1.0 / 1.0`
  - pulse telemetry: fires `1`, suppressed attempts `11`, max growth request `0.3103`

## Interpretation

- The pilot is working technically: the mode is opt-in, summary-safe, serialized, tested, and isolated to Phase 8/runtime-plus-laminated entrypoints.
- The current pulse policy is likely too suppressive on some C/HR cases.
- The telemetry is useful already:
  - `HR1` shows a near-complete suppression failure mode
  - `C3S2` shows high suppression and near-zero floor accuracy
  - `HR2` suggests the pulse gate is not universally harmful and may help on some regime structures

## Likely Next Move

Tune the pulse gate before any broader rollout:

- lower the default threshold or reduce accumulator decay loss
- let ambiguity retention delay durable promotion without starving forward routing as aggressively
- consider a minimum-fire escape hatch after repeated suppressed attempts
- evaluate whether source-adjacent or forecast-sensitive nodes should use a softer gate than midstream nodes

## Files Touched

- `phase8/models.py`
- `phase8/environment.py`
- `phase8/adapters.py`
- `phase8/lamination.py`
- `scripts/evaluate_laminated_phase8.py`
- `scripts/evaluate_hidden_regime_forecasting.py`
- `tests/test_phase8_pulse_local_unit.py`
