# 2026-03-19 1028 - Self Selected Rebaseline After Anticipation and Carryover

## Why

The original session goal was to move Phase 8 away from externally chosen REAL modes and toward endogenous capability recruitment:

- latent-context inference recruited when local ambiguity warrants it
- morphogenesis recruited when local structural pressure and stabilization warrant it

Since that initial self-selected work, the repo changed in two relevant ways:

1. `real_core` gained explicit recognition and prediction support
2. Phase 8 transfer/carryover selection was cleaned up, especially for visible-task compatibility during transfer

This trace re-runs the original lightweight `A1/B2/C3` self-selected smoke slice on the current codebase to answer a simple question:

> did the anticipation and carryover work materially move the original self-selected capability objective?

## What Was Run

### Lightweight self-selected smoke

```powershell
$env:PYTHONPATH='C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate;C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate\scripts;C:\Users\nscha\AppData\Roaming\Python\Python313\site-packages'; @'
from scripts.compare_self_selected_smoke import evaluate_self_selected_smoke
result = evaluate_self_selected_smoke(benchmark_ids=['A1','B2','C3'], task_keys=['task_a'], seeds=[13])
for point in result['results']:
    self_selected = next(item for item in point['methods'] if item['method_id'] == 'self-selected')
    oracle = next(item for item in point['methods'] if item['method_id'] == point['oracle_method_id'])
    print(point['benchmark_id'], point['oracle_method_id'], oracle['exact_match_rate'], self_selected['exact_match_rate'], point['self_selected_oracle_gap'], self_selected['latent_recruitment_cycles'], self_selected['growth_recruitment_cycles'])
print('aggregate', result['aggregate'])
'@ | C:\Python313\python.exe -
```

### Focused source-side benchmark node probes

```powershell
$env:PYTHONPATH='C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate;C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate\scripts;C:\Users\nscha\AppData\Roaming\Python\Python313\site-packages'; @'
from scripts.diagnose_benchmark_node_probe import evaluate_benchmark_node_probe
for benchmark_id in ('B2','C3'):
    result = evaluate_benchmark_node_probe(benchmark_id=benchmark_id, task_keys=('task_a',), method_id='self-selected', seed=13, cycle_limit=80)
    run = result['task_runs']['task_a']
    source = run['nodes'][run['focus_nodes'][0]]
    print(benchmark_id, run['summary'], source['summary'])
'@ | C:\Python313\python.exe -
```

## Current Smoke Results

### Current-code local winners on the tiny slice

This matters because the fixed-policy comparison landscape has shifted relative to the March 18 traces.

| Benchmark | fixed-visible | fixed-latent | growth-visible | growth-latent | self-selected |
|---|---:|---:|---:|---:|---:|
| A1 | 0.0556 | **0.5556** | 0.0556 | **0.5556** | 0.0556 |
| B2 | 0.6019 | **0.6944** | 0.6667 | **0.6944** | 0.5648 |
| C3 | 0.2037 | 0.2500 | **0.3333** | 0.2778 | 0.2222 |

### Self-selected vs current-code oracle

| Benchmark | Current oracle | Oracle exact | Self-selected exact | Oracle gap | Latent recruit | Growth recruit |
|---|---|---:|---:|---:|---|---|
| A1 | `fixed-latent` | 0.5556 | 0.0556 | 0.5000 | `[]` | `[]` |
| B2 | `fixed-latent` | 0.6944 | 0.5648 | 0.1296 | `[32]` | `[]` |
| C3 | `growth-visible` | 0.3333 | 0.2222 | 0.1111 | `[47]` | `[]` |

Aggregate:

- mean self-selected oracle gap: `0.2469`
- by family:
  - `A`: `0.5000`
  - `B`: `0.1296`
  - `C`: `0.1111`

## Comparison To The Earlier Self-Selected Checkpoint

The closest prior checkpoint is the tuned March 18 smoke slice:

