# AGENTS.md

This repository is a standalone REAL neural-substrate research prototype. It combines:

- `real_core/`: the reusable generalized REAL engine, memory substrate contracts, carryover, and shared types
- `phase8/`: the native substrate implementation where each node is a local REAL agent

The purpose of this file is to keep the architectural constraints of the repo explicit so future work strengthens the substrate instead of quietly drifting back toward ordinary optimization-first patterns.

## Core Stance

This repo is not building a conventional neural network with passive weights, global loss, and backprop-driven updates.

The active thesis is:

- computation should emerge from local allostatic adaptation
- nodes should act through local observation, local action, and local memory
- durable learning should appear as changes in maintained substrate, not as opaque global parameter updates

In practice, Phase 8 treats each node as a local REAL agent running:

`perceive -> select -> execute -> score -> consolidate`

with sequential feedback, ATP-like metabolic constraints, and local carryover.

## Repo Boundaries

Keep these boundaries clear:

- `real_core` is the generalized engine layer and should remain domain-agnostic
- `phase8` is the neural/native-substrate experiment layer and may specialize around routing, transform credit, admission, and topology growth
- top-level runners are experiment entrypoints, not the architectural center of the repo

Do not reintroduce dependencies on the old umbrella workspace. This repo should remain runnable on its own.

## Non-Negotiable Design Constraints

When modifying this repo, preserve these rules unless the user explicitly decides to change the architecture:

1. No global gradient path.
Feedback must remain local or sequentially propagated. Do not add a single global loss update that mutates all nodes at once.

2. Local knowledge only.
Node logic should operate on local state, neighbor-accessible information, and returned feedback. Avoid global-oracle shortcuts.

3. Metabolic costs matter.
Action availability, routing, maintenance, and growth should continue to respect ATP-style budget limits instead of treating cost as decorative telemetry.

4. Learning should write into structure.
When behavior becomes durable, it should show up as substrate support, maintained bias, promoted patterns, or carryover state.

5. `real_core` stays reusable.
If a feature is truly general to the REAL loop, it belongs in `real_core`. If it is specific to the native substrate experiments, it belongs in `phase8`.

6. Keep the standalone boundary clean.
Do not add `sys.path` hacks or assume sibling folders from the umbrella repo exist.

## Working Heuristics

Use these heuristics when deciding where code belongs:

- Put engine contracts, carryover serialization, selectors, meshes, and substrate primitives in `real_core` when they are not specific to routing-task experiments.
- Put routing environments, node-local adapters, transfer-task mechanics, admission logic, and topology growth in `phase8`.
- Prefer extending existing substrate state and diagnostics over adding parallel shadow systems.
- Prefer explicit state transitions and inspectable summaries over hidden emergent magic.

## Expectations For Coding Agents

If you are modifying this repo as an agent:

0. Orient before editing.
Read `README.md` and this file first, then search the docs and trace files by relevant keywords before changing code. Use the technical report, session synthesis, architecture notes, and trace documents to cross-reference the current state of transfer, neural baseline, morphogenesis, topology-scaling, and latent-context work so your changes stay aligned with the actual research direction.

1. Preserve decision traces.
When a change is architectural or experimentally important, capture the reasoning in docs or tests instead of leaving it implicit in code diffs.
When creating or updating trace documents, put the timestamp in the human-visible title as well as the filename so people and agents can identify the date and time without opening folder metadata. Prefer titles in the form `YYYY-MM-DD HHMM - Short Description` or an equally explicit timestamp-first format.

2. Promote stable constraints into the repo.
If a pattern becomes important, encode it in tests, docs, or structural interfaces. Do not rely on memory alone.

3. Evaluate changes for coherence, not just correctness.
Check whether a change improves continuity, accountability, differentiation, and reflexivity of the codebase, not merely whether it runs.

4. Work in small loops.
Make changes incrementally, run tests, and use feedback before broadening the refactor.

5. Favor runnable clarity.
The repo should remain easy to inspect, run, and explain. If a shortcut makes the codebase less legible, it needs a strong reason.

## Recommended Validation

Before closing substantial work, try to leave the repo in a state where at least these still work:

- `python -m unittest discover -s tests -p "test_*.py"`
- `python run_phase8_demo.py --mode comparison --seed 13 --scenario branch_pressure`
- one transfer-oriented smoke check such as `compare_task_transfer.py`

## Related Docs

- `README.md` for repo purpose and quickstart
- `docs/architecture_notes.md` for the fuller Phase 8 architectural framing
- `docs/project_overview_cross_phase.md` for how `real_core` and `phase8` fit together
