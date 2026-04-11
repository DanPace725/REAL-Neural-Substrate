# 2026-03-18 2216 - Transfer Recognition Timing Probe

Author: GPT-5 Codex

## Why

After fixing recognition availability in warm transfer, the remaining question was timing and coverage:

- are recognized route entries appearing early enough to matter?
- are they showing up at the source where transfer-critical route decisions begin?
- or are they arriving later and downstream after the important mistakes are already underway?

## What Changed

Extended `scripts/probe_phase8_transfer_recognition.py` to report:

- recognized route cycles
- recognized source-route cycles
- first recognized route cycle
- first and last wrong-delivery cycles
- recognized entries before, during, and after the wrong-delivery window
- recognized entries inside vs. after the transfer-adaptation window

Also tightened `tests/test_phase8_transfer_recognition_probe.py` to assert the presence of timing fields and a non-null first recognized route cycle.

## Validation

Ran:

- `python -m unittest tests.test_phase8_transfer_recognition_probe tests.test_phase8_recognition_probe tests.test_phase8_recognition tests.test_real_core`
- `python -m scripts.probe_phase8_transfer_recognition --seed 13`

## Result

For seed `13`, warm transfer with recognition bias enabled produced:

- `recognized_route_cycles = [29, 30, 31, 32, 33]`
- `first_recognized_route_cycle = 29`
- `recognized_source_route_cycles = []`
- `first_wrong_delivery_cycle = 26`
- `last_wrong_delivery_cycle = 37`
- `recognized_before_first_wrong_delivery_count = 0`
- `recognized_during_wrong_delivery_window_count = 5`
- `recognized_after_last_wrong_delivery_count = 0`
- `recognized_within_transfer_window_count = 0`
- `recognized_after_transfer_window_count = 5`

The same timing profile appeared with recognition bias disabled, as expected, since the bias does not affect whether recognition itself is recorded.

## Interpretation

This clarifies the current limitation quite a bit.

Recognition in this transfer probe is:

- **not** appearing at the source
- **not** appearing before the first transfer mistakes
- **not** appearing during the early transfer-adaptation window
- instead appearing later, downstream, while the wrong-delivery window is already in progress

So the route-recognition mechanism is currently too late and too downstream to improve this transfer case.

That explains why:

- recognition is now present
- but the route bias still does not move the warm-transfer metrics

The problem is no longer "recognition absent" and not yet "recognition weight too small." It is more specifically:

- recognition coverage missing at the source
- recognition timing missing the early transfer window

## Likely Next Step

The next best small step is to target source-side transfer recognition specifically.

The most plausible direction is to add a source-oriented pattern family or source-oriented recognizer input that can fire on early transfer route pressure before downstream route patterns stabilize.
