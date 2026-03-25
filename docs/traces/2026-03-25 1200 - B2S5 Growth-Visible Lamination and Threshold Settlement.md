# 2026-03-25 1200 - B2S5 Growth-Visible Lamination and Threshold Settlement

## Purpose

This trace records the introduction of `growth-visible` mode to the laminated
evaluation harness and the first successful threshold-driven settlement on B2S5. It
covers three sequential experiments that together demonstrate the slow layer acting
as a Global Closure Operator over a morphogenetically-enabled fast layer.

## Context

Prior session established the following:

- Temporally laminated REAL architecture was functional at B2S1 scale
- At B2S5 visible (non-growth) mode, the plain `self-selected` policy plateaus at
  ~0.58 bit_acc — the source defaults to `identity` for most packets, achieving only
  ~30% exact matches on a two-context task
- Per-context accuracy (`context_accuracy: Dict[str, float]`) was added to
  `SliceSummary` and populated per slice
- `HeuristicSliceRegulator` was extended with `accuracy_threshold` — settle fires
  when `min(context_accuracy.values()) >= threshold`
- Guidance bias wiring was added: slow layer seeds `ConnectionSubstrate` action
  support toward dominant hint transforms when `accuracy_gap > 0`
- With `max_slices=5, initial_cycle_budget=95`, the non-growth laminated run achieved
  0.597 bit_acc (vs 0.581 baseline) after 5 slices, `final_decision=continue` —
  threshold of 0.7 never fired because context_1 (`xor_mask_1010`) stuck at ~0.48–0.59

The core problem blocking threshold settlement in non-growth mode was a hint tie:
both `rotate_left_1` and `xor_mask_1010` had identical hint weights (0.546), so the
bias always seeded the globally dominant transform and couldn't break the context_1
stall.

## What Changed

### `growth-visible` mode added to CLI

`scripts/evaluate_laminated_phase8.py` extended to support four modes:
`visible`, `latent`, `growth-visible`, `growth-latent`.

Growth modes use the same scenario as their non-growth counterparts
(`visible_scenario` / `latent_scenario`) but pass `capability_policy="growth-visible"`
to `NativeSubstrateSystem`, which auto-enables morphogenesis at line 3281 of
`phase8/environment.py`:

```python
if resolved_policy in ("growth-visible", "growth-latent", "self-selected"):
    self.morphogenesis_config.enabled = True
```

No changes were needed to `phase8/lamination.py` or `real_core/lamination.py` —
morphogenesis is handled entirely within the substrate. The CLI change was:

```python
# mode → scenario mapping
if mode in ("visible", "growth-visible"):
    scenario = task.visible_scenario
elif mode in ("latent", "growth-latent"):
    scenario = task.latent_scenario

# capability_policy derived from mode for growth variants
resolved_capability_policy = mode if mode.startswith("growth-") else capability_policy
```

## Benchmark Configuration (all runs)

- Benchmark: `B2S5` — 75-node, 432-example hidden-memory task, 476 total cycles
- Task: `task_a`
- Seed: 13
- Mode: `growth-visible`
- Accuracy threshold: varies per run (see below)

---

## Run 1 — Growth-Visible, 15×32, threshold=0.7

**Command:** `--mode growth-visible --max-slices 15 --initial-cycle-budget 32 --accuracy-threshold 0.7`

**Growth-visible baseline (same mode, full 476c):**

| metric | value |
|---|---|
| exact_matches | 355 |
| mean_bit_accuracy | 0.8912 |
| total_action_cost | 64.737 |
| ctx0 bit_acc | 0.8731 |
| ctx1 bit_acc | 0.8990 |
| bud_successes | 6 |
| prune_events | 2 |
| apoptosis_events | 6 |

Morphogenesis alone closed the two-context gap entirely: full-scenario growth-visible
baseline hit 0.891 vs 0.581 for non-growth visible. The network grew 6 nodes and
pruned/apoptosed structure it no longer needed, restructuring to handle both
`rotate_left_1` and `xor_mask_1010` simultaneously.

**Laminated result:**

| metric | value |
|---|---|
| exact_matches | 51 |
| mean_bit_accuracy | 0.7105 |
| total_action_cost | 78.932 |
| ctx0 bit_acc | 0.6552 |
| ctx1 bit_acc | 0.7348 |
| final_decision | **settle** |
| slices run | **3 / 15** |
| cycles used | ~96 / 476 |

**Slice breakdown:**

| Slice | Budget | Ex | Exact | Bit Acc | Hint | ctx0 | ctx1 |
|---|---|---|---|---|---|---|---|
| 1 | 32 | 32 | 7 | 0.5000 | escalate | 0.667 | 0.435 |
| 2 | 32 | 32 | 16 | 0.7167 | escalate | 0.550 | 0.800 |
| 3 | 32 | 32 | 28 | 0.9091 | escalate | 0.750 | 0.978 |

