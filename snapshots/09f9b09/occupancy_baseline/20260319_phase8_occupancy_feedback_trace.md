# Phase 8 Occupancy Feedback Trace - 2026-03-19

**Timestamp**: 2026-03-19 UTC  
**Model**: GPT-5.2-Codex

## Intent

Couple occupancy episode correctness back into local Phase 8 learning without introducing a global optimizer or forcing a deep rewrite of the environment.

## Hypotheses tested during implementation

1. Occupancy-specific feedback can be expressed as local edge events rather than a global gradient.
   - Result: accepted. Correctly routed occupancy packets now emit edge-by-edge feedback events along the route they actually used, and those events reuse the existing node-level feedback absorption path.

2. We should reward class-consistent decision paths before introducing explicit contradiction penalties.
   - Result: accepted for this slice. Correct decision-branch traffic receives local positive feedback first; negative occupancy-specific penalties can be added later if needed, but they are not assumed here.

3. The execution result should expose occupancy feedback metrics explicitly.
   - Result: accepted. `OccupancyEpisodeResult` and the aggregate summary now track feedback event counts and total feedback amount per episode.

## Frictions encountered

- The current environment owns feedback internally for sink scoring, so occupancy-specific class feedback had to be layered on top of that path at the wrapper level.
- It would have been easy to make stronger assumptions about class loss or explicit penalties, but this slice intentionally keeps the coupling narrow and local.

## Decisions promoted to maintained substrate

- Occupancy-specific learning signals should follow the actual route used by a packet, not a detached global target update.
- Positive local feedback is enough for the first occupancy-learning slice; stronger negative shaping should be introduced only after we inspect behavior.
- Occupancy execution summaries should report feedback volume explicitly so we can track whether the REAL path is actually receiving learning signal.
