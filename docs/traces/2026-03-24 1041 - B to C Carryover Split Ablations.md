# 2026-03-24 1041 - B to C Carryover Split Ablations

## Intent

Follow up on the first `B -> C` carryover bridge result by splitting the
combined scrub into two independent ablations.

The previous bridge showed:

- `full` carryover hurt visible `B -> C`
- `full_context_scrubbed` rescued it strongly

But the scrubbed bundle still mixed three interventions:

- zero carried `context_action:*` substrate values
- clear carried context-credit accumulator state
- remove promoted `context_transform_attractor` patterns

The new question was:

- which part of that stale bundle is actually doing the rescue?

## Change

Extended `scripts/diagnose_b_to_c_carryover_bridge.py` to compare:

1. `none`
2. `substrate`
3. `substrate_context_actions_scrubbed`
4. `substrate_context_patterns_scrubbed`
5. `substrate_context_scrubbed`
6. `full`
7. `full_context_actions_scrubbed`
8. `full_context_patterns_scrubbed`
9. `full_context_scrubbed`

Interpretation of the new split modes:

- `context_actions_scrubbed`
  - zero `context_action:*` keys
  - clear `context_credit_accumulator`
  - keep `context_transform_attractor` patterns

- `context_patterns_scrubbed`
  - remove `context_transform_attractor` patterns
  - keep carried `context_action:*` support
  - keep context-credit accumulator state

The original combined scrub remains for comparison.

Also updated `tests/test_b_to_c_carryover_bridge.py` so the mode inventory and
scrub summaries are locked into the repo.

## Run

Executed:

- `python -m unittest tests.test_b_to_c_carryover_bridge`
- `python -m scripts.diagnose_b_to_c_carryover_bridge --seeds 13 23 37`

Saved artifact:

- `docs/experiment_outputs/2026-03-24_b_to_c_carryover_bridge_split_13_23_37.json`

## Aggregate result

| Mode | Mean exact | Mean bit acc | Delta vs none exact | Delta vs none bit acc |
|---|---:|---:|---:|---:|
| `none` | `10.6667` | `0.6111` | `0.0` | `0.0` |
| `substrate` | `10.3333` | `0.6019` | `-0.3333` | `-0.0093` |
| `substrate_context_actions_scrubbed` | `10.3333` | `0.6019` | `-0.3333` | `-0.0093` |
| `substrate_context_patterns_scrubbed` | `10.6667` | `0.6111` | `0.0` | `0.0` |
| `substrate_context_scrubbed` | `8.3333` | `0.4815` | `-2.3333` | `-0.1296` |
| `full` | `9.0` | `0.5` | `-1.6667` | `-0.1111` |
| `full_context_actions_scrubbed` | `12.6667` | `0.7037` | `+2.0` | `+0.0926` |
| `full_context_patterns_scrubbed` | `9.0` | `0.5` | `-1.6667` | `-0.1111` |
| `full_context_scrubbed` | `15.3333` | `0.8519` | `+4.6667` | `+0.2407` |

## Per-seed pattern

### Seed 13

All modes were effectively identical. This seed remains neutral to the bridge.

### Seed 23

- `full` was bad: `7 / 0.3889`
- `full_context_actions_scrubbed` jumped to `18 / 1.0`
- `full_context_patterns_scrubbed` stayed bad: `7 / 0.3889`
- `full_context_scrubbed` matched the action-only rescue: `18 / 1.0`

### Seed 37

- `full` was mildly positive: `10 / 0.5556`
- `full_context_actions_scrubbed` stayed the same: `10 / 0.5556`
- `full_context_patterns_scrubbed` stayed the same: `10 / 0.5556`
- `full_context_scrubbed` jumped to `18 / 1.0`

The substrate-only side behaved differently:

- seed `37` liked plain `substrate`
- pattern-only scrub preserved that upside
- combined scrub erased it

## Interpretation

This narrows the carryover story substantially.

### 1. The main early rescue comes from scrubbing carried context-action support, not pattern removal alone

The strongest clean signal is seed `23`:

- action-only scrub rescued `full`
- pattern-only scrub did not

That suggests the selector was being dragged most directly by carried
`context_action:*` support and associated context-credit state.

### 2. Removing `context_transform_attractor` patterns alone is not enough

Across the three-seed slice, `full_context_patterns_scrubbed` was effectively
the same as `full`.

So the patterns may still matter, but they are not the dominant harmful signal
by themselves in this visible `B -> C` slice.

### 3. The strongest rescue still needs the combined scrub

Seed `37` did not improve with either split ablation alone, but it did improve
dramatically with the combined scrub.

That suggests at least one mixed case where:

- carried context-action support alone is not the whole problem
- stale patterns alone are not the whole problem
- together they create a reinforcing trap that the combined scrub breaks

### 4. Substrate-only remains a different regime

The substrate-only modes do not follow the same story cleanly.

In particular:

- seed `37` benefited from plain `substrate`
- combined substrate scrub destroyed that benefit

So the bridge conclusion remains specific:

- the clearest harmful bundle is inside full visible `B -> C` carryover
- the substrate-only bridge is not just a weaker version of full carryover

## Best current read

The visible `B -> C` poison is now best described as:

- primarily stale carried context-action support
- with at least some cases where promoted context-transform patterns reinforce
  that stale support enough that both need to be scrubbed together

That is a stronger and more actionable conclusion than the previous generic
“stale structural context carryover” wording.

## Next step

The best next follow-up is no longer another broad bridge sweep.

The next precise question is:

- can we get most of the `full_context_scrubbed` benefit by changing selector
  use of carried context-action support at transfer time, without literally
  deleting it from carryover?

That would keep the intervention closer to REAL’s local-accountability thesis:

- keep carried structure
- but make it more challengeable under task-family mismatch

If that works, the architecture would not need a special carryover export path
to get the benefit.
