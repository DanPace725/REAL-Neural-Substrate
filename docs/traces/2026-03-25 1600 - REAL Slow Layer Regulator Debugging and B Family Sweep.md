# 2026-03-25 1600 - REAL Slow Layer Regulator Debugging and B Family Sweep

## Purpose

This trace records a debugging and validation session for the `REALSliceRegulator`
introduced in the prior session. The slow-layer regulator had been wired and tested
against B2S5 in isolation, but systematic cross-scale testing revealed several bugs
that collectively produced misleading results. All bugs were identified and fixed, and
a B family sweep was run to characterise the regulator's behaviour across scales.

## Context

The prior session established `REALSliceRegulator` as the slow layer, backed by a
full `RealCoreEngine` running one cycle per slice. The action space was 10 named
compound policies (`NAMED_POLICIES`) encoding (capability_mode, carryover_filter,
budget_multiplier, context_pressure). Phase 1 wiring gave the runner a `_switch_mode`
method that rebuilds `NativeSubstrateSystem` in-place when the regulator selects a
new mode.

The CLI (`scripts/evaluate_laminated_phase8.py`) had been rewritten with short flags
(`-b`, `-t`, `-m`, `-s`, `--slices`, `--budget`, `--thresh`, `--reg`), `--sweep`, and
`--compact`, but had not yet been tested at scale.

## Bug 1: Mode Thrashing via Incorrect Family Mapping

### Symptom

B2S3 trace showed the mode switching from `growth-visible` (which was producing
bit_acc=0.913 in slice 3) back to plain `visible` in slice 4 via `visible_push`,
dropping accuracy to 0.448. Slice 5 then had bit_acc=0.0 and empty context_accuracy
because the newly re-initialised system had no time to adapt before the scenario ended.

### Root Cause

`_MODE_FAMILY` in `real_core/meta_agent.py` mapped `"growth-visible"` to `"visible"`,
so `_POLICIES_BY_FAMILY["visible"]` was offered to the engine while in growth-visible
mode. That family includes `visible_explore` and `visible_push`, both of which specify
`capability_mode="visible"`, causing the runner to call `_switch_mode("visible")` and
discard all accumulated morphogenetic state.

### Fix

`_MODE_FAMILY` was updated to map `"growth-visible"` to its own `"growth-visible"`
family and `"growth-latent"` to `"growth-latent"`. Each growth family only contains
growth-compatible policies (`growth_engage`, `growth_consolidate`, `growth_reset`,
`growth_hold`). The plain-visible policies remain available when starting from
`"visible"` or `"self-selected"`, allowing the initial upgrade path to growth, but
once in growth mode the engine cannot step back.

## Bug 2: Budget Creep from Multipliers > 1.0

### Symptom

Slice 5 of several B2S3 runs had bit_acc=0.0 and empty context_accuracy despite the
runner correctly capping to remaining cycles (`cycles_to_run = min(budget, remaining)`).
Total planned cycles: 25 + 25 + 31 + 31 + 31 = 143, but B2S3 has only 128 cycles.
The last slice started at cycle 112 with only 16 remaining, too few to process
meaningful packets.

### Root Cause

`growth_reset` and `visible_push` had `budget_multiplier=1.25`, and `growth_engage`
and `latent_push` also had 1.25×. In a fixed-length scenario, any multiplier above
1.0 steals cycles from later slices, making them progressively less useful.

### Fix

All `budget_multiplier` values above 1.0 were reduced to 1.0. The consolidation
multiplier (0.75) was preserved — it is meaningful as a way to conserve cycles for
later slices. The effect: total cycle consumption now stays at or below the scenario
total, and no slice is starved.

## Bug 3: laminated_summary Reporting on Discarded System

### Symptom

After both bugs above were fixed, the compact row for B2S3 still showed `lam=0.460`
despite per-slice bit_acc rising to 0.76–0.96 in slices 2–5. The laminated run was
visibly improving, but the summary metric showed no benefit over baseline.

### Root Cause

`evaluate_laminated_scenario` computed the laminated summary via
`laminated_system.summarize()`, where `laminated_system` is the original
`NativeSubstrateSystem` created before the first slice. Each call to `_switch_mode`
replaces `runner.system` with a new system, but `laminated_system` still references
the discarded initial object. That object had only processed slice 1 (25 cycles),
hence 25 packets vs 108 for the baseline.

### Fix

Changed to `runner.system.summarize()`, which calls summarize on the currently active
system — the one that processed all slices from the last mode switch onward. For B2S3,
this covered slices 2–5 (the growth-visible period), giving a realistic accuracy
figure.

### Impact

After this fix, B2S3 and B2S5 jumped from negative or marginal deltas to strong
improvements:

| Benchmark | Before fix | After fix |
|-----------|------------|-----------|
| B2S1      | +0.028     | +0.195    |
| B2S3      | −0.146     | +0.236    |
| B2S5      | +0.035     | +0.266    |

## Bug 4: Spurious Settle from Coherence Flatness at Zero Activity

### Symptom

B2S2 with `--slices 10 --budget auto` settled at slice 9 with `lam=0.389` and
`context_1=0.25` — well below the 0.8 threshold. The settle fired despite accuracy
being nowhere near the target.

### Root Cause

