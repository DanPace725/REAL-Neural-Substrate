# 2026-03-19 0920 - C to A Seed 51 Exception Diagnosis

## Summary

Ran a tight follow-up on the only negative case from the widened sweep:

- train: `cvt1_task_c_stage1`
- transfer: `cvt1_task_a_stage1`
- seed: `51`

Goal:

- determine whether the small regression with recognition enabled comes from the same source-side selector interaction we had previously fixed

## Result

It does not appear to be a source-side recognition-selection problem.

### Key finding

- source route decision count: `18`
- source decision diff cycles between enabled and disabled: none

So the source chose the same route/transform actions in both runs.

## Behavioral Difference

The regression shows up only in the outcome summary:

- enabled: `11` exact, `0.75` mean bit accuracy
- disabled: `12` exact, `0.8056` mean bit accuracy

The difference is concentrated in `context_1`:

- enabled `context_1` exact: `2`
- disabled `context_1` exact: `3`
- enabled `context_1` mean bit accuracy: `0.5`
- disabled `context_1` mean bit accuracy: `0.625`

`context_0` is identical across both runs.

## Interpretation

This strongly suggests the exception is not caused by the current source-side recognition gate.

Instead, the small difference is more likely coming from:

- downstream node behavior
- feedback propagation timing
- or a later local interaction after the source has already made the same choices in both runs

That makes this a much lower-priority exception for the current line of work.

## Practical Conclusion

The widened sweep still supports the main conclusion:

- the evidence-confirmation gate fixed the earlier source-side recognition problem

And this one remaining dip does not currently look like a reason to reopen that source-side selector change.
