# Allostatic Neural Substrate: Emergent Competence and Native Interpretability Through Metabolically Constrained Local Agents

_Draft v1 — ALIFE 2026 submission target_

---

## Abstract

We present REAL Neural Substrate, a learning architecture in which each node of a network is an autonomous local agent operating under a metabolic energy budget rather than a passive unit updated by global gradient descent. Agents accumulate a persistent routing substrate through allostatic self-regulation, stigmergic substrate writing, and context-indexed action support — producing transfer, latent context inference, and topology growth as emergent properties rather than designed objectives. On a real-world room occupancy dataset, the system reaches F1 of 0.952 (warm carryover) against an MLP baseline of 0.963, achieving near-parity through local allostasis without any global loss function, and with substrate that transfers to a fresh system at 99.15% efficiency.

Beyond performance, we identify and distinguish two roles that native interpretability plays in this architecture: interpretability as a structural **capability** — the system's local decisions, memory structures, and metabolic state are directly readable at the node level — and interpretability as a **development workflow** — this readability was the primary tool by which failure modes were diagnosed and architectural changes were motivated. We demonstrate the latter through five development cases where node-level traces identified specific breakdowns, each of which led to a targeted mechanism change that improved measured behavior. We argue that these two roles are both novel relative to standard neural approaches, where interpretability is neither native to the architecture nor part of the development process.

---

## 1. Introduction

The dominant paradigm in machine learning optimizes a global loss function by propagating error gradients through every parameter in a model simultaneously. This approach is powerful but carries two structural costs. First, the learned representations are distributed across the full weight tensor: no individual component of the network has a local explanation for its behavior, because behavior is an emergent property of millions of interacting parameters shaped by a process — backpropagation — that has no biological analogue. Second, interpretability is a retrospective problem. When the system fails, the failure is visible only in aggregate output; the mechanism producing that failure is not accessible without external probe methods (SHAP, LIME, attention visualization) that approximate explanations rather than read them.

Biological learning systems work differently. Neurons maintain local energy budgets; synaptic modification is local, conditional on pre- and post-synaptic activity; learning is accumulated in substrate structure rather than communicated globally. The persistent physical substrate — not a weight matrix, but a pattern of connection strengths shaped by metabolic history — is the memory. And crucially, this substrate is readable: its state at any moment reflects the causal history of the organism's experience.

REAL (Relationally Embedded Allostatic Learning) Neural Substrate takes these biological principles seriously as architectural constraints rather than metaphors. Each node in the network instantiates a local REAL engine that: observes only its immediate neighborhood, selects actions from a local vocabulary under metabolic pressure, evaluates its own behavior across six relational coherence dimensions, and consolidates useful patterns into a persistent substrate that reduces the future cost of behaviors that have historically earned feedback. No node has a global view. No global gradient is computed. The network learns through the compound effect of local agents managing their own metabolic survival.

This paper makes three connected claims:

1. **Competence.** A network of local REAL agents, without any global objective, develops cross-task transfer, latent context inference, difficulty-correlated topology growth, and near-MLP performance on a real-world classification task it was not designed for.

2. **Interpretability as capability.** Because computation in REAL emerges from local agents with explicit local state, the network is natively inspectable: node decisions, ATP budgets, action support structures, context confidence levels, and routing choices are all direct objects that can be read without post-hoc approximation.

3. **Interpretability as development workflow.** This readability was not incidental. Across the development of Phase 8, the primary engineering methodology was: inspect local state → identify the specific mechanism producing a failure → change that mechanism → verify. We document five cases where this workflow produced targeted improvements that would not have been reachable through aggregate accuracy tracking alone.

---

## 2. Background and Motivation

### 2.1 Biologically-Grounded Learning

A persistent theoretical thread in ALife and cognitive science holds that learning in biological systems is fundamentally allostatic: organisms regulate their internal state toward viable operating ranges, and behavioral adaptation is a consequence of that regulation rather than a separate optimization process [citations]. This contrasts sharply with supervised learning, where an external loss signal drives parameter update — a process that has no plausible biological substrate.

Stigmergy — learning through modification of a shared environment rather than through direct communication or centralized update — has been studied extensively in swarm systems [citations] and underlies proposals for distributed cognition [citations]. A substrate that encodes behavioral history as a bias on future behavior is stigmergic in precisely this sense: it is written by action, read by future action, and persists beyond any individual session.