- `A1`: gap `0.0000`, latent `[]`, growth `[]`
- `B2`: gap `0.4722`, latent `[31]`, growth `[]`
- `C3`: gap `0.2963`, latent `[33]`, growth `[]`
- aggregate mean gap: `0.2562`

### What clearly improved

- `B2` improved substantially relative to its local oracle:
  - gap `0.4722 -> 0.1296`
- `C3` also improved relative to its local oracle:
  - gap `0.2963 -> 0.1111`

### What clearly got worse

- `A1` is now much worse relative to the local oracle:
  - gap `0.0000 -> 0.5000`

### Important caution

This is **not** a clean apples-to-apples comparison to the March 18 family map.

The fixed-policy winners on this tiny slice shifted under the current codebase:

- `A1` no longer favors visible in the tiny smoke slice
- `B2` now favors latent in the tiny smoke slice
- `C3` now favors growth-visible in the tiny smoke slice

So the current re-baseline should be read as:

- self-selected versus the **current-code local oracle**
- not as a direct replacement for the broader March 18 family prescription document

## What The Focused B2 / C3 Probes Show

### B2

Source summary over the first `80` cycles:

- first source-sequence cycle: `1`
- first latent-context cycle: `28`
- first latent-capability cycle: `32`
- pre-sequence guidance match rate: `0.725`
- mean source-sequence context confidence: `0.95`
- mean latent-context confidence: `0.65176`

Interpretation:

- local sequence evidence appears immediately
- latent-context estimation is present before capability recruitment
- latent capability still waits until cycle `32`
- action selection is already following the best sequence hint about `72.5%` of the time in this probe

### C3

Source summary over the first `80` cycles:

- first source-sequence cycle: `3`
- first latent-context cycle: `28`
- first latent-capability cycle: `47`
- pre-sequence guidance match rate: `0.32051`
- mean source-sequence context confidence: `0.92625`
- mean latent-context confidence: `0.53124`

Interpretation:

- sequence evidence also appears early
- latent-context estimation again appears before capability recruitment
- but capability activation is much later than `B2`
- the selector is following the strongest sequence hint only about `32%` of the time in this probe

## What The Prediction Work Seems To Have Done

The best current read is:

- the architecture now has real local recognition and prediction support
- the self-selected controller is operating on a richer substrate than it had originally
- on `B2` and `C3`, local evidence does appear before latent capability flips on

That is a meaningful improvement in *plausibility* of endogenous capability choice.

However, this specific benchmark-node probe is still mostly sequence/latent-guidance oriented. It does not yet expose Phase 8 expectation-model terms cleanly enough to say:

- whether current-cycle prediction itself is what caused the capability switch
- or whether the switch is still mostly driven by older contradiction / latent-summary pathways

So the anticipation story is currently strongest at the architectural and timing level, not yet at the direct causal-diagnostic level.

## Current Take Stock

### What seems stronger than before

- `real_core` is now anticipation-capable
- Phase 8 now has a genuine `recognize -> predict -> select` path
- `B2` and `C3` self-selected behavior are closer to the local fixed-policy winners than they were in the earlier tuned checkpoint
- local evidence now clearly precedes latent recruitment in the two hard cases

### What remains unresolved

- `A1` is a problem again on the current tiny slice, even without latent recruitment
- `B2` and `C3` still do not show a clean direct line from prediction to better self-selected capability timing
- the tiny-slice fixed-policy winners themselves have shifted enough that the smoke harness should be interpreted cautiously

## Best Next Step

The most useful next move is probably **not** another broad feature push.

It is one of these two small steps:

1. make the benchmark-node probe explicitly prediction-aware so it reports current-cycle expectation terms before capability recruitment
2. rerun the `A1/B2/C3` self-selected slice with one narrow controller adjustment only after the prediction-aware probe clarifies whether the current switch logic is actually using the new anticipation path

Given the current evidence, option `1` looks cleaner.
