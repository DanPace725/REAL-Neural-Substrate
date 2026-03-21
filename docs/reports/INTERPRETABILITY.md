# Interpretability In REAL Neural Substrate

_Why interpretability has been central to development, what is inspectable in the architecture, and how that inspectability has been used to diagnose and improve the system._

---

## 1. Why This Matters Here

Interpretability has not been a side feature in this repo. It has been one of the main engineering tools used to develop the architecture.

In practice, many of the biggest changes in Phase 8 were not driven by aggregate accuracy alone. They were driven by inspecting:

- what specific nodes were seeing
- what action terms were actually winning a decision
- whether recognition or prediction was present, absent, early, late, sparse, or misleading
- how substrate support and carryover were shaping later behavior
- where a failure was happening in the local loop

This matters because REAL is not organized like a conventional end-to-end optimizer. The architecture is local, sequential, substrate-writing, and cycle-driven. That makes it possible to inspect the learning process at the same level the system actually operates.

The practical claim of this document is:

> REAL has been developed through direct inspection of local state, local decisions, and local memory transitions, not only through post hoc score comparison.

---

## 2. What Is Natively Inspectable

The interpretability story starts in the core types, not only in the scripts.

### 2.1 Cycle-level records are first-class data

`real_core` stores a per-cycle record in [`real_core/types.py`](../../real_core/types.py). [`CycleEntry`](../../real_core/types.py) includes:

- `state_before`
- `state_after`
- `dimensions`
- `coherence`
- `delta`
- `recognition`
- `prediction`
- `prediction_error`

That means a local run does not just yield an output. It yields a structured record of what the node saw, what it did, how that action scored, and what anticipatory state was present at the time.

### 2.2 Selection context is explicit

[`SelectionContext`](../../real_core/types.py) and the engine wiring in [`real_core/engine.py`](../../real_core/engine.py) let selectors see current-cycle recognition and prediction without collapsing them into one hidden score.

This is important because the repo can distinguish:

- recognition of a familiar local pattern
- prediction of expected local action outcome
- later prediction error

rather than treating them as one opaque "confidence" value.

### 2.3 Selector term breakdowns are exposed

[`phase8/selector.py`](../../phase8/selector.py) now exposes:

- `capture_route_breakdowns`
- `debug_route_score_breakdown(...)`
- `latest_route_score_breakdowns()`

This has been one of the most important interpretability surfaces in the repo. It makes source and node decisions inspectable as term-by-term comparisons rather than as unexplained chosen actions.

### 2.4 Anticipation metrics are summarized separately

[`scripts/benchmark_anticipation_metrics.py`](../../scripts/benchmark_anticipation_metrics.py) computes metrics like:

- predicted route entry counts
- first predicted route cycle
- mean prediction confidence
- source stale-family risk

This gives the repo a way to ask whether anticipation exists and when it appears, independently of whether a benchmark score has improved yet.

### 2.5 Carryover and experiment manifests are inspectable artifacts

The repo's experiment tooling writes JSON manifests and targeted probe outputs under [`docs/experiment_outputs/`](../experiment_outputs/). These are not just final scores. Many of them preserve node summaries, cycle summaries, transfer metrics, and protocol metadata so the reasoning chain is reviewable later.

---

## 3. The Main Interpretability Tools In Practice

Several script families now act as the repo's working interpretability toolkit.

### 3.1 Node probes

- [`scripts/diagnose_benchmark_node_probe.py`](../../scripts/diagnose_benchmark_node_probe.py)
- [`scripts/diagnose_c_node_probe.py`](../../scripts/diagnose_c_node_probe.py)

These inspect per-cycle node behavior such as:

- packet/task/context availability
- latent-context confidence and promotion readiness
- source-sequence hints
- route branch and transform choices
- contradiction pressure
- growth candidate and bud availability
- first-cycle timing markers for latent activation or guidance

Representative result artifacts:

- [`c_node_probe_c3_taskb_taskc_growth_latent_seed13_20260318.json`](../experiment_outputs/c_node_probe_c3_taskb_taskc_growth_latent_seed13_20260318.json)
- [`c_node_probe_c3_taskb_taskc_growth_latent_seed13_postroutegate_20260318.json`](../experiment_outputs/c_node_probe_c3_taskb_taskc_growth_latent_seed13_postroutegate_20260318.json)

