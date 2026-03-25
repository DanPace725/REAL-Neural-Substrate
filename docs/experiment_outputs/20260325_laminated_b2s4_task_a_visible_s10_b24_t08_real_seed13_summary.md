# 2026-03-25 1111 - laminated phase8

**timestamp:** `2026-03-25T18:11:54.003120Z`  
**harness:** `laminated_phase8`  
**scenarios:** ['B2S4']  
**seeds:** [13]

## Run identity

| Key | Value |
|---|---|
| benchmark_id | B2S4 |
| task_key | task_a |
| mode | visible |
| capability_policy | self-selected |
| seed | 13 |
| max_slices | 10 |
| initial_cycle_budget | 24 |
| accuracy_threshold | 0.8 |
| regulator_type | real |

## Baseline summary

| Metric | Value |
|---|---:|

## Laminated controller outcome

| Key | Value |
|---|---|
| final_decision | `continue` |
| final_cycle_budget | 18 |
| final_signal.next_slice_budget | 18 |
| final_signal.carryover_filter_mode | `keep` |
| final_signal.context_pressure | `medium` |
| final_signal.decision_hint | `continue` |
| final_signal.stop_reason | `` |

## Slice summaries

| slice | budget | cycles | mode_used | min_ctx_acc | mean_bit_acc | conflict | ambiguity | uncertainty | cost | exact | partial | hint |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 24 | 24 | `self-selected` | 0.5000 | 0.6458 | 0.3750 | 1.0000 | 0.7283 | 43.3489 | 9.0000 | 13.0000 | `escalate` |
| 2 | 24 | 24 | `visible` | 0.4688 | 0.5417 | 0.2292 | 0.7500 | 0.7569 | 45.5106 | 3.0000 | 20.0000 | `escalate` |
| 3 | 24 | 24 | `growth-visible` | 0.5333 | 0.5833 | 0.2292 | 1.0000 | 0.7545 | 45.8903 | 7.0000 | 14.0000 | `escalate` |
| 4 | 24 | 24 | `growth-visible` | 0.5588 | 0.5870 | 0.1957 | 1.0000 | 0.7508 | 9.2674 | 6.0000 | 15.0000 | `escalate` |
| 5 | 24 | 24 | `growth-visible` | 0.5714 | 0.5714 | 0.2619 | 1.0000 | 0.7501 | 28.2176 | 7.0000 | 10.0000 | `escalate` |
| 6 | 24 | 24 | `growth-visible` | 0.5833 | 0.7692 | 0.1346 | 1.0000 | 0.7103 | 12.9056 | 15.0000 | 10.0000 | `escalate` |
| 7 | 24 | 24 | `growth-visible` | 0.4286 | 0.7500 | 0.3385 | 1.0000 | 0.6738 | 23.2067 | 14.0000 | 11.0000 | `escalate` |
| 8 | 24 | 24 | `growth-visible` | 0.5000 | 0.8333 | 0.3333 | 1.0000 | 0.6199 | 8.4651 | 18.0000 | 4.0000 | `escalate` |
| 9 | 24 | 24 | `growth-visible` | 0.4375 | 0.7955 | 0.3182 | 1.0000 | 0.6455 | 1.9454 | 16.0000 | 3.0000 | `escalate` |
| 10 | 18 | 18 | `growth-visible` | 0.5000 | 0.7500 | 0.2250 | 0.9000 | 0.6851 | 0.0000 | 1.0000 | 1.0000 | `escalate` |
