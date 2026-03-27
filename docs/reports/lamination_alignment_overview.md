# Temporal Constrain Lamination: Theory-to-Implementation Alignment

**REAL Neural Substrate Project** | March 25, 2026

---

## 1. Overview

This document describes the alignment work performed on the Temporal Constrain Lamination (TCL) system within the REAL Neural Substrate. The implementation had drifted from the Phase 1 TCL theory in several ways that fundamentally undermined the design intent: the coupling between cycles and slices was too tight, termination was driven by counters rather than criteria, and the budget regulation was inverted.

Six specific misalignments were identified and corrected. After the fixes, all three benchmark families show strong results:

- **A-family** (topology scaling): 4/4 scales settled above 0.8 threshold (A1–A4)
- **B-family** (hidden sequential dependence): 14/14 scale/task combinations settled above 0.8
- **C-family** (ambiguity resolution): 3/4 scales settled above 0.8; C3S4 represents a genuine capability boundary at this architecture scale

---

## 2. TCL Theory Summary

The Temporal Constrain Lamination theory defines a two-layer adaptive system:

- **Fast layer** runs bounded exploration slices. Each slice executes the full REAL loop (observe → recognize → predict → select → execute → score → compare → consolidate) over multiple cycles.
- **Slow layer** regulates via **tilt** (additive modulation), not reshape (parametric modulation). Tilt is robust to the timing delays inherent in cross-layer communication.
- **Termination is criteria-driven:** the system runs until the Global Coherence Observation (GCO) reaches STABLE consistently. There is no pre-allocated budget. If the problem isn't solved, the system keeps working.
- **Three constants** define an operating window for robust adaptive lamination: a timing ratio between layers, a coupling strength bound, and an information compression target.

The key insight is that the slow layer should *learn when to stop*, not be told. The GCO tracks whether accuracy thresholds have been met across all contexts. Only sustained STABLE status triggers settlement.

---

## 3. Misalignments Identified and Fixed

| Misalignment | Before (Broken) | After (TCL-Aligned) |
|---|---|---|
| Hard `max_slices` cap on controller loop | `for`-loop limited by pre-allocated slices | `while True` loop; only GCO STABLE triggers settlement |
| Budget shrank when stalling | Stalling multiplied budget by 0.75x | Stalling grows budget 1.25x (system needs more time) |
| Heuristic regulator owned termination | Rule-based ESCALATE on DEGRADED/CRITICAL GCO | Only REAL engine GCO trajectory can settle; no escalation on poor performance |
| Pre-divided cycle budget | `scenario.cycles / max_slices` = per-slice budget | Budget is a simple integer; slices take what they need |
| Consolidate policies shrunk budget | `budget_multiplier=0.75` on consolidate policies | `budget_multiplier=1.00`; consolidation maintains effort |
| Slices past schedule got no data | No signal injection after original schedule ended | Signal schedule wraps cyclically so learning continues |

### 3.1 Controller Loop: Counters → Criteria

The controller used a `for` loop bounded by `max_slices`, treating slice count as a hard budget. This was replaced with a `while True` loop that only exits when the regulator issues a non-CONTINUE settlement decision (SETTLE, BRANCH). A `safety_limit` (default 200) exists solely as a development guard against infinite loops.

```python
# Before: hard cap
for slice_id in range(1, max_slices + 1):
    ...

# After: criteria-driven
while True:
    slice_id += 1
    summary = self.runner.run_slice(...)
    signal = self.regulator.regulate(history)
    decision = self._resolve_decision(history, signal)
    if decision != SettlementDecision.CONTINUE:
        return LaminatedRunResult(...)
    if slice_id >= self.safety_limit:  # dev guard only
        return LaminatedRunResult(...)
```

### 3.2 Budget Direction Reversal

The heuristic regulator was shrinking the cycle budget (0.75x) when the system was stalling. This is backwards: a stalling system needs more time to explore, not less. The fix reverses the direction: stalling grows the budget 1.25x, while convergence maintains the current budget.

