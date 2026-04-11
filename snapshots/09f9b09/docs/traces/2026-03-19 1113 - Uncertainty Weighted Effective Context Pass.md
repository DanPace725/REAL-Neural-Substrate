# 2026-03-19 1113 - Uncertainty Weighted Effective Context Pass

## Context

The previous selector reading suggested that `C3` was snapping into a resolved effective context too readily. Once that happened, the selector shifted into a task-affinity + history + contextual-support regime that strongly reinforced `rotate_left_1`.

From the REAL perspective, that looked a bit too discrete for a multistate ambiguous task. The next nudge was to keep multistate latent context more uncertainty-weighted before it hardens into `effective_has_context`.

## Change

Updated [phase8/environment.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/environment.py).

Added `_latent_resolution_weight(...)`, which applies only to multistate latent contexts (`context_count > 2`).

It discounts the confidence used for `effective_has_context` when:

- the high-confidence sequence context estimate disagrees with the current latent estimate
- or channel-level context estimates disagree with the current latent estimate

Binary tasks are left unchanged.

Important boundary:

- this does **not** change the raw latent tracker confidence
- it only changes how confidently latent state is promoted into the selector-facing `effective_context_*` fields

Also exposed `latent_resolution_weight` in local observation for easier diagnostics.

## Focused Tests

Added [tests/test_phase8_context_uncertainty.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/tests/test_phase8_context_uncertainty.py) covering:

- multistate disagreement softens effective context enough to suppress promotion
- multistate agreement preserves promotion
- binary tasks ignore this uncertainty discount

Validation:

```powershell
$env:PYTHONPATH='C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate;C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate\scripts;C:\Users\nscha\AppData\Roaming\Python\Python313\site-packages'; C:\Python313\python.exe -m unittest tests.test_phase8_context_uncertainty tests.test_phase8_capability_prediction tests.test_benchmark_node_probe
```

Result: `OK`

## Smoke Result

Re-ran the same small `A1/B2/C3` self-selected slice on `task_a`, seed `13`.

### Before this pass

- `A1`: `0.0556`, gap `0.5000`
- `B2`: `0.5648`, gap `0.1296`
- `C3`: `0.2222`, gap `0.1111`
- aggregate mean gap: `0.2469`

### After this pass

- `A1`: `0.0556`, gap `0.5000`
- `B2`: `0.5648`, gap `0.1296`
- `C3`: `0.2315`, gap `0.1018`
- aggregate mean gap: `0.2438`

So the visible result is small but real:

- `C3` improved slightly
- `A1` and `B2` stayed unchanged on this slice

## C3 Probe Read

Updated `C3` source summary after the pass:

- first latent capability cycle: `46`
- first effective context cycle: still `null`
- route transform counts:
  - `rotate_left_1`: `60`
  - `xor_mask_1010`: `18`
  - `xor_mask_0101`: `2`
- pre-sequence guidance match rate: `0.34615`

Compared to the earlier post-prediction-coupling probe:

- `rotate_left_1` usage dropped slightly
- `xor_mask_1010` usage rose slightly
- self-selected exact improved slightly

This is consistent with the intended mechanism:

- keep ambiguous multistate context from collapsing too quickly
- preserve more room for competing evidence to shape choice

## Interpretation

This was a good theoretical nudge:

- it matches the REAL framing better than a harder binary commit
- it preserves the multicontext C-task direction
- and it produced a modest `C3` gain without changing binary-task behavior

The effect is still small, which suggests the broader bottleneck remains:

- selector integration after latent activation / partial context resolution

But this pass moved the system in a more principled direction and did so safely.

## Best Next Step

If we continue on this thread, the next narrow move should probably be:

- keep sequence evidence partially live even after partial effective context emerges on multistate tasks

That would complement this pass:

- this pass made context resolution softer
- the next pass would make the competing evidence remain influential longer
