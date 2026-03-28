# 2026-03-27 1030 - Gradient Controller Bounded Slices and Rescue Portfolio

## Purpose

Record the work completed after
`docs/traces/2026-03-26 2210 - Fast Layer Ambiguity Retention and Weak Branch Stabilization.md`,
with emphasis on:

- the new gradient-first laminated controller
- adaptive slice duration inside a slice
- rescue-only speculative slice portfolio with winner-takes-state semantics
- the problem we found where adaptive slices could silently balloon back into
  giant monolithic runs
- the bounded-slice correction and the first benchmark read on B, C, and HR

## Summary

The main conclusion from this phase is:

- the gradient controller is now real, not just a design note
- adaptive slices and rescue-portfolio infrastructure are now implemented
- the first pass worked well on the repaired B lanes and on a small HR check
- the first pass also revealed a real failure mode: hard C-family cases could
  re-expand into giant single slices even though the controller was nominally
  sliced
- after clamping both inter-slice and in-slice budget growth, that failure was
  contained
- the rescue portfolio now actually activates on hard C-family stalls, but it
  has not yet produced a clear C-family breakthrough

So the architecture is healthier than before:

- normal cases stay sequential
- easy and medium cases can stop early
- hard cases can trigger bounded speculative rescue
- but the controller no longer quietly turns one “slice” into a thousand-cycle
  pseudo-monolith

## What Changed

### 1. Added a continuous control vector to the slow layer

`RegulatorySignal` was extended to carry continuous control terms:

- `budget_target`
- `pressure_level`
- `hygiene_level`
- `growth_drive`
- `portfolio_drive`
- `settlement_confidence`
- `execution_plan`

This makes the primary slow-layer representation more gradient-like and less
string-driven, while preserving the existing compatibility outputs:

- `carryover_filter_mode`
- `context_pressure`
- `growth_authorization`

Those string outputs still matter because Phase 8 currently consumes them, but
they are now a bridge layer rather than the only control channel.

### 2. Added `SliceExecutionPlan`

The new internal execution contract now includes:

- `initial_budget`
- `extend_step`
- `soft_cap`
- `hard_cap`
- `early_stop_patience`

This lets a single slice run in micro-batches rather than as one fixed cycle
block.

### 3. Added `GradientSliceRegulator`

The new regulator computes continuous control from compact slice summaries.

The main ingredients are:

- floor gap
- aggregate gap
- debt mass
- context spread
- uncertainty/conflict
- provisional ambiguity
- commitment hardness
- progress velocity
- failed-hygiene persistence
- slice efficiency
- growth request pressure/readiness

It still keeps threshold-style logic only where it belongs:

- settlement
- escalation
- hard reframe conditions

Everything else now trends through graded signals.

### 4. Added rescue-only portfolio support to `LaminatedController`

The controller can now:

- stay sequential by default
- detect rescue conditions from `portfolio_drive`
- snapshot fast-layer state
- run `short`, `base`, and `long` candidate slices from the same snapshot
- score candidates floor-first
- commit only the winner’s fast-layer state
- discard losers

This is the first implementation of the speculative parallel slice idea, but
with strict winner-takes-state semantics and no branch merging.

### 5. Added Phase 8 adaptive slice stepping and snapshot/restore

`Phase8SliceRunner` now supports:

- `run_slice_plan(...)`
- `snapshot_fast_state()`
- `restore_fast_state(...)`

This makes the rescue portfolio real rather than conceptual, and also gives the
runner the ability to stop or extend a slice incrementally.

The Phase 8 adapter also now maps gradient controls into the existing levers:

- hygiene level -> keep / soften / drop
- pressure level -> low / medium / high
- growth drive -> hold / authorize / initiate

### 6. REAL now uses the gradient controller as its primary ordinary control path

