# 2026-03-18 2054 - Runtime Slack Probe

## Context

This trace records a direct check of the question:

> If we keep the exact same benchmark stream but allow more runtime cycles, do REAL agents eventually solve the task?

The key distinction was:

- same example stream
- same task definition
- same seed
- only the cycle budget changes

This is a runtime-slack test, not a longer-training-data test.

## Code Changes

Added [evaluate_runtime_slack.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/scripts/evaluate_runtime_slack.py):

- stretches benchmark scenario `cycles` by a chosen multiplier
- keeps the same injected signal stream and expected-example count
- reports:
  - `exact_match_rate`
  - `criterion_reached`
  - `examples_to_criterion`
  - `best_rolling_exact_rate`
  - `best_rolling_bit_accuracy`
  - deltas relative to the `1.0x` baseline

Added [test_runtime_slack.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/tests/test_runtime_slack.py):

- smoke test for `B2` / `task_a` / `self-selected`

## Validation

Test:

```powershell
$env:PYTHONPATH='C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate;C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate\scripts;C:\Users\nscha\AppData\Roaming\Python\Python313\site-packages'; C:\Python313\python.exe -m unittest tests.test_runtime_slack
```

Result: `OK`

Runtime-slack probe:

- benchmark: `B2`
- task: `task_a`
- seed: `13`
- methods:
  - `fixed-visible`
  - `self-selected`
- cycle multipliers:
  - `1.0x`
  - `1.5x`
  - `2.0x`

## Results

### `fixed-visible`

Baseline (`1.0x`, `128` cycles):

- exact match rate: `0.7222`
- exact matches: `78 / 108`
- criterion reached: `true`
- examples to criterion: `48`
- best rolling exact rate: `1.0`

At `1.5x` (`192` cycles):

- no change in exact match rate
- no change in best rolling exact rate
- no change in examples to criterion

At `2.0x` (`256` cycles):

- no change in exact match rate
- no change in best rolling exact rate
- no change in examples to criterion

### `self-selected`

Baseline (`1.0x`, `128` cycles):

- exact match rate: `0.2500`
- exact matches: `27 / 108`
- criterion reached: `false`
- examples to criterion: `None`
- best rolling exact rate: `0.625`
- latent recruitment cycles: `[31]`

At `1.5x` (`192` cycles):

- no change in exact match rate
- no change in best rolling exact rate
- no change in criterion status

At `2.0x` (`256` cycles):

- no change in exact match rate
- no change in best rolling exact rate
- no change in criterion status

Aggregate summary:

- improved exact-match cases: `0`
- improved best-rolling cases: `0`

## Interpretation

For this `B2` setup, extra runtime slack alone does not help.

That means the current failure is not “the same stream ends before the agent finishes settling” in the simple sense. Once the scheduled stream has been processed, giving the system more empty cycles does not recover the missed performance.

So the current bottleneck still looks like:

- selector integration of latent / source-sequence guidance
- or a need for more useful examples during the period when the latent controller is forming

and not merely “more idle time after the same examples.”

## Follow-Up

If we want to keep pushing on the time question, the next more informative variant would be:

1. keep the same benchmark family and task
2. increase the number of injected examples or prolong the schedule
3. compare whether `self-selected` improves when it gets *more online experience*, not just more empty cycles

That would test “does REAL eventually get there with more lived interaction?” more directly than the slack-only probe.
