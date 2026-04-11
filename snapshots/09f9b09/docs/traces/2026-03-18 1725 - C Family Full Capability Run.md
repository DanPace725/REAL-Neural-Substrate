# 2026-03-18 1725 - C Family Full Capability Run

## Purpose

This trace records the first REAL-only follow-up to the March 18 ceiling benchmark pilot, focused on the generated hard ambiguity points in Family C.

The goal was to answer the question the pilot left open:

- what happens when the modified C tasks are run with full REAL capability coverage, not just `fixed-visible`, `fixed-latent`, and `growth-visible`?

## What Was Added

- New harness: `scripts/diagnose_c_family_real.py`
- New mode coverage:
  - `fixed-visible`
  - `fixed-latent`
  - `growth-visible`
  - `growth-latent`
- Warm transfer coverage from `task_a` into:
  - `task_b`
  - `task_c`
- New smoke test: `tests/test_c_family_real_diagnostic.py`

Unlike `compare_ceiling_benchmarks.py`, this harness is REAL-only and avoids importing the neural baseline stack. That keeps the modified C-family diagnostic runnable even when `numpy` / `torch` are not available.

## Runs Executed

### Run 1: seed-13 full sweep on `C3` and `C4`

Artifact:

- `docs/experiment_outputs/c_family_real_diagnostic_20260318_seed13.json`

Command surface:

- benchmark ids: `C3 C4`
- seeds: `13`
- transfer: enabled

### Run 2: 3-seed stability check on `C3`

Artifact:

- `docs/experiment_outputs/c_family_real_diagnostic_c3_3seed_20260318.json`

Command surface:

- benchmark id: `C3`
- seeds: `13 23 37`
- transfer: enabled

## C3 Results (3 seeds)

### Cold start, aggregated across `task_a/task_b/task_c`

| Method | Mean exact | Mean bit acc | Criterion rate |
|---|---:|---:|---:|
| fixed-latent | 0.2202 | 0.5334 | 0.0000 |
| growth-latent | 0.2212 | 0.5242 | 0.0000 |
| fixed-visible | 0.2047 | 0.4902 | 0.0000 |
| growth-visible | 0.2047 | 0.4840 | 0.0000 |

Cold read:

- latent modes are stronger than visible modes on `C3`
- adding morphogenesis to latent mode does not improve cold-start behavior
- `growth-visible` remains the weakest cold variant on the first hard ambiguity point

### Warm transfer from `task_a`

| Method | Transfer target | Warm exact | Warm bit acc | Delta exact vs cold target | Delta bit vs cold target |
|---|---|---:|---:|---:|---:|
| fixed-latent | task_b | 0.2654 | 0.5663 | +0.0802 | +0.0648 |
| fixed-latent | task_c | 0.1760 | 0.5293 | -0.0771 | -0.0309 |
| fixed-visible | task_b | 0.2130 | 0.5000 | -0.0524 | -0.0031 |
| fixed-visible | task_c | 0.1914 | 0.5108 | +0.0062 | +0.0232 |
| growth-latent | task_b | 0.1080 | 0.4321 | -0.1173 | -0.0787 |
| growth-latent | task_c | 0.1327 | 0.4460 | -0.1512 | -0.1327 |
| growth-visible | task_b | 0.2932 | 0.5355 | +0.0710 | +0.0617 |
| growth-visible | task_c | 0.1944 | 0.5154 | -0.0062 | +0.0185 |

Transfer read:

- `task_b` is the cleanest beneficiary of carryover on `C3`
- best transfer modes diverge by mechanism:
  - `fixed-latent` gives the best latent transfer into `task_b`
  - `growth-visible` gives the best visible transfer into `task_b`
- `task_c` does **not** show the same warm benefit:
  - only `fixed-visible` posts a slight exact-match gain
  - all latent transfer modes either regress or remain unstable
- `growth-latent` is the clear failure mode on `C3`; combining latent context and morphogenesis appears actively harmful on the ambiguity ladder

## C4 Results (seed 13 exploratory)

### Cold start, aggregated across `task_a/task_b/task_c`

| Method | Mean exact | Mean bit acc | Criterion rate |
|---|---:|---:|---:|
| fixed-visible | 0.1728 | 0.5116 | 0.0000 |
| growth-visible | 0.1636 | 0.4954 | 0.0000 |
| growth-latent | 0.1559 | 0.5224 | 0.0000 |
| fixed-latent | 0.1327 | 0.4946 | 0.0000 |

### Warm transfer from `task_a`

| Method | Transfer target | Warm exact | Warm bit acc | Delta exact vs cold target | Delta bit vs cold target |
|---|---|---:|---:|---:|---:|
| fixed-visible | task_b | 0.1620 | 0.5208 | +0.0185 | +0.0277 |
| fixed-visible | task_c | 0.1898 | 0.4931 | +0.0324 | -0.0115 |
| fixed-latent | task_b | 0.1852 | 0.5116 | +0.0695 | +0.0255 |
| fixed-latent | task_c | 0.1574 | 0.4421 | +0.0417 | -0.0556 |
| growth-visible | task_b | 0.1389 | 0.4815 | -0.0324 | -0.0185 |
| growth-visible | task_c | 0.1435 | 0.4653 | -0.0139 | -0.0231 |
| growth-latent | task_b | 0.1944 | 0.5162 | +0.0601 | +0.0255 |
| growth-latent | task_c | 0.2176 | 0.4884 | +0.0926 | -0.0139 |

Exploratory read:

- `C4` remains unstable and weak for all modes
- transfer can still help exact match, but the bit-accuracy changes are mixed and often negative
- `growth-visible` is again the least reliable transfer mode on the hardest ambiguity point
- `growth-latent` looks more promising than expected on exact match for `A -> C4 task_c`, but this is only a single seed and should not be treated as stable yet

## Working Interpretation

The full-capability runs sharpen the problem statement:

1. The main bottleneck in late Family C is not simple lack of morphogenesis.
`growth-visible` remains weak, and `growth-latent` can even regress sharply on `C3`.

2. Latent context helps more than morphogenesis on the first hard ambiguity point.
`fixed-latent` is the strongest cold-start mode on `C3`, and also the strongest warm mode for `A -> B`.

3. Transfer benefit is target-dependent.
Warm carryover helps `task_b` more consistently than `task_c` on the modified ambiguity ladder. This suggests the generated transform relationships no longer align with the original Task-C transfer geometry as cleanly as the named `A/B/C` scenarios did.

4. The combination "latent + morphogenesis" is not automatically the strongest path.
On `C3`, `growth-latent` is clearly worse than `fixed-latent`, which points to timing interference: growth likely fires before the hidden-context estimate has stabilized enough to seed productive new structure.

## Next Diagnostic Change

If the goal is to isolate the actual failure mechanism rather than just confirm difficulty, the next useful move is:

1. keep the new REAL-only harness
2. add a context-stability readout per run
3. compare `fixed-latent` vs `growth-latent` on `C3/C4`

That would test whether late Family C is failing because:

- the latent tracker never stabilizes
- it stabilizes too late for morphogenesis to help
- or it stabilizes, but the generated transform map is still too ambiguous for durable carryover
