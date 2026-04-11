# 2026-03-19 0905 - Evidence Confirmation Generalization Sweep

## Summary

Ran a small post-fix generalization sweep for the evidence-confirmed transform-recognition gate.

Goal:

- check that the new confirmation-gated selector does not reintroduce harmful divergence outside the original single-seed `A -> B` probe

Scope:

- seeds: `13`, `23`, `37`
- transfer pairs:
  - `cvt1_task_a_stage1 -> cvt1_task_b_stage1`
  - `cvt1_task_a_stage1 -> cvt1_task_c_stage1`
  - `cvt1_task_b_stage1 -> cvt1_task_c_stage1`

For each pair and seed, compared:

- recognition bias enabled
- recognition bias disabled

## Result

Across all `9` pair/seed combinations:

- `delta_exact_matches = 0`
- `delta_mean_bit_accuracy = 0.0`
- `delta_best_rolling_exact_rate = 0.0`

So within this lightweight sweep, the confirmation-gated recognition path is behaviorally neutral relative to disabling the recognition bonus entirely.

## Detailed Readout

### A -> B

- seed `13`: identical at `13` exact, `0.8056` mean bit accuracy
- seed `23`: identical at `3` exact, `0.3889` mean bit accuracy
- seed `37`: identical at `10` exact, `0.6389` mean bit accuracy

### A -> C

- seed `13`: identical at `3` exact, `0.5278` mean bit accuracy
- seed `23`: identical at `10` exact, `0.5556` mean bit accuracy
- seed `37`: identical at `7` exact, `0.5833` mean bit accuracy

### B -> C

- seed `13`: identical at `5` exact, `0.5833` mean bit accuracy
- seed `23`: identical at `8` exact, `0.6667` mean bit accuracy
- seed `37`: identical at `2` exact, `0.4444` mean bit accuracy

## Interpretation

This is a good stability result.

The evidence-confirmation gate appears to have removed the earlier harmful recognition-only influence without introducing new behavior drift in this small transfer sweep.

What this does **not** show yet:

- that the gate actively improves transfer
- that the same neutrality will hold on larger or more ambiguous topologies

But it does support the narrower claim:

- confirmation-gated recognition is safer than the earlier flat recognition bonus

## Command Shape

Used a small ad hoc sweep that reproduced the warm-transfer comparison with recognition bias toggled on/off for the selected pair/seed combinations.
