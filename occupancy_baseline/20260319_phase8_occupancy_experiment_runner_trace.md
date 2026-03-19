# Phase 8 Occupancy Experiment Runner Trace - 2026-03-19

**Timestamp**: 2026-03-19 UTC  
**Model**: GPT-5.2-Codex

## Intent

Move the occupancy baseline from a one-off CLI scaffold to a small reproducible experiment flow that can save result artifacts for later REAL-side comparison.

## Hypotheses tested during implementation

1. The baseline runner should expose a reusable experiment layer instead of keeping all logic inside the CLI.
   - Result: accepted. Added `experiment.py` with config/result dataclasses plus `run_experiment()` and `save_result()` helpers.

2. Saving a JSON artifact is worth doing before dataset presets exist.
   - Result: accepted. A saved result file gives the next REAL comparison step a stable, inspectable handoff format.

3. The train/test split should remain sequential instead of randomly shuffled.
   - Result: accepted for now. Preserving order is the safer default for a time-indexed occupancy sequence and keeps the baseline aligned with the later sequential REAL mapping.

## Frictions encountered

- The repo still does not include a canonical occupancy CSV, so reproducibility currently means reproducible code paths and artifact shapes rather than a checked-in benchmark file.
- With tiny smoke-test fixtures, metric values are unstable; the saved-result path is more important than headline accuracy at this stage.

## Decisions promoted to maintained substrate

- Occupancy baseline runs should be representable as explicit config/result objects, not only console output.
- Saved JSON result artifacts should remain simple and human-readable so they can be compared directly against future REAL experiment summaries.
- Sequential splitting remains the default unless a later benchmark definition explicitly introduces shuffled or cross-room evaluation protocols.
