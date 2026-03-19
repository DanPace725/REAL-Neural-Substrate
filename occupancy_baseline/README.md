# Occupancy Baseline — Traditional Neural Network Setup

This folder is the separate traditional-neural-network track for the first real-world comparison problem in Phase 8: **room occupancy detection from environmental sensors**.

The goal of this folder is to keep the conventional supervised baseline isolated from the native REAL substrate code so we can compare the two approaches cleanly.

## Why this problem

Occupancy detection is a small, real-world classification task that a simple neural network can solve:

- inputs are low-dimensional environmental sensor readings
- the target is binary (`occupied` vs `unoccupied`)
- short temporal windows matter, which makes it a good bridge from static classification to the sequential/local substrate logic in Phase 8

## Folder contents

- `dataset.py` — CSV loading, feature normalization, and rolling-window construction
- `mlp.py` — small pure-Python MLP baseline for binary classification
- `experiment.py` — reproducible experiment config/result helpers and JSON output support
- `presets.py` — named benchmark presets that freeze the canonical traditional-baseline protocol
- `run_baseline.py` — command-line entrypoint for loading data, training, and reporting metrics
- `benchmark_protocol.md` — the current fixed benchmark contract before REAL mapping begins
- `__init__.py` — exports the public setup utilities

## Expected CSV schema

The initial loader expects a CSV with these columns:

- `temperature`
- `humidity`
- `light`
- `co2`
- `humidity_ratio`
- `occupancy`

The label column should contain `0/1` values.

## Initial workflow

1. Start with the checked-in synthetic benchmark at `data/occupancy_synth_v1.csv` or swap in a real occupancy CSV later.
2. Build rolling windows from the sensor sequence.
3. Train a tiny MLP on the flattened windows.
4. Report accuracy / precision / recall / F1.
5. Use the same processed windows later as the input stream for a REAL comparison harness.

## Canonical preset

The current frozen traditional baseline is the `synth_v1_default` preset.

```bash
python -m occupancy_baseline.run_baseline --preset synth_v1_default
```

## Example override path

```bash
python -m occupancy_baseline.run_baseline \
  --csv occupancy_baseline/data/occupancy_synth_v1.csv \
  --window-size 5 \
  --hidden-size 12 \
  --epochs 60 \
  --output-json tests_tmp/occupancy_result.json
```

## Notes

- This folder is deliberately separate from the current CVT-1 synthetic comparison scripts.
- The first version keeps dependencies minimal: standard library only.
- A checked-in synthetic benchmark now gives us a stable in-repo starting point before we swap to an external real occupancy dataset.
- The CLI can now optionally save a JSON artifact, which gives us a stable handoff point for later REAL-side comparison harnesses.
- The canonical benchmark protocol is now frozen in `benchmark_protocol.md` and `presets.py` so the REAL mapping can target a stable baseline.
- `scripts/compare_occupancy_baseline.py` now provides the first in-repo REAL comparison path using the same normalized rolling windows as the frozen baseline.
