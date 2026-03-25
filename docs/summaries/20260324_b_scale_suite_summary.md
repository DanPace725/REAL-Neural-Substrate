# B Scale Suite Summary

**Date:** 2026-03-24  
**Scope:** first dedicated B-family scale pass across two hidden-memory lanes  
**Harness:** `scripts/compare_b_scale_suite.py`

## Goal

The purpose of the B-scale work was to answer a cleaner question than the mixed
ceiling ladder allows:

- what happens when we hold one hidden-memory rule fixed
- then scale topology and horizon upward in the same style as the A-scale suite?

So far, two lanes have been probed:

- `B2` lane: parity over the previous `2` packets
- `B8` lane: parity over the previous `8` packets

## Why B Matters

Unlike the A-scale lane, B-family scaling is not just about routing headroom.
It asks whether the substrate can stay coherent when the correct transform
depends on a hidden sequential state.

That makes B a better test of "meaningful scaling" than A, but also a much more
difficult one to interpret if we mix several memory rules together. This suite
therefore scales each memory rule separately.

## Files

### B2 lane

- [b2_scale_b2s5_seed13_initial_20260324.json](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/experiment_outputs/b2_scale_b2s5_seed13_initial_20260324.json)
- [b2_scale_b2s6_seed13_fixed_vs_growth_visible_20260324.json](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/experiment_outputs/b2_scale_b2s6_seed13_fixed_vs_growth_visible_20260324.json)
- [20260324_b2_scale_suite_initial_summary.md](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/summaries/20260324_b2_scale_suite_initial_summary.md)

### B8 lane

- [b8_scale_b8s5_seed13_initial_20260324.json](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/experiment_outputs/b8_scale_b8s5_seed13_initial_20260324.json)
- [b8_scale_b8s6_seed13_fixed_vs_growth_visible_20260324.json](/C:/Users/nscha/Coding/Relationally%20Embedded%20Learning/REAL-Neural-Substrate/docs/experiment_outputs/b8_scale_b8s6_seed13_fixed_vs_growth_visible_20260324.json)

## B2 Lane

### `B2S5` task_a, seed 13

| Method | Exact match rate | Bit accuracy | Elapsed |
|---|---:|---:|---:|
| `growth-visible` | **0.7870** | **0.8600** | 116.9s |
| `fixed-visible` | 0.7523 | 0.8507 | **51.1s** |
| `fixed-latent` | 0.3657 | 0.6296 | 44.0s |
| `growth-latent` | 0.3495 | 0.6273 | 126.9s |

### `B2S6` task_a, seed 13

| Method | Exact match rate | Bit accuracy | Elapsed |
|---|---:|---:|---:|
| `fixed-visible` | **0.8079** | **0.8854** | **108.7s** |
| `growth-visible` | 0.5602 | 0.7350 | 305.4s |

### B2 interpretation

- Visible modes are clearly dominant on this lane.
- Latent modes are far behind and should be treated as comparison paths, not
  preferred scaling modes.
- `growth-visible` can help at an intermediate scale point (`B2S5`), but does
  not scale monotonically.
- By `B2S6`, `fixed-visible` is decisively better than `growth-visible` on both
  quality and runtime.

The practical read for the `B2` lane is:

- `fixed-visible` is the strongest and safest scaling mode
- `growth-visible` is not reliable enough to be the default

## B8 Lane

### `B8S5` task_a, seed 13

| Method | Exact match rate | Bit accuracy | Elapsed |
|---|---:|---:|---:|
| `fixed-visible` | **0.7361** | **0.8380** | 44.0s |
| `growth-visible` | 0.6319 | 0.7639 | 108.4s |
| `growth-latent` | 0.4051 | 0.6516 | 101.1s |
| `fixed-latent` | 0.4028 | 0.6539 | **40.4s** |

### `B8S6` task_a, seed 13

| Method | Exact match rate | Bit accuracy | Elapsed |
|---|---:|---:|---:|
| `growth-visible` | **0.3160** | **0.5961** | 577.9s |
| `fixed-visible` | 0.1794 | 0.5451 | **261.6s** |

### B8 interpretation

- At `B8S5`, `fixed-visible` is still the best mode.
- At `B8S6`, both visible modes degrade heavily, but `growth-visible` beats
  `fixed-visible`.
- So the deeper-memory lane behaves differently from the `B2` lane:
  growth becomes more useful again at the harder scale point, but the whole
  regime is much weaker and much more expensive.

The practical read for the `B8` lane is:

- the harder memory demand is exposing a real scaling difficulty
- `growth-visible` may help once the fixed-visible path starts collapsing
- but the cost is extremely high, and the resulting performance is still modest

## Cross-Lane Interpretation

The B-scale story is no longer one-dimensional.

### 1. Memory depth matters a lot

The `B2` and `B8` lanes do not scale in the same way.

- `B2S6`: `fixed-visible` wins decisively
- `B8S6`: `growth-visible` wins, but both methods are weak and expensive

So "B scaling" depends strongly on the hidden-memory depth being held constant.

### 2. Visible modes remain the center of gravity

Across all runs so far, the visible modes are still the best-performing paths.
The latent modes have not shown a compelling scaling advantage on B-family
cold-start conditions.

### 3. Growth becomes a rescue mechanism, not a clean default

On the easier `B2` lane, growth can help at some scale points but is unstable.
On the harder `B8` lane, growth becomes useful again at the largest point, but
only in a much weaker and slower regime.

That suggests a more nuanced framing:

- on B-family scale, growth is not the default best mode
- it may become valuable when fixed-visible begins to degrade under harder
  memory pressure

### 4. B is giving a more realistic scaling challenge than A

The A-family scale suite suggested that scale alone is not currently REAL's
first failure axis.

The B-family suite is already showing something closer to a real frontier:

- moderate hidden-memory scale remains workable
- deeper hidden-memory scale begins to degrade sharply
- the mode ordering can change as that pressure rises

## Current Working Summary

If someone asked today how REAL scales on hidden-memory tasks, the most accurate
short answer would be:

"REAL can scale meaningfully on B-family tasks, but the scaling story is mode-
and memory-depth-dependent. For moderate memory depth, fixed-visible remains the
strongest practical path. For deeper memory pressure, performance degrades
substantially, and growth-visible may recover some capability, but only at much
higher runtime cost."

## Next Recommended Step

The best next move is probably not another brand-new lane yet. The highest-value
follow-up would be one of:

1. a second-seed confirmation on `B8S6`, or
2. a compact compare doc that places A-scale and B-scale side by side so the
   repo has one clear "scaling story so far" summary.
