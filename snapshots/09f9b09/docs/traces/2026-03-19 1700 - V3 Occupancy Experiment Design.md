# 2026-03-19 1700 - V3 Occupancy Experiment Design

**Model**: Claude Sonnet 4.6 (claude-sonnet-4-6)
**Session type**: H_e (Episodic Trace)

---

## Intent

Design and implement a version of the occupancy test that is built around
what REAL actually does, rather than trying to use REAL as a traditional
classifier and measuring it on accuracy vs MLP.

The v2 synthesis established that v1 had three structural defects (ATP
starvation, no carryover test, no context mechanism active) and fixed them.
But even fixed, v2 is still using REAL in a supervised classification framing
that doesn't match its design.

The design conversation identified two core problems with the v2 framing:

1. The comparison axis (REAL accuracy vs MLP accuracy) asks the wrong
   question.  REAL's claim is substrate carryover efficiency, not final
   classification accuracy.

2. Sessions are not structured as sessions.  v1/v2 used an 80/20 sequential
   train/test split on individual windows — the same frame used for standard
   neural network evaluation.  REAL is designed around episodic sessions with
   substrate accumulated across them.

---

## Architectural decisions

### Sessions defined by state transitions

A session = maximal contiguous run of windowed episodes with the same
occupancy label.  This maps directly to the structure of REAL's CVT-1
experiment (Task A, B, C each with their own routing rule) but uses
naturally-occurring temporal segments from the occupancy data.

The occupancy dataset (14 days, 15-minute samples, ~1,344 rows) produces
approximately 60-80 sessions.  Each session is typically 5-40 episodes long.

Decision: segment on windowed episode labels (not raw rows).  This is
slightly cleaner because the episode is the unit the substrate operates on,
and every episode in a session shares the same routing target.

### Composite context code (0-3)

Context derived from per-session mean CO2 and light, relative to
training-set medians:

    co2_bit   = 1 if session_co2_mean  > co2_median  else 0
    light_bit = 1 if session_light_mean > light_median else 0
    context_code = co2_bit * 2 + light_bit

Rationale:
- Two sensor axes are more robust than CO2 alone (v2 lesson).
- CO2 and light are each correlated with occupancy but not deterministic —
  neither leaks the label.
- The four resulting context classes map to physically meaningful session
  types (overnight empty, daylit unoccupied, evening occupied, peak occupied).
- ConnectionSubstrate auto-registers context values 2 and 3 via
  `_ensure_context_registered` — no substrate changes needed.

### Context code applied at session level

Context is computed from all episodes in the session (offline, not
incrementally).  All episodes in the session receive the same context_code,
including the first ones.  This is slightly "future-knowing" but:
- Keeps the context stable and clean throughout the session.
- Avoids a chicken-and-egg problem (you need windows to estimate context, but
  the first windows don't have a context to route with yet).
- In a real deployment the running estimate would converge quickly; the
  offline computation is a reasonable approximation.

### Routing during priming

All episodes route and receive feedback, including the first episodes of a
session.  There is no observation-only priming window.  This is consistent
with REAL's local allostatic learning principle — the substrate should be
learning from the very first interaction, not waiting for a free look.

### Feedback always on

`eval_feedback_fraction=1.0` by default, following v2's hard-won lesson.
Both warm and cold eval paths receive full feedback.  The "training vs eval"
distinction in v3 refers to which substrate the system uses (accumulated vs
fresh), not whether feedback fires.

### Primary metric: carryover efficiency ratio

    efficiency_ratio[i] = warm_delivery[i] / cold_delivery[i]

at each eval session index.  The key scalar is `mean_efficiency_ratio` and
`sessions_to_80pct_delivery` for warm vs cold.

This is the occupancy analogue of CVT-1's 8-9× sample efficiency result.
A mean efficiency ratio > 1.0 means the carryover substrate consistently
routes better than cold-start on the same eval sessions.

---

## Files created

- `occupancy_baseline/session_splitter.py` — `OccupancySession` dataclass,
  `segment_into_sessions`, `compute_training_medians`, `assign_context_codes`,
  `session_inventory`.

- `scripts/occupancy_real_v3.py` — `OccupancyRealV3Config`, episode loader,
  `run_session_v3`, `_efficiency_metrics`, `_context_transfer_probe`,
  `run_occupancy_real_v3_experiment`.

- `scripts/run_occupancy_real_v3.py` — CLI entrypoint with formatted output
  for all four phases.

---

## What was NOT changed

- `phase8/`, `real_core/` — no modifications.
- `occupancy_real.py` and `occupancy_real_v2.py` — untouched.  v3 reuses
  helper functions (`_direct_inject_packet`, `_episode_batches`, etc.) via
  import from occupancy_real.
- The MLP baseline — untouched.  v3 does not produce an accuracy-vs-MLP
  comparison.

---

## Hypotheses to test

1. **Carryover accelerates session orientation.**
   H: warm_sessions_to_80pct < cold_sessions_to_80pct.

2. **Context code activates context-indexed substrate.**
   H: mean delivery ratio is higher with context codes than without
   (can verify by comparing cold system, which has no substrate support for
   any context, to warm system which has context-indexed support).

3. **Seen-context sessions benefit more from carryover than unseen-context
   sessions.**
   H: warm_seen_mean_delivery > warm_unseen_mean_delivery.
   This would demonstrate that the substrate's context-indexed action supports
   are doing useful work — not just general routing practice.

---

## Known limitations for v3 initial run

- Context is computed from full session feature data (offline).  In a
  real deployment, context would be estimated incrementally.

- The train/eval split is purely temporal (first 70% of sessions).  This
  means the model has not seen future temporal patterns.  If occupancy
  patterns shift over the 14-day window (e.g., weekend effects accumulate
  near the end), eval will be slightly harder than train.

- Session count (~60-80) is small.  The carryover efficiency curves will be
  noisy, especially at session 1 and 5.  Repeating with different
  `selector_seed` values would give confidence intervals.
