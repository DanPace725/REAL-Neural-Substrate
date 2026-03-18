# 2026-03-18 1248 - Ceiling Benchmark 3-Seed Pilot

## Scope

This trace records the first 3-seed cold-start pilot over the full ceiling benchmark ladder, executed as three family shards and then merged:

- Family A: scale / horizon
- Family B: hidden-memory
- Family C: transform ambiguity

Transfer was intentionally skipped in this pass. The purpose was to determine whether the current ladder already produces a clean sustained REAL collapse band before freezing the 5-seed paper sweep.

## Operational Outcome

No family produced a formal ceiling band in the current pilot.

Merged frontier:

- Family A ceiling band: `None`
- Family B ceiling band: `None`
- Family C ceiling band: `None`
- Earliest global ceiling: `None`

This means the ladder is not yet severe enough, under the current collapse rule, to support the paper narrative of a clear REAL failure frontier.

## Best NN Pattern

- Family A: `causal-transformer` was best at every band
- Family B: `causal-transformer` was best at every band
- Family C:
  - `C1`: `causal-transformer`
  - `C2`: `elman`
  - `C3`: `elman`
  - `C4`: `mlp-latent`

This is interesting in its own right: the most ambiguous tasks do not consistently favor the largest sequence model. The current ambiguity family appears to introduce regimes where a smaller recurrent or even latent-stateless baseline can compete, likely because the visible/latent cues are still too compressible.

## Weakest REAL Region

The lowest REAL aggregates in the merged pilot were:

- `C4 growth-visible`: mean bit accuracy `0.4825`, exact-match rate `0.1574`
- `C3 growth-visible`: mean bit accuracy `0.4840`, exact-match rate `0.2047`
- `C3 fixed-visible`: mean bit accuracy `0.4902`, exact-match rate `0.2047`

Even here, the exact-match rate remains above the collapse threshold (`0.10`), so these points are weak but not yet collapsed by the paper rule.

## Engineering Notes

During the pilot, `growth-visible` on `A3` exposed a real morphogenesis bug: feedback pulses could still reference a dynamic node after topology removal. The fix was to skip stale feedback edges whose source node has already been removed. A regression test now exercises `A3` growth-visible as a smoke path.

The full 12-point pilot did not finish comfortably as a single monolithic run in this environment, so the benchmark was executed in family-sized shards and merged afterward. This chunked flow is now part of the tooling and should be used for larger sweeps.

## Immediate Next Change

The next ladder revision should push difficulty harder in the ambiguity/memory direction rather than only adding more scale.

Recommended next adjustments:

1. Add one harsher ambiguity band after `C4` where visible context is intentionally uninformative and the hidden controller state is delayed longer than 2 packets.
2. Add one harsher memory band after `B4` that uses a longer delayed summary than the current 8-step rolling parity.
3. Keep Family A unchanged for now; it is useful as a non-collapse anchor ladder.
