# 2026-03-18 1815 - C Family Credit Debt Evaluation

## Why This Probe

The remaining `C3/C4` failures were no longer dominated by pre-promotion latent mistakes after the downstream latent route gate landed. Node probes showed a different pattern on late Family C:

- downstream nodes were often reaching resolved latent context
- many resolved feedback events were landing at `bit_match_ratio = 0.5`
- those partial matches were frequently on the transform expected for the resolved context
- the existing low-match path still treated those cases almost like transform contradictions

That was a poor fit for generated Family C, where a node can choose the correct transform under the correct latent context and still receive only partial end-to-end credit because a later hop or later branch goes wrong.

## Code Change

Three related adjustments were made:

1. In `phase8/environment.py`, resolved low-match feedback now distinguishes:
   - transform-aligned partial matches
   - true transform/context contradictions

2. For transform-aligned partial matches:
   - generic and context transform credit are preserved more strongly
   - transform/context transform debt is not allowed to spike
   - branch-side debt can still accumulate, because the remaining path may still be locally wrong at the branch level

3. In `phase8/substrate.py`, `record_context_feedback()` now accepts `aligned_transform`.
   - aligned partial matches no longer wipe the context credit accumulator with the old `* 0.2` collapse
   - contextual action support is demoted more gently
   - promotion progress can survive alternating `1.0` and `0.5` resolved outcomes

`phase8/node_agent.py` now forwards the alignment flag from feedback events into the substrate.

## Sanity Checks

Focused tests that still run without the neural-baseline import path passed:

- `python -m unittest tests.test_latent_route_transform_gate tests.test_c_node_probe tests.test_latent_growth_gate`

Direct spot checks of the new regression scenarios also matched the intended behavior:

- substrate aligned partial:
  - support `0.4447 -> 0.3736`
  - accumulator `0.5675 -> 0.5288`
- environment aligned partial on `ceiling_c4_task_c` / `context_3` / `identity`:
  - `transform_matches_context = True`
  - transform debt stayed at `0.0`
  - context transform debt stayed at `0.0`
  - branch-side debts increased (`0.0770`, `0.1045`, `0.1210`)

`tests.test_phase8` could not be run end-to-end in this shell because its neural-baseline import chain still fails to import `numpy`, even though the package appears to be installed in the user site. That looks environmental rather than specific to this patch.

## Quick C-Family Read

Saved artifact:

- `docs/experiment_outputs/c_family_credit_debt_spotcheck_20260318.json`

Seed `13`, cold-only, latent modes:

- `C3 fixed-latent`: exact `0.3704`, bit `0.6235`
- `C3 growth-latent`: exact `0.3426`, bit `0.5910`
- `C4 fixed-latent`: exact `0.3179`, bit `0.5887`
- `C4 growth-latent`: exact `0.3102`, bit `0.5749`

Compared with the earlier quick spot checks, this is a substantial improvement, especially on the late `task_c` cases that motivated the investigation:

- `C3 growth-latent task_c`: `0.2593 -> 0.3333` exact
- `C4 growth-latent task_c`: `0.2037 -> 0.3565` exact
- `C4 fixed-latent task_c`: now `0.3519` exact, `0.6435` bit

## Current Read

The credit/debt path was part of the problem.

The remaining late Family C difficulty no longer looks like a simple inability to resolve latent context. REAL was already reaching resolved context downstream; it was then over-penalizing partially successful, context-aligned actions and failing to let that local evidence consolidate into durable contextual support.

This patch does not solve all of `C3/C4`, but it materially improves the exact failure mode we were seeing and gives stronger support to the view that late Family C was stressing the local credit-assignment machinery, not just the latent-context estimator.
