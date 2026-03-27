# 2026-03-26 1338 - Hidden Regime Budget 4 Safety 100 Sweep

**Type:** Experiment trace  
**Author:** Codex  
**Model:** GPT-5 Codex

## Purpose

This run revisits the hidden-regime laminated benchmark after the `budget=8`
pass underperformed. The intent was to restore the shorter slice budget that
had shown cleaner behavior (`budget=4`) while greatly increasing the slice
headroom to `safety_limit=100`.

## Configuration

Command:

- `python -m scripts.evaluate_hidden_regime_forecasting --sweep HR1,HR2,HR4 --all-tasks --observable hidden --reg real --budget 4 --safety-limit 100 --compact`

Key settings:

- benchmark family: `HR1`, `HR2`, `HR4`
- tasks: `task_a`, `task_b`, `task_c`
- observable mode: hidden
- regulator: `real`
- initial slice budget: `4`
- safety limit: `100`

## Results

- `HR1/task_a`: `0.750`, continue, 100 slices
- `HR1/task_b`: `0.875`, continue, 100 slices
- `HR1/task_c`: `0.750`, continue, 100 slices
- `HR2/task_a`: `0.875`, continue, 100 slices
- `HR2/task_b`: `0.750`, continue, 100 slices
- `HR2/task_c`: `0.250`, continue, 100 slices
- `HR4/task_a`: `0.750`, continue, 100 slices
- `HR4/task_b`: `0.700`, continue, 100 slices
- `HR4/task_c`: `1.000`, settle, 4 slices

Saved outputs:

- `docs/experiment_outputs/20260326_133714_141319_hidden_regime_hr1_task_a_hidden_self_selected_b4_s100_seed13.json`
- `docs/experiment_outputs/20260326_133714_141319_hidden_regime_hr1_task_b_hidden_self_selected_b4_s100_seed13.json`
- `docs/experiment_outputs/20260326_133714_141319_hidden_regime_hr1_task_c_hidden_self_selected_b4_s100_seed13.json`
- `docs/experiment_outputs/20260326_133714_141319_hidden_regime_hr2_task_a_hidden_self_selected_b4_s100_seed13.json`
- `docs/experiment_outputs/20260326_133714_141319_hidden_regime_hr2_task_b_hidden_self_selected_b4_s100_seed13.json`
- `docs/experiment_outputs/20260326_133714_141319_hidden_regime_hr2_task_c_hidden_self_selected_b4_s100_seed13.json`
- `docs/experiment_outputs/20260326_133714_141319_hidden_regime_hr4_task_a_hidden_self_selected_b4_s100_seed13.json`
- `docs/experiment_outputs/20260326_133714_141319_hidden_regime_hr4_task_b_hidden_self_selected_b4_s100_seed13.json`
- `docs/experiment_outputs/20260326_133714_141319_hidden_regime_hr4_task_c_hidden_self_selected_b4_s100_seed13.json`
- `docs/experiment_outputs/20260326_133714_141319_hidden_regime_suite_hr1_hr2_hr4_all_tasks_hidden_self_selected_b4_s100_seed13.json`

## Working Read

Compared with the earlier `budget=4 / safety_limit=30` runs:

- several cases improved materially with the longer safety horizon
- `HR4/task_c` remained the cleanest success and still settled quickly
- most cases still did not settle even with 100 slices
- `HR2/task_c` degraded sharply and looks like a strong candidate for slice-level
  diagnosis

The current pattern suggests that:

- shorter slices are still better than the `budget=8` alternative for this
  benchmark family
- some tasks benefit from more opportunities for slow-layer intervention
- the remaining failures are not just "ran out of slices"; some appear to be
  genuinely unstable or misdirected under the current policy-selection dynamics

## Next Direction

The next useful move is probably not another blind sweep. The highest-signal
follow-up would be a slice-by-slice analysis of:

- `HR2/task_c` as a degradation case
- `HR4/task_c` as the strongest quick-settle success
- one of `HR1/task_b` or `HR2/task_a` as a high-but-non-settling case
