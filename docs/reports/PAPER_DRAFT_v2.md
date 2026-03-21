# Allostatic Neural Substrate: Emergent Competence and Native Interpretability Through Metabolically Constrained Local Agents

_Draft v2 — ALIFE 2026 submission target_

---

## Abstract

We present REAL Neural Substrate, a learning architecture in which each network node is an autonomous agent operating under a metabolic energy budget rather than a passive unit updated by global gradient descent. Persistent routing substrate accumulates through allostatic self-regulation and stigmergic substrate writing, producing cross-task transfer, latent context inference, and difficulty-correlated topology growth as emergent properties rather than engineered objectives. On a real-world room occupancy dataset, the system reaches F1 of 0.952 (warm carryover) against an MLP baseline of 0.963, with substrate that transfers to a fresh system at 99.15% efficiency — confirming that the routing substrate, not runtime state, is the actual knowledge carrier.

We identify and distinguish two roles that native interpretability plays in this architecture: interpretability as structural **capability** — local decisions, memory structures, and metabolic states are directly readable because they are explicit properties of local agents, not distributed consequences of a global optimization — and interpretability as **development workflow** — this readability was the primary tool by which failure modes were diagnosed and architectural changes were motivated across the system's development. We argue that building this system, rather than formalizing it, revealed several things about learning and agency that prior theory did not anticipate.

---

## 1. Introduction

The dominant paradigm in machine learning optimizes a global loss function by propagating error gradients through every parameter simultaneously. This works, and works well at scale, but it carries two structural costs that are rarely foregrounded. The first is opacity: because behavior is a distributed consequence of the entire weight tensor shaped by a non-local process, there is no local explanation for why any particular decision was made. The second is the evaluation frame: when a gradient-trained system fails, the failure appears in aggregate output, and the path from observed failure to architectural insight runs through external probe methods that approximate explanations rather than read them.

Biological learning systems are organized differently. Neurons maintain local energy budgets; synaptic change is local and conditional; learning accumulates in substrate structure that persists beyond any episode. Allostasis — regulation toward viable internal operating ranges — is the primary organizing principle, not loss minimization. And crucially, the substrate encoding a biological system's history is in principle readable: its state at any moment reflects the causal record of the organism's experience.

REAL (Relationally Embedded Allostatic Learning) Neural Substrate takes these principles as architectural constraints rather than metaphors. Each node in the network is a local allostatic agent: it observes only its immediate neighborhood, selects actions from an explicit vocabulary under metabolic pressure, evaluates its own behavior across six relational coherence dimensions, and consolidates useful patterns into a persistent substrate that physically reduces the future cost of behaviors that have earned feedback. No node has a global view. No global gradient is computed.

This paper makes three connected claims. First: a network of such agents, without any global objective, develops cross-task transfer, latent context inference, difficulty-correlated topology growth, and near-MLP performance on a real-world dataset it was not designed for. Second: the architecture is natively interpretable — not because of added observability tooling, but because the structural organization that makes behavior possible also makes it readable. Third: this interpretability was not incidental; it was the primary development methodology. We present both the architecture and the five-week experimental record as a case study in what building a biologically-grounded learning system can reveal that formalizing it alone could not.

---

## 2. Architecture

### 2.1 The REAL Node

Each node in REAL Neural Substrate runs an independent local loop: perceive its immediate neighborhood, select an action from an explicit vocabulary, execute, evaluate the outcome, and consolidate. The key architectural properties are three.

**Observation is strictly local.** A node sees its own ATP balance, the packets currently present, the current context signal, and the substrate-key indices of its own prior routing history. It has no access to any other node's state, the global packet count, or the loss on any global objective.

**Selection is substrate-biased.** The base ATP cost of action $a$ under context $k$ is discounted by accumulated substrate support:

$$c_t(a \mid k) = c_0(a) \cdot \bigl(1 - \alpha \cdot M_s(a, k)\bigr)$$

where $c_0(a)$ is the base cost, $M_s(a, k) \in [0, 1]$ is the substrate support for action $a$ under context $k$, and $\alpha$ is the discount rate. Actions that have historically earned feedback cost less to repeat. This is allostasis in the literal sense: the system biases itself toward what has supported its own viability.

