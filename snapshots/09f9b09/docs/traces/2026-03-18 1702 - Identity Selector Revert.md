# 2026-03-18 1702 - Identity Selector Revert

## Context

After the downstream latent route gate improved `C3/C4`, I tested a second selector tweak aimed at promoted `C4` cases where `identity` was losing to non-identity transforms despite strong local identity evidence.

The attempted change:

- reduced the context-resolved identity penalty when `history_transform_evidence_identity` was already strong

## Outcome

The tweak improved the narrow identity-scoring corner case, but it was not a net win in quick benchmark reads.

Observed quick spot check with the extra selector tweak still enabled:

- `C3 growth-latent`: aggregate exact `0.2438`, bit `0.5062`
- `C4 growth-latent`: aggregate exact `0.2253`, bit `0.5200`

That compared poorly to the stronger post-route-gate baseline:

- `C3 growth-latent`: aggregate exact `0.2747`, bit `0.5448`
- `C4 growth-latent`: aggregate exact `0.2114`, bit `0.5255`

So the tweak traded away too much `C3` performance for a more ambiguous `C4` effect.

## Decision

Reverted the identity-penalty relaxation and its regression test.

Kept:

- the downstream latent route gate in [adapters.py](C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate\phase8\adapters.py)
- the node probe tooling in [diagnose_c_node_probe.py](C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate\scripts\diagnose_c_node_probe.py)

## Validation

Focused tests after the revert:

- `python -m unittest tests.test_latent_route_transform_gate tests.test_c_node_probe tests.test_latent_growth_gate`

Quick spot checks after the revert:

- `C3 growth-latent`: exact `0.2747`, bit `0.5448`
- `C4 growth-latent`: exact `0.2114`, bit `0.5255`

## Read

The downstream pre-promotion transform gate looks like a real fix.

The later identity-penalty relaxation does not.

That suggests the remaining `C4` difficulty is probably not best attacked by broad identity-favoring selector changes. A more promising direction is likely context-specific branch/transform evidence shaping after promotion, rather than relaxing identity penalties globally.
