# 2026-03-19 1142 - C Transfer Exposure Prediction Probe

## Context

After the warm `A -> B` transfer-exposure probe, we had a useful but incomplete result:

- repeated transfer exposure increased source-side prediction confidence
- exact-match stayed flat on that slice

The next small check was to use the same probe on a C-involving transfer path, with `C` as the transfer task, because that is the more ambiguity-rich place where anticipatory structure should matter more.

## Probe

Ran:

`python -m scripts.probe_transfer_exposure_prediction --train-scenario cvt1_task_b_stage1 --transfer-scenario cvt1_task_c_stage1 --seeds 13 --repeat-counts 1 2 3 --carryover-mode full`

This keeps the probe narrow:

- warm transfer with full carryover
- single seed
- repeated transfer stream only
- no changes to REAL mechanics

## Result

This slice behaved very differently from warm `A -> B`.

Baseline warm `B -> C`, seed `13`, repeat `1x`:

- exact-match rate: `0.2222`
- mean bit accuracy: `0.3611`
- best rolling exact rate: `0.375`
- mean source prediction confidence: `0.2238`
- mean source expected delta: `-0.0015`

Repeat `2x`:

- exact-match rate: `0.3889`
- mean bit accuracy: `0.4583`
- best rolling exact rate: `0.75`
- final-pass exact-match rate: `0.5556`
- mean source prediction confidence: `0.2528`
- mean source expected delta: `0.0309`

Repeat `3x`:

- exact-match rate: `0.4444`
- mean bit accuracy: `0.4907`
- best rolling exact rate: `0.75`
- final-pass exact-match rate: `0.5556`
- mean source prediction confidence: `0.2620`
- mean source expected delta: `0.0419`

Aggregate probe counts:

- improved overall exact cases: `2`
- improved final-pass cases: `2`
- increased prediction-confidence cases: `2`

## Interpretation

This is the first small transfer-exposure result where prediction growth and adaptation improvement move together in a meaningful way.

Compared with warm `A -> B`:

- `A -> B` showed prediction strengthening without better transfer accuracy
- `B -> C` showed prediction strengthening alongside materially better transfer performance

That does not prove causality by itself, but it is exactly the kind of pattern we wanted to know whether the new anticipation path could reveal.

The other useful detail is qualitative:

- pass 1 still looks weak and ambiguity-heavy
- pass 2 is where the big improvement appears
- pass 3 mostly consolidates rather than creating a second jump

So for this C-transfer slice, repeated exposure appears to give REAL enough additional interaction for predictive commitment to become behaviorally useful.
