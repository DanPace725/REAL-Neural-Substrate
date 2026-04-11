# 2026-03-18 1650 - C4 Post Route Gate Spot Check

## Scope

Quick post-route-gate spot check on `C4`, `growth-latent`, `seed=13`.

Artifacts:

- [c_node_probe_c4_taskb_taskc_growth_latent_seed13_postroutegate_20260318.json](C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate\docs\experiment_outputs\c_node_probe_c4_taskb_taskc_growth_latent_seed13_postroutegate_20260318.json)

## Quick read

Cold `C4` seed-13 `growth-latent` spot check:

- `task_a`: exact `0.2315`, bit `0.5324`
- `task_b`: exact `0.1991`, bit `0.5162`
- `task_c`: exact `0.2037`, bit `0.5278`
- aggregate: exact `0.2114`, bit `0.5255`

This is still not “solved,” but it is much healthier than the earlier weak `C4 growth-latent` picture.

## Node-level read

`C4 task_c` after the downstream route gate:

- `n3` route transforms are now mostly `identity` (`18`) with a smaller number of non-identity commits (`rotate_left_1: 3`, `xor_mask_1010: 3`)
- `bud_while_idle_recent_latent_cycles` is `0` on all probed nodes
- late non-identity `n3` commits happen with promoted latent state, not under ambiguous latent context

Examples from `n3 task_c`:

- cycle `23`: latent confidence `0.96117`, effective confidence `0.96117`, promotion-ready `1.0`, action `route_transform:n10:rotate_left_1`
- cycle `34`: latent confidence `0.93590`, effective confidence `0.93590`, promotion-ready `1.0`, action `route_transform:n9:xor_mask_1010`
- cycle `40`: latent confidence `0.86592`, effective confidence `0.86592`, promotion-ready `1.0`, action `route_transform:n9:xor_mask_1010`

So the remaining `C4` difficulty no longer looks dominated by premature downstream transform commitment under ambiguous latent state. What remains is likely a harder routing/control problem after context has already resolved.

## Current interpretation

The downstream route gate appears to fix a real `C3` failure mode and also improves `C4`, but `C4` now looks like a different class of problem:

- less about early ambiguous commitment
- more about which promoted transform/branch gets selected once the deeper controller has already resolved
