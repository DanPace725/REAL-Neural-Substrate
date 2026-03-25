# Temporally Laminated REAL v0

## Purpose

This note defines a first-pass **2-layer laminated architecture** for REAL.
The goal is not to replace the current `real_core` plus `phase8` stack with a
new monolith. The goal is to introduce a disciplined outer loop that lets a
small, fast REAL substrate work on bounded slices, produce compact summaries,
receive slower regulatory guidance, and continue only as long as that guidance
still justifies another slice.

This is a design note, not an implementation spec for a full refactor.
It is intended to be decision-complete enough that later implementation can
start without reopening the core architectural questions.

## Why This Fits The Repo

The current repo is already closer to a laminated system than to a classic
single-pass model:

- [`real_core`](../README.md) already provides a reusable local REAL loop:
  `observe -> recognize -> predict -> select -> execute -> score -> compare -> consolidate`
- [`phase8`](../README.md) already treats each node as a local REAL agent
  rather than as a passive weight.
- [`real_core.mesh.TiltRegulatoryMesh`](../real_core/mesh.py) already
  introduces a light regulatory layer over dimension scores using TCL-style
  operating-window constants.
- current experiment summaries show that the sharpest difficulties are not
  generic scale alone, but **hidden-memory depth**, **ambiguity and path
  dependence**, **carryover alignment**, and **runtime cost**; see
  [20260324_cross_family_scale_summary.md](summaries/20260324_cross_family_scale_summary.md).

That makes lamination a natural next move. Instead of expanding one substrate
until it must hold too much live structure at once, the system can:

1. process a bounded slice locally
2. compress what happened into a narrow summary
3. regulate the next slice using slower, lower-bandwidth control
4. stop, continue, branch, or reset based on explicit settlement criteria

## Phase 1 Alignment

This architecture is directly aligned with the two Phase 1 anchors that matter
most here.

Primary references:

- [B2 — Dynamics and Formal Validation](../../Phase%201/Synthesis%20Project/B2%20%E2%80%94%20Dynamics%20and%20Formal%20Validation.ormd)
- [README.md](../README.md)
- [architecture_notes.md](summaries/architecture_notes.md)

### AVIA alignment

Phase 1 frames AVIA as hierarchical abstraction: when a system reaches the edge
of its current abstraction layer, it must either fail or generate a higher-order
abstraction that treats the previous layer as manageable raw material.

The laminated v0 interpretation is:

- the **fast layer** does local adaptation inside a slice
- the **slow layer** treats the fast layer's compressed summary as its input
- regulation is itself a higher-order abstraction over repeated local runs

This is not depth in the standard ML sense. It is staged abstraction over local
processes.

### TCL alignment

Phase 1 frames TCL as a **fast layer / slow layer** system under metabolic
constraints, with a safe operating window and a distinction between:

- **tilt coupling**: robust biasing
- **reshape coupling**: powerful but fragile restructuring

The laminated v0 interpretation is:

- the slow layer should mostly **tilt** the fast layer through bias, gating,
  context pressure, and stop criteria
- it should avoid high-bandwidth "reshape" behavior such as pushing raw state,
  full episodic dumps, or direct task solutions back into the fast layer

That is the main safety rule of this note.

## Problem Statement

The repo's current results suggest that one live substrate session is often
being asked to carry too much at once:

- `B`-family pressure rises sharply with hidden-memory depth
- `C`-family behavior is strongly ambiguity-sensitive and path-dependent
- visible and latent carryover each have failure modes under transfer
- extra idle runtime alone does not solve the problem
- stale carried structure can actively poison later tasks if it is moved forward
  without compatibility filtering

The laminated v0 hypothesis is:

> REAL may perform better when long-horizon work is decomposed into bounded
> slices whose outputs are compressed into strict summaries and regulated by a
> slower, lower-bandwidth layer, rather than by forcing one monolithic live
> substrate to keep all relevant structure active at once.

## v0 Architecture

Temporally Laminated REAL v0 has three moving parts:

1. a **fast execution layer**
2. a **slow regulatory/evaluative layer**
3. a **laminated controller** that mediates between them

Only the first two are learning layers. The controller is orchestration.

### 1. Fast execution layer

The fast layer is the existing local REAL substrate used for actual task work.
For v0, it remains the execution substrate and is not replaced.

Responsibilities:

- run the ordinary local REAL loop over a short bounded slice
- work with local state, local costs, local predictions, and local feedback
- accumulate only the minimum information needed to summarize the slice
- export a compact summary at the end of the slice

Operational rule:

- a slice is a bounded segment of work, not an entire training or transfer run

For CVT-style tasks, a slice may be defined by one of:

- a fixed example count
- a fixed cycle budget
- a fixed context-resolution window
- a fixed rolling-criterion window

The exact slicing policy can vary by benchmark, but the fast layer must never
assume it owns the whole horizon.

### 2. Slow regulatory/evaluative layer

The slow layer consumes only the summary emitted by the fast layer. It does not
read raw episodic traces, node-level logs, or full carryover payloads.

