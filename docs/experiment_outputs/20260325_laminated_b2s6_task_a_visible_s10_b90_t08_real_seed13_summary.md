# 2026-03-25 1121 - laminated phase8

**timestamp:** `2026-03-25T18:21:16.154877Z`  
**harness:** `laminated_phase8`  
**scenarios:** ['B2S6']  
**seeds:** [13]

## Run identity

| Key | Value |
|---|---|
| benchmark_id | B2S6 |
| task_key | task_a |
| mode | visible |
| capability_policy | self-selected |
| seed | 13 |
| max_slices | 10 |
| initial_cycle_budget | 90 |
| accuracy_threshold | 0.8 |
| regulator_type | real |

## Baseline summary

| Metric | Value |
|---|---:|

## Laminated controller outcome

| Key | Value |
|---|---|
| final_decision | `continue` |
| final_cycle_budget | 38 |
| final_signal.next_slice_budget | 38 |
| final_signal.carryover_filter_mode | `drop` |
| final_signal.context_pressure | `high` |
| final_signal.decision_hint | `continue` |
| final_signal.stop_reason | `` |

## Slice summaries

| slice | budget | cycles | mode_used | min_ctx_acc | mean_bit_acc | conflict | ambiguity | uncertainty | cost | exact | partial | hint |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 90 | 90 | `self-selected` | 0.5345 | 0.6167 | 0.4000 | 1.0000 | 0.6650 | 89.5241 | 27.0000 | 57.0000 | `escalate` |
| 2 | 90 | 90 | `visible` | 0.6000 | 0.6023 | 0.4148 | 1.0000 | 0.6572 | 85.9957 | 27.0000 | 52.0000 | `escalate` |
| 3 | 90 | 90 | `visible` | 0.4821 | 0.6648 | 0.5500 | 1.0000 | 0.5704 | 59.5899 | 42.0000 | 37.0000 | `escalate` |
| 4 | 90 | 90 | `growth-visible` | 0.4808 | 0.4886 | 0.2375 | 1.0000 | 0.7646 | 90.7931 | 6.0000 | 74.0000 | `escalate` |
| 5 | 90 | 90 | `growth-visible` | 0.4400 | 0.5000 | 0.1919 | 0.9721 | 0.7500 | 63.9533 | 10.0000 | 66.0000 | `escalate` |
| 6 | 90 | 90 | `growth-visible` | 0.4630 | 0.4731 | 0.3726 | 0.8398 | 0.7637 | 50.8907 | 1.0000 | 86.0000 | `escalate` |
| 7 | 68 | 68 | `growth-visible` | 0.5556 | 0.5896 | 0.1746 | 0.9000 | 0.7509 | 17.5096 | 17.0000 | 45.0000 | `escalate` |
| 8 | 51 | 51 | `growth-visible` | 0.5147 | 0.5288 | 0.1385 | 0.6577 | 0.7668 | 9.6809 | 9.0000 | 37.0000 | `escalate` |
| 9 | 38 | 38 | `growth-visible` | 0.5625 | 0.5882 | 0.1456 | 0.9000 | 0.7381 | 5.0014 | 9.0000 | 22.0000 | `escalate` |
| 10 | 38 | 38 | `growth-visible` | 0.4833 | 0.5000 | 0.0671 | 0.7780 | 0.7046 | 35.6168 | 9.0000 | 23.0000 | `escalate` |