### 3.2 Recognition and selector probes

- [`scripts/probe_phase8_recognition_bias.py`](../../scripts/probe_phase8_recognition_bias.py)
- [`scripts/probe_phase8_transfer_recognition.py`](../../scripts/probe_phase8_transfer_recognition.py)
- [`scripts/diagnose_phase8_transfer_selector_interaction.py`](../../scripts/diagnose_phase8_transfer_selector_interaction.py)

These were used to answer questions like:

- does recognition activate at all in real transfer traffic?
- if it activates, when?
- does it matter to a decision?
- if it matters, which scoring terms is it competing with?

### 3.3 Prediction and expectation probes

- [`scripts/diagnose_phase8_transfer_prediction_interaction.py`](../../scripts/diagnose_phase8_transfer_prediction_interaction.py)
- [`phase8/expectation.py`](../../phase8/expectation.py)

These made it possible to test whether prediction was merely present in traces or whether it actually changed route decisions.

### 3.4 Carryover diagnostics

- [`scripts/diagnose_b_to_c_carryover.py`](../../scripts/diagnose_b_to_c_carryover.py)
- [`scripts/analyze_transfer_timecourse.py`](../../scripts/analyze_transfer_timecourse.py)

These support interpretability at the session and transfer level rather than only at the single-node level.

### 3.5 Occupancy analysis

- [`scripts/analyze_experiment_output.py`](../../scripts/analyze_experiment_output.py)
- [`scripts/run_occupancy_real_v3.py`](../../scripts/run_occupancy_real_v3.py)

The occupancy series extended interpretability into an external-dataset setting by making delivery, feedback, admission, early-session orientation, and context-transfer applicability visible rather than relying on F1 alone.

---

## 4. Five Concrete Development Cases

The strongest argument for REAL interpretability is not theoretical. It is the repeated pattern where a local diagnostic found a specific failure mode and a targeted architectural change followed from it.

### 4.1 Case 1: Downstream nodes were committing transforms too early under latent uncertainty

Key traces:

- [`2026-03-18 1640 - C Node Probe.md`](../traces/2026-03-18%201640%20-%20C%20Node%20Probe.md)
- [`2026-03-18 1646 - Downstream Latent Route Gate.md`](../traces/2026-03-18%201646%20-%20Downstream%20Latent%20Route%20Gate.md)

What the probe showed:

- `task_c` was underperforming `task_b` early on generated `C3`
- the first major latent node behaved similarly across tasks
- the divergence localized downstream, especially at `n3`
- `n3` was repeatedly choosing non-identity transform routes while latent context was available but still below promotion threshold

That is a very specific diagnosis. It is not "performance is low." It is:

> a downstream node is making hard transform commitments during an ambiguous latent window.

The follow-up change in [`phase8/adapters.py`](../../phase8/adapters.py) added a narrow downstream action gate that suppresses non-identity `route_transform:*` choices before latent promotion is ready.

Observed result:

- the ambiguous window shifted from hard transform commitment to identity routing
- `task_c` improved sharply in the quick benchmark read described in the follow-up trace

This is a clean example of interpretability driving a targeted mechanism change.

### 4.2 Case 2: B2 was not only an inference problem; it was also a use-path problem

Key traces:

- [`2026-03-18 2027 - B2 Benchmark Node Probe.md`](../traces/2026-03-18%202027%20-%20B2%20Benchmark%20Node%20Probe.md)
- [`2026-03-18 2041 - B2 Use Path Analysis.md`](../traces/2026-03-18%202041%20-%20B2%20Use%20Path%20Analysis.md)

What the initial probe showed:

- the source node built strong sequence confidence
- latent recruitment did happen
- route and transform policy still looked almost the same as a less capable baseline

Interpretation:

> latent evidence existed, but it was not redirecting behavior.

The follow-up then inspected the actual use path:

- source-sequence estimate
- source-sequence transform hint
- latent estimate
- chosen route transform

That analysis found two separate problems:

1. a modeling mismatch in the B-family sequence window definition
2. a source observation mismatch between what the capability controller used and what the source selector observed

After fixing those, the new probe showed something even more useful:

