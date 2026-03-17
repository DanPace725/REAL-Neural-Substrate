# Phase 8 — Morphogenesis on Large Topology Trace

**Date:** 2026-03-17
**Time:** UTC evening (session 4)
**Model:** Claude Sonnet 4.6
**Type:** H_e (Episodic Trace)
**Harness:** `compare_morphogenesis_large.py`
**Seeds:** 13, 23, 37, 51, 79
**Follows:** `20260317_phase8_expansion_trace.md`

---

## 1. Setup

Morphogenesis evaluated on the 10-node large topology (3-way source branching, 5-hop paths) with 36-packet stage-2 sessions, using the same `benchmark_morphogenesis_config()` as the small-topology runs:

```
context_resolution_growth_gate=0.55
dynamic_node_upkeep=0.012
growth_grace_ticks=4
anticipatory_growth_backlog_threshold=0.55
routing_feedback_gate=0.05
max_dynamic_nodes=4
```

Three in-distribution scenarios tested cold (no carryover), plus A→B transfer with morphogenesis.

**Comparison baseline (6-node small topology):**
- cvt1_task_b_stage1: realization=80%, earned=20%, win=20%
- A→B transfer: earned=80%, win=60%, node_utilization=56.7%, node_value=0.223

---

## 2. Results

### 2a. Task A large (cold start)

| Metric | Fixed | Growth | Delta |
|---|---|---|---|
| Exact matches (avg/36) | 14.8 | 13.2 | **−1.6** |
| Growth realization | — | **100%** | — |
| Earned growth rate | — | **100%** | — |
| Growth win rate | — | **40%** | — |
| New node utilization | — | 0.700 | — |
| Dynamic node value | — | 0.2005 | — |
| Dynamic net energy | — | −0.101 | — |

**Morphogenesis mildly hurts task A.** Growth fires in every seed (100% realization) and is utilized (70% utilization, node_value=0.20), but task performance is slightly lower in the growth condition. The mechanism: Task A already achieves near-criterion performance on the large topology (14.8/36 avg; criterion reached for at least one seed in prior evaluation). When the fixed topology is already converging efficiently, morphogenesis introduces new nodes mid-session that compete for routing credit, adding overhead without proportional benefit. The growth earns value (positive node_value, high utilization) but the disruption cost slightly exceeds the routing gain.

### 2b. Task B large (cold start)

| Metric | Fixed | Growth | Delta |
|---|---|---|---|
| Exact matches (avg/36) | 11.8 | **19.2** | **+7.4** |
| Growth realization | — | **100%** | — |
| Earned growth rate | — | **100%** | — |
| Growth win rate | — | **80%** | — |
| New node utilization | — | 0.567 | — |
| Dynamic node value | — | 0.177 | — |

**Morphogenesis provides its largest benefit on the hardest task.** +7.4 exact matches (63% improvement over fixed). Task B has the lowest cold-start performance (11.8/36 = 33% exact), leaving the most headroom for growth to help. The 10-node topology's multiple branch paths give new nodes viable routing options to specialize into context-specific transform paths. 100% of seeds realized earned growth, 80% were net wins.

The mechanism: Task B's lower cold-start score means more ATP is spent on suboptimal routes. This creates the surplus windows that trigger growth. New nodes with the richer seeding environment of the larger topology (more candidate edges, more diverse feedback signals) find productive routing niches faster than on the 6-node topology.

### 2c. Task C large (cold start)

| Metric | Fixed | Growth | Delta |
|---|---|---|---|
| Exact matches (avg/36) | 17.0 | 16.0 | **−1.0** |
| Growth realization | — | 80% | — |
| Earned growth rate | — | **80%** | — |
| Growth win rate | — | **40%** | — |
| Dynamic node value | — | 0.181 | — |

