# 2026-03-26 1430 - Laminated Growth Continuity Audit

## Purpose

Audit whether laminated growth/control has drifted from the intended REAL design,
with emphasis on:

- whether growth is being selected top-down by the slow layer instead of requested
  bottom-up by fast-layer pressure and then approved between slices
- whether growth hysteresis is masking broken continuity across slices and mode
  switches
- what state actually survives a lamination mode transition
- whether slice budget is still regulator-controlled or has effectively drifted
  back into a benchmark knob

## Summary

The main architectural problem is not that `real_core` lacks memory. It is that
the laminated Phase 8 mode-switch path preserves only node-engine carryover while
discarding the wider system/runtime layer where much of growth continuity actually
lives.

This creates a mismatch:

- `real_core` correctly preserves substrate snapshots, episodic carryover,
  prior coherence, and dimension history per node
- Phase 8 already has full system-level carryover hooks that preserve topology,
  latent/context state, capability state, admission substrate, packet/runtime
  state, and pending morphogenesis work
- the laminated `_switch_mode()` path does not use those Phase 8 continuity
  hooks and instead rebuilds a fresh system from the original scenario graph

That makes the growth lock/hysteresis understandable as a defensive patch, but
also suggests it is currently compensating for broken continuity instead of
solving it.

## Findings

### 1. `real_core` memory/carryover is implemented and survives per-node mode switches

`SessionCarryover` includes:

- `substrate`
- `episodic_entries`
- `dim_history`
- `prior_coherence`
- `metadata`

`RealCoreEngine.export_carryover()` and `load_carryover()` preserve those fields,
including substrate state and prior coherence.

Implication:

- node-local REAL memory is not the missing concept
- the memory model in `real_core` is doing what it claims to do

### 2. Laminated mode switching only restores node-engine carryover, not full system continuity

`Phase8SliceRunner._switch_mode()`:

1. exports `agent.engine.export_carryover()` for each current node
2. rebuilds a new `NativeSubstrateSystem` from `build_system_for_scenario(...)`
3. restores each node's engine carryover with `agent.engine.load_carryover(...)`

What it does not preserve:

- environment runtime state
- dynamic topology state
- pending growth proposals
- latent context trackers
- capability states
- admission substrate
- queue/inbox/source-buffer state
- pending feedback
- capability timeline

So continuity at the node engine level survives, but continuity at the system
layer does not.

### 3. Phase 8 already has richer continuity hooks that lamination is bypassing

`RoutingEnvironment.export_runtime_state()` / `load_runtime_state()` preserve:

- topology
- node runtime state
- inboxes / source buffer / dropped packets / delivered packets
- pending feedback
- current cycle counters
- admission substrate and source-admission history
- pending growth proposals
- latent context trackers
- capability states
- capability policy

`NativeSubstrateSystem.save_carryover()` / `load_carryover()` preserve this full
runtime state plus all node carryover payloads.

`save_memory_carryover()` / `load_memory_carryover()` and
`save_substrate_carryover()` / `load_substrate_carryover()` also preserve a
middle layer including:

- topology
- admission substrate
- latent context trackers
- capability states
- task ids seen

Implication:

- the repo already has the machinery needed for mode-invariant memory
- the laminated mode switch is not using it

### 4. Accumulated growth is likely being destroyed above the node-memory layer

Because `_switch_mode()` rebuilds from `scenario.adjacency` and `scenario.positions`,
it throws away dynamic structural state and then reloads only per-node engine
carryover.

Most likely lost on switch:

- dynamic nodes and dynamic edges created by morphogenesis
- topology event history
- pending growth proposals waiting for checkpoint application
- environment-side capability recruitment state
- latent task/context trackers
- runtime ATP/reward/load history in `node_states`
- packet backlog and feedback continuity

Most likely preserved on switch:

- per-node substrate slow support
- per-node episodic entries
- per-node prior coherence
- per-node dimension history

This explains why "growth was destroyed" can be true even though `real_core`
carryover exists: the missing memory is not primarily inside `real_core`; it is
in the Phase 8 runtime layer.

### 5. Slow-layer growth choice has drifted toward top-down selection

`REALSliceRegulator` chooses one named compound policy per slice. Each policy
already bundles:

- `capability_mode`
- `carryover_filter`
- `budget_multiplier`
- `context_pressure`

Growth is therefore currently a direct slow-layer action, not merely an approval
of a fast-layer request.

At the same time, `self-selected` Phase 8 still computes bottom-up local
capability pressure and local `growth_enabled` state from contradiction, load,
prediction, ATP, latent confidence, and stabilization signals.

So the architecture is currently mixed:

- bottom-up/local recruitment exists in `self-selected`
- but the laminated controller can also impose `growth-visible` top-down

This drifts from the cleaner intended design where growth pressure should arise
from fast-layer conditions and the slow layer should adjudicate between slices.

### 6. Hysteresis is protecting continuity, but probably masking the real bug

The existing growth-family lock was introduced after a real failure: switching
from growth mode back to visible discarded accumulated growth and tanked
performance.

That logic now prevents stepping back out of growth except after enough degraded
cycles.

This makes sense as a temporary guard, but given the current audit the more
likely interpretation is:

- hysteresis is compensating for broken mode-switch continuity
- not proving that destructive reversion is architecturally necessary

If mode-invariant memory were preserved correctly, the slow layer should not need
to avoid non-growth modes simply to prevent memory loss.

### 7. Budget has partially drifted back into a benchmark knob under the REAL regulator

`LaminatedController` still treats budget as a regulator output in principle.

But in current practice:

- `REALSliceRegulator` computes next budget from the selected policy's
  `budget_multiplier`
- all current named policies use `budget_multiplier = 1.00`
- the heuristic regulator's own budget proposal is not used by the REAL regulator
  for the final budget

Result:

- under `reg=real`, slice budget is operationally fixed after initialization
- the benchmark's initial budget is doing most of the work

So budget has not drifted back into a fixed knob everywhere, but it effectively
has for the current REAL-regulated laminated benchmarks.

## Recommendation

Growth control should be refactored toward three layers:

1. fast-layer growth request
   - emit compact per-slice pressure summaries from local capability state and
     pending morphogenesis conditions
   - examples: growth pressure, stabilization readiness, unresolved overload,
     pending proposal pressure, context-resolution gate status

2. slow-layer adjudication
   - the slow layer should approve, defer, damp, or reset growth between slices
   - this keeps lamination responsible for regulation without inventing growth
     pressure from scratch

3. mode-invariant memory preservation
   - mode switches should preserve the full runtime/memory layer, not only node
     engine carryover
   - the laminated switch path should reuse Phase 8 system/runtime carryover
     machinery or an in-memory equivalent of it

### Concretely

The likely good target is:

- keep `self-selected` as the default fast-layer capability substrate
- add fast-layer summary fields for growth request / growth pressure
- let the slow layer decide whether to authorize stronger growth posture for the
  next slice
- preserve topology, latent/capability state, runtime state, and node carryover
  across that transition

That would align much better with the March 19 self-selection design: local
capabilities become recruitable by fast-layer conditions, while the slow layer
governs when a cross-slice regime shift is actually warranted.

## Open Questions

- Should "visible" in the slow-layer policy vocabulary map to `fixed-visible` or
  continue mapping to `self-selected`?
- Should a mode switch preserve all packet/runtime queues, or should there be a
  narrower continuity contract that keeps topology/capability/context memory but
  intentionally resets transient traffic?
- Should growth hysteresis remain as a soft guard even after continuity is fixed,
  or should it be replaced by a requirement for repeated fast-layer growth
  requests?

