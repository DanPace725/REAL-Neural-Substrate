# Occupancy Benchmark Protocol

This document freezes the **current canonical traditional baseline protocol** for the occupancy bridge task.

## Canonical preset

Preset name: `synth_v1_default`

## Fixed choices in this preset

- dataset: `data/occupancy_synth_v1.csv`
- normalization: enabled
- window size: `5`
- hidden size: `12`
- learning rate: `0.05`
- epochs: `60`
- seed: `0`
- train/test split: sequential `80/20`

## Why freeze this now?

We want the traditional benchmark target to stop moving before we design the REAL mapping.

That means:

- no silent changes to window length
- no silent changes to split policy
- no silent changes to default hyperparameters
- no ambiguity about which JSON artifact represents the canonical baseline run

## Allowed next changes

The next stage may add:

- extra named presets for robustness sweeps
- an external real occupancy dataset alongside this synthetic bridge benchmark
- comparison scripts that read the canonical preset artifact and a future REAL artifact side-by-side

But the `synth_v1_default` preset should remain the baseline reference unless we explicitly version a replacement.
