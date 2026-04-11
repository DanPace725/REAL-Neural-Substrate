# C Family Diagnostic — 2026-03-18

**Runs:** `c_family_real_diagnostic_20260318_seed13.json` (C3+C4, seed 13) and `c_family_real_diagnostic_c3_3seed_20260318.json` (C3, seeds 13/23/37)  
**Harness:** `scripts/diagnose_c_family_real.py` — REAL-only, four modes, with warm transfer

---

## Why this diagnostic exists

The March 18 ceiling benchmark pilot found that REAL's criterion rate drops to zero at C3 and C4, but those pilot runs only covered three REAL modes (`fixed-visible`, `fixed-latent`, `growth-visible`) and no transfer. The ceiling benchmark cold-start regime also doesn't distinguish between the modes that can actually respond to the specific challenge C3/C4 present.

This diagnostic adds the fourth REAL mode — `growth-latent` — and includes warm transfer from `task_a` into `task_b` and `task_c`, to see whether any combination of mode or carryover can recover performance on the hard ambiguity points.

---

## What makes C3 and C4 hard

The C family ladder progressively degrades the informativeness of the visible context bit:

- **C1–C2**: visible context perfectly or mostly determines the transform
- **C3**: both visible branches are ambiguous — each context bit maps to two different transforms at unequal rates (~66%/34%)
- **C4**: visible context is intentionally scrambled — the most frequent transform per branch is only 37–40%, making the visible label nearly a distractor

This is not just "harder Task C." C3/C4 are weak-observation latent-inference problems. The system cannot cleanly learn a stable context-to-transform mapping because the observable signal genuinely does not determine it.

---

## C3 Cold Start (3 seeds: 13/23/37)

| Method | EM rate | Bit acc | Criterion |
|---|---|---|---|
| `fixed-latent` | 0.220 | 0.533 | 0% |
| `growth-latent` | 0.221 | 0.524 | 0% |
| `fixed-visible` | 0.205 | 0.490 | 0% |
| `growth-visible` | 0.205 | 0.484 | 0% |

**Latent modes outperform visible modes.** This is the key reversal from C1–C2 behavior, where `fixed-visible` led. With both visible context branches being ambiguous at C3, committing to the visible label actually hurts — it binds action supports to an unreliable signal. Latent modes infer context from behavioral outcomes, which is slower but more accurate in a noisy-label regime.

Criterion rate is zero across all modes and seeds. All bit accuracies are near 0.50 (chance for full-sequence exact matching), confirming that no mode has a reliable handle on the task. Performance is above chance at the bit level for latent modes (~0.52–0.53), but not enough to drive correct transform selection consistently.

**Morphogenesis does not help cold-start at C3.** `growth-latent` slightly edges `fixed-latent` on EM rate (0.221 vs 0.220) but loses on bit accuracy. `growth-visible` is slightly below `fixed-visible`. This matches the pattern established on the previous morphogenesis analysis: morphogenesis helps routing-headroom problems, not observation-identifiability problems. When the bottleneck is that the visible signal is misleading, adding nodes doesn't fix the signal.

---

## C3 Transfer from task_a (3 seeds)

| Method | Target | Warm EM | d\_EM | Warm bit | d\_bit |
|---|---|---|---|---|---|
| `fixed-latent` | task\_b | 0.265 | +0.080 | 0.566 | +0.065 |
| `growth-visible` | task\_b | 0.293 | +0.071 | 0.535 | +0.062 |
| `growth-latent` | task\_b | 0.108 | −0.117 | 0.432 | −0.079 |
| `fixed-visible` | task\_b | 0.213 | −0.052 | 0.500 | −0.003 |
| `fixed-visible` | task\_c | 0.191 | +0.006 | 0.511 | +0.023 |
| `fixed-latent` | task\_c | 0.176 | −0.077 | 0.529 | −0.031 |
| `growth-visible` | task\_c | 0.194 | −0.006 | 0.515 | +0.018 |
| `growth-latent` | task\_c | 0.133 | −0.151 | 0.446 | −0.133 |

**Transfer benefit is split by target.** `task_b` is a cleaner carryover target than `task_c`:

- `fixed-latent` into `task_b`: +8.0 EM points — the best single warm result at C3. Latent carryover from `task_a` seeds context-specific action supports that happen to align with `task_b`'s transform structure.
- `growth-visible` into `task_b`: +7.1 EM points — second best. The combination of routing consolidation from `task_a` plus morphogenesis creates useful structure for `task_b`'s topology.
- `task_c` shows minimal benefit or regression for most modes. The generated transform relationships in the late C ladder don't align with the original `task_a → task_c` transfer geometry the way the named scenario families did.

