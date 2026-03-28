# 2026-03-27 1600 - Layer 2 Growth Semantics and Structural Need Initiation

## Purpose

Record the work completed after
`docs/traces/2026-03-27 1030 - Gradient Controller Bounded Slices and Rescue Portfolio.md`,
with emphasis on:

- fuller Layer 2 development beyond the first gradient-controller pass
- the new Layer 2 regulatory substrate and its initial integration
- the growth-debug path used to inspect slow-layer growth control without
  changing the main harness
- the semantic mismatch discovered between `authorize` and actual growth
  behavior
- the fixes that made `authorize` bottom-up and `initiate` top-down
- the new chronic structural-need path that lets Layer 2 initiate growth when
  Layer 1 stays stuck
- the resulting B / HR / C-family behavior

## Summary

The main conclusions from this phase are:

- Layer 2 is now more than a single compressed controller. A small slow
  regulatory substrate exists and is influencing control in a real way.
- The old growth contract had drifted semantically:
  - `authorize` did not truly mean “bottom-up growth request approved”
  - `initiate` and `authorize` were overlapping in ways that blurred the
    layered responsibilities
- That growth contract has now been cleaned up:
  - `authorize` now means a real bottom-up request is present and has been
    honored
  - `initiate` now means Layer 2 is opening growth because persistent
    structural need is present even without a clear bottom-up request
- Layer 2 can now drive real structural growth on hard cases like `C3S1 task_c`
  through normal execution, not only through a debug override
- This did not broadly break the benchmark guardrails, but it did shift the
  profile:
  - some B lanes improved
  - some B lanes regressed
  - HR remained acceptable overall
  - C-family still does not settle reliably, but growth is no longer dormant

So the architecture is more aligned than before:

- Layer 2 is learning regulatory structure instead of only emitting smooth
  heuristics
- growth semantics are cleaner
- Layer 2 can now escalate from sensing structural need to opening a growth
  regime
- the remaining problems are increasingly about whether Layer 1 uses that
  growth productively, not whether Layer 2 notices the need

## What Changed

### 1. Added a Layer 2 regulatory substrate

A new slow-layer substrate was added in:

- `real_core/regulatory_substrate.py`

This introduced a small Layer 2 memory and composition system around abstract
regulatory primitives:

- `differentiate`
- `hygiene`
- `stabilize`
- `expand`
- `settle`
- `explore`

Each primitive now carries:

- activation
- provisional support
- durable support
- credit
- debt
- velocity
- local effect history

This gives Layer 2 a slower analog of some Layer 1 patterns rather than asking
one monolithic decision point to do everything.

### 2. Added latent Layer 2 regulatory state and primitive coupling

The Layer 2 substrate was then extended with slow latent regulatory states:

- `poisoned`
- `recoverable_branch`
- `structural_need`
- `confidently_wrong`

These latent states feed primitive demand, and the primitives now interact
through a small coupling map. This is still a small substrate, not a full Layer
2 graph, but it is a real move toward Layer 2 learning regulatory structure.

### 3. Integrated the Layer 2 substrate into the gradient controller

`GradientSliceRegulator` in:

- `real_core/lamination.py`

now builds a `RegulatoryObservation`, steps the Layer 2 substrate, and blends
its composition into the existing continuous control vector:

- `budget_target`
- `pressure_level`
- `hygiene_level`
- `growth_drive`
- `portfolio_drive`
- `settlement_confidence`

This remains a transitional blended design. The older gradient formulas are
still present, but Layer 2 is no longer just metadata on the side.

### 4. Improved rescue portfolio shaping using Layer 2 state

The rescue portfolio no longer varies only slice duration.

In `real_core/lamination.py`, the candidate profiles now use Layer 2 primitive
and latent state to shape rescue behavior:

- `short` candidates lean more toward differentiation / hygiene
- `long` candidates lean more toward expansion / exploration
- `base` candidates stay closer to the current center

This makes the rescue portfolio more meaningfully regulatory rather than only a
timing variant.

### 5. Added a debug-only forced-growth harness

To inspect growth behavior without changing the main core or benchmark harnesses,
a new debug-only script was added:

- `scripts/debug_force_growth.py`

This wraps an existing regulator and rewrites only the outgoing
`growth_authorization` field for a run. It supports forcing:

- `hold`
- `authorize`
- `initiate`

This was important because it allowed direct comparison between:

- normal slow-layer growth behavior
- forced `authorize`
- forced `initiate`

without wiring a debug override into the main code path.

### 6. Fixed growth-poisoning interactions in fast-layer hygiene

During the growth audit, two problems showed up in `phase8/environment.py`:

1. unresolved latent difficulty was suppressing growth pressure
2. hard reset/drop hygiene was wiping growth proposals and damping growth state

That was backwards for the intended architecture. Slice-level growth signal is
supposed to persist across slices.

The fast-layer hygiene path was updated so that:

- unresolved latent difficulty increases growth pressure instead of reducing it
- hard reset/drop no longer clears pending growth proposals
- hard reset/drop no longer heavily damps growth state variables

The hygiene path still scrubs poisoned episodic/task-local state, but it no
longer erases the growth-side signal that Layer 2 is trying to maintain.

## The Growth Semantics Bug

The clearest architecture bug uncovered in this phase was a mismatch between
what `authorize` sounded like and what it actually did.

### What was happening

The system was effectively using three different notions of growth:

1. bottom-up request summary in the slice metadata
2. Layer 2 authorization
3. a second stricter local growth gate inside Layer 1

That led to an incoherent state where:

- Layer 1 could appear to be “asking”
- Layer 2 could say `authorize`
- but Layer 1 still could not act because it had to clear an even stricter
  second threshold

So `authorize` did not really mean “bottom-up request approved.” It meant
something closer to “growth is permitted in principle if Layer 1 later becomes
even more convinced.”

That was not aligned with the intended layered semantics.

### The correction

The contract was cleaned up in three places.

#### 1. Gradient regulator semantics

In `real_core/lamination.py`, `authorize` is now emitted only when a real
bottom-up growth request is present. A growth request is represented by the
compact slice summary fields:

- `requesting_nodes`
- `active_growth_nodes`
- `pending_proposals`

If there is no bottom-up request, the gradient path no longer emits
`authorize` simply because `growth_drive` is moderate.

#### 2. Phase 8 adapter semantics

In `phase8/lamination.py`, the gradient-mode adapter was previously rewriting
growth authorization from `growth_drive` alone. That meant even a regulator
that correctly emitted `None` or `hold` could still arrive in the environment
as `authorize`.

That compatibility rewrite was corrected so explicit regulator output is now
honored.

#### 3. Layer 1 action gate semantics

In `phase8/environment.py`, the Layer 1 `authorize` path no longer requires a
second stricter “request again” threshold before growth actions are exposed.

Now the semantics are:

- `hold`: growth blocked
- `authorize`: bottom-up request honored
- `initiate`: top-down growth opening when Layer 1 is too stuck to request

This is much closer to the intended layering.

## What the Debug Runs Showed

The debug growth harness was used to compare growth behavior on the hard lane:

- `C3S1 task_c`

### Before the semantic fixes

Forced `authorize` did not produce real growth:

- `bud_attempts = 0`
- `bud_successes = 0`
- `dynamic_node_count = 0`

Forced `initiate`, however, did produce growth:

- `bud_attempts > 0`
- `dynamic_node_count > 0`

This showed that Layer 1 growth mechanics were still intact, but `authorize`
was too weak or too semantically muddy to wake them up in hard cases.

### After the semantic fixes

Normal `C3S1 task_c` runs under `gradient` began to show real top-down growth
initiation in the chronic-need case:

- `bud_attempts = 19`
- `bud_successes = 19`
- `dynamic_node_count = 2`
- applied growth authorization counts included both:
  - `initiate`
  - `authorize`

So the major shift is:

- growth is no longer just “permitted”
- Layer 2 can now actually open a growth regime in normal execution

That does not yet solve the task, but it is a real behavioral change.

## Layer 2 Initiation Tuning

Once the growth semantics were clean, Layer 2 still needed a route from:

- chronic structural need
- weak-branch recoverability
- active rescue pressure

to actual `initiate`.

The late-slice C-family profile looked like this:

- `structural_need` around `0.56-0.65`
- `expand` around `0.22-0.30`
- `explore` around `0.28-0.35`
- `pressure_level` around `0.50-0.64`
- `settlement_confidence` still only around `0.42-0.49`
- `floor_gap` still large
- no bottom-up growth request

