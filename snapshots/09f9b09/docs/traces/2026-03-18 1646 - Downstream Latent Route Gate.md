# 2026-03-18 1646 - Downstream Latent Route Gate

## Context

The `C3` node probe showed a downstream selector failure on `growth-latent`:

- `n3 task_c` repeatedly chose `route_transform:n9:xor_mask_1010`
- those choices happened while the node had a packet and latent context was available
- but latent confidence was still below promotion, so context had not stabilized enough to justify hard transform commitment

This suggested that downstream nodes were being allowed to commit non-identity transforms too early under ambiguous latent state.

## Change

Added a narrow action-availability gate in [adapters.py](C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate\phase8\adapters.py):

- applies only to downstream nodes (`node_id != source_id`)
- only when the head packet has a task but no visible context
- only when latent context is available but `context_promotion_ready < 0.5`
- suppresses non-identity `route_transform:*` actions during that ambiguous window
- keeps `route:*` and `route_transform:*:identity` available
- does not affect the source pre-promotion latent-routing path

Added focused coverage in [test_latent_route_transform_gate.py](C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate\tests\test_latent_route_transform_gate.py).

## Validation

Focused tests passed:

- `python -m unittest tests.test_latent_route_transform_gate tests.test_c_node_probe tests.test_latent_growth_gate`

Updated node probe artifact:

- [c_node_probe_c3_taskb_taskc_growth_latent_seed13_postroutegate_20260318.json](C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate\docs\experiment_outputs\c_node_probe_c3_taskb_taskc_growth_latent_seed13_postroutegate_20260318.json)

Observed local behavior change:

- previously, `n3 task_c` repeatedly committed `xor_mask_1010` while latent context remained below promotion
- after the gate, the ambiguous window falls back to `identity` instead of hard non-identity commitment

Example late `n3 task_c` actions after the change:

- cycle `30`: `route_transform:g1:identity`, latent confidence `0.45505`, promotion-ready `0.0`
- cycle `31`: `route_transform:g1:identity`, latent confidence `0.51928`, promotion-ready `0.0`

## Quick benchmark read

Cold `C3` seed-13 `growth-latent` spot check with `_run_real_method`:

- `task_a`: exact `0.3241`, bit `0.5787`
- `task_b`: exact `0.2407`, bit `0.5139`
- `task_c`: exact `0.2593`, bit `0.5417`
- aggregate: exact `0.2747`, bit `0.5448`

Compared to the earlier post-growth-gate quick check:

- prior aggregate exact `0.1944`, bit `0.4877`
- current aggregate exact `0.2747`, bit `0.5448`

The biggest change is `task_c`, which improved from exact `0.1296` / bit `0.4213` to exact `0.2593` / bit `0.5417`.

## Current read

This strongly supports the hypothesis that a meaningful part of late Family C failure was downstream premature transform commitment under ambiguous latent state, not just insufficient morphogenesis or insufficient latent cardinality.
