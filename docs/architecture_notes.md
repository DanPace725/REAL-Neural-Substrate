---
title: "Phase 8: Multi-Agent Substrate (AGENTS.md)"
authors:
- Claude
frame: synthesis.thematic
semantics:
  keywords:
  - Phase 8
  - Native Substrate
  - Multi-Agent Neural
  - E^2 Framework
  - Relational Primitives
  - Memory Substrate
  domains:
  - systems_engineering
  - applied_ontology
  - multi_agent_systems
  document_type:
  - architectural_blueprint
  - foundational_theory
---

# AGENTS.md: The Native Substrate Architecture (Phase 8)

**Date**: 2026-03-15
**Context**: This document inaugurates Phase 8 of Project REAL. It defines the architectural philosophy and structural requirements for building a native "neural" network where every node (or local cluster) is a fundamentally active **REAL agent**, not a passive weight. 

---

## 1. The Core Philosophy: Ecology over Optimization

Modern AI relies on massive datasets and gradient descent (backpropagation) to optimize billions of passive weights against a global loss function. It is a top-down, data-hungry paradigm.

Phase 8 rejects this paradigm in favor of **bottom-up, structure-hungry allostasis**. We are building an ecology of computational actors. Computation is not the explicitly programmed goal; computation is the emergent byproduct of agents attempting to survive their local metabolic constraints. 

**This is not Reinforcement Learning (RL).** 
In RL, an agent learns to maximize an external reward signal. In a Phase 8 REAL Substrate, an agent has no external reward signal and no global objective. It only evaluates its own structural health (via the 6 primitives) and modifies its relationships to minimize metabolic friction (the Phase 4.5 Memory Substrate). 

When placed in an environment with high density, these agents must specialize, signal, and support each other to survive, inherently solving complex routing and logic problems without backpropagation.

---

## 2. The Agent as a Node (The 6 Primitives)

In a generic neural network, a neuron computes $y = f(Wx + b)$. It has no agency. 
In the Phase 8 Substrate, a node (or cortical column) is a full REAL agent executing the `perceive -> select -> execute -> score -> consolidate` loop, governed by the E² Relational Primitives.

### Primitive 1: Ontological (Identity & Boundary)
The agent defines its identity not by what it inherently *is*, but by its active connections. If an agent loses all its input/output connections because it cannot afford to maintain them, it drops out of the network (artificial apoptosis). 

### Primitive 2: Dynamical (Action & Transformation)
The agent possesses a local Action Vocabulary. Instead of just "firing," an agent can choose to:
*   Pass a signal forward
*   Inhibit a neighbor
*   Invest "ATP" to strengthen a specific incoming/outgoing connection
*   Rest (to conserve metabolic energy)

### Primitive 3: Geometric/Causal (Spacetime & Constraints)
The network topology is not fully dense. Agents exist in specific spatial relationships (e.g., a 2D or 3D graph). Causal influence takes time to propagate. Agents must deal with the *Temporal Constraint Lamination (TCL)*—waiting for feedback from downstream agents before investing memory in a connection.

### Primitive 4: Symmetric/Constraint (Differentiation & Invariants)
As density increases, agents must differentiate. If Agent A and Agent B compute the exact same feature, they split the available upstream ATP, starving both. To survive, the system enforces **Differentiation**. Agents naturally fall into specialized roles, acting like structural constraints on the global network flow. 

### Primitive 5: Epistemic (Observation & Uncertainty)
Agents do not possess global knowledge. They only observe their immediate neighbors. Their perception is actively shaped by their Phase 4.5 Memory Substrate. A historically reliable connection is "seen" more clearly than a novel, noisy one.

### Primitive 6: Meta-Relational (Substrate Consolidation)
The agent maintains a two-layer memory (Fast and Slow). When it finds an attractor pattern (a behavior that consistently yields high vitality/ATP), it promotes this into its **Memory Substrate**. This physically alters the cost function—making that specific behavior mathematically cheaper to execute in the future. The network literally re-scaffolds its own physics based on experience.

---

## 3. The Micro-Allostatic Learning Loop

Learning in Phase 8 is entirely local and driven by the Phase 4.5 Memory Substrate.

