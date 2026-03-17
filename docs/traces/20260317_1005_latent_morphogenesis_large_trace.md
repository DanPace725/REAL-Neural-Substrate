# 2026-03-17 1005 - Latent Large-Topology Morphogenesis

**Type:** H_e (Experiment trace)
**Harness:** `compare_morphogenesis_large.py`
**Output artifact:** `docs/experiment_outputs/20260317_1002_latent_morphogenesis_large.json`

**Seeds:** 13, 23, 37, 51, 79
**Mode:** latent context, source-sequence enabled, latent transfer split enabled
**Topology:** `cvt1_large (10 nodes, 5-hop paths)`

---

## 1. Transfer result

Latent `A -> B` transfer with morphogenesis on the large topology produced:

| Metric | Fixed | Growth | Delta |
|---|---:|---:|---:|
| Exact matches | 9.6 | 16.6 | +7.0 |
| Bit accuracy | 0.5139 | 0.6611 | +0.1472 |
| Route cost | 0.03769 | 0.03475 | -0.00293 |
| Earned growth rate | — | 1.0 | — |
| Growth win rate | — | 0.6 | — |

Additional growth characteristics:

- avg bud successes: `5.0`
- avg dynamic node count: `3.4`
- avg new node utilization: `0.7167`
- avg time to first feedback: `7.3333`

**Reading:** latent large-topology transfer plus morphogenesis is a strong positive result. Growth is always earned, improves routing efficiency, and adds a large task-performance gain.

---

## 2. Per-scenario cold-start effects

| Scenario | Delta exact | Delta bit acc | Earned growth | Win rate |
|---|---:|---:|---:|---:|
| `cvt1_task_a_large` | +0.6 | +0.0361 | 1.0 | 0.8 |
| `cvt1_task_b_large` | +2.6 | +0.0972 | 1.0 | 0.8 |
| `cvt1_task_c_large` | -0.2 | -0.0222 | 0.4 | 0.2 |

**Reading:** the latent path appears to soften the disruption cost that previously dominated the easier large-topology scenarios. Task A is now slightly positive rather than negative, Task B still benefits clearly, and Task C remains the main weak spot but only mildly regresses.

---

## 3. Comparison to the earlier visible large-topology trace

Relative to the March 17 visible large-topology morphogenesis trace already in the repo, this latent slice suggests a different tradeoff profile:

- transfer gain is much larger in this latent run (`+7.0` exact here versus `+2.2` in the earlier visible trace)
- Task A looks better under latent growth (`+0.6` here versus a visible regression in the earlier trace)
- Task B still benefits, though less dramatically than the earlier visible cold-start `B` gain
- Task C remains the fragile case in both modes

This is an inference from comparing today's latent run against the existing March 17 visible trace, not from a same-command paired rerun today. Still, the pattern is strong enough to justify a direct paired latent-vs-visible large-topology benchmark next.

---

## 4. Interim conclusion

- Large-topology latent morphogenesis is not just supported by the wrapper now; it produces a meaningful result.
- The strongest current signal is the transfer condition, where latent growth appears to be a major sweet spot.
- The scenario pattern now looks more nuanced than the earlier "only hard tasks benefit" reading. Under latent training, `Task A` also gains slightly.

**Next question:** run a paired visible-vs-latent large-topology morphogenesis comparison in one harness so the tradeoff can be attributed directly rather than through cross-trace comparison.
