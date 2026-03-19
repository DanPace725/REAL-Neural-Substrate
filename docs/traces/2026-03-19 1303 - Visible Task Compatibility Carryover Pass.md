# 2026-03-19 1303 - Visible Task Compatibility Carryover Pass

## Context

The first carryover hygiene pass was safe but too gentle:

- stale carried `context_action_support` was measurably reduced
- but the first warm `B -> C` source decision still did not change
- macro `B -> C` transfer metrics stayed essentially flat

That suggested the higher-leverage issue was not just “too much stale support,” but also:

- visible-context transfer already knows the current task geometry locally
- yet that compatibility signal was still too weak compared with the carried prior

## Change

Updated `phase8/selector.py` again.

This pass keeps the earlier context-support hygiene, but adds a small visible-task compatibility signal when:

- an explicit or effective context is present
- the task is visible rather than hidden
- the transform family is compatible or incompatible with the current task/context map

The intent is:

- compatible transforms get a modest local bonus
- incompatible transforms get a modest penalty
- the effect is stronger when carried context support has already been discounted

This keeps the selector local and task-grounded without removing carryover.

Added a focused regression in `tests/test_phase8_recognition.py` showing that, under visible-context mismatch, a task-compatible transform can now outrank stale carried support.

## Result

### Early B -> C carryover diagnosis

Seed `13`, first `task_c`, `context_0` source decision:

- `none` chose `route_transform:n2:xor_mask_1010`
- `substrate` now also chose `route_transform:n2:xor_mask_1010`
- `full` still did not fully resolve cleanly on this micro-probe, choosing `route_transform:n1:xor_mask_0101`

So the new pass did improve the source-side early decision for the structural carryover case, even if the full-carryover single-step probe still shows some branch ambiguity.

### Warm B -> C exposure probe, full carryover

Before this pass:

- repeat `1x`: exact `0.2222`
- repeat `2x`: exact `0.3889`
- repeat `3x`: exact `0.4444`
- final-pass exact: `0.2222 / 0.5556 / 0.5556`

After this pass:

- repeat `1x`: exact `0.5556`
- repeat `2x`: exact `0.7500`
- repeat `3x`: exact `0.8148`
- final-pass exact: `0.5556 / 0.9444 / 0.9444`

Prediction still strengthened with exposure:

- mean source prediction confidence: `0.2407 -> 0.2608 -> 0.2632`

### Sanity checks

Warm `A -> C`, full carryover, also improved strongly:

- repeat `1x`: exact `0.5000`
- repeat `2x`: exact `0.7500`
- repeat `3x`: exact `0.8333`
- final-pass exact: `0.5000 / 1.0000 / 1.0000`

Warm `B -> C`, no carryover, stayed essentially unchanged:

- repeat `1x`: exact `0.5556`
- repeat `2x`: exact `0.5556`
- repeat `3x`: exact `0.5370`

That last point matters because it suggests the improvement is not just a generic inflation of all transfer slices. It is concentrated where carryover was previously hurting.

## Interpretation

This second pass looks materially more meaningful than the first one.

Current read:

- the real issue was not only stale support magnitude
- it was also the selector underusing visible task compatibility during transfer
- once that compatibility signal was made more explicit, the harmful carryover slices improved dramatically

This is a good point to step back, because the result is now large enough that the next question is broader:

- where does this improvement generalize?
- what other transfer slices benefit or regress?
- and which capability jumps now matter most relative to more ambitious prediction or capability-control work?
