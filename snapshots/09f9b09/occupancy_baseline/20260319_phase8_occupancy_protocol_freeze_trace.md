# Phase 8 Occupancy Protocol Freeze Trace - 2026-03-19

**Timestamp**: 2026-03-19 UTC  
**Model**: GPT-5.2-Codex

## Intent

Freeze the traditional occupancy benchmark protocol into a named preset before beginning REAL-specific task encoding.

## Hypotheses tested during implementation

1. The benchmark should have one canonical preset rather than only ad hoc CLI flags.
   - Result: accepted. Added `synth_v1_default` so future comparisons can point to one stable traditional baseline.

2. The canonical benchmark contract should live in both code and prose.
   - Result: accepted. Added `presets.py` for executable defaults and `benchmark_protocol.md` for the human-facing protocol definition.

3. The CLI should support preset-driven runs directly.
   - Result: accepted. `run_baseline.py` can now list presets or execute the canonical preset without manually repeating the config.

## Frictions encountered

- Presets need to reduce ambiguity without making exploratory runs harder, so the CLI still supports raw `--csv` usage as an override path.
- The benchmark is now frozen on the traditional side, but the REAL-side mapping still needs deliberate design rather than a rushed direct port.

## Decisions promoted to maintained substrate

- The first REAL comparison should target `synth_v1_default`, not an improvised occupancy run.
- Benchmark protocol changes should happen by adding or versioning presets, not by silently changing the default CLI examples.
- Traditional-side stabilization should precede REAL-side encoding so only one side of the comparison changes at a time.