**`growth-latent` is the worst transfer mode at C3** — clearly and consistently. It regresses sharply on both targets. The interpretation: morphogenesis fires before the latent context estimate has stabilized under ambiguous observations. New nodes bud into an under-determined routing space, reinforcing incorrect structure early and propagating that error forward. The combination of slow context commitment (latent) and early structural growth is actively harmful when the visible signal is already misleading.

---

## C4 Cold Start (seed 13 exploratory)

| Method | EM rate | Bit acc | Criterion |
|---|---|---|---|
| `fixed-visible` | 0.173 | 0.512 | 0% |
| `growth-latent` | 0.156 | 0.522 | 0% |
| `growth-visible` | 0.164 | 0.495 | 0% |
| `fixed-latent` | 0.133 | 0.495 | 0% |

C4 is worse than C3 across all modes, as expected. Bit accuracies hover at 0.49–0.52 — effectively chance. The mode ordering reverses somewhat from C3: `fixed-visible` leads on EM rate, which is surprising given that the visible context is maximally scrambled at C4. One interpretation: with almost no usable signal, fixed-visible's faster commitment produces random but consistent behavior that occasionally hits correct transforms more often than the slower latent inference path — essentially noise-driven rather than signal-driven accuracy.

*Note: C4 data is a single seed and should be treated as exploratory.*

---

## C4 Transfer from task_a (seed 13 exploratory)

| Method | Target | Warm EM | d\_EM | Warm bit | d\_bit |
|---|---|---|---|---|---|
| `growth-latent` | task\_c | 0.218 | +0.093 | 0.488 | −0.014 |
| `fixed-latent` | task\_b | 0.185 | +0.070 | 0.512 | +0.026 |
| `growth-latent` | task\_b | 0.194 | +0.060 | 0.516 | +0.025 |
| `fixed-visible` | task\_c | 0.190 | +0.032 | 0.493 | −0.012 |
| `fixed-latent` | task\_c | 0.157 | +0.042 | 0.442 | −0.056 |
| `fixed-visible` | task\_b | 0.162 | +0.019 | 0.521 | +0.028 |
| `growth-visible` | task\_b | 0.139 | −0.032 | 0.481 | −0.019 |
| `growth-visible` | task\_c | 0.143 | −0.014 | 0.465 | −0.023 |

Transfer helps more at C4 than cold-start would predict for several modes — particularly `growth-latent` into `task_c` (+9.3 EM points, the largest single warm gain in the entire C family diagnostic). However, the bit-accuracy deltas are mixed or negative for these same cases, which means the exact-match gains are likely driven by occasional lucky alignment with the correct full-sequence output rather than stable improved transform selection. `growth-visible` remains the weakest transfer mode.

This is a single-seed result and the instability in bit accuracy means it should not be treated as evidence that `growth-latent` is the right path for C4. Further seeds are needed.

---

## Summary

| Finding | Implication |
|---|---|
| C3/C4 cold-start: zero criterion, near-chance bit accuracy | The hard ambiguity ladder correctly identifies a regime where current REAL capability cannot reliably solve the task |
| Latent modes > visible modes at C3 cold-start | Visible context commitment is harmful when the observable signal is genuinely ambiguous |
| `fixed-latent` into `task_b` at C3: +8.0 EM | Transfer from a simpler task partially offsets the ambiguity — specific substrate priors help even when cold-start fails |
| `growth-latent` worst transfer mode at C3; regresses sharply | Morphogenesis + latent is actively harmful when slow context stabilization and early structural growth interfere |
| C4 transfer results noisy but sometimes positive | Task-a substrate carryover can occasionally help, but results are unstable at single seed |

The C family diagnostic confirms that the ceiling the pilot benchmarks suggested is real: REAL's current architecture does not have the mechanism to handle tasks where the observable context signal is structurally uninformative about the transform. The problem is not scale, not routing headroom, and not hidden memory depth — it is specifically **observation identifiability**. The most promising direction based on current data is `fixed-latent` with transfer from a related task, but this only partially recovers performance and doesn't reach criterion.

---

*Data files: `c_family_real_diagnostic_20260318_seed13.json`, `c_family_real_diagnostic_c3_3seed_20260318.json`*  
*Traces: `docs/traces/2026-03-18 1535 - C Family Diagnostic.md`, `docs/traces/2026-03-18 1725 - C Family Full Capability Run.md`*
