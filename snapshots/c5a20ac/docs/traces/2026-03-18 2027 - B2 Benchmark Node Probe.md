# 2026-03-18 2027 - B2 Benchmark Node Probe

## Context

This trace records a focused diagnostic step for the `B2` self-selected failure mode.

The immediate goal was not to tune the controller again. It was to reuse the repo's existing probe style and create a short-run benchmark-level node probe that can inspect `B2` directly, especially at the source node where self-selected latent recruitment is decided.

## Code Changes

Added [diagnose_benchmark_node_probe.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/scripts/diagnose_benchmark_node_probe.py):

- generic benchmark probe for generated ceiling benchmarks
- supports `fixed-visible`, `fixed-latent`, `growth-visible`, `growth-latent`, and `self-selected`
- defaults to including the source node in `focus_nodes`
- records per-cycle source-sequence, latent-capability, visible-trust, and route-choice fields
- reads source diagnostics from the same focus-packet path the capability controller uses, instead of relying only on the source inbox

Added [test_benchmark_node_probe.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/tests/test_benchmark_node_probe.py):

- smoke test for `B2` + `task_a` + `self-selected`

## Validation

Focused test:

```powershell
$env:PYTHONPATH='C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate;C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate\scripts;C:\Users\nscha\AppData\Roaming\Python\Python313\site-packages'; C:\Python313\python.exe -m unittest tests.test_benchmark_node_probe
```

Result: `OK`

Short probe comparisons run:

- `B2` / `task_a` / seed `13` / `self-selected` / `40` cycles
- `B2` / `task_a` / seed `13` / `fixed-visible` / `40` cycles

## Probe Readout

`self-selected` on `B2` for the first `40` cycles:

- exact matches: `14 / 108` (`0.12963`)
- latent recruitment cycles: `[31]`
- source first sequence-available cycle: `2`
- source first latent-context-available cycle: `28`
- source first latent-capability-enabled cycle: `31`
- source mean sequence confidence: `0.92625`
- source mean latent-context confidence: `0.32500`
- source top actions:
  - `route_transform:n1:xor_mask_1010`: `33`
  - `route_transform:n1:rotate_left_1`: `3`
  - `route_transform:n2:xor_mask_1010`: `4`

`fixed-visible` on the same short run:

- exact matches: `13 / 108` (`0.12037`)
- no latent recruitment
- source top actions are almost the same:
  - `route_transform:n1:xor_mask_1010`: `36`
  - `route_transform:n1:rotate_left_1`: `3`
  - `route_transform:n2:xor_mask_1010`: `1`

## Interpretation

The key result is that `B2` does not currently look like an inference failure first.

The source node in `self-selected` is building strong sequence confidence very early and eventually reaches strong latent-capability support, but the route/transform policy remains almost the same as `fixed-visible`. In other words:

- latent evidence is present
- latent recruitment does happen
- but recruited latent does not yet redirect behavior in a way that improves `B2`

That suggests the next `B2` investigation should focus on the *use path* from latent estimate to route/transform choice, not only on earlier activation thresholds.

## Follow-Up

Two follow-ups now look especially worthwhile:

1. compare source latent estimate versus chosen transform over time on `B2` to see whether latent state and transform hint disagree
2. inspect whether `B2` is being funneled through task-transform affinity or visible-context priors even after latent capability is enabled

This is also consistent with the existing note in [2026-03-18 2145 - Latent Context Generalization.md](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/docs/traces/2026-03-18%202145%20-%20Latent%20Context%20Generalization.md): B-family hidden-memory tasks likely still sit on an older sequence-summary path that is not yet fully aligned with the newer latent-control surfaces.
