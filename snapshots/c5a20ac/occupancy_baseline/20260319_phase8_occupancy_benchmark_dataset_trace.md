# Phase 8 Occupancy Benchmark Dataset Trace - 2026-03-19

**Timestamp**: 2026-03-19 UTC  
**Model**: GPT-5.2-Codex

## Intent

Stabilize the traditional occupancy benchmark before starting REAL-specific mapping by checking in a reasonable synthetic dataset and the generator that produced it.

## Hypotheses tested during implementation

1. A checked-in synthetic benchmark is useful even if the long-term goal is a real external dataset.
   - Result: accepted. It gives us a stable regression target, consistent artifact shape, and a concrete task definition while the REAL mapping is still being designed.

2. The benchmark should preserve sequential structure rather than random independent rows.
   - Result: accepted. The generator emits a time-ordered 15-minute sequence over multiple days so later REAL work can respect temporal continuity.

3. The synthetic task should be correlated but not trivial.
   - Result: accepted. Occupancy influences multiple channels, and rare off-hours cleaning/light anomalies keep `light` from becoming a perfect shortcut.

## Frictions encountered

- Without a bundled real occupancy dataset, there is still an eventual handoff from synthetic benchmark to external benchmark.
- The task must stay simple enough for the traditional baseline while also remaining rich enough to justify careful REAL-side design.

## Decisions promoted to maintained substrate

- The checked-in occupancy benchmark should remain deterministic and regenerable from code.
- Sequential, office-like occupancy dynamics are the right initial bridge because they are easy to explain on the NN side and still meaningful for later REAL adaptation work.
- We should freeze the traditional benchmark definition before introducing any REAL-specific task encoding, so we do not accidentally move both targets at once.
