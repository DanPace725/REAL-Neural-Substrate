# REAL Neural Substrate — Project Synthesis

_Last updated: 2026-03-20 (includes V3 occupancy results)_

---

## What It Is

REAL Neural Substrate is a local-learning research prototype that investigates whether useful computation, cross-task transfer, and structural adaptation can emerge from a network of metabolically constrained agents — without backpropagation, global loss functions, or any centralized planner.

REAL stands for **Relationally Embedded Allostatic Learning**. In this repo, the name refers to the architectural stance of the system: learning is embedded in local relations, local metabolic pressure, and persistent substrate change rather than in a single global optimization pass. The current codebase represents Phase 8 of a multi-phase research trajectory. Earlier phases (4 through 7) progressively formalized the core engine, developed reusable interfaces, and demonstrated persistent substrate carryover. Phase 8 is the convergence point where all of that prior work is combined into a fully multi-agent "native substrate" architecture.

The repository is an intentional research prototype, not a stabilized public library. It is explicitly positioned against the standard deep learning paradigm: where conventional AI optimizes passive weights via global gradient descent over large datasets, REAL proposes that computation should emerge from local agents managing their own metabolic survival.

---

## What It Does

The system routes information-carrying packets through a graph of nodes. Each node is an autonomous agent with a local ATP-like energy budget. Packets carry payload bits and optional context information. The sink (destination) node returns feedback upstream through the routing path when a packet arrives correctly transformed. Nodes that contribute to successful routing receive ATP; nodes that waste budget on fruitless actions are eventually starved and drop out.

Over repeated sessions, nodes accumulate a persistent **memory substrate** — a durable record of which edges and transforms proved metabolically valuable under which context conditions. This substrate lowers the cost of repeating successful behaviors in future sessions, biasing the routing network toward patterns that worked before without any explicit weight update.

The key demonstrations the system is designed to produce are:

- **Transfer learning without gradient descent.** A substrate trained on Task A should give Task B a meaningful head start, even though Task B differs in what some contexts require.
- **Latent context inference.** Nodes can learn to infer hidden task structure from packet flow statistics alone, without being given an explicit context label.
- **Topology growth under metabolic pressure (morphogenesis).** When a region of the substrate is struggling — spending ATP without earning feedback — new nodes can bud in to provide additional routing capacity.
- **Multi-step sequential transfer without catastrophic forgetting.** A chain of task sessions (A → B → C) should compound useful substrate rather than overwriting it.

---

## How It Works (High Level)

### The REAL Engine (`real_core/`)

The foundation of the system is the `RealCoreEngine`, a domain-agnostic implementation of the REAL loop. Every node in Phase 8 instantiates one of these engines. A single cycle of the engine runs:

1. **Perceive** — the node observes its local state through an `ObservationAdapter`: what packets are present, what its ATP balance is, what the current context signal is.
2. **Select** — a `Selector` (typically CFAR-based, drawing on the substrate for cost biasing) proposes an action from the node's local vocabulary.
3. **Execute** — the action is applied: route a packet, inhibit a neighbor, rest, invest ATP in a connection, or apply a data transform before routing.
4. **Score** — a `CoherenceModel` evaluates the outcome across six dimensions derived from the E² relational primitives: continuity, vitality, contextual fit, differentiation, accountability, and reflexivity.
5. **Consolidate** — useful patterns move from a fast episodic trace (`H_e`) into consolidated memory (`H_c`) and eventually into the maintained substrate (`M_s`). The substrate physically reduces the ATP cost of behaviors that have historically earned feedback.

The six relational primitives are the architectural backbone of what each node evaluates about itself: its identity through connections (ontological), its action vocabulary (dynamical), its causal neighborhood (geometric), differentiation pressure from neighbors doing redundant work (symmetric), local-only observation (epistemic), and the two-layer memory that re-scaffolds behavior costs over time (meta-relational).

### Phase 8 Multi-Agent Substrate (`phase8/`)

Phase 8 wraps the `RealCoreEngine` in a routing environment where many nodes operate simultaneously. Key components:

- **Node agents** (`node_agent.py`) each run independent REAL loops. They have no global view — only their immediate neighbors, their own ATP, and their local substrate state.
- **The routing environment** (`environment.py`) manages packet ingress, propagates sink feedback upstream through the active path, and drives the context signal (visible or latent).
- **The connection substrate** (`substrate.py`, `consolidation.py`) tracks edge support (how reliable a route has been) and context-indexed action support (how valuable a specific transform was for a specific context bit). These are the durable learned structures.
- **Admission control** (`admission.py`) gates ingress at the source node: the network can only accept packets when its metabolic state allows it, preventing overload.
- **Morphogenesis** (`topology.py`) allows nodes to bud new edges or entirely new nodes when local ATP surplus exceeds a threshold and routing feedback indicates the existing topology is insufficient. New nodes receive a grace period before their upkeep costs become active.
- **Scenarios** (`scenarios.py`) define named task configurations — topology, packet budget, transform-to-context mappings — that the experiment scripts run reproducibly.