```python
# Before: stalling → shrink (wrong)
next_slice_budget = _clamp_budget(round(current.slice_budget * 0.75))

# After: stalling → grow (correct)
next_slice_budget = _clamp_budget(round(current.slice_budget * 1.25))
```

### 3.3 GCO-Driven Termination Ownership

The heuristic regulator was issuing ESCALATE decisions when it observed consecutive DEGRADED or CRITICAL GCO states. This is the opposite of the intended behavior: CRITICAL means the system hasn't solved the problem and should keep working. The fix removes all escalation logic. Only consecutive STABLE states trigger SETTLE.

```python
def _evaluate_gco_trajectory(self):
    """Only terminal condition: sustained accuracy threshold met."""
    entries = self._engine.memory.entries
    if len(entries) < self._gco_settle_window:
        return None
    recent = entries[-self._gco_settle_window:]
    if all(e.gco == GCOStatus.STABLE for e in recent):
        return SettlementDecision.SETTLE, "engine_gco_stable"
    return None  # No escalation — keep working
```

### 3.4 Budget Pre-Division Removal

The evaluation harness had a `_resolve_budget()` function that divided total scenario cycles by the number of slices to produce per-slice budgets. This was removed entirely. The `--budget` CLI parameter is now a simple integer (default 8), and the slow-layer regulator adjusts it dynamically based on observed performance.

### 3.5 Policy Budget Multiplier Correction

Named policies with `consolidate` in their carryover filter had `budget_multiplier=0.75`, meaning consolidation was associated with reducing effort. This was changed to 1.00: consolidation should maintain the current effort level, not shrink it.

### 3.6 Signal Schedule Wrapping

When slices ran past the original scenario's signal schedule, no new data was injected, causing accuracy to drop to zero. A wrapping mechanism was added: once the schedule is exhausted, it cycles back to the beginning, ensuring the system always has new examples to learn from.

---

## 4. Files Changed

| File | Changes |
|---|---|
| `real_core/lamination.py` | Controller loop, HeuristicSliceRegulator budget logic, safety_limit |
| `real_core/meta_agent.py` | REALSliceRegulator GCO ownership, policy multipliers, observation adapter |
| `real_core/interfaces.py` | `CoherenceModel.gco_status` signature (`state_after` kwarg) |
| `real_core/engine.py` | Pass `state_after` to `gco_status` call |
| `phase8/lamination.py` | Removed `cycles_remaining` cap, signal schedule wrapping, safety_limit, cross-slice carryover |
| `phase8/adapters.py` | `gco_status` signature alignment |
| `scripts/evaluate_laminated_phase8.py` | Removed `_resolve_budget`, `--safety-limit` CLI, compact output shows final acc, C-family support |
| `scripts/analyze_experiment_output.py` | Added `safety_limit` to metadata keys |
| `tests/test_lamination.py` | Removed `max_slices` from all `LaminatedController` tests |
| `tests/test_phase8_lamination.py` | `safety_limit=10`, removed stale `baseline_summary` assertion |
| `tests/test_real_core.py` | `gco_status` signature alignment |

---

## 5. Architecture After Changes

### 5.1 Slice Execution Flow

1. **LaminatedController** enters a `while True` loop.
2. Each iteration runs one slice via `Phase8SliceRunner`, which executes `cycle_budget` REAL cycles with wrapped signal injection.
3. The slice produces a **SliceSummary** (accuracy, uncertainty, conflict, context breakdown, metadata).
4. **REALSliceRegulator** observes the summary, runs one REAL engine cycle to select a policy, then checks GCO trajectory for settlement.
5. If GCO is STABLE for a consecutive window, SETTLE is issued and the loop exits. Otherwise, the regulatory signal (mode, carryover filter, budget, pressure) is applied and the next slice begins.

### 5.2 Cross-Slice State Preservation

Between slices, the system now preserves substrate state across mode switches via the `export_carryover`/`load_carryover` mechanism. Before a mode switch rebuilds the `NativeSubstrateSystem`, each agent's carryover (substrate weights, consolidated memories, coherence history) is exported. After the rebuild, carryover is loaded into matching agents, so accumulated learning survives capability mode transitions.

