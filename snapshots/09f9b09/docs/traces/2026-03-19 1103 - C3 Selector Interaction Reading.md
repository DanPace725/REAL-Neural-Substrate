# 2026-03-19 1103 - C3 Selector Interaction Reading

## Why

The `C3` latent-activation diagnosis showed:

- latent now activates a bit earlier
- but source transform choice does not change in the activation window

This trace records the code-level explanation of how the relevant selector signals currently interact.

## What Was Inspected

Read the source selector path in [phase8/selector.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/selector.py), especially:

- `_score_route(...)`
- `_prediction_route_bias(...)`
- `_effective_context(...)`
- `_effective_context_action_support(...)`

Also captured route-score breakdowns for `C3 / task_a / self-selected / seed 13` around cycles `44-50`, spanning the new latent activation point.

## Main Finding

The critical interaction is:

1. once the selector has an effective context bit
2. it leaves the hidden-task / sequence-hint-heavy path
3. and it falls into a context-weighted task-affinity + history + contextual-support regime
4. where `rotate_left_1` dominates before latent activation can change the chosen transform family

## How The Signals Currently Work Together

### 1. Sequence hints matter mostly in hidden-task commitment mode

Inside `_score_route(...)`, `source_sequence_hint` is used strongly only when:

- `head_has_task >= 0.5`
- `head_has_context < 0.5`
- `effective_has_context < 0.5`

That is the `hidden_task_commitment` branch.

In that branch:

- sequence hint can directly increase `task_transform_bonus`
- sequence hint can increase `source_pre_effective_route_drive`
- wrong-family transforms can be penalized through `hidden_wrong_family_penalty`

So this is the regime where sequence evidence has its clearest influence.

### 2. Once effective context resolves, the selector changes regimes

When `effective_has_context >= 0.5`, `_effective_context(...)` returns a real `context_bit` and `context_weight`.

Then the selector starts leaning on:

- `task_transform_affinity`
- `history_transform_evidence`
- contextual action support from substrate
- context feedback credit / debt
- branch-context credit / debt
- visible task compatibility / incompatibility terms

At that point, the sequence-hint-specific path is no longer the main driver.

### 3. In the C3 activation window, rotate-left already owns the transform family race

In the inspected cycles `44-50`:

- chosen action is always `route_transform:n4:rotate_left_1`
- the top competitor is also `rotate_left_1`, just on a different neighbor

That means the main competition is no longer:

- `rotate_left_1` vs `xor_mask_1010` / `xor_mask_0101`

It has already become:

- `rotate_left_1 on n4` vs `rotate_left_1 on n1/n3`

So the transform-family choice is effectively settled before neighbor choice happens.

### 4. Why rotate-left dominates in that window

Representative chosen-action breakdowns around cycles `44-50` show:

- `raw_task_transform_affinity = 1.0`
- `raw_history_transform_evidence = 0.686 -> 1.0`
- `task_transform_bonus_term = 0.08`
- `history_transform_term = 0.1098 -> 0.16`
- `feedback_credit_term ~= 0.05 -> 0.086`
- `context_feedback_credit_term ~= 0.11 -> 0.25`
- `raw_context_action_support ~= 0.14 -> 0.43`

By contrast, prediction terms are much smaller:

- `prediction_delta_term ~= 0.003 -> 0.006`
- `prediction_coherence_term ~= 0.0006 -> 0.0011`

So even though prediction is real and active, it is nowhere near large enough to overturn the transform-family advantage already accumulated for `rotate_left_1`.

## Why The Earlier Latent Activation Did Not Change Behavior

The important point is not merely "latent activated but selector ignored it."

It is more specific:

- latent activation occurs after the selector has already consolidated a strong context-compatible `rotate_left_1` policy
- once effective context is available, the selector exits the sequence-heavy hidden-task regime
- then task affinity, transform history, context action support, and context feedback reinforce the same family

So earlier latent activation by itself is not enough if the resolved latent/effective context feeds the selector into a regime that already strongly prefers `rotate_left_1`.

## Likely Structural Interpretation

The current `C3` bottleneck is probably one of these:

1. **Latent estimate semantics are too collapsed.**
   If the resolved latent/effective context lands on `context_bit = 0` in a way that maps to `rotate_left_1`, then activating latent earlier only locks that family in earlier.

2. **Sequence evidence loses too much authority once context resolves.**
   The selector currently treats sequence hints as an early hidden-task cue rather than an ongoing competitor to the resolved context estimate.

3. **Transform history becomes self-reinforcing too quickly.**
   Once `history_transform_evidence_rotate_left_1` reaches `1.0`, the family race is largely over unless something explicitly pushes against it.

## Best Next Step

The next most informative move would be a narrow diagnostic or change in one of two directions:

1. keep sequence evidence alive longer after latent activation on `C3`, so resolved context does not immediately drown it out
2. inspect whether the latent/effective context estimate itself should remain more plural or uncertainty-weighted on `C3`, instead of collapsing quickly into a single context bit

This trace strongly suggests the next bottleneck is **selector integration after latent activation**, not capability recruitment timing alone.
