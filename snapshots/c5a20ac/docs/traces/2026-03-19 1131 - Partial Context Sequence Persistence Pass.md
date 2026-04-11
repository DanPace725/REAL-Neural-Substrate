# 2026-03-19 1131 - Partial Context Sequence Persistence Pass

## Context

The uncertainty-weighted effective-context pass made multistate context resolution softer and slightly improved `C3` self-selected performance.

The next theory-aligned step was:

- keep sequence evidence partially influential after context begins to resolve on multistate tasks

The motivation was the earlier selector reading:

- once effective context exists, the selector exits the sequence-heavy hidden-task regime
- then task affinity, history evidence, and context support dominate

## Change

Updated [phase8/selector.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/selector.py).

Added a narrow selector path that applies only when:

- source node
- sequence evidence is available
- task has more than 2 contexts
- latent is active or effective context is present

The added terms:

- `partial_context_sequence_bonus_term`
- `partial_context_sequence_penalty_term`

They are scaled by:

- `latent_resolution_weight`
- `effective_context_confidence`

So sequence evidence stays alive longer only when context is still partially resolved or uncertainty-weighted.

Binary tasks are unaffected.

Also exposed `latent_context_count` in [phase8/environment.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/environment.py) so the selector can distinguish multistate from binary cases.

## Focused Test

Added a selector regression in [tests/test_phase8_recognition.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/tests/test_phase8_recognition.py):

- positive sequence hint under partial multistate context yields a positive continuation bonus
- negative sequence hint under the same conditions yields a penalty

Validation:

```powershell
$env:PYTHONPATH='C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate;C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate\scripts;C:\Users\nscha\AppData\Roaming\Python\Python313\site-packages'; C:\Python313\python.exe -m unittest tests.test_phase8_recognition tests.test_phase8_context_uncertainty tests.test_phase8_capability_prediction tests.test_benchmark_node_probe
```

Result: `OK`

## Result

### Self-selected smoke slice

Re-ran:

- `A1`
- `B2`
- `C3`
- `task_a`
- seed `13`

Result:

- `A1`: unchanged at `0.0556`
- `B2`: unchanged at `0.5648`
- `C3`: unchanged at `0.2315`

So the self-selected target did **not** improve on this slice.

### Important side effect

The current-code fixed-policy comparator shifted substantially on `C3`:

- `fixed-latent` rose to `0.6574`

That means the local smoke oracle for `C3` moved from `0.3333` to `0.6574`, making the self-selected gap appear much worse even though self-selected itself did not regress.

### C3 self-selected source summary

The core self-selected `C3` source profile stayed effectively the same:

- first latent capability cycle: `46`
- route transform counts:
  - `rotate_left_1`: `60`
  - `xor_mask_1010`: `18`
  - `xor_mask_0101`: `2`
- pre-sequence guidance match rate: `0.34615`

So the new persistence path did not meaningfully alter the self-selected source behavior on this slice.

## Interpretation

This pass is structurally coherent but did not move the intended target.

What it seems to have done:

- improved a latent-policy path where sequence-like evidence is already better aligned with the latent scenario

What it did **not** do:

- improve the visible-scenario self-selected `C3` run
- change the self-selected source transform distribution in a meaningful way

So this is a useful negative result:

- keeping sequence evidence alive longer is not sufficient by itself on the current self-selected `C3` path

## Current Best Read

The remaining bottleneck is probably even narrower now:

- not merely "sequence evidence disappears too soon"
- but "self-selected visible-scenario control is not converting the retained competing evidence into a different transform-family decision"

That likely points toward one of:

- a deeper conflict between the visible-scenario path and the latent estimate semantics
- or the need for selector logic that uses partial context plus sequence disagreement more explicitly, rather than just preserving both signals

## Suggested Next Step

Given the result here, the next best move is probably not another small selector-weight tweak on this same seam.

A better next step may be to step back and compare:

- self-selected on visible scenario
- fixed-latent on latent scenario

for `C3`, cycle-by-cycle, to understand what the latent scenario is giving the selector that self-selected never actually reaches.
