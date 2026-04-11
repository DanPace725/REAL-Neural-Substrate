# 2026-03-18 2045 - Context Cardinality Groundwork

## Why Context Was Binary

Phase 8 inherited a binary context model from the original 6-node CVT benchmark family:

- `Task A`, `Task B`, and `Task C` each branch on `context_0` vs `context_1`
- the early latent-context path was framed as "recover the missing bit"
- substrate supports, transform credit, and diagnostics were all optimized around that two-context regime

So the binary context assumption was originally a benchmark simplification, not a general architectural claim.

The problem is that this assumption then hardened into substrate primitives:

- `SignalPacket.__post_init__` collapsed any nonzero context label to `1`
- `ConnectionSubstrate` preallocated contextual support keys only for `(0, 1)`
- growth seeding only looked at contexts `(0, 1)`

That means later benchmarks with richer hidden controllers were hitting a storage-layer bottleneck before we even got to the latent inference logic.

## Groundwork Patch Applied

This session applied a low-risk first step toward multi-context support:

- `phase8/models.py`
  - explicit packet context labels are now preserved as integers instead of being coerced to binary
- `phase8/substrate.py`
  - contextual support keys can be registered lazily for new integer context labels
  - dynamic context support is included in save/load and overlap copy paths
- `phase8/topology.py`
  - growth seeding can inspect observed context ids beyond the legacy `(0, 1)` defaults
- `tests/test_multicontext_substrate.py`
  - regression coverage for packet preservation, dynamic context registration, and save/load restoration

## What This Does Not Solve Yet

This does **not** by itself make the latent path multi-state.

The bigger binary assumptions still live in `phase8/environment.py`:

- `LatentTaskState.context_evidence` is initialized as `{0: 0.0, 1: 0.0}`
- `dominant_context` is resolved by comparing only contexts `0` and `1`
- `sequence_context_estimate` still models only a one-bit parity hint
- several diagnostics and summaries still render only contexts `0/1`

So this patch opens the storage and carryover layer first, but the latent tracker still needs a follow-up generalization if we want REAL to represent `C3/C4`-style controller states directly.

## Recommended Next Step

Generalize the latent tracker from "binary dominant context" to "small categorical context distribution":

1. make `LatentTaskState.context_evidence` and `context_evidence_by_channel` fully dynamic maps
2. compute dominant context from `argmax` over observed context ids rather than a hard-coded `0/1` comparison
3. add an optional task-local controller state separate from visible `context_bit`
4. upgrade the sequence hint from previous parity to a configurable controller-depth feature

That would let the environment reason over richer latent state without forcing the entire repo to abandon the original binary CVT benchmarks.
