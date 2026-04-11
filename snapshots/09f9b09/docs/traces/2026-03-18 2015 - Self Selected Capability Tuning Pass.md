# 2026-03-18 2015 - Self Selected Capability Tuning Pass

## Context

This trace captures a focused tuning pass on the Phase 8 `self-selected` capability controller after the lightweight smoke harness exposed a specific failure shape:

- `A1` needed to stay visible-first and avoid unnecessary latent recruitment
- `C3` needed earlier and more durable latent recruitment
- `B2` remained the awkward case, because it wants local ambiguity sensitivity without drifting away from the fixed-visible cold-start behavior

The goal of this pass was not to optimize the full ceiling suite. It was to make a small, inspectable controller adjustment and check whether the `A1/B2/C3` smoke slice moved in the expected direction.

## Code Changes

Updated [phase8/environment.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/environment.py):

- added `CAPABILITY_LATENT_IDLE_TASK_WINDOW = 12`
- changed `_recent_latent_task_summary()` so recent latent task confidence persists across sparse observations instead of dropping out after a single idle cycle
- exposed a `recency_weight` in the recent latent summary
- changed self-selected capability updates to use an age-weighted `effective_latent_confidence`
- increased the influence of durable latent confidence on latent recruitment pressure and latent support
- kept `A1` protection by leaving visible reliability suppression intact

Updated [tests/test_phase8.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/tests/test_phase8.py):

- added a regression test that the source can track latent evidence before visible context is suppressed
- added a regression test that recent latent task state persists across sparse observations

## Tuning Notes

One additional experiment temporarily raised `latent_activation_threshold` from `0.44` to `0.50`. That made `B2` slightly worse without improving `C3`, so it was reverted in the final state. The repo is left on the better persistence-based variant, not the stricter-threshold variant.

## Validation

Focused tests:

```powershell
$env:PYTHONPATH='C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate;C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate\scripts;C:\Users\nscha\AppData\Roaming\Python\Python313\site-packages'; C:\Python313\python.exe -m unittest tests.test_phase8.TestCapabilityControl
```

Result: `OK` (`6` tests)

Lightweight smoke check:

```powershell
$env:PYTHONPATH='C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate;C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate\scripts;C:\Users\nscha\AppData\Roaming\Python\Python313\site-packages'; @'
from scripts.compare_self_selected_smoke import evaluate_self_selected_smoke
report = evaluate_self_selected_smoke(benchmark_ids=["A1", "B2", "C3"], task_keys=["task_a"], seeds=[13])
print(report["aggregate"])
'@ | C:\Python313\python.exe -
```

Final smoke results on the reverted persistence-tuned state:

- `A1`: oracle `fixed-visible`, self-selected oracle gap `0.0000`, latent recruitment `[]`, growth recruitment `[]`
- `B2`: oracle `fixed-visible`, self-selected oracle gap `0.4722`, latent recruitment `[31]`, growth recruitment `[]`
- `C3`: oracle `fixed-latent`, self-selected oracle gap `0.2963`, latent recruitment `[33]`, growth recruitment `[]`
- aggregate mean self-selected oracle gap: `0.2562`

## Interpretation

This pass improved the controller in one important way: `C3` now ends with durable latent support instead of collapsing back to zero at the end of the run. The source-side capability state for `C3` now remains strongly latent-enabled, which is much closer to the intended ambiguity-handling behavior.

`A1` remains clean, which matters because it means the persistence change did not reopen the earlier “latent everywhere” failure.

`B2` is still the main unresolved problem. The controller now recruits latent earlier than before, but that recruitment does not improve benchmark performance and may still be arriving for the wrong local reasons. The next tuning loop should probably target *why* `B2` crosses latent activation at all, rather than continuing to add more latent persistence globally.
