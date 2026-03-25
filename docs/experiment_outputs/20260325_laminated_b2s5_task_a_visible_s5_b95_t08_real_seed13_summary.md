# 2026-03-25 1049 - laminated phase8

**timestamp:** `2026-03-25T17:49:40.361690Z`  
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
| max_slices | 5 |
| initial_cycle_budget | 95 |
| accuracy_threshold | 0.8 |
| regulator_type | real |

## Baseline summary

| Metric | Value |
|---|---:|
| cycles | 476.0000 |
| injected_packets | 432.0000 |
| admitted_packets | 432.0000 |
| delivered_packets | 432.0000 |
| delivery_ratio | 1.0000 |
| dropped_packets | 0.0000 |
| drop_ratio | 0.0000 |
| mean_latency | 3.2569 |
| mean_hops | 11.0000 |
| node_atp_total | 9.6667 |
| node_reward_total | 10.6600 |
| mean_route_cost | 0.0405 |
| total_action_cost | 68.7279 |
| exact_matches | 130.0000 |
| partial_matches | 242.0000 |
| mean_bit_accuracy | 0.5810 |
| mean_feedback_award | 0.1046 |
| node_count | 76.0000 |
| edge_count | 212.0000 |
| bud_successes | 0.0000 |
| prune_events | 0.0000 |
| apoptosis_events | 0.0000 |

### Context breakdown (baseline)

| context | count | exact_matches | mean_bit_accuracy |
|---|---:|---:|---:|
| context_0 | 130 | 90 | 0.8115 |
| context_1 | 302 | 40 | 0.4818 |

## Laminated controller outcome

| Key | Value |
|---|---|
| final_decision | `continue` |
| final_cycle_budget | 95 |
| final_signal.next_slice_budget | 95 |
| final_signal.carryover_filter_mode | `soften` |
| final_signal.context_pressure | `high` |
| final_signal.decision_hint | `continue` |
| final_signal.stop_reason | `` |

## Delta vs baseline (reported)

| Metric | Delta |
|---|---:|
| exact_matches | 131.0000 |
| mean_bit_accuracy | 0.2825 |
| total_action_cost | -21.3440 |

## Slice summaries

| slice | budget | cycles | mode_used | min_ctx_acc | mean_bit_acc | conflict | ambiguity | uncertainty | cost | exact | partial | hint |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 95 | 95 | `self-selected` | 0.5227 | 0.6158 | 0.4316 | 1.0000 | 0.6570 | 76.8106 | 34.0000 | 49.0000 | `escalate` |
| 2 | 95 | 95 | `growth-visible` | 0.6071 | 0.7737 | 0.3358 | 1.0000 | 0.7001 | 78.9791 | 58.0000 | 31.0000 | `escalate` |
| 3 | 95 | 95 | `growth-visible` | 0.7679 | 0.8684 | 0.0984 | 1.0000 | 0.6572 | 44.2443 | 74.0000 | 17.0000 | `escalate` |
| 4 | 95 | 95 | `growth-visible` | 0.9127 | 0.9409 | 0.1237 | 1.0000 | 0.6422 | 0.2866 | 84.0000 | 7.0000 | `escalate` |
| 5 | 95 | 95 | `growth-visible` | 0.7667 | 0.8796 | 0.0648 | 1.0000 | 0.6423 | 0.0000 | 45.0000 | 5.0000 | `escalate` |
