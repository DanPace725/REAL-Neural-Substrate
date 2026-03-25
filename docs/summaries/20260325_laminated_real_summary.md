# Laminated REAL — Architecture and Results Summary (Updated)

**Date:** 2026-03-25
**Scope:** Full summary of the temporally laminated REAL system — architecture,
all benchmark results, and the path to first successful threshold settlement.
Supersedes `20260324_laminated_real_summary.md`.

---

## What Was Built

The laminated system adds a structured outer loop on top of the existing Phase 8
substrate. The core idea from `docs/temporally_laminated_real_v0.md`:

> REAL may perform better when long-horizon work is decomposed into bounded slices
> whose outputs are compressed into strict summaries and regulated by a slower,
> lower-bandwidth layer, rather than by forcing one monolithic live substrate to keep
> all relevant structure active at once.

The slow layer is intended to act as a **Global Closure Operator** over the fast
layer: monitoring compact accuracy signals, tilting the fast layer toward a
metastable configuration, and issuing a stop signal once the target is reached.

### Fast execution layer — `Phase8SliceRunner`

Located in `phase8/lamination.py`. Wraps `NativeSubstrateSystem` and exposes a
bounded `run_slice(slice_id, cycle_budget, regulatory_signal)` interface.

Each slice:
- runs up to `cycle_budget` cycles of the scenario workload
- applies any incoming `RegulatorySignal` before running (bias seeding, carryover filtering)
- builds a compact `SliceSummary` from the resulting substrate state

Summary fields: `coherence_delta`, `mean_uncertainty`, `ambiguity_level`,
`conflict_level`, `guidance_alignment`, `cost_summary`, `examples_seen`,
`candidate_carryover_labels`, `settlement_hint`, `context_accuracy`,
`metadata` (including `mean_bit_accuracy`).

### Slow regulatory layer — `HeuristicSliceRegulator`

Located in `real_core/lamination.py`. Consumes only the slice summary — never raw
substrate state or task solutions.

Decision paths:

- **Settle (threshold)**: fires when `min(context_accuracy.values()) >= accuracy_threshold`.
  Checked first, before heuristic settle logic, so it overrides conflict/ambiguity signals.
- **Settle (heuristic)**: fires when recent slices are flat, low-conflict, and either
  (a) low ambiguity or (b) productive with tapering input.
- **Escalate**: fires when recent slices are flat, high-ambiguity, and not productive.
- **Branch**: fires when productive but carryover is incompatible with continued progress.
- **Continue**: default.

The regulator also:
- adjusts the next slice budget: ×1.25 when `improving + uncertainty_dropping`,
  holds steady (no longer shrinks) when `weak_context_gap > 0` (accuracy target not met).
- emits `bias_updates` including `accuracy_gap`, `weak_context_bit`, `weak_context_gap`
  for the fast layer to use when seeding action support.

### Laminated controller — `LaminatedController`

Located in `real_core/lamination.py`. Orchestrates the loop:

```
run_slice → SliceSummary → regulate → RegulatorySignal → SettlementDecision
```

Parameters: `max_slices` (hard cap), `initial_cycle_budget` (starting budget,
adjustable per the regulator).

Terminates early on `settle`, `escalate`, or `branch`. Falls through to `continue`
if `max_slices` is reached without a terminal signal.

### Contracts

All shared types live in `real_core`:

| Type | Role |
|---|---|
| `SliceSummary` | fast-to-slow payload, strictly summary-level |
| `RegulatorySignal` | slow-to-fast payload: bias/gating/carryover/budget |
| `SettlementDecision` | `continue / settle / branch / escalate` |
| `LaminatedRunResult` | final result including slice history |

The information boundary is narrow by design: `SessionCarryover` is explicitly
forbidden at the fast-to-slow interface, and the slow layer cannot emit raw state.

---

## Capability Modes

The laminated harness supports four modes:

| Mode | Scenario | Morphogenesis | Capability Policy |
|---|---|---|---|
| `visible` | visible | off | `self-selected` (or explicit) |
| `latent` | latent | off | `self-selected` (or explicit) |
| `growth-visible` | visible | **on** | `growth-visible` |
| `growth-latent` | latent | **on** | `growth-latent` |