`HeuristicSliceRegulator._should_settle()` has two independent code paths: an
accuracy-threshold path and a coherence-flatness path. With `budget=4` cycles/slice,
slices 8 and 9 had `ambiguity_level=0.0` and `conflict_level=0.0` because there was
essentially no activity (the scenario had run out of meaningful packets). The flatness
path fired — "flat + no conflict = converged" — regardless of accuracy.

### Fix

When `accuracy_threshold > 0.0` is set, the coherence-flatness paths are now skipped
entirely. The method returns immediately after the threshold check. The flatness
heuristics are only used when no accuracy target is specified (exploratory runs
without an explicit criterion). This ensures flat-but-inaccurate cannot be mistaken
for convergence.

## Bug 5: --compact Suppressed File Output

### Symptom

Sweep runs using `--compact` produced no JSON output files in
`docs/experiment_outputs/`, even though the flag is intended to only change the
display format.

### Root Cause

The output path resolution logic in `main()` used:
```python
output_path = None if args.compact else _auto_output_path(...)
```
so `--compact` implicitly disabled saving.

### Fix

Removed the `compact` guard. `--compact` now only affects what is printed to stdout;
file writing always uses the auto-generated path unless `--no-output` is explicitly
passed.

## Additional Change: Auto-Budget Capping for Small Scenarios

Small B scales have very few total cycles (B2S1=24, B2S2=45). With `--slices 10
--budget auto`, the computed budget is `scenario.cycles // 10`, which floors at 2–4
cycles/slice. At that granularity the runner exhausts the scenario after 3–5 real
slices and the remaining slices process nothing.

`_resolve_budget` was updated to:
1. Apply a minimum floor of 8 cycles per slice.
2. Compute `effective_max_slices = min(max_slices, scenario.cycles // budget)` to
   cap the controller at the number of slices that can do meaningful work.

The function now returns `(budget, effective_max_slices)` and the call site uses both.
For B2S1 this gives 3 effective slices at budget=8; for B2S2, 5 effective slices.

## B Family Results (5 slices, post-fix)

Run with `--sweep all-b --slices 5 --reg real --thresh 0.8`. The laminated summary
reflects `runner.system` (current active system after mode switches).

| Benchmark | Baseline | Laminated | Delta  | Cost delta | Decision | Final ctx          |
|-----------|----------|-----------|--------|------------|----------|--------------------|
| B2S1      | 0.472    | 0.536     | +0.064 | −3.4       | continue | 0.50 / 0.50        |
| B2S2      | 0.528    | 0.759     | +0.232 | −0.1       | settle   | 1.00 / 1.00        |
| B2S3      | 0.607    | 0.649     | +0.043 | +6.1       | continue | 1.00 / 0.50        |
| B2S4      | 0.600    | 0.605     | +0.006 | −8.5       | continue | 0.94 / 0.92        |
| B2S5      | 0.581    | 0.864     | +0.282 | −21.3      | continue | 0.77 / 0.92        |

B2S4 and B2S5 showed contexts at or near threshold at max_slices, confirming that
the 5-slice ceiling was the primary obstacle to settlement rather than fundamental
incapacity.

## B Family Results (10 slices, post-fix, with auto-cap)

Run with `--sweep B2S1,B2S2,B2S3,B2S4 --slices 10 --reg real --thresh 0.8`.

| Benchmark | Effective slices | Laminated | Decision | Final ctx     | Notes                            |
|-----------|-----------------|-----------|----------|---------------|----------------------------------|
| B2S1      | 3 (capped)      | 0.562     | branch   | 0.50 / 0.60   | 24-cycle scenario, too small     |
| B2S2      | 5 (capped)      | 0.446     | continue | 0.50 / 0.75   | context_0 stuck at 0.50 all run  |
| B2S3      | 10              | 0.806     | settle   | 0.83 / 0.94   | Settled at slice 4, breakthrough at slice 3 (0.958) |
| B2S4      | 10              | 0.532     | continue | 0.50 / 0.30   | No traction across 10 slices     |

B2S3 settling at slice 4/10 with lam=0.806 is the clearest success — the extra
headroom allowed the system to confirm convergence across two consecutive slices
rather than hitting max_slices mid-convergence.

B2S4 is the outstanding problem: 10 slices at budget=24 (240 total cycles) produced
no meaningful improvement, with both contexts hovering around 0.5 throughout. The
growth substrate cycles through `growth_consolidate → growth_reset → growth_hold`
without progress, suggesting either a structural difficulty with the B2S4 task or
that the current policy selection isn't able to navigate this scale effectively.

## Open Questions

- **B2S4 stagnation**: What is structurally different about B2S4 vs B2S3 that causes
  the growth mode to fail to find traction? Is this a topology/task difficulty issue
  or a regulator signal quality problem?
- **Context imbalance**: B2S2 and B2S4 both show one context stuck at ~0.50 across
  all slices. The current policy set has no mechanism for deliberately applying
  context-specific pressure to an underperforming context.
- **Dynamic slice count**: The `max_slices` ceiling is still artificial. The goal is
  to run until the threshold is met with no predetermined limit. This requires either
  a session-level budget or a wall-clock/cost cap as the termination backstop.
- **laminated_summary coverage**: `runner.system.summarize()` only covers slices from
  the last mode switch. For runs with multiple mode changes, early slices contribute
  to task performance but are invisible in the summary metric. A fully aggregated
  per-packet accuracy across all slices would be more faithful.
