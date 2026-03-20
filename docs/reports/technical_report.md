# REAL Neural Substrate Technical Report

_Updated: 2026-03-17_

This report is the standalone Markdown successor to the original Phase 8 `.docx` report. It merges:

- the March 16 technical report snapshot
- the March 16 latent-context and morphogenesis traces
- the March 17 session synthesis
- the March 17 neural-baseline and large-topology morphogenesis traces

It is intended to be the current high-level reference for what the repo has already demonstrated, what remains provisional, and which findings are strong enough to treat as the working benchmark set.

## 1. Executive Summary

REAL Neural Substrate is a local-learning research prototype built around the claim that useful computation, transfer, and structural adaptation can emerge from metabolically constrained node agents without global loss functions, broadcast reward, or backpropagation.

As of March 17, 2026, the strongest repo-level results are:

- Phase 8 already demonstrates positive `Task A -> Task B` transfer on the core 6-node CVT-1 substrate, with warm carryover outperforming cold start on both exact matches and mean bit accuracy.
- Latent-context transfer is now competitive with, and on the current March 17 benchmark slice slightly better than, the visible-context transfer path.
- A small neural-baseline comparison now exists and supports a strong sample-efficiency claim: the best latent neural baseline needs roughly `144-162` examples to reach criterion, while REAL reaches comparable milestone behavior in a single 18-packet session.
- Morphogenesis is no longer merely implemented; it is benchmarked. On the small topology it helps most in transfer and harder tasks, while on the 10-node large topology it becomes strongly beneficial for the hardest cold-start task and for warm transfer.
- Sequential `A -> B -> C` carryover works without catastrophic forgetting in the current benchmark slice.

The system should now be understood as a credible experimental platform for:

- sparse task learning
- local structural carryover
- cross-task transfer
- latent context inference
- topology growth under metabolic constraints

## 2. Architecture Snapshot

The repo has two layers:

- `real_core/`: generalized REAL engine, carryover, memory substrate, selectors, mesh, and shared types
- `phase8/`: node-local substrate experiments, routing/task environment, admission control, morphogenesis, and scenario definitions

The key architectural commitments remain:

- every node is a local REAL agent
- nodes observe only local state and direct neighbors
- actions cost ATP-like metabolic budget
- sink feedback returns upstream sequentially
- durable learning is written into maintained substrate rather than a global weight update
- no global gradient or centralized planner is allowed

At the experiment layer, packets carry mutable payload bits, optional context/task structure, and path history. Nodes can route, rest, inhibit, invest, and apply transform-plus-route actions. The substrate maintains:

- edge support
- transform/action support
- context-specific action support

Morphogenesis extends this by allowing nodes to bud edges or nodes when local metabolic conditions justify growth.

## 3. Experimental Program

### 3.1 CVT-1 small-topology benchmark

The original core benchmark uses a compact 6-node routing graph and 18-packet sessions. The task family is context-dependent:

- `Task A`: `context_0 -> rotate_left_1`, `context_1 -> xor_mask_1010`
- `Task B`: `context_0 -> rotate_left_1`, `context_1 -> xor_mask_0101`
- `Task C`: `context_0 -> xor_mask_1010`, `context_1 -> xor_mask_0101`

This setup lets the repo measure:

- cold learning
- warm full carryover
- substrate-only carryover
- directional transfer
- latent-context inference

### 3.2 Large-topology benchmark

The March 17 expansion adds a 10-node, 3-way branching topology with longer 36-packet sessions. This matters because it gives dynamic nodes a richer routing space and more time to accumulate useful substrate.

In practice, the large topology is the first setting where morphogenesis consistently earns its structure rather than only existing as a mechanistic possibility.

### 3.3 Neural baseline benchmark

The neural baseline harness uses the same 18-example CVT-1 sequence and the same rolling-window criterion:

- `MLP-explicit`: 5 inputs, explicit context provided
- `MLP-latent`: 4 inputs, no context provided
- `RNN-latent`: Elman RNN with hidden-state sequence memory

All baselines are trained online, one example at a time, predict-then-update, to keep the comparison close to REAL's operating regime.

