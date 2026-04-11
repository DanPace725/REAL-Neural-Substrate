# 2026-03-19 1609 - Phase 8 Occupancy Real v2 Trace

**Timestamp**: 2026-03-19 2310 UTC  
**Model**: Antigravity (Google Deepmind)  
**Session type**: H_e (Episodic Trace)

## Intent

Redesign the REAL occupancy evaluation to address three structural mismatches
identified by analysis:
1. Feedback disabled during eval → ATP starvation / packet delivery collapse
2. No carryover test → REAL's core value prop never tested
3. No context bit → latent context mechanism never activates

## Hypotheses tested

1. Enabling feedback during eval prevents the packet delivery collapse.
   - **Accepted.** `eval_mean_dropped` fell from 17.35 (v1) to 4.2 (v2_live).
     Eval accuracy rose from 77% to 89.2%. Eval F1 rose from 0.032 to 0.748.

2. Fresh-system substrate carryover preserves trained routing behavior.
   - **Accepted.** `v2_carryover` (fresh eval system loaded from training substrate)
     reached 90.0% eval accuracy — slightly better than v2_live (89.2%), confirming
     the substrate accumulated during training transfers productively into a cold system.

3. CO2-derived context bit activates context-indexed substrate supports and
   further improves packet delivery.
   - **Strongly accepted.** `v2_live_ctx_co2_high` dropped only 0.724 packets/episode
     (vs 4.2 without context). Eval accuracy 90.0%, F1 0.766. The context bit let
     nodes index their action supports by the class-correlated CO2 signal, sharply
     reducing routing uncertainty.

## Results

| Condition | Train Acc | Eval Acc | Eval F1 | Eval Dropped | Eval Fdbk Events |
|---|---:|---:|---:|---:|---:|
| v1_baseline (original) | ~0.925 | 0.772 | 0.032 | 17.35 | 0.0 |
| v2_live | 0.874 | 0.892 | 0.748 | 4.21 | 13.92 |
| v2_carryover | 0.874 | 0.900 | 0.757 | 4.23 | 14.18 |
| v2_live_ctx_co2_high | 0.890 | 0.900 | 0.766 | 0.72 | 18.05 |
| v2_carry_ctx_co2_high | 0.890 | 0.896 | 0.764 | 0.76 | 18.10 |

*v1_baseline from occupancy_bridge_seed13_20260319.json for reference.*

## Key findings

- **ATP starvation was the dominant failure mode in v1.** Keeping feedback alive in eval
  solved most of the eval collapse without any architectural change.
- **Substrate carryover transfers cleanly.** The `fresh_eval` system reaches equal or
  better accuracy than the continuous system, confirming the substrate state is
  the carrier of learning, not runtime ATP or episodic memory alone.
- **Context almost eliminates packet drops.** CO2 context reduced per-episode dropped
  packets from ~4.2 to ~0.72 — a 5.8x improvement. This is the latent context
  mechanism doing exactly what was designed.
- **Train accuracy converges near 90% for all v2 conditions.** The substrate is
  learning routing effectively; the eval collapse was purely an evaluation design flaw.

## Frictions

- Full run was initially too slow (~10+ min) because conditions ran sequentially over
  the full 1,684-episode dataset. Fixed with `ProcessPoolExecutor` parallelism and
  500/250 default episode caps. Runtime: 723.8s for 4 conditions.
- `FeedbackPulse` does not natively carry `context_bit`, so context is passed via
  packet metadata and absorbed during the feedback drain phase.

## Decisions promoted to maintained substrate

- Eval feedback should never be zero for REAL experiments. Default should be
  `eval_feedback_fraction=1.0` (same as training).
- Carryover eval mode (fresh_eval) should be a standard condition in any REAL
  comparison that claims to measure "what REAL learned".
- CO2-derived context is a practical and fair context proxy for this dataset —
  it does not leak the label and produces a large routing improvement.
- Run episode caps + parallel execution are necessary for interactive experiments
  to complete in reasonable time (~5-10 min target).
