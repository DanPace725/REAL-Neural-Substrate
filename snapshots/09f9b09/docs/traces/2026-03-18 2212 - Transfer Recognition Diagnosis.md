# 2026-03-18 2212 - Transfer Recognition Diagnosis

Author: GPT-5 Codex

## Why

The first warm-transfer recognition probe returned a null result with zero recognized route entries. That left an ambiguity:

- was the new recognition route bias too weak?
- or was recognition not activating at all in the real transfer path?

This follow-up isolated that question.

## Diagnosis

The initial failure was primarily a representation mismatch.

Phase 8 route consolidation writes route patterns in substrate key space, for example:

- `edge:n1`
- `edge:n2`

But transfer-time `state_before` observations did not expose those keys. The recognizer therefore had to fall back to:

- generic REAL coherence dimensions

which do not live in the same space as the route patterns.

That meant route-pattern recognition had no aligned local signal to compare against in the real transfer run.

## What Changed

### Phase 8 observation alignment

Updated `LocalNodeMemoryBinding.modulate_observation(...)` in `phase8/adapters.py` to expose substrate-key aliases in the local observation, including:

- edge support keys
- action support keys
- context-action support keys when context is resolved

This keeps the recognizer local while giving it access to the same structural coordinate system Phase 8 patterns already use.

### Better recognizer source selection

Updated `PatternRecognitionModel` in `real_core/recognition.py` so it does not blindly accept the first available candidate state source.

It now compares multiple candidates, including:

- `state_before`
- `substrate.dim_history`
- `history`

and chooses the source with the best top pattern match.

This matters because:

- in synthetic tests, history can still be the best source
- in Phase 8 transfer, aligned `state_before` keys can become the best source once exposed

## Result

After the fix, the warm-transfer probe for seed `13` changed from:

- `recognized_route_entry_count = 0`

to:

- `recognized_route_entry_count = 5`
- `recognized_route_entry_rate = 0.061`
- `mean_recognition_confidence_on_recognized_routes = 0.5492`

So recognition is now genuinely active in the real transfer path.

However, the transfer outcome metrics remained unchanged between recognition bias enabled vs. disabled in that tiny probe.

## Interpretation

This is a much better state than the earlier null result.

Before:

- recognition route bias could not matter because route recognition never fired

After:

- route recognition does fire in warm transfer
- but only sparsely
- and that sparse activation is not yet enough to change the measured transfer outcome

So the current bottleneck is no longer "recognition absent." It is now closer to:

- recognition too sparse
- recognition too late
- or recognition not yet coupled strongly enough to the right transfer decisions

## Validation

Ran:

- `python -m unittest tests.test_phase8_transfer_recognition_probe tests.test_phase8_recognition_probe tests.test_phase8_recognition tests.test_real_core`
- `python -m scripts.probe_phase8_transfer_recognition --seed 13`

## Likely Next Step

The next best move is another small diagnostic, but now focused on timing and coverage:

- when do the 5 recognized route entries occur?
- are they concentrated after the important transfer mistakes already happened?
- do they align with the branch decisions that actually matter for transfer recovery?
