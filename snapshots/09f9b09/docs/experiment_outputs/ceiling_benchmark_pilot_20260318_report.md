# Ceiling Benchmark Pilot — 2026-03-18

**Harness:** `ceiling_benchmark_suite` | **Timestamp:** 2026-03-18T18:59–19:00Z  
**Seeds:** {13, 23, 37} | **Task variants per benchmark:** task_a, task_b, task_c

---

## What this benchmark is for

The goal is to find where REAL's local allostatic learning breaks down — a **ceiling** where performance collapses relative to neural baselines. To measure this honestly, the benchmark surface is frozen before any tuning, so the first collapse is observed rather than tuned away.

Three families probe distinct architectural pressure points:

- **Family A** (A1–A4) — topology scaling from 6→10→30→50 nodes, 18→36→108→216 examples
- **Family B** (B1–B4) — hidden-memory depth: context depends on parity over 1, 2, 4, then 8 prior packets
- **Family C** (C1–C4) — transform ambiguity: 2→3→4 transforms, then 4 transforms with increased latent ambiguity on a 50-node topology

Nine methods compete: three REAL substrates (`fixed-visible`, `fixed-latent`, `growth-visible`) and six neural baselines (`mlp-explicit`, `mlp-latent`, `elman`, `gru`, `lstm`, `causal-transformer`).

Collapse is defined as REAL failing fixed accuracy thresholds *while a NN clearly outperforms it* — a conservative bar that avoids declaring ceiling from noise.

---

## Main finding: no ceiling found yet

Across all 12 benchmark bands, **no collapse has been observed**. REAL consistently leads neural baselines on both exact-match rates and — most starkly — on criterion-reaching.

---

## Criterion-reaching: the clearest signal

"Criterion" means the system solved the task to the required rolling accuracy threshold — not just average closeness, but actual consistent correctness. This is the most relevant metric for REAL's architectural claim.

| Benchmark | REAL criterion rate | NN criterion rate |
|---|---|---|
| A1 | 11% | 0% |
| A2 | 15% | 0% |
| A3 | 44% | 6% |
| A4 | **63%** | 0% |
| B1 | 44% | 6% |
| B2 | **56%** | 11% |
| B3 | **52%** | 0% |
| B4 | 48% | 2% |
| C1 | 44% | 6% |
| C2 | 30% | 0% |
| C3 | **0%** | 0% |
| C4 | **0%** | 0% |

Rates are averaged over all methods and seeds within each model family (27 REAL runs, 54 NN runs per benchmark).

Neural baselines essentially never reach criterion. REAL does so reliably across A and B families, and into C1–C2. The first genuine failure appears at **C3–C4** — where all REAL methods drop to zero criterion rate. No NN reaches criterion at C3–C4 either.

---

## Family A — scaling does not hurt REAL

As topology grows from 6 to 50 nodes and examples grow from 18 to 216, REAL's criterion rate *increases* (11% → 63%). Exact-match rate climbs from ~0.35 to ~0.45. The `fixed-visible` method leads, with `growth-visible` competitive at A2–A3.

This is the opposite of what scaling pressure would cause if REAL were hitting capacity limits. The larger routing space gives the substrate more positions to specialize into and more examples to consolidate over. **Scale, so far, helps REAL.**

Neural baselines (best: `causal-transformer`) also improve modestly in bit accuracy but never reach criterion on A2–A4, and their exact-match rates (~0.09–0.21) remain well below REAL's (~0.35–0.45).

---

## Family B — hidden memory is handled

B1–B4 hold topology fixed (30-node, 108-packet) and progressively deepen the parity look-back requirement. REAL's criterion rate holds steady at 44–56% across all four bands. B2 (2-step parity) is REAL's highest-performing single point: `fixed-visible` reaches 100% criterion rate at B2 while `causal-transformer` (the best NN) reaches only 11%.

The `fixed-latent` method (no external context labels) consistently underperforms `fixed-visible` on B-family, which is expected — hidden-memory tasks benefit from visible context because the parity signal provides cleaner state separation.

NN criterion rates are low throughout B-family (0–11%) and the exact-match gap is large: REAL hits ~0.50 EM rates while the best NNs reach ~0.18–0.32. **The B-family data is the clearest demonstration that REAL's local memory outperforms neural baselines on sequentially dependent tasks.**

---

## Family C — first signs of difficulty

C1 mirrors the A3/B baseline topology and REAL performs equivalently (~44% criterion, ~0.43 EM). C2 starts showing degradation (criterion drops to 30%). At C3 and C4 — four-transform families with a 4-state controller and increased latent ambiguity — **all REAL methods drop to zero criterion rate**.

Bit accuracy at C3–C4 (~0.49–0.53) remains slightly above the expected chance level but is not meaningfully above it for exact-sequence correctness. Notably, NNs also reach zero criterion at C3–C4, and the bit-accuracy gap between REAL and NNs narrows considerably. `fixed-latent` edges ahead of `fixed-visible` at C3–C4, which is a notable reversal: when context labels don't cleanly separate the latent transform state (high ambiguity), inferring context locally without labels may actually be less misleading than committing to an incorrect visible label.

**C3–C4 is the most likely location for the eventual ceiling observation**, though the collapse definition requires NNs to clearly outperform REAL — which they don't yet.

---

## REAL method summary across families

| Method | Strength | Weakness |
|---|---|---|
| `fixed-visible` | Dominant across A and B; leads on C1–C2 | Drops sharply at C3–C4 ambiguity |
| `fixed-latent` | Most resilient at C3–C4 | Lower EM and criterion on B-family |
| `growth-visible` | Competitive with fixed-visible on A2–B family | No distinct advantage on high-ambiguity C bands |

---

## Summary

REAL holds a clear and consistent advantage over all neural baselines across topology scaling (A-family) and hidden-memory depth (B-family). The advantage is largest on exact task completion rather than bit-level accuracy — REAL solves tasks outright far more often than NNs do.

The first hint of where a ceiling may eventually appear is the C-family transform-ambiguity axis: at C3–C4, REAL's criterion rate drops to zero (though NNs also fail, so no collapse has been declared). Whether further tuning, morphogenesis, or latent-context mechanisms can recover performance in this regime is what the ongoing runs are designed to answer.

---

*Data sources: `ceiling_benchmark_pilot_20260318.json`, `ceiling_benchmark_pilot_20260318_frontier.json`, and per-family slices and report directories in this folder.*
