# 2026-03-24 1130 - A Scale Suite Start

## Purpose

This trace records the first dedicated pass on an A-family scale-specific harness.
The goal was to separate "does REAL scale under cleaner task conditions?" from the
mixed pressure surface used by the ceiling benchmark suite.

The immediate design target was:

- preserve the existing `A1-A4` ladder exactly as-is
- add two larger aspirational points (`A5`, `A6`) without changing the registered scenarios
- report both task quality and runtime / substrate-commitment signals
- keep the first pass cold-start and REAL-only so the suite is fast enough to iterate on

## What Was Added

- New dedicated harness: `scripts/compare_a_scale_suite.py`
- New focused tests: `tests/test_a_scale_suite.py`

The harness includes:

- registered `A1-A4` cases from the existing ceiling benchmark suite
- generated `A5` and `A6` cases:
  - `A5`: 75 nodes, 432 examples
  - `A6`: 100 nodes, 864 examples
- configurable REAL methods:
  - `fixed-visible`
  - `fixed-latent`
  - `self-selected`
  - and the growth modes if requested explicitly
- runtime and commitment reporting per run:
  - wall-clock seconds
  - examples/sec
  - cycles/sec
  - memory entry count
  - pattern count
  - active edge count
  - context-support totals

## Design Choices

1. Keep A as the backbone scale lane.

The ceiling suite already showed that A-family is the least confounded scaling axis.
Unlike B and C, it does not mix scale with hidden-memory depth or observation ambiguity.

2. Extend A beyond the previous ceiling point without mutating the canonical scenario registry.

`A5` and `A6` are generated inside the new harness instead of being added to
`phase8_scenarios()`. That keeps the first pass lightweight and avoids turning a
new scale hypothesis into a repo-wide default before it is vetted.

3. Measure runtime directly, not just exact-match rate.

The main motivation for this suite is that a skeptical audience will ask whether
REAL scales on ordinary hardware. That means the suite must report operational
cost, not only task performance.

4. Stay cold-start first.

Carryover and transfer are important, but the first scale question is simpler:
"If we just make the clean A-family tasks larger, does REAL stay coherent and how
expensive does that get?"

## Initial Validation

Validation run list:

- `C:\Python313\python.exe -m py_compile scripts\compare_a_scale_suite.py tests\test_a_scale_suite.py`
- `C:\Python313\python.exe -m unittest tests.test_a_scale_suite`
- `C:\Python313\python.exe -m scripts.compare_a_scale_suite --benchmarks A5 --tasks task_a --methods fixed-visible --seeds 13`

Observed `A5` smoke result:

- benchmark: `A5`
- topology: 75 nodes, depth 11
- workload: 432 examples, 476 cycles, TTL 44
- method: `fixed-visible`
- seed: `13`
- elapsed: `108.8774s`
- throughput: `3.9678 examples/s`
- exact match rate: `0.6806`
- mean bit accuracy: `0.7963`
- criterion reached: `true`
- examples to criterion: `105`
- memory entry count: `2790`
- pattern count: `218`

This is only a first single-seed smoke run, but it is already useful:

- REAL did not collapse at the first generated aspirational point
- the runtime is substantial but still practical on consumer hardware
- the scale question now has a harness that can be extended without reusing the
  ambiguity- or memory-heavy families as stand-ins for scale

## Interpretation

The first `A5` run supports the earlier ceiling-suite intuition that scale alone
is not currently the clearest failure axis for REAL. The more likely near-term
breakpoints remain:

- hidden-memory depth under larger horizons
- ambiguity / weak observability
- operational cost as generated cases move from `A5` toward `A6` and beyond

That said, this suite is now the right place to make the scale story explicit
instead of inferring it indirectly from the broader ceiling harness.

## Next Steps

1. Run a small 2-seed or 3-seed pass on `A5` for `fixed-visible`, `fixed-latent`,
   and `self-selected`.
2. Smoke `A6` at one seed to find the next practical runtime band.
3. Add optional carryover mode later if the cold-start scale curve stays stable.
4. Only after that, decide whether B-family scaling should become the second lane.