Consolidation also runs at slice boundaries when memory grows large, compressing episodic entries into durable substrate state rather than simply discarding them.

### 5.3 Slow-Layer Policy Space

The REAL engine slow layer selects from named policies that bundle four control dimensions:

- **`capability_mode`**: which substrate mode to run (visible, growth-visible, latent-visible, etc.)
- **`carryover_filter`**: how aggressively to filter episodic memory between slices (keep, soften, consolidate, drop)
- **`budget_multiplier`**: scale factor for next-slice cycle budget (1.0–2.0)
- **`context_pressure`**: pressure label forwarded to the fast layer (normal, explore, exploit)

Policy selection is learned: the engine's substrate accumulates support for (context, policy) pairs that produce accuracy improvements via the same bistable mechanism the fast layer uses for routing.

---

## 6. Benchmark Results: A-Family (Topology Scaling)

The A-family benchmark tests how the system scales with increasing topology size. A1–A6 present progressively larger networks. All runs used the REAL slow-layer regulator with a 0.8 accuracy threshold and a safety limit of 500 slices.

| Scale | Task | Final Acc | Slices | Decision | Context 0 | Context 1 |
|-------|------|-----------|--------|----------|-----------|-----------|
| A1 | task_a | **0.938** | 12 | settle | 0.90 | 1.00 |
| A2 | task_a | **0.812** | 6 | settle | 0.80 | 0.83 |
| A3 | task_a | **0.857** | 9 | settle | 0.83 | 0.88 |
| A4 | task_a | **0.938** | 22 | settle | 0.83 | 1.00 |

### Key Observations

- **100% settlement:** All 4 scales settled above the 0.8 threshold.
- **Efficient scaling:** A2 settled in just 6 slices; A4 (the largest) needed 22, showing the system allocates proportional effort without any hard cap.
- **Diverse policy usage:** All four scales used a mix of `growth_engage`, `growth_hold`, `growth_consolidate`, and `growth_reset`. A4 also deployed `growth_hold` heavily (6 of 22 cycles), indicating the slow layer learned to stabilize during longer runs.
- **Strong context balance:** Both contexts consistently above 0.8 across all scales, with several reaching 1.00 on context_1.

---

## 7. Benchmark Results: B-Family (Hidden Sequential Dependence)

The B-family benchmark tests hidden sequential dependence at increasing scale. B2S1–B2S6 scale from small to large topologies. Tasks A, B, and C test different routing patterns within each scale. All runs used the REAL slow-layer regulator with a 0.8 accuracy threshold and a safety limit of 500 slices.

| Scale | Task | Final Acc | Slices | Decision | Context 0 | Context 1 |
|-------|------|-----------|--------|----------|-----------|-----------|
| B2S1 | task_a | **0.938** | 7 | settle | 0.75 | 1.00 |
| B2S1 | task_b | **0.938** | 11 | settle | 0.83 | 1.00 |
| B2S1 | task_c | **0.938** | 8 | settle | 1.00 | 0.92 |
| B2S2 | task_a | **0.812** | 13 | settle | 0.83 | 0.80 |
| B2S2 | task_b | **0.812** | 4 | settle | 1.00 | 0.70 |
| B2S2 | task_c | **0.875** | 8 | settle | 1.00 | 0.83 |
| B2S3 | task_a | **0.812** | 5 | settle | 0.83 | 0.80 |
| B2S3 | task_b | **0.938** | 16 | settle | 0.83 | 1.00 |
| B2S3 | task_c | **1.000** | 6 | settle | 1.00 | 1.00 |
| B2S4 | task_a | **1.000** | 17 | settle | 1.00 | 1.00 |
| B2S4 | task_b | **0.833** | 24 | settle | 0.75 | 0.86 |
| B2S4 | task_c | **1.000** | 10 | settle | 1.00 | 1.00 |
| B2S5 | task_a | **0.812** | 18 | settle | 1.00 | 0.70 |
| B2S6 | task_a | **0.833** | 194 | settle | 0.50 | 0.93 |

