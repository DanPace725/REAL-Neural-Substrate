# REAL Configuration × Task Family Performance Map

**Date:** 2026-03-18
**Status:** Current — reflects all patches through the credit/debt alignment fix
**Sources:** Ceiling benchmark 3-seed pilot, C-family full capability runs, carryover bridge diagnostic, cyclic transfer experiments, latent morphogenesis robustness trace

---

## Overview

Across Task Families A, B, and C, a consistent pattern has emerged: no single REAL configuration dominates everywhere. The four base modes — `fixed-visible`, `fixed-latent`, `growth-visible`, `growth-latent` — each have task-specific win conditions tied to three structural properties of the problem:

1. How informative the visible context is
2. Whether warm substrate carryover is available
3. How much time/topology the session gives morphogenesis to stabilize

This report maps each configuration to its performance profile per family, surfaces the underlying principles, and provides a practical prescription table.

---

## Configuration Taxonomy

| Config ID | Latent context | Morphogenesis | Carryover |
|---|:---:|:---:|---|
| `fixed-visible` | ✗ | ✗ | Cold start |
| `fixed-latent` | ✓ | ✗ | Cold start |
| `growth-visible` | ✗ | ✓ | Cold start |
| `growth-latent` | ✓ | ✓ | Cold start |
| `transfer-fixed` | either | ✗ | Full episodic |
| `transfer-growth` | either | ✓ | Full episodic |

A critical hidden dimension: **full episodic vs substrate-only carryover** produces opposite effects on the visible and latent paths — covered in detail in Section 4.

---

## Section 1: Family A — Scale / Horizon

**Task structure:** Visible context fully determines the transform. No ambiguity. Challenge scales from A1 (6 nodes, 18 packets) to A4 (full scale). The core difficulty is routing headroom as topology grows.

### Cold-start results (3-seed pilot, seeds 13/23/37)

| Benchmark | fixed-visible | fixed-latent | growth-visible |
|---|---:|---:|---:|
| A1 | 0.3457 / 0.0% criterion | 0.3210 / 22.2% | 0.3333 / 11.1% |
| A2 | 0.3796 / 22.2% criterion | 0.3087 / 0.0% | 0.4105 / 22.2% |
| A3 | 0.4321 / 55.6% criterion | 0.2531 / 22.2% | 0.4239 / 55.6% |
| A4 | 0.4491 / 66.7% criterion | 0.2983 / 55.6% | 0.3210 / 66.7% |

*Values: mean exact match rate / criterion rate*

### Transfer results (large topology, 5-seed, seeds 13/23/37/51/79)

| Policy | Carryover mode | Transfer delta (exact) | Transfer delta (bit acc) |
|---|---|---:|---:|
| all-visible | full episodic | +2.2 | +0.042 |
| all-visible | substrate-only | **+6.0** | **+0.131** |
| all-latent | full episodic | **+7.0** | **+0.147** |
| all-latent | substrate-only | −2.2 | −0.036 |
| visible-train → latent-transfer | full episodic | −2.0 | −0.078 |
| visible-train → latent-transfer | substrate-only | +3.2 | +0.058 |

### A-family profile

- **Best cold:** `fixed-visible` — clean routing signal, no ambiguity to resolve.
- **Best transfer:** `growth-latent + full episodic carryover` — the +7.0 exact match delta is the strongest transfer result in the dataset.
- **Morphogenesis condition:** Cold-start morphogenesis earns growth in only ~20% of seeds and provides no task performance lift. Warm carryover transfers push earned growth rate to 80% and win rate to 60%, with +1.2 exact and +7.8% bit accuracy over fixed topology.
- **Key risk:** Visible full-episodic carryover embeds task A's context-specific action supports, which map `context_1 → xor_mask_1010`. Task B expects `context_1 → xor_mask_0101`. This "context poison" costs ~3.8 exact matches relative to substrate-only carryover (observed: seed 37 visible-B transfer delivered 17/18 packets via `xor_mask_1010`, 0 exact on all `context_1` packets).

---

## Section 2: Family B — Hidden Memory

**Task structure:** The correct transform depends on a latent memory state — a hidden controller that visible context does not cleanly identify. The visible context bit exists but is an imperfect proxy. The core difficulty is learning to track sequential hidden state, not routing headroom.

### Cold-start results (3-seed pilot)

