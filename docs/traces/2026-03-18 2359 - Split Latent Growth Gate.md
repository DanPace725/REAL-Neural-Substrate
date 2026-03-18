# 2026-03-18 2359 - Split Latent Growth Gate

## Scope

This trace records the follow-up change after the cardinality-aware threshold work:

- latent routing/support commitment keeps the relaxed multistate threshold
- morphogenesis now uses a separate stricter latent growth gate

## Code Change

`phase8/environment.py` now distinguishes:

- `context_promotion_ready`
  - used for latent routing/support commitment
  - can become true under the cardinality-aware multistate threshold
- `context_growth_ready`
  - used only by the morphogenesis gate
  - remains tied to the stricter base promotion threshold

Tracker snapshots now expose:

- `growth_promotion_threshold`
- `growth_ready`

And the growth gate now blocks latent budding when `context_growth_ready < 0.5`, rather than when `context_promotion_ready < 0.5`.

## Fast Validation

Focused tests passed:

- `python -m unittest tests.test_latent_context_tracker tests.test_multicontext_substrate tests.test_latent_growth_gate`

The new growth-gate test verifies the intended separation:

- a multistate latent estimate can be routing-promotion-ready
- while still not growth-ready
- and growth proposals remain blocked in that case

## Quick Runtime Read

Targeted `C3` latent probes after the gate split:

- `task_b fixed-latent`: `0.2963 / 0.5787`
- `task_c fixed-latent`: `0.2593 / 0.5556`
- `task_b growth-latent`: `0.1759 / 0.4861`
- `task_c growth-latent`: `0.1944 / 0.4954`

A cold-only `C3` sweep was rerun:

- artifact: `docs/experiment_outputs/c_family_real_diagnostic_c3_seed13_postgrowthgate_cold_20260318.json`

Result:

- no aggregate change relative to the immediately previous post-threshold-scale cold `C3` run

Interpretation:

- the gate split is architecturally correct
- but its effect is not visible on this cold-only `C3` slice
- the `growth-latent` regression is likely showing up more in transfer or longer growth-active regimes than in cold-start `C3`

## Recommended Next Step

If we keep avoiding long runs, the next high-signal move is not another broad benchmark.

Instead:

1. instrument when `context_promotion_ready` and `context_growth_ready` first fire during `growth-latent C3`
2. inspect whether growth actually buds before the latent estimate stabilizes on the transfer path
3. only then rerun the smallest transfer slice that is likely to expose the timing issue
