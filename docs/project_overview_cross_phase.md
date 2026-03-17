# Project REAL Overview (Phase 8 Anchored)

_Last updated: 2026-03-16 by GPT-5.2-Codex_

## 1) Start Point: What Phase 8 is trying to prove

Phase 8 reframes the project from "one agent using REAL" into a **multi-agent substrate** where each node is itself a local REAL agent. The key claim is that useful computation can emerge from local allostatic adaptation (ATP budgets, local memory, sequential feedback), without global loss functions or backprop updates.

In practical terms, the Phase 8 codebase currently focuses on:
- node-local decision loops (`perceive -> select -> execute -> score -> consolidate`)
- edge/transform memory substrate that lowers local action costs over time
- task-oriented packet routing with graded sink feedback
- carryover comparisons (cold vs warm starts, including transfer from Task A to Task B)

This is the immediate execution layer of the architecture and currently the most operational phase.

## 2) Phase 8 implementation map (current runnable system)

The `phase8/` package is organized around local-only substrate mechanics:
- `node_agent.py`: wraps `RealCoreEngine` for each node.
- `environment.py`: small routing environment with sequential, localizable feedback flow.
- `substrate.py`/`consolidation.py`/`selector.py` (plus adapters/models): local memory promotion, selection pressure, and substrate carryover mechanics.
- `admission.py`: source admission control so ingress is metabolically gated.

The top-level runners (`run_phase8_demo.py`, `compare_cold_warm.py`, `compare_task_transfer.py`) provide reproducible scenario comparisons and transfer evaluations.

## 3) How earlier phases support Phase 8

### Phase 7 (memory substrate experiments)

Phase 7 appears to function as the direct precursor for substrate persistence experiments. It contributes:
- substrate-centric A/B testing patterns
- budget sweeps and retention analyses
- practical tooling for observing carryover benefits over repeated sessions

This phase provides an empirical bridge from simple episodic learning to persistent structural biasing.

### Phase 6 (integration into Emergence Engine)

Phase 6 ports/adapts REAL logic into a JS simulation environment and emphasizes:
- operational telemetry
- comparative snapshots
- tuning of coherence dimensions under live simulation dynamics

Its main contribution is systems integration discipline: logging, diagnostics, and repeatable A/B workflows that Phase 8 continues to rely on conceptually.

### Phase 5 (generalized infrastructure and tooling)

Phase 5 broadens experimentation and inference tooling around REAL, forming the scaffolding for cross-domain operation and test harnesses. It prepares the project for richer experimental loops rather than a single monolithic demo.

### Phase 4 (domain-agnostic REAL core)

Phase 4 is the architectural backbone used by later phases. It formalizes REAL as a reusable tuple/interface system (`S, A, c, O, Phi, H, Psi, Gamma, Omega`) and defines domain adapters. This is the explicit decoupling that allows Phase 8 node agents to instantiate a shared engine rather than hardcoded task logic.

## 4) Throughline across phases

Across the project, the trajectory is:
1. **Core endogenous-learning principle** (REAL loop and coherence-driven evaluation).
2. **Generalization into reusable engine/interfaces** (Phase 4).
3. **Operational experimentation and integration** (Phases 5 and 6).
4. **Persistent substrate and carryover experimentation** (Phase 7).
5. **Multi-agent native substrate for emergent computation** (Phase 8).

So Phase 8 is not a reset; it is the convergence point where prior core abstractions, memory substrate work, and experimental rigor are combined into a local-learning network architecture.

## 5) Current project status (high-level)

Project REAL is presently in a **transition from theory + prototype mechanics to measurable computational demonstrations**:
- Routing and metabolic adaptation are established.
- Context-sensitive transform learning is introduced (CVT-1 Stage 1 trajectory).
- Transfer behavior is observable but still being stabilized.
- Next work likely focuses on stronger transfer quality, substrate maintenance policy, and clearer diagnostics for why/where adaptation fails.

In short: the project now has a credible substrate-learning testbed, and the near-term challenge is to convert that into consistently strong, benchmarkable task-learning outcomes.
