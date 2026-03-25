# 2026-03-25 1042 - laminated phase8

**timestamp:** `2026-03-25T17:42:59.043956Z`  
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
| max_slices | 5 |
| initial_cycle_budget | 48 |
| accuracy_threshold | 0.8 |
| regulator_type | real |

## Baseline summary

| Metric | Value |
|---|---:|
| cycles | 244.0000 |
| injected_packets | 216.0000 |
| admitted_packets | 216.0000 |
| delivered_packets | 216.0000 |
| delivery_ratio | 1.0000 |
| dropped_packets | 0.0000 |
| drop_ratio | 0.0000 |
| mean_latency | 1.9306 |
| mean_hops | 7.4769 |
| node_atp_total | 7.0403 |
| node_reward_total | 6.5200 |
| mean_route_cost | 0.0398 |
| total_action_cost | 46.8313 |
| exact_matches | 69.0000 |
| partial_matches | 121.0000 |
| mean_bit_accuracy | 0.5995 |
| mean_feedback_award | 0.1079 |
| node_count | 51.0000 |
| edge_count | 95.0000 |
| bud_successes | 0.0000 |
| prune_events | 0.0000 |
| apoptosis_events | 0.0000 |

### Context breakdown (baseline)

| context | count | exact_matches | mean_bit_accuracy |
|---|---:|---:|---:|
| context_0 | 66 | 38 | 0.7803 |
| context_1 | 150 | 31 | 0.5200 |

## Laminated controller outcome

| Key | Value |
|---|---|
| final_decision | `continue` |
| final_cycle_budget | 20 |
| final_signal.next_slice_budget | 20 |
| final_signal.carryover_filter_mode | `keep` |
| final_signal.context_pressure | `low` |
| final_signal.decision_hint | `continue` |
| final_signal.stop_reason | `` |

## Delta vs baseline (reported)

| Metric | Delta |
|---|---:|
| exact_matches | -27.0000 |
| mean_bit_accuracy | 0.0059 |
| total_action_cost | -8.4773 |

## Slice summaries

| slice | budget | cycles | mode_used | min_ctx_acc | mean_bit_acc | conflict | ambiguity | uncertainty | cost | exact | partial | hint |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 48 | 48 | `self-selected` | 0.5357 | 0.6064 | 0.4149 | 1.0000 | 0.6570 | 49.4549 | 16.0000 | 25.0000 | `escalate` |
| 2 | 48 | 48 | `growth-visible` | 0.5469 | 0.5851 | 0.2223 | 1.0000 | 0.7524 | 55.1577 | 13.0000 | 29.0000 | `escalate` |
| 3 | 36 | 36 | `growth-visible` | 0.4500 | 0.4730 | 0.2554 | 0.7054 | 0.7699 | 3.8628 | 1.0000 | 33.0000 | `escalate` |
| 4 | 36 | 36 | `growth-visible` | 0.5000 | 0.5278 | 0.2139 | 0.8556 | 0.7567 | 37.7121 | 5.0000 | 28.0000 | `escalate` |
| 5 | 27 | 27 | `growth-visible` | 0.9167 | 0.9259 | 0.0000 | 0.8333 | 0.6605 | 0.6419 | 23.0000 | 4.0000 | `escalate` |
