# 2026-03-25 1111 - laminated phase8

**timestamp:** `2026-03-25T18:11:30.804044Z`  
**harness:** `laminated_phase8`  
**scenarios:** ['B2S3']  
**seeds:** [13]

## Run identity

| Key | Value |
|---|---|
| benchmark_id | B2S3 |
| task_key | task_a |
| mode | visible |
| capability_policy | self-selected |
| seed | 13 |
| max_slices | 10 |
| initial_cycle_budget | 12 |
| accuracy_threshold | 0.8 |
| regulator_type | real |

## Baseline summary

| Metric | Value |
|---|---:|

## Laminated controller outcome

| Key | Value |
|---|---|
| final_decision | `settle` |
| final_cycle_budget | 7 |
| final_signal.next_slice_budget | 7 |
| final_signal.carryover_filter_mode | `keep` |
| final_signal.context_pressure | `high` |
| final_signal.decision_hint | `settle` |
| final_signal.stop_reason | `coherence_flat_and_conflict_low` |

## Slice summaries

| slice | budget | cycles | mode_used | min_ctx_acc | mean_bit_acc | conflict | ambiguity | uncertainty | cost | exact | partial | hint |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 12 | 12 | `self-selected` | 0.3889 | 0.4167 | 0.3750 | 1.0000 | 0.7465 | 14.1866 | 3.0000 | 4.0000 | `continue` |
| 2 | 12 | 12 | `growth-visible` | 0.5000 | 0.5417 | 0.4583 | 1.0000 | 0.7716 | 14.2946 | 2.0000 | 9.0000 | `continue` |
| 3 | 9 | 9 | `growth-visible` | 0.6667 | 0.8333 | 0.3500 | 0.9000 | 0.7170 | 9.7442 | 6.0000 | 3.0000 | `escalate` |
| 4 | 9 | 9 | `growth-visible` | 0.8333 | 0.9444 | 0.4278 | 1.0000 | 0.6695 | 7.0254 | 8.0000 | 1.0000 | `escalate` |
| 5 | 7 | 7 | `growth-visible` | 1.0000 | 1.0000 | 0.3214 | 0.9000 | 0.6388 | 4.5089 | 7.0000 | 0.0000 | `escalate` |