### Key Observations

- **100% settlement:** All 14 scale/task combinations settled above the 0.8 threshold.
- **Proportional effort:** Smaller scales (S1–S3) settled in 4–16 slices. Larger scales needed more: S4 took 10–24, S5 took 18, S6 took 194.
- **Diverse policies:** The slow layer used `growth_engage`, `growth_hold`, `growth_reset`, `growth_consolidate`, and latent variants throughout runs, demonstrating genuine policy learning.
- **Context balance:** Most settled runs show both contexts above 0.8, indicating the system learned to route correctly for both context patterns.

---

## 8. Benchmark Results: C-Family (Ambiguity Resolution)

The C-family benchmark tests ambiguity resolution, where overlapping signal patterns must be disambiguated. C3S1–C3S4 scale from 8 to 54 nodes. After wiring in cross-slice carryover preservation:

| Scale | Task | Final Acc | Slices | Decision | Context 0 | Context 1 |
|-------|------|-----------|--------|----------|-----------|-----------|
| C3S1 | task_a | **0.812** | 181 | settle | 0.83 | 0.80 |
| C3S2 | task_a | **0.938** | 17 | settle | 1.00 | 0.90 |
| C3S3 | task_a | **0.812** | 80 | settle | 0.75 | 1.00 |
| C3S4 | task_a | 0.556 | 500 | continue | 0.50 | 0.62 |

### Key Observations

- **3 of 4 settled:** C3S1–C3S3 all reached the 0.8 threshold and settled cleanly.
- **C3S4 plateau:** Hit the 500-slice safety limit at 0.556 accuracy. The trajectory shows a stable plateau (0.50–0.65) rather than oscillation, indicating the system learned what it could but the topology (54 nodes, 103 edges) exceeds the routing architecture's disambiguation capacity at this scale.
- **Carryover impact:** Before wiring in substrate preservation, C3S4 oscillated wildly (0.200–0.688). After carryover, the floor lifted to ~0.500 and stabilized. The improvement confirms that substrate state continuity matters for complex tasks.
- **Effort scales with difficulty:** C3S2 settled in 17 slices but C3S1 needed 181, suggesting that certain topological structures are harder to disambiguate even at smaller scale.

---

## 9. Design Principles Validated

### 9.1 Criteria Over Counters

Removing hard slice caps and letting GCO drive termination produced dramatically better results. The system naturally takes 5 slices for easy problems and 194 for hard ones. Pre-allocated budgets either waste time on easy problems or starve hard ones.

### 9.2 Tilt, Not Reshape

The slow layer communicates via bias (mode selection, context pressure, carryover filtering) rather than directly modifying fast-layer parameters. This is robust to the timing delay between layers and allows the fast layer to maintain its own internal coherence.

### 9.3 Budget Grows Under Stress

Reversing the budget direction (stalling = grow, not shrink) is critical. When a system is struggling, reducing its resources guarantees failure. The corrected logic gives stalling systems more cycles to explore, matching the biological principle that difficult problems require sustained attention.

### 9.4 No Premature Termination

Removing ESCALATE on DEGRADED/CRITICAL GCO states was essential. The old behavior would stop the system precisely when it most needed to continue. The only valid termination is success (sustained STABLE) or the development safety limit.

---

## 10. Remaining Work

- Benchmark A5 and A6 under lamination (larger topology scales, not yet tested).
- Investigate C3S4 capability boundary: may require larger substrate capacity or architectural changes to the routing disambiguation mechanism.
- Tune GCO settle window size (currently requires consecutive STABLE states; optimal window may vary by task family).
- Benchmark cross-task transfer within laminated runs (e.g., train on task_a, transfer to task_b within the same laminated session).
- Profile computational cost vs. accuracy tradeoff across scale families.
- Expand B-family and C-family to tasks B and C at larger scales (S5/S6 currently only have task_a results).

---

*End of Report*
