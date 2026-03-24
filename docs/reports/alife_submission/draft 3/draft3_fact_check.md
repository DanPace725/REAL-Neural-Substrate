# `draft3.tex` Fact Check

_Audit target:_ [draft3.tex](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/reports/alife_submission/draft%203/draft3.tex)

_Audit basis:_ current repo code, current docs, current traces, and checked-in experiment outputs as of 2026-03-24.

## Scope

This is a factual audit of the paper draft, not a style review. The goal is to mark what is:

- supported by current code and result artifacts
- supported but overstated or simplified
- incorrect relative to the current repo state

The highest-priority checks were:

- the REAL process/loop description
- what `real_core` and `phase8` actually do
- whether interpretability claims are grounded in current tooling
- whether the CVT-1, morphogenesis, and occupancy result claims match stored outputs

## Overall Verdict

The paper is directionally strong, and much of the core architectural framing is consistent with the repo. The biggest factual issues are concentrated in the occupancy section and a few process-description details.

The most important corrections are:

1. The paper still describes an older REAL loop in one central section.
2. The occupancy benchmark currently used in-repo is the checked-in synthetic bridge dataset, not a bundled external real-world occupancy CSV.
3. The occupancy V3 result table mixes single-seed values with 3-seed sweep means.
4. The occupancy efficiency-ratio interpretation is currently too strong and, in the draft's present wording, misleading.
5. The occupancy MLP comparison currently mixes different split protocols and misstates some baseline counts and metrics.

## High-Priority Corrections

| Area | Status | Correction |
|---|---|---|
| REAL loop in Architecture section | Incorrect | The current loop is `observe -> recognize -> predict -> select -> execute -> score -> compare -> consolidate`, not `perceive, select, execute, evaluate, consolidate`. |
| Occupancy dataset framing | Incorrect | Current V3 runs use [`occupancy_synth_v1.csv`](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/occupancy_baseline/data/occupancy_synth_v1.csv), a deterministic synthetic benchmark, not a bundled real external occupancy dataset. |
| Occupancy "3-seed mean" table | Incorrect | The table uses 3-seed mean accuracy/delivery but single-seed F1 values from seed 13. |
| Efficiency-ratio interpretation | Incorrect / overstated | In current V3 code, `mean_efficiency_ratio = mean(warm_delivery / cold_delivery)`. The 3-seed sweep mean is `0.9915`, which indicates near parity and slightly lower warm delivery on average, not a strong portability proof by itself. |
| MLP comparison counts | Incorrect | The MLP baseline summary uses `1072` train examples and `268` test examples on the 80/20 rolling-window split, not "full 1,344-example training split." |
| REAL occupancy training counts | Incorrect | V3 best run used `926` training episodes/windows across `62` sessions, not `926 sessions`. |
| Occupancy protocol labels | Incorrect | The 3-seed sweep was run with `eval_mode = fresh_session_eval`, so labeling the warm row as "persistent" is wrong for that summary table. |
| Prediction-error wording | Needs clarification | Prediction error is computed after action execution and feeds later behavior through local state; it is not directly part of same-cycle pre-action selection context in `real_core`. |

## Section-by-Section Audit

## 1. Abstract and Introduction

### Supported

- REAL is correctly expanded as **Relationally Embedded Allostatic Learning**.
- The general architectural stance is correct: no global gradient path, local metabolic constraints, persistent substrate, carryover, and routing-oriented multi-agent learning.
- The interpretability framing is substantially supported by current repo materials:
  - [INTERPRETABILITY.md](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/reports/INTERPRETABILITY.md)
  - [real_core/types.py](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/real_core/types.py)
  - [phase8/selector.py](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/selector.py)

### Needs correction

- The occupancy sentence currently overstates what the checked-in results establish.
  - The draft says the substrate transfers to a fresh system at `99.15%` efficiency, confirming substrate is the true knowledge carrier.
  - Current V3 sweep output instead shows near parity on delivery under `fresh_session_eval`, with `mean_efficiency_ratio = 0.9915` in [v3_best_real_sweep_13_23_37.json](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/experiment_outputs/v3_best_real_sweep_13_23_37.json).
  - In current code this ratio is `warm_delivery / cold_delivery`, not a direct measure of "fresh substrate-loaded system vs continuous system" in the way the abstract implies.
  - Safer wording: the current occupancy V3 results show near-MLP task performance, while the carryover/isolation metric on occupancy remains close to parity rather than strongly separated.

