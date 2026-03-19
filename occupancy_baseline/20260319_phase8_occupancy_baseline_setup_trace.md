# Phase 8 Occupancy Baseline Setup Trace - 2026-03-19

**Timestamp**: 2026-03-19 UTC  
**Model**: GPT-5.2-Codex

## Intent

Create a separate traditional-neural-network workspace for the first real-world comparison task so the occupancy benchmark does not get mixed into the existing CVT-1 synthetic comparison code.

## Hypotheses tested during implementation

1. The baseline folder should live under `Phase 8/` rather than the repo root.
   - Result: accepted. The work is conceptually a Phase 8 comparison track, not a new cross-phase subsystem.

2. The first setup should include more than an empty folder.
   - Result: accepted. Added a small runnable scaffold: dataset loader, rolling-window builder, pure-Python MLP, CLI runner, and tests.

3. The first baseline should avoid heavyweight dependencies.
   - Result: accepted. The setup uses the standard library only so the scaffold runs even in minimal environments.

## Frictions encountered

- The exact occupancy dataset file path is not yet fixed, so the runner must be data-path driven rather than preset-driven.
- The first comparison problem is real-world, but the current Phase 8 harnesses are synthetic and routing-native, so keeping a separate folder reduces conceptual bleed.

## Decisions promoted to maintained substrate

- Real-world neural baselines should live in their own Phase 8 subfolder when they target a separate benchmark family.
- The first occupancy baseline should keep preprocessing explicit and inspectable: CSV schema, normalization, windowing, and metrics should all be transparent.
- The baseline setup should remain dependency-light until the dataset contract and comparison protocol stabilize.
