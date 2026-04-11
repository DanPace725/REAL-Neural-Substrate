# 2026-04-08 2135 - Occupancy Paper Alignment Clarification

## Context

We re-ran the REAL-native occupancy V3 harness on current `main` while trying to reproduce the high-F1 result that informed the ALIFE paper framing. The current branch no longer reproduces that result cleanly, even when using the saved seed-13 configuration from the March artifacts.

## What We Observed

- The saved best artifact in `docs/experiment_outputs/v3_best_real_seed13_summary.md` reports the strongest occupancy result from the paper-writing period.
- A current-code rerun on `main` produced lower warm-eval F1, even though routing-efficiency style metrics stayed similar or slightly improved.
- An older `c5a20ac` snapshot ran with an earlier CLI and also failed to cleanly reproduce the saved best artifact.
- A snapshot at `09f9b09` is a better practical checkpoint for paper-era occupancy work because it still lives in the March V3 line and matches the paper-writing window more closely than the current branch.

## Working Interpretation

The paper occupancy result should be treated as a historical result from a March 2026 code state, not as a guarantee about current `main`. The saved artifact appears to have been produced from code that was likely between commits or otherwise ahead of the clean `c5a20ac` snapshot. That means commit SHA alone is not enough to identify the exact high-F1 state.

For incoming readers who start from the ALIFE paper:

- use the saved V3 occupancy artifacts in `docs/experiment_outputs/` as the reference record for the paper-aligned run
- use a checkout or snapshot around `09f9b09` when you want code that is closer to the paper-era occupancy harness
- treat current `main` as a later research line whose occupancy behavior has evolved beyond the paper snapshot

## Repo Follow-Through

To make this visible without forcing people to rediscover it, the README and `docs/running_occupancy_v3.md` now call out that the paper-aligned occupancy result is historical and that current `main` may not reproduce it exactly.

## Referenced Files

- `README.md`
- `docs/running_occupancy_v3.md`
- `docs/experiment_outputs/v3_best_real_seed13_summary.md`
- `docs/experiment_outputs/v3_best_real_seed13.json`
- `scripts/run_occupancy_real_v3.py`
