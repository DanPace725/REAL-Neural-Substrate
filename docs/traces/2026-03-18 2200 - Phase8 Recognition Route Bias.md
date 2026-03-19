# 2026-03-18 2200 - Phase8 Recognition Route Bias

Author: GPT-5 Codex

## Why

After hooking the pattern recognizer into `NodeAgent`, Phase 8 could record recognition traces but those traces had no influence on control.

The next safe step was to let recognition affect exactly one narrow decision path:

- route scoring in `Phase8Selector`

without changing latent capability control, growth logic, or the broader selector architecture.

## What Changed

### Selector context support

`Phase8Selector` now implements `select_with_context(...)`.

The implementation is intentionally minimal:

- it stores the current `SelectionContext`
- delegates to the existing `select(...)`
- clears the context afterward

This means the existing Phase 8 selector flow stays intact, but route scoring can now consult recognition when the engine provides it.

### Narrow recognition-driven route bias

Added a small route-only bias in `_score_route(...)`.

The bias activates only when:

- a current `SelectionContext` exists
- recognition is present
- the recognition contains matched substrate patterns with a valid `pattern_index`

The selector then:

1. looks up the matched substrate pattern
2. infers which neighbor that pattern is focused on
3. adds a small bonus for `route_attractor`
4. adds a small penalty for `route_trough`

The bias is scaled by:

- recognition confidence
- match score
- pattern strength
- novelty damping

This keeps the effect modest and local rather than letting recognition override the rest of Phase 8 scoring.

## What Did Not Change

This pass still does **not**:

- change latent recruitment logic
- change growth recruitment logic
- use recognition to choose transforms directly
- rewrite route scoring around recognition

Recognition is just one additional local factor in route evaluation.

## Validation

Ran:

- `python -m unittest tests.test_phase8_recognition tests.test_real_core`

Added a focused test showing:

- without recognition context, the selector follows the baseline route choice
- with a recognized `route_attractor`, the selector flips toward the recognized branch

## Interpretation

This is a good incremental integration step because it demonstrates proactive use of memory-shaped recognition in Phase 8 control without destabilizing the broader system.

The path now looks like:

- consolidation writes route patterns into substrate
- recognizer detects those patterns later
- selector uses that recognition as a small route prior

That is much closer to "memory shaping future action space" than the earlier purely reactive setup, while still staying well within the repo's local-only constraints.

## Likely Next Step

The next safest experiment is to measure whether this route bias helps in a tiny targeted probe, especially on transfer or repeated-experience situations where recognized route structure should matter more than cold-start ambiguity.
