# 2026-03-24 1310 - B Scale Suite Start

## Purpose

This trace records the first dedicated B-family scale pass.

The design goal was to avoid reusing the mixed ceiling ladder as a stand-in for
"B scaling" and instead hold one hidden-memory rule fixed while scaling topology
and horizon in the same style as the new A-family scale suite.

For the first pass, the chosen lane is:

- `memory_window = 2`
- binary hidden state = parity over the previous two packets
- visible context path exposes that binary state directly
- latent path must infer it from sequence history

This corresponds most closely to the original `B2` task structure, so the new
lane uses benchmark ids `B2S1` through `B2S6`.

## What Was Added

- new harness: `scripts/compare_b_scale_suite.py`
- new tests: `tests/test_b_scale_suite.py`

The harness currently supports:

- a parameterized hidden-memory window (`--memory-window`, default `2`)
- six scale points:
  - `B2S1`: 6 nodes, 18 examples
  - `B2S2`: 10 nodes, 36 examples
  - `B2S3`: 30 nodes, 108 examples
  - `B2S4`: 50 nodes, 216 examples
  - `B2S5`: 75 nodes, 432 examples
  - `B2S6`: 100 nodes, 864 examples
- the same runtime/commitment metrics used in the A-scale harness

## Design Choices

1. Scale the B task family by fixing one memory rule.

The existing ceiling B family changes the hidden-memory depth from 1 to 8. That
is useful for finding a memory-depth frontier, but it does not isolate scaling.
This harness instead fixes the memory rule and scales only topology/horizon.

2. Start with the `B2` lane.

The `2`-packet parity version is the most stable entry point because it already
has a known baseline in the March 18 work. If this lane behaves sensibly, later
passes can add `memory_window = 4` or `8`.

3. Keep visible and latent modes in the same run.

The visible path is still important here even though it receives the context bit,
because it gives a clean "best available B-family cold-start" comparison against
the latent path on the same scaled topology.

## Validation

Validation commands:

- `C:\Python313\python.exe -m py_compile scripts\compare_b_scale_suite.py tests\test_b_scale_suite.py`
- `C:\Python313\python.exe -m unittest tests.test_b_scale_suite`
- `C:\Python313\python.exe -m scripts.compare_b_scale_suite --memory-window 2 --benchmarks B2S5 --tasks task_a --methods fixed-visible fixed-latent growth-visible growth-latent --seeds 13 --output docs\experiment_outputs\b2_scale_b2s5_seed13_initial_20260324.json`

## First B-Scale Result: `B2S5`

Run:

- benchmark: `B2S5`
- topology: 75 nodes, depth 11
- workload: 432 examples
- task: `task_a`
- seed: `13`

Results:

| Method | Exact match rate | Bit accuracy | Criterion | Elapsed |
|---|---:|---:|---:|---:|
| `growth-visible` | **0.7870** | **0.8600** | **1.0** | 116.9s |
| `fixed-visible` | 0.7523 | 0.8507 | **1.0** | 51.1s |
| `fixed-latent` | 0.3657 | 0.6296 | 0.0 | **44.0s** |
| `growth-latent` | 0.3495 | 0.6273 | 1.0 | 126.9s |

Additional notes:

- `growth-visible` added only `1` dynamic node
- `fixed-visible` remained very strong and much cheaper than `growth-visible`
- latent modes were substantially weaker than visible at this point

## Interpretation

The first `B2S5` run suggests a different scale story than the clean A lane:

1. Visible modes remain the dominant cold-start path.

This matches the earlier family-level map: when the visible context bit cleanly
identifies the current binary memory state, the visible path retains a large
advantage over the latent path.

2. `growth-visible` can still improve quality, but the cost premium is large.

At `B2S5`, `growth-visible` slightly outperformed `fixed-visible` on task quality,
but took more than twice as long in wall-clock time.

3. Latent scaling is not yet strong on this lane.

`fixed-latent` and `growth-latent` both stayed far below the visible modes on
exact-match rate, even though the latent path was still fast enough to be runnable.

## Immediate Next Step

The most useful next B-scale pass is probably:

1. a `B2S6` one-seed visible comparison (`fixed-visible` vs `growth-visible`), or
2. a `B4`-style lane where the hidden-memory window itself is larger and the scale
   question becomes meaningfully harder for the latent path.
