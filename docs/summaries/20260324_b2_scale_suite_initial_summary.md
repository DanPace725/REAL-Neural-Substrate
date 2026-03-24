# B2 Scale Suite Initial Summary

**Date:** 2026-03-24  
**Scope:** first dedicated B-family scale pass with fixed hidden-memory rule  
**Harness:** `scripts/compare_b_scale_suite.py`  
**Memory lane:** `memory_window = 2` (`B2`)

## Goal

The purpose of this pass was to scale a single B-family hidden-memory rule across
larger topologies and longer horizons, instead of mixing scale with changing
memory depth as the ceiling ladder does.

This lane keeps the core task structure fixed:

- hidden state = parity over the previous two packets
- visible path receives that binary state as context
- latent path must infer it sequentially

## Benchmark Points Used So Far

| Benchmark | Nodes | Examples | Depth | Notes |
|---|---:|---:|---:|---|
| `B2S5` | 75 | 432 | 11 | first generated aspirational hidden-memory scale point |
| `B2S6` | 100 | 864 | 10 | second generated aspirational hidden-memory scale point |

## Data Files

- `docs/experiment_outputs/b2_scale_b2s5_seed13_initial_20260324.json`
- `docs/experiment_outputs/b2_scale_b2s6_seed13_fixed_vs_growth_visible_20260324.json`

## B2S5 Results

### `B2S5` task_a, seed 13

| Method | Exact match rate | Bit accuracy | Criterion rate | Elapsed |
|---|---:|---:|---:|---:|
| `growth-visible` | **0.7870** | **0.8600** | **1.0** | 116.9s |
| `fixed-visible` | 0.7523 | 0.8507 | **1.0** | 51.1s |
| `fixed-latent` | 0.3657 | 0.6296 | 0.0 | **44.0s** |
| `growth-latent` | 0.3495 | 0.6273 | **1.0** | 126.9s |

### B2S5 takeaways

- Visible modes were clearly stronger than latent modes.
- `growth-visible` had a small quality edge over `fixed-visible`.
- That edge came at more than `2x` the wall-clock cost.
- Latent modes were much weaker than visible even though they remained runnable.

## B2S6 Results

### `B2S6` task_a, seed 13

| Method | Exact match rate | Bit accuracy | Criterion rate | Elapsed |
|---|---:|---:|---:|---:|
| `fixed-visible` | **0.8079** | **0.8854** | **1.0** | **108.7s** |
| `growth-visible` | 0.5602 | 0.7350 | **1.0** | 305.4s |

### B2S6 takeaways

- The pattern flipped at the next scale point.
- `fixed-visible` became clearly stronger than `growth-visible`.
- `growth-visible` was about `2.8x` slower and also substantially worse.
- Growth added `3` dynamic nodes in this run, but that structural activity did
  not improve task performance.

## Cross-Point Interpretation

The first B-scale story is already distinct from the A-scale story:

1. Visible modes remain the dominant cold-start path.

This matches the earlier repo-level B-family interpretation: when the visible
context cleanly reflects the current binary memory state, the visible path has a
major advantage over the latent path.

2. Latent scaling is currently weak on this lane.

At `B2S5`, both latent modes were far behind the visible modes. That makes the
current B2 scale lane very different from the clean A lane, where latent modes
remained more competitive.

3. Growth-visible does not scale monotonically here.

At `B2S5`, it slightly outperformed `fixed-visible`.
At `B2S6`, it underperformed badly while also costing much more runtime.

So on this hidden-memory lane, growth appears less stable as scale increases than
it was on the clean visible-context A lane.

## Practical Read

For the current B2 scale lane on consumer hardware:

- `fixed-visible` is the strongest practical mode so far.
- `growth-visible` may help at intermediate scale points, but it is not reliable
  enough to treat as the default.
- latent modes are presently weak enough that they should be treated as
  comparison paths, not preferred B2 scaling modes.

## Next Recommended Step

The next most informative follow-up is likely one of:

1. a small 2-seed confirmation run on `B2S6` `fixed-visible`, or
2. a new `B4` lane where the hidden-memory window is larger and the scaling
   problem becomes meaningfully harder for the visible path as well.
