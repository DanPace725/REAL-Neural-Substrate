# Occupancy Comparison Preview Summary — 2026-03-19

## What the preview run actually measured

This manifest is **not** a miniature full benchmark. It is a deliberately tiny review slice built to answer a narrower question:

> when we force the held-out preview to include one empty episode and one occupied episode, what does the current REAL occupancy bridge do?

The run used:

- baseline preset: `synth_v1_default`
- REAL selector seed: `13`
- REAL train episodes: `3`
- held-out preview: `1` empty + `1` occupied episode

## What appears to be working

1. **The preview selection itself is doing the right thing.**
   - The preview manifest includes one held-out empty episode and one held-out occupied episode.
   - That means the quick review path is now genuinely evaluative for both labels instead of over-reading early empty-only tail examples.

2. **The baseline side is healthy on this slice.**
   - The frozen MLP baseline scores `1.0` accuracy / precision / recall / F1 on the two selected held-out examples.
   - So the preview examples themselves are not unusually ambiguous for the conventional model.

3. **The REAL bridge is at least routing enough traffic to make a decision.**
   - On the empty held-out episode (`1072`), REAL predicts correctly.
   - Delivery is not collapsing to zero: the eval episodes deliver `19` and `18` packets respectively.
   - So this is not a pure transport failure; the system is executing and producing stable branch preferences.

## What is not working yet

1. **Occupied-class recognition is not working in this tiny run.**
   - On the occupied held-out episode (`1084`), REAL predicts `empty`.
   - Preview accuracy is therefore `0.5`, and occupied recall is `0.0`.

2. **The decision policy is strongly biased toward `decision_empty`.**
   - For the occupied eval episode, only `3` delivered packets vote for `decision_occupied`, while `15` vote for `decision_empty`.
   - This means the system is not merely uncertain; it is routing most evidence down the wrong class branch.

3. **The training slice is extremely biased.**
   - All three training episodes in this preview run have label `0` (`empty`).
   - So the preview is mostly telling us what happens after a very small empty-only warmup, not after even a minimally balanced occupancy training pass.

## How to interpret the delta to baseline

The preview delta block (`accuracy -0.5`, `precision -1.0`, `recall -1.0`, `f1 -1.0`) should be read as:

- the preview-aware baseline gets both held-out preview examples right
- REAL gets only the empty one right
- the occupied miss is doing almost all of the damage

This is a meaningful warning sign, but it is **not** the same claim as “REAL fails the occupancy task in general.”
It means:

- the current bridge does **not** show occupied-class competence under this tiny empty-heavy training budget
- the new preview mode successfully reveals that weakness instead of hiding it behind empty-only eval examples

## Practical takeaway

The recent manifest tells us two things at once:

- **methodologically:** the preview workflow is now good enough for quick evaluative inspection
- **substantively:** the current REAL occupancy bridge still lacks usable occupied-class discrimination under a tiny training budget, and its packet votes remain skewed toward the empty branch

So the run is useful precisely because it exposes a real failure mode quickly, without needing the full held-out tail.