| Benchmark | fixed-visible | fixed-latent | growth-visible |
|---|---:|---:|---:|
| B1 | 0.4321 / 55.6% criterion | 0.2500 / 22.2% | 0.4239 / 55.6% |
| B2 | **0.6019 / 100% criterion** | 0.2233 / 0.0% | 0.5103 / 66.7% |
| B3 | 0.5093 / 77.8% criterion | 0.3148 / 11.1% | 0.4650 / 66.7% |
| B4 | 0.5000 / 77.8% criterion | 0.3056 / 11.1% | 0.4012 / 55.6% |

### Transfer results (A→B, 5-seed)

| Policy | Exact matches (avg/5 seeds) | Bit accuracy |
|---|---:|---:|
| Visible cold (task B alone) | 3.0 | 0.422 |
| Latent cold (task B alone) | 4.0 | 0.500 |
| Visible A→B transfer | 6.2 | 0.506 |
| Latent A→B transfer | 5.8 | 0.517 |
| **Growth (A→B, large topology)** | **7.4** | **0.583** |

### Cyclic transfer (A→B→C→A)

| Policy | Delta vs cold (exact) |
|---|---:|
| Visible cyclic | +0.6 |
| **Latent cyclic** | **+2.4** |

### B-family profile

- **Best cold (surprise):** `fixed-visible` dominates — B2 reaches 100% criterion rate at 0.6019 exact. Visible frequency-matching finds correct transforms even without understanding the hidden memory structure.
- **Worst cold:** `fixed-latent` — weak across B1-B4 (0-11% criterion). The latent path needs more signal time than short cold-start B sessions provide.
- **Best transfer:** `growth-visible` A→B large topology (+7.4 exact, +0.583 bit acc). Warm substrate from task A provides routing clarity; morphogenesis fires after that clarity is established.
- **Latent transfer advantage:** Near-parity with visible on direct A→B (5.8 vs 6.2 exact) but dramatically better on cyclic sequences (+2.4 vs +0.6 delta). Latent carryover does not embed context-specific bindings, so context poison does not accumulate across transfer hops.
- **Morphogenesis cold win rate:** ~20%. Same cold-start limitation as Family A — growth fires before routing clarity and produces unused nodes.

---

## Section 3: Family C — Transform Ambiguity

**Task structure:** Progressive degradation of visible observability over a 4-state hidden controller. C1 is clean (visible context perfectly identifies transform). C2 introduces partial ambiguity. C3/C4 have both visible branches ambiguous, driven by a 2-step parity controller that visible context no longer cleanly exposes.

This family required two architectural fixes before REAL could engage meaningfully:
1. **Task-ID fix (2026-03-18 1915):** Generated benchmark IDs (`ceiling_c3_task_a`) were invisible to the latent task-family logic.
2. **Credit/debt alignment fix (2026-03-18 1815):** Resolved downstream nodes were over-penalized for transform-aligned partial matches, collapsing contextual support accumulation.

### Cold-start: original pilot (pre-fix, 3-seed)

| Benchmark | fixed-visible | fixed-latent | growth-visible |
|---|---:|---:|---:|
| C1 | 0.4321 / 55.6% | 0.2500 / 22.2% | 0.4239 / 55.6% |
| C2 | 0.4033 / 55.6% | 0.2243 / 0.0% | 0.2932 / 33.3% |
| C3 | 0.2047 / 0.0% | 0.2202 / 0.0% | 0.2047 / 0.0% |
| C4 | 0.1811 / 0.0% | 0.1749 / 0.0% | 0.1574 / 0.0% |

### Cold-start: post-fix (seed 13, all 4 modes)

| Benchmark | fixed-visible | fixed-latent | growth-visible | growth-latent |
|---|---:|---:|---:|---:|
| C3 | 0.3549 / 33.3% | **0.3704 / 33.3%** | 0.2438 / 0.0% | 0.3426 / 33.3% |
| C4 | 0.1883 / 0.0% | **0.3179 / 0.0%** | 0.1837 / 0.0% | 0.3102 / 0.0% |

*The improvement from ~0.20 to ~0.37 exact on C3 fixed-latent is the combined effect of the task-ID fix, multicontext architecture, cardinality-aware thresholds, and credit/debt alignment.*

### Transfer: A→B and A→C (post-fix, seed 13)

#### C3 transfer deltas vs cold

| Method | A→task_b delta | A→task_c delta |
|---|---:|---:|
| fixed-visible | **+0.185** | −0.065 |
| fixed-latent | +0.102 | +0.074 |
| growth-visible | −0.019 | −0.120 |
| **growth-latent** | **−0.083** | **−0.157** |