Growth modes pass `capability_policy="growth-visible"` to `NativeSubstrateSystem`,
which auto-enables morphogenesis internally. No changes to `phase8/lamination.py`
or `real_core/lamination.py` were needed — the substrate handles it entirely.

Morphogenesis allows the network to grow new relay nodes and prune underperforming
connections between slices, restructuring topology in response to routing pressure.

---

## Tests

Seven focused tests in `tests/test_lamination.py` and `tests/test_phase8_lamination.py`:

- `SliceSummary` rejects raw `SessionCarryover` in metadata
- Controller settles on flat, low-conflict history
- Controller escalates on flat, high-conflict history
- Controller settles on productive tapering history (regression for flat-ambiguous-
  but-productive case)
- `Phase8SliceRunner` produces a compact B2 summary with all required fields
- Carryover filter `drop` clears prior episodic entries before the next slice
- `evaluate_laminated_benchmark` returns baseline, laminated, and slice history

All 7 pass cleanly as of 2026-03-24.

---

## Benchmark Results

### B2S1 — Calibration (2026-03-24)

B2S1 is the 6-node, 18-example, single-pass hidden-memory task. Best operating
point: **`max_slices=5, initial_cycle_budget=6`** (s5_b6).

- All 9 calibration runs ended in `settle`
- Exact match and bit accuracy matched baseline across all runs
- ~0.77 lower average action cost vs full baseline

This works because the 30-cycle budget (5×6) comfortably covers the ~18-22 cycle
scenario. The regulator sees enough history to settle correctly.

---

### B2S5 — Non-Growth Visible (2026-03-24)

B2S5: 75-node, 432-example, 476 total cycles, 10-layer DAG.

**Root cause of all non-growth results:** the task has two contexts —
`context_0 → rotate_left_1` (130 packets), `context_1 → xor_mask_1010` (302 packets).
Without morphogenesis, the source node defaults to `identity` for most packets,
and a hint tie (`rotate_left_1` and `xor_mask_1010` both score 0.546) prevents
guidance bias from breaking the context_1 stall.

#### s5_b6 (initial test)

Total budget: 30 cycles = 6.3% of scenario.

| | Baseline | Laminated s5_b6 |
|---|---|---|
| exact_matches | 130 | 11 |
| mean_bit_accuracy | 0.581 | 0.607 |
| total_action_cost | 68.73 | 11.56 |
| final_decision | — | `continue` (max_slices hit) |

The controller hit `max_slices` before seeing enough signal. Apparent −57 cost is
a side effect of doing 6.9% of the work.

#### 5×95 with accuracy_threshold=0.7 (guidance bias active)

One full scenario pass per slice. Bias seeding wired to `ConnectionSubstrate`.
Per-context accuracy added to `SliceSummary`.

| | Baseline | Lam 5×95 thresh=0.7 |
|---|---|---|
| exact_matches | 130 | 126 |
| mean_bit_accuracy | 0.581 | 0.597 |
| total_action_cost | 68.73 | 52.42 |
| final_decision | — | `continue` (thresh never fired) |
| slices run | — | 5 / 5 |

Context_1 peaked at 0.587 — bias helps but can't break the hint tie. Threshold
of 0.7 never fires. Per-context min-accuracy logic correctly blocked premature
settlement when only one context was passing.

#### 10×48 / 15×32 sweeps

Testing different slice granularities (10 and 15 slices) confirmed the same
ceiling: context_1 oscillates between 0.42–0.59 without monotonic improvement.
Budget-shrink fix confirmed stable (budget held at configured value throughout).

**Key finding:** the hint-tie problem cannot be resolved by guidance bias on a
fixed topology. Context_1 accuracy requires either structural change (morphogenesis)
or a smarter disambiguation signal.

---

### B2S5 — Growth-Visible (2026-03-25)

Morphogenesis enabled via `--mode growth-visible`. The network can grow relay nodes
and prune underperforming connections during the run.

#### Growth-Visible Baseline (full 476c)

| metric | value |
|---|---|
| exact_matches | **355** |
| mean_bit_accuracy | **0.891** |
| total_action_cost | 64.74 |
| ctx0 bit_acc | 0.873 |
| ctx1 bit_acc | 0.899 |
| bud_successes | 6 |
| prune_events | 2 |
| apoptosis_events | 6 |

