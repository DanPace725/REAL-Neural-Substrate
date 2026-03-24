# A Scale Suite Initial Summary

**Date:** 2026-03-24  
**Scope:** first dedicated A-family scale pass on generated `A5` and `A6` points  
**Harness:** `scripts/compare_a_scale_suite.py`

## Goal

The purpose of this pass was to separate clean scaling questions from the mixed
stressors used by the ceiling suite. A-family remains the best place to ask:

- does REAL stay coherent as topology and horizon increase?
- what is the runtime cost on consumer hardware?
- which current REAL mode is strongest under larger clean-task conditions?

## Benchmark Points

| Benchmark | Nodes | Examples | Depth | Notes |
|---|---:|---:|---:|---|
| `A5` | 75 | 432 | 11 | first generated aspirational scale point |
| `A6` | 100 | 864 | 10 | second generated aspirational scale point |

## Data Files

- `docs/experiment_outputs/a_scale_a5_seed13_23_visible_latent_selfselected_20260324.json`
- `docs/experiment_outputs/a_scale_a5_seed13_23_growth_visible_latent_20260324.json`
- `docs/experiment_outputs/a_scale_a6_seed13_fixed_vs_growth_visible_20260324.json`
- `docs/experiment_outputs/a_scale_a6_seed13_fixed_latent_20260324.json`

## A5 Results

### `A5` task_a, seeds 13/23

| Method | Exact match rate | Bit accuracy | Criterion rate | Mean elapsed |
|---|---:|---:|---:|---:|
| `growth-visible` | **0.8542** | **0.9062** | **1.0** | 118.3s |
| `fixed-visible` | 0.7234 | 0.8253 | **1.0** | 122.5s |
| `growth-latent` | 0.5347 | 0.7188 | **1.0** | 108.5s |
| `fixed-latent` | 0.5278 | 0.7309 | 0.5 | **43.6s** |
| `self-selected` | 0.3577 | 0.6111 | 0.0 | 75.3s |

### A5 takeaways

- `growth-visible` was the strongest current mode at this scale point.
- `fixed-visible` was also strong and fully reliable across the two seeds.
- `fixed-latent` was substantially faster but weaker.
- `self-selected` was clearly not ready for this scale point.
- Growth did not explode structurally:
  - `growth-visible` mean dynamic node count was only `0.5`
  - the benefit appears to come from selective useful growth, not runaway expansion

## A6 Results

### `A6` task_a, seed 13

| Method | Exact match rate | Bit accuracy | Criterion rate | Elapsed |
|---|---:|---:|---:|---:|
| `growth-visible` | **0.7188** | **0.8339** | **1.0** | 310.7s |
| `fixed-visible` | 0.5845 | 0.7564 | **1.0** | 118.7s |
| `fixed-latent` | 0.5058 | 0.7228 | **1.0** | **104.8s** |

### A6 takeaways

- REAL remained coherent at `100` nodes / `864` examples.
- `growth-visible` was still the strongest mode on task quality.
- The runtime tradeoff became much sharper:
  - `growth-visible` was about `2.6x` slower than `fixed-visible`
  - `fixed-latent` remained the fastest of the three tested modes
- Even at `A6`, growth remained small in structural terms:
  - `growth-visible` added only `1` dynamic node in this run

## Cross-Point Interpretation

The current scale story is already fairly clear:

1. Scale alone does not appear to be the first failure axis for REAL.
   Both `A5` and `A6` remained strong enough to reach criterion.

2. `growth-visible` is currently the best-performing mode on the clean A-scale lane.
   This is notable because earlier expectations were that cold-start growth would
   probably underperform. On these generated A-family scale tasks, it did not.

3. Runtime and task quality are beginning to separate.
   At `A5`, `growth-visible` and `fixed-visible` were fairly close in wall-clock cost.
   At `A6`, the quality advantage for `growth-visible` remained, but the runtime
   cost increased sharply.

4. `self-selected` is currently the weak point on this lane.
   The system can perform well at scale when the right mode is chosen, but the
   autonomous policy is not yet matching the best fixed configuration.

## Practical Read

On consumer hardware, the current evidence suggests:

- `fixed-visible` is the best practical default for larger clean A-family runs
  when runtime matters.
- `growth-visible` is the best current quality mode when longer runtime is acceptable.
- `fixed-latent` is a fast comparison mode, but not the strongest performer on
  this lane.

## Next Recommended Step

Before pushing beyond `A6`, the most useful next pass is probably:

1. a small multi-seed `A6` check for `fixed-visible` and `growth-visible`, or
2. a first B-family scale lane so scaling is tested under hidden-memory pressure
   rather than only clean visible-context conditions.
