# 2026-03-30 1015 - Pulse Preset and C3S1 Overlap Inspection

## Why

The overlap topology plus `pulse_local_unit` combination was only reproducible through ad hoc runtime tweaks:

- `base_threshold = 0.45`
- `accumulator_decay = 0.92`
- `initial_plasticity_gate = 0.05`

This pass makes that configuration a named opt-in preset so C/HR pilot runs can be reproduced cleanly, serialized with runtime state, and attributed in manifests. After wiring the preset, the run was inspected on `C3S1 task_a visible` under the overlap graph with a larger laminated budget to see what the combined system is doing at node level.

## What Changed

- Added a named Phase 8 pulse preset layer in `phase8/models.py`:
  - `PulseLocalUnitPreset`
  - `PULSE_LOCAL_UNIT_PRESETS`
  - `resolve_pulse_local_unit_preset(...)`
  - `pulse_local_unit_preset_names()`
- Added preset-aware local-unit initialization and serialization in `phase8/environment.py`.
- Added `local_unit_preset` plumbing through:
  - `phase8/lamination.py`
  - `scripts/evaluate_laminated_phase8.py`
  - `scripts/evaluate_hidden_regime_forecasting.py`
- Added focused tests in `tests/test_phase8_pulse_local_unit.py` covering:
  - named preset application to initial local-unit state
  - laminated slice metadata carrying the preset
  - hidden-regime result metadata carrying the preset

## Preset Added

Named preset:

- `c_hr_overlap_tuned_v1`

Parameters:

- `base_threshold = 0.45`
- `accumulator_decay = 0.92`
- `cooldown_ticks = 1`
- `initial_plasticity_gate = 0.05`

Default behavior remains unchanged:

- `local_unit_mode = legacy`
- `local_unit_preset = default`

## Verification

Passed:

- `python -m py_compile phase8\models.py phase8\environment.py phase8\lamination.py phase8\__init__.py scripts\evaluate_laminated_phase8.py scripts\evaluate_hidden_regime_forecasting.py tests\test_phase8_pulse_local_unit.py`
- `python -m unittest tests.test_phase8_pulse_local_unit tests.test_c_hr_overlap_topology tests.test_phase8_lamination`

## C3S1 Inspection Run

Configuration:

- benchmark: `C3S1`
- task: `task_a`
- observable mode: visible
- topology: `bounded_overlap_13715`
- local-unit mode: `pulse_local_unit`
- local-unit preset: `c_hr_overlap_tuned_v1`
- seed: `13`
- initial cycle budget: `6`
- safety limit: `10`
- regulator: `heuristic`

Outcome:

- final decision: `continue`
- slices: `10`
- final accuracy: `0.4118`
- floor accuracy: `0.3750`
- forecast accuracy: `0.4146`
- delivered packets: `119 / 123`
- mean bit accuracy: `0.4454`

Transform use at the sink:

- `rotate_left_1`: `91`
- `identity`: `24`
- `xor_mask_0101`: `2`
- `xor_mask_1010`: `2`

Context breakdown:

- `context_0`: mean bit accuracy `0.4219`, exact matches `8 / 64`
- `context_1`: mean bit accuracy `0.4727`, exact matches `7 / 55`

Local-unit aggregate telemetry:

- pulse fires: `239`
- suppressed attempts: `161`
- mean accumulator level: `0.0223`
- mean plasticity gate: `0.0421`
- max growth request pressure: `0.2954`

## Node-Level Read

The tuned preset fixes the earlier total starvation failure, but it does not yet produce well-differentiated transform learning on `C3S1`.

Observed pattern:

- first-layer and early second-layer nodes are active, so the overlap graph is genuinely being used
- `n1` is the busiest first-layer node with `61` fires and only `17` suppressions, but it still ends up with a strong `xor_mask_1010` last-fire trace and a plasticity gate of only `0.4399`
- `n3` and `n9` are busy but still suppression-heavy (`38` and `29` suppressions respectively)
- most nodes finish with very low plasticity gate despite high traffic; aggregate mean plasticity is only `0.0421`
- first-layer `action_supports` are still almost entirely zero, except a small `rotate_left_1` support on `n3 -> n8`

The most important qualitative result is:

- the tuned preset makes the combined graph plus pulse system runnable and inspectable
- the remaining `C3S1` weakness is no longer "nothing fires"
- it is now closer to "traffic moves, but transform differentiation stays biased and plasticity rarely opens enough to stabilize alternatives"

## Interpretation

The preset should stay as an opt-in pilot setting because it is the first reproducible non-starving configuration for the overlap-graph plus pulse combination. But this run suggests the next `C3S1` iteration should focus on the transform-use path, not just pulse suppression.

Most likely next questions:

- why `rotate_left_1` dominates sink transforms despite overlap routing activity
- why first-layer `action_supports` remain near zero after a full 10-slice run
- whether the pulse evidence term should stop depending on `observation["action_supports"]` and instead read live substrate support directly from the environment

## Files

- `phase8/models.py`
- `phase8/environment.py`
- `phase8/lamination.py`
- `phase8/__init__.py`
- `scripts/evaluate_laminated_phase8.py`
- `scripts/evaluate_hidden_regime_forecasting.py`
- `tests/test_phase8_pulse_local_unit.py`
