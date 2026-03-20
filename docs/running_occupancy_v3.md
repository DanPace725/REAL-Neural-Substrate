# Running the V3 Occupancy Experiment

All commands are run from the **repo root** (the folder containing `scripts/`, `occupancy_baseline/`, etc.).

---

## Quick reference

| Goal | Command |
|---|---|
| Smoke test (fast) | `python -m scripts.run_occupancy_real_v3 --max-train-sessions 8 --max-eval-sessions 5` |
| Full run, results to JSON | `python -m scripts.run_occupancy_real_v3 --output-json docs/experiment_outputs/v3_seed13.json` |
| Full run, summary only | `python -m scripts.run_occupancy_real_v3 --summary-only` |
| Sequential (no parallelism) | `python -m scripts.run_occupancy_real_v3 --workers 1` |
| Different seed | `python -m scripts.run_occupancy_real_v3 --selector-seed 23 --output-json docs/experiment_outputs/v3_seed23.json` |

---

## All flags

### Data

| Flag | Default | Description |
|---|---|---|
| `--csv PATH` | `occupancy_baseline/data/occupancy_synth_v1.csv` | Path to the occupancy CSV file. |
| `--window-size N` | `5` | Number of timesteps per rolling episode window. |

### Session split

| Flag | Default | Description |
|---|---|---|
| `--train-session-fraction F` | `0.70` | Fraction of state-transition sessions (in temporal order) used for training. The remaining sessions form the eval set. |
| `--max-train-sessions N` | *(all)* | Hard cap on training sessions. Applied after the temporal split. Useful for smoke tests. |
| `--max-eval-sessions N` | *(all)* | Hard cap on eval sessions. Applied after the temporal split. |

### Substrate / feedback

| Flag | Default | Description |
|---|---|---|
| `--selector-seed N` | `13` | Seed for the `NativeSubstrateSystem` selector. Change this to get independent replications. |
| `--feedback-amount F` | `0.18` | Feedback amount per correctly-routed packet. |
| `--eval-feedback-fraction F` | `1.0` | Fraction of `feedback-amount` applied during eval sessions. Default is full feedback — do not reduce this below 1.0 without a specific reason (see v2 synthesis for why). |
| `--packet-ttl N` | `8` | Packet time-to-live in substrate cycles. |

### Execution

| Flag | Default | Description |
|---|---|---|
| `--workers N` | `2` | Worker processes for the warm/cold eval phase. `2` runs them in parallel (recommended). `1` runs sequentially — useful for debugging or when process spawning is unavailable. |

### Output

| Flag | Default | Description |
|---|---|---|
| `--output-json PATH` | *(none)* | Write the full result dict to this JSON file. The directory is created if it does not exist. |
| `--summary-only` | off | When set, per-session result lists are omitted from the JSON output (smaller files, same summary metrics). |

---

## Timing estimates

All timings on the synth_v1 dataset (89 sessions, 1,340 episodes):

| Mode | Approx. wall time |
|---|---|
| Smoke test (`--max-train-sessions 8 --max-eval-sessions 5`) | ~90s |
| Full run, `--workers 2` (parallel eval) | ~6–7 min |
| Full run, `--workers 1` (sequential) | ~10 min |

---

## Manifest

Every run prints a manifest block at the top and bottom of stdout:

```
------------------------------------------------------------
  run_id:   v3_seed13_20260319T170000Z
  run_at:   2026-03-19T17:00:00+00:00
  git_sha:  c357957
  csv:      occupancy_baseline/data/occupancy_synth_v1.csv
  seed:     13  window: 5  train_frac: 0.7
  workers:  2
  elapsed:  412.3s
------------------------------------------------------------
```

The manifest is also written into the JSON output under the key `"manifest"`, so every result file is self-describing. The `run_id` uses the format `v3_seed{N}_{timestamp}` — use it to label output filenames when running multi-seed sweeps.

---

## Recommended runs

### 1. Smoke test — verify the pipeline works

```
python -m scripts.run_occupancy_real_v3 ^
    --max-train-sessions 8 ^
    --max-eval-sessions 5 ^
    --workers 1
```

Takes ~90s. No JSON output. Use `--workers 1` to keep all output in one process for easier debugging.

### 2. Full single-seed run

```
python -m scripts.run_occupancy_real_v3 ^
    --output-json docs/experiment_outputs/v3_seed13.json ^
    --summary-only
```

Takes ~6–7 min with default `--workers 2`. `--summary-only` keeps the JSON file small (omits per-session episode lists while keeping all learning curves and metrics).

### 3. Multi-seed sweep (seeds 13, 23, 37)

Run each in a separate terminal or sequentially:

```
python -m scripts.run_occupancy_real_v3 --selector-seed 13 --output-json docs/experiment_outputs/v3_seed13.json --summary-only
python -m scripts.run_occupancy_real_v3 --selector-seed 23 --output-json docs/experiment_outputs/v3_seed23.json --summary-only
python -m scripts.run_occupancy_real_v3 --selector-seed 37 --output-json docs/experiment_outputs/v3_seed37.json --summary-only
```

Compare `carryover_efficiency.mean_efficiency_ratio` across seeds to distinguish signal from substrate noise.

### 4. Full run with per-session episode detail

```
python -m scripts.run_occupancy_real_v3 ^
    --output-json docs/experiment_outputs/v3_seed13_full.json
```

Omit `--summary-only` to include `train_session_results`, `warm_eval_session_results`, and `cold_eval_session_results` in the JSON. These contain the per-session delivery ratio, accuracy, and episode count for every session — useful for plotting learning curves.

---

## What to look for in the results

The terminal output is structured in four sections:

**Phase 1 — Session inventory**
Confirms the dataset segmented correctly. Check `by_context_code` to verify all four context classes (0–3) are present in training. If any context code is absent from training but present in eval, the context transfer probe will show an unseen-context comparison.

**Phase 2 — Training run summary**
Episode-level accuracy and F1 across all training sessions run sequentially. Rising delivery ratio across sessions is the learning signal.

**Phase 3 — Carryover efficiency**
The core claim. Look at:
- `mean_efficiency_ratio` — warm delivery / cold delivery averaged over all eval sessions. Values > 1.0 mean carryover helps.
- `warm_sessions_to_80pct` vs `cold_sessions_to_80pct` — how many eval sessions before the system reaches 80% delivery ratio. A lower warm number confirms faster orientation with carryover.
- The delivery-at-session-N table — shows the trajectory, not just the mean.

**Phase 4 — Context transfer probe**
`warm_seen_mean_delivery` vs `warm_unseen_mean_delivery` — if the substrate's context-indexed action supports are doing useful work, seen-context sessions should route better than unseen-context sessions on the warm path. The cold path should show no such difference (no context-indexed support exists in a cold substrate).
