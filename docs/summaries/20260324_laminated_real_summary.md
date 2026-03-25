# Laminated REAL — Architecture and Results Summary

**Date:** 2026-03-24
**Scope:** full summary of the temporally laminated REAL system as implemented and tested to date

---

## What Was Built

The laminated system adds a structured outer loop on top of the existing Phase 8
substrate. The core idea from `docs/temporally_laminated_real_v0.md`:

> REAL may perform better when long-horizon work is decomposed into bounded slices
> whose outputs are compressed into strict summaries and regulated by a slower,
> lower-bandwidth layer, rather than by forcing one monolithic live substrate to keep
> all relevant structure active at once.

Three components were implemented:

### Fast execution layer — `Phase8SliceRunner`

Located in `phase8/lamination.py`. Wraps the existing `NativeSubstrateSystem` and
exposes a bounded `run_slice(slice_id, cycle_budget, regulatory_signal)` interface.

Each slice:
- runs up to `cycle_budget` cycles of the scenario workload
- applies any incoming `RegulatorySignal` before running (carryover filtering, gating)
- builds a compact `SliceSummary` from the resulting substrate state

The summary carries: `coherence_delta`, `mean_uncertainty`, `ambiguity_level`,
`conflict_level`, `guidance_alignment`, `cost_summary`, `examples_seen`,
`candidate_carryover_labels`, and `settlement_hint`.

### Slow regulatory layer — `HeuristicSliceRegulator`

Located in `real_core/lamination.py`. Consumes only the slice summary, never raw
substrate state.

Three decision paths:

- **Settle**: if recent slices are flat, low-conflict, and either (a) low ambiguity
  or (b) productive with tapering input, stop the run as good enough.
- **Escalate**: if recent slices are flat, high-ambiguity, and not productive, flag
  the regime as unresolvable by the current controller.
- **Branch**: if the run is productive but carryover is incompatible with continued
  progress, suggest a fork.

The regulator also adjusts the next slice budget: ×1.25 on improving + uncertainty-
dropping conditions, ×0.75 when flat and stale.

A critical fix was made to the escalation criterion during calibration: flat,
ambiguous slices only escalate when they are also *unproductive*. Productive tapering
runs can now settle instead of escalating. This was the key change that eliminated
bad escalate endings at B2S1.

### Laminated controller — `LaminatedController`

Located in `real_core/lamination.py`. Orchestrates the loop:

```
run_slice → SliceSummary → regulate → RegulatorySignal → SettlementDecision
```

Parameters: `max_slices` (hard cap on iterations), `initial_cycle_budget` (starting
budget for each slice, adjustable per the regulator).

Terminates early on `settle`, `escalate`, or `branch`. Falls through to `continue`
if `max_slices` is reached without a terminal signal.

### Contracts

All shared types live in `real_core`:

| Type | Role |
|---|---|
| `SliceSummary` | fast-to-slow payload, strictly summary-level |
| `RegulatorySignal` | slow-to-fast payload, bias/gating/carryover/budget |
| `SettlementDecision` | `continue / settle / branch / escalate` |
| `LaminatedRunResult` | final result including slice history |

The information discipline is intentionally narrow: `SessionCarryover` is explicitly
forbidden at the fast-to-slow interface, and the slow layer cannot emit raw state or
task solutions.

---

## Tests

Seven focused tests in `tests/test_lamination.py` and `tests/test_phase8_lamination.py`
cover the core contracts:

- `SliceSummary` rejects raw `SessionCarryover` in metadata
- Controller settles on flat, low-conflict history
- Controller escalates on flat, high-conflict history
- Controller settles on productive tapering history (the new regression test for the
  flat-ambiguous-but-productive case)
- `Phase8SliceRunner` produces a compact B2 summary with all required fields
- Carryover filter `drop` clears prior episodic entries before the next slice
- `evaluate_laminated_benchmark` returns baseline, laminated, and slice history

All 7 pass cleanly as of 2026-03-24.

---

## Calibration: B2S1

The calibration regime was 9 runs on `B2S1` (6-node, 18-example, single-pass hidden-
memory task) spanning a range of `max_slices` and `initial_cycle_budget` values.

Best operating point identified: **`max_slices=5, initial_cycle_budget=6`** (s5_b6).