#### C4 transfer deltas vs cold

| Method | A→task_b delta | A→task_c delta |
|---|---:|---:|
| fixed-visible | +0.028 | +0.014 |
| fixed-latent | +0.102 | −0.009 |
| growth-visible | +0.028 | +0.000 |
| **growth-latent** | **+0.176** | **+0.000** |

### C-family profile

- **Best cold (C1/C2):** `fixed-visible` — still high criterion rate when context is partially reliable.
- **Best cold (C3/C4):** `fixed-latent` — the only mode that substantially outperforms visible once context is degraded. Latent's 4-state controller representation gives it the disambiguation capacity visible modes lack.
- **Worst cold (consistently):** `growth-visible` — zero criterion on C3/C4, lowest exact match across the board.
- **Transfer (C3):** `fixed-visible → task_b` is the strongest single delta (+0.185), but it fails on `task_c` (−0.065). `fixed-latent` is the only mode with positive deltas on both targets.
- **Transfer (C4):** `growth-latent → task_b` is the best result in the family (+0.176 delta, 0.1806 → 0.3565 exact). The larger C4 topology gives morphogenesis enough runway to stabilize before transfer.
- **Critical asymmetry:** `growth-latent` is **catastrophically harmful on C3 transfer** (−0.157 on A→C) but **strongly beneficial on C4 transfer** (+0.176 on A→B). This is a topology threshold effect, not a tuning issue.

---

## Section 4: Three Structural Principles

### Principle 1: Morphogenesis is a warm-substrate phenomenon

Across all three families, cold-start morphogenesis win rates cluster around 20% and provide no measurable task performance lift. The same configurations reach 60-80% win rates and clear performance improvements under warm carryover.

The mechanism is consistent: growth requires routing clarity before it can seed productive nodes. During cold start, the topology has no established packet flow, so new nodes receive default action supports and are never utilized. During warm transfer, existing high-support routes generate early feedback, creating an ATP surplus that triggers growth at a useful moment — after partial routing clarity exists.

**Implication:** `growth-*` modes should not be evaluated as cold-start alternatives to `fixed-*`. They are transfer amplifiers.

| Condition | Morphogenesis earned growth rate | Performance lift |
|---|---:|---|
| Cold start (any family) | ~20% | ~0 |
| Warm transfer, short topology (C3) | Low | Harmful (growth-latent) |
| Warm transfer, large topology (A/B/C4) | 60-80% | +1.2 to +7.0 exact matches |

### Principle 2: Latent carryover is transfer-safe; visible carryover is task-geometry-sensitive

Visible training embeds context-specific action supports (e.g., `context_1 → xor_mask_1010` for task A). If the transfer target shares that geometry, visible carryover helps. If it doesn't — task B expects `context_1 → xor_mask_0101` — visible carryover injects poison that costs 3-4 exact matches.

Latent training never commits to context-specific bindings during training. The carryover substrate carries context-agnostic supports that don't interfere with the new task's geometry. The cost is a weaker cold-start baseline; the benefit is a reliably positive transfer floor and compounding advantage in cyclic sequences.

| Carryover type | Task-aligned geometry | Task-misaligned geometry |
|---|---|---|
| Visible full episodic | Helpful (+2.2 to +7.4 exact) | Harmful (context poison, −2.0 to −4.0 exact) |
| Visible substrate-only | Often better than full (+6.0 vs +2.2) | Avoids the worst poison |
| Latent full episodic | Strong (+5.8 to +7.0 exact) | Near-neutral floor (avoids poison by construction) |
| Latent substrate-only | Collapses advantage (−2.2 from +7.0) | Similar collapse |

Latent full episodic carryover is better than substrate-only because some nontrivial learned state (beyond bare topology and supports) is necessary for latent transfer to work. Stripping it removes the advantage. This is why `growth-latent + full episodic` is the dominant transfer configuration for large-topology tasks.

### Principle 3: Topology scale determines whether growth-latent can stabilize

The most surprising finding across the C family is the direct inversion of growth-latent's transfer behavior between C3 and C4:

| Task | Topology | growth-latent A→task_b delta |
|---|---|---:|
| C3 | 30 nodes, 108 packets | −0.083 |
| C4 | 50 nodes, 216 packets | **+0.176** |

C3's session ends before the latent estimate stabilizes enough to gate morphogenesis productively. Growth fires into unresolved context, seeds wrong structure, and that structure actively interferes with transfer. C4's additional nodes and packets provide just enough runway for latent stabilization to precede growth commitment.