- The claim that the occupancy benchmark is "real-world" is not accurate for the current repo artifacts.
  - Current V3 defaults point to [`occupancy_baseline/data/occupancy_synth_v1.csv`](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/occupancy_baseline/data/occupancy_synth_v1.csv).
  - The dataset is explicitly documented as synthetic in [occupancy_baseline/README.md](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/occupancy_baseline/README.md), [occupancy_baseline/data/README.md](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/occupancy_baseline/data/README.md), and [occupancy_baseline/generate_dataset.py](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/occupancy_baseline/generate_dataset.py).


## 2. Background

### Mostly supported

- The predictive-processing motivation is consistent with the current architecture after the March 18-19 changes.
- Recognition and prediction are first-class `real_core` concepts in:
  - [real_core/interfaces.py](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/real_core/interfaces.py)
  - [real_core/types.py](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/real_core/types.py)
  - [real_core/engine.py](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/real_core/engine.py)
- The anticipation/recognition/prediction shift is well documented in [2026-03-19 1151 - Session Synthesis Anticipation Self Selection and Carryover.md](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/traces/2026-03-19%201151%20-%20Session%20Synthesis%20Anticipation%20Self%20Selection%20and%20Carryover.md).

### Needs clarification

- The sentence "prediction error modulates the current selection context" is too strong as written.
  - In current `real_core`, same-cycle selection context contains recognition, predictions, prior coherence, budget, and action costs.
  - Prediction error is computed later, after execution, in [real_core/engine.py](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/real_core/engine.py).
  - In Phase 8, prior prediction-error traces can influence future behavior through local observed state such as `last_prediction_error_magnitude` in [phase8/environment.py](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/environment.py).
  - Safer wording: prediction error is computed post-action and can shape later local selection indirectly through updated local state.

## 3. Architecture

### REAL node process

### Incorrect

- The sentence "Each node ... runs an independent local loop: perceive, select, execute, evaluate, consolidate" is out of date.
  - Current engine flow in [real_core/engine.py](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/real_core/engine.py) is:
    - observe
    - recognize
    - predict
    - select
    - execute
    - score
    - compare
    - consolidate

### Supported but simplified

- The "selection is substrate-biased" claim is correct at a high level.
  - Action costs are influenced by substrate support in Phase 8 through `use_cost(...)`.
  - However, Equation (1) should be treated as a conceptual simplification, not a literal one-line implementation of the current selector.
  - Current route choice in [phase8/selector.py](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/selector.py) includes many terms beyond substrate support, including recognition, prediction, history, task affinity, sequence hints, context feedback, branch pressure, and penalties.

- The "coherence evaluation" section is broadly correct, but Equation (2) is also a conceptual simplification.
  - The six dimensions are implemented in [phase8/adapters.py](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/adapters.py).
  - The current composite in `LocalNodeCoherenceModel.composite(...)` is a simple mean, not an exposed weighted sum with user-facing `w_i` parameters.

### Supported

- The six coherence dimensions in the text match the current code:
  - continuity
  - vitality
  - contextual_fit
  - differentiation
  - accountability
  - reflexivity

- Current cycle records really do preserve recognition, prediction, and prediction error in [real_core/types.py](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/real_core/types.py).

### Needs moderation

- The growth description is directionally right, but it is cleaner to say growth is gated by a combination of ATP surplus or anticipatory backlog plus routing/readiness signals, not only "ATP surplus while failing to route productively."
  - Current growth configuration in [phase8/topology.py](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/topology.py) includes:
    - `atp_surplus_threshold`
    - `anticipatory_growth_backlog_threshold`
    - contradiction and overload thresholds
    - routing feedback gates
    - context-resolution gates

## 4. Interpretability

### Strongly supported

This is one of the best-supported parts of the draft.

