# 2026-03-19 1213 - B to C Carryover Diagnosis

## Context

The recent transfer-exposure comparison suggested that warm `B -> C` may be limited more by stale or misaligned carryover than by lack of prediction:

- `B -> C`, no carryover started much stronger than `full` or `substrate`
- repeated exposure still increased prediction confidence in all modes
- but the weak carryover cases had more room to improve because they started worse

The next question was whether the harmful signal was mainly:

- retained episodic entries from full carryover, or
- structural carryover already present in the substrate snapshot

## Diagnostic

Added `scripts/diagnose_b_to_c_carryover.py`.

It:

- trains on `cvt1_task_b_stage1`
- saves both `full` and `substrate` carryover
- loads `none`, `substrate`, and `full` into fresh `cvt1_task_c_stage1` systems
- probes the very first source-node route decision for both `context_0` and `context_1`
- reports the carried source supports, promoted pattern sources, and the chosen first action

Added structural coverage in `tests/test_b_to_c_carryover_diagnosis.py`.

## Result

Seed `13`, first `task_c` source decision:

### Context 0

Expected transform: `xor_mask_1010`

- `none` chose `route_transform:n2:xor_mask_1010`
- `substrate` chose `route_transform:n2:rotate_left_1`
- `full` chose `route_transform:n2:rotate_left_1`

### Context 1

Expected transform: `xor_mask_0101`

- `none` chose `route_transform:n2:xor_mask_1010`
- `substrate` chose `route_transform:n2:rotate_left_1`
- `full` chose `route_transform:n2:rotate_left_1`

The important structural detail is that `substrate` and `full` had the same carried source-side support layout:

- pattern sources: `{"route_attractor": 2, "context_transform_attractor": 3}`
- edge supports: both branches seeded at `0.32`
- no generic transform supports on source branches
- but context-specific rotate support was already seeded:
  - `n2 / context_0 / rotate_left_1 = 0.24`
  - `n1 / context_1 / rotate_left_1 = 0.24`
  - `n2 / context_1 / rotate_left_1 = 0.24`
- the corresponding `xor_mask_1010` and `xor_mask_0101` context supports were `0.0`

The `full` run differed mainly in having retained episodic entries (`24` vs `0`), but the first bad `ctx0` choice was the same as `substrate`.

## Interpretation

This strongly suggests that the main harmful carryover on `B -> C` is already structural:

- stale `rotate_left_1` context-transform support from B is being promoted into the source substrate
- that structural prior is enough to flip the very first `task_c` `ctx0` choice away from the correct `xor_mask_1010`
- removing episodic entries alone is not enough, because `substrate` still makes the same wrong first choice

So the current limiter does not look like “too much replay memory.” It looks more like “promoted context-transform support is too task-insensitive across transfer.”

## Practical Conclusion

If we want to improve warm `B -> C`, the next intervention should probably target carryover hygiene for promoted context-transform structure, for example:

- stronger suppression of stale carried context-transform supports during early transfer adaptation
- task-compatibility gating before old context-transform attractors influence route selection
- or a more selective carryover policy for promoted context-transform supports across task-family shifts

The important point is that the diagnosis now points at structural carryover, not just episodic carryover.
