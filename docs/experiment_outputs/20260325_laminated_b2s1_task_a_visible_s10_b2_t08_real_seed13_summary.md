# 2026-03-25 1131 - laminated phase8

**timestamp:** `2026-03-25T18:31:58.157599Z`  
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
| initial_cycle_budget | 2 |
| accuracy_threshold | 0.8 |
| regulator_type | real |

## Baseline summary

| Metric | Value |
|---|---:|

## Laminated controller outcome

| Key | Value |
|---|---|
| final_decision | `continue` |
| final_cycle_budget | 2 |
| final_signal.next_slice_budget | 2 |
| final_signal.carryover_filter_mode | `keep` |
| final_signal.context_pressure | `low` |
| final_signal.decision_hint | `continue` |
| final_signal.stop_reason | `` |

## Slice summaries

| slice | budget | cycles | mode_used | min_ctx_acc | mean_bit_acc | conflict | ambiguity | uncertainty | cost | exact | partial | hint |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 2 | 2 | `self-selected` | 0.5000 | 0.7500 | 0.2500 | 1.0000 | 0.7495 | 0.3000 | 1.0000 | 1.0000 | `continue` |
| 2 | 2 | 2 | `visible` | 0.2500 | 0.2500 | 0.5500 | 1.0000 | 0.7500 | 0.3000 | 0.0000 | 1.0000 | `continue` |
| 3 | 2 | 2 | `growth-visible` | 0.5000 | 0.5000 | 0.5500 | 1.0000 | 0.7766 | 0.3000 | 0.0000 | 2.0000 | `continue` |
| 4 | 2 | 2 | `growth-visible` | 0.5000 | 0.7500 | 0.2500 | 1.0000 | 0.7738 | 0.5745 | 1.0000 | 1.0000 | `continue` |
| 5 | 2 | 2 | `growth-visible` | 0.0000 | 0.2500 | 0.2500 | 0.5000 | 0.7567 | 0.2970 | 0.0000 | 1.0000 | `continue` |
| 6 | 2 | 2 | `growth-visible` | 0.2500 | 0.2500 | 0.2500 | 0.5000 | 0.7740 | 0.3000 | 0.0000 | 1.0000 | `escalate` |
| 7 | 2 | 2 | `growth-visible` | 0.5000 | 0.7500 | 0.2250 | 0.9000 | 0.7913 | 0.4236 | 1.0000 | 1.0000 | `continue` |
| 8 | 2 | 2 | `growth-visible` | 0.0000 | 0.2500 | 0.2250 | 0.4500 | 0.7622 | 0.4326 | 0.0000 | 1.0000 | `continue` |
| 9 | 2 | 2 | `growth-visible` | 0.5000 | 0.5000 | 0.2250 | 0.4500 | 0.7502 | 0.5659 | 0.0000 | 2.0000 | `continue` |
| 10 | 2 | 2 | `growth-visible` | — | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.5400 | 0.0000 | 0.0000 | `settle` |