Predictive processing frameworks [citations] propose that biological neural systems are fundamentally anticipatory: each local circuit maintains a generative model of its expected inputs, generating predictions that can be confirmed or violated. REAL's recognition-anticipation-prediction loop operationalizes this at the node level.

### 2.2 Interpretability in Neural Systems

The machine learning interpretability literature broadly divides into post-hoc methods and transparent-by-design approaches. Post-hoc methods — SHAP, LIME, integrated gradients, attention visualization — approximate the behavior of a trained model by testing input perturbations or analyzing internal activations [citations]. They are correlational: they identify what inputs a model is sensitive to, not what decision procedure it executed.

Transparent-by-design approaches include decision trees, linear models, and rule-based systems, which are interpretable because their decision procedures are explicit. The cost is typically expressivity: these models struggle to match the performance of deep networks on complex tasks.

REAL proposes a third position: a system that is expressive (capable of acquiring complex routing behavior across multi-step tasks) while remaining natively interpretable (because every decision is made by a local agent with an explicit local state, not by a global function composition). This native interpretability is not a feature added to an opaque system — it is a structural property of the architecture.

---

## 3. Architecture

### 3.1 The REAL Core Loop

The generalized REAL loop is:

```
observe → recognize → predict → select → execute → score → compare → consolidate
```

Each node in the network runs this loop independently on every cycle. A cycle's output is not just a routing decision: it is a structured record (`CycleEntry`) containing the node's state before and after the action, the coherence dimensions scored, the delta from the previous cycle, and — as of the current architecture — recognition confidence and prediction error. This record is first-class data: it persists in the node's episodic trace and is available for direct inspection.

**Observe.** The node reads its immediate neighborhood: packets present, ATP balance, context signal (visible or latent), and — critically — substrate-key aliases that expose the same coordinate space in which the node's route patterns were consolidated. This last detail matters for recognition: the observation must be in the same representational space as the stored patterns, or pattern matching cannot fire.

**Recognize.** A `PatternRecognitionModel` compares the current observation against consolidated route patterns, returning a recognition confidence if a match is found. Recognition is local: the node can identify that a familiar routing situation has recurred, without knowing whether any other node has reached the same conclusion.

**Predict.** A prediction module (`phase8/expectation.py`) generates an expected routing outcome given the current recognition state and action history. Prediction error on the previous cycle's outcome feeds back into the current cycle's selection context.

**Select.** A CFAR-based selector draws on the substrate for cost biasing: actions that have historically earned feedback cost less ATP to attempt. The substrate creates behavioral inertia toward what has worked — allostatic regulation in the literal sense. The selection context is explicit: the selector receives current recognition confidence and prediction state as named fields, not collapsed into an opaque hidden vector.

**Execute.** The selected action is applied: route a packet toward a neighbor (with or without transform), rest, invest ATP in a connection, or apply an inhibitory signal to a neighbor node.

**Score.** A coherence model evaluates the outcome across six dimensions derived from the E² relational primitives:
- _Continuity_: identity persistence through action sequences
- _Vitality_: productive energy expenditure (inverted parabola; neither idle nor exhausted)
- _Contextual fit_: alignment between the node's action and the current context signal
- _Differentiation_: contrast with neighboring nodes' behavior (avoiding redundancy)
- _Accountability_: coherence between stated intent and observed outcome
- _Reflexivity_: behavioral revision following coherence dips

**Compare.** The new score is compared against the node's recent history. Significant deviations — positive or negative — are flagged for consolidation.

**Consolidate.** Useful patterns migrate from the fast episodic trace (`H_e`) through a consolidated memory layer (`H_c`) into the maintained substrate (`M_s`). The substrate is the durable learned structure: it physically reduces the ATP cost of successful behaviors and indexes action supports by context, so that context-specific routing preferences accumulate separately and are recoverable in future sessions.

### 3.2 Phase 8: A Network of Local REAL Agents

Phase 8 instantiates multiple REAL core engines simultaneously as nodes in a routing graph. Packets enter at a source node and must reach a sink node, with the correct payload transform applied en route. The sink returns feedback upstream through the path that delivered the packet; nodes on the successful path earn ATP.

Key components that are specific to Phase 8:

**The substrate.** `substrate.py` and `consolidation.py` maintain edge support (how reliable each outgoing route has been) and context-indexed action support (how valuable a specific transform action has been under each context bit). Both structures persist across sessions through explicit carryover serialization and loading.