**Why 3 slices, not 2:** Slice 2 had mean_bit_acc=0.717 > 0.7, but the min-context
check `min(ctx0=0.550, ctx1=0.800) = 0.550 < 0.7` — threshold not met.
Slice 3: `min(ctx0=0.750, ctx1=0.978) = 0.750 >= 0.7` → **settle fires**.

This is correct behavior — the per-context min guard prevented premature settlement
when only one context was performing well.

---

## Run 2 — Growth-Visible, 5×95, threshold=0.8

**Command:** `--mode growth-visible --max-slices 5 --initial-cycle-budget 95 --accuracy-threshold 0.8`

This is the "original" 5-slice test parameter set (one full scenario pass per slice)
with morphogenesis enabled and a stricter threshold.

**Laminated result:**

| metric | value |
|---|---|
| exact_matches | 140 |
| mean_bit_accuracy | 0.8413 |
| total_action_cost | 80.731 |
| ctx0 bit_acc | 0.8246 |
| ctx1 bit_acc | 0.8485 |
| final_decision | **settle** |
| slices run | **2 / 5** |
| cycles used | ~190 / 476 |

**Slice breakdown:**

| Slice | Budget | Ex | Exact | Bit Acc | Hint | ctx0 | ctx1 |
|---|---|---|---|---|---|---|---|
| 1 | 95 | 95 | 50 | 0.7074 | escalate | 0.655 | 0.731 |
| 2 | 95 | 95 | 90 | 0.9737 | escalate | 1.000 | 0.963 |

**Threshold check after slice 1:** `min(0.655, 0.731) = 0.655 < 0.8` → continue.
**Threshold check after slice 2:** `min(1.000, 0.963) = 0.963 >= 0.8` → **settle fires**.

The laminated system reached 0.841 mean bit_acc covering only 190 of 476 cycles
(**40% of the scenario**) and correctly terminated. Three unused slices were
discarded. The 0.05 gap vs the full-scenario baseline reflects covering only 40%
of packets — not underperformance on those packets.

---

## Interpretation

### Morphogenesis solves the hint-tie problem

The core blocker in all prior non-growth runs was a hint tie: both transforms had
identical support weights and the bias seeding couldn't break the context_1 stall.
Morphogenesis bypasses this entirely. Rather than trying to tilt an existing fixed
substrate toward the correct transforms, the network grows new structure that
routes each context independently. The substrate topology becomes the disambiguation
mechanism rather than action-support weights.

### The slow layer is functioning as a Global Closure Operator

With growth-visible + threshold=0.8, the fast layer adapted in two slices.
The slow layer monitored per-context accuracy, evaluated that both contexts were
above the target, and issued a `settle` decision — correctly halting the run at 40%
scenario coverage. This is precisely the intended behavior: the slow layer acts as a
closure condition over fast-layer learning, stopping the process when the learned
configuration is good enough rather than when the scenario clock runs out.

### Budget-shrink fix held correctly

The budget-shrink-on-poor-performance logic was corrected in the prior session
(budget should shrink under good performance to reduce wasted cycles, not grow
under poor performance). Budget held at 95 through both slices in Run 2, confirming
the fix is stable.

### Settlement hint vs settlement decision

All slices in both runs reported `hint=escalate`. The accuracy threshold settle
check fires at the TOP of `_should_settle`, before the heuristic conflict/ambiguity
logic. Settle correctly overrides escalate when the threshold is met. The hint
reflects the heuristic layer's reading of the fast-layer state (high conflict,
ambiguity still present); the threshold settle reflects the slow layer's goal
criterion. These can and should disagree.

---

## Files Touched

| File | Change |
|---|---|
| `scripts/evaluate_laminated_phase8.py` | Added `growth-visible`, `growth-latent` to `--mode` choices; auto-derives `capability_policy` for growth modes |

No changes to `phase8/lamination.py` or `real_core/lamination.py` — morphogenesis
is handled entirely within `NativeSubstrateSystem`.

---

## Next Steps

1. Test `growth-latent` mode — latent scenario removes explicit context bits, forcing
   the substrate to learn context from sequence structure alone. Growth may or may not
   help when the context signal is implicit.
2. Run C-family benchmarks (ambiguity-heavy tasks) with growth-visible to see if
   morphogenesis helps where context is noisy rather than hidden.
3. Consider a sweep over `accuracy_threshold` values (0.7, 0.8, 0.85, 0.9) to
   characterize the cost vs quality tradeoff curve for growth-visible lamination.
4. Examine per-slice growth events (buds/prunes/apoptosis) to understand whether
   morphogenesis is frontloaded to early slices or distributed across the run.
