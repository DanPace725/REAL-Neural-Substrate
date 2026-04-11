# Phase 8 First Computational Experiment Spec

## Purpose

This document specifies the first Phase 8 experiment that moves the native substrate from packet routing into content-bearing computation.

It is the concrete next step implied by:

- `vision.md`
- `operational_orientation.md`
- `AGENTS.md`

The goal is not to broaden the project. The goal is to define the smallest experiment that can legitimately test whether a local, metabolically constrained REAL substrate can learn a context-dependent computation, retain useful structure, and later transfer that structure to a related task.

## Experiment Name

Contextual Vector Transform (CVT-1)

## Primary Claim

If a small REAL substrate is given content-bearing signals, local transformation actions, and sequential local feedback, it should be able to learn a context-dependent mapping from sparse examples and later adapt faster on a related mapping when maintained substrate is preserved.

## Why This Experiment

CVT-1 is designed to satisfy the constraints from `vision.md` and `AGENTS.md`.

- It is small enough to run on consumer hardware.
- It is more than routing: the sink must judge transformed content, not only arrival.
- It uses temporal context, so episodic memory and substrate carryover can matter.
- It can be benchmarked against a small neural baseline.
- It preserves local-only learning, ATP scarcity, and sequential feedback.

## Non-Negotiable Constraints

The implementation of this experiment must preserve the following:

- no global loss function or shared gradient update
- no broadcast reward signal
- no node access to full graph state
- no hidden centralized planner that chooses correct routes or transforms
- no cheating by writing final targets directly into substrate state
- no abandonment of ATP costs as real gating constraints

## Current Starting Point

Phase 8 already has the following assets:

- a local routing environment in `phase8/environment.py`
- content-free `SignalPacket` records in `phase8/models.py`
- node-local observation, action, and memory bindings in `phase8/adapters.py`
- node agents backed by `RealCoreEngine` in `phase8/node_agent.py`
- scenario and comparison harness patterns in `phase8/scenarios.py` and `compare_cold_warm.py`

CVT-1 should extend these rather than bypass them.

## Task Definition

### Input Space

Each packet carries a 4-bit content vector:

- `x_t in {0,1}^4`

The environment produces a stream of packets over cycles.

### Context Rule

The correct transformation for packet `x_t` depends on the parity of the previous packet's input vector:

- `context_t = even` if `x_(t-1)` has even Hamming parity
- `context_t = odd` if `x_(t-1)` has odd Hamming parity

For the first packet in a session, use `context_0 = even`.

This makes the task sequence-contingent while keeping the context rule simple and measurable.

### Task A

For the first task:

- if `context_t = even`, target output is `rotate_left_1(x_t)`
- if `context_t = odd`, target output is `xor_mask_1010(x_t)`

### Task B

For the transfer task:

- if `context_t = even`, target output remains `rotate_left_1(x_t)`
- if `context_t = odd`, target output becomes `xor_mask_0101(x_t)`

This makes Task B related rather than unrelated. Half the task remains stable, while one branch changes. That gives maintained substrate something real to preserve and something real to update.

## Two-Stage Rollout

To respect TCL and the AGENTS requirement for small testable loops, CVT-1 should be built in two stages.

### Stage 1: Explicit Context Packet

In Stage 1, each packet carries:

- the 4-bit input vector
- a 1-bit context flag computed by the environment from the previous input parity

Purpose:

- validate content transport
- validate local transform actions
- validate sink-side scoring
- validate sequential feedback for computational success

This stage is an engineering bridge. It is not yet the strongest scientific version of the task.

### Stage 2: Latent Context

In Stage 2, the explicit context bit is removed from the packet.

Nodes only receive:

- the current packet content
- their ordinary local environment state
- their own episodic and substrate history

Purpose:

- require actual sequence-sensitive adaptation rather than explicit context labeling
- make episodic memory and warm-start carryover more central to performance

Stage 2 is the real target. Stage 1 is the minimum viable bridge.

## Topology