- The repo really does expose cycle-level records, selector score breakdowns, and targeted node probes.
- Interpretability as development workflow is explicitly supported by:
  - [INTERPRETABILITY.md](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/reports/INTERPRETABILITY.md)
  - [phase8/selector.py](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/selector.py)
  - [scripts/diagnose_c_node_probe.py](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/scripts/diagnose_c_node_probe.py)
  - [scripts/probe_phase8_transfer_recognition.py](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/scripts/probe_phase8_transfer_recognition.py)
  - [scripts/diagnose_phase8_transfer_prediction_interaction.py](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/scripts/diagnose_phase8_transfer_prediction_interaction.py)

### Case-study checks

- **Case 1: downstream transform commitment under latent uncertainty**
  - Supported by [2026-03-18 1640 - C Node Probe.md](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/traces/2026-03-18%201640%20-%20C%20Node%20Probe.md).
  - The quoted confidence values `0.28942`, `0.47695`, and `0.60893` are correct.
  - The intervention is reflected in Phase 8 route-transform gating behavior in [phase8/adapters.py](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/adapters.py).

- **Case 2: recognition absent, then present, then blunt**
  - Supported by:
    - [2026-03-18 2207 - Phase8 Transfer Recognition Probe.md](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/traces/2026-03-18%202207%20-%20Phase8%20Transfer%20Recognition%20Probe.md)
    - [2026-03-18 2212 - Transfer Recognition Diagnosis.md](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/traces/2026-03-18%202212%20-%20Transfer%20Recognition%20Diagnosis.md)
  - The draft's "zero to five recognized route entries" claim is accurate.

- **Case 3: occupancy V1 failure diagnosed at mechanism level**
  - Supported by:
    - [occupancy_bridge_seed13_20260319_summary.md](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/experiment_outputs/occupancy_bridge_seed13_20260319_summary.md)
    - [20260319_phase8_occupancy_v2_synthesis.md](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/summaries/20260319_phase8_occupancy_v2_synthesis.md)
  - The `0.032 -> 0.748` jump from enabling eval feedback is well supported.

## 5. Experimental Results

## 5.1 CVT-1 Transfer and Sample Efficiency

### Supported by current docs/traces

- Cold Task B `3.9 exact / 0.477 bit accuracy`
- Warm full `A -> B` `10.6 / 0.704`
- Warm substrate-only `A -> B` `7.3 / 0.586`
- Latent `A -> B` `7.0` vs visible `6.2`
- `A -> B -> C` and direct `A -> C` both at `7.6 exact`
- neural baseline criterion around `144-162` examples

These are consistently reflected in:

- [SYNTHESIS.md](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/reports/SYNTHESIS.md)
- [20260317_phase8_session_synthesis.md](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/summaries/20260317_phase8_session_synthesis.md)
- [technical_report.md](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/reports/technical_report.md)

### Minor caution

- Some of these claims are synthesis-level aggregates rather than re-derived directly from a single canonical JSON in this pass. They are still well supported by the repo's current summary layer.

## 5.2 Morphogenesis

### Supported

- Large-topology Task B gain of `+7.4 exact` is well supported in the March 17 synthesis/traces.
- The broad "difficulty-correlated growth" pattern is supported as a benchmark observation:
  - growth helps the weaker Task B condition
  - growth mildly hurts already-stronger Task A/C conditions

### Needs moderation

- It is safer to frame this as an empirical pattern observed on the tested topologies and scenarios, not as a universal law of REAL.

## 5.3 Occupancy

This is the section that needs the most factual cleanup.

### What is supported

- V1 bridge failure:
  - eval F1 about `0.032`
  - mean dropped packets rose from about `0.96` in training to `17.35` in eval
- V2 best context-enabled result:
  - eval F1 about `0.766`
- V3 best single-seed result:
  - warm accuracy `0.9807`
  - warm F1 `0.9524`
  - cold accuracy `0.9686`
  - cold F1 `0.9193`
  - from [v3_best_real_seed13.json](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/experiment_outputs/v3_best_real_seed13.json)
- V3 three-seed sweep aggregate:
  - mean warm accuracy `0.9734`
  - mean cold accuracy `0.9678`
  - mean warm delivery `0.9687`
  - mean cold delivery `0.9773`
  - mean efficiency ratio `0.9915`
  - from [v3_best_real_sweep_13_23_37.json](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/experiment_outputs/v3_best_real_sweep_13_23_37.json)

