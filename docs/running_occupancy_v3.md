# Running the V3 Occupancy Experiment

All commands are run from the repo root.

## Historical note for ALIFE readers

The occupancy result discussed during the ALIFE paper-writing window is a March 2026 result, not a promise about current `main`. If you are trying to line up with the paper, the closest practical reference points are the saved artifacts in `docs/experiment_outputs/v3_best_real_seed13_summary.md` and `docs/experiment_outputs/v3_best_real_seed13.json`, plus a checkout or snapshot around commit `09f9b09`.

Current `main` has continued to evolve since that paper-facing run. The same V3 command family may therefore produce different F1 values today, even when the seed and headline settings match the saved configuration. Treat the saved March artifacts as the paper record, and treat current `main` as a later research branch of the occupancy work.

## Quick reference

| Goal | Command |
|---|---|
| Smoke test (fast) | `python -m scripts.run_occupancy_real_v3 --max-train-sessions 8 --max-eval-sessions 5` |
| Full single-seed run | `python -m scripts.run_occupancy_real_v3 --output-json docs/experiment_outputs/v3_seed13.json --summary-only` |
| Sequential debug run | `python -m scripts.run_occupancy_real_v3 --workers 1` |
| Different seed | `python -m scripts.run_occupancy_real_v3 --selector-seed 23 --output-json docs/experiment_outputs/v3_seed23.json --summary-only` |
| Multi-seed sweep with auto CPU budgeting | `python -m scripts.run_occupancy_real_v3 --selector-seeds 13 23 37 --summary-only --output-json docs/experiment_outputs/v3_sweep_13_23_37.json` |

## Key flags

### Data and split

| Flag | Default | Description |
|---|---|---|
| `--csv PATH` | `occupancy_baseline/data/occupancy_synth_v1.csv` | Occupancy CSV path. |
| `--window-size N` | `5` | Timesteps per rolling episode window. |
| `--train-session-fraction F` | `0.70` | Temporal fraction used for training sessions. |
| `--max-train-sessions N` | all | Optional training-session cap for smoke tests. |
| `--max-eval-sessions N` | all | Optional eval-session cap for smoke tests. |

### Harness behavior

| Flag | Default | Description |
|---|---|---|
| `--eval-mode MODE` | `fresh_session_eval` | `fresh_session_eval`, `persistent_eval`, or `both`. |
| `--topology-mode MODE` | `multihop_routing` | `fixed_small` control or `multihop_routing` benchmark default. |
| `--context-mode MODE` | `online_running_context` | `offline_session_context`, `online_running_context`, or `latent_context`. |
| `--ingress-mode MODE` | `admission_source` | REAL-native source admission or direct injection debug path. |

### Seed and worker control

| Flag | Default | Description |
|---|---|---|
| `--selector-seed N` | `13` | Single-seed run. |
| `--selector-seeds N...` | none | Optional multi-seed sweep. When present, it overrides `--selector-seed`. |
| `--workers N` | auto (~75% of visible CPUs) | Total worker budget. Single-seed runs use this for eval parallelism. Multi-seed sweeps partition it across concurrent seeds and per-seed eval workers. |

### Feedback and output

| Flag | Default | Description |
|---|---|---|
| `--feedback-amount F` | `0.18` | Feedback awarded per correctly routed packet. |
| `--eval-feedback-fraction F` | `1.0` | Eval-time feedback multiplier. |
| `--packet-ttl N` | `8` | Packet time-to-live in substrate cycles. |
| `--output-json PATH` | none | Write the full result dict to JSON. |
| `--summary-only` | off | Omit per-session episode lists from JSON output. |

## Worker behavior

The runner now auto-targets about 75% of visible CPU capacity when `--workers` is omitted.

- Single-seed run: that budget goes to eval protocol parallelism.
- Multi-seed sweep: that same budget is split across concurrent seed runs and per-seed eval workers.
- `--workers 1` forces the whole run into a sequential/debug-friendly mode.

Example on a 20-CPU machine:

- auto worker budget: `floor(20 * 0.75) = 15`
- sweep over `13 23 37`: `3` concurrent seeds, `5` eval workers per seed
- single seed: up to `15` eval workers for the fresh-session protocol

If process pools are unavailable in the environment, the runner reports
`fallback_sequential` in the output instead of failing.

## Output shape

- Single-seed run: the manifest `run_id` looks like `v3_seed13_<timestamp>`.
- Multi-seed sweep: the manifest `run_id` looks like `v3_sweep3seeds_<timestamp>`.
- Sweep JSON includes both `aggregate` metrics and `seed_summaries`, plus the
  full `seed_results` payload when deeper inspection is needed.

## Recommended runs

### 1. Fast smoke

```powershell
python -m scripts.run_occupancy_real_v3 `
  --max-train-sessions 8 `
  --max-eval-sessions 5 `
  --workers 1
```

### 2. Full single-seed benchmark

```powershell
python -m scripts.run_occupancy_real_v3 `
  --summary-only `
  --output-json docs/experiment_outputs/v3_seed13.json
```

### 3. Multi-seed sweep

```powershell
python -m scripts.run_occupancy_real_v3 `
  --selector-seeds 13 23 37 `
  --summary-only `
  --output-json docs/experiment_outputs/v3_sweep_13_23_37.json
```

The sweep output includes:

- aggregate warm vs cold delivery and accuracy
- aggregate early-session carryover deltas
- best seed by efficiency ratio
- per-seed summaries with protocol parallelism status

## What to inspect in results

- `aggregate.mean_efficiency_ratio` in a sweep, or `carryover_efficiency.mean_efficiency_ratio` in a single run, for the overall warm-vs-cold advantage.
- `session_1_delivery_delta`, `mean_first_episode_delivery_delta`, and `mean_first_three_episode_delivery_delta` for the orientation signal.
- `parallelism_status` and worker policy fields to confirm whether the run used process pools or fell back to sequential execution.
- context transfer status to make sure unseen-context claims are actually applicable.