**Consolidation is explicit and inspectable.** Useful patterns migrate from a fast episodic trace through a consolidated memory layer into the maintained substrate $M_s$. The substrate is not a weight matrix — it is a set of named entries that can be enumerated, compared across sessions, and selectively included or excluded. A node's learning history is readable as structure, not inferred from parameter values.

### 2.2 Coherence Evaluation

Rather than measuring performance against an external loss, each node scores its own cycle outcome across six relational dimensions derived from the E² primitive framework:

$$\Phi = \sum_{i=1}^{6} w_i \cdot \phi_i$$

The six dimensions are: _continuity_ (identity persistence through action sequences), _vitality_ (productive energy expenditure, penalizing both idle and exhausted states), _contextual fit_ (alignment between action and current context signal), _differentiation_ (contrast with neighboring nodes, penalizing redundancy), _accountability_ (coherence between stated action intent and observed outcome), and _reflexivity_ (behavioral revision following coherence dips). Together these constitute an endogenous evaluation: the node asks "am I maintaining coherent operation?" rather than "did an external observer approve my output?"

### 2.3 Phase 8: A Multi-Agent Routing Substrate

In Phase 8, many REAL nodes operate simultaneously in a routing graph. Packets enter at a source, must reach a sink with a context-dependent payload transform applied, and the sink returns feedback upstream through the successful routing path. Nodes on the path earn ATP; nodes that waste budget on fruitless actions are eventually starved.

The durable learned structure is the substrate: edge supports (how reliable each outgoing route has been) and context-indexed action supports (how valuable a specific transform action has been under each context bit). Both persist across sessions and are the basis of carryover experiments.

Two context modes exist. In _visible_ mode, the context bit is given to nodes directly. In _latent_ mode, nodes must infer context from packet flow statistics without an explicit label. Latent inference is slower to commit but accumulates substrate entries that are not bound to a specific context label — making them transfer-safe by construction, since they carry no expectation that could conflict with a new task's context-transform mapping.

When a node accumulates ATP surplus while failing to route productively, it can bud a new node or edge. The surplus gate means growth fires when the node is metabolically stressed — exactly where additional routing capacity is needed. Difficulty-correlated topology growth is a consequence of this gate, not a separately designed objective.

---

## 3. Interpretability

### 3.1 As Structural Capability

REAL is natively interpretable because computation is organized as local agents making explicit choices rather than as global function composition. This distinction has three concrete consequences.

**Selection is readable as a term-by-term comparison.** The selector exposes the contributing scores for each candidate action: substrate support weight, coherence history bias, recognition confidence, and ATP cost, each as a named value. A routing decision is not a matrix multiply — it is a record of what evidence supported what action.

**Memory is inspectable as structure.** What a node has learned is encoded in specific, named substrate entries. The question "does Task A's substrate help or hurt Task B?" is answerable directly by reading which context-indexed action supports carry over and whether they match or conflict with Task B's transform requirements. This is categorically different from inspecting weight norms.

**Counterfactuals are mechanistically meaningful.** Many experiments are designed as mechanism toggles: recognition enabled vs. disabled, fresh-session vs. persistent evaluation, full vs. substrate-only carryover, visible vs. latent context mode. These isolate specific causal contributions. In a weight-matrix system, disabling "recognition" would require architectural surgery that changes the function computed; here, toggling a mechanism holds everything else constant while asking what that one component contributes.

A further property is that null results are diagnostically informative. When a mechanism produces no improvement in aggregate metrics, local observability allows a more precise question: was the mechanism absent? Present but too late? Present but competing with a stronger term and losing? This precision prevents the false conclusion that a mechanism is useless because accuracy didn't move.

### 3.2 As Development Workflow

The structural capability described above was not primarily used after the fact to explain completed behavior. It was the primary engineering methodology throughout development: inspect local state → identify the specific mechanism producing a failure → change that mechanism → verify. We document three cases.

**Case 1: Downstream transform commitment under latent uncertainty.** One task variant underperformed a closely related variant despite identical behavior at the first latent node. A per-node probe revealed that a downstream node was repeatedly selecting transform-specific routes while latent context confidence was well below the promotion threshold — in one representative trace, choosing a hard transform at cycles where confidence was 0.289, then 0.477, then 0.609, none of which crossed the 0.78 threshold. The diagnosis was specific: the node had a packet and a task but was committing to transforms before it had sufficient contextual evidence. The intervention was targeted: a downstream action gate that suppresses non-identity transform choices while latent context is available but unpromoted. Task performance improved sharply in subsequent benchmarks. The workflow produced a specific mechanistic claim, a minimal surgical fix, and a verifiable result — none of which were accessible from aggregate accuracy alone.

