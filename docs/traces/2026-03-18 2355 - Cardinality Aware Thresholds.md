# 2026-03-18 2355 - Cardinality Aware Thresholds

## Scope

This trace records a quick follow-up after the post-multicontext rerun suggested that:

- the 4-state latent path was now representable
- but the old binary-tuned confidence thresholds were likely too strict for multi-state competition

## Code Change

`phase8/environment.py` now scales latent effective/promotion thresholds by context cardinality:

- binary tasks keep the original thresholds
- multi-state tasks lower the threshold by `sqrt(2 / context_count)`, clamped at `0.5`

This affects:

- effective latent context activation in `observe_local(...)`
- promotion-ready gating in `LatentContextTracker.snapshot(...)`

The tracker snapshot now also exposes:

- `context_count`
- `context_ids`
- `promotion_threshold`

## Fast Validation

Focused tests passed:

- `python -m unittest tests.test_latent_context_tracker tests.test_multicontext_substrate`

Added regression coverage verifies:

- binary tasks still use threshold scale `1.0`
- 4-state tasks get a lower promotion threshold
- a moderate-confidence 4-state estimate can now become promotion-ready

## Quick Runtime Probe

Targeted `C3` latent slices were rerun first:

- `task_b fixed-latent`: exact `0.2315 -> 0.2963`, bit `0.5694 -> 0.5787`
- `task_c fixed-latent`: exact `0.1852 -> 0.2593`, bit `0.5139 -> 0.5556`

Then a cold-only `C3` sweep was run:

- artifact: `docs/experiment_outputs/c_family_real_diagnostic_c3_seed13_postthresholdscale_cold_20260318.json`

Aggregate deltas vs the immediately previous post-multicontext cold `C3` run:

- `fixed-visible`: unchanged
- `fixed-latent`: exact `0.1945 -> 0.2253`, bit `0.5231 -> 0.5355`
- `growth-visible`: unchanged
- `growth-latent`: exact `0.2191 -> 0.1882`, bit `0.5185 -> 0.4861`

## Current Read

This strengthens the interpretation:

1. the old latent thresholds were indeed too harsh for 4-state competition
2. lowering them helps the fixed-topology latent path
3. but the same relaxation likely lets latent morphogenesis commit too early

That fits the code structure:

- `fixed-latent` benefits from earlier effective context availability
- `growth-latent` also uses `context_promotion_ready` to unblock structural growth
- so the same threshold change can help routing while hurting growth timing

## Recommended Next Step

Do **not** revert the cardinality-aware thresholding yet.

Instead, separate:

- latent routing/support commitment threshold
- latent growth-unlock threshold

That would let `fixed-latent` keep the multistate benefit while keeping `growth-latent` on a stricter confidence gate.
