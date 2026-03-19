# 2026-03-19 1141 - C3 Self Selected vs Fixed Latent Comparison

## Question

After the uncertainty-weighted context and partial sequence-persistence passes, why does `C3` `fixed-latent` still outperform `self-selected` so strongly?

## Method

Ran the benchmark node probe side by side on `C3 / task_a / seed 13` with:

- `self-selected` on the visible scenario
- `fixed-latent` on the latent scenario

using:

```powershell
python -m scripts.diagnose_benchmark_node_probe --benchmark C3 --method self-selected --seed 13 --tasks task_a --cycles 80
python -m scripts.diagnose_benchmark_node_probe --benchmark C3 --method fixed-latent --seed 13 --tasks task_a --cycles 80
```

Then compared source-node (`n0`) summaries plus early cycles and the latent-activation window.

## Main Result

`fixed-latent` is much better on the current code path:

- `self-selected`: exact-match `0.19444`, mean bit accuracy `0.6013`
- `fixed-latent`: exact-match `0.49074`, mean bit accuracy `0.8063`

The source behavior is qualitatively different:

- `self-selected` route transforms:
  - `rotate_left_1`: `60`
  - `xor_mask_1010`: `18`
  - `xor_mask_0101`: `2`
- `fixed-latent` route transforms:
  - `xor_mask_1010`: `41`
  - `xor_mask_0101`: `36`
  - `rotate_left_1`: `3`

This is not mostly a prediction-availability gap:

- `self-selected` first prediction cycle: `1`
- `fixed-latent` first prediction cycle: `1`

It is also not a simple latent-confidence gap:

- `self-selected` mean latent-context confidence: `0.51929`
- `fixed-latent` mean latent-context confidence: `0.16513`

So `fixed-latent` is not winning because its latent estimate is stronger in the naive sense.

## Early Window Reading

Cycles `1-6` are broadly similar. Both methods begin to follow the source-sequence transform hints.

The major separation starts around cycle `7`:

- `self-selected` begins drifting into repeated `rotate_left_1` selections
- `fixed-latent` keeps alternating with the XOR-family hints

Example:

- cycle `7`
  - `self-selected`: pre-sequence hint favors `xor_mask_0101`, but chosen transform is `rotate_left_1`
  - `fixed-latent`: chooses `xor_mask_0101`
- cycle `9`
  - `self-selected`: pre-sequence hint favors `rotate_left_1`, but it is already in a mixed/sticky regime and later keeps collapsing back into rotate
  - `fixed-latent`: still follows the alternating family cleanly

The source summary captures this:

- `self-selected` pre-sequence guidance match rate: `0.34615`
- `fixed-latent` pre-sequence guidance match rate: `0.69231`

## Activation Window Reading

The clearest surprise is around cycles `40-55`.

`self-selected`:

- latent support rises sharply
- latent capability turns on at cycle `46`
- prediction stays active throughout
- but the chosen transform remains almost entirely `rotate_left_1`

Representative window:

- cycle `45`
  - pre-sequence hint favors `rotate_left_1`
  - chosen transform: `rotate_left_1`
  - latent support: `0.36347`
- cycle `46`
  - pre-sequence hint favors `xor_mask_1010`
  - chosen transform: `rotate_left_1`
  - latent capability enabled: `1.0`
- cycle `47`
  - pre-sequence hint favors `xor_mask_0101`
  - chosen transform: `rotate_left_1`
- cycles `48-55`
  - latent support saturates toward `1.0`
  - chosen transform stays `rotate_left_1`

`fixed-latent` in the same window:

- latent capability is already on from cycle `1`
- chosen transforms continue to alternate with the XOR-family sequence hints
- prediction expected delta and expected match ratio are generally higher than `self-selected`

## Most Important Diagnosis

The current bottleneck is not:

- missing prediction
- missing latent activation
- low latent confidence

The stronger diagnosis is:

`self-selected` visible-scenario `C3` still falls into a stable context-0 / rotate-left attractor before latent capability becomes behaviorally decisive, and once latent support rises it does not pull transform selection back out of that attractor.`

Two details support that reading:

1. `self-selected` source latent estimate is effectively stuck on `0` throughout the activation window, even while source-sequence estimates continue to alternate.
2. `fixed-latent` does much better while carrying lower average latent confidence, which suggests the advantage is selector regime / scenario geometry, not confidence magnitude by itself.

## Implication

This comparison suggests the next useful question is not "how do we raise latent pressure further?"

It is closer to:

- how does the visible-scenario `C3` path bias the source latent estimate toward a stable context too early?
- and how can self-selected latent use keep transform-family competition open long enough for multistate ambiguity to matter?

In other words, the remaining gap looks more like a visible-path latent-use problem than a raw prediction or activation problem.