Results at B2S1 with s5_b6:
- all 9 runs ended in `settle`
- exact match and bit accuracy matched baseline across all 9 runs
- approximately **0.77 lower average action cost** vs full baseline

This is the expected behavior at B2S1 scale: the 30-cycle total budget (5 × 6)
comfortably covers the full ~18-22 cycle scenario, so the regulator can observe
enough history to decide settlement, and does so before burning the remaining budget.

---

## First Real Benchmark: B2S5

### Setup

B2S5 is a significantly larger point:
- 75 nodes, 432 examples, 476 scenario cycles
- 10-layer DAG (widths: 4-6-9-12-12-11-8-6-4-2)
- same s5_b6 setting: `max_slices=5, initial_cycle_budget=6`
- total budget available: **30 cycles** (5 × 6)

### Coverage

30 cycles out of 476 = **6.3% of scenario cycles**, **6.9% of examples** (30/432).

This is the root cause of all results below.

### Results: Visible Mode

| | Baseline (full run) | Laminated s5_b6 |
|---|---|---|
| exact_matches | 130 | 11 |
| mean_bit_accuracy | 0.5810 | 0.6071 |
| total_action_cost | 68.73 | 11.56 |
| examples processed | 432 / 432 | 30 / 432 |
| final_decision | — | `continue` |

Deltas: `exact_matches −119`, `bit_accuracy +0.026`, `action_cost −57.17`

Slice-by-slice:

| Slice | Examples | Exact | Bit Acc | Ambiguity | Conflict | Hint |
|---|---|---|---|---|---|---|
| 1 | 6 | 1.0 | 0.417 | 1.0 | 0.417 | escalate |
| 2 | 6 | 5.0 | 0.917 | 1.0 | 0.367 | escalate |
| 3 | 6 | 2.0 | 0.583 | 1.0 | 0.275 | escalate |
| 4 | 6 | 1.0 | 0.500 | 1.0 | 0.833 | escalate |
| 5 | 6 | 2.0 | 0.625 | 1.0 | 0.413 | escalate |

Every slice reports `ambiguity=1.0`. The budget held flat at 6 throughout (no
`improving + uncertainty_dropping` signal), the regulator kept issuing `escalate`
hints, and the controller hit `max_slices` without reaching a terminal decision.
`final_decision=continue`.

### Results: Latent Mode

| | Baseline (full run) | Laminated s5_b6 |
|---|---|---|
| exact_matches | 161 | 9 |
| mean_bit_accuracy | 0.6303 | 0.5714 |
| total_action_cost | 69.35 | 75.80 |
| examples processed | 432 / 432 | 30 / 432 |
| final_decision | — | `continue` |

Deltas: `exact_matches −152`, `bit_accuracy −0.059`, `action_cost +6.45`

Slice-by-slice:

| Slice | Examples | Exact | Bit Acc | Ambiguity | Conflict | Hint |
|---|---|---|---|---|---|---|
| 1 | 6 | 1.0 | 0.500 | 0.167 | 0.0 | settle |
| 2 | 6 | 2.0 | 0.667 | 0.550 | 0.0 | escalate |
| 3 | 6 | 2.0 | 0.600 | 0.880 | 0.0 | escalate |
| 4 | 6 | 2.0 | 0.500 | 0.750 | 0.0 | escalate |
| 5 | 6 | 2.0 | 0.571 | 0.629 | 0.0 | escalate |

Conflict stays at 0.0 throughout (no stale-context pressure in latent mode), but
ambiguity rises steadily after slice 1. The local `settle` hint on slice 1 could
not trigger a controller decision because the regulator requires ≥2 slices of
history. By slice 2, ambiguity had already risen above the settle threshold.

---

## Interpretation

### 1. The s5_b6 setting is not scale-invariant

This is the central finding from the B2S5 run.

At B2S1: 30-cycle budget covers ~100%+ of the scenario. The regulator sees the full
workload and can settle correctly.

At B2S5: 30-cycle budget covers 6.9% of the scenario. The controller terminates on
`max_slices` not because the system settled, but because it ran out of slice budget
before it had seen enough of the task.

The apparent −57 action cost in visible mode is a side effect of doing 6.9% of
the work, not genuine efficiency. The latent mode cost actually increases because
routing overhead without context bits is higher per cycle, and the system never
gets enough examples to amortize that cost.

### 2. The regulator behaved correctly given what it could see

