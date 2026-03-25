# 2026-03-25 1112 - laminated phase8

**timestamp:** `2026-03-25T18:12:53.798649Z`  
**harness:** `laminated_phase8`  
**scenarios:** ['B2S5']  
**seeds:** [13]

## Run identity

| Key | Value |
|---|---|
| benchmark_id | B2S5 |
| task_key | task_a |
| mode | visible |
| capability_policy | self-selected |
| seed | 13 |
| max_slices | 10 |
| initial_cycle_budget | 47 |
| accuracy_threshold | 0.8 |
| regulator_type | real |

## Baseline summary

| Metric | Value |
|---|---:|

## Laminated controller outcome

| Key | Value |
|---|---|
| final_decision | `settle` |
| final_cycle_budget | 35 |
| final_signal.next_slice_budget | 35 |
| final_signal.carryover_filter_mode | `keep` |
| final_signal.context_pressure | `high` |
| final_signal.decision_hint | `settle` |
| final_signal.stop_reason | `coherence_flat_and_conflict_low` |

## Slice summaries

| slice | budget | cycles | mode_used | min_ctx_acc | mean_bit_acc | conflict | ambiguity | uncertainty | cost | exact | partial | hint |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 47 | 47 | `self-selected` | 0.5000 | 0.5532 | 0.3723 | 1.0000 | 0.7252 | 75.4113 | 13.0000 | 26.0000 | `escalate` |
| 2 | 47 | 47 | `visible` | 0.5172 | 0.5349 | 0.4070 | 1.0000 | 0.7371 | 72.1266 | 8.0000 | 30.0000 | `escalate` |
| 3 | 35 | 35 | `growth-visible` | 0.6042 | 0.6324 | 0.2250 | 0.9000 | 0.7514 | 89.4024 | 14.0000 | 15.0000 | `escalate` |
| 4 | 35 | 35 | `growth-visible` | 0.8000 | 0.9143 | 0.1429 | 1.0000 | 0.6425 | 0.0000 | 30.0000 | 4.0000 | `escalate` |
| 5 | 35 | 35 | `growth-visible` | 0.9792 | 0.9857 | 0.1571 | 1.0000 | 0.6198 | 0.0000 | 34.0000 | 1.0000 | `escalate` |
