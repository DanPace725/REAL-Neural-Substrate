# 2026-03-18 2222 - Earlier Transfer Recognition via Relative Shape

Author: GPT-5 Codex

## Why

After aligning Phase 8 observations with substrate-key space, recognition became available in warm transfer, but it still appeared too late to matter much.

The main issue was that the recognizer still compared early transfer state against stored route attractor patterns in absolute support space.

That is too strict for early transfer because route supports are often:

- present only weakly
- partially decayed
- not yet fully separated

while the stored route patterns are already shaped like strong attractors.

## What Changed

Updated `PatternRecognitionModel` in `real_core/recognition.py` to add a new candidate state source:

- `state_before_relative`

This candidate keeps the same observed pattern keys but normalizes them into a relative attractor-shape range.

The intention is simple:

- let early weak branch contrast count as "this looks like the same shape"
- without requiring absolute support magnitudes to already match the consolidated pattern

The recognizer still compares multiple candidates and chooses the one with the best top match.

## Validation

Ran:

- `python -m unittest tests.test_phase8_transfer_recognition_probe tests.test_phase8_recognition_probe tests.test_phase8_recognition tests.test_real_core`
- `python -m scripts.probe_phase8_transfer_recognition --seed 13`

## Result

Warm-transfer probe for seed `13` improved materially on recognition timing and coverage:

Before this change:

- `recognized_route_entry_count = 5`
- `first_recognized_route_cycle = 29`
- `recognized_before_first_wrong_delivery_count = 0`

After this change:

- `recognized_route_entry_count = 39`
- `recognized_route_entry_rate = 0.4756`
- `mean_recognition_confidence_on_recognized_routes = 0.7591`
- `first_recognized_route_cycle = 11`
- `first_wrong_delivery_cycle = 26`
- `recognized_before_first_wrong_delivery_count = 8`

So recognition is now triggering substantially earlier during transfer overall.

## Important Limitation

This did **not** yet move the transfer outcome metrics in the tiny warm-transfer probe.

It also did **not** solve source timing:

- `first_recognized_source_route_cycle = 30`

So the improvement is real, but mostly downstream or non-source coverage at this stage.

## Interpretation

This is still a meaningful step.

We now know:

- early transfer recognition was being blocked by absolute-shape matching
- relative-shape matching helps recognition fire sooner
- the remaining gap is more specifically about **where** recognition becomes available, not simply **whether** it becomes available

That is good pressure relief on the diagnosis. We are no longer fully stuck on late recognition; we are now looking at late **source-side** recognition.

## Likely Next Step

The next narrow step should target source-side transfer recognition specifically, likely by introducing recognition support for transform-oriented or source-sequence-oriented pattern families rather than only route-attractor branch patterns.
