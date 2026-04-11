# 2026-03-30 1112 - Pulse Delay Not Hard Suppression

## Context

The first Phase 8 pulse pilot treated pulse thresholding as a hard route gate.
That created a mismatch with the intended REAL behavior:

- nodes should still learn by making routing trials
- bad routing should decay through ATP cost, weak reward, and substrate drift
- pulse should delay over-eager commitment, not permanently decide whether routing is allowed

The immediate symptom was routing starvation in overlap-topology C/HR experiments.

## Change

The pulse route path was revised so thresholding now acts as a **bounded delay** rather than an unbounded veto.

Implementation notes:

- per-channel `delay_streaks` were added to `SignalState`
- `evaluate_route_action()` now:
  - still accumulates evidence and computes threshold/cooldown
  - delays weak routes briefly
  - but forces release after a small bounded number of repeated delayed attempts
- cooldown remains a short anti-chatter hold
- successful route results now carry pulse metadata (`pulse_reason`, `pulse_forced_release`, etc.) so delayed-release behavior is inspectable in normal runs

## Why This Matches REAL Better

This keeps the pulse idea as a timing/commitment mechanism while preserving REAL's local trial-and-feedback character.

The route itself is the micro-trial:

- if the node routes poorly, it pays ATP and gets weak or bad feedback
- if it routes well, substrate support and context credit can consolidate
- pulse slows premature commitment, but does not become a global permission oracle

## Current Read

Focused tests now verify:

- first attempts can still be delayed
- repeated weak attempts eventually release into a real route trial
- cooldown still blocks immediate refire

A quick `C3S1` pulse+overlap smoke with the tuned preset remained effectively unchanged, which suggests the semantic correction is in place but further selector-side or source-context adjustments are still needed for larger benchmark gains.
