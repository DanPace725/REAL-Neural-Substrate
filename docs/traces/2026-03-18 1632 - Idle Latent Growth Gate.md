# 2026-03-18 1632 - Idle Latent Growth Gate

## Context

After splitting latent promotion and latent growth thresholds, `C3 growth-latent` still opened early bud proposals on generated Family C. A focused timing probe showed that the first meaningful bud event came from `n2`, not the source.

## Finding

The problem was not only threshold calibration. `n2` could offer contradiction-driven bud proposals while it had no current packet in its inbox:

- cycle 8: `n2` had no packet and no visible head task, but contradiction pressure was `0.5926`
- cycle 8: `n2` already had strong recent latent-task state (`last_observed_cycle=8`, `observation_streak=2`, `confidence=0.9721`)
- cycle 8: the old logic still exposed `12` bud actions because the context gate only activated when `head_has_task >= 0.5`

That meant morphogenesis could commit structure from stored contradiction alone during a brief idle window between latent-task observations.

## Change

Added a small recency-aware latent growth gate in [environment.py](C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate\phase8\environment.py):

- introduced `LATENT_GROWTH_IDLE_TASK_WINDOW = 1`
- added `_recent_latent_task_summary(node_id)` to surface very recent latent-task state even when the inbox head is empty
- exposed recent latent-task signals through `observe_local()`
- suppressed regular contradiction/overload-driven growth when a node is in a recent latent-task window but has no current head task
- left the anticipatory backlog path intact

This is intentionally narrow: it targets stale contradiction-driven budding without removing pressure-responsive source growth.

## Validation

Focused tests passed:

- `python -m unittest tests.test_latent_growth_gate tests.test_latent_context_tracker tests.test_multicontext_substrate tests.test_c_growth_timing`

Targeted runtime probe on `C3 task_b growth-latent`:

- before: cycle 8 on `n2` exposed `12` bud actions
- after: cycle 8 on `n2` exposed `0` bud actions

Quick cold `C3` seed-13 spot check with `_run_real_method`:

- `task_a`: exact `0.2130`, bit `0.5139`
- `task_b`: exact `0.2407`, bit `0.5278`
- `task_c`: exact `0.1296`, bit `0.4213`
- aggregate: exact `0.1944`, bit `0.4877`

Relative to the prior quick probe, this looks like a small aggregate improvement driven mostly by `task_b`, with `task_c` regressing.

## Read

Current interpretation:

- the fix addresses a real architectural leak in the growth gate
- it helps where premature contradiction-based branching was hurting `task_b`
- `task_c` still likely needs better handling of longer-horizon latent ambiguity, not just tighter morphogenesis timing