Responsibilities:

- evaluate whether the last slice settled, drifted, conflicted, or stalled
- apply low-bandwidth control to the next slice
- decide whether candidate carryover should be kept, filtered, or dropped
- decide whether the system should continue, branch, reset, or escalate

Allowed outputs:

- bias or gating shifts
- context-confidence pressure
- carryover keep/drop/filter hints
- reset, continue, reframe, branch, or escalate signals
- recursion stop criteria

Forbidden outputs:

- direct task answers
- direct route or transform prescriptions that bypass the fast layer's local
  choice process
- full-state restoration into the fast layer
- any global loss update path

### 3. Laminated controller

The controller runs the outer loop:

`fast slice -> summarize -> regulate -> next slice`

The controller should be designed as a reusable orchestration concept that can
later live near `real_core`, not as a `phase8`-specific special case.

Responsibilities:

- define slice boundaries
- invoke the fast layer on a slice
- hand only the resulting summary to the slow layer
- apply the returned regulatory signal to the next slice configuration
- stop when settlement criteria are met

The controller is not allowed to smuggle raw `SessionCarryover` or full node
snapshots into the slow layer.

## Information Discipline

The main risk in a laminated architecture is fake compression:
passing so much raw state between layers that the architecture becomes a
monolithic system in disguise.

For v0, the fast-to-slow interface must be **strictly summary-level**.

### Explicitly forbidden

- full `SessionCarryover`
- full episodic memory dumps
- full substrate snapshots
- full node-level action histories
- raw per-cycle logs
- direct target labels or hidden task answers not already local to the fast run

### Allowed

- compressed outcome statistics
- uncertainty and ambiguity summaries
- coarse carryover candidates
- conflict markers
- slice-level cost and efficiency summaries
- stop/continue recommendations

## Carryover Hygiene Model

The current repo already shows that carryover is valuable but not automatically
safe.

Two current empirical anchors matter:

1. selective scrubbing can rescue visible transfer when stale context-transform
   structure is the poison; see
   [2026-03-24 1033 - B to C Carryover Bridge.md](traces/2026-03-24%201033%20-%20B%20to%20C%20Carryover%20Bridge.md)
2. latent carryover can be transfer-safe by design when it avoids hard
   context-binding; see
   [20260317_phase8_session_synthesis.md](summaries/20260317_phase8_session_synthesis.md)

The laminated v0 rule is therefore:

> Slow-layer memory should prefer **summary-level, compatibility-checked
> carryover** over raw context-bound carried structure.

This means:

- the slow layer should reason over whether a carryover candidate looks
  reusable, ambiguous, conflicting, or task-bound
- the slow layer should filter candidates before they become future priors
- the slow layer should preserve the current latent-path advantage of avoiding
  brittle context binding where possible

The slow layer is not a warehouse for raw carryover. It is a compatibility
filter.

## Future Interface Sketch

The following types are reserved for later implementation. The names are part
of the v0 design contract.

### `SliceSummary`

`SliceSummary` is the only required fast-to-slow payload.

It should contain:

- `slice_id`
- `benchmark_family`
- `task_key`
- `slice_budget`
- `examples_seen`
- `cycles_used`
- `coherence_delta`
- `success_summary`
- `uncertainty_summary`
- `ambiguity_markers`
- `candidate_carryover`
- `conflict_markers`
- `cost_summary`
- `settlement_hint`

Behavioral meaning:

- `success_summary`: compressed local outcome, not raw traces
- `uncertainty_summary`: confidence, instability, or unresolved prediction
  pressure
- `ambiguity_markers`: evidence that multiple interpretations remain live
- `candidate_carryover`: a shortlist of what might be worth preserving
- `conflict_markers`: likely stale or mutually incompatible priors
- `cost_summary`: metabolic cost, route/transform cost, or runtime efficiency
- `settlement_hint`: whether the fast layer itself looks settled enough to stop

### `RegulatorySignal`

`RegulatorySignal` is the only required slow-to-fast payload.

It should contain:

- `bias_updates`
- `gating_updates`
- `context_pressure`
- `carryover_filter_hints`
- `slice_budget_adjustment`
- `reset_flags`
- `reframe_flags`
- `continue_confidence`
- `stop_reason`

Behavioral meaning:

- `bias_updates`: tilt-style changes that make some options cheaper or harder
- `gating_updates`: enable, suppress, or delay classes of behavior
- `context_pressure`: ask the next slice to resolve or defer context more
  aggressively
- `carryover_filter_hints`: retain, soften, scrub, or quarantine candidates
- `slice_budget_adjustment`: run shorter, longer, or unchanged next slice
- `reset_flags`: clear stale pressure without wiping the whole system
- `reframe_flags`: branch to a different mode, benchmark lane, or carryover mode

### `SettlementDecision`

`SettlementDecision` is the controller's explicit termination or branching
decision.

Allowed values:

- `continue`
- `settle`
- `branch`
- `escalate`

