# 2026-03-19 1405 - Occupancy Bridge Port

**Model:** GPT-5.4

## Goal
Port the transplanted occupancy baseline work into the standalone repo in a way that respects the current Phase 8 boundaries instead of reintroducing old-repo assumptions.

## Hypotheses tested
1. The first occupancy bridge can live mostly at the experiment layer without rewriting `phase8/environment.py`.
   - Result: accepted. The port uses a dedicated comparison harness plus a wrapper-level REAL runner that builds occupancy episodes from the same normalized rolling windows and drives the existing Phase 8 system through direct packet injection.

2. We can preserve the old fairness argument while staying inside the current 4-bit packet model.
   - Result: accepted for this slice. Each occupancy window becomes a 25-packet episode: one packet per sensor reading, 4-bit one-hot bucketed from the normalized scalar value, with sensor identity carried by the injection node and temporal order preserved by packet order.

3. Occupancy supervision can remain local rather than becoming a hidden global loss.
   - Result: accepted. Forward execution runs with sink feedback disabled for occupancy packets, then episode correctness is converted into local `FeedbackPulse`s only along packets that actually reached the correct decision branch.

## Frictions encountered
- The current environment still assumes a single formal `source_id`, so the bridge uses a wrapper-level topology with a dormant hub plus direct injection into sensor-specific inboxes rather than forcing a deeper environment refactor.
- The transplanted baseline runner carried a `sys.path` bootstrap from the old repo layout. That was removed here so the occupancy package stays compatible with the standalone boundary and runs via `python -m occupancy_baseline.run_baseline`.

## Decisions promoted
- The occupancy baseline remains a separate package, but the REAL bridge and comparison harness live alongside the existing experiment scripts instead of inside `real_core`.
- The first occupancy topology is intentionally fixed and interpretable: sensor sources, two binary decision nodes, one shared sink.
- Comparison artifacts now report the frozen baseline result, per-seed REAL runs, and explicit eval-minus-baseline deltas so seed variance does not get mistaken for the whole benchmark story.
