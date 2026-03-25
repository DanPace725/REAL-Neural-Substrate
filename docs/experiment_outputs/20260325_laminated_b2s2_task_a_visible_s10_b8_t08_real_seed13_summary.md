# 2026-03-25 1132 - laminated phase8

**timestamp:** `2026-03-25T18:32:40.481143Z`  
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
| initial_cycle_budget | 8 |
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
| 1 | 8 | 8 | `self-selected` | 0.3333 | 0.3750 | 0.5000 | 1.0000 | 0.7528 | 3.1990 | 0.0000 | 6.0000 | `continue` |
| 2 | 8 | 8 | `growth-visible` | 0.3000 | 0.3750 | 0.5000 | 1.0000 | 0.7756 | 3.3885 | 0.0000 | 6.0000 | `continue` |
| 3 | 8 | 8 | `growth-visible` | 0.2857 | 0.3125 | 0.5500 | 1.0000 | 0.7659 | 3.2732 | 0.0000 | 5.0000 | `escalate` |
| 4 | 8 | 8 | `growth-visible` | 0.6000 | 0.6250 | 0.5000 | 1.0000 | 0.7632 | 2.8023 | 2.0000 | 6.0000 | `escalate` |
| 5 | 8 | 8 | `growth-visible` | 0.2500 | 0.3750 | 0.6875 | 0.8250 | 0.7873 | 2.6654 | 0.0000 | 3.0000 | `escalate` |
| 6 | 8 | 6 | `growth-visible` | — | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 1.3748 | 0.0000 | 0.0000 | `continue` |
| 7 | 6 | 0 | `growth-visible` | — | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | `settle` |
| 8 | 4 | 0 | `growth-visible` | — | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | `settle` |
| 9 | 3 | 0 | `growth-visible` | — | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | `settle` |
| 10 | 2 | 0 | `growth-visible` | — | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | `settle` |