- the selector now received strong pre-action guidance
- but it still ignored the strongest hinted transform about 25% of the time in the short `B2` run

So the repo moved from "B2 fails" to "B2 is partly a selector integration / weighting problem." That is a much stronger design diagnosis than a benchmark score alone can provide.

### 4.3 Case 3: Recognition was first absent, then present, then shown to be blunt

Key traces:

- [`2026-03-18 2207 - Phase8 Transfer Recognition Probe.md`](../traces/2026-03-18%202207%20-%20Phase8%20Transfer%20Recognition%20Probe.md)
- [`2026-03-18 2212 - Transfer Recognition Diagnosis.md`](../traces/2026-03-18%202212%20-%20Transfer%20Recognition%20Diagnosis.md)
- [`2026-03-18 2243 - Transfer Selector Interaction Diagnosis.md`](../traces/2026-03-18%202243%20-%20Transfer%20Selector%20Interaction%20Diagnosis.md)

This sequence is especially important because it shows three different interpretability stages.

Stage 1: the first real transfer probe showed a null result.

- recognition bias on vs off produced the same transfer outcome
- `recognized_route_entry_count = 0`

The interpretation was not "recognition does nothing." It was:

> recognition is not ecologically engaged in real transfer traffic yet.

Stage 2: the follow-up diagnosed a representation mismatch.

- route patterns were written in substrate key space
- transfer-time observations did not expose aligned substrate-key aliases
- the recognizer therefore had no matching local coordinate system

Fixes were made in:

- [`phase8/adapters.py`](../../phase8/adapters.py)
- [`real_core/recognition.py`](../../real_core/recognition.py)

After that, recognition became active in warm transfer.

Stage 3: selector interaction diagnostics showed that recognition was now active, but not always helpful.

Using term-level route score breakdowns from [`phase8/selector.py`](../../phase8/selector.py), the repo could see that:

- recognition was not being ignored
- it was sometimes large enough to win close source decisions
- in the tested slice, it tended to tip near-ties toward a stale carried family

This is a strong example of why explicit breakdown terms matter. The conclusion was not "increase recognition weight" or "delete recognition." The conclusion was:

> recognition needed freshness or contradiction discounting, because it was arriving in time but being integrated too bluntly.

### 4.4 Case 4: Prediction became observable before it became strongly useful

Key traces:

- [`2026-03-19 1008 - Phase8 Expectation Binding Probe.md`](../traces/2026-03-19%201008%20-%20Phase8%20Expectation%20Binding%20Probe.md)
- [`2026-03-19 1020 - Phase8 Prediction Interaction Diagnosis.md`](../traces/2026-03-19%201020%20-%20Phase8%20Prediction%20Interaction%20Diagnosis.md)

Prediction was added through [`phase8/expectation.py`](../../phase8/expectation.py) and wired into node-local runs through [`phase8/node_agent.py`](../../phase8/node_agent.py).

The first expectation-binding pass established that:

- `recognize -> predict -> select` was now structurally real inside Phase 8
- predicted route entry counts were nonzero
- first predicted route cycles appeared very early
- lightweight transfer outcomes still did not move much

The prediction-interaction diagnostic then refined the answer:

- prediction could alter source decisions
- its effect was typically small
- it often mattered later than the early adaptation window
- on some seeds it was active but produced no decision divergence at all

That is interpretability serving scientific discipline:

- prediction was not declared a success just because it existed
- it was not declared useless just because benchmark scores barely moved
- instead the repo identified the new bottleneck: prediction terms were too weak or too redundant with existing evidence

### 4.5 Case 5: Occupancy V1 looked terrible because the harness was wrong, not because REAL was incapable

Key references:

- [`20260319_phase8_occupancy_v2_synthesis.md`](../summaries/20260319_phase8_occupancy_v2_synthesis.md)
- [`2026-03-20 1018 - Occupancy V3 Harness and Sweep Follow Through.md`](../traces/2026-03-20%201018%20-%20Occupancy%20V3%20Harness%20and%20Sweep%20Follow%20Through.md)

This case is more system-level than node-level, but it is still interpretability in the repo's development sense.

The occupancy analysis did not stop at a bad eval F1. It inspected the underlying runtime behavior and found:

