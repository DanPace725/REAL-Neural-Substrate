# 2026-04-01 - Trace Organizer Frontier Sense and Slow Layer

**Type**: Development trace
**Author**: Claude Opus 4
**Model**: Claude Opus 4

## Purpose

Document the current state of the REAL trace organizer — a system that organizes
its own development traces using REAL's allostatic regulation, without supervised
labels or clustering algorithms. This session added three major capabilities:
lexicon persistence, a slow-layer retry loop, and endogenous frontier awareness.

## Context

The trace organizer is REAL doing something useful: reading 109 development traces
and discovering meaningful organizational structure through allostatic pressure.
The system has a six-dimensional coherence model mapped to E² relational primitives,
a CFAR selector with regulator bias, a cell pool (surveyor/refiner sub-agents),
and a REAL-native lexicon that builds linguistic understanding through co-occurrence
rather than imported embeddings.

Before this session, the system could organize ~70% of traces before stagnating.
It had no memory across runs (lexicon rebuilt from scratch each time), no retry
mechanism, and no felt sense of how much world remained unexplored.

## What Was Built

### 1. Lexicon Persistence

The lexicon — the system's accumulated vocabulary of word meanings derived from
relational co-occurrence — now saves and restores across sessions.

- `Lexicon.save_state(path)` serializes the co-occurrence graph, document
  frequencies, per-trace tokens, and per-trace TF to JSON
- `Lexicon.load_state(path)` restores from disk and clears caches for fresh
  profile recomputation
- The run harness loads prior state at startup, saves at shutdown
- Re-ingestion is idempotent: `if trace_id in self._trace_tokens: return`

**Effect**: Second run starts with higher initial coherence (0.353 vs 0.320)
because the lexicon already understands the project vocabulary. Each run extends
the vocabulary rather than rebuilding it.

### 2. Slow-Layer Retry Loop

The harness now wraps the inner engine loop in a meta-regulatory outer loop that
evaluates session outcomes and adjusts parameters for retry.

**Structure**:
- `run_attempt()` executes one full engine session, returns outcome metrics
- `slow_layer_evaluate()` diagnoses what went wrong and proposes adjustments
- `main()` orchestrates up to N attempts within a wall-clock budget

**Diagnosis logic**:
- CLOSURE reached → satisfied, stop
- Above viability floor (0.757) with decent organization → satisfied
- CRITICAL_KILL → boost exploration rate for next attempt
- STAGNATION with low reads → more exploration, slight frustration floor
- STAGNATION with reads but no organizing → shift to exploitation
- BUDGET_EXHAUSTED while improving → continue with same params

**What carries across attempts**:
- Lexicon (vocabulary accumulates — this is the learning that persists)
- Seed shifts by +7 per attempt (different trajectory through action space)
- Exploration rate and frustration floor adjusted by diagnosis

**What resets per attempt**:
- Organization (groups, assignments — structural work starts fresh)
- Engine, substrate, cell pool (clean slate for inner loop)

### 3. Frontier Sense (Endogenous Boundary Awareness)

The system now has a felt sense of unexplored territory — not a goal to "process
all files" but an endogenous incompleteness signal, like a slime mold sensing
nutrients beyond its current reach.

**Two signals on `TraceEnvironment`**:

`frontier_pressure()`: Nonlinear incompleteness using `(1.0 - read_ratio) ** 0.6`.
At 70% coverage this is still 0.455 — the system doesn't feel "mostly done" until
very late. The sublinear exponent means early exploration barely relieves pressure,
while the last few traces feel tantalizingly close.

`frontier_novelty()`: Fraction of the total keyword vocabulary that exists only in
unread traces. When the remaining traces cover familiar topics, novelty is low
(near frontier). When there are entire unexplored topic clusters, novelty is high
(far frontier). This captures the near/far gradient without separate signals.

**Where frontier flows**:

- **Observation space**: Both signals added to `observe()`, visible to the engine
- **Vitality (P2)**: The parabola's optimal point shifts rightward with frontier
  pressure (`0.55 + 0.20 * frontier`). When there's unexplored world, reading more
  still feels like productive growth instead of overshooting peak productivity
- **Accountability (P5)**: Frontier creates tension — `0.18 * frontier + 0.08 * novelty`
  drag on accountability. Unexplored territory is undone work. Amplified when the
  frontier contains genuinely novel topics
