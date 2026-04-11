# 2026-03-18 2041 - B2 Use Path Analysis

## Context

This trace records the follow-up analysis after the `B2` benchmark-node probe suggested that self-selected REAL was inferring latent structure without translating that inference into better source-node routing behavior.

The immediate goal was to inspect the actual use path:

- source-sequence estimate
- source-sequence transform hint
- latent estimate
- chosen route transform

and determine where the `B2` hidden-memory signal stops affecting behavior.

## Code Changes

Updated [phase8/environment.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/environment.py):

- added benchmark-aware sequence windows for `ceiling_b1` through `ceiling_b4`
- changed latent tracker sequence estimation so B-family tasks use the same parity windows that the ceiling benchmark generator uses
- added `sequence_recent_parities` to latent task state and carryover serialization
- changed `observe_local()` to use the source focus packet path instead of source inbox only, so source-side sequence features can be observed from `source_buffer`

Updated [diagnose_benchmark_node_probe.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/scripts/diagnose_benchmark_node_probe.py):

- added pre-action source-sequence and latent fields from `entry.state_before`
- added explicit guidance-following summaries:
  - `pre_sequence_guidance_match_rate`
  - `pre_latent_guidance_match_rate`

Updated tests:

- [test_latent_context_tracker.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/tests/test_latent_context_tracker.py)
  - added `B2` parity-window regression
- [test_phase8.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/tests/test_phase8.py)
  - added source-buffer observation regression for `ceiling_b2_task_a`
- [test_benchmark_node_probe.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/tests/test_benchmark_node_probe.py)
  - extended probe summary coverage

## Validation

Focused regressions:

```powershell
$env:PYTHONPATH='C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate;C:\Users\nscha\Coding\Relationally Embedded Allostatic Learning\REAL-Neural-Substrate\scripts;C:\Users\nscha\AppData\Roaming\Python\Python313\site-packages'; C:\Python313\python.exe -m unittest tests.test_phase8.TestLatentContextProbe.test_source_sequence_adapter_uses_source_buffer_focus_packet_for_b2_hidden_memory tests.test_latent_context_tracker.TestLatentContextTracker.test_generated_b2_sequence_context_uses_two_packet_parity_window tests.test_benchmark_node_probe.TestBenchmarkNodeProbe.test_benchmark_node_probe_runs_b2_self_selected_short_cycle_limit
```

Result: `OK` (`3` tests)

Short probe:

- benchmark: `B2`
- task: `task_a`
- method: `self-selected`
- seed: `13`
- cycle limit: `40`

## Findings

### 1. There was a real modeling mismatch in the B-family sequence path

The ceiling benchmark generator defines:

- `B1`: previous `1` packet parity
- `B2`: previous `2` packet parity
- `B3`: previous `4` packet parity
- `B4`: previous `8` packet parity

Before this pass, the latent source-sequence estimator used the old one-step summary for all non-C tasks. That meant `B2/B3/B4` source sequence state was structurally misaligned with the benchmark definition.

### 2. There was also a real source observation mismatch

`observe_local()` was still reading source latent/sequence features from the source inbox, while self-selected capability control already used the source focus packet path (`source_buffer` fallback). That made it possible for the source selector to miss the same sequence evidence that the capability controller was using.

### 3. After both fixes, the selector still only partially follows the source-sequence guidance on `B2`

From the updated short `B2` source-node probe:

- first source-sequence cycle: `1`
- first latent-context-available cycle: `28`
- first latent-capability-enabled cycle: `31`
- pre-sequence guidance count: `40`
- pre-sequence guidance match count: `30`
- pre-sequence guidance match rate: `0.75`

This is the important result.

The source selector *does* receive a strong pre-action sequence transform hint after the fixes, but it still ignores the strongest hinted transform about `25%` of the time in this short run.

Concrete example from pre-action state:

- cycle `32`
  - source-sequence estimate: `0`
  - source-sequence confidence: `0.95`
  - `source_sequence_transform_hint_rotate_left_1`: `0.95`
  - `source_sequence_transform_hint_xor_mask_1010`: `0.1425`
  - chosen action: `route_transform:n2:xor_mask_1010`

So the current `B2` bottleneck is now much clearer:

- it is **not only** an inference problem
- it is a **selector integration / weighting** problem as well

## Impact On Smoke Results

The lightweight `A1/B2/C3` smoke summary did not materially move from this pass alone. That is expected because these fixes repaired benchmark alignment and observation surfaces, but did not yet retune selector weighting.

## Recommended Next Step

The next clean experiment is not another latent-threshold tweak.

It should be a selector-facing intervention:

1. increase how much pre-action source-sequence transform hints can bias route-transform choice once latent is active
2. compare `B2` short probes before and after that selector change using the new `pre_sequence_guidance_match_rate`
3. only then rerun the lightweight `A1/B2/C3` smoke slice