The first implementation should use a fixed, small branching topology.

Recommended topology:

- source node `n0`
- two first-hop branches `n1`, `n2`
- one or two downstream nodes `n3`, `n4`
- sink

The exact shape can reuse the current `branch_pressure` pattern as the initial scaffold.

Reason:

- enough branching for specialization to emerge
- small enough to inspect manually
- not so large that performance hides in complexity

Topology growth is explicitly out of scope for CVT-1.

## Packet and State Model

`SignalPacket` should be extended to carry computational content.

Required packet fields:

- `input_bits`: original 4-bit vector
- `payload_bits`: current mutable 4-bit vector
- `context_bit`: present in Stage 1 only
- `task_id`: `task_a` or `task_b`
- `transform_trace`: ordered list of local transformations applied
- `matched_target`: whether sink evaluation succeeded
- `target_bits`: optional sink-side reference for logging only, not for node observation

Constraint:

- nodes may observe `payload_bits`
- nodes may not observe `target_bits`

## Node Observation Requirements

Local observation should be extended so a node can perceive the packet it is about to act on without gaining global knowledge.

Minimum additions:

- current head-of-queue payload bits
- local indicator that a packet is present
- optional Stage 1 context bit for the head packet
- local transform trace depth or mutation count

Still forbidden:

- full path outcome labels before sink evaluation
- downstream target information
- non-local graph state

## Local Action Vocabulary

The first computational slice should keep the action space small and discrete.

Required actions:

- `rest`
- `route:<neighbor>`
- `route_transform:<neighbor>:identity`
- `route_transform:<neighbor>:rotate_left_1`
- `route_transform:<neighbor>:xor_mask_1010`
- `route_transform:<neighbor>:xor_mask_0101`
- `inhibit:<neighbor>` only if retained from the routing substrate

Design note:

Combining transform and route in one action is acceptable for CVT-1 because it keeps the loop small and preserves local causality. A later phase can separate transform and forwarding into distinct actions if needed.

## Sink Evaluation

When a packet reaches the sink, the environment computes the target output from:

- the packet's original input vector
- the current task definition
- the session history needed for context

Then the sink compares `payload_bits` against the target.

Required sink outcomes:

- exact success
- partial match score based on bit overlap
- failure

Feedback policy:

- exact success produces the strongest upstream ATP pulse
- partial match produces a smaller sequential ATP pulse
- failure produces no positive pulse

This keeps feedback scalar and local while still making the task more graded than pure success/failure.

## Learning Signal

The learning signal in CVT-1 should remain purely structural.

- successful or partially successful transform-route sequences become cheaper through maintained substrate
- unproductive sequences remain metabolically expensive
- episodic traces preserve the history of which local actions preceded success or failure
- no parameter tensors are updated through backpropagation

## Metrics

CVT-1 needs metrics at both engineering and research levels.

### Engineering Metrics

- packets evaluated
- exact-match count
- partial-match count
- mean bit accuracy at sink
- mean action cost
- mean route-transform cost
- mean latency
- feedback returned per delivered packet

### Research Metrics

- examples to criterion
- cycles to criterion
- metabolic cost to criterion
- warm-start versus cold-start delta on Task A
- warm-start versus cold-start delta on Task B
- substrate-only versus full-carryover delta
- return-to-Task-A recovery after Task B

### Criterion Definition

For the first comparison harness, criterion should be:

- rolling exact-match rate >= 0.85 over the last 20 evaluated packets

Secondary criterion:

- rolling mean bit accuracy >= 0.95 over the last 20 evaluated packets

These can be adjusted later, but the initial version must pick explicit thresholds so comparisons are real.

## Benchmark Protocol

### Phase 1: Task A Sparse Learning

Run multiple seeds for:

- cold-start REAL substrate
- warm full carryover REAL substrate
- warm substrate-only REAL substrate

Report:

- examples to criterion
- cycles to criterion
- metabolic cost to criterion

### Phase 2: Task Transfer A -> B

Procedure:

1. train on Task A to criterion
2. save carryover states
3. switch to Task B
4. compare adaptation against a cold-start Task B run

Report:

- examples to regain criterion
- cycles to regain criterion
- cost during re-adaptation
- retained performance if switched back to Task A

### Phase 3: Baseline Comparison

Add a small neural baseline.

Recommended baseline:

- Stage 1: small MLP taking current input bits plus explicit context bit
- Stage 2: small recurrent baseline, or an MLP given current input plus previous input bits as its explicit context channel

The baseline comparison should be honest and minimal. It does not need to be state of the art. It needs to be fair, reproducible, and appropriate to the task.

## Implementation Slices

CVT-1 should be built in this order.

### Slice 1: Content-Carrying Packets

Change scope:

- extend `phase8/models.py`
- update packet creation and routing in `phase8/environment.py`

Exit condition:

- packets can carry mutable content end to end without breaking current routing behavior

### Slice 2: Transform-and-Route Actions

Change scope:

- extend `phase8/adapters.py`
- update local action availability and execution

Exit condition:

- nodes can apply one of the allowed transforms locally while forwarding

### Slice 3: Sink Scoring and Sequential Computational Feedback

Change scope:

- extend `phase8/environment.py`
- add task definitions, target computation, and graded feedback

Exit condition:

- delivered packets are scored for exact and partial correctness
- feedback still returns upstream one hop at a time

### Slice 4: Stage 1 Scenario and Comparison Harness

Change scope:

- extend `phase8/scenarios.py`
- add a new comparison runner or extend `compare_cold_warm.py`

Exit condition:

- Task A learning curves can be run and summarized over multiple seeds

### Slice 5: Transfer Harness

Change scope:

- add task switching support
- add A -> B protocol

Exit condition:

- warm-start and cold-start transfer comparisons are runnable

### Slice 6: Stage 2 Latent Context

Change scope:

- remove explicit context bit from node-visible packet state
- rely on sequential history instead

Exit condition:

- the task still runs end to end without centralized shortcuts

### Slice 7: Neural Baseline

Change scope:

- add a small standalone baseline script and shared dataset protocol

Exit condition:

- REAL and neural runs are comparable on examples, cycles, and task accuracy

## Testing Requirements

The first implementation must add tests for:

- packet content survives routing and transforms correctly
- sink exact-match and partial-match scoring
- feedback remains sequential and edge-local
- nodes never observe target output directly
- Stage 1 packets include context bit only when configured
- Stage 2 packets do not expose context bit
- carryover restores computational substrate state
- task switching from A to B runs without resetting maintained substrate unless explicitly requested

## Success and Failure Conditions

### Engineering Success

CVT-1 is engineering-successful when:

- the full task runs end to end
- the comparison harness produces reproducible learning curves
- carryover and task switching are both functional
- all tests pass

### Research Success

CVT-1 is research-successful when:

- the REAL substrate reaches criterion on Task A from sparse examples
- warm starts improve adaptation on Task B over cold starts
- maintained substrate contributes measurable benefit beyond episodic survivors alone
- the result is strong enough to survive comparison against a small neural baseline

### Honest Failure Case

If CVT-1 runs end to end but warm starts do not improve adaptation, that is still useful.

It would mean:

- the architecture can compute locally
- the current maintained substrate is not yet carrying the right transferable structure

That would narrow the problem rather than invalidate the approach.

## Immediate Build Decision

The implementation should begin with Stage 1, not Stage 2.

Reason:

- it keeps the first loop small
- it validates the mechanics of computational feedback before the harder problem of latent context inference
- it preserves the path toward the stronger result without forcing too much change into one step

## Deliverables

The first implementation pass for this spec should produce:

- code changes for content-bearing packets and transform actions
- one runnable CVT-1 Stage 1 scenario
- one comparison script for Task A cold versus warm
- tests covering content flow and sink scoring
- a trail document recording the implementation loop

That is the minimum package that turns the current Phase 8 substrate from routing proof into computational substrate prototype.
