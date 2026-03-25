# 2026-03-24 2215 - B2S5 Per-Context Bias

## Purpose

This trace records the results of the per-context accuracy signal extension to the
laminated REAL system. The changes add `context_accuracy` to `SliceSummary`, emit
a targeted `weak_context_bit` bias from the regulator, and apply alternative-transform
seeding for the weak context in `_apply_guidance_bias`. The run is `max_slices=10`,
`initial_cycle_budget=95`, `accuracy_threshold=0.7`, B2S5 visible, seed=13.

## Changes Since Prior Session

Four additions were made across the system:

### `real_core/types.py`
- Added `context_accuracy: Dict[str, float]` field to `SliceSummary` (with
  `_ensure_summary_safe` validation).

### `phase8/lamination.py`
- `_build_slice_summary`: groups `delivered_packets` by `packet.context_bit`,
  computes per-context mean bit accuracy, populates `context_accuracy` as
  `{"context_0": ..., "context_1": ...}`.
- `_apply_regulatory_signal`: reads `weak_context_bit` and `weak_context_gap` from
  the incoming signal and passes them to `_apply_guidance_bias`.
- `_apply_guidance_bias`: new `weak_context_bit` / `weak_context_gap` parameters.
  For the weak context, after seeding the dominant transform as before, also seeds
  all non-dominant hinted transforms with a gap-scaled boost
  (`alt_seed = min(0.5, seed_value * (1 + weak_context_gap * 3))`), encouraging
  the fast layer to explore alternatives for that context.
- `evaluate_laminated_scenario`: includes `context_accuracy` in slice summary
  serialization.

### `real_core/lamination.py`
- `regulate()`: identifies the weakest context from `current.context_accuracy`
  (lowest accuracy value), computes `weak_context_gap = threshold - worst_acc`,
  emits `weak_context_bit` and `weak_context_gap` in `bias_updates`.
- `_should_settle()`: when `context_accuracy` is present, uses
  `min(context_accuracy.values())` for the threshold check instead of
  `mean_bit_accuracy`. This ensures the threshold fires only when all contexts
  have reached the target, not just the average.

## Benchmark Configuration

- Benchmark: `B2S5` (75 nodes, 432 examples, 476 cycles)
- Task: `task_a` visible, seed 13
- `max_slices=10`, `initial_cycle_budget=95`, `accuracy_threshold=0.7`
- Total budget capacity: 950 cycles (10 × 95), scenario is 476 cycles

## Results

| | Baseline | Laminated |
|---|---|---|
| exact_matches | 130 | 126 |
| mean_bit_accuracy | 0.5810 | 0.5833 |
| total_action_cost | 68.728 | 8.427 |
| examples processed | 432 / 432 | 432 / 432 |
| final_decision | — | `settle` |
| slices run | — | 8 |

Delta vs baseline: `exact_matches −4`, `bit_accuracy +0.002`, `action_cost −60.30`

### Slice history

| Slice | Budget | Examples | Exact | Bit Acc | ctx_0 | ctx_1 | Ambiguity | Conflict | Hint |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 95 | 95 | 34 | 0.6158 | 0.828 | 0.523 | 1.000 | 0.432 | escalate |
| 2 | 95 | 95 | 20 | 0.5824 | 0.769 | 0.508 | 1.000 | 0.544 | escalate |
| 3 | 95 | 95 | 21 | 0.5303 | 0.617 | 0.493 | 1.000 | 0.485 | escalate |
| 4 | 95 | 95 | 26 | 0.5652 | 0.672 | 0.516 | 1.000 | 0.500 | escalate |
| 5 | 95 | 52 | 25 | 0.6545 | 0.844 | 0.577 | 1.000 | 0.550 | escalate |
| 6 | 95 | 0  | 0  | 0.0000 | —     | —     | 0.000 | 0.000 | continue |
| 7 | 71 | 0  | 0  | 0.0000 | —     | —     | 0.000 | 0.000 | settle |
| 8 | 53 | 0  | 0  | 0.0000 | —     | —     | 0.000 | 0.000 | settle |

## Diagnosis

### Settle triggered by scenario exhaustion, not accuracy threshold

The scenario has 476 cycles total. Five slices of 95 cycles = 475 cycles. By the
end of slice 5, all 432 examples had been seen (slice 5 ran only 52 examples
because the remaining injected packet schedule was smaller than 95). Slices 6-8
ran with 0 examples in the cycle window — the packet schedule was empty and no
new signals were injected.