**Case 2: Recognition absent, then present, then blunt.** An early probe showed zero recognized route entries during warm transfer. Rather than concluding recognition was ineffective, the local trace was inspected: route patterns were consolidated in substrate key space, but transfer-time observations did not expose those same keys, so the recognizer had no aligned coordinate system to compare against. After aligning the observation adapter to expose substrate-key indices, recognized route entry count moved from zero to five — recognition was now genuinely active, though sparse. A subsequent selector interaction probe then showed that sparse recognition was occasionally winning close routing decisions, but tipping them toward stale carried route families. The conclusion was not "disable recognition" but "recognition needs freshness discounting." Three distinct diagnostic conclusions — absent, present but unaligned, present but blunt — emerged from a sequence of local observations, each narrowing the question rather than collapsing it to a binary pass/fail.

**Case 3: Occupancy V1 failure diagnosed at the mechanism level.** The initial occupancy evaluation produced an eval F1 of 0.032. The harness was inspected node-by-node rather than treated as evidence of architectural incapacity. Three compounding failure modes were found: feedback was suppressed during evaluation, causing ATP to collapse as nodes spent their budgets without replenishment — dropped packets surged from under 1 per episode during training to over 17 per episode during evaluation; no carryover round-trip was ever measured; and the context-indexed support layer was dormant because no context signal was injected. Addressing the first flaw alone — enabling feedback during evaluation — raised eval F1 from 0.032 to 0.748, a 23× improvement. This established that the failure was entirely in the evaluation harness, not in the system's representational capacity.

---

## 4. Results

### 4.1 CVT-1 Benchmark: Transfer, Latency, and Sample Efficiency

The primary controlled benchmark uses context-dependent routing tasks (CVT-1). Three task variants (A, B, C) form a structured transfer landscape where some prior substrate is a useful prior and some is a context poison.

| Condition | Exact matches | Bit accuracy |
|---|---|---|
| Task B cold start | 3.9 | 0.477 |
| A→B substrate-only carryover | 7.3 | 0.586 |
| A→B full episodic carryover | 10.6 | 0.704 |
| A→B latent carryover (tuned) | 7.0 | — |
| A→B visible carryover | 6.2 | — |

Both forms of carryover substantially outperform cold start. After tuning latent commitment parameters, latent A→B transfer (7.0 exact) slightly exceeds visible (6.2 exact) — the mechanism being that latent substrate entries carry no context binding and therefore cannot introduce context poison into the new task's different transform mapping.

Sequential A→B→C transfer reaches 7.6 exact matches on Task C, equal to a direct A→C skip but via different substrate mechanisms. Neither path overwrites prior structure: the substrate specializes through layered accumulation.

A neural baseline comparison (same 18-example session, predict-then-update) shows the Elman RNN requires approximately 144–162 examples to reach the criterion REAL achieves in a single 18-packet session — an 8–9× sample efficiency advantage in the low-data regime.

### 4.2 Morphogenesis: Emergent Difficulty-Correlated Growth

On the large topology (10 nodes, 36-packet sessions), morphogenesis produces outcomes that differ systematically by baseline task performance:

| Task | Baseline (fixed topology) | With morphogenesis | Delta |
|---|---|---|---|
| Task A (high baseline) | 14.8 / 36 | 13.2 | −1.6 |
| Task B (low baseline) | 11.8 / 36 | 19.2 | **+7.4** |
| Task C (moderate baseline) | 17.0 / 36 | 16.0 | −1.0 |

The pattern — growth helps where performance is lowest and disrupts where it is already high — is not designed. It is the ATP surplus gate operating correctly: high-performing tasks consume budget efficiently, leaving little surplus to trigger growth; struggling tasks fail more, spending ATP on misrouted packets and opening the surplus window that enables budding. Earned growth rate (cases where morphogenesis produced a genuine benefit) improved from 20% on the 6-node topology to 100% on the 10-node topology under task-carrying conditions, revealing a minimum topology complexity threshold below which new nodes cannot find productive specializations before the session ends.

### 4.3 Occupancy: Real-World Generalization

