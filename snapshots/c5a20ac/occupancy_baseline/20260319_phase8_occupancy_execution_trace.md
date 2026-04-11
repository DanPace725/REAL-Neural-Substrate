# Phase 8 Occupancy Execution Trace - 2026-03-19

**Timestamp**: 2026-03-19 UTC  
**Model**: GPT-5.2-Codex

## Intent

Move the occupancy work from fair packetization into actual Phase 8 execution/scoring, while still fitting the current single-sink routing substrate instead of rewriting the environment all at once.

## Hypotheses tested during implementation

1. The first executable occupancy slice can use a single real sink while still preserving an occupied-vs-empty decision boundary.
   - Result: accepted. The execution topology routes through `evidence_occ` or `evidence_empty` and then into a shared sink, letting episode-level scoring read the last decision node rather than requiring a second physical sink in the core environment.

2. Occupancy packets can be injected directly into sensor-source inboxes without relying on the existing single-source admission buffer.
   - Result: accepted for now. This avoids overfitting the occupancy mapping to a fake monolithic source while keeping the environment changes local to the wrapper layer.

3. Episode scoring should come before occupancy-specific learning feedback changes.
   - Result: accepted. This slice establishes actual execution and fair episode-level prediction metrics before we decide how class-shaped local feedback should be introduced.

## Frictions encountered

- The current environment strongly assumes one admission source and one physical sink, so the occupancy execution layer has to wrap those constraints rather than replacing them wholesale.
- A direct class-feedback path would have forced stronger assumptions about what REAL should do, so this slice stops at execution plus episode scoring.

## Decisions promoted to maintained substrate

- The first occupancy execution path should prefer wrapper-layer adaptation over a large environment rewrite.
- Episode-level class prediction should be inferred from the final decision node traffic, not from any hidden side channel.
- We should validate execution/scoring first, then decide deliberately how occupancy-specific feedback should couple back into local learning.