Behavioral meaning:

- `continue`: another slice is justified
- `settle`: the system is stable enough to stop this laminated episode
- `branch`: split into a new carryover or interpretation path
- `escalate`: move to a slower or broader evaluation path because the current
  lamination is not resolving the problem

## Controller Contract

The controller should follow this sequence:

1. initialize fast-layer state and slice policy
2. run one bounded slice
3. obtain `SliceSummary`
4. pass only `SliceSummary` to the slow layer
5. obtain `RegulatorySignal`
6. decide `SettlementDecision`
7. either:
   - stop
   - run another slice with updated bias/gating
   - branch to a different carryover or context mode
   - escalate to a slower analysis path

The controller must remain explicit about where each decision is made:

- local action selection remains in the fast layer
- regulatory judgment remains in the slow layer
- episode-level orchestration remains in the controller

## Relation To Existing Components

### `real_core`

The laminated v0 architecture should build on `real_core`, not replace it.

Reusable pieces already present:

- local REAL loop
- recognition and prediction summaries
- carryover export/import
- session summaries
- tilt-style regulation through `TiltRegulatoryMesh`

Likely future home:

- controller abstractions
- `SliceSummary`, `RegulatorySignal`, `SettlementDecision`
- summary-level carryover filtering hooks

### `phase8`

`phase8` remains the first benchmark substrate, not the final shape of the
laminated architecture.

Role in v0:

- provide the concrete fast-layer workload for initial experiments
- remain the place where routing, transfer, ambiguity, and morphogenesis are
  measured
- supply the practical pressure tests that the laminated controller must handle

## Validation Order

Validation should proceed in this order.

### 1. Primary v0 benchmark: `B2`

Use `B2` first.

Reason:

- it isolates hidden sequential dependence without the extra ambiguity confound
- it is the cleanest first test of whether slices plus slow regulation help
  hidden-memory pressure

Primary success criterion:

- the laminated controller improves hidden-memory handling without requiring a
  larger monolithic live substrate

Useful secondary measures:

- exact-match rate
- bit accuracy
- examples to criterion
- cycles to criterion
- cost to criterion
- whether the fast layer needs less live carryover pressure to stay coherent

### 2. Secondary validation lane: `C3S5` / `C3S6`

Use `C` only after the contracts are stable on `B2`.

Reason:

- `C` is where ambiguity, path dependence, and carryover conflict are sharpest
- it is the right stress test for regulatory filtering and settlement decisions

Primary success criterion:

- regulation reduces ambiguity-driven drift and does not make latent carryover
  more harmful than current baselines; see
  [2026-03-24 1705 - C Scale Transfer Slice.md](traces/2026-03-24%201705%20-%20C%20Scale%20Transfer%20Slice.md)

Secondary questions:

- does the slow layer detect when carryover should be softened or scrubbed
  before the next slice?
- can the controller stop early when the ambiguous regime is not settling?

### 3. Runtime check

Compare equal-example runs with and without lamination.

Reason:

- the repo already shows that extra idle runtime alone does not rescue failure
  in the current setup; see
  [2026-03-18 2054 - Runtime Slack Probe.md](traces/2026-03-18%202054%20-%20Runtime%20Slack%20Probe.md)
- the question is whether slicing plus regulation improves useful computation
  per runtime, not whether simply waiting longer does

Primary success criterion:

- equal-example laminated runs produce better outcome-per-runtime than the same
  monolithic run

### 4. Negative tests

The design must explicitly fail review if any of the following happen:

- raw-state explosion between layers
- hidden centralized planner behavior
- a global loss path that updates the fast layer directly
- slow-layer outputs that directly solve the task instead of biasing local work

## Guardrails

These are hard v0 rules.

1. Higher layers may only receive compact summaries and emit compact control
   signals.
2. The slow layer may bias, filter, gate, or stop. It may not directly execute
   task solutions.
3. `SessionCarryover` is not a laminated interface.
4. If a slice cannot be summarized compactly, the slice is too large.
5. Prefer tilt-style regulation to reshape-style intervention.
6. Build on current `real_core` contracts and carryover mechanisms before adding
   new `phase8`-specific machinery.

## Out Of Scope For v0

The following are intentionally deferred:

- a full 3-layer stack
- arbitrary recursive depth
- replacing `phase8` with a new substrate
- turning the slow layer into a planner
- large-scale benchmark expansion before `B2` and `C` prove the concept
- any claim that lamination alone solves morphogenesis, transfer, and ambiguity
  simultaneously

## Bottom Line

Temporally Laminated REAL v0 is a way to make the current architecture more
biologically and theoretically aligned without pretending the system must become
one giant live substrate.

The fast layer stays local and cheap.
The slow layer stays compressed and regulatory.
The controller stays explicit.
The interface stays narrow.

If this note is implemented faithfully, the next step is not a broad rewrite.
The next step is a small laminated controller tested first on `B2`, then on
`C`, with strict checks that the architecture remains summary-driven rather than
monolithic in disguise.
