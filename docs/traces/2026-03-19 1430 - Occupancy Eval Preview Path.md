# 2026-03-19 1430 - Occupancy Eval Preview Path

## Intent

Answer the practical question: how do we get occupancy-task evaluation signal without paying for a full held-out tail run that mostly repeats the same empty-class behavior at the front of the eval split?

## Decision

Add a small held-out preview mode that selects the first `N` eval episodes for each occupancy label from the existing post-split eval tail.

For this pass, the public CLI flag is:

```bash
--eval-preview-per-label N
```

This keeps the baseline protocol and chronological train/eval split intact while making tiny review runs actually evaluative for both `empty` and `occupied`.

## Why this is preferable to the previous tiny tail slice

- The prior `--max-eval-episodes 2` shortcut only took the first two held-out tail episodes.
- On the synthetic benchmark, those earliest held-out episodes are both `empty`, which makes tiny-slice accuracy look better than the occupied-class behavior actually is.
- A per-label preview preserves the held-out boundary but forces minimal class coverage, which is what we need for reviewable occupancy behavior.

## Review command

```bash
python -m scripts.compare_occupancy_baseline \
  --preset synth_v1_default \
  --selector-seed 13 \
  --max-train-episodes 3 \
  --eval-preview-per-label 1 \
  --output docs/experiment_outputs/occupancy_comparison_preview_20260319.json
```

## Result summary

- The saved preview manifest now evaluates one held-out empty episode and one held-out occupied episode.
- In this tiny preview, the frozen MLP baseline scores perfectly on the two selected held-out examples.
- The sampled REAL run with selector seed `13` predicts the empty episode correctly but misses the occupied episode, yielding preview accuracy `0.5` and occupied recall `0.0`.

## Design constraint check

- No global loss or backprop path was added to the REAL side.
- The change only affects how we select a tiny held-out review slice.
- The full tail evaluation path remains available and unchanged when `--eval-preview-per-label` is omitted.
