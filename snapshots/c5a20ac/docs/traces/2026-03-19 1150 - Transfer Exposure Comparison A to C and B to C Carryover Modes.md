# 2026-03-19 1150 - Transfer Exposure Comparison A to C and B to C Carryover Modes

## Context

After the first warm `B -> C` transfer-exposure probe with full carryover, the next useful comparisons were:

- warm `A -> C` with full carryover
- warm `B -> C` with weaker carryover modes (`substrate` and `none`)

The goal was to separate three things:

- repeated transfer exposure
- predictive strengthening
- carryover benefit or interference

## Probes

Ran:

- `python -m scripts.probe_transfer_exposure_prediction --train-scenario cvt1_task_a_stage1 --transfer-scenario cvt1_task_c_stage1 --seeds 13 --repeat-counts 1 2 3 --carryover-mode full`
- `python -m scripts.probe_transfer_exposure_prediction --train-scenario cvt1_task_b_stage1 --transfer-scenario cvt1_task_c_stage1 --seeds 13 --repeat-counts 1 2 3 --carryover-mode substrate`
- `python -m scripts.probe_transfer_exposure_prediction --train-scenario cvt1_task_b_stage1 --transfer-scenario cvt1_task_c_stage1 --seeds 13 --repeat-counts 1 2 3 --carryover-mode none`

For reference, the earlier full-carryover warm `B -> C` result was:

- repeat `1x`: exact `0.2222`
- repeat `2x`: exact `0.3889`
- repeat `3x`: exact `0.4444`

## Result

### A -> C, full carryover

- repeat `1x`: exact `0.2778`, final-pass exact `0.2778`, source prediction confidence `0.2297`
- repeat `2x`: exact `0.4444`, final-pass exact `0.6111`, source prediction confidence `0.2608`
- repeat `3x`: exact `0.4630`, final-pass exact `0.5000`, source prediction confidence `0.2723`

Prediction and adaptation both improved. The main jump happened at pass 2.

### B -> C, substrate carryover

- repeat `1x`: exact `0.2778`, final-pass exact `0.2778`, source prediction confidence `0.2325`
- repeat `2x`: exact `0.4167`, final-pass exact `0.5556`, source prediction confidence `0.2654`
- repeat `3x`: exact `0.4630`, final-pass exact `0.5556`, source prediction confidence `0.2853`

This is very similar to the earlier full-carryover `B -> C` story, and slightly better on the baseline and later prediction confidence.

### B -> C, no carryover

- repeat `1x`: exact `0.5556`, final-pass exact `0.5556`, source prediction confidence `0.2783`
- repeat `2x`: exact `0.5556`, final-pass exact `0.5556`, source prediction confidence `0.2901`
- repeat `3x`: exact `0.5370`, final-pass exact `0.5000`, source prediction confidence `0.2933`

Prediction still strengthened a bit with exposure, but adaptation did not improve because the no-carryover baseline was already much stronger.

## Interpretation

Two things stand out.

First, `A -> C` and `B -> C` both show the same broad pattern under full or substrate carryover:

- pass 1 is weak
- pass 2 is where prediction and adaptation both jump
- pass 3 mostly consolidates

Second, the `B -> C` carryover comparison strongly suggests that some carryover is actually interfering on this slice:

- `none` starts far stronger than either `full` or `substrate`
- repeated exposure still nudges prediction upward under `none`
- but there is little room left for exposure to improve accuracy

So the current read is:

- repeated exposure can strengthen prediction across these C-transfer slices
- that predictive strengthening can align with better adaptation when transfer starts in a weak state
- on `B -> C`, the main limiter may now be stale or misaligned carryover more than lack of prediction

This makes `B -> C` a good candidate for future work on carryover hygiene or context-sensitive carryover suppression, rather than just stronger prediction terms.
