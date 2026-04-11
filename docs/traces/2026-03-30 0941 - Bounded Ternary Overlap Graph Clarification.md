# 2026-03-30 0941 - Bounded Ternary Overlap Graph Clarification

## Why

The redesign discussion had been mixing two different hypotheses:

- the current node/local-unit abstraction may be over-compressing signal, ambiguity, plasticity, and growth
- the current routing graph geometry may itself be too weak for harder tasks

The first hypothesis is what the `pulse_local_unit` pilot is testing.
The second hypothesis is a topology question and needed to be stated explicitly.

## Clarification Added

Updated `docs/20260330 Redesign.md` to make the intended graph idea concrete:

- each node can have up to 3 forward children
- layers expand by overlap rather than full branching
- intended bounded counts follow `1, 3, 7, 15, ...`
- adjacent parents share downstream children, so next-layer structure contains both separation and recombination

This is not meant as a literal full hypergraph rewrite.
It is a bounded overlap topology proposal that may provide richer differentiation capacity than the current simpler `source -> routes -> sink` family.

## Important Separation

The doc now explicitly separates:

- **pulse/local-unit pilot**
  - current topology
  - better local state decomposition
  - thresholded route commitment
- **bounded ternary-overlap graph proposal**
  - altered topology geometry
  - shared-child branching
  - more structured downstream recombination

That separation matters because a failure of the pulse pilot should not automatically be interpreted as a failure of the topology idea.

## Practical Implication

If the current pulse pilot still underperforms after tuning, a reasonable next architecture experiment is:

- build a small bounded overlap topology scaffold for a narrow C-family task
- keep the rest of Phase 8 as close as possible
- compare whether topology alone improves differentiation before combining it with pulse gating

## Files

- `docs/20260330 Redesign.md`
