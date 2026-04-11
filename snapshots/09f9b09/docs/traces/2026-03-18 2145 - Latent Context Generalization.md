# 2026-03-18 2145 - Latent Context Generalization

## Scope

This trace records the next architectural step after the context-cardinality groundwork:

- latent context tracking is no longer hard-coded to a binary `0/1` contest
- generated `ceiling_c*` tasks now expose their richer transform maps directly to the environment
- original A/B behavior was smoke-checked after the change

## What Changed

### 1. Task-aware transform maps in `phase8/environment.py`

The environment now recognizes:

- original `task_a/task_b/task_c` two-context mappings
- generated `ceiling_c1_*` 4-state collapsed mappings
- generated `ceiling_c2_*` 3-transform mappings
- generated `ceiling_c3_*` and `ceiling_c4_*` 4-transform mappings

This affects:

- `_expected_transform_for_task(...)`
- `_candidate_transforms_for_task(...)`
- `_target_bits_for_task(...)`

Practical impact:

- latent evidence can now accumulate against the actual generated C-family controller states
- `identity` is no longer invisible on the 4-transform C tasks

### 2. `LatentContextTracker` now supports dynamic context ids

Previously the tracker initialized and recomputed only:

- `context_evidence[0]`
- `context_evidence[1]`

It now:

- derives candidate context ids from the task family plus observed evidence
- maintains dynamic per-channel context maps
- computes the dominant context as the top score over the observed context set
- computes confidence from the gap between the top context and runner-up, not just `0` vs `1`

This preserves the old behavior for two-context tasks while allowing richer generated tasks to use `0..3`.

### 3. Sequence context for generated Family C is now 4-state

For generated `ceiling_c*` tasks, the source sequence estimate now follows the actual benchmark controller:

- `hidden_state = parity(previous packet) + 2 * parity(packet before previous)`

So the latent sequence hint can emit a 4-state estimate instead of only the previous parity bit.

## Validation

Focused tests passed:

- `python -m unittest tests.test_multicontext_substrate tests.test_latent_context_tracker tests.test_c_family_real_diagnostic`

Runtime smokes also passed:

- `python -m scripts.run_phase8_demo --mode comparison --seed 13 --scenario cvt1_task_a_stage1`
- `python -m scripts.run_phase8_demo --mode comparison --seed 13 --scenario cvt1_task_b_stage1`

Observed result:

- original `task_a` and `task_b` scenarios still run normally
- `task_b` still shows the familiar pattern of weak cold start and stronger warm carryover

## Remaining Limits

This is a meaningful architecture expansion, but it is not the full `C3/C4` solution.

Still outstanding:

- the latent tracker is task-aware in a hand-coded way for generated Family C, not yet a fully generic controller-state system
- B-family hidden-memory tasks still use the older one-bit sequence summary rather than task-depth-aware rolling parity
- some reporting/diagnostic surfaces still primarily assume visible packet context rather than latent controller state

## Recommended Next Step

If we continue down this path, the clean follow-up is:

1. add task-aware sequence controllers for generated B-family latent tasks
2. rerun the REAL-only `C3/C4` diagnostic after this latent generalization
3. compare whether `fixed-latent` and `growth-latent` improve specifically on the new 4-state C-family path
