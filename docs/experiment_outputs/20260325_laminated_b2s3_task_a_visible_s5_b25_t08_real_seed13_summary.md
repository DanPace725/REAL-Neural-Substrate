# 2026-03-25 1041 - laminated phase8

**timestamp:** `2026-03-25T17:41:59.810134Z`  
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
| max_slices | 5 |
| initial_cycle_budget | 25 |
| accuracy_threshold | 0.8 |
| regulator_type | real |

## Baseline summary

| Metric | Value |
|---|---:|
| cycles | 128.0000 |
| injected_packets | 108.0000 |
| admitted_packets | 108.0000 |
| delivered_packets | 108.0000 |
| delivery_ratio | 1.0000 |
| dropped_packets | 0.0000 |
| drop_ratio | 0.0000 |
| mean_latency | 1.5556 |
| mean_hops | 6.7315 |
| node_atp_total | 4.9059 |
| node_reward_total | 5.9100 |
| mean_route_cost | 0.0380 |
| total_action_cost | 27.5994 |
| exact_matches | 43.0000 |
| partial_matches | 45.0000 |
| mean_bit_accuracy | 0.6065 |
| mean_feedback_award | 0.1092 |
| node_count | 31.0000 |
| edge_count | 55.0000 |
| bud_successes | 0.0000 |
| prune_events | 0.0000 |
| apoptosis_events | 0.0000 |

### Context breakdown (baseline)

| context | count | exact_matches | mean_bit_accuracy |
|---|---:|---:|---:|
| context_0 | 34 | 24 | 0.8382 |
| context_1 | 74 | 19 | 0.5000 |

## Laminated controller outcome

| Key | Value |
|---|---|
| final_decision | `continue` |
| final_cycle_budget | 14 |
| final_signal.next_slice_budget | 14 |
| final_signal.carryover_filter_mode | `keep` |
| final_signal.context_pressure | `low` |
| final_signal.decision_hint | `continue` |
| final_signal.stop_reason | `` |

## Delta vs baseline (reported)

| Metric | Delta |
|---|---:|
| exact_matches | -20.0000 |
| mean_bit_accuracy | 0.0426 |
| total_action_cost | 6.0965 |

## Slice summaries

| slice | budget | cycles | mode_used | min_ctx_acc | mean_bit_acc | conflict | ambiguity | uncertainty | cost | exact | partial | hint |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 25 | 25 | `self-selected` | 0.4474 | 0.4600 | 0.7800 | 1.0000 | 0.7412 | 26.0840 | 6.0000 | 11.0000 | `escalate` |
| 2 | 25 | 25 | `visible` | 0.5625 | 0.5800 | 0.2420 | 1.0000 | 0.7439 | 26.5075 | 8.0000 | 13.0000 | `escalate` |
| 3 | 19 | 19 | `growth-visible` | 0.6154 | 0.7105 | 0.4263 | 0.9000 | 0.7375 | 21.3793 | 9.0000 | 9.0000 | `escalate` |
| 4 | 19 | 19 | `growth-visible` | 0.3750 | 0.5789 | 0.5211 | 1.0000 | 0.7378 | 18.4572 | 6.0000 | 10.0000 | `escalate` |
| 5 | 19 | 19 | `growth-visible` | 0.5000 | 0.6579 | 0.4211 | 1.0000 | 0.7159 | 15.2387 | 8.0000 | 9.0000 | `escalate` |