- **Frustration (regulator)**: Plateau-satisfied check — when frustration is low
  but frontier is high, inject gentle restlessness (`FRUSTRATION_RATE * 0.5 * frontier`).
  Not urgency, curiosity. Also amplifies exploratory action boosts by
  `(1.0 + frontier_pressure)` so reading gets a stronger nudge when there's more to find
- **Stagnation window**: Stretches with frontier pressure — up to 2x patience when
  most of the world is unexplored. The engine won't give up while there's petri dish

**Design principle**: No probe action was added. A slime mold doesn't have a
"scan edges" command — it feels edges through the same sensing it uses for
everything. Frontier information flows passively through existing observation and
coherence channels, making existing foraging actions naturally more attractive
when territory remains.

## Bugs Fixed Along the Way

### Threshold Mismatch
The regulator used 0.003 as improvement threshold while the engine used 0.005.
The regulator thought progress was happening when the engine didn't count it,
so frustration never built when it should have. Aligned both to 0.005.

### Reading Momentum Blind Spot
The vitality momentum bonus (`+0.08 * recent_reads`) only counted `read_trace`,
not `read_neighbor`, `read_gap`, or `read_surprise`. Since foraging strategies
are the system's main reading actions after early phase, this meant the most
interesting reading wasn't being rewarded. Fixed to count all `read_*` actions.

## Results

| Metric | Before | After |
|--------|--------|-------|
| Traces assigned | 70-80 / 109 (64-73%) | 105 / 109 (96%) |
| Cycles before stagnation | 140-204 | 340 |
| Best coherence | 0.722-0.744 | 0.756-0.776 |
| Unassigned traces | 29-39 | 4-9 |
| Lexicon vocabulary | 3613 (per-run) | 3742 → 4087 (accumulating) |
| Wall-clock time | ~15s (1 attempt) | ~43s (2 attempts, 60s cap) |

## Architecture Notes

### What This Is NOT
- Not a clustering algorithm with a "process all files" loop
- Not an ML pipeline with train/eval phases
- Not goal-directed planning toward a coverage target

### What This IS
- A REAL agent under allostatic pressure discovering its world's boundaries
- Frontier sense as proprioception, not prescription
- Language understanding through relational engagement, not imported embeddings
- Multi-timescale regulation: fast (CFAR selector), medium (regulator bias),
  slow (retry loop with parameter adjustment)

### Key Files
- `trace_domain/lexicon.py` — REAL-native language understanding, co-occurrence graph
- `trace_domain/environment.py` — world model, frontier sense, foraging strategies
- `trace_domain/adapters.py` — coherence model (6 dimensions), action backend
- `trace_domain/regulator.py` — slow-layer bias, frustration, frontier-aware nudging
- `trace_domain/selector.py` — CFAR with regulator bias integration
- `trace_domain/cell_pool.py` — living workforce (surveyor, refiner sub-agents)
- `scripts/run_trace_organizer.py` — harness with slow-layer retry loop

### The Developmental Stack (Timescales)
1. **Per-cycle**: CFAR selector picks action, coherence scored, GCO evaluated
2. **Per-10-cycles**: Regulator updates dim→action map, frustration builds/decays
3. **Per-reorient**: Strategy review, bias signal updated
4. **Per-attempt**: Slow layer evaluates outcome, adjusts exploration/frustration
5. **Per-session**: Lexicon vocabulary persists, grows across all runs

## Open Questions

- The surveyor consistently finds only 1 cluster. The lexicon should help with
  richer similarity, but the surveyor's internal clustering may need tuning.
- Contextual fit remains the persistent bottleneck (~0.35-0.45). The lexicon
  improves trace similarity but the coherence dimension's dependence on
  `intra_group_similarity` means groups need to be tighter.
- The system creates too many groups (up to 49 in one run) — possibly the
  differentiation dimension rewards splitting too aggressively. A group count
  penalty exists but may need strengthening.
- READER and LINKER cell roles are defined but have no runners. They're filtered
  from growth candidates, but building them could create new capabilities.
- The slow layer's diagnosis is hand-coded heuristics. Could the regulator's
  own learning (dim→action map) inform meta-level parameter adjustments?
