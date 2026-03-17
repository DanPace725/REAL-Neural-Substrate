# 2026-03-17 0935 - Parallel Subagent Coordination Trace

**Type:** H_c (Parallel coordination)
**Scope:** `REAL-Neural-Substrate` repo audit with parallel subagent exploration
**Inputs reviewed:** `AGENTS.md`, `README.md`, `docs/20260317_phase8_session_synthesis.md`, top-level experiment harnesses, `tests/test_phase8.py`, local git refs

---

## 1. Branch Reality

- `master` is the correct working base.
- `origin/dev` and `origin/exp` both point to `207cad4` (`port updates`).
- `master` is ahead only by:
  - `9baa016` `update readme`
  - `ac0afc6` `Update AGENTS.md`
- Practical implication: the side branches do not contain newer experiment code. They are only missing the current operating guidance.

**Recommendation:** branch future agent work from `master` so every worker inherits the current `README.md` and `AGENTS.md` constraints.

---

## 2. What Already Exists

The repo already has runnable coverage for most of the current Phase 8 surface:

- visible vs latent single-task and `A -> B` transfer: `compare_latent_context.py`
- latent source-sequence ablation: `compare_latent_ablations.py`
- visible transfer comparisons: `compare_task_transfer.py`, `compare_transfer_matrix.py`, `evaluate_transfer_asymmetry.py`
- visible sequential transfer: `compare_sequential_transfer.py`
- small-topology morphogenesis, including latent-capable plumbing: `compare_morphogenesis.py`
- large-topology morphogenesis wrapper: `compare_morphogenesis_large.py`
- large-topology cold and warm visible evaluation: `compare_large_topology.py`
- timeline diagnostics for transfer and latent commitment: `analyze_transfer_timecourse.py`
- neural cold-start baseline comparison: `neural_baseline.py`

The March 17 open questions are therefore mostly harness-extension problems, not missing-core-architecture problems.

---

## 3. Gaps That Matter Most

### 3.1 Missing experiment shapes

- No dedicated `A -> B -> C -> A` cyclic transfer harness exists yet.
- No latent sequential transfer harness exists yet, even though latent single-hop transfer does.
- Large-topology morphogenesis is exposed only through a visible wrapper, despite latent-capable support already existing in `compare_morphogenesis.py`.

### 3.2 Tracking gap

- Current experiment entrypoints mostly print JSON and rely on manual trace writeups afterward.
- For rapid iteration, the repo still lacks a standard persisted result artifact such as a run manifest, JSON report, or trace stub emitted directly by harnesses.

### 3.3 Guardrail gap

- `tests/test_phase8.py` already provides broad subsystem coverage plus March 17 single-seed harness smoke checks, but the obvious next experiment shapes are still uncovered:
  - cyclic transfer beyond `A -> B -> C`
  - latent sequential transfer
  - latent plus large-topology morphogenesis
- If more harnesses are added quickly, lightweight output-shape tests should be added at the same time so iteration speed does not outrun basic correctness.
- There is also no stable manifest/schema assertion for experiment outputs, so downstream aggregation could drift silently even when harnesses still "run."

---

## 4. Prioritized Next Tasks

### Priority 1 - Add persisted result capture for experiment runs

**Why now**

- The user priority is rapid exploration with tracked outputs.
- This is the main repo-level bottleneck for running many short experiment loops without losing provenance.

**Minimal shape**

- Add a small shared helper that writes:
  - timestamp
  - git commit
  - harness name
  - seed list
  - scenario names
  - JSON results
- Store artifacts in a stable folder such as `docs/traces/` or a dedicated `experiment_runs/` directory.

**Likely files**

- new helper module near the top-level harnesses
- `compare_sequential_transfer.py`
- `compare_morphogenesis.py`
- `compare_morphogenesis_large.py`
- `compare_latent_context.py`

### Priority 2 - Add latent sequential transfer

**Why now**

- Best value-to-effort experiment extension.
- Directly answers the March 17 open question about whether latent multi-step carryover avoids visible context poison while preserving transfer benefit.

**Minimal shape**

- Extend `compare_sequential_transfer.py` with:
  - `latent_context`
  - `source_sequence_context_enabled`
- Reuse `latent_signal_specs()` from `compare_latent_context.py`.
- Preserve current per-context delta reporting for `ctx0` and `ctx1`.

**Likely files**

- `compare_sequential_transfer.py`
- `compare_latent_context.py`
- `tests/test_phase8.py`

### Priority 3 - Generalize sequential transfer into cyclic transfer

**Why now**

- `A -> B -> C -> A` is the clearest unresolved systems-level question in the session synthesis.
- The current sequential harness already has the carryover-saving pattern needed for this.

**Minimal shape**

- Refactor the fixed `A/B/C` chain logic into a generic ordered task-chain runner.
- Add either:
  - `compare_cyclic_transfer.py`, or
  - a generalized chain mode inside `compare_sequential_transfer.py`
- Report terminal-task deltas against cold baselines and keep per-context metrics.

**Likely files**

- `compare_sequential_transfer.py`
- optional new `compare_cyclic_transfer.py`
- `tests/test_phase8.py`

### Priority 4 - Expose latent large-topology morphogenesis plus narrow config sweeps

**Why now**

- `compare_morphogenesis.py` already supports latent-mode wiring.
- The large-topology wrapper is the shortest path to testing whether the strongest current morphogenesis result survives latent training.
- A narrow sweep can directly probe the "difficulty-correlated growth" question without touching core architecture.

**Minimal shape**

- Thread through:
  - `latent_context`
  - `source_sequence_context_enabled`
  - `latent_transfer_split_enabled`
- Add a narrow sweep over a few scenario-aware knobs:
  - `atp_surplus_threshold`
  - `max_dynamic_nodes`
  - possibly `seed_action_support`

**Likely files**

- `compare_morphogenesis_large.py`
- `compare_morphogenesis.py`
- optional new `compare_morphogenesis_sweep.py`
- `tests/test_phase8.py`

---

## 5. Suggested Parallel Split For Follow-On Agent Work

### Worker A - Transfer extensions

- Own `compare_sequential_transfer.py`
- Add latent sequential support
- Then generalize to cyclic transfer
- Add smoke tests for new output keys

### Worker B - Morphogenesis extensions

- Own `compare_morphogenesis_large.py`
- Expose latent large-topology mode
- Add one narrow scenario-aware config sweep harness
- Add smoke tests for latent large-topology output shape

### Worker C - Result tracking and trace hygiene

- Own shared result-capture helper
- Add persisted JSON artifacts for major harnesses
- Ensure trace metadata includes timestamp-first titles and run provenance
- Add schema-level tests for persisted manifests and major harness top-level keys

This split keeps write scopes mostly disjoint while matching the repo's current experimental bottlenecks.

---

## 6. Operational Guardrails

- Start from `master`, not `dev` or `exp`.
- Read `README.md` and `AGENTS.md` before editing.
- Treat `real_core` as stable reusable infrastructure and keep experiment-specific work in `phase8` or top-level harnesses.
- Every new harness should get at least one single-seed smoke test in `tests/test_phase8.py`.
- Every major harness should also get one schema-level test for required top-level output keys.
- Every new manually written trace should include an explicit timestamp in both filename and title.

---

## 7. Near-Term Recommendation

If only one fast iteration is funded next, do this sequence:

1. add persisted result capture
2. add latent sequential transfer
3. run a small latent-vs-visible sequential comparison
4. write a fresh timestamped trace from those outputs

That path is the shortest route from the current March 17 state to a new decision-relevant result.
