# 2026-03-26 1645 - Laminated Context Collapse and Differentiation Reframe

## Purpose

Record the laminated slow-layer work completed after the growth continuity audit,
summarize the benchmark behavior on B and hidden-regime tasks, and document the
remaining failure mode now showing up most clearly in `B2S2 task_c`.

This trace is specifically about the gap between:

- preserving fast-layer developmental state across slices
- keeping the slow-layer interface summary-safe
- and responding in a general Phase 1 aligned way when one context or regime
  collapses while another succeeds

## Summary

The main architectural cleanup succeeded:

- fast-layer runtime continuity is now preserved across laminated mode changes
- the slow layer still sees only compact slice summaries
- growth is now a fast-layer request and a slow-layer authorization decision,
  not a direct slow-layer mode takeover
- explicit threshold settlement now uses `final_accuracy`
- asymmetry features are exposed to the slow layer
- persistent asymmetry now triggers a general differentiation reframe

However, the main benchmark failure did not disappear.

`B2S2 task_c` is still a genuine one-context collapse problem:

- aggregate/final accuracy can become moderately good
- one context remains effectively dead
- the slow layer can now see that asymmetry and does sometimes trigger a
  differentiation reframe
- but the recovery is not yet strong or persistent enough to restore the dead
  context

So the issue has shifted from "the slow layer cannot see the problem" to
"the slow layer sees the problem but does not yet sustain an effective
relational recovery policy."

## Phase 1 Alignment

The current direction is more aligned with the Phase 1 materials than the prior
drifted implementation.

From `Phase 1/Summarized Context/Relational Primitives V3_summary.ormd`:

- **Dynamical**: fast-layer slices should keep local change and adaptation alive
- **Symmetric/Constraint**: slice boundaries should preserve durable structure
  rather than destroying accumulated growth
- **Epistemic**: higher layers should only receive summary-safe, uncertainty-aware
  views of lower-layer state
- **Meta-Relational**: the slow layer should respond to failed correspondence
  across contexts/scales by reframing, not by replacing the lower layer

From `Phase 1/Context Layer/TCL_Three_Constants.ormd`:

- the slow layer should primarily **tilt** the fast layer, not continuously
  reshape it from above
- there is a narrow viable operating window, so gross top-down regime forcing is
  a bad default

From `Phase 1/Context Layer/Adaptation via Informational Abstraction (AVIA) A .ormd`:

- higher-order abstractions should guide lower-order components without erasing
  their accumulated local organization
- multiscale adaptation should preserve local progress while using higher-order
  summaries to manage complexity

The implemented changes below move the laminated path closer to that model.

## What Changed

### 1. Fast-layer continuity is preserved across mode changes

The first bug was that laminated mode switching rebuilt a fresh Phase 8 system
and restored only node-local `real_core` carryover.

That meant the following fast-layer state could be lost on a slice/mode change:

- topology/runtime continuity
- capability state
- pending growth proposals
- latent trackers
- queue/runtime state
- packet and feedback continuity

The switch path now preserves the full Phase 8 runtime layer internally while
still keeping the slow-layer summary interface compact.

Result:

- slice boundaries no longer imply "destroy accumulated growth"
- fast memory remains rich and local
- slow-layer input remains summary-only

This work follows up the earlier audit in
`docs/traces/2026-03-26 1430 - Laminated Growth Continuity Audit.md`.

### 2. Growth was refactored from top-down selection into request plus authorization

The next drift was that the slow layer had effectively become the direct chooser
of growth posture.

That was refactored so:

- fast-layer state emits compact growth request summaries
- the slow layer returns `authorize` or `hold`
- `hold` suppresses new growth actions while preserving accumulated substrate
  progress and pending work

This is much closer to a TCL-style regulatory tilt than a top-down landscape
rewrite.

### 3. Threshold settlement now uses `final_accuracy`

The earlier settle behavior was wrong for the intended criterion.

The threshold path now uses `final_accuracy` directly rather than context-minimum
or mean-bit fallback logic when `--thresh` is set.

This removed the main under-settling/false-settling ambiguity in the laminated
benchmark loop.

### 4. The slow layer now sees context asymmetry explicitly

The REAL slow-layer observation path now includes:

- `best_ctx_acc`
- `worst_ctx_acc`
- `context_accuracy_spread`
- `asymmetric_context_collapse`

These are also folded into the slow-layer coherence logic, so asymmetry is not
just logged; it counts against the run.

### 5. Weak-context guidance had a concrete bug

The weak-context rescue path in `phase8/lamination.py` had a bug where the
dominant neighbor id was being treated as the dominant transform label.

That meant the code meant to seed non-dominant transforms for the weak context
could accidentally fail to exclude the dominant transform correctly.

That bug was fixed.

### 6. Added a general differentiation reframe

Persistent asymmetric collapse now triggers a general slow-layer response rather
than a benchmark-specific patch.

The current reframe behavior is:

- `reframe_flags["context_differentiation"] = 1.0`
- `reset_flags["episodic"] = 1.0`
- `carryover_filter_mode = "drop"`
- `growth_authorization = "hold"`
- `context_pressure = "high"`
- next budget growth is suppressed on that slice

Phase 8 applies that reframe by:

- clearing episodic memory while preserving substrate/runtime progress
- increasing weak-context guidance bias
- preserving the fast-layer continuity boundary

### 7. Added observability for applied reframe/reset state

Slice metadata and the serialized laminated `final_signal` now surface:

- applied growth authorization
- applied carryover filter mode
- applied context pressure
- applied reset flags
- applied reframe flags

This made it possible to verify that the reframe is actually firing in live
runs rather than only in unit tests.

## Validation

Focused test coverage now includes:

