# 2026-03-19 1058 - C3 Latent Activation Window Diagnosis

## Context

The prediction-coupled capability pass moved `C3` self-selected latent activation earlier:

- before: first latent capability cycle `47`
- after: first latent capability cycle `45`

But the lightweight `A1/B2/C3` smoke slice did not improve.

This trace checks the obvious next question:

> does the earlier latent activation actually change source route/transform choice on `C3`?

## What Was Examined

Used the updated benchmark-node probe on:

- benchmark: `C3`
- task: `task_a`
- method: `self-selected`
- seed: `13`
- cycle limit: `80`

Focused on the source node around cycles `38-55`, which straddle the new activation point.

Also compared three windows:

- `pre_activation`: cycles `28-44`
- `activation_window`: cycles `45-55`
- `post_window`: cycles `56-80`

## Main Result

The earlier latent activation is real, but it does **not** change the source transform policy in the activation band.

### Cycle-by-cycle pattern

From cycles `38-55`:

- source transform stays almost entirely `rotate_left_1`
- latent support rises steadily and crosses activation at cycle `45`
- latent support then saturates rapidly to `1.0`
- prediction confidence remains moderate (`~0.45-0.59`)
- prediction expected delta remains positive but modest (`~0.09-0.17`)
- prediction expected match ratio is often only middling (`~0.52-0.60`, with a few `1.0` spikes)
- `pre_source_sequence_transform_hint` continues alternating among transform families
- `pre_latent_context_estimate` is already `0` with rising confidence before and after activation

But despite all of that:

- cycle `45-55` still chooses `rotate_left_1` on every source route

### Window comparison

#### Pre-activation (`28-44`)

- count: `17`
- mean prediction confidence: `0.40623`
- mean prediction expected delta: `0.08859`
- mean latent support: `0.13329`
- latent-enabled cycles: `0`
- transforms:
  - `rotate_left_1`: `15`
  - `xor_mask_1010`: `2`

#### Activation window (`45-55`)

- count: `11`
- mean prediction confidence: `0.51551`
- mean prediction expected delta: `0.13132`
- mean latent support: `0.86447`
- latent-enabled cycles: `11`
- transforms:
  - `rotate_left_1`: `11`

#### Post window (`56-80`)

- count: `25`
- mean prediction confidence: `0.45759`
- mean prediction expected delta: `0.07371`
- mean latent support: `1.0`
- latent-enabled cycles: `25`
- transforms:
  - `rotate_left_1`: `25`

## Interpretation

This narrows the current bottleneck substantially.

The problem is probably **not**:

- lack of early prediction
- lack of latent recruitment
- or failure of latent support to persist once recruited

The problem looks more like one of these:

1. **Latent activation is not changing the operative source estimate enough to change action choice.**
   The source already shows `pre_latent_context_estimate = 0` with high confidence through the activation window, but transform choice does not move with the alternating sequence hints.

2. **Selector integration after latent activation is still too weak or too rigid.**
   Even once latent is enabled and support is high, the chosen transform policy remains effectively locked on `rotate_left_1`.

3. **The latent estimate itself may be collapsing into an unhelpful fixed context.**
   If the source latent path settles too quickly on a single context estimate, earlier activation alone will not help.

There is also a probe limitation worth noting:

- `expected_transform` stayed `null` in this inspected window because the current-cycle observable `latent_context_available` was not active even though `pre_latent_context_estimate` was present in `state_before`

That means the best immediate signal here is the invariant transform choice, not the route-transform match metric.

## Current Best Read

Earlier latent activation on `C3` is real but currently **non-operative** at the behavioral level.

It changes capability state:

- yes

It changes source transform choice in the critical window:

- not yet

## Best Next Step

The next most productive target is probably not more capability-pressure tuning.

It is a selector / latent-use diagnostic for `C3`, specifically:

- when latent is enabled, how much weight does `pre_latent_context_estimate` actually have against sequence hints, task affinity, and accumulated transform evidence?

That should tell us whether the next fix belongs in:

- latent estimate quality
- latent-to-selector integration
- or source-side transform bias resolution after activation
