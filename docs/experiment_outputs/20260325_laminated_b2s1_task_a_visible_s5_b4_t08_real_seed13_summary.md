# 2026-03-25 1041 - laminated phase8

**timestamp:** `2026-03-25T17:41:46.149557Z`  
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
| max_slices | 5 |
| initial_cycle_budget | 4 |
| accuracy_threshold | 0.8 |
| regulator_type | real |

## Baseline summary

| Metric | Value |
|---|---:|
| cycles | 24.0000 |
| injected_packets | 18.0000 |
| admitted_packets | 18.0000 |
| delivered_packets | 18.0000 |
| delivery_ratio | 1.0000 |
| dropped_packets | 0.0000 |
| drop_ratio | 0.0000 |
| mean_latency | 1.0000 |
| mean_hops | 3.0000 |
| node_atp_total | 4.3136 |
| node_reward_total | 3.0000 |
| mean_route_cost | 0.0471 |
| total_action_cost | 5.5163 |
| exact_matches | 3.0000 |
| partial_matches | 11.0000 |
| mean_bit_accuracy | 0.4722 |
| mean_feedback_award | 0.0850 |
| node_count | 7.0000 |
| edge_count | 9.0000 |
| bud_successes | 0.0000 |
| prune_events | 0.0000 |
| apoptosis_events | 0.0000 |

### Context breakdown (baseline)

| context | count | exact_matches | mean_bit_accuracy |
|---|---:|---:|---:|
| context_0 | 6 | 1 | 0.5833 |
| context_1 | 12 | 2 | 0.4167 |

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

## Delta vs baseline (reported)

| Metric | Delta |
|---|---:|
| exact_matches | 0.0000 |
| mean_bit_accuracy | 0.0635 |
| total_action_cost | -3.3723 |

## Slice summaries

| slice | budget | cycles | mode_used | min_ctx_acc | mean_bit_acc | conflict | ambiguity | uncertainty | cost | exact | partial | hint |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 4 | 4 | `self-selected` | 0.5000 | 0.5000 | 0.3750 | 1.0000 | 0.7373 | 0.8745 | 1.0000 | 2.0000 | `continue` |
| 2 | 4 | 4 | `growth-visible` | 0.5000 | 0.6250 | 0.4125 | 1.0000 | 0.7752 | 0.8745 | 1.0000 | 3.0000 | `continue` |
| 3 | 4 | 4 | `growth-visible` | 0.5000 | 0.5000 | 0.4125 | 1.0000 | 0.7602 | 0.7370 | 1.0000 | 2.0000 | `escalate` |
| 4 | 4 | 4 | `growth-visible` | 0.5000 | 0.5000 | 0.2750 | 0.8250 | 0.7687 | 0.7340 | 1.0000 | 2.0000 | `continue` |
| 5 | 3 | 3 | `growth-visible` | 0.5000 | 0.5000 | 0.6750 | 0.4500 | 0.7272 | 0.6731 | 0.0000 | 2.0000 | `escalate` |
