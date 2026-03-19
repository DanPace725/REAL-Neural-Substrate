# 2026-03-18 2059 - Repeated Experience Probe

## Context

This trace records the follow-up to the runtime-slack probe.

The slack-only result showed that extra empty cycles after the same stream did not help `B2`. The next question was stronger:

> If the system is allowed to live through the same benchmark stream multiple times, does it improve on later passes?

That is a better fit for REAL than idle runtime, because it gives the substrate more actual online interaction rather than more waiting.

## Code Changes

Added [evaluate_experience_extension.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/scripts/evaluate_experience_extension.py):

- repeats the exact same benchmark signal stream `N` times
- preserves within-pass signal timing
- removes unnecessary between-pass slack
- reports:
  - overall exact rate
  - criterion status
  - examples to criterion
  - best rolling exact rate
  - per-pass exact rate / criterion / best rolling exact rate
  - delta from the single-pass baseline

Added [test_experience_extension.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/tests/test_experience_extension.py):

- smoke test for `B2` repeated-experience evaluation

## Validation

Test:

```powershell
$env:PYTHONPATH='C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate;C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate\scripts;C:\Users\nscha\AppData\Roaming\Python\Python313\site-packages'; C:\Python313\python.exe -m unittest tests.test_experience_extension
```

Result: `OK`

Probe:

- benchmark: `B2`
- task: `task_a`
- seed: `13`
- methods:
  - `fixed-visible`
  - `self-selected`
- repeat counts:
  - `1`
  - `2`
  - `3`

## Results

### `fixed-visible`

Single pass:

- overall exact rate: `0.7222`
- criterion reached: `true`
- examples to criterion: `48`

Two passes:

- overall exact rate: `0.8472`
- second-pass exact rate: `0.9722`
- second-pass examples to criterion: `8`

Three passes:

- overall exact rate: `0.8920`
- third-pass exact rate: `0.9815`
- third-pass examples to criterion: `8`

### `self-selected`

Single pass:

- overall exact rate: `0.2500`
- criterion reached: `false`
- best rolling exact rate: `0.625`

Two passes:

- overall exact rate: `0.3287`
- criterion reached: `true`
- overall examples to criterion: `169`
- second-pass exact rate: `0.4074`
- second-pass examples to criterion: `61`
- best rolling exact rate: `0.875`

Three passes:

- overall exact rate: `0.4383`
- criterion reached: `true`
- overall examples to criterion: `169`
- third-pass exact rate: `0.6574`
- third-pass examples to criterion: `8`
- best rolling exact rate: `0.875`

Aggregate summary:

- improved overall exact cases: `4`
- improved final-pass cases: `4`

## Interpretation

This is the clearest answer yet to the “does more time help?” question:

- more idle runtime does **not** help
- more repeated online experience **does** help

That means `B2` is not blocked by post-stream settling time. It is blocked by needing more actual task interaction for the substrate and selector to become useful.

The most important result is the self-selected case:

- it fails on the first pass
- it reaches criterion across the repeated run by the second pass
- by the third pass its per-pass exact rate climbs to `0.6574`

So self-selected REAL is not simply incapable on `B2`. It does improve with additional lived exposure. The remaining issue is sample efficiency and selector use of the latent signal, not total inability to learn.

## Follow-Up

The next best step is to connect this back to the selector integration problem:

1. run the benchmark-node probe on pass `2` and pass `3`
2. compare whether `pre_sequence_guidance_match_rate` rises across passes
3. if it does not rise enough, tune selector weighting toward source-sequence / latent hints once latent capability is active