- feedback was suppressed during evaluation
- ATP therefore collapsed during eval
- dropped packets surged
- carryover was not isolated
- the context-indexed support mechanism was dormant because no context bit was injected

The redesign that followed was architectural, not cosmetic:

- feedback during eval
- explicit fresh-session carryover
- context activation
- later, REAL-native ingress, online running context, multihop routing, and explicit protocol reporting

That path eventually led to the V3 occupancy harness and the near-parity occupancy result described in [`docs/reports/SYNTHESIS.md`](./SYNTHESIS.md).

Again, the pattern is the same:

- inspect mechanism-level behavior
- localize the failure
- revise the architecture around what REAL is actually supposed to demonstrate

---

## 5. What Is Distinct About REAL Here

The repo's interpretability is not just "we log more metrics." The more important distinction is structural.

### 5.1 Explanations are local and native

REAL decisions are made by local nodes with local state, local memory, and local selection context. The repo can inspect those objects directly. It does not need to infer a local decision explanation from a huge hidden global state after the fact.

### 5.2 Memory is inspectable as structure

Because durable learning is written into substrate support, patterns, action supports, and carryover rather than into one opaque weight tensor, the repo can inspect what was consolidated, which supports are active, and whether stale structure is helping or harming transfer.

### 5.3 Counterfactuals are cheap and meaningful

Many of the probes work by toggling one mechanism while holding the rest of the system fixed:

- recognition bias on vs off
- prediction term on vs off
- carryover mode full vs substrate vs cold
- fresh-session vs persistent eval

That gives the repo causal leverage in analysis instead of only correlation.

### 5.4 Null results are still informative

A recurring pattern in the traces is that a null benchmark result still narrowed the architectural question because the repo could ask:

- was the mechanism absent?
- present but late?
- present but weak?
- present and harmful?

That is a much stronger workflow than "accuracy did not improve."

---

## 6. Current Limits

The interpretability story is strong, but it is still fragmented.

Current limitations:

- many probes are standalone scripts rather than one unified interface
- the key insights still live partly in traces rather than in one stable doc
- some analyses are source-node focused and less standardized for mid-graph nodes
- occupancy analysis is more mature at the harness level than at the node-level introspection level

In other words, the capability is real, but the documentation and interface around it are still catching up.

---

## 7. Practical Starting Points

If you want to understand how interpretability is used in this repo, start with:

1. [`real_core/types.py`](../../real_core/types.py)
2. [`phase8/selector.py`](../../phase8/selector.py)
3. [`scripts/diagnose_benchmark_node_probe.py`](../../scripts/diagnose_benchmark_node_probe.py)
4. [`scripts/diagnose_c_node_probe.py`](../../scripts/diagnose_c_node_probe.py)
5. [`scripts/diagnose_phase8_transfer_selector_interaction.py`](../../scripts/diagnose_phase8_transfer_selector_interaction.py)
6. [`scripts/diagnose_phase8_transfer_prediction_interaction.py`](../../scripts/diagnose_phase8_transfer_prediction_interaction.py)
7. [`docs/traces/2026-03-18 2212 - Transfer Recognition Diagnosis.md`](../traces/2026-03-18%202212%20-%20Transfer%20Recognition%20Diagnosis.md)
8. [`docs/traces/2026-03-18 2243 - Transfer Selector Interaction Diagnosis.md`](../traces/2026-03-18%202243%20-%20Transfer%20Selector%20Interaction%20Diagnosis.md)
9. [`docs/traces/2026-03-19 1020 - Phase8 Prediction Interaction Diagnosis.md`](../traces/2026-03-19%201020%20-%20Phase8%20Prediction%20Interaction%20Diagnosis.md)
10. [`docs/summaries/20260319_phase8_occupancy_v2_synthesis.md`](../summaries/20260319_phase8_occupancy_v2_synthesis.md)

---

## 8. Bottom Line

One of the clearest differentiators of REAL in this repo is that interpretability has been part of the architecture and the development process from the start of Phase 8 work, even if it was not previously written down in one place.

The most important practical point is:

> REAL has repeatedly been improved by reading local state, local memory, and local decision terms directly, then changing the mechanism that those readings exposed.

That workflow is already visible across the traces. This document is meant to make that pattern explicit.