**Context modes.** In _visible_ mode, the current context bit is provided directly to nodes. In _latent_ mode, nodes must infer context from their local packet flow statistics — tracking whether recent feedback patterns suggest context_0 or context_1 is active. Latent inference is slower to commit (typically 2-3 cycles of consistent evidence before promotion) but produces substrate entries indexed without a context binding, which are naturally transfer-safe.

**Morphogenesis.** When a node accumulates ATP surplus beyond a threshold while routing feedback indicates the existing topology is insufficient, it can bud a new node or edge. The surplus gate means growth fires precisely when the node is metabolically stressed — when it is collecting energy without successfully routing. This creates difficulty-correlated growth as an emergent property: topology expands where the network is struggling, not where it is succeeding.

**Admission control.** The source node gates packet ingress based on its current metabolic state. The network can only accept new packets when its budget allows — preventing runaway ATP collapse under load.

**The recognition–anticipation–prediction loop.** Added in the current codebase, this loop gives nodes a structured form of memory-based anticipation: recognize a familiar context, predict the expected outcome, let prediction error modulate selection. This is the node-level implementation of predictive processing, local to each agent without any global consistency requirement.

---

## 4. Interpretability

### 4.1 Interpretability as Structural Capability

The REAL architecture is natively inspectable in ways that conventional neural networks are not. This is not a consequence of added logging infrastructure — it is a consequence of how computation is organized.

**Local decisions are explicit.** In a feedforward neural network, the "decision" at any layer is a matrix multiplication followed by a nonlinearity. There is no agent making a choice, no action vocabulary from which a selection was made, and no reason beyond the global gradient history that the weights have the values they do. In REAL, each node selects from an explicit action vocabulary. The selected action, the runner-up actions, and the ATP cost assigned to each are all concrete, readable values. The `debug_route_score_breakdown()` interface in `phase8/selector.py` exposes the selection as a term-by-term comparison: action support weight, coherence history bias, recognition confidence contribution, and ATP cost, all separately visible.

**Memory is inspectable as structure.** In a trained neural network, "what the network learned" is distributed across the full weight tensor in a form that resists direct interpretation. In REAL, what the node learned is encoded in specific substrate entries: this edge has support X under context_0, this transform action has support Y under context_1. These entries can be enumerated, compared across sessions, and selectively included or excluded in carryover experiments. "Does the substrate from Task A help or hurt Task B?" is a direct question with a direct answer, not an inference from weight norms.

**Counterfactuals are cheap and causally meaningful.** Many REAL experiments are designed as mechanism toggles: recognition bias on vs. off, prediction term on vs. off, fresh-session vs. persistent eval, full vs. substrate-only carryover, visible vs. latent context mode. These toggles isolate the contribution of each mechanism to the measured outcome. The resulting comparisons are causally interpretable in a way that attention ablations in transformers typically are not — because in REAL, the toggled mechanism has a clear local functional role, not a distributed one.

**Null results are diagnostically informative.** When a mechanism produces no improvement in aggregate metrics, REAL's local observability allows a more precise question: was the mechanism absent? Present but too late? Present but competing with a stronger term? This precision prevents the false conclusion that a mechanism is useless simply because accuracy didn't move.

### 4.2 Interpretability as Development Workflow

The structural capability described above would be of limited scientific value if it were only used after the fact to explain completed behavior. What distinguishes the development of Phase 8 is that local inspectability was the primary engineering methodology throughout. We document five cases where this workflow was decisive.

**Case 1: Downstream transform commitment under latent uncertainty.** Task C underperformed Task B on generated C3 even though the first major latent node (`n2`) behaved identically across both tasks. A node probe revealed that node `n3` was repeatedly selecting hard transform-specific routes while latent context confidence was below promotion threshold (cycle 25: confidence 0.289; cycle 30: confidence 0.477; cycle 32: confidence 0.609 — none above the 0.78 promotion threshold). The diagnosis was precise: the node had a packet and a task but was committing to transforms before it had sufficient context confidence to do so correctly. The intervention was targeted: a downstream action gate in `phase8/adapters.py` that suppresses non-identity transform choices while latent context is available but unpromoted. Task C improved sharply in subsequent benchmarks. Note what this workflow provided: not "change the learning rate" or "train longer," but a specific mechanistic claim ("node N3 is committing transforms before context is ready") followed by a minimal surgical fix.

