# 2026-03-24 1101 - B to C Visible Timecourse Diagnostic

## Intent

The bridge and split-ablation runs had already narrowed the visible `B -> C`
problem to two different-seeming failure signatures:

- seed `23`: mostly `route_wrong_transform_potentially_right`
- seed `37`: mostly `wrong_transform_family` plus
  `stale_context_support_suspicions`

The next question was whether those signatures showed up as:

- an immediate bad source decision,
- a slower downstream lock-in,
- or different node-local drift patterns over the transfer run.

## Change

Added `scripts/analyze_b_to_c_visible_timecourse.py`.

The new harness reuses the bridge carryover construction and records a
cycle-by-cycle visible transfer timeline for selected modes.

Per cycle it captures:

- transfer metrics already exposed by `task_diagnostics`
- cumulative deltas for visible failure fields
- source selector choice and compact score breakdowns
- source latent/context snapshot fields
- focused node snapshots for the source plus direct branch nodes
- selector-cycle branch/transform counts

Added structural coverage in `tests/test_b_to_c_visible_timecourse.py`.

Also corrected the first draft of the summary helper so selector-window rollups
aggregate the nested `selector_cycle` payloads instead of the full cycle
records.

## Validation

Executed:

- `python -m unittest tests.test_b_to_c_visible_timecourse`
- `python -m unittest tests.test_b_to_c_visible_timecourse tests.test_b_to_c_carryover_bridge`

Both passed.

## Run

Executed:

- `python -m scripts.analyze_b_to_c_visible_timecourse --seeds 23 37 --modes none full full_context_actions_scrubbed full_context_scrubbed --output docs/experiment_outputs/2026-03-24_b_to_c_visible_timecourse_23_37.json`

Saved artifact:

- `docs/experiment_outputs/2026-03-24_b_to_c_visible_timecourse_23_37.json`

## Result

The timecourse makes the split diagnosis much clearer.

### Seed 23

`full` fails as a branch-compatibility problem, not mainly as a transform-family
problem:

- final: `7 exact / 0.3889 bit / 0.0 ctx1 bit`
- peak `wrong_transform_family`: only `2`
- peak `route_wrong_transform_potentially_right`: `9`

Action-only scrub fixes it immediately:

- `full_context_actions_scrubbed`: `18 exact / 1.0 bit / 1.0 ctx1 bit`
- first perfect `context_1` cycle: `2`

The important subtlety is that the **source** selector looks nearly the same in
the early cycles of `full` and `full_context_actions_scrubbed`:

- source keeps choosing `route_transform:n1:xor_mask_1010`
- early selector branch counts are the same

So the rescue is not explained by a different first source choice alone. The
drift is happening in the downstream visible path after that source decision.

### Seed 37

`full` and `full_context_actions_scrubbed` are effectively identical:

- final: `10 exact / 0.5556 bit / 0.0 ctx1 bit`
- peak `wrong_transform_family`: `8`
- peak `stale_context_support_suspicions`: `8`

Combined scrub fixes it immediately:

- `full_context_scrubbed`: `18 exact / 1.0 bit / 1.0 ctx1 bit`
- first perfect `context_1` cycle: `2`

This is the strongest evidence yet that action-only scrubbing is insufficient
for this seed. The remaining failure after action scrub is consistent with
retained structural pattern bias on the downstream visible path.

## Interpretation

The timecourse supports a sharper two-mechanism read:

1. Seed `23` is mostly a visible branch-use failure that unfolds **after**
   an initially similar source decision.
2. Seed `37` is a stronger wrong-transform-family trap where action-only scrub
   does not help, and combined scrub is needed to break the retained structural
   bias.

That means the next best diagnostic or intervention should probably target
downstream branch-node behavior under visible transfer mismatch, not just the
source selector.

The new timecourse harness is useful because it gives a stable place to inspect
that progression directly rather than inferring it from endpoint summaries.