## 4. Results

### 4.1 Small-topology transfer remains the core proof

The March 16 report established the original central result on the 6-node substrate:

- cold `Task B`: `3.9` exact matches, `0.477` mean bit accuracy
- warm full `Task A -> Task B`: `10.6` exact matches, `0.704` mean bit accuracy
- warm substrate-only `Task A -> Task B`: `7.3` exact matches, `0.586` mean bit accuracy

This remains the clearest demonstration that maintained substrate and carryover are doing real work rather than merely replaying recent episode history.

The transfer matrix and contradiction-debt work from March 16 also established that transfer is directional rather than symmetric: some prior task structures are useful launchpads, while others act as stale traps.

### 4.2 Latent context is now a first-class path, not just a degradation mode

March 16 latent-context work showed that hidden-context transfer could be rescued by a latent bridge and transfer-specific control split. The March 17 synthesis strengthens that story:

- before the March 17 latent retune, `Task B` latent cold-start was `4.0` exact and latent `A -> B` transfer was `5.8`
- after reducing latent commitment streak from `3` to `2` and tightening the promotion threshold from `0.75` to `0.78`, `Task B` latent cold-start rose to `8.6`
- on the March 17 benchmark slice, latent `A -> B` transfer reached `7.0` exact, slightly above visible `A -> B` transfer at `6.2`

The important interpretation is architectural, not merely numerical:

- visible carryover can poison future contexts because it stores strongly context-bound supports
- latent carryover accumulates less context-specific poison and can therefore transfer more safely across changed task conditions

That does not mean latent is universally better. The same March 17 session notes that cold latent `Task A` regressed from `3.0` to `2.2` under the faster-commitment setting. The current best reading is that latent commitment is now tuned for transfer advantage, not for uniformly best cold performance on every hidden-context task.

### 4.3 Neural baselines support the sample-efficiency claim

The March 17 neural-baseline trace adds the first serious comparison against online gradient-based learners.

The strongest numbers are from the epoch-scan criterion comparison:

- `MLP-explicit`: criterion in about `54` examples
- `MLP-latent`: does not reach criterion within 20 epochs
- `RNN-latent`: criterion in about `144-162` examples
- REAL: meaningful task performance within a single 18-example session

The single-pass neural exact-match counts were not fully logged, so they should be treated as approximate. The more defensible claim is the epoch-scan one:

- the best latent neural baseline requires roughly `8-9x` more examples than REAL's single-session path

This is especially important because the latent RNN is the fairest neural analogue to REAL's hidden-context setting. The result does not show that neural baselines fail in principle; it shows that under the same online, low-data regime, REAL is currently much more sample-efficient.

### 4.4 Morphogenesis is beneficial, but only in the right regime

The March 16 small-topology morphogenesis work already showed an early sweet spot:

- cold `Task B` on the 6-node topology did not improve meaningfully
- warm `Task A -> Task B` transfer with morphogenesis improved over fixed topology by about `+1.2` exact matches and `+0.078` bit accuracy

The March 17 large-topology results are much stronger:

- large-topology cold `Task B`: fixed `11.8`, growth `19.2`, delta `+7.4`
- large-topology `Task A -> Task B` transfer: fixed `15.2`, growth `17.4`, delta `+2.2`
- earned growth on task-carrying scenarios rose from `20%` on the small topology to `100%` on the large topology

At the same time, morphogenesis is not a universal win:

- large-topology cold `Task A`: `14.8 -> 13.2`
- large-topology cold `Task C`: `17.0 -> 16.0`

This has now become a stable emergent pattern:

- morphogenesis helps when the task is difficult enough to leave routing headroom
- morphogenesis hurts or mildly disrupts performance when the fixed topology is already efficient

That is a useful scientific result in its own right. The growth system is not blindly beneficial; it appears to self-activate where there is actual structural headroom and to impose a measurable disruption cost where there is not.

### 4.5 Large topology unlocks a qualitatively different growth regime

The large-topology traces make clear that topology size is not just a scaling detail. It changes the behavior class of morphogenesis:

- more candidate edges give new nodes viable niches
- longer sessions give growth enough time to earn feedback
- warm transfer provides routing clarity before growth fires

This is why large-topology transfer plus morphogenesis is currently the best growth result in the repo:

- `100%` earned growth
- `80%` win rate
- high dynamic-node utilization

The repo should therefore treat topology complexity as a real independent variable, not just a bigger version of the same benchmark.

### 4.6 Sequential transfer works without catastrophic forgetting

The March 17 sequential-transfer synthesis adds another major result:

- cold `Task C`: `4.6` exact
- `B -> C`: `6.0` exact
- `A -> B -> C`: `7.6` exact, `0.561` bit accuracy
- `A -> C` direct skip: `7.6` exact, `0.528` bit accuracy

The important part is not just the improvement over cold `Task C`, but that the `A -> B -> C` chain does not collapse into forgetting. Instead:

- some prior supports help because they preserve routing scaffold
- some prior supports hurt because they carry stale context-action expectations
- the overall effect is graceful specialization rather than catastrophic overwrite

That means the substrate is starting to behave like a layered transfer system rather than a single-task memorizer.

## 5. Consolidated Interpretation

Across the March 16 and March 17 work, five patterns now look stable enough to treat as the repo's current scientific position.

### 5.1 Carryover is real and useful

Both full and substrate-only carryover outperform cold start in the core transfer benchmark. This remains the bedrock result.

### 5.2 Context binding is both power and poison

Visible context enables strong task performance, but tightly context-bound supports can become stale under transfer. Latent carryover avoids some of that poisoning by construction.

### 5.3 Growth needs structure before it can help

Morphogenesis is most effective when:

- some routing clarity already exists
- context/task structure is present
- the topology is large enough for new nodes to find useful roles

That is why warm transfer and large topology are the current morphogenesis sweet spots.

### 5.4 The repo now has a baseline comparison story

The neural baseline work does not yet cover every comparison one might want, but it is already enough to justify a serious sample-efficiency claim:

- stateless latent models fail structurally
- recurrent latent models eventually learn, but require far more examples
- REAL is currently competitive or better under the most data-scarce online regime

### 5.5 Phase 8 is no longer just "routing with philosophy"

The repo now has evidence for:

- context-dependent computation
- transfer with carryover
- latent context inference
- topology adaptation
- a baseline comparison against neural learners

That is a much stronger position than the March 16 report alone captured.

## 6. Current Limits

Several limitations are now clearer than they were in the original `.docx` report.

- The most precise small-topology transfer result and the newer March 17 latent-transfer slice should be treated as different benchmark slices, not collapsed into a single table without noting the date and condition.
- Some neural single-pass numbers were reconstructed rather than logged directly; the epoch-scan comparison is the more reliable baseline claim.
- Morphogenesis still appears mismatched to task-free routing scenarios under the current CVT-1 coupling.
- Sustained-load anticipatory growth likely needs a new observation signal rather than more tuning of the current gates.
- The large-topology scenario and March 17 harnesses are documented here, but not all of that expansion work has been fully integrated into the standalone code package yet.

## 7. Recommended Next Report-Level Milestones

The next meaningful report revision should be driven by one or more of these:

1. Port the large-topology and sequential-transfer harnesses fully into the standalone runnable code, not just the documentation layer.
2. Add a direct neural transfer baseline (`Task A -> Task B` fine-tuning) rather than only cold-start neural baselines.
3. Re-run the latent plus morphogenesis benchmark after confidence-gated growth is integrated in the standalone package.
4. Freeze one benchmark table for small topology and one for large topology so later progress does not blur across incompatible slices.

## 8. Source Notes

Primary source documents in this repo:

- `docs/20260317_phase8_session_synthesis.md`
- `docs/traces/20260317_phase8_neural_baseline_trace.md`
- `docs/traces/20260317_phase8_morphogenesis_large_trace.md`
- `docs/traces/20260317_phase8_latent_transfer_morphogenesis_robustness_trace.md`
- `docs/project_overview_cross_phase.md`
- `docs/architecture_notes.md`

Legacy source carried forward conceptually:

- the original March 16 `Phase8_Technical_Report.docx`