**Case 2: Recognition absent due to representation mismatch.** The first recognition probe on warm transfer returned `recognized_route_entry_count = 0`. Rather than concluding that recognition was ineffective, the diagnostic inspected why it was zero. The finding: Phase 8 consolidates route patterns using substrate key space (`edge:n1`, `edge:n2`, etc.), but transfer-time observations did not expose those keys, so the recognizer had no aligned coordinate system to compare against. The fix updated `LocalNodeMemoryBinding.modulate_observation()` to expose substrate-key aliases in the observation. After this change, `recognized_route_entry_count` rose from 0 to 5 (rate 0.061, mean confidence 0.549). Recognition was now genuinely active — though sparse, and not yet strongly coupled to improved transfer outcomes. This established the new bottleneck ("recognition present but sparse") rather than the old false negative ("recognition useless").

**Case 3: Recognition present but blunt.** The selector interaction diagnostic then showed that recognition was firing and occasionally winning close decisions — but tipping them toward stale carried route families rather than the current task's correct transform. The conclusion was not "disable recognition" but "recognition needs freshness or contradiction discounting." This is a much more precise research question than any aggregate accuracy comparison could produce.

**Case 4: Prediction observable before it is useful.** The expectation binding probe showed that the recognize–predict–select loop was structurally active (nonzero predicted route entry counts, early first prediction cycles) but prediction's influence on route decisions was small and sometimes statistically zero. The interpretation was neither "prediction works" nor "prediction fails" but: "prediction terms are arriving but are too weak or too redundant with existing evidence to swing decisions in this session length." This locates the research frontier.

**Case 5: Occupancy V1 failure diagnosed at the mechanism level.** The initial occupancy evaluation produced an eval F1 of 0.032 — catastrophic. Rather than treating this as evidence that REAL cannot perform classification, the harness was inspected node-by-node. Three specific failure modes were identified: (1) feedback was suppressed during evaluation, causing progressive ATP collapse — dropped packets surged from under 1 per episode during training to over 17 per episode during eval; (2) no carryover round-trip was tested, so the system's primary learning mechanism was never measured; (3) the context-indexed action support layer was dormant because no context signal was injected. Each flaw was addressed independently. Enabling feedback alone raised eval F1 from 0.032 to 0.748 — a 23× improvement — confirming that the dominant failure was ATP starvation, not representational incapacity.

The pattern across all five cases is the same: a local observation narrows the failure to a specific mechanism, a targeted change addresses that mechanism, and the result is verified both locally (the mechanism now fires as intended) and globally (aggregate performance improves). This workflow is not available in conventional neural network development, where the equivalent of "node N3 is committing transforms too early" does not exist as a statement — there are no nodes making choices, only weights encoding distributed tendencies.

---

## 5. Experimental Results

### 5.1 CVT-1: Transfer, Latent Context, and Sample Efficiency

The primary controlled benchmark is CVT-1, a context-dependent routing task in which the correct payload transform depends on a context bit. Three task variants (A, B, C) define a structured transfer landscape where some prior task structures are useful priors and others are context poisons.

**Cold vs. warm carryover.** On the 6-node baseline topology (18-packet sessions), cold start on Task B produces 3.9 exact matches (mean bit accuracy 0.477). Full episodic carryover from Task A raises this to 10.6 exact matches (0.704), and substrate-only carryover to 7.3 (0.586). Both forms of carryover substantially outperform cold start, confirming that the maintained substrate is doing real work and is not merely a side effect of continuous runtime state.

**Latent context inference.** In latent mode, nodes infer context from packet flow statistics without being given an explicit label. After tuning the commitment streak to 2 observations (threshold 0.78), Task B latent cold-start reaches 8.6 exact matches. Critically, A→B transfer under latent mode (7.0 exact) slightly exceeds visible mode (6.2 exact). The mechanism is architectural: latent carryover accumulates action supports that are not bound to a specific context label, so they cannot inject poison into Task B's different context-transform mapping. Latent inference is slower to commit but produces transfer-safe substrate by construction.

**Sequential transfer without catastrophic forgetting.** The A→B→C chain reaches 7.6 exact matches on Task C, equal to a direct A→C skip but via complementary mechanisms. Chain transfer deeply reinforces the correct context_1 transform (delta +0.463); direct skip provides a correct prior for context_0 (+0.14). Neither path erases prior structure: the substrate specializes rather than overwrites.

**Sample efficiency.** An online neural baseline comparison (same 18-example CVT-1 sequence, predict-then-update training) shows that the best neural analogue — an Elman RNN with latent context — requires approximately 144–162 examples to reach the criterion that REAL achieves in a single 18-packet session (8–9× more data). A stateless latent MLP fails to reach criterion at all.

