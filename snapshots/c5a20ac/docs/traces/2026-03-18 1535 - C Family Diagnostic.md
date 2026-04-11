# 2026-03-18 1535 - C Family Diagnostic

## Scope

This note consolidates what the repo currently shows about the March 18 ceiling-benchmark C family, how it differs from the earlier Task C experiments, and where REAL appears to struggle.

## Most Recent Relevant Tests

The newest benchmark work is the March 18 ceiling harness and 3-seed pilot:

- `docs/traces/2026-03-18 1200 - Ceiling Benchmark Harness.md`
- `docs/traces/2026-03-18 1248 - Ceiling Benchmark 3-Seed Pilot.md`
- `docs/experiment_outputs/ceiling_benchmark_pilot_family_c_20260318.json`

These runs tested the generated ambiguity ladder `C1-C4`, not just the original named `cvt1_task_c_*` scenarios.

## What The C Family Actually Tested

The C family in `scripts/ceiling_benchmark_suite.py` is a modified ambiguity ladder:

- `C1`: 30-node / 108-packet generated ambiguity task with a 4-state hidden controller collapsed to a 2-state visible label, but the visible label still perfectly determines the transform.
- `C2`: 30-node / 108-packet task where one visible branch is ambiguous across multiple transforms.
- `C3`: 30-node / 108-packet task where both visible branches are ambiguous.
- `C4`: 50-node / 216-packet task where the visible context bit is intentionally scrambled and only weakly predicts the transform.

This means the late C-family points are not just "harder Task C". They are progressively weaker-observation inference problems.

## Capability Coverage In The March 18 Pilot

Cold-start methods actually run in the pilot:

- REAL `fixed-visible`
- REAL `fixed-latent`
- REAL `growth-visible`
- NN `mlp-explicit`
- NN `mlp-latent`
- NN `elman`
- NN `gru`
- NN `lstm`
- NN `causal-transformer`

Important omissions:

- Transfer was skipped entirely in the March 18 pilot.
- There is no `growth-latent` REAL mode in the ceiling harness.
- The C-family ambiguity tasks were not run through the older paired latent+morphogenesis or large-topology transfer harnesses.

So the answer to "were Transfer and Morphogenesis applied to the March 18 C family tests?" is:

- Morphogenesis: partially, via `growth-visible` only.
- Transfer: no, not in the recorded pilot.
- Full "all capabilities" coverage: no.

## Where REAL Struggled In The Pilot

Family-C aggregate cold-start results from `ceiling_benchmark_pilot_family_c_20260318.json`:

| Benchmark | REAL method | Mean exact | Mean bit acc | Criterion rate |
|---|---|---:|---:|---:|
| C1 | fixed-visible | 0.4321 | 0.6384 | 0.5556 |
| C1 | fixed-latent | 0.2500 | 0.5494 | 0.2222 |
| C1 | growth-visible | 0.4239 | 0.6183 | 0.5556 |
| C2 | fixed-visible | 0.4033 | 0.6116 | 0.5556 |
| C2 | fixed-latent | 0.2243 | 0.5324 | 0.0000 |
| C2 | growth-visible | 0.2932 | 0.5545 | 0.3333 |
| C3 | fixed-visible | 0.2047 | 0.4902 | 0.0000 |
| C3 | fixed-latent | 0.2202 | 0.5334 | 0.0000 |
| C3 | growth-visible | 0.2047 | 0.4840 | 0.0000 |
| C4 | fixed-visible | 0.1811 | 0.5067 | 0.0000 |
| C4 | fixed-latent | 0.1749 | 0.5072 | 0.0000 |
| C4 | growth-visible | 0.1574 | 0.4825 | 0.0000 |

Weakest region:

- `C4 growth-visible`: bit accuracy `0.4825`, exact `0.1574`
- `C3 growth-visible`: bit accuracy `0.4840`, exact `0.2047`
- `C3 fixed-visible`: bit accuracy `0.4902`, exact `0.2047`

Interpretation:

- REAL is still clearly above the NN exact-match rates on `C1-C2`.
- From `C3` onward, REAL stops hitting criterion and drifts toward chance-level bit accuracy.
- `growth-visible` is not helping on the hard ambiguity points, which fits the earlier repo pattern: morphogenesis helps routing-headroom problems more than observation-identifiability problems.

## Why The C Ladder Gets So Hard

The hidden controller is computed from the parity of the previous two packets. The visible context bit becomes less and less informative across the ladder.

Exact transform predictiveness of the visible context label:

### C1

- `task_a`: `ctx0 -> rotate_left_1` (55/55), `ctx1 -> xor_mask_1010` (53/53)
- `task_b`: `ctx0 -> rotate_left_1` (55/55), `ctx1 -> xor_mask_0101` (53/53)
- `task_c`: `ctx0 -> xor_mask_1010` (55/55), `ctx1 -> xor_mask_0101` (53/53)