Morphogenesis alone closes the two-context gap entirely: 355 exact vs 130 non-growth.
The network grew 6 nodes and restructured topology to handle both contexts
independently — the disambiguation mechanism is topological, not weight-based.

#### Laminated Growth-Visible — 15×32, threshold=0.7

| | Baseline (full) | Lam growth 15×32 thresh=0.7 |
|---|---|---|
| exact_matches | 355 | 51* |
| mean_bit_accuracy | 0.891 | 0.710 |
| total_action_cost | 64.74 | 78.93 |
| final_decision | — | **settle** |
| slices run | — | **3 / 15** |
| cycles used | 476 | ~96 (20%) |

*\*Only 95 packets processed — run stopped at 20% of scenario*

Slice history:

| Slice | Budget | Exact | Bit Acc | Hint | ctx0 | ctx1 |
|---|---|---|---|---|---|---|
| 1 | 32 | 7 | 0.500 | escalate | 0.667 | 0.435 |
| 2 | 32 | 16 | 0.717 | escalate | 0.550 | 0.800 |
| 3 | 32 | 28 | 0.909 | escalate | 0.750 | 0.978 |

Slice 2: mean=0.717 > 0.7 but `min(0.550, 0.800) = 0.550 < 0.7` → no settle.
Slice 3: `min(0.750, 0.978) = 0.750 >= 0.7` → **settle fires**. ✓

#### Laminated Growth-Visible — 5×95, threshold=0.8

| | Baseline (full) | Lam growth 5×95 thresh=0.8 |
|---|---|---|
| exact_matches | 355 | 140* |
| mean_bit_accuracy | 0.891 | 0.841 |
| total_action_cost | 64.74 | 80.73 |
| final_decision | — | **settle** |
| slices run | — | **2 / 5** |
| cycles used | 476 | ~190 (40%) |

*\*Only 190 cycles processed — run stopped at 40% of scenario*

Slice history:

| Slice | Budget | Exact | Bit Acc | Hint | ctx0 | ctx1 |
|---|---|---|---|---|---|---|
| 1 | 95 | 50 | 0.707 | escalate | 0.655 | 0.731 |
| 2 | 95 | 90 | 0.974 | escalate | 1.000 | 0.963 |

Slice 1: `min(0.655, 0.731) = 0.655 < 0.8` → continue.
Slice 2: `min(1.000, 0.963) = 0.963 >= 0.8` → **settle fires**. ✓

The laminated system reached 0.841 mean bit_acc at 40% coverage and stopped.
Three unused slices discarded.

---

## Overall Results Table

| Run | Mode | Slices | Budget | Threshold | Bit Acc | Exact | Final Decision |
|---|---|---|---|---|---|---|---|
| B2S1 calibration | visible | 5 | 6 | none | ≈baseline | ≈baseline | settle (all 9) |
| B2S5 s5_b6 | visible | 5 | 6 | none | 0.607 | 11 | continue |
| B2S5 5×95 | visible | 5 | 95 | 0.7 | 0.597 | 126 | continue |
| B2S5 10×48 | visible | 10 | 48 | 0.7 | 0.594 | 132 | continue |
| B2S5 15×32 | visible | 15 | 32 | 0.7 | 0.597 | 131 | **settle** (14 slices) |
| B2S5 15×32 | growth-visible | 15 | 32 | 0.7 | **0.710** | 51* | **settle (3 slices)** |
| B2S5 5×95 | growth-visible | 5 | 95 | 0.8 | **0.841** | 140* | **settle (2 slices)** |

\* Stopped early — fewer total packets, not underperformance.

---

## Key Findings

### 1. Scale-invariance of s5_b6

The B2S1 calibration value (`initial_cycle_budget=6`) covers ~100% of B2S1 but
only 6.3% of B2S5. It cannot be carried forward. Budget must be expressed relative
to scenario size for results to be comparable.

### 2. Morphogenesis solves what guidance bias cannot

