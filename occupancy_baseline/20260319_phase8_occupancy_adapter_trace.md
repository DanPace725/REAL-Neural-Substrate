# Phase 8 Occupancy Adapter Trace - 2026-03-19

**Timestamp**: 2026-03-19 UTC  
**Model**: GPT-5.2-Codex

## Intent

Implement the first REAL-side occupancy slice without assuming extra REAL capabilities: only adapt the frozen traditional benchmark into Phase 8-native packet episodes and a fixed small topology.

## Hypotheses tested during implementation

1. The first REAL occupancy slice should stop before environment-level class scoring.
   - Result: accepted. This change only builds the adapter/topology layer so the comparison target is encoded without prematurely assuming how classification should emerge.

2. The adapter should preserve fairness by using only the benchmark window values plus packet order.
   - Result: accepted. The packet specs use the same five sensor channels, the same window length, and no generator-only metadata like `day_index` or `minute_of_day`.

3. The current 4-bit packet format is enough for a first occupancy bridge.
   - Result: accepted for now. Sensor values are bucketed into four one-hot bins so the adapter fits the existing packet model instead of rewriting Phase 8 signal representation first.

## Frictions encountered

- `SignalSpec` does not carry source-node identity, so the adapter needs a small wrapper dataclass for source-aware packet specs.
- The benchmark windowing helper was initially flatten-only, so a fair REAL mapping required adding a non-flattened path in the traditional baseline utilities first.

## Decisions promoted to maintained substrate

- The first REAL occupancy comparison should begin from packetized benchmark windows, not from a custom handcrafted occupancy label shortcut.
- Fairness means REAL gets the same sensor window content as the traditional preset, with temporal order but without extra latent schedule metadata.
- The first occupancy topology should remain fixed and interpretable until the adapter itself is validated by the user.