The occupancy series applies REAL to a 14-day room occupancy dataset (CO2, temperature, humidity, light, humidity ratio at 15-minute intervals predicting room occupancy). The system was not designed for this task; it was the first external-dataset test.

Following the V1 harness diagnosis described in Section 3.2, the V3 harness redesigned the evaluation to match REAL's native operating mode: sessions as first-class units, online multi-sensor context encoding (CO2 and light combined into a 4-code context space), full multi-hop routing, and explicit fresh-session vs. persistent evaluation protocols. Results across 3 seeds:

| Condition | Accuracy | F1 | Delivery ratio |
|---|---|---|---|
| MLP baseline (full training data, 1,344 examples) | 0.985 | 0.963 | — |
| REAL V3 warm (persistent eval, 926 training sessions) | 0.973 | **0.952** | 0.969 |
| REAL V3 cold (fresh-session eval, loaded substrate) | 0.968 | 0.919 | 0.977 |
| Carryover efficiency ratio (cold delivery / warm delivery) | — | — | **0.9915** |

Warm F1 of 0.952 closes the gap to the MLP to 0.011. The remaining difference is a recall gap on the minority class, attributable to the absence of class-weighted feedback in the current implementation. Both systems achieve near-identical precision (~0.98). The efficiency ratio of 0.9915 — cold-start substrate performing at 99.15% of continuous-system delivery, from the first session, without warm-up — confirms that the routing substrate is the actual knowledge carrier. What transfers is not runtime ATP state or episodic memory, but the durable record of which routing patterns earned feedback under which context conditions.

---

## 5. Discussion

### 5.1 What Building the System Revealed

Several findings emerged from operating REAL that prior formalization did not anticipate, and that the ALIFE framing of artificial life as experimental philosophy makes explicit.

The most significant is that the right evaluation frame for a system like this is not immediately obvious and cannot be derived from the theory. The occupancy V1 result — 0.032 eval F1 — looked like a system failure. But the node-level traces showed a harness failure: the evaluation was actively starving the network by suppressing the feedback that nodes require to maintain their ATP. Correcting for this alone raised F1 twenty-threefold. What appeared to be a measurement of the system's capacity was actually a measurement of how the system responds to metabolic starvation — a different and more interesting result. The system did exactly what an allostatic system should do when deprived of feedback: it conserved remaining budget and stopped routing. This was not incorrect behavior; it was the architecture working as designed in conditions the harness had not anticipated.

A second discovery concerns the substrate efficiency ratio. The original research question was "how does REAL compare to an MLP on classification accuracy?" V3's result — that a fresh system loaded with trained substrate performs within 0.85% of a continuous system from the very first session — suggests the more fundamental question is about the portability of learned structure. The routing substrate is not a snapshot of runtime state; it is a compressed record of which routing patterns have earned feedback, indexed by context, that can be transferred into a new system like a learned reflex rather than like a weight matrix. This property was not predicted by the theory; it emerged from measuring the right thing.

A third discovery is the difficulty-correlated morphogenesis pattern. The ATP surplus gate was designed to prevent runaway growth; it was not designed to produce growth that concentrates where performance is worst. That pattern emerged from the interaction between the gate and the metabolic dynamics of high-performing vs. low-performing tasks. The system self-allocates structural resources in a way that tracks its own deficits, without being told to.

These three discoveries share a structure: they were all accessible only through operating the system and reading its local state. None of them appear in the formal specification of REAL. This is the experimental philosophy claim: the system as a built artifact makes falsifiable claims that the formal system does not, and some of those claims turn out to be correct in ways that revise the theory.

### 5.2 On Interpretability

The distinction between interpretability as capability and interpretability as development workflow matters because they make different claims. The capability claim is structural: the architecture produces decisions that are readable because they are made by agents with explicit local state, not by global function composition. This is not a debugging convenience — it is a fundamental difference in what kind of object the computation is. When a REAL node selects an action, there is a node, there is a state it observed, there is a set of candidate actions with named scores, and there is a selected action. All of these are first-class objects that can be read, compared, and reasoned about.

The workflow claim is empirical: this readability was used. Across three documented cases, the development methodology was inspect → localize → change → verify, and each step in that chain was possible because of the structural capability. The workflow did not simply require "more logging" — it required that local state have the right kind of semantic structure to support mechanistic inference. A transformer with richer logging does not produce the claim "node N3 is committing to transforms before context is ready," because there is no node N3, there is no context readiness state, and there is no action vocabulary from which a commitment was made.