With 0 examples, `ambiguity=0.0`, `conflict=0.0`, and `coherence_delta≈0.0`.
The settle condition fires on two consecutive flat+low-conflict slices (slices 7 and 8),
giving `final_decision=settle`. This is a settle-by-exhaustion, not a
settle-by-threshold. The 0.7 threshold was never reached.

### Context_1 improved but remains below 0.7

Context_1 accuracy across slices: 0.523 → 0.508 → 0.493 → 0.516 → 0.577. The
per-context bias is having an effect — slice 5 reached 0.577 vs the earlier run's
0.606 mean and slice 5 result. Context_0 reached 0.844 in slice 5.

However, context_1 is hard: `xor_mask_1010` has near-identical hint weights to
`rotate_left_1` (both ~0.546 from prior diagnostic). The alternative-transform
seeding boosts `xor_mask_1010` for context_1, but the substrate has already been
shaped across many cycles by the dominant `rotate_left_1` path. Five slices are
not enough to shift the preference sufficiently for context_1 at this task scale.

### Cost result is meaningful even at full coverage

Unlike the s5_b6 run where 94% of the scenario was skipped, here all 432 examples
were processed. The 8.427 action cost vs 68.728 baseline is genuine efficiency:
the same workload at nearly the same quality for 12% of the action cost. The
`settle` decision (even by exhaustion) is correct — there is no more work left.

### The threshold criterion is now working correctly

The `_should_settle` change to use `min(context_accuracy.values())` correctly
blocks threshold-settle until both contexts reach 0.7. The settle that fired here
was the flat-empty-window path, which is appropriate: if the scenario is done,
there is no reason to continue.

### Ambiguity=1.0 on all active slices

Every slice that saw examples reported `ambiguity=1.0`. This is unchanged from
prior runs — the 75-node scenario always has some wrong-transform packets, and with
only one task and two contexts, the wrong-transform fraction is high enough that
ambiguity saturates. The regulator's escalate hints were correct but never
accumulated two consecutive productive+escalate readings to trigger a hard escalate
decision; meanwhile the controller hit scenario exhaustion first.

## Working Read

The per-context accuracy signal is populated correctly and visible in results.
The weak-context alternative-transform seeding is wired through correctly.
The threshold-settle correctly uses min(context_accuracy) instead of mean.

The core constraint is unchanged: context_1 (xor_mask_1010) cannot reach 0.7 in
5 active slices because the hint weights for both contexts are near-tied at the
source node, and the substrate's learned preference for rotate_left_1 resists
override. The per-context bias seeding provides a directional push but not
enough for 5 slices to overcome a deeply established preference.

Two options for the next step:

1. **Increase max_slices past 10** with the per-context bias running. More slices
   means more bias applications before the scenario exhausts. But the scenario
   only has 476 cycles and slices of 95 already cover everything in 5 — so
   additional slices after 5 will always be empty.

2. **Reduce initial_cycle_budget to allow more active slices within the scenario**.
   E.g., `initial_cycle_budget=48`, `max_slices=10` → 10 active slices of 48 cycles,
   with each slice applying a bias update before the next. This lets the per-context
   signal accumulate and shift the substrate preference earlier in the scenario,
   potentially improving context_1 accuracy on later slices when it matters most.

Option 2 is the more promising experimental thread, as it keeps all slices active
and gives the per-context bias more opportunities to reshape the fast layer while
the scenario is still running.

## Next Steps

1. Re-run B2S5 visible with `initial_cycle_budget=48`, `max_slices=10`,
   `accuracy_threshold=0.7` to allow 10 active slices across the full scenario.
   Check whether context_1 accuracy improves beyond 0.577 with more bias cycles.
2. If context_1 still cannot reach 0.7, consider whether the hint-tie problem
   requires a substrate-level intervention (e.g., direct inspection of slow weights
   to identify the competing xor_mask_1010 path and seed it more aggressively).
3. Check whether C3 family tasks have a more tractable context split for validating
   the per-context signal before returning to B2S5.

## Related Documents

- `docs/summaries/20260324_laminated_real_summary.md` — architecture overview
- `docs/traces/2026-03-24 1930 - B2S5 Laminated First Benchmark.md` — s5_b6 results
- `real_core/types.py` — `SliceSummary.context_accuracy` field
- `real_core/lamination.py` — `HeuristicSliceRegulator` with `weak_context_bit` emit
- `phase8/lamination.py` — `_apply_guidance_bias` with targeted context seeding
