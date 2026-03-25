# 2026-03-24 1930 - B2S5 Laminated First Benchmark

## Purpose

This trace records the first real-scale laminated benchmark run on B2S5, following
the B2S1 calibration work that established `max_slices=5, initial_cycle_budget=6`
as the recommended operating point. The goal was to check whether the cost/quality
tradeoff seen at B2S1 still holds before moving to C3S5.

## Context

Prior session (Codex) completed the lamination architecture and calibrated on B2S1:

- `real_core/lamination.py`: `HeuristicSliceRegulator` and `LaminatedController`
- `phase8/lamination.py`: `Phase8SliceRunner` and `evaluate_laminated_scenario`
- `scripts/evaluate_laminated_phase8.py`: CLI evaluation entry point
- `tests/test_lamination.py`, `tests/test_phase8_lamination.py`: focused test suite

B2S1 calibration result (from handoff):
- all 9 small runs ended in `settle`
- exact/bit accuracy matched baseline across all runs
- ~0.77 lower action cost on average

Focused tests confirmed passing before this benchmark run:

```
python -m unittest tests.test_lamination tests.test_phase8_lamination
# Ran 7 tests in 0.605s — OK
```

## Benchmark Configuration

- Benchmark: `B2S5` — 75-node, 432-example aspirational hidden-memory scale point on a
  deeper layered DAG (layer widths: 4-6-9-12-12-11-8-6-4-2, 10 layers)
- Scenario cycles: 476 (432 examples + 44 slack)
- Task: `task_a` (visible and latent modes)
- Seed: 13
- `max_slices=5`, `initial_cycle_budget=6` (the calibrated s5_b6 setting)
- Total budget available to laminated controller: 30 cycles (5 × 6)

## Results

### Visible Mode

| | Baseline | Laminated |
|---|---|---|
| exact_matches | 130 | 11 |
| mean_bit_accuracy | 0.5810 | 0.6071 |
| total_action_cost | 68.728 | 11.558 |
| examples processed | 432 / 432 | 30 / 432 |
| final_decision | — | `continue` |

Deltas vs baseline: `exact_matches -119`, `bit_accuracy +0.026`, `action_cost -57.17`

Slice history:

| Slice | Budget | Cycles | Examples | Exact | Bit Acc | Ambiguity | Conflict | Hint |
|---|---|---|---|---|---|---|---|---|
| 1 | 6 | 6 | 6 | 1.0 | 0.417 | 1.0 | 0.417 | escalate |
| 2 | 6 | 6 | 6 | 5.0 | 0.917 | 1.0 | 0.367 | escalate |
| 3 | 6 | 6 | 6 | 2.0 | 0.583 | 1.0 | 0.275 | escalate |
| 4 | 6 | 6 | 6 | 1.0 | 0.500 | 1.0 | 0.833 | escalate |
| 5 | 6 | 6 | 6 | 2.0 | 0.625 | 1.0 | 0.413 | escalate |

Final signal: `decision=continue`, `stop_reason=""`, `carryover=soften`, `pressure=medium`

### Latent Mode

| | Baseline | Laminated |
|---|---|---|
| exact_matches | 161 | 9 |
| mean_bit_accuracy | 0.6303 | 0.5714 |
| total_action_cost | 69.351 | 75.799 |
| examples processed | 432 / 432 | 30 / 432 |
| final_decision | — | `continue` |

Deltas vs baseline: `exact_matches -152`, `bit_accuracy -0.059`, `action_cost +6.45`

Slice history:

| Slice | Budget | Cycles | Examples | Exact | Bit Acc | Ambiguity | Conflict | Hint |
|---|---|---|---|---|---|---|---|---|
| 1 | 6 | 6 | 6 | 1.0 | 0.500 | 0.167 | 0.0 | settle |
| 2 | 6 | 6 | 6 | 2.0 | 0.667 | 0.550 | 0.0 | escalate |
| 3 | 6 | 6 | 6 | 2.0 | 0.600 | 0.880 | 0.0 | escalate |
| 4 | 6 | 6 | 6 | 2.0 | 0.500 | 0.750 | 0.0 | escalate |
| 5 | 6 | 6 | 6 | 2.0 | 0.571 | 0.629 | 0.0 | escalate |

