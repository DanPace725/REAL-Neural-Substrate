# 2026-03-17 1005 - Cyclic Transfer Exploration

**Type:** H_e (Experiment trace)
**Harness:** `compare_cyclic_transfer.py`
**Output artifacts:**

- `docs/experiment_outputs/20260317_1002_cyclic_transfer.json`
- `docs/experiment_outputs/20260317_1004_cyclic_transfer_latent.json`

**Seeds:** 13, 23, 37, 51, 79
**Task sequence:** `A -> B -> C -> A`

---

## 1. Visible cyclic transfer

Aggregate result from `20260317_1002_cyclic_transfer.json`:

| Metric | Cold A | Final A after cycle | Delta |
|---|---:|---:|---:|
| Exact matches | 10.0 | 10.6 | +0.6 |
| Bit accuracy | 0.7389 | 0.7111 | -0.0278 |

Per-seed exact deltas:

| Seed | Cold A | Final A | Delta |
|---|---:|---:|---:|
| 13 | 8 | 10 | +2 |
| 23 | 9 | 5 | -4 |
| 37 | 11 | 15 | +4 |
| 51 | 14 | 7 | -7 |
| 79 | 8 | 16 | +8 |

**Reading:** visible cyclic transfer is viable but unstable. Exact-match recovery is slightly positive on average, but bit accuracy drops and the per-seed spread is wide. The cycle can compound useful structure, but it can also reintroduce enough context-specific poison to hurt the return to Task A.

---

## 2. Latent cyclic transfer

Aggregate result from `20260317_1004_cyclic_transfer_latent.json`:

| Metric | Cold A | Final A after cycle | Delta |
|---|---:|---:|---:|
| Exact matches | 3.0 | 5.4 | +2.4 |
| Bit accuracy | 0.4611 | 0.5111 | +0.0500 |

Per-seed exact deltas:

| Seed | Cold A | Final A | Delta |
|---|---:|---:|---:|
| 13 | 4 | 9 | +5 |
| 23 | 2 | 10 | +8 |
| 37 | 3 | 1 | -2 |
| 51 | 2 | 6 | +4 |
| 79 | 4 | 1 | -3 |

**Reading:** latent cyclic transfer is more promising than visible cyclic transfer in this first run. It starts from a weaker cold `A` baseline but shows a larger average gain on both exact matches and bit accuracy after the full cycle. This is consistent with the March 17 latent-transfer story: latent carryover appears less vulnerable to context-specific poisoning over longer chains.

---

## 3. Interim conclusion

- Cyclic return to `A` is not only structurally runnable; it is experimentally nontrivial.
- Visible cyclic transfer is mixed and high-variance.
- Latent cyclic transfer produced the stronger average recovery signal in this slice:
  - `+2.4` exact vs `+0.6`
  - `+0.0500` bit accuracy vs `-0.0278`

**Next question:** run a direct visible-vs-latent cyclic comparison trace that also breaks the terminal `A` performance down by context and transform-family failure modes. The current aggregate is enough to justify that follow-up.