### C2

- `ctx1` still perfectly identifies one transform.
- `ctx0` becomes mixed:
  - `task_a`: `xor_mask_0101` 36/55 vs `rotate_left_1` 19/55
  - `task_b`: `xor_mask_1010` 36/55 vs `rotate_left_1` 19/55
  - `task_c`: `rotate_left_1` 36/55 vs `xor_mask_1010` 19/55

### C3

- Both visible branches are ambiguous.
- Example `task_c`:
  - `ctx0`: `rotate_left_1` 36/55 vs `xor_mask_1010` 19/55
  - `ctx1`: `xor_mask_0101` 36/53 vs `identity` 17/53

### C4

- The visible context is intentionally scrambled.
- Top transform frequency is only about 37-40% per visible branch:
  - `task_c ctx0`: `xor_mask_0101` 42/110
  - `task_c ctx1`: `rotate_left_1` 39/106

Working read: `C4` is no longer mainly a routing or scale challenge. It is a weak-observation latent-inference task where the visible bit is almost a distractor.

## What The NNs Did

The NNs also failed to solve the C family in the one-pass online regime. They generally remained well below criterion and low in exact match.

Important nuance:

- On `C3-C4`, several NNs slightly exceed REAL on mean bit accuracy while remaining much worse on exact match.
- That suggests bitwise hedging rather than discrete transform selection.
- REAL is still choosing the full transform correctly more often, but not often enough to separate cleanly under the ceiling rule.

So "all NNs failed" is basically true for criterion, but it does not imply the current C ladder cleanly isolates a uniquely REAL-specific failure mode.

## What Earlier Task C Experiments Already Showed

The older March 17 work did exercise transfer and morphogenesis around the original named Task C family:

- Sequential transfer trace: `A -> B -> C` and `A -> C` both reached `7.6 / 18` exact on the small topology.
- Large-topology morphogenesis trace: `cvt1_task_c_large` fixed `17.0 / 36`, growth `16.0 / 36` (visible); paired latent run improved the fixed baseline to `18.4 / 36` and reduced the morphogenesis penalty to `-0.2`.

That older evidence says:

- Task C itself is not generically broken for REAL.
- Morphogenesis is usually neutral-to-negative on already-strong Task C settings.
- Latent mode can help Task C when the visible label is less reliable.

## Exploratory REAL-Only Transfer Check On Hard Modified C Points

A lightweight one-seed (`seed=13`) exploratory run was executed directly against the generated `C3-C4` benchmark points to see whether carryover helps `task_a -> task_c` on the modified ambiguity ladder.

| Benchmark | Method | Cold task_c exact / bit | Warm A->C exact / bit |
|---|---|---:|---:|
| C3 | fixed-visible | 0.2222 / 0.5324 | 0.2130 / 0.5231 |
| C3 | fixed-latent | 0.1944 / 0.5463 | 0.2130 / 0.5972 |
| C3 | growth-visible | 0.1667 / 0.4907 | 0.2407 / 0.5509 |
| C4 | fixed-visible | 0.1574 / 0.5046 | 0.1898 / 0.4931 |
| C4 | fixed-latent | 0.1157 / 0.4977 | 0.1574 / 0.4421 |
| C4 | growth-visible | 0.1574 / 0.4884 | 0.1435 / 0.5025 |

This is only an exploratory seed, but the pattern is already informative:

- Warm carryover is mixed, not uniformly rescuing the ambiguity ladder.
- `C3` shows some upside for latent or growth transfer.
- `C4` remains unstable and does not show a clean transfer benefit.

## Current Working Hypothesis

The main problem is probably not "REAL cannot do Task C". The likely issue is that the generated late C-family points combine multiple difficulty sources at once:

1. transform ambiguity
2. hidden-state depth
3. degraded visible observability
4. scale increase at `C4`

That makes `C3-C4` closer to an identifiability stress test than to the earlier transferable Task C family. In that regime:

- morphogenesis has little reason to help because the bottleneck is not mainly routing headroom
- visible-mode learning loses its clean supervision signal
- one-pass neural baselines hedge instead of committing
- transfer may help only when prior structure aligns with the hidden controller in a very specific way

## Recommended Next Experiments

1. Add a transfer-inclusive C-family diagnostic run for `C3-C4` over 3 seeds, but REAL-only first.
2. Add a `growth-latent` ceiling mode so the ambiguity ladder actually covers the strongest current REAL path for weak-observation tasks.
3. Split late-family difficulty axes:
   - one ladder for hidden-state depth with reliable visible labels
   - one ladder for scrambled visible labels without simultaneous scale increase
4. Add a same-task scale sweep for the modified C task itself, instead of jumping from 30-node ambiguity to 50-node scrambled ambiguity.
5. If the paper goal is a clean REAL ceiling, make one harsher family where NNs still have a learnable signal but REAL's local substrate specifically runs out of sequential context-tracking capacity.
