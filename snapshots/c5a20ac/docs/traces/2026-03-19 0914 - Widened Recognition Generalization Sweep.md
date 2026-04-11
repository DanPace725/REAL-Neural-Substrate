# 2026-03-19 0914 - Widened Recognition Generalization Sweep

## Summary

Widened the post-fix evaluation beyond the first lightweight transfer checks.

Compared recognition bias enabled vs disabled under the evidence-confirmed selector across:

- full stage-1 directed transfer matrix over tasks `A/B/C`
- a small large-topology transfer slice

This was a read-only experiment pass. No code changes were made in this step.

## Scope

### Stage-1 matrix

Pairs:

- `cvt1_task_a_stage1 -> cvt1_task_b_stage1`
- `cvt1_task_a_stage1 -> cvt1_task_c_stage1`
- `cvt1_task_b_stage1 -> cvt1_task_a_stage1`
- `cvt1_task_b_stage1 -> cvt1_task_c_stage1`
- `cvt1_task_c_stage1 -> cvt1_task_a_stage1`
- `cvt1_task_c_stage1 -> cvt1_task_b_stage1`

Seeds:

- `13`, `23`, `37`, `51`, `79`

### Large-topology slice

Pairs:

- `cvt1_task_a_large -> cvt1_task_b_large`
- `cvt1_task_a_large -> cvt1_task_c_large`

Seeds:

- `13`, `23`, `37`

## Result

### Overall pattern

The broader pattern is still strongly stable:

- nearly all pair/seed combinations were exactly identical with recognition enabled vs disabled
- the evidence-confirmed selector does not appear to introduce broad regressions in this widened sweep

### One exception

There was one real negative case:

- `cvt1_task_c_stage1 -> cvt1_task_a_stage1`
- seed `51`

Enabled vs disabled:

- enabled: `11` exact, `0.75` mean bit accuracy
- disabled: `12` exact, `0.8056` mean bit accuracy

The recheck reproduced the same result, so this is not just a one-off run artifact.

## Stage-1 Matrix Readout

### Neutral pairs across all tested seeds

These were fully identical for all tested seeds:

- `A -> B`
- `A -> C`
- `B -> A`
- `B -> C`
- `C -> B`

### Mostly neutral pair with one loss

`C -> A`:

- seeds `13`, `23`, `37`, `79`: identical
- seed `51`: enabled lost `1` exact match and `0.0556` mean bit accuracy

Aggregate for `C -> A`:

- `sum_delta_exact_matches = -1`
- `mean_delta_mean_bit_accuracy = -0.0111`

## Large-Topology Slice

Both tested large-topology pairs were fully identical across seeds `13/23/37`:

- `cvt1_task_a_large -> cvt1_task_b_large`
- `cvt1_task_a_large -> cvt1_task_c_large`

For both pairs:

- `sum_delta_exact_matches = 0`
- `mean_delta_mean_bit_accuracy = 0.0`
- `mean_delta_best_rolling_exact_rate = 0.0`

## Interpretation

This widened sweep supports a stronger version of the earlier claim:

- the evidence-confirmation gate is substantially safer than the earlier flat recognition bonus

But it is not perfectly neutral in every case.

The `C -> A`, seed `51` exception suggests there may still be a narrow case where confirmed recognition is slightly too permissive, possibly when:

- prior transform-family evidence is real enough to activate the gate
- but the carried family is still misaligned for a subset of the new context structure

So the next step should probably be targeted rather than broad:

- diagnose the `C -> A`, seed `51` exception at the selector-interaction level
- check whether confirmation should incorporate a stronger contradiction discount or family-specific disambiguation signal in that transfer direction

## Commands

Used an ad hoc sweep comparing recognition enabled vs disabled for the selected pair/seed combinations, plus a direct recheck of the one negative exception:

```text
stage-1 directed matrix over seeds 13/23/37/51/79
large-topology A->B and A->C over seeds 13/23/37
recheck: cvt1_task_c_stage1 -> cvt1_task_a_stage1, seed 51
```
