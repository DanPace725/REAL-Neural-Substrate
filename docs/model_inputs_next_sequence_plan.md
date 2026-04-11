# Model Inputs Next-Sequence Plan

## Dataset Shape

The current `model_inputs.csv` has:

- 990,000 rows
- 1,000 distinct `scenario_id` values
- 990 ordered windows per scenario (`window_start_index` runs `0..989`)
- one scalar target-like field: `result`
- two matrix-valued fields per window: `gasf` and `gadf`

The matrix columns are quoted and multiline, so the file must always be read with a real CSV parser.

## Why The Chunks Are Scenario-Aligned

The cleanest boundary is `scenario_id`.

Each scenario appears to be one temporal trajectory with 990 ordered windows. Splitting inside a scenario would break sequence continuity and make it harder for REAL to carry state or for any later loader to reconstruct temporal order. Splitting by contiguous scenario ranges keeps:

- each chunk semantically coherent
- window order intact
- chunk loading simple for both experiments and preprocessing
- session-style evaluation possible without cross-file stitching

Using 50 scenarios per chunk gives 20 chunk files, which is a good tradeoff between file size and file count.

## Best First REAL Experiment

The fastest path is to reuse the pattern already proven in the occupancy harness:

- packetize each window into a small number of discrete signals
- let REAL carry state across ordered windows within one `scenario_id`
- ask the forecast/readout layer to predict the next step

### Stage 1: Start With A Reduced Prediction Target

Do not ask REAL to predict the full next `gasf` or `gadf` matrix first.

Start with one of these:

1. `next_result_bucket`
2. `next_result_sign`
3. `next_result_delta_bucket`

That gives us a tractable first benchmark and a clean success metric.

## How To Represent Each Window For REAL

Use the occupancy flow as the template:

- `scripts/occupancy_real.py`
- `scripts/occupancy_real_v3.py`
- `occupancy_baseline/dataset.py`

For each row/window, derive compact features such as:

- current `result`
- delta from previous `result`
- `gasf_mean`, `gasf_std`, `gasf_diag_mean`, `gasf_abs_mean`
- `gadf_mean`, `gadf_std`, `gadf_diag_mean`, `gadf_abs_mean`
- optional coarse energy bins for selected matrix regions

Then quantize those summaries into bit packets the same way occupancy bins sensor values into packets.

That keeps the task aligned with REAL's local-routing substrate instead of forcing huge dense tensors directly into the nodes.

## How A Session Should Run

Treat one `scenario_id` as one REAL session.

For each scenario:

1. Feed windows in ascending `window_start_index`.
2. At step `t`, expose packets for window `t`.
3. Ask REAL to forecast a label for window `t + 1`.
4. Reveal the true next label after the prediction.
5. Route feedback locally and let carryover accumulate within the scenario.
6. Reset or partially reset between scenarios.

That mirrors the repo's existing stance:

- local prediction before action
- local feedback after outcome
- durable learning written into substrate/carryover

## Recommended Benchmark Structure

Split by scenario, not by row.

- Train scenarios: `0..699`
- Validation scenarios: `700..849`
- Eval scenarios: `850..999`

Within each scenario, preserve full temporal order. This avoids leakage from neighboring windows of the same underlying sequence.

## How To Judge Success

Since the semantic meaning of `result` is still unclear, the first success criteria should be operational rather than interpretive.

Measure:

1. next-step direction accuracy
2. precision / recall / F1 for the `next_result_up` label
3. mean scenario accuracy
4. gain over simple baselines

The two most important baselines are:

- `majority_label`: always predict the most common training label
- `repeat_last_delta_direction`: predict that the next step will continue the current direction

For an early harness, REAL is doing something interesting if it:

- beats both baselines on held-out scenarios
- stays above them across more than one seed
- does not collapse into predicting only one class

If it only beats one baseline, that still tells us something useful about what kind of temporal structure it is or is not picking up.

## Minimal Implementation Path

1. Add a loader that streams one scenario at a time from the chunk files.
2. Add a summarizer that converts `gasf` and `gadf` into compact numeric features.
3. Add a packetizer that maps those features into bit packets.
4. Clone the occupancy harness pattern into a new script, for example `scripts/model_inputs_real_v1.py`.
5. Start with `next_result_bucket` prediction.
6. Compare against a tiny baseline such as:
   - persist last bucket
   - predict sign of last delta
   - small MLP on the compact features

## What I Would Build Next

If we want to move from proposal to runnable experiment, the best next deliverable is:

- a compact feature-extraction script for `gasf`/`gadf`
- a `model_inputs_real_v1.py` harness modeled after `occupancy_real_v3.py`
- a first evaluation on one or two chunk files before scaling to all 20

That would give us an honest read on whether REAL can learn sequential anticipation on this dataset without immediately overcomplicating the representation.