Final signal: `decision=continue`, `stop_reason=""`, `carryover=keep`, `pressure=medium`

## Diagnosis

### Root cause: budget mismatch, not quality regression

The s5_b6 setting is not scale-invariant. At B2S1, the total scenario is ~18-22
cycles. A 30-cycle budget (5 × 6) comfortably covers the full run, which is why all
9 B2S1 runs settled and matched baseline quality.

At B2S5 the scenario runs 476 cycles. The same 30-cycle budget covers only 30/476 =
**6.3% of cycles** and **6.9% of examples** (30 of 432). The laminated controller
hits `max_slices` and terminates with `continue` — it never ran enough of the
scenario to accumulate the signal needed to settle.

The apparent −57 action cost in visible mode is almost entirely a side effect of
stopping after 6.9% of work. It is not genuine efficiency.

### Visible mode: regulator reads persistent escalation

Every slice in visible mode reported `ambiguity=1.0`. The regulator saw flat,
high-ambiguity slices across all five slices and kept signalling `escalate` — but
the regulator also requires two consecutive slices to fire an escalate decision, and
the budget clock ran out first. Result: `final_decision=continue`, not `escalate`.

The budget was never scaled up between slices (no `improving + uncertainty_dropping`
signal to trigger the ×1.25 budget expansion). The regulator held the budget flat at
6 the entire run.

### Latent mode: early settle followed by ambiguity growth

Slice 1 of the latent run had low ambiguity (0.167) and met the local `settle` hint
criteria. But the regulator requires ≥2 slices before it can return a settle
decision, so the controller continued. By slices 2–5, ambiguity rose to 0.55–0.88
as more of the hard-to-route latent packets accumulated. Conflict stayed at 0.0
throughout (no stale-context pressure without explicit context bits), but the rising
ambiguity kept the hint on `escalate`.

The latent mode also showed a cost increase vs baseline (+6.45). This is because
the controller still incurred overhead across 30 cycles of a harder routing problem
(no context bits) without completing enough of the workload to show net gains.

### The calibration gap

The B2S1 calibration exposed a structural assumption: that `initial_cycle_budget=6`
is meaningful relative to scenario length. At B2S1 scale it is. At B2S5 scale, 6
cycles per slice is a rounding error on the total workload.

To maintain the same coverage fraction as B2S1, B2S5 would need approximately
`initial_cycle_budget = round(476 / 5) = 95` cycles per slice. That would be a
fundamentally different operating regime.

## Working Read

The s5_b6 setting is a B2S1-scale configuration. It should not be applied
unchanged to B2S5 and above. The laminated controller is architecturally sound —
the contracts, regulator logic, and slice mechanics all worked correctly — but the
budget values are not portable across scale points.

Before moving to C3S5, the question to answer is what lamination should mean at
scale:

1. **Relative budget**: set `initial_cycle_budget` as a fraction of scenario cycles
   (e.g., `scenario.cycles // max_slices`). This preserves coverage parity but loses
   the efficiency motivation at larger scales.

2. **Strict early-stop as the intent**: accept that the laminated controller
   intentionally stops well before full coverage, and evaluate it as a budget-capped
   policy rather than as a full-scenario quality match. In that framing the B2S5
   visible result (+0.026 bit accuracy on 30 examples at 6× lower cost) is
   meaningful — just a different comparison than "parity with baseline."

3. **Scale-adaptive calibration**: run a separate s5_b_N sweep at each scale point
   to find the minimum budget that achieves settlement, instead of carrying the B2S1
   calibration value up the ladder.

The C3S5 recommendation from the prior session should be held pending this
decision.

## Next Steps

1. Decide which of the three budget strategies above fits the research intent before
   extending to C3S5 or larger B scale points.
2. If relative budget is chosen, re-run B2S5 with `initial_cycle_budget=95` (or
   `scenario_cycles // max_slices`) and check whether the regulator can now settle
   rather than hitting the slice cap.
3. If strict early-stop is the intent, write a separate comparison harness that
   evaluates baseline on the same 30-cycle budget so the laminated result is
   comparable.
4. Document the chosen interpretation in a follow-up trace before broadening the
   laminated benchmark sweep.
