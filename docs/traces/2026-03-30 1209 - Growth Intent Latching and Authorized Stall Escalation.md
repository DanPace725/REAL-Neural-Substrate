# 2026-03-30 1209 - Growth Intent Latching and Authorized Stall Escalation

## Context

The prior growth path allowed a repeated `authorize` state without any actual
growth proposals or active growth nodes. The core mismatch was:

- fast-layer growth need was recomputed from transient local state
- slow-layer authorization was global and did not bind to specific nodes
- context-resolution gating could still suppress all proposals even after authorization
- the REAL regulator did not escalate repeated authorized-without-proposal stalls

## Implemented Changes

- Added per-node `GrowthIntentState` to preserve:
  - request pressure and readiness
  - authorization state and cycle
  - blocked reason and blocked streak
  - authorized stall count
  - last proposal cycle
- Slow-layer growth authorization is now applied to node-local growth intents.
- `growth_action_specs()` now:
  - consults the latched node authorization
  - bypasses the context gate for authorized requesting nodes
  - records explicit blocked reasons when no proposal can be produced
- Compact slice growth summaries now include:
  - `top_requesting_nodes`
  - `top_blocked_nodes`
  - `blocked_reason_counts`
  - `authorized_without_proposal_count`
  - `authorized_stall_slices`
- The REAL regulator now escalates repeated `authorize` stalls to `initiate`.

## First Read

Targeted long-safety validation showed:

- `HR2` now reaches `initiate`
- `HR2` also shows `active_growth_nodes = 1` on initiated slices
- `C3S2` still reaches `authorize` but not `initiate`

So the bi-directional growth contract is now alive in at least one real pilot
case. The remaining work is to improve when visible-task C-family cases
translate authorization into actual structural growth.
