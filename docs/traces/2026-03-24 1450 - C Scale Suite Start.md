# 2026-03-24 1450 - C Scale Suite Start

## Purpose

This trace records the first dedicated C-family scale pass.

The goal is to separate "can REAL scale on ambiguity-heavy C-family tasks?" from
the broader ceiling benchmark, which mixed ambiguity, hidden-state inference, and
scale changes into a single ladder. The new harness fixes the C3-style ambiguity
structure and scales topology and horizon in the same way as the new A- and
B-scale suites.

For the first pass, the chosen lane is:

- 4-state hidden controller derived from the previous two packets
- visible context collapsed to `state % 2`
- both visible branches ambiguous, matching the original `C3` ceiling structure
- scale points `C3S1` through `C3S6`

## What Was Added

- new harness: `scripts/compare_c_scale_suite.py`
- new tests: `tests/test_c_scale_suite.py`

The harness currently supports:

- six scale points:
  - `C3S1`: 6 nodes, 18 examples
  - `C3S2`: 10 nodes, 36 examples
  - `C3S3`: 30 nodes, 108 examples
  - `C3S4`: 50 nodes, 216 examples
  - `C3S5`: 75 nodes, 432 examples
  - `C3S6`: 100 nodes, 864 examples
- the same runtime and commitment reporting used in the A- and B-scale harnesses
- visible, latent, and growth REAL modes

## Design Choices

1. Start with a C3-style lane rather than C4.

`C4` is a harsher compound stress point because it adds scrambled visible context
and a larger topology shift at the same time. `C3` is the cleaner first lane for
answering whether scale changes anything when the bottleneck is already ambiguity.

2. Keep the ambiguity structure fixed.

The C-family question is not just whether REAL can solve a hard task. It is
whether larger ambiguous tasks remain coherent and whether any capability path
becomes more useful as the system scales. Fixing the ambiguity pattern lets the
suite answer that directly.

3. Reuse the A/B scale ladder shape.

Using the same `S1-S6` topology and horizon ladder makes later cross-family
comparison much easier. If A, B, and C all share the same size progression, then
quality and runtime differences are easier to interpret.

## Validation

Validation commands:

- `C:\Python313\python.exe -m py_compile scripts\compare_c_scale_suite.py tests\test_c_scale_suite.py`
- `C:\Python313\python.exe -m unittest tests.test_c_scale_suite`
- `C:\Python313\python.exe -m scripts.compare_c_scale_suite --benchmarks C3S5 --tasks task_a --methods fixed-visible fixed-latent growth-visible growth-latent --seeds 13 --output docs\experiment_outputs\c3_scale_c3s5_seed13_initial_20260324.json`

## First C-Scale Result: `C3S5`

Run:

- benchmark: `C3S5`
- topology: 75 nodes, depth 11
- workload: 432 examples
- task: `task_a`
- seed: `13`

Results:

| Method | Exact match rate | Bit accuracy | Criterion | Elapsed |
|---|---:|---:|---:|---:|
| `fixed-visible` | **0.2940** | 0.5625 | 0.0 | 51.7s |
| `fixed-latent` | 0.2755 | **0.5694** | **1.0** | **43.2s** |
| `growth-visible` | 0.2731 | 0.5486 | 0.0 | 128.6s |
| `growth-latent` | 0.2685 | 0.5648 | **1.0** | 108.5s |

Additional notes:

- visible and latent paths are very close on exact-match rate
- latent modes retain slightly better bit accuracy and a short-window criterion hit
- `growth-visible` added `2` dynamic nodes but remained weaker than `fixed-visible`
- the whole lane remains far below the clean A-family quality band

## Interpretation

The first `C3S5` result strongly reinforces the earlier March 18 C-family read:
the limiting factor here is still weak observability and ambiguity, not raw scale.

This run differs from the A- and B-family scale lanes in several important ways:

1. Scaling did not produce a clear dominant mode.

On A and B, visible fixed or visible growth usually separates from the pack. On
`C3S5`, all four REAL modes remain in the same general performance band.

2. Growth is not helping.

This fits the earlier diagnostic hypothesis that morphogenesis helps routing
headroom more than identifiability problems. Adding nodes does not repair a weak
or ambiguous local signal.

3. Latent still does not collapse, but it also does not cleanly solve the lane.

The latent modes remain competitive with visible modes and slightly better on bit
accuracy, which matches the older C-family pattern. But scale alone is not enough
to turn that into a strong solution.

## Working Read

At this point the C-family scale story looks different from both A and B:

- A-family: scale alone is comparatively friendly and growth-visible can help
- B-family: scaling depends strongly on hidden-memory depth and can flip which
  visible mode is best
- C-family: ambiguity remains the dominant bottleneck, and larger topology/horizon
  do not by themselves unlock a better capability path

That is useful evidence in its own right. It suggests REAL's current scaling
limits are family-dependent, and that "bigger" only helps when the bottleneck is
capacity or routing headroom rather than observation identifiability.

## Next Steps

1. Run `C3S6` visible vs latent, or visible vs growth-visible, to see whether the
   ambiguity-scale lane degrades further at the next aspirational point.
2. Consider a transfer-inclusive C-scale check after the cold-start shape is clear.
3. Compare A, B, and C scale summaries once the first C lane has at least two
   larger points on record.