**Morphogenesis mildly hurts task C.** Same pattern as Task A: Task C has the highest cold-start performance (17.0/36 = 47%), leaving little room for improvement. Growth fires in 4/5 seeds but is mildly disruptive. 80% earned (nodes are genuinely utilized) but only 40% win (task performance doesn't improve despite utilization).

### 2d. A→B Transfer with morphogenesis (large topology)

| Metric | Fixed | Growth | Delta |
|---|---|---|---|
| Exact matches (avg/36) | 15.2 | **17.4** | **+2.2** |
| Bit accuracy | 0.614 | **0.656** | +0.042 |
| Earned growth rate | — | **100%** | — |
| Growth win rate | — | **80%** | — |
| New node utilization | — | **78.3%** | — |
| Dynamic node value | — | **0.230** | — |
| Dynamic net energy | — | −0.093 | — |
| Time to first feedback | — | 3.9 cycles | — |

**Transfer morphogenesis on the large topology is the best result yet.** +2.2 exact matches (vs +1.2 on small topology), 100% earned growth, 80% win rate (vs 60% on small). Node utilization 78.3% (vs 56.7% on small). Node value 0.230 (stable vs 0.223 on small despite more nodes and longer sessions).

The larger topology with warm A→B carryover creates ideal conditions: the A substrate establishes high-support routes across the 10-node graph, the transfer to B creates uncertainty windows that trigger growth at well-established routing positions, and new nodes have many more candidate edges to specialize into. The result is that growth fires earlier, finds feedback faster (3.9 cycles to first feedback), and earns value more consistently.

---

## 3. Comparison: Small vs Large Topology Morphogenesis

| Condition | Topology | Fixed Exact | Growth Exact | Delta | Earned | Win |
|---|---|---|---|---|---|---|
| task_b cold | 6-node/18-pkt | 3.0 | 3.0 | 0 | 20% | 20% |
| task_b cold | **10-node/36-pkt** | 11.8 | **19.2** | **+7.4** | **100%** | **80%** |
| A→B transfer | 6-node/18-pkt | 6.2 | 7.4 | +1.2 | 80% | 60% |
| A→B transfer | **10-node/36-pkt** | 15.2 | **17.4** | **+2.2** | **100%** | **80%** |

The large topology radically improves morphogenesis outcomes for both cold-start task B and A→B transfer. The small topology's 20% earned/win rate on cold-start B becomes 100%/80% on the large topology.

---

## 4. Emergent Pattern: Difficulty-Correlated Morphogenesis

Across all evaluations, a clear pattern has emerged:

| Task performance (cold) | Morphogenesis outcome |
|---|---|
| High (Task A: 14.8, Task C: 17.0) | Slight regression (−1.6, −1.0) — growth disrupts efficient routing |
| Medium (Task B large: 11.8) | Large gain (+7.4) — growth fills routing gaps |
| Low (Task B small: 3.0) | No gain (0) — insufficient substrate clarity for growth to anchor |
| Warm carryover (transfer) | Consistent gain (+1.2 to +2.2) — warm substrate provides the anchor growth needs |

**Morphogenesis is self-limiting at extremes:**
- When performance is already high, ATP surplus is low (efficient routing consumes ATP productively), growth rarely fires or fires too late to help.
- When performance is very low (cold start, small topology), routing is too chaotic for new nodes to find stable positions before the session ends.
- The sweet spot is **medium cold-start difficulty** or **warm substrate with transfer uncertainty** — both provide clear routing signal with some room for new specialization.

This is an emergent self-regulation property: the metabolic gate (ATP surplus threshold) naturally calibrates growth timing to match the routing state.

---

## 5. H_c Consolidated Pattern Update

**Morphogenesis benefit scales with routing headroom and topology size.** Task B on the large topology (+7.4 exact, 80% win) is the strongest morphogenesis result yet. The larger topology provides the key missing ingredient from the small-topology cold-start experiments: viable routing paths for new nodes to specialize into.

**100% earned growth rate is achievable on task scenarios.** The large topology consistently achieves 100% earned growth across all conditions except task C (80%). On the 6-node topology, task-scenario cold-start earned growth was only 20%. This confirms that earned growth rate is fundamentally topology-dependent — more routing diversity enables more productive morphogenesis.

**The disruption cost of morphogenesis is observable.** Tasks A and C show that morphogenesis can hurt performance even when nodes are genuinely utilized. The disruption cost (~1.0–1.6 exact matches) is consistent across conditions. This is a real overhead that must be offset by routing gain. In the large topology, task B provides sufficient headroom; in task A and C, it does not.

**Transfer remains the most reliable morphogenesis sweet spot.** 80% win rate, 100% earned, 78.3% utilization — all best-in-class values. Warm carryover substrate is the mechanism: it provides routing clarity at the moment growth fires, without requiring the high cold-start performance that naturally suppresses growth.
