# 2026-03-25 1132 - laminated phase8

**timestamp:** `2026-03-25T18:32:39.492892Z`  
**harness:** `laminated_phase8`  
**scenarios:** ['B2S1']  
**seeds:** [13]

## Run identity

| Key | Value |
|---|---|
| benchmark_id | B2S1 |
| task_key | task_a |
| mode | visible |
| capability_policy | self-selected |
| seed | 13 |
| max_slices | 10 |
| initial_cycle_budget | 8 |
| accuracy_threshold | 0.8 |
| regulator_type | real |

## Baseline summary

| Metric | Value |
|---|---:|

## Laminated controller outcome

| Key | Value |
|---|---|
| final_decision | `branch` |
| final_cycle_budget | 8 |
| final_signal.next_slice_budget | 6 |
| final_signal.carryover_filter_mode | `keep` |
| final_signal.context_pressure | `low` |
| final_signal.decision_hint | `branch` |
| final_signal.stop_reason | `productive_but_carried_context_incompatible` |

## Slice summaries

| slice | budget | cycles | mode_used | min_ctx_acc | mean_bit_acc | conflict | ambiguity | uncertainty | cost | exact | partial | hint |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 8 | 8 | `self-selected` | 0.5000 | 0.5625 | 0.3750 | 1.0000 | 0.7432 | 1.6145 | 2.0000 | 5.0000 | `continue` |
| 2 | 8 | 8 | `growth-visible` | 0.5000 | 0.5625 | 0.7563 | 1.0000 | 0.7513 | 1.5254 | 2.0000 | 5.0000 | `continue` |
