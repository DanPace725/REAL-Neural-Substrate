# 2026-03-18 1915 - C Family Architecture Diagnosis

## Scope

This trace records a code-level diagnosis of why REAL breaks down on the generated `C3/C4` ambiguity ladder, plus the first fixes attempted during diagnosis.

It follows:

- `2026-03-18 1535 - C Family Diagnostic`
- `2026-03-18 1725 - C Family Full Capability Run`

## Main Finding

There are two different problems mixed together in late Family C:

1. a real code-path blind spot that was suppressing the latent-task machinery on generated benchmark ids
2. a deeper architecture/task mismatch where the benchmark requires more than the current binary-context substrate can represent

These should not be conflated.

## Code-Level Cause #1: Generated Task Ids Were Invisible To The Latent Task Logic

The generated ceiling tasks use ids like:

- `ceiling_c3_task_a`
- `ceiling_c4_task_b`
- `ceiling_c4_task_c`

But Phase 8 task-mapping helpers in `phase8/environment.py` only recognized literal:

- `task_a`
- `task_b`
- `task_c`

That meant three important subsystems were effectively blind on the generated C-family:

1. `_expected_transform_for_task(...)`
2. `_candidate_transforms_for_task(...)`
3. all latent tracker updates that depend on those helpers

Practical effect:

- latent route / feedback evidence could not map transforms back to context hypotheses
- `task_transform_affinity_*` stayed neutral
- `source_sequence_transform_hint_*` stayed neutral
- the hidden-task selector path lost the intended transform-family prior on generated tasks

## Fix Applied

Added `_canonical_task_family(...)` in `phase8/environment.py` so generated ids ending in `_task_a`, `_task_b`, or `_task_c` inherit the same task-family semantics as the original CVT tasks.

Also added regression coverage in:

- `tests/test_c_family_real_diagnostic.py`

## Measured Impact Of The Task-Id Fix

### `C3`, seed 13, full-capability REAL run

Cold aggregated over `task_a/task_b/task_c`:

| Method | Before | After |
|---|---:|---:|
| fixed-latent exact | 0.2160 | **0.2562** |
| fixed-latent bit acc | 0.5555 | 0.5293 |
| fixed-latent criterion rate | 0.0000 | **0.3333** |
| growth-latent exact | 0.2346 | 0.2346 |
| growth-latent bit acc | 0.5278 | 0.5015 |

Transfer:

| Method | Target | Before exact | After exact |
|---|---|---:|---:|
| growth-latent | `task_b` | 0.0833 | **0.1759** |
| growth-latent | `task_c` | 0.1204 | **0.1574** |

Interpretation:

- the fix materially improved latent-mode access to the generated task structure
- the biggest immediate win was recovering `growth-latent` from a near-collapse transfer mode on `C3`
- visible modes were unchanged, which is exactly what we would expect from a fix that only touches hidden-task routing priors

### `C4`, seed 13, full-capability REAL run

Cold aggregated over `task_a/task_b/task_c`:

| Method | Before | After |
|---|---:|---:|
| fixed-latent exact | 0.1327 | **0.2099** |
| fixed-latent bit acc | 0.4946 | **0.5193** |
| growth-latent exact | 0.1559 | 0.1621 |

Transfer:

| Method | Target | Before exact | After exact |
|---|---|---:|---:|
| growth-latent | `task_b` | 0.1944 | **0.2269** |
| fixed-latent | `task_c` | 0.1574 | **0.1806** |

Interpretation:

- the bug fix helps on `C4` too
- but it does not remove the late-family difficulty wall

## Architecture-Level Cause #2: Family C Exceeds The Current Binary Context Model

The harder C-family points are generated from a 4-state hidden controller:

- hidden state is computed from the parity of the previous two packets
- visible context compresses or scrambles that 4-state controller
- the correct transform depends on more than one binary bit of latent history

Current Phase 8 context machinery is still binary:

- `SUPPORTED_CONTEXTS = (0, 1)` in `phase8/substrate.py`
- `LatentContextTracker` only tracks `context_evidence[0]` and `context_evidence[1]`
- `dominant_context` is a single binary state
- contextual action support is keyed by one `context_bit`

This means the substrate can only learn:

- one context-conditioned support set for `0`
- one context-conditioned support set for `1`

It cannot represent the full 4-state controller needed by `C3/C4`.

That is the deeper reason the ladder gets stuck:

- `C1` works because visible context still identifies the transform exactly
- `C2` is partially survivable because only one visible branch is ambiguous
- `C3/C4` require disambiguation inside the same visible context branch, which the current binary-context substrate cannot stably encode

## Architecture-Level Cause #3: The Sequence Tracker Only Models One Bit Of State

`LatentContextTracker.observe_packet(...)` currently sets:

- `sequence_context_estimate = prior_parity`

So the sequence-side hint only tracks the parity of the immediately previous input.

But late Family C is driven by a two-step parity controller. That means the source-side hint is underpowered even after the task-id fix:

- it gives a one-bit guess
- the benchmark requires a two-bit hidden controller

So the current latent path is not just under-tuned. It is structurally narrower than the generated benchmark.

## Secondary Mismatch: Growth Gate vs Promotion Gate

There was also a smaller semantic mismatch:

- morphogenesis gating used `effective_context_confidence >= 0.55`
- consolidation / maintenance use stronger promotion semantics (`promotion_ready`, higher confidence)

This means `growth-latent` could begin budding while the context estimate was barely effective but not yet promotion-ready.

A small gate alignment fix was applied in `phase8/environment.py` so growth is still blocked while latent context is unpromoted.

Observed effect on the `C3` seed-13 rerun:

- no measurable change relative to the task-id fix alone

Interpretation:

- the gate alignment is still architecturally cleaner
- but it is not the dominant bottleneck on `C3`

## Current Best Explanation Of The Breakdown

`C3/C4` are failing for two different reasons:

1. REAL had been handicapped by a generated-task-id bug in the latent path
2. even after that fix, the benchmark is asking a binary-context substrate to solve a 4-state hidden-controller task

So the current state is:

- some of the apparent failure was accidental and fixable
- the remaining failure is mostly real and architectural

## What Might Actually Improve Results

### High-confidence improvement

Keep the generated-task-id fix. It restores intended behavior for all generated benchmark families, not just C.

### Likely next improvement

Generalize context from a single binary bit to a small categorical latent state for tasks that need it.

Concretely, late Family C likely wants one of:

1. context cardinality > 2 in the substrate and latent tracker
2. a task-local latent-state key separate from `context_bit`
3. a small controller-state substrate indexed by sequence state, not just visible context

### Also likely worthwhile

Upgrade the sequence tracker from "previous parity bit" to the same controller depth the benchmark uses:

- for `C3/C4`, this means at least a two-step parity state

Without that, the source-side hidden-task heuristic will keep underrepresenting the benchmark's actual latent structure.

## Recommendation

Do not treat the remaining `C3/C4` weakness as evidence that REAL simply "loses to ambiguity."

The cleaner interpretation is:

- REAL was partially undercut by a task-id bug, now fixed
- the remaining hard points exceed the current binary-context architecture

The next serious improvement should therefore be architectural:

- add multi-state latent context support
- or redesign the late C-family so it stays within the current binary-context thesis if that is the intended experimental boundary