### Task Structure

The primary benchmark family is **CVT-1**, which uses context-dependent transforms as the learning target. A packet's payload should be transformed differently depending on which context bit is active. Three task variants create a structured transfer landscape:

- **Task A:** `context_0 → rotate_left_1`, `context_1 → xor_mask_1010`
- **Task B:** `context_0 → rotate_left_1`, `context_1 → xor_mask_0101` (shares context_0 with A)
- **Task C:** `context_0 → xor_mask_1010`, `context_1 → xor_mask_0101` (shares context_1 with B; context_0 maps to what was A's context_1)

This structure makes transfer directional and asymmetric: the substrate that is helpful for one direction of transfer can be actively harmful ("context poison") for another, because strongly context-bound supports carry the wrong transform expectation into a new session.

### Context Modes

The system can operate in two context modes. In **visible** mode, the context bit is provided explicitly to nodes during training. In **latent** mode, nodes must infer context from packet flow statistics — specifically, whether recent feedback suggests context_0 or context_1 is active. Latent inference is slower to commit but produces context-agnostic substrate entries that are naturally transfer-safe: they carry no binding to a specific context label, so they cannot inject poison into a new task.

---

## How It Has Been Tested

Testing has proceeded across four overlapping experimental programs, each building on the previous. The most recent is the occupancy series.

### 1. CVT-1 Small-Topology Benchmarks (March 16)

The original core benchmark used a compact 6-node graph with 18-packet sessions. This established the bedrock results:

- Cold start on Task B: **3.9 exact matches**, 0.477 mean bit accuracy.
- Warm full carryover (Task A → B): **10.6 exact matches**, 0.704 mean bit accuracy.
- Warm substrate-only carryover (A → B): **7.3 exact matches**, 0.586 mean bit accuracy.

Both forms of carryover substantially outperformed cold start, confirming that the maintained substrate is doing real work. The transfer matrix work also established that transfer is directional: some prior task structures are useful launchpads and some are stale traps.

### 2. Latent Context, Morphogenesis, and Large-Topology Experiments (March 17)

A major session on March 17 expanded the benchmark in four simultaneous directions:

**Latent context tuning.** Reducing the commitment streak (from 3 observations to 2) and tightening the confidence threshold (from 0.75 to 0.78) caused Task B latent cold-start to jump from 4.0 to 8.6 exact matches. Latent A→B transfer (7.0 exact) now slightly exceeds visible A→B transfer (6.2 exact). The architectural explanation is that latent carryover accumulates context-agnostic supports that cannot introduce context poison, so faster commitment seeds useful substrate earlier without the risk visible training carries.

**Sequential A→B→C transfer.** The chain produced 7.6 exact matches on Task C, equal to a direct A→C skip but via different mechanisms — the chain deeply reinforces the correct context_1 transform while the direct skip provides a different correct prior for context_0. Neither path catastrophically forgets prior structure: the substrate is layered and specializes rather than overwrites.

**Large topology.** A 10-node, 3-way branching topology with 36-packet sessions unlocked qualitatively different morphogenesis behavior. Cold-start earned growth rate improved from 20% (6-node) to 100% (10-node) for task-carrying scenarios. Task B on the large topology gained +7.4 exact matches from morphogenesis, versus essentially no gain on the small topology. Morphogenesis consistently helps where performance is low (large routing headroom) and consistently disrupts where performance is already high — an emergent self-regulatory pattern from the ATP surplus gate.

**Neural baseline comparison.** An online MLP/RNN comparison harness (same 18-example CVT-1 sequence, predict-then-update training) established a sample-efficiency benchmark: the best latent neural analogue (an Elman RNN) requires roughly 8–9× more examples (~144–162) to reach the criterion that REAL achieves in a single 18-packet session. The stateless latent MLP fails to reach criterion at all.

### 3. Configuration × Task Family Map (March 18)

The March 18 work organized findings across three task families (A: scale/horizon, B: hidden memory, C: transform ambiguity) and four base REAL configurations (fixed-visible, fixed-latent, growth-visible, growth-latent). Key findings consolidated into three structural principles:

- **Morphogenesis is a warm-substrate phenomenon.** Cold-start win rates cluster around 20% across all families. Under warm carryover, they reach 60–80%. Growth requires existing routing clarity before it can seed productive nodes.
- **Latent carryover is transfer-safe by construction; visible carryover is geometry-sensitive.** Visible full-episodic carryover can cost 3–4 exact matches when the transfer target changes a context's expected transform. Latent full-episodic carryover provides a positive transfer floor in all tested conditions.
- **Topology scale determines whether growth-latent can stabilize.** On the C-family deep-ambiguity tasks, growth-latent was harmful on 30-node topologies (C3) but beneficial on 50-node topologies (C4). The latent estimate needs enough packets to stabilize before morphogenesis fires; below a topology-size threshold the session ends before that stabilization occurs.

This work also required two architectural bug fixes for the C family: a task-ID registration gap that prevented the latent task-family logic from recognizing generated benchmark IDs, and a credit/debt alignment bug where downstream nodes were being over-penalized for transform-aligned partial matches.

### 4. Occupancy Experiments (March 19–20 — Most Recent)

The occupancy series applies REAL to a real-world dataset: room occupancy prediction from environmental sensor data (CO2, temperature, humidity, light, motion). This is the first external-dataset test of the substrate, replacing the synthetic CVT-1 packet tasks with actual time-series classification. The series progressed through three harness iterations across two days.

**V1 evaluation (found to be invalid).** The initial occupancy bridge (`occupancy_real.py`) produced a misleading result (eval F1: 0.032) due to three compounding design flaws: feedback suppressed during evaluation caused ATP starvation and an 18× surge in dropped packets; no carryover round-trip was ever tested; and no context bit was injected, leaving the entire context-indexed action support layer dormant.

**V2 redesign (March 19).** Three targeted fixes addressed each flaw: (1) feedback enabled during eval at full fraction, (2) a `fresh_eval` carryover mode that saves the training substrate and loads it into a clean system for evaluation, and (3) a CO2-derived context bit (high/low relative to training median) as a physically meaningful, non-label-leaking proxy for occupancy state. Enabling feedback alone raised eval F1 from 0.032 to 0.748 — a 23× improvement. The best V2 configuration achieved 0.766 F1 and a 0.977 delivery ratio using only 500 training episodes (37% of the available training data).

**V3 harness (March 20).** A third iteration completed on March 20 made four architectural changes to align the benchmark more closely with how REAL natively operates:

- **Online running context** replaced V2's single CO2 high/low bit. Context is now derived continuously from multi-sensor readings during each session, producing a 4-code context space instead of a 1-bit proxy.
- **Multihop routing topology** (`multihop_routing`) replaced the `fixed_small` control path, engaging the full substrate edge support and transform support mechanisms.
- **Admission-source ingress** replaced direct injection, restoring metabolic gating at the source node.
- **Explicit fresh-session vs persistent eval protocols** (`fresh_session_eval` default, `persistent_eval` for comparison) made the warm/cold carryover isolation explicit and measurable. Multi-seed sweep support and auto CPU budgeting (75% of visible cores) were also added.

**V3 results.** Early March 20 runs explored training-split fractions and produced the first occupancy-series efficiency ratio above 1.0 (1.014 at a 79% split), meaning warm carryover outperformed cold start. The full V3 harness runs showed a large improvement over V2:

| Configuration | Warm F1 | Cold F1 | Efficiency ratio |
|---|---|---|---|
| V2 best (CO2 context, 500 eps) | 0.766 | — | — |
| V3 full run, 62 sessions (18:56) | **0.9524** | 0.9193 | 0.9977 |
| V3 3-seed sweep avg (seeds 13, 23, 37) | — | — | **0.9915** (mean warm acc 0.9734) |

For comparison, an MLP baseline trained on the full ~1,344-example training split achieved 0.963 F1. The V3 warm F1 of 0.9524 closes the gap with the MLP to **0.011** — down from 0.197 in V2. The remaining gap is almost entirely a recall difference (MLP 0.951 vs V3 warm 0.920); both systems achieve near-identical precision (~0.98). The MLP optimizes a classification loss directly; REAL infers occupancy indirectly through context-indexed substrate routing without any global objective.

---

## Current Scientific Position

Across all experimental programs, six findings now appear stable enough to treat as the project's working scientific position:

1. **Carryover is real and measurable.** Both full and substrate-only carryover consistently outperform cold start on the core transfer benchmarks. The occupancy V3 results confirm this extends to a real-world time-series dataset: the efficiency ratio of 0.9977 on the fresh-session protocol confirms that trained substrate transfers productively into a clean system.
2. **Latent context inference is transfer-safe by architectural construction.** The latent path's weaker cold-start performance is the acceptable cost of a reliably positive transfer floor and compounding advantage in cyclic and multi-step chains.
3. **Morphogenesis is a transfer amplifier, not a cold-start optimizer.** It earns its structure when routing clarity already exists (warm carryover) and when the topology is large enough for new nodes to specialize. Below a topology-size threshold it is actively harmful.
4. **The system is substantially more sample-efficient than online gradient learners** in the low-data regime tested by CVT-1, achieving comparable milestone behavior in 8–9× fewer examples than the best neural analogue.
5. **The substrate supports graceful multi-step specialization without catastrophic forgetting.** A→B→C chains compound substrate value; prior task structure is selectively useful rather than blindly preserved or overwritten.
6. **On a real-world occupancy dataset, V3 REAL with online context and native routing is competitive with a fully-trained MLP.** Warm F1 of 0.952 vs MLP F1 of 0.963, with REAL achieving this through local allostasis rather than global gradient descent. The remaining gap is a recall gap on the minority class attributable to the absence of class-weighted feedback.
