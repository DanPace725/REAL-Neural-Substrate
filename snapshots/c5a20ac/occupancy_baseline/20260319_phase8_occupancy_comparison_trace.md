# 2026-03-19 - Phase 8 occupancy comparison trace

**Model:** GPT-5.2-Codex

## Goal
Resume the interrupted occupancy comparison work by turning the first single-seed comparison harness into a repeatable comparison runner that can report how the REAL path behaves across multiple selector seeds.

## Hypotheses tested
1. The comparison runner should keep the frozen traditional baseline artifact constant while varying only the REAL selector seed.
   - Result: accepted. The new series runner executes the same preset-level baseline once per run configuration and aggregates REAL train/eval summaries across the requested selector seeds.

2. The comparison output should expose the gap to the baseline explicitly instead of forcing later readers to calculate it by hand.
   - Result: accepted. Each run now records `baseline_metrics` plus `eval_minus_baseline` deltas for overlapping metrics like accuracy, and the series result aggregates those deltas across seeds.

3. The CLI should support both one-off debugging and repeated comparison runs without a second script.
   - Result: accepted. `compare_occupancy_baseline.py` now supports either a single `--selector-seed`, an explicit `--selector-seeds ...` list, or a built-in `--default-series-seeds` mode.

## Friction encountered
- The original comparison result structure only stored the full baseline artifact and two REAL summaries, which made it awkward to answer the obvious question: “how far behind or ahead is REAL on the metric we actually share?”
- The original CLI only covered one seed at a time, so it was easy to over-read a single selector trajectory as “the comparison result.”

## Decisions promoted
- The occupancy comparison path should distinguish three levels of reporting: raw baseline artifact, per-seed REAL comparison run, and multi-seed aggregate comparison summary.
- Repeated comparison runs should vary selector seed only unless a future experiment intentionally changes another configuration dimension.
- Shared metrics should be compared explicitly in the artifact as deltas rather than left implicit in separate JSON branches.
