# 2026-03-24 1033 - B to C Carryover Bridge

## Intent

Follow up on the March 19 `B -> C` carryover diagnosis with a more surgical
bridge test.

The open question was no longer whether carryover can hurt `B -> C`. That was
already established. The narrower question was:

- if we keep the useful parts of warm state but scrub the suspected stale
  context-transform structure, does `B -> C` recover?

This was meant to separate:

- harmful structural context carryover
- potentially useful episodic carryover
- the already-known cold-start baseline

## Implementation

Added:

- `scripts/diagnose_b_to_c_carryover_bridge.py`
- `tests/test_b_to_c_carryover_bridge.py`

The new diagnostic trains on `cvt1_task_b_stage1`, then compares five transfer
modes on `cvt1_task_c_stage1`:

1. `none`
2. `substrate`
3. `substrate_context_scrubbed`
4. `full`
5. `full_context_scrubbed`

The scrubbed modes copy the saved carryover and then selectively remove:

- all `context_action:*` support values from the node substrate snapshot
- all stored context-credit accumulator entries
- all promoted patterns with source `context_transform_attractor`

Everything else is preserved, including the difference between substrate-only
and full episodic carryover.

The harness records:

- first source-node transfer decision for `context_0` and `context_1`
- full transfer-run summary
- transfer metrics from `compare_task_transfer.py`
- aggregate cross-seed mode comparison

## Run

Executed:

- `python -m unittest tests.test_b_to_c_carryover_bridge tests.test_b_to_c_carryover_diagnosis`
- `python -m scripts.diagnose_b_to_c_carryover_bridge --seeds 13 23 37`

Saved artifact:

- `docs/experiment_outputs/2026-03-24_b_to_c_carryover_bridge_13_23_37.json`

## Result

Aggregate over seeds `13, 23, 37`:

| Mode | Mean exact | Mean bit acc | Delta vs none exact | Delta vs none bit acc |
|---|---:|---:|---:|---:|
| `none` | `10.6667` | `0.6111` | `0.0` | `0.0` |
| `substrate` | `10.3333` | `0.6019` | `-0.3333` | `-0.0093` |
| `substrate_context_scrubbed` | `8.3333` | `0.4815` | `-2.3333` | `-0.1296` |
| `full` | `9.0` | `0.5` | `-1.6667` | `-0.1111` |
| `full_context_scrubbed` | `15.3333` | `0.8519` | `+4.6667` | `+0.2407` |

Per-seed behavior:

- seed `13`: all modes were effectively the same
- seed `23`: `full_context_scrubbed` rose from `7 / 0.3889` under `full` to
  `18 / 1.0`
- seed `37`: `full_context_scrubbed` rose from `10 / 0.5556` under `full` to
  `18 / 1.0`

The scrub operation itself was substantial on the saved carryover:

- `288` zeroed context-action keys
- `12` cleared context-credit entries
- `11` removed `context_transform_attractor` patterns

## Interpretation

This result is much stronger than the earlier hygiene pass.

The most important pattern is:

- `full` is worse than `none`
- `full_context_scrubbed` is much better than both

That strongly supports the view that the damaging part of warm `B -> C` is not
carryover in general. It is stale structural context-transform carryover.

At the same time, the fact that `full_context_scrubbed` beats `none` while
`substrate_context_scrubbed` does not suggests that useful episodic or other
non-scrubbed carried state still matters once the stale structural poison is
removed.

So the current best read is:

- stale promoted context-transform structure is the main poison on visible
  `B -> C`
- full carryover still contains something useful after that poison is removed
- substrate-only is too blunt a bridge for this slice

This aligns with the large-topology bridge story from March 17:

- the winning bridge is likely between naive full carryover and broad
  substrate-only carryover, not at either endpoint

## Next Step

The next highest-signal follow-up is to make the bridge more selective rather
than broader:

1. split the scrub into two independent ablations:
   - zero context-action supports only
   - remove `context_transform_attractor` patterns only
2. rerun the same `13/23/37` slice
3. check which component is doing most of the rescue

That should tell us whether the next architectural move belongs in:

- structural carryover filtering
- selector-time compatibility scaling
- or a more explicit carryover-mode split for visible transfer
