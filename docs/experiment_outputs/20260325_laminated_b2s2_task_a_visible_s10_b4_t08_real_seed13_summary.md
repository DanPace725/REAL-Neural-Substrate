# 2026-03-25 1131 - laminated phase8

**timestamp:** `2026-03-25T18:31:59.161883Z`  
**harness:** `laminated_phase8`  
**scenarios:** ['B2S2']  
**seeds:** [13]

## Run identity

| Key | Value |
|---|---|
| benchmark_id | B2S2 |
| task_key | task_a |
| mode | visible |
| capability_policy | self-selected |
| seed | 13 |
| max_slices | 10 |
| initial_cycle_budget | 4 |
| accuracy_threshold | 0.8 |
| regulator_type | real |

## Baseline summary

| Metric | Value |
|---|---:|

## Laminated controller outcome

| Key | Value |
|---|---|
| final_decision | `settle` |
| final_cycle_budget | 3 |
| final_signal.next_slice_budget | 3 |
| final_signal.carryover_filter_mode | `soften` |
| final_signal.context_pressure | `high` |
| final_signal.decision_hint | `settle` |
| final_signal.stop_reason | `coherence_flat_and_conflict_low` |

## Slice summaries

| slice | budget | cycles | mode_used | min_ctx_acc | mean_bit_acc | conflict | ambiguity | uncertainty | cost | exact | partial | hint |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 4 | 4 | `self-selected` | 0.5000 | 0.5000 | 0.5000 | 1.0000 | 0.7571 | 1.5365 | 0.0000 | 4.0000 | `continue` |
| 2 | 4 | 4 | `visible` | 0.5000 | 0.5000 | 0.3750 | 1.0000 | 0.7578 | 1.5365 | 1.0000 | 2.0000 | `continue` |
| 3 | 4 | 4 | `growth-visible` | 0.3333 | 0.3750 | 0.5500 | 1.0000 | 0.7795 | 1.5515 | 0.0000 | 3.0000 | `continue` |
| 4 | 4 | 4 | `growth-visible` | 0.2500 | 0.3750 | 0.5500 | 1.0000 | 0.7731 | 1.6970 | 0.0000 | 3.0000 | `escalate` |
| 5 | 4 | 4 | `growth-visible` | 0.5000 | 0.6250 | 0.5000 | 1.0000 | 0.7679 | 1.5585 | 1.0000 | 3.0000 | `continue` |
| 6 | 4 | 4 | `growth-visible` | 0.6250 | 0.6250 | 0.5500 | 1.0000 | 0.7789 | 1.3065 | 2.0000 | 1.0000 | `escalate` |
| 7 | 4 | 4 | `growth-visible` | 0.7500 | 0.8750 | 0.2750 | 1.0000 | 0.7244 | 1.8502 | 3.0000 | 1.0000 | `continue` |
| 8 | 4 | 4 | `growth-visible` | 0.5000 | 0.7500 | 0.9625 | 1.0000 | 0.6968 | 1.2705 | 2.0000 | 2.0000 | `escalate` |
| 9 | 3 | 3 | `growth-visible` | 1.0000 | 1.0000 | 0.1500 | 0.9000 | 0.6668 | 1.1360 | 3.0000 | 0.0000 | `escalate` |
| 10 | 3 | 3 | `growth-visible` | 1.0000 | 1.0000 | 0.5500 | 1.0000 | 0.6536 | 0.9368 | 1.0000 | 0.0000 | `escalate` |