The regulator's `escalate` outputs in visible mode were not wrong given the
high-ambiguity summaries it received. The problem is that 6-cycle slices of a
75-node, 432-example scenario are too small a window for the ambiguity signal to
mean anything actionable. The regulator saw ambiguity=1.0 every slice because it
was watching 6 examples from a 432-example horizon, which is always
ambiguity-saturated from the controller's perspective.

### 3. What parity at B2S1 actually implied

The B2S1 calibration demonstrated that *when the budget covers the whole scenario*,
the laminated controller can match baseline quality and settle gracefully with lower
action cost. That is a meaningful result — it shows the architecture is sound and
the regulator logic is correct in principle.

B2S5 shows that the budget coverage assumption must be made explicit rather than
carried forward implicitly.

### 4. The B2S5 baseline is strong in its own right

The baseline numbers at B2S5 are worth noting separately from the lamination result:
- visible: 130/432 exact (0.301 rate), 0.581 bit accuracy
- latent: 161/432 exact (0.373 rate), 0.630 bit accuracy

This is in line with the B2 scale suite's general picture: `fixed-visible` and
`fixed-latent` are both workable at B2S5, with latent slightly stronger on exact
match for this task/seed. Those numbers come from running the full 476-cycle scenario.

---

## Open Questions

### The budget strategy question

There are three coherent interpretations of how budget should work at scale:

1. **Relative budget**: set `initial_cycle_budget = scenario.cycles // max_slices`
   at each scale point. For B2S5 that would be `476 // 5 = 95` cycles per slice.
   This preserves coverage parity but loses the efficiency motivation — the
   laminated run would cost roughly the same as the baseline.

2. **Strict early-stop**: treat the laminated controller as a budget-capped
   inference policy rather than a full-scenario replacement. In this framing,
   the B2S5 visible result (+0.026 bit accuracy on 30 examples at 6× lower
   cost) is a meaningful comparison — just against a budget-matched baseline, not
   the full run.

3. **Scale-adaptive calibration**: run a budget sweep at each new scale point to
   find the minimum `initial_cycle_budget` that achieves settlement, rather than
   carrying the B2S1 value upward. For B2S5, this would require running
   several trials to find the smallest per-slice budget that reliably produces
   `settle`.

These are not equivalent. The choice determines what lamination *means* in this
research context and should be settled before C3S5 is attempted.

### Does the regulator work at the right granularity for large scenarios?

At B2S5, the regulator receives a 6-example window each slice and cannot distinguish
between "genuinely ambiguous regime" and "too-early-in-the-scenario to see any
pattern." A budget-relative design, or a regulator that is aware of what fraction
of the scenario has been covered, might avoid this.

### Can the controller settle at any budget level at B2S5?

Unknown. With `initial_cycle_budget=95` (covering the full scenario across 5 slices),
would the regulator settle correctly? This is the next experiment if option 1 above
is chosen.

---

## What the Architecture Has Demonstrated

Despite the B2S5 scale mismatch, the implementation itself is working as designed:

- The `SliceSummary` and `RegulatorySignal` interface boundary held correctly
- No raw state leaked between layers
- The `drop` / `soften` / `keep` carryover modes apply correctly between slices
- Budget adjustment logic fires correctly (though in B2S5's case the condition for
  expansion was never met)
- All contract tests pass
- The productive-tapering settle path (the key regulator fix) works correctly and is
  now covered by a regression test

The laminated controller is a sound architectural addition. What it needs next is
a clear budget semantics decision before being extended to harder families.

---

## Related Documents

- `docs/temporally_laminated_real_v0.md` — design spec and architectural rationale
- `docs/traces/2026-03-24 1930 - B2S5 Laminated First Benchmark.md` — detailed B2S5 results and diagnosis
- `docs/summaries/20260324_cross_family_scale_summary.md` — broader family-by-family scale context
- `docs/summaries/20260324_b_scale_suite_summary.md` — B2 and B8 cold-start scale results
- `real_core/lamination.py` — `HeuristicSliceRegulator`, `LaminatedController`
- `phase8/lamination.py` — `Phase8SliceRunner`, `evaluate_laminated_scenario`
- `scripts/evaluate_laminated_phase8.py` — CLI entry point
- `tests/test_lamination.py`, `tests/test_phase8_lamination.py` — contract tests