### 5.2 Morphogenesis: Difficulty-Correlated Topology Growth

On the large topology (10 nodes, 36-packet sessions), morphogenesis produces markedly different outcomes depending on the task's baseline performance:

| Task | Baseline (fixed) | With morphogenesis | Delta |
|------|------------------|--------------------|-------|
| Task A (high baseline: 14.8/36) | 14.8 | 13.2 | −1.6 |
| Task B (low baseline: 11.8/36) | 11.8 | 19.2 | **+7.4** |
| Task C (moderate baseline: 17.0/36) | 17.0 | 16.0 | −1.0 |

Tasks with already-high performance lose ground under morphogenesis; the task with the lowest baseline gains most. This is not a tuning failure. It is the ATP surplus gate working correctly: high-performing tasks consume budget efficiently, leaving little surplus to trigger growth. Low-performing tasks fail more, spending ATP on misrouted packets and creating the surplus window that enables budding. New nodes then provide routing capacity precisely where the network was metabolically stressed.

Earned growth rate (cases where morphogenesis produced a genuine benefit) improved from 20% on the 6-node topology to 100% on the 10-node topology under task-carrying conditions. This reveals a minimum topology complexity threshold for productive morphogenesis: below it, the edge space is too constrained for new nodes to find productive specializations before the session ends.

### 5.3 Occupancy: Real-World Generalization

The occupancy experiment applies REAL to a 14-day room occupancy dataset: five environmental sensors (CO2, temperature, humidity, light, humidity ratio) sampled at 15-minute intervals predict whether a room is occupied. This is an external real-world dataset that the system was not designed for.

After the V1 failure diagnosis described in Case 5 above, the V2 harness achieved 0.766 F1 using only 500 training episodes (37% of the full training split), with a delivery ratio of 0.977 using a CO2-derived context proxy.

The V3 harness redesigned the evaluation frame to match how REAL natively operates: sessions (maximal contiguous runs of same-label episodes) as first-class units, online multi-sensor context encoding (CO2 and light combined into a 4-code context space), full multi-hop routing topology, and explicit fresh-session vs. persistent evaluation protocols.

V3 results across 3 seeds:

| Condition | Accuracy | F1 | Delivery ratio |
|-----------|----------|----|----------------|
| MLP baseline (full training data) | 0.985 | 0.963 | — |
| REAL V3 warm (persistent eval) | 0.973 | **0.952** | 0.969 |
| REAL V3 cold (fresh-session eval) | 0.968 | 0.919 | 0.977 |
| REAL V3 efficiency ratio (cold/warm delivery) | — | — | **0.9915** |

The warm F1 of 0.952 closes the gap with the MLP to 0.011 — down from 0.197 in V2. The remaining gap is a recall difference on the minority (occupied) class, attributable to the absence of class-weighted feedback; precision is near-identical (~0.98). The MLP optimizes a global classification loss on labeled examples; REAL infers occupancy indirectly through context-indexed routing under local metabolic pressure, with no access to the global dataset distribution.

The efficiency ratio of 0.9915 means that a fresh system loaded with the trained substrate performs nearly as well as the continuously running system — from the first session, with no warm-up. This confirms that the substrate is the actual knowledge carrier: what transfers is not runtime state or episodic memory, but the durable pattern of edge supports and context-indexed action supports accumulated during training.

---

## 6. Discussion

### 6.1 What These Results Mean Together

Taken individually, any one of these results could be explained away. Near-MLP performance on occupancy might be attributed to dataset simplicity. Good transfer efficiency might be specific to the CVT-1 task structure. Difficulty-correlated morphogenesis might be a coincidental consequence of the ATP threshold.

What is harder to dismiss is the consistency of the underlying mechanism across all experimental programs. In every case, the system's behavior is explained at the local level by the same dynamics: metabolic pressure shapes substrate, substrate biases future selection, context-indexed support accumulates separately and transfers independently. These dynamics were not specifically tuned for any of the experimental outcomes. They are the consequences of building a network out of local allostatic agents.

The interpretability story is similarly consistent. The development workflow documented in Section 4.2 worked because the architecture made it possible. You cannot run a node probe on a transformer and read "node N3 is committing to transforms before context is ready" — because a transformer does not have nodes making choices, and "context readiness" is not a local state that can be inspected. REAL's development methodology is inseparable from its architecture.

### 6.2 What REAL Is Not Claiming

