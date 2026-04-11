# 2026-03-17 1046 - Large-Topology Mode-Switched Morphogenesis

**Type:** H_e (Experiment trace)
**Harness:** `compare_morphogenesis_large_mode_switched.py`
**Output artifact:** `docs/experiment_outputs/20260317_1044_morphogenesis_large_mode_switched.json`

**Seeds:** 13, 23, 37, 51, 79
**Policies compared on `A large -> B large` transfer:**

- `all_visible`
- `all_latent`
- `visible_train_latent_transfer`

---

## 1. Headline result

The simple mode-switch curriculum tested here did **not** outperform the single-mode baselines.

| Policy | Transfer exact delta | Transfer bit-acc delta | Growth win rate |
|---|---:|---:|---:|
| all visible | +2.2 | +0.0417 | 0.8 |
| all latent | +7.0 | +0.1472 | 0.6 |
| visible train -> latent transfer | -2.0 | -0.0778 | 0.4 |

The switched policy underperformed both:

- vs visible: `-4.2` exact delta, `-0.1195` bit-acc delta
- vs latent: `-9.0` exact delta, `-0.2250` bit-acc delta

---

## 2. Interpretation

The naive handoff from visible training to latent transfer appears to break continuity rather than combine strengths.

The likely reason is architectural rather than accidental:

- visible training writes context-bound supports into the substrate
- latent transfer then evaluates and adapts without the same explicit context binding
- the resulting substrate may carry the liabilities of visible context-specific commitment without giving the latent phase enough continuity to exploit them cleanly

So the earlier hypothesis was directionally sensible but operationally wrong in this first form. The two modes are not plug-compatible just because they are individually strong in different settings.

---

## 3. What this means for next steps

This negative result narrows the search productively.

- Do **not** assume that phase-wise mode switching is beneficial by default.
- If a mixed policy is tried again, it likely needs an explicit bridge:
  - selective carryover
  - edge-only carryover
  - latent-specific warm-up or adaptation window
  - explicit stripping or remapping of visible context-bound action supports before latent transfer

The better immediate follow-up is a **bridge-policy** experiment, not another raw visible-to-latent handoff.
