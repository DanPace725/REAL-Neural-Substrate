# 2026-03-19 1238 - B to C Carryover Hygiene Pass

## Context

The `B -> C` carryover diagnosis showed that the main stale signal was already structural:

- carried `context_transform_attractor` patterns
- carried context-specific `rotate_left_1` support
- same first wrong `ctx0` choice in both `substrate` and `full`

The cleanup goal was deliberately conservative:

- damp stale carried context-transform support
- do not delete carried structure
- preserve transfer benefit when local evidence starts to confirm the carryover

## Change

Updated `phase8/selector.py` so carried `context_action_support` is treated more like a prior than a command.

The new behavior computes an effective context-action support that:

- starts from the raw carried support
- down-weights it when the current task geometry contradicts that transform
- down-weights it more strongly during transfer adaptation
- relaxes the damping when local confirmation appears through:
  - history transform evidence
  - feedback credit
  - context feedback credit
  - branch/context feedback credit

Added focused selector tests in `tests/test_phase8_recognition.py` to lock in:

- stale support gets damped under mismatch
- confirming local evidence raises the effective support scale again

## Result

The cleanup is real, but modest.

On the rerun of the `B -> C` carryover diagnostic for seed `13`, `ctx0`, both `substrate` and `full` now show:

- raw carried context support for `n2 / rotate_left_1`: `0.24`
- effective context support after hygiene: `0.174924`
- support scale: `0.72885`

So the stale carried support is being reduced by about `27%`.

That said, the first source decision still did not flip:

- expected `ctx0` transform: `xor_mask_1010`
- `substrate` still chose `route_transform:n2:rotate_left_1`
- `full` still chose `route_transform:n2:rotate_left_1`

The repeated warm `B -> C` exposure probe also stayed effectively unchanged:

- repeat `1x`: exact `0.2222`
- repeat `2x`: exact `0.3889`
- repeat `3x`: exact `0.4444`

## Interpretation

This pass looks like the right kind of cleanup:

- it is local
- it is evidence-sensitive
- it does not remove transfer structure
- it measurably reduces stale carried support

But it is not yet strong enough to change the observed `B -> C` transfer behavior by itself.

So the current read is:

- the hygiene direction is sound
- the change is safe
- but the stale structural prior is still strong enough to win the first `B -> C` source decision

That means a next step, if we take one, should probably stay in the same family:

- a slightly stronger or more targeted task-compatibility gate for carried context-transform supports
- not a broad rollback of carryover
- and not a generic prediction retune
