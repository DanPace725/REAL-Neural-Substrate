# 2026-03-17 1021 - Paired Visible vs Latent Large-Topology Morphogenesis

**Type:** H_e (Experiment trace)
**Harness:** `compare_morphogenesis_large_paired.py`
**Output artifact:** `docs/experiment_outputs/20260317_1019_morphogenesis_large_paired.json`

**Seeds:** 13, 23, 37, 51, 79
**Topology:** `cvt1_large (10 nodes, 5-hop paths)`
**Modes compared:** visible vs latent context, both with source-sequence enabled and latent transfer split enabled on the latent side

---

## 1. Transfer is the clearest latent win

Direct paired comparison for the large-topology `A -> B` transfer condition:

| Metric | Visible growth delta | Latent growth delta | Latent minus visible |
|---|---:|---:|---:|
| Exact matches | +2.2 | +7.0 | +4.8 |
| Bit accuracy | +0.0417 | +0.1472 | +0.1055 |
| Growth win rate | 0.8 | 0.6 | -0.2 |

**Reading:** latent large-topology morphogenesis is much stronger than visible morphogenesis in the transfer condition on raw task gain, even though the visible path still wins slightly on win rate. The latent path appears to produce fewer but larger wins.

---

## 2. Scenario tradeoff profile

| Scenario | Visible delta exact | Latent delta exact | Latent minus visible |
|---|---:|---:|---:|
| `cvt1_task_a_large` | -1.6 | +0.6 | +2.2 |
| `cvt1_task_b_large` | +7.4 | +2.6 | -4.8 |
| `cvt1_task_c_large` | -1.0 | -0.2 | +0.8 |

Bit-accuracy comparison:

| Scenario | Visible delta bit acc | Latent delta bit acc | Latent minus visible |
|---|---:|---:|---:|
| `cvt1_task_a_large` | -0.0611 | +0.0361 | +0.0972 |
| `cvt1_task_b_large` | +0.1333 | +0.0972 | -0.0361 |
| `cvt1_task_c_large` | -0.0166 | -0.0222 | -0.0056 |

**Reading:** visible growth still dominates the hardest cold-start scenario (`Task B`), but latent growth is clearly better on `Task A` and modestly less harmful on `Task C`. The paired run sharpens the earlier inference: latent morphogenesis changes the tradeoff surface rather than uniformly dominating visible morphogenesis.

---

## 3. Best current interpretation

- **Visible growth** remains the better cold-start strategy when the goal is to maximize gains on the hardest single scenario (`Task B`).
- **Latent growth** appears to be the better transfer strategy on the large topology.
- **Latent growth** also reduces the disruption cost on easier scenarios, especially `Task A`.

This suggests a mode-dependent policy:

- prefer visible morphogenesis for hardest cold-start task acquisition
- prefer latent morphogenesis for transfer-heavy or multi-stage curricula

---

## 4. Next step

The next decision-relevant experiment is not another broad sweep. It is a targeted policy comparison:

1. visible growth during cold-start `B`
2. latent growth during `A -> B` transfer
3. compare whether a curriculum that switches mode by phase outperforms either single-mode policy

The new paired harness is enough to drive that next slice directly.