- continuity preservation across mode changes
- growth `hold` preserving pending growth while blocking new growth actions
- explicit final-accuracy settlement behavior
- slow-layer asymmetry observation features
- heuristic and REAL regulator propagation of differentiation reframe
- surfacing of applied reset/reframe flags in slice metadata

Current focused validation command:

```text
python -m unittest tests.test_lamination tests.test_phase8_lamination
```

Result at the end of this trace:

- `21` tests passing

## Benchmark Results So Far

### B family

After the settlement fix, the B-family thresholded laminated runs improved
substantially.

At `--thresh 0.8`:

- the `B2S1` to `B2S3` sweep at safety `40` settled `7/9`
- the same sweep at safety `100` settled `8/9`

The remaining holdout was:

- `B2S2 task_c`

Representative saved manifest:

- `docs/experiment_outputs/20260326_laminated_b2s2_task_c_visible_b6_t08_real_seed13.json`

### Hidden Regime family

The hidden-regime sweep exposed that the old fallback settlement logic was still
allowing some runs to settle below the intended `.8` criterion.

After the settle fix:

- `HR1 task_b` still settles once it genuinely crosses threshold
- `HR1 task_a` no longer falsely settles below threshold
- several HR failures now appear to be real task failures rather than stop-rule
  artifacts

Representative saved suite manifest:

- `docs/experiment_outputs/20260326_155827_299789_hidden_regime_suite_hr1_hr2_hr3_all_tasks_hidden_self_selected_b6_s40_t08_seed13.json`

## Detailed Issue: One-Context Collapse

### What the failure looks like

The cleanest current case is:

- `B2S2 task_c`

In the saved `100`-slice manifest:

- overall mean bit accuracy is about `0.7068`
- `context_0` mean bit accuracy is `0.0179`
- `context_1` mean bit accuracy is `0.9821`

So the run is not "weak everywhere." It is solving one context and abandoning
the other.

Final task diagnostics show:

- `context_0` expected `xor_mask_1010`
- `context_0` produced `identity` `882/892` times
- `context_0` had `883` wrong-transform-family events

This is a classic collapsed differentiation failure:

- one context has captured the routing/transform policy
- the other context is effectively being treated as noise or defaulted into
  identity fallback

### Why this was hard to see earlier

Before the asymmetry features were added, the slow layer mostly saw aggregate
quality and general conflict/ambiguity metrics.

That meant a run could look "moderately productive" at the aggregate level while
still containing a catastrophic internal split:

- one context near zero
- one context near one

Without explicit asymmetry features, the slow layer had no clean way to
distinguish:

- broad low-quality learning
- from failed context differentiation

### What the slow layer is doing now

Tracing a short `B2S2 task_c` run after the new reframe path showed:

- slice `3`: differentiation reframe fired
- slice `9`: differentiation reframe fired again

Those slices showed:

- `applied_reset_flags = {"episodic": 1.0}`
- `applied_reframe_flags = {"context_differentiation": 1.0}`

So the slow layer is no longer blind. It is detecting the problem and issuing a
general recovery move.

### Why the problem remains

The issue now appears to be response strength and persistence rather than
visibility.

Observed behavior:

- reframe can temporarily disrupt the collapsed attractor
- the run sometimes briefly rebalances or improves aggregate accuracy
- but it often drifts back into the same collapsed pattern

In short:

- the reframe is episodic
- the failure is structural

The system currently knows how to say "this is a bad asymmetric state," but it
does not yet know how to hold a different relational stance long enough to
stabilize a genuinely differentiated solution.

### Why aggregate accuracy is still misleading here

Even after the new visibility work, aggregate accuracy can temporarily suppress
further intervention because the run can look "good enough" in the aggregate
while still keeping one context dead.

That is the key conceptual issue:

- aggregate/final accuracy is the right stop metric
- but it is not sufficient as the only recovery metric

For failed differentiation, the system likely needs a secondary structural rule:

- do not treat a one-hot / one-dead context split as healthy convergence just
  because the aggregate score is temporarily acceptable

## Current Interpretation

The layered architecture is healthier now than it was at the start of this
debugging pass.

What has been fixed:

- memory/growth continuity drift
- slow-layer top-down growth takeover
- threshold settlement metric drift
- lack of asymmetry visibility
- lack of observability for reframe application

What remains:

- a persistent failed-differentiation mode in which one context captures the
  substrate and another context never stabilizes

This now looks less like a plumbing bug and more like an incomplete relational
recovery policy.

## Likely Next Step

The next improvement should remain general and Phase 1 aligned.

The strongest candidate is:

- make differentiation reframe persist for a short regulatory window rather than
  a single slice

That would mean:

- once persistent asymmetry is detected, keep a short-lived slow-layer
  commitment to differentiated recovery
- maintain episodic scrubbing / high context pressure / weak-context rescue for
  more than one slice
- avoid immediately drifting back into ordinary policy churn after a single
  brief reset

That would still preserve the current boundary:

- fast-layer rich state stays local
- slow-layer input stays compact
- slow-layer output remains regulatory rather than solution-imposing

## Files Touched In This Pass

- `real_core/lamination.py`
- `real_core/meta_agent.py`
- `phase8/lamination.py`
- `tests/test_lamination.py`
- `tests/test_phase8_lamination.py`
- `scripts/experiment_manifest.py`
- `tests/test_experiment_manifest.py`

## Key Artifacts

- `docs/traces/2026-03-26 1430 - Laminated Growth Continuity Audit.md`
- `docs/experiment_outputs/20260326_laminated_b2s2_task_c_visible_b6_t08_real_seed13.json`
- `docs/experiment_outputs/20260326_155827_299789_hidden_regime_suite_hr1_hr2_hr3_all_tasks_hidden_self_selected_b6_s40_t08_seed13.json`