`REALSliceRegulator` was updated so the gradient regulator is no longer just
metadata on the side. It now drives the ordinary budget / hygiene / pressure /
growth outputs, while the REAL policy selector remains responsible for the
learned meta-policy path and its own GCO-based settlement.

## The New Failure We Found

The first implementation of adaptive slices revealed a subtle but important
architectural failure:

- hard ambiguous cases, especially `C3S1 task_c`, could still silently grow
  into giant slices
- that happened because the gradient regulator kept raising `budget_target`
  relative to the already-expanded current slice
- the adaptive runner then legitimately extended inside that larger request
  until a “slice” was no longer meaningfully small

In one probe, a C-family lane ended up using over a thousand cycles inside a
single slice. That was exactly the wrong direction conceptually. Even though the
controller was technically sliced, the effect was still monolithic.

This matters because the whole point of the laminated architecture is:

- bounded local solving
- compact slow-layer summaries
- repeated regulation between bounded efforts

If slices silently become huge, we lose that discipline.

## The Correction

To fix that, the controller was tightened in two places.

### 1. Inter-slice budget growth was clamped

The gradient regulator now caps next-slice budget growth so it can increase, but
only within a bounded range.

### 2. In-slice execution plans were capped

`SliceExecutionPlan` generation now clamps:

- target budget
- soft cap
- hard cap
- extension step sizes

The current hard ceiling is intentionally simple and conservative. The point was
not to find the final perfect number, but to re-enforce the principle that a
slice must stay a slice.

## Benchmark Read So Far

After the bounded-slice correction:

- `B2S2 task_c`: settled, `final=1.0`, `floor=1.0`
- `B2S3 task_c`: settled, `final=1.0`, `floor=1.0`
- `HR1 task_a`: settled at threshold, `final=0.8`, `floor=0.8`

These were good signs:

- the new controller did not regress the repaired B-family hard cases
- the HR check stayed viable
- the easy/medium lanes remained sequential and did not need the rescue
  portfolio

For `C3S1 task_c`:

- the lane remained unsolved
- but the runaway giant-slice behavior was contained
- and after lowering the rescue threshold, the portfolio started to activate
  on persistent bounded stalls

That means the controller is now doing the right kind of thing structurally:

- it detects persistent bounded struggle
- it opens speculative rescue
- it still does not yet have a strong enough winner-selection effect or policy
  variation to convert that into reliable C-family success

## Current Interpretation

The most important outcome of this phase is not that C is solved. It is that
the architecture is now closer to the intended form:

- gradient-first control rather than mostly discrete strings
- adaptive slice duration rather than fixed slice length
- rescue-only portfolio exploration rather than always-on branching
- winner-takes-state rather than merge confusion
- bounded slices even on hard cases

The remaining open problem is more specific now:

- the rescue machinery engages on the hard C lane
- but the candidate variations are still too mild, or the winner scoring is not
  yet extracting enough useful asymmetry recovery from them

So the next likely move is not “more budget.” It is one of:

- stronger rescue candidate diversification inside the bounded portfolio
- better winner scoring for ambiguity-heavy C-family cases
- a more explicit relationship between weak-context debt and portfolio
  candidate shaping

## Files Touched In This Phase

Primary implementation files:

- `real_core/types.py`
- `real_core/interfaces.py`
- `real_core/lamination.py`
- `real_core/meta_agent.py`
- `phase8/lamination.py`
- `scripts/evaluate_laminated_phase8.py`

Primary regression coverage:

- `tests/test_lamination.py`
- `tests/test_phase8_lamination.py`

## Bottom Line

This phase produced a meaningful architectural upgrade:

- the gradient laminated controller is implemented
- adaptive slices are real
- rescue portfolio execution is real
- bounded-slice discipline has been restored after the first overshoot bug

The B-family and a small HR lane look healthy under the new controller.

The C-family remains the main open problem, but it is now failing in a more
useful and interpretable way than before: bounded, observable, and able to
enter rescue mode instead of simply stretching into unbounded slices.