On a fixed topology, the hint-tie problem (identical support weights for the two
required transforms) made context_1 unresolvable by bias seeding alone. Morphogenesis
bypasses this: the network grows structure to handle each context independently,
making disambiguation topological rather than weight-based. B2S5 baseline jumped
from 0.581 to 0.891 bit_acc.

### 3. The slow layer is functioning as a Global Closure Operator

With growth-visible + threshold, the slow layer correctly:
- monitors per-context min accuracy each slice
- withholds settle while any context is below threshold (even if mean is above)
- fires settle as soon as all contexts are above threshold
- discards unused slices rather than running them unnecessarily

This is the intended behavior: stop when the fast layer has reached a good
configuration, not when the scenario clock runs out.

### 4. Settlement hint vs settlement decision

In all growth-visible runs, every slice reported `hint=escalate` from the heuristic
layer (high conflict, ambiguity present). The threshold settle check fires first and
overrides the hint. This is correct: the heuristic reads internal routing state,
the threshold reads task performance. They measure different things and can disagree.

### 5. Per-context min-accuracy correctly blocks premature settlement

The guard `min(context_accuracy.values()) >= threshold` rather than `mean >= threshold`
prevented slice 2 of the 15×32 run from settling when only one context was passing.
This is the right semantics: the slow layer should not declare success until all
contexts are handled, not just the easy one.

---

## Architecture Summary: What Each Layer Does

```
Fast layer (Phase8SliceRunner)
  ├── Runs bounded cycles of scenario workload
  ├── Applies morphogenesis (bud/prune/apoptosis) within cycle budget
  ├── Applies guidance bias from slow layer before each slice
  └── Emits compact SliceSummary (per-context accuracy, coherence, conflict)

Slow layer (HeuristicSliceRegulator)
  ├── Reads SliceSummary only — no raw state access
  ├── Checks accuracy threshold (min per-context) as primary settle criterion
  ├── Falls back to heuristic settle/escalate for non-threshold runs
  ├── Emits RegulatorySignal (carryover mode, budget, bias_updates)
  └── Acts as Global Closure Operator: stop when good, not when time is up

Controller (LaminatedController)
  ├── Orchestrates fast/slow loop up to max_slices
  ├── Terminates early on settle/escalate/branch
  └── Falls through to continue if max_slices reached
```

---

## Open Questions

1. **Growth-latent**: does morphogenesis help when context bits are absent? The
   substrate must infer context from sequence structure — harder than visible mode.

2. **C-family benchmarks**: ambiguity-heavy tasks with noisy context. Does growth
   help where the challenge is disambiguation noise rather than hidden signal?

3. **Threshold sweep**: what is the cost vs quality tradeoff curve across
   thresholds (0.7, 0.8, 0.85, 0.9) for growth-visible? At what threshold does
   the laminated run require more slices than the full-scenario baseline?

4. **Slice-level growth events**: buds/prunes/apoptosis are reported in the final
   summary but not per slice. Adding slice-level morphogenesis counts to
   `SliceSummary` would let the regulator adjust pressure based on whether growth
   has stabilized.

5. **Cost comparison framing**: the current delta vs baseline compares a partial-
   coverage laminated run against a full-scenario baseline. A budget-matched
   comparison (baseline run capped to the same cycle count) would give a cleaner
   efficiency number.

---

## Related Documents

- `docs/temporally_laminated_real_v0.md` — design spec and architectural rationale
- `docs/traces/2026-03-24 1930 - B2S5 Laminated First Benchmark.md` — s5_b6 detailed results
- `docs/traces/2026-03-25 1200 - B2S5 Growth-Visible Lamination and Threshold Settlement.md` — growth-visible results and threshold settlement
- `docs/summaries/20260324_cross_family_scale_summary.md` — broader family-by-family scale context
- `docs/summaries/20260324_b_scale_suite_summary.md` — B2 and B8 cold-start scale results
- `real_core/lamination.py` — `HeuristicSliceRegulator`, `LaminatedController`
- `phase8/lamination.py` — `Phase8SliceRunner`, `evaluate_laminated_scenario`
- `scripts/evaluate_laminated_phase8.py` — CLI entry point (all four modes)
- `tests/test_lamination.py`, `tests/test_phase8_lamination.py` — contract tests
