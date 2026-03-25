# 2026-03-24 1705 - C Scale Transfer Slice

## Purpose

This trace records the first transfer-capable extension of the dedicated
`compare_c_scale_suite.py` harness.

The immediate goal was to stop treating C-family transfer as a one-off exploratory
diagnostic and instead make it a first-class part of the new ambiguity-scale lane.
The target use case is:

- train on `task_a`
- evaluate transfer on `task_c`
- compare `cold` vs `warm` carryover on the same scaled C-family point
- keep the run REAL-only and small enough to iterate on without the full ceiling stack

## What Changed

- extended `scripts/compare_c_scale_suite.py` with an optional transfer slice
- added focused transfer coverage in `tests/test_c_scale_suite.py`

The new transfer path:

- keeps the existing cold-start scale runs intact
- optionally runs a `cold` transfer-task baseline
- optionally runs a `warm` transfer-task evaluation after training on `task_a`
- stores the transfer results in `result["transfer_slice"]`
- records deltas on the warm aggregate relative to cold:
  - `exact_match_rate_delta_vs_cold`
  - `bit_accuracy_delta_vs_cold`
  - `elapsed_ratio_vs_cold`

CLI additions:

- `--include-transfer`
- `--train-task`
- `--transfer-tasks`

## Validation

Validation commands:

- `C:\Python313\python.exe -m py_compile scripts\compare_c_scale_suite.py tests\test_c_scale_suite.py`
- `C:\Python313\python.exe -m unittest tests.test_c_scale_suite`

Both completed successfully.

## First Transfer Run

Command:

- `C:\Python313\python.exe -m scripts.compare_c_scale_suite --benchmarks C3S5 --tasks task_a --methods fixed-visible fixed-latent --seeds 13 --include-transfer --train-task task_a --transfer-tasks task_c --output docs\experiment_outputs\c3_scale_c3s5_transfer_task_a_to_c_seed13_visible_latent_20260324.json`

Note:

- an earlier wider run including `growth-visible` hit the session timeout before
  finishing, so the first confirmed transfer slice was narrowed to the two fixed
  modes to get a reliable result on record first

## First C-Scale Transfer Result: `C3S5`, `task_a -> task_c`

### `fixed-visible`

- cold exact / bit: `0.3866 / 0.5938`
- warm exact / bit: `0.4375 / 0.6424`
- delta vs cold: `+0.0509 exact`, `+0.0486 bit`
- criterion:
  - cold: reached
  - warm: reached earlier, with stronger best rolling performance

### `fixed-latent`

- cold exact / bit: `0.3380 / 0.5810`
- warm exact / bit: `0.1806 / 0.4132`
- delta vs cold: `-0.1574 exact`, `-0.1678 bit`
- criterion:
  - cold: not reached
  - warm: not reached and clearly worse

## Interpretation

This is the first strong split in the new C-family work between cold-start scaling
and transfer scaling.

1. Visible carryover can help on the ambiguity lane.

That is important because the C-scale cold-start results made the family look
flat and ambiguity-limited. The transfer slice shows that warm visible carryover
can still improve behavior even in this weak-observation regime.

2. Latent carryover can be actively harmful here.

This is stronger than "latent did not help." On this first `C3S5` transfer run,
latent warm carryover materially degraded both exact-match rate and bit accuracy
relative to the cold latent baseline.

3. C-family still looks highly path-dependent.

The cold-start `C3S6` result suggested latent may become the strongest mode at
larger ambiguity scale points. But the first transfer result at `C3S5` shows that
the same latent path can become worse under carryover. That makes the family more
subtle than a simple "visible bad, latent good" story.

## Working Read

The current C-family picture is now:

- cold-start scale:
  - ambiguity remains the dominant bottleneck
  - latent becomes more competitive as scale increases
- transfer:
  - visible carryover can still be useful
  - latent carryover can destabilize transfer rather than helping it

That suggests the C-family transfer problem is not only about hidden-state
inference. It is also about whether the stored substrate aligns or conflicts with
the next ambiguous task regime.

## Next Steps

1. Confirm the `C3S5 task_a -> task_c` visible/latent transfer split with a second
   seed.
2. Decide whether `growth-visible` is worth rerunning separately on transfer or if
   the cost is too high for the information gain.
3. Extend transfer to `C3S6` only after the `C3S5` split is confirmed, so the next
   larger-point run has a cleaner expectation.
