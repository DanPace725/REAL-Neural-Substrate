# 2026-03-18 2133 - Real Core Anticipation Phase 2

Author: GPT-5 Codex

## Why

Phase 1 made local expectations representable in `real_core`, but those expectations were still observational only. The engine could record what it expected and how wrong it was, yet current-cycle prediction could not influence action selection.

This pass adds the smallest clean control bridge: selectors can now opt in to seeing current-cycle anticipation without forcing every existing selector implementation to change.

## What Changed

### New selector context

Added `SelectionContext` in `real_core/types.py`.

It carries the local state needed for anticipation-aware choice:

- current cycle
- recordable pre-action state
- current-cycle predictions
- prior coherence
- remaining budget
- per-action cost estimates

This is runtime control context, not durable memory or carryover state.

### Backward-compatible selector extension

Added `ContextualSelector` in `real_core/interfaces.py`.

Selectors may now optionally implement:

- `select_with_context(available, history, context)`

The engine checks for this method and uses it when available. Otherwise it falls back to the original:

- `select(available, history)`

This keeps older selectors and domain code paths valid.

### Anticipatory selector

Added `AnticipatorySelector` in `real_core/selector.py`.

It extends the existing CFAR-style selector rather than replacing it wholesale.

Behavior:

- if current-cycle predictions are strong, confident, and sufficiently separated from alternatives, choose anticipatorily
- otherwise fall back to the existing CFAR selection logic

Its scoring combines:

- expected delta
- expected coherence relative to prior coherence
- confidence
- uncertainty
- cost sensitivity
- a light retrospective contribution from historical delta

This keeps the selector grounded in prior experience while allowing prediction to matter immediately when the local signal is strong enough.

### Engine integration

`RealCoreEngine` now builds a `SelectionContext` each cycle and passes it to selectors that support contextual selection.

This is the first point where the generalized REAL core can use anticipation before action rather than only after action.

## What Did Not Change

This pass still does **not**:

- require all selectors to consume prediction
- make anticipation mandatory for any domain
- add a generalized recognition protocol
- rewrite Phase 8 selectors to use the new core path yet

Those remain separate decisions.

## Validation

Ran:

- `python -m unittest tests.test_real_core`

Added focused tests for:

- engine passing `SelectionContext` into an opt-in contextual selector
- `AnticipatorySelector` preferring a high-confidence low-uncertainty prediction

## Interpretation

This is the first genuine proactive step in `real_core`.

The core loop can now:

1. form local expectations
2. expose them to control
3. act on them when a selector is designed to do so
4. record what happened and how wrong the expectation was

That is still a modest anticipatory mechanism, but it is no longer purely retrospective.

## Likely Next Step

The next strong candidate is a generalized recognition interface that distinguishes:

- pattern match / problem-shape recognition
- forward expectation / prediction

That would make the proposed loop clearer:

- `sense -> recognize -> predict -> select -> execute -> compare -> consolidate`

without forcing prediction itself to stand in for recognition.