### 5.3 Limits

Several current limits are worth stating explicitly. Morphogenesis requires task and context metadata to seed productive growth; load-based growth in the absence of task structure remains outside the current design. Prediction's influence on routing decisions is currently observable but weak in the tested session lengths. The occupancy recall gap on the minority class would likely close with class-weighted feedback. And the sample-efficiency advantage at small scale has not been tested at the scales where gradient-based systems are dominant.

---

## 6. Related Work

**Biologically-plausible learning.** REAL connects to a long tradition of local learning rules that avoid global credit assignment — Hebbian learning, predictive coding [Rao & Ballard 1999], contrastive Hebbian learning [Movellan 1991], and more recently equilibrium propagation [Scellier & Bengio 2017]. REAL differs from this tradition in that it is not attempting to approximate backpropagation with a local rule, but to replace the optimization objective entirely with allostatic coherence.

**Stigmergy and distributed learning.** The substrate-as-memory architecture has structural parallels with ant colony optimization [Dorigo et al. 1996] and stigmergic multi-agent systems [Theraulaz & Bonabeau 1999]. REAL differs in orienting toward generalization and cross-task transfer rather than combinatorial optimization.

**Reservoir computing.** Liquid state machines and echo state networks also use substrate structure for computation [Maass et al. 2002, Jaeger 2001]. Their substrates are random or fixed, not learned through metabolic feedback; transfer is not a design objective; and local decisions are no more interpretable than in standard networks.

**Interpretable machine learning.** Post-hoc methods — SHAP [Lundberg & Lee 2017], LIME [Ribeiro et al. 2016], integrated gradients [Sundararajan et al. 2017] — approximate explanations of trained models through input perturbation or activation analysis. These are correlational by construction. REAL's interpretability is causal: the explanation of a routing decision is the decision record itself, not an approximation derived from perturbing the input space.

---

## 7. Conclusion

REAL Neural Substrate demonstrates that a network of local allostatic agents, without global gradient descent, can develop cross-task transfer, latent context inference, difficulty-correlated topology growth, and near-MLP performance on a real-world classification task. The biological principles it operationalizes — metabolic constraint, allostatic coherence, stigmergic substrate — are sufficient to produce competitive behavior without a global objective.

The system is natively interpretable in two distinct and separable senses. As a structural capability, REAL decisions are readable because they are made by agents with explicit local state; memory is inspectable because it is encoded in named substrate entries rather than distributed weight values; and counterfactual analysis is mechanistically meaningful because mechanisms can be toggled without redesigning the computation. As a development workflow, this readability enabled a methodology — inspect local state, localize the failure, change the mechanism, verify — that was productive across five development cases and would not have been available in a gradient-trained system.

The three experimental discoveries discussed in Section 5.1 — that the occupancy failure was a harness failure readable from metabolic traces; that substrate portability is the more fundamental capability than classification accuracy; that difficulty-correlated growth is an emergent property of the metabolic gate — were all accessible only through building and operating the system. They constitute the experimental-philosophy contribution: the built artifact makes claims that the formal specification does not, and some of those claims revise the theory in ways that advance it.

---

## References

_[To be populated — scaffolded citations present in text]_

---

_Notes for v3:_
- _Figures needed: (1) The REAL loop diagram with the six coherence dimensions labeled; (2) The carryover efficiency comparison (warm vs cold across seeds) as a simple bar chart or table visual; (3) Possibly a simplified node diagram showing local observability contrast with a standard neuron. These would allow the architecture section to shrink further._
- _Page estimate: approximately 5–6 pages at standard ALIFE formatting. Tables contribute ~0.5pp each; the architecture section is now the densest prose block and could shrink further with a figure._
- _Phase 2 / Raspberry Pi origin: remains omitted. Consider a single sentence in the introduction ("The system was initially developed on consumer hardware using real compute cycles as ATP, establishing the metabolic grounding as a physical constraint rather than a metaphor") to establish the origin without expanding the paper._
- _Special session framing: Section 5.1 is written toward "artificial life as experimental philosophy." If the submission is to the general track rather than the special session, this section can be repositioned as a discussion of emergent properties._