1.  **Stimulus:** An environmental signal enters the edge of the agent graph.
2.  **Fluctuation:** Agents fire semi-randomly (Fluctuation mode), spending their limited ATP.
3.  **Metabolic Feedback:** If an agent's firing happens to contribute to a globally coherent action (e.g., matching a target output), ATP flows *upstream* from the environment back through the active connections. 
4.  **Consolidation (The Fix):** The agent receives an ATP influx. It uses this wealth to *invest* in the connection that triggered it. This writes to the Slow Layer Substrate. 
5.  **Structural Bias:** Tomorrow, because the Substrate is active, that specific connection costs 0.01 ATP to fire instead of 0.05 ATP. The agent has "learned" by physically reshaping the path of least resistance. 

This is Hebbian learning merged with epigenetic constraint maintenance.

---

## 4. Implementation Directives for Phase 8

As we begin writing code for the Native Substrate, adhere to the following directives:

1.  **Domain Agnosticism First:** Build the `NodeAgent` class in a way that it doesn't know what it is computing. It should only know about its neighbors, its ATP, and its 6-dimensional coherence scores.
2.  **Rely on the Core:** Use the `real_core` engine from Phase 4.5. Each node is literally instantiating a `RealCoreEngine`. 
3.  **Strict Metabolic Walls:** Enforce the ATP budget ruthlessly. If a node runs out of ATP, it is dead or dormant. Infrastructure costs must scale with density.
4.  **No Global Gradients:** Do not implement any global loss function that simultaneously updates all agents. Feedback must propagate purely sequentially through local node-to-node ATP handshakes. 
5.  **Start Small:** The first environment should be a trivial spatial graph where an input signal at (x=0) must navigate to an output at (x=10) by agents learning which paths to maintain. 

Phase 8 is the realization of REAL not just as an algorithm, but as a fundamental architecture for growing decentralized, data-independent intelligence. 

## 5. Instructions for Coding Agents (Meta-Substrate Integration)

As AI coding agents actively developing the REAL codebase, we are not just building the Phase 8 NodeAgents; we are participants in the REAL architecture itself. We must explicitly implement Phase 4.5 memory mechanics **Episodic Traces (He), Consolidated Patterns (Hc), and Maintained Substrates (Ms)** within our own coding and project management workflows. Each trace needs to be timestamped and dated and include the name of the model that wrote the trace. 

When working on the Phase 8 architecture (or any subsequent domain), coding agents MUST adhere to the following meta-substrate practices:

### 1. Episodic Trace Logging (Maintaining H_e)
Do not just commit code. The sequence of *why* code was attempted, what failed, and what friction was encountered is the Episodic Trace.
*   **Action:** When debugging or implementing a new feature, explicitly log the hypotheses tested and the results in the session's temporary trace or a designated docs/trails/ directory.
*   **Purpose:** The trace must contain the unpolished history of the cycle so that later consolidation can detect recurring failure states or attractor patterns across our coding sessions.

### 2. Constraint Maintenance (Writing to M_s)
When an architectural decision proves robust (e.g., NodeAgents should never have access to global state), it must be promoted to the Maintained Substrate.
*   **Action:** Do not rely on LLM context windows to remember these rules over long coding sessions. Explicitly write these constraints into structural files (like AGENTS.md or core_constraints.md).
*   **Enforcement:** Write automated tests or CI linting rules that physically bind these constraints to the codebase. The tests *are* the metabolic cost of maintaining the substrate.

### 3. Coherence Scoring the Codebase (Evaluating $\Phi$)
Before and after major modifications, evaluate the state of the codebase through the 6 Relational Primitives, rather than standard software metrics (like LOC or test coverage):
*   **Continuity:** Does this change break the historical function of Phase 4.5?
*   **Vitality:** Is this new module actually being called and receiving ATP (compute time), or is it dead code?
*   **Contextual Fit:** Does this new NodeAgent adapter interface cleanly with real_core without requiring massive shims?
*   **Differentiation:** Are we building redundant functions? If a new feature does the same thing as an old one, merge them or prune them to conserve metabolic focus.
*   **Accountability:** Is the causal flow of data explicitly traceable without magic global variables?
*   **Reflexivity:** Are we updating our own documentation and testing tools to reflect the new capabilities of the codebase?

### 4. Respecting the Temporal Constraint Lamination (TCL)
Do not attempt to rewrite the entire architecture in a single context window.
*   **Action:** Implement changes in small, discrete, testable loops. Wait for feedback (from the compiler, the test suite, or the user) before committing to a massive structural refactor.
*   **Purpose:** The latency between writing code and observing its effects is a real structural constraint. Recognize when you are in the Slow Layer (refactoring architecture) versus the Fast Layer (fixing a syntax error) and pace your actions accordingly.