### What is incorrect or mixed

- **Dataset type**
  - The paper currently calls this a real-world occupancy dataset.
  - Current repo artifacts show the benchmark uses the synthetic file [`occupancy_synth_v1.csv`](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/occupancy_baseline/data/occupancy_synth_v1.csv).

- **Safer occupancy framing**
  - It is not accurate to call the current benchmark "real-world data."
  - It is accurate to call it:
    - a realistic room-occupancy prediction benchmark
    - a real-world-inspired occupancy prediction task
    - a room-occupancy problem framed after real sensor-based occupancy detection, evaluated here on a synthetic in-repo benchmark

- **Episode vs session terminology**
  - This should be made explicit in the paper because the MLP and REAL v3 are not organized around the same unit.
  - In V3 occupancy:
    - an **episode** is one rolling-window occupancy example
    - a **session** is a contiguous run of same-label episodes after temporal segmentation
  - The full V3 best-run inventory in [v3_best_real_seed13.json](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/experiment_outputs/v3_best_real_seed13.json) is:
    - `1344` raw rows
    - `1340` total episodes/windows
    - `89` total sessions
    - `62` train sessions
    - `27` eval sessions
    - `926` training episodes across those `62` sessions
    - `414` eval episodes across those `27` sessions
  - So sessions are the higher-level temporal units REAL uses to test carryover and orientation, while episodes are the within-session classification/routing units.

- **Dataset split comparison**
  - The MLP baseline summary is on `1072` train examples and `268` test examples in [occupancy_bridge_seed13_20260319_summary.md](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/experiment_outputs/occupancy_bridge_seed13_20260319_summary.md).
  - The V3 best run uses a session-aware split yielding `926` training episodes and `414` eval episodes across `62` train sessions and `27` eval sessions in [v3_best_real_seed13.json](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/experiment_outputs/v3_best_real_seed13.json).
  - So the comparison is **not** apples-to-apples at the split/protocol level.
  - But this mismatch is worth stating clearly because it is actually favorable to REAL in raw training-window count:
    - MLP train examples: `1072`
    - REAL V3 train episodes: `926`
  - The careful interpretation is: REAL reaches near-MLP task performance while being trained on fewer window-level training examples, but under a different, session-native evaluation protocol.

- **"REAL trained on 926 sessions"**
  - This is wrong.
  - It should be `926` training episodes/windows across `62` sessions.

- **"3-seed mean" table values**
  - The current table mixes sweep means and single-seed values.
  - If the table is truly a 3-seed mean, then the warm/cold F1 values should be derived from the sweep's per-seed F1s.
  - Averaging the per-seed F1s in [v3_best_real_sweep_13_23_37.json](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/experiment_outputs/v3_best_real_sweep_13_23_37.json) gives:
    - mean warm F1 `0.9357`
    - mean cold F1 `0.9213`
  - The current draft's `0.952` / `0.919` pair is seed-13-like, not a 3-seed mean.

- **Warm row labeled "persistent"**
  - The 3-seed sweep was run with `eval_mode = fresh_session_eval`, not persistent.
  - In fresh-session protocol, warm means a fresh system loaded with training carryover before each eval session; cold means a fresh blank system for each eval session.

- **Efficiency ratio meaning**
  - In current code, efficiency ratio is `warm_delivery / cold_delivery`, not a generic portability percentage.
  - The sweep mean `0.9915` means warm carryover delivery is near parity and slightly below cold delivery on average in that metric.
  - It does not support the strong conclusion that occupancy V3 has already demonstrated substrate portability as the main story.
  - What the occupancy V3 results currently support more strongly is near-MLP task performance under a REAL-native harness, not a clear warm-over-cold carryover win.