That was exactly the situation where Layer 2 should say:

- “Layer 1 is not requesting growth clearly, but this system is structurally
  stuck and still recoverable”

So a new chronic-structural-need initiate path was added in
`real_core/lamination.py`.

That rule now allows `initiate` when:

- structural need is high
- expansion and exploration drives are nontrivial
- rescue pressure is already high
- floor gap remains large
- growth readiness is not zero
- settlement confidence is still low enough that the run is clearly unresolved

This is the current Layer 2 route from “sensed structural need” to “open
growth.”

## Benchmark Read After These Changes

### C-family hard lane

`C3S1 task_c` remains unsolved, but the behavior changed materially.

At 30 slices under `gradient`:

- `final_accuracy = 0.5625`
- `floor_accuracy = 0.3529`
- `decision = continue`
- `bud_attempts = 19`
- `bud_successes = 19`
- `dynamic_node_count = 2`

So the task did not break through, but growth is now genuinely active instead
of dormant.

That narrows the remaining question:

- are the new buds being placed on useful branches
- or is growth simply reinforcing the wrong scaffold

### B-family regression check

A quick sweep on:

- `B2S1`
- `B2S2`
- `B2S3`

under `gradient`, `budget=6`, `threshold=0.8`, `safety=40` produced:

- `6/9` settled

Strong lanes remained healthy:

- `B2S2 task_b`
- `B2S2 task_c`
- `B2S3 task_b`
- `B2S3 task_c`

Notable changes:

- `B2S1 task_b` improved and settled strongly
- `B2S1 task_c` regressed and did not settle
- `B2S3 task_a` regressed and did not settle

So the new growth-initiate behavior did not cause a total B-family collapse,
but it did shift the profile enough that those two visible B lanes need
inspection.

### HR-family regression check

A quick sweep on:

- `HR1`
- `HR2`
- `HR3`

under `gradient`, `budget=6`, `threshold=0.8`, `safety=40` produced:

- `5/9` settled

Strong:

- `HR1 task_a`
- `HR1 task_b`
- `HR2 task_a`
- `HR2 task_b`
- `HR2 task_c`

Still weak:

- all `HR3` tasks
- `HR1 task_c`

This is acceptable as a guardrail read. The growth-initiation changes did not
appear to broadly destabilize the hidden-regime family.

## Current Interpretation

The most important result of this phase is not that the hard C lane is solved.
It is that the system now behaves more honestly:

- Layer 2 has a real regulatory substrate
- growth semantics match the intended layered contract more closely
- Layer 2 can now open growth when chronic structural need persists
- growth can now actually appear in normal execution instead of only under a
  debug override

The remaining limitation has moved again:

- it is less about whether Layer 2 notices the need
- and more about whether Layer 1 can use newly opened growth productively

That suggests the next diagnostic focus should probably be:

- where the new dynamic nodes are being placed
- whether the new buds support the weak branch or the dominant scaffold
- whether post-growth branch credit remains local long enough to help the task
  instead of just amplifying an already-wrong route family

## Files Touched In This Phase

- `real_core/regulatory_substrate.py`
- `real_core/lamination.py`
- `real_core/__init__.py`
- `phase8/environment.py`
- `phase8/lamination.py`
- `scripts/debug_force_growth.py`
- `scripts/evaluate_hidden_regime_forecasting.py`
- `tests/test_lamination.py`
- `tests/test_phase8_lamination.py`
- `tests/test_latent_growth_gate.py`
- `tests/test_debug_force_growth.py`

## Validation

Focused validation after the latest changes:

- `python -m unittest tests.test_lamination tests.test_phase8_lamination tests.test_latent_growth_gate tests.test_debug_force_growth tests.test_latent_route_transform_gate`

Latest focused result:

- `51` tests passed

## Current Best Read

This phase successfully moved Layer 2 closer to the intended role:

- it learns regulatory structure in a small slow substrate
- it now distinguishes more cleanly between bottom-up request and top-down
  initiation
- it can persist growth-side intent across slices
- it can open actual growth on chronic structural-need lanes

The remaining problem is no longer “why is growth always dormant?” It is closer
to:

- “when Layer 2 opens growth, what exactly does Layer 1 build, and is that
  structure actually helping the unresolved branch?”
