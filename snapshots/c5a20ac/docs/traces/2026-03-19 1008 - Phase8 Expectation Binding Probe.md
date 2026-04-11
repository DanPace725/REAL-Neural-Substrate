# 2026-03-19 1008 - Phase8 Expectation Binding Probe

## Summary

Added a narrow Phase 8 expectation binding so node-local REAL runs now emit route-action predictions through `real_core`'s anticipation path. The expectation model is intentionally small and local: it uses existing Phase 8 observation features, optional recognition matches, and current route/transform evidence to estimate expected local outcome, expected coherence, and expected delta for route actions.

This pass answers the immediate architectural question: Phase 8 prediction is now real and observable rather than only implied by selector heuristics. It does **not** yet show an adaptation benefit in the lightweight transfer probes.

## Code Changes

- Added [phase8/expectation.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/expectation.py)
  - `Phase8ExpectationModel`
  - predicts route-action expectations from local route quality, transform evidence, hidden-task signals, and optional recognition alignment
  - compares predicted progress / match-ratio / coherence / delta against observed outcome
- Updated [phase8/node_agent.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/node_agent.py)
  - wires `Phase8ExpectationModel` into `RealCoreEngine`
- Updated [phase8/selector.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/selector.py)
  - adds a very small selector read of current-cycle predictions through `SelectionContext`
  - exposes prediction terms in route-score breakdowns
- Added / updated tests:
  - [tests/test_phase8_expectation.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/tests/test_phase8_expectation.py)
  - [tests/test_phase8_recognition.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/tests/test_phase8_recognition.py)
  - [tests/test_transfer_adaptation_recognition.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/tests/test_transfer_adaptation_recognition.py)
  - [tests/test_phase8_transfer_recognition_probe.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/tests/test_phase8_transfer_recognition_probe.py)

## Results

### Validation

- `python -m unittest tests.test_phase8_expectation tests.test_phase8_recognition tests.test_compare_task_transfer_metrics tests.test_transfer_adaptation_recognition tests.test_phase8_transfer_selector_interaction tests.test_phase8_transfer_recognition_probe tests.test_real_core`

### Transfer Adaptation Probe

- `A -> B`, seeds `13/23/37`
  - `predicted_route_entry_count` is now nonzero on every seed: `71 / 63 / 70`
  - `first_predicted_route_cycle` is `2` on every seed
  - recognition remains present on the same runs
  - early-window adaptation metrics remain unchanged between recognition enabled and disabled

- `C -> A`, seed `51`
  - `predicted_route_entry_count = 80`
  - `first_predicted_route_cycle = 2`
  - early adaptation metrics again remain unchanged between recognition enabled and disabled

## Interpretation

This is a clean structural win but not yet an experimental win.

- We now have a genuine `recognize -> predict -> select` path running inside Phase 8.
- Prediction is early and abundant enough that the prior `predicted_route_entry_count = 0` result is no longer true.
- The current expectation signal is still not changing the lightweight transfer outcomes in a measurable way.

That likely means one of two things:

1. the selector-facing predictive term is still too weak or too redundant with existing heuristics
2. the current expectation model is mostly describing the same local evidence the selector already had, rather than adding a genuinely new anticipatory signal

## Next Best Step

Use one diagnostic pass to compare:

- selector breakdown with prediction term on vs off
- earliest source-route cycles in transfer
- whether the predictive term changes any near-tie route/transform choices at all

If it never changes choices, we should improve the distinctiveness of the expectation signal before increasing its weight.
