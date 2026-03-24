# 2026-03-24 1049 - Selector Time Carryover Challenge Probe

## Intent

Test whether the `B -> C` carryover-bridge rescue could be approximated by a
selector-time intervention instead of a special carryover export path.

The split-ablation result had already suggested:

- the strongest harmful signal in visible `B -> C` is carried
  `context_action` support
- removing that support from full carryover helps a lot

So the next question was:

- can the selector locally challenge stale carried `context_action` support
  hard enough during transfer mismatch that we recover the same benefit without
  deleting state from carryover?

## Change

Updated `phase8/selector.py` so that discounted context-specific support no
longer leaks back into the main `action_support` path during route scoring.

Before this pass:

- `_effective_context_action_support(...)` could down-weight carried
  `context_action` support
- but `action_support` still came from `substrate.action_support(...)`, which
  already folds context-specific support back into the transform score

This meant stale context support could still influence:

- the main `action_support_term`
- candidate-evidence comparison in competition logic

The patch changed the selector to use:

- `raw_action_support` for diagnostics
- `effective_action_support` for scoring under explicit context

and added a focused regression in `tests/test_phase8_recognition.py` proving
that stale contextual support is now reduced in the effective action-support
path during transfer.

## Validation

Executed:

- `python -m unittest tests.test_phase8_recognition tests.test_b_to_c_carryover_bridge`

All targeted tests passed.

## Probe

Reran the bridge sweep:

- `python -m scripts.diagnose_b_to_c_carryover_bridge --seeds 13 23 37`

Saved artifact:

- `docs/experiment_outputs/2026-03-24_b_to_c_carryover_bridge_split_13_23_37_postselector.json`

## Result

The bridge aggregate did **not** change materially.

Key unchanged lines:

- `full`: `9.0` exact, `0.5` bit accuracy
- `full_context_actions_scrubbed`: `12.6667` exact, `0.7037`
- `full_context_scrubbed`: `15.3333` exact, `0.8519`

So the selector-time challenge patch was structurally correct, but it did not
reproduce the carryover-export ablation benefit on the actual `B -> C` slice.

## Interpretation

This is a useful negative result.

It suggests that the carryover-export rescue is not explained solely by one
selector leak in the route score.

The remaining gap is likely one of:

1. stale carried context-action support still affects behavior through another
   path not yet challenged strongly enough by the selector
2. the rescue depends on early-run adaptation dynamics across multiple cycles,
   not just first-pass route scoring
3. the combined bridge is altering downstream structural competition in a way
   the current selector-time patch does not yet reproduce

The per-context summaries reinforce that the problem is not uniform:

- seed `23`, `full`: `context_1` is a pure branch failure
  (`route_wrong_transform_potentially_right = 8`)
- seed `37`, `full`: `context_1` is a pure wrong-transform-family failure
  (`wrong_transform_family = 8`)

That makes the remaining issue broader than a single stale-transform term.

## Best current read

The export ablation remains the strongest explanatory tool.

The selector-time patch improves correctness of the scoring contract, but it
does not yet recover the visible `B -> C` transfer benefit by itself.

So the next selector-side step, if taken, should probably target:

- branch-sensitive visible transfer competition
- or multi-cycle transfer adaptation dynamics

rather than only stronger scalar suppression of carried context-action support.
