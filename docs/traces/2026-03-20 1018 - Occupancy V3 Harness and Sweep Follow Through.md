# 2026-03-20 1018 - Occupancy V3 Harness and Sweep Follow Through

**Model**: GPT-5 Codex
**Session type**: H_e (Episodic Trace)

---

## Intent

Continue the occupancy v3 line until the harness better reflects what REAL is
supposed to demonstrate, then improve throughput only at the level of
independent runs rather than trying to turn REAL into a gradient-style batch
trainer.

This follow-through had two priorities:

1. Correct the occupancy evaluation framing so the benchmark stops treating
   REAL like a conventional train/test classifier.
2. Reduce wall-clock time by parallelizing only work that is structurally
   independent: eval sessions inside `fresh_session_eval`, occupancy test
   modules, and now multi-seed v3 sweeps.

No JAX or neural-baseline work was added in this pass.

---

## Architectural reading

This pass was guided by:

- `AGENTS.md`
- `README.md`
- `docs/architecture_notes.md`
- `docs/20260319_phase8_occupancy_v2_synthesis.md`
- `docs/traces/2026-03-19 1700 - V3 Occupancy Experiment Design.md`

The constraint that stayed central throughout: REAL learning remains local,
sequential, and substrate-writing. Speed work is allowed only where it does
not change the causal order of a single system's adaptation loop.

---

## Harness changes completed

### 1. Explicit eval protocols

`scripts/occupancy_real_v3.py` now supports:

- `persistent_eval`
- `fresh_session_eval`
- `both`

`fresh_session_eval` remains the default primary metric because it isolates
training carryover from eval-time self-training.

### 2. REAL-native ingress and topology/context controls

The v3 harness now exposes the benchmark axes directly in config and CLI:

- `topology_mode = fixed_small | multihop_routing`
- `context_mode = offline_session_context | online_running_context | latent_context`
- `ingress_mode = admission_source | direct_injection`

The default path is now:

- `fresh_session_eval`
- `multihop_routing`
- `online_running_context`
- `admission_source`

This keeps occupancy closer to REAL's native routing substrate instead of a
thin packet-inbox bridge.

### 3. Metrics tightened around orientation and applicability

The reporting now emphasizes:

- session-1 delivery delta
- first-episode and first-3-episode delivery deltas
- admission counts and source-admission summaries
- reset counts by protocol
- context-transfer status values such as
  `not_applicable_all_eval_contexts_seen`

This avoids over-reading saturated metrics and makes it explicit when a
transfer claim is not actually testable on a given split.

### 4. Test coverage promoted into the repo

`tests/test_occupancy_real_v3.py` now covers:

- fresh-session reset behavior
- REAL-native source-admission ingress as the default path
- online context without future leakage
- latent context with no explicit injected context code
- both topology modes
- sweep worker-plan sizing
- multi-seed sweep aggregation

Existing occupancy v1/v2 tests still pass after the harness revision.

---

## Speed work completed

### 1. Auto CPU budgeting

The occupancy v3 runner now auto-targets about 75% of visible CPU capacity
when `workers` is omitted.

On a 20-CPU machine that means:

- worker budget = `floor(20 * 0.75) = 15`

### 2. Eval fanout inside a single seed

For `fresh_session_eval`, independent eval sessions are eligible for process
pool fanout. This preserves per-session causal integrity while reducing
wall-clock time on the eval side.

### 3. Parallel occupancy test runner

`scripts/run_occupancy_tests_parallel.py` runs the occupancy test modules in
parallel subprocesses using the same 75% CPU heuristic.

### 4. Multi-seed sweep support

The new outer-layer sweep helper in `scripts/occupancy_real_v3.py` and the
CLI support in `scripts/run_occupancy_real_v3.py` now allow:

`python -m scripts.run_occupancy_real_v3 --selector-seeds 13 23 37`

The worker budget is partitioned across:

- concurrent seed runs
- eval workers per seed

This is intentionally coarse-grained parallelism. Each individual REAL system
still runs with its local sequential adaptation semantics intact.

### 5. Shared-state collision fix

Parallel seed runs would have raced on one shared
`tests_tmp/real_v3_carryover` directory. The harness now creates a unique
carryover directory per run using seed, process id, and a short UUID suffix.

---

## Throughput reading

Recent occupancy outputs suggest eval remains a large fraction of total work:

- `v3_train75_seed13_summary.md`: train `37952` cycles, warm eval `49660`,
  cold eval `12106`
- `v3_train75_seed13_2_summary.md`: train `27263` cycles, warm eval `41142`,
  cold eval `14019`

So coarse-grained parallelism can materially reduce wall time, but not
linearly with CPU count because training remains sequential inside each seed.

The speed strategy remains:

- parallelize independent seeds
- parallelize independent fresh-session eval work
- keep single-system adaptation loops sequential

---

## Validation

Validated during this pass:

- `python -m unittest tests.test_occupancy_real_v3`
- `python -m unittest discover -s tests -p "test_occupancy_real*.py"`
- `python -m scripts.run_occupancy_real_v3 --selector-seeds 13 23 --max-train-sessions 1 --max-eval-sessions 1 --summary-only`

In the current sandbox, process spawning still falls back to sequential in
some cases because of environment restrictions. The important change is that
the harness now reports `fallback_sequential` cleanly instead of crashing, and
the worker planner still computes the intended budget correctly.

---

## Documentation follow-through

Updated user-facing docs alongside the code:

- `docs/running_occupancy_v3.md` now reflects the current v3 CLI, including
  harness modes, auto worker budgeting, and multi-seed sweeps.
- `README.md` now lists `scripts/run_occupancy_real_v3.py` as a main
  experiment entrypoint and points readers to the dedicated run guide.

---

## Open next steps

If occupancy speed remains painful after this, the next likely wins are still
outside the core REAL loop:

1. Save sweep outputs directly as compact manifests for later aggregation.
2. Separate fast-smoke occupancy coverage from heavier end-to-end harness
   checks in the default test flow.
3. Profile train-session hot spots before considering any deeper runtime
   optimization work.

The main line remains unchanged: get the evaluation structurally right first,
then optimize around the edges without compromising the local-substrate model.