- **Precision/recall comparison to the MLP**
  - The current paper language around "near-identical precision (~0.98)" is not consistent with the checked-in baseline summary.
  - The stored MLP baseline summary reports:
    - precision `0.9455`
    - recall `0.9811`
    - F1 `0.9630`
  - For the 3-seed V3 sweep, averaging per-seed metrics gives:
    - mean warm precision `0.9541`
    - mean warm recall `0.9195`
  - So the safer conclusion is:
    - REAL is competitive on F1 and accuracy
    - REAL reaches that competitiveness with fewer training windows than the stored MLP baseline artifact
    - REAL's current occupancy tradeoff is lower recall than the MLP
    - "missing class-weighted feedback" is still a plausible hypothesis, not a demonstrated causal explanation yet

### Technical read of what the occupancy results currently show

- The MLP baseline is still stronger on the standard flat-window benchmark in [occupancy_bridge_seed13_20260319_summary.md](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/experiment_outputs/occupancy_bridge_seed13_20260319_summary.md):
  - accuracy `0.9851`
  - precision `0.9455`
  - recall `0.9811`
  - F1 `0.9630`

- REAL V3 best single-seed performance is genuinely close on task performance in [v3_best_real_seed13.json](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/experiment_outputs/v3_best_real_seed13.json):
  - warm accuracy `0.9807`
  - warm precision `0.9877`
  - warm recall `0.9195`
  - warm F1 `0.9524`

- REAL V3 three-seed sweep still supports a strong competitiveness claim, but with a lower mean F1 than the best seed:
  - mean warm accuracy `0.9734`
  - mean warm F1 `0.9357`
  - mean cold F1 `0.9213`
  - mean warm precision `0.9541`
  - mean warm recall `0.9195`
  - mean efficiency ratio `0.9915`
  - derived from [v3_best_real_sweep_13_23_37.json](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/experiment_outputs/v3_best_real_sweep_13_23_37.json)

- The technically important distinction is:
  - **MLP result**: stronger conventional classification benchmark under a flat rolling-window split
  - **REAL V3 result**: near-parity task performance under a session-native routing/carryover harness, using fewer training windows than the stored MLP artifact and preserving temporal session structure

- So the strongest accurate occupancy claim is:
  - REAL is competitive on the occupancy task itself
  - it does so under a fundamentally different learning regime
  - it does so with fewer training windows than the stored MLP benchmark artifact
  - and it does so while preserving session-level structure that the flat MLP benchmark does not model

## 6. Discussion and Conclusion

### Supported

- The paper's broader thesis that interpretability was used as a development method is strongly supported.
- The claim that the artifact revealed issues the initial framing did not anticipate is consistent with the trace record, especially around:
  - recognition availability vs usefulness
  - prediction becoming observable before strongly useful
  - occupancy V1 harness failure

### Needs correction

- The paragraph claiming that "a fresh system loaded with trained substrate performs within 0.85% of a continuously running system from the very first session" should not rely on the occupancy V3 efficiency ratio in its current form.
  - Current occupancy V3 fresh-session results do not show a strong warm-delivery advantage.
  - If you want a strong substrate-portability argument, it is better anchored in the earlier CVT-1 transfer/carryover results than in occupancy V3.

## Recommended Paper-Safe Reframing

If you want the paper to stay strong while staying accurate to the current repo, the safest version is:

- Treat occupancy V3 as the strongest evidence of REAL's task competence under a REAL-native harness.
- Treat interpretability as strongly supported both structurally and procedurally.
- Treat CVT-1 and transfer results as the stronger support for carryover/substrate claims.
- Treat occupancy carryover on V3 as still near parity and not yet the strongest win.
- Treat class-weighted-feedback explanations and some "knowledge carrier" language as hypotheses or partial interpretations, not settled conclusions.

## Minimal Must-Fix List Before Submission

1. Update the REAL loop description in the Architecture section.
2. Replace "real-world occupancy dataset" with language matching the current synthetic occupancy bridge benchmark, unless you are swapping to a real external artifact before submission.
3. Fix the occupancy table so it does not mix single-seed and sweep values.
4. Fix the occupancy baseline counts:
   - MLP baseline: `1072 train / 268 test`
   - REAL V3 best run: `926` train episodes across `62` sessions, `414` eval episodes across `27` sessions
5. Reword the efficiency-ratio interpretation so it does not claim stronger carryover evidence than the current occupancy outputs support.
6. Reword the class-weighted-feedback sentence as a hypothesis rather than a verified cause.

