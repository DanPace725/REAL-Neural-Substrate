# 2026-03-24 1120 - B to C Downstream Selector Read

## Context

The first visible timecourse pass showed that the source selector was not enough
to explain the whole `B -> C` story:

- seed `23` stayed bad in `full` even though the early source choice looked
  similar to the rescued modes
- seed `37` stayed bad after action-only scrub even when source-side carried
  context-action support had already been removed

That made the next useful question narrower:

- what are the direct downstream branch nodes actually choosing?

## Change

Extended `scripts/analyze_b_to_c_visible_timecourse.py` to capture
`focused_selector_snapshots` for:

- the source
- direct branch nodes `n1` and `n2`

Each snapshot now records:

- chosen action
- chosen and top-competitor route breakdowns
- local `state_before` transform/context-action fields

Updated `tests/test_b_to_c_visible_timecourse.py` to lock in the new payload.

## Validation

Executed:

- `python -m unittest tests.test_b_to_c_visible_timecourse`

Passed.

## Rerun

Reran:

- `python -m scripts.analyze_b_to_c_visible_timecourse --seeds 23 37 --modes none full full_context_actions_scrubbed full_context_scrubbed --output docs/experiment_outputs/2026-03-24_b_to_c_visible_timecourse_23_37.json`

## Result

The downstream read is clearer than the source-only view.

### Seed 23

The hotspot is `n1`, not the source.

Early on:

- `full`, cycle `2`: `n1 -> n3 : xor_mask_0101`
- `full_context_actions_scrubbed`, cycle `2`: same choice

So the branch node initially looks similar across bad and rescued modes too.

But the difference appears in what stabilizes afterward:

- `full`: `context_1` remains stuck at `0.0`
- `n1` keeps oscillating between `n3:xor_mask_0101` and `n3:xor_mask_1010`
- `context_1` mismatches stay in the correct family (`xor_mask_0101`)
- `route_wrong_transform_potentially_right` keeps rising

Meanwhile, in the rescued modes:

- `context_1` becomes perfect by cycle `2`
- by cycles `5-6`, `n1 -> n3` grows strong clean context-local support
  for the transfer-compatible transforms instead of just drifting

So seed `23` looks like a **downstream visible branch-use instability**, not a
simple bad source choice and not mainly a wrong-family trap.

### Seed 37

Here the downstream read points to a stronger local trap at `n1`.

Key early cycles:

- `full`, cycle `2`: `n1 -> n3 : xor_mask_1010`
- `full_context_actions_scrubbed`, cycle `2`: still `n1 -> n3 : xor_mask_1010`
- `full_context_scrubbed`, cycle `2`: flips to `n1 -> n3 : xor_mask_0101`

That is the cleanest local difference in the whole probe.

It also lines up with the metrics:

- `full` and `full_context_actions_scrubbed` keep accumulating
  `context_1` mismatches as `xor_mask_1010`
- `full_context_scrubbed` clears them immediately

So seed `37` is not just “source prior too strong.” The decisive lock-in is on
the downstream visible branch selector itself.

## Interpretation

The downstream read sharpens the earlier two-mechanism diagnosis:

1. Seed `23`
   The failure is mostly a downstream visible branch-use instability after an
   initially similar source and branch start.

2. Seed `37`
   The decisive poison is already visible in the downstream branch selector:
   combined scrub is the first mode that flips `n1` into the correct
   `context_1` transform choice at cycle `2`.

That means the next most useful intervention, if we want one, is probably not a
generic source-side carryover rule. It is something closer to:

- branch-node visible transfer challenge,
- or branch-node-local compatibility gating for carried context structure.