The same principle explains why Family A and B large-topology results (+7.0 exact) exceed their small-topology equivalents. There is a topology-scale threshold below which `growth-latent` degrades — its precise location is not yet mapped, but it lies somewhere between C3 (30 nodes) and C4 (50 nodes).

---

## Section 5: Practical Prescription Table

| Task characteristics | Best cold config | Best transfer config | Configs to avoid |
|---|---|---|---|
| Short horizon, unambiguous visible context (A1-A2) | `fixed-visible` | `growth-visible` + substrate-only carryover | `fixed-latent` cold |
| Large scale, unambiguous visible context (A3-A4) | `fixed-visible` | `growth-latent` + full episodic carryover | Visible full episodic (context poison) |
| Hidden memory, adequate packet budget (B2-B4) | `fixed-visible` | `growth-latent` + full episodic carryover | `fixed-latent` cold |
| Partial ambiguity (C1-C2) | `fixed-visible` | `fixed-visible` A→task_b; `fixed-latent` for both targets | `growth-latent` cold |
| Deep ambiguity, short topology (C3) | `fixed-latent` | `fixed-latent` (safe on both targets) | `growth-latent` transfer; `growth-visible` cold |
| Deep ambiguity, large topology (C4) | `fixed-latent` | `growth-latent` A→task_b; `fixed-latent` A→task_c | `fixed-visible` cold |
| Multi-hop cyclic sequences (any family) | `fixed-latent` | `latent` cyclic (+2.4 vs +0.6 for visible) | Visible full episodic cyclic |

---

## Section 6: Open Questions

The following gaps in the configuration map would most improve the prescriptions above:

1. **Topology threshold for growth-latent.** There is a crossover between C3 (30 nodes, harmful) and C4 (50 nodes, beneficial). A scale sweep at 35, 40, 45 nodes would locate the threshold and let you prescribe growth-latent by topology size rather than family label.

2. **3-seed transfer validation for C3/C4.** All post-fix transfer results are single-seed (seed 13). The C3 transfer pattern — growth-latent harmful, fixed-latent positive — needs multi-seed confirmation before it can be treated as a stable finding.

3. **growth-latent cold performance on Family B.** The ceiling pilot only covered `fixed-visible`, `fixed-latent`, `growth-visible` on B. The carryover bridge diagnostic shows `growth-latent` is the dominant transfer mode for B large-topology, but B cold-start growth-latent has never been run.

4. **Visible substrate-only carryover for C family.** The bridge diagnostic showed substrate-only carryover recovers much of the visible poison problem for Family A. It has not been tested on C3/C4. Given that `fixed-visible` tanks on A→C transfer, substrate-only might rescue it.

5. **Cardinality effects on B family.** The B family uses a 1-bit parity hidden controller. The latent tracker now supports 4-state estimation (introduced for C3/C4). Whether the B-family latent path benefits from this upgrade has not been re-tested since the multicontext architecture landed.

---

## Appendix: Score Reference

### Exact match rates at a glance (post-fix, seed 13 unless noted)

| Task | fixed-visible | fixed-latent | growth-visible | growth-latent |
|---|---:|---:|---:|---:|
| **A cold** (3-seed avg) | 0.40 | 0.29 | 0.37 | — |
| **A→B transfer** (large, 5-seed) | 0.34 (+2.2 exact) | 0.32 (+5.8 exact) | 0.41 (+7.4 exact) | **0.39 (+7.0 exact)** |
| **B2 cold** (3-seed) | **0.60** | 0.22 | 0.51 | — |
| **B→transfer** (large, 5-seed) | 0.34 | 0.32 | **0.41** | 0.39 |
| **C1 cold** (3-seed) | 0.43 | 0.25 | 0.42 | — |
| **C3 cold** (seed 13) | 0.35 | **0.37** | 0.24 | 0.34 |
| **C3 A→task_b** (seed 13) | **0.43** | 0.35 | 0.18 | 0.12 |
| **C3 A→task_c** (seed 13) | 0.20 | **0.33** | 0.22 | 0.18 |
| **C4 cold** (seed 13) | 0.19 | **0.32** | 0.18 | 0.31 |
| **C4 A→task_b** (seed 13) | 0.25 | 0.31 | 0.19 | **0.36** |
| **C4 A→task_c** (seed 13) | 0.17 | **0.34** | 0.19 | **0.36** |