REAL is not claiming to replace gradient-based deep learning for large-scale supervised learning tasks. The occupancy benchmark involves a few hundred training episodes; the CVT-1 benchmark involves 18-packet sessions. The sample-efficiency advantage at small scale may not hold at larger scales. REAL is also not claiming that its interpretability is fully mature: as documented in `INTERPRETABILITY.md`, the probing tools are currently standalone scripts rather than a unified interface, and some failure modes remain harder to trace than others.

What REAL is claiming is more specific: that the biological principles it operationalizes — allostasis, stigmergy, metabolic constraint, local agency — are sufficient to produce competent and interpretable behavior at non-trivial task scales, and that the interpretability is architectural rather than retrofitted.

### 6.3 Limits and Open Questions

Several architectural limits are currently confirmed:

- Morphogenesis in task-free routing scenarios does not activate, because the growth seeding mechanism requires task and context metadata. Load-based growth would require a separate observation signal (e.g., admission velocity).
- Prediction's influence on routing is currently weak: the mechanism is structurally present and locally observable, but its contribution to transfer benchmarks is marginal in the tested session lengths. Whether longer sessions would amplify prediction's role is an open question.
- The occupancy eval gap on the minority class recall suggests that the absence of class-weighted feedback is limiting. A feedback signal that differentially rewards correct minority-class routing would likely close this gap.

Open experimental questions include: cyclic transfer (A→B→C→A) and whether substrate can maintain coherence across a full cycle; whether latent sequential transfer avoids the context poison that visible sequential transfer introduces; and whether the recognition and prediction loop can be strengthened to produce larger transfer improvements.

---

## 7. Related Work

_[To be expanded — sketch only]_

**Biologically-plausible learning.** REAL connects to the broader program of learning rules that do not require global credit assignment: local Hebbian rules [citations], predictive coding [citations], contrastive Hebbian learning [citations]. REAL differs in that it is not attempting to approximate backprop with a local rule — it is proposing a different functional objective (allostatic coherence rather than loss minimization).

**Stigmergy and swarm learning.** The substrate-as-memory architecture has structural parallels with ant colony optimization [citations] and stigmergic multi-agent systems [citations], but where those systems typically solve combinatorial optimization problems, REAL is oriented toward generalization and transfer.

**Interpretable machine learning.** Post-hoc interpretability methods [SHAP, LIME, integrated gradients — citations] approximate explanations of opaque models. Transparent-by-design approaches [decision trees, rule-based systems — citations] sacrifice expressivity for legibility. REAL occupies a different position: expressive enough to reach near-MLP performance, interpretable by architectural construction.

**Reservoir computing and liquid state machines.** These approaches also use fixed or slowly-adapting substrate structures for computation [citations]. They differ in that the substrate is random and fixed, not learned through metabolic feedback; transfer between tasks is not a design objective; and interpretability is no better than standard neural networks.

---

## 8. Conclusion

REAL Neural Substrate demonstrates that a network of local allostatic agents, operating without global gradient descent, can acquire cross-task transfer, latent context inference, difficulty-correlated topology growth, and near-MLP performance on a real-world classification task. The architecture grounds each of these capabilities in biological principles — metabolic constraint, stigmergic substrate, and local coherence evaluation — rather than in task-specific design.

We have identified and distinguished two roles that native interpretability plays in this system. As a structural capability, REAL's architecture makes local decisions, memory structures, and metabolic state directly readable without post-hoc approximation — a consequence of building computation from agents with explicit local state rather than from global function composition. As a development workflow, this readability was the primary tool by which failure modes were diagnosed across five documented cases, each producing a targeted architectural improvement that aggregate metrics alone could not have motivated.

The interpretability is not a feature. It is what the architecture makes possible.

---

## Acknowledgements

_[placeholder]_

## References

_[placeholder — to be populated with appropriate citations for ALife, predictive coding, stigmergy, biologically-plausible learning, and interpretable ML literature]_

---

_Notes for revision:_
- _Abstract needs tightening once we know the exact page target (3 pages vs 8)_
- _Related Work section needs full citations — this is a scaffold_
- _Consider adding one figure: the REAL loop diagram, or a node probe trace excerpt as a concrete illustration of the interpretability workflow_
- _The distinction between "capability" and "workflow" interpretability is the conceptual contribution of this paper — make sure it is foregrounded in the introduction and echoed in the conclusion_
- _Confirm whether to include Phase 2 (Raspberry Pi / hardware-embedded agent) as a "Prior Work / Development History" subsection, or leave it for a future extended paper_
