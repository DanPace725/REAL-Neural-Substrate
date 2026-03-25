# 2026-03-25 1104 - laminated phase8

**timestamp:** `2026-03-25T18:04:12.835877Z`  
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
| max_slices | 5 |
| initial_cycle_budget | 180 |
| accuracy_threshold | 0.8 |
| regulator_type | real |

## Baseline summary

| Metric | Value |
|---|---:|
| cycles | 904.0000 |
| injected_packets | 864.0000 |
| admitted_packets | 864.0000 |
| delivered_packets | 864.0000 |
| delivery_ratio | 1.0000 |
| dropped_packets | 0.0000 |
| drop_ratio | 0.0000 |
| mean_latency | 2.2002 |
| mean_hops | 10.0000 |
| node_atp_total | 10.5748 |
| node_reward_total | 9.2400 |
| mean_route_cost | 0.0397 |
| total_action_cost | 78.4637 |
| exact_matches | 547.0000 |
| partial_matches | 268.0000 |
| mean_bit_accuracy | 0.7882 |
| mean_feedback_award | 0.1419 |
| node_count | 101.0000 |
| edge_count | 283.0000 |
| bud_successes | 0.0000 |
| prune_events | 0.0000 |
| apoptosis_events | 0.0000 |

### Context breakdown (baseline)

| context | count | exact_matches | mean_bit_accuracy |
|---|---:|---:|---:|
| context_0 | 259 | 35 | 0.4884 |
| context_1 | 605 | 512 | 0.9165 |

## Laminated controller outcome

| Key | Value |
|---|---|
| final_decision | `continue` |
| final_cycle_budget | 180 |
| final_signal.next_slice_budget | 180 |
| final_signal.carryover_filter_mode | `drop` |
| final_signal.context_pressure | `high` |
| final_signal.decision_hint | `continue` |
| final_signal.stop_reason | `` |

## Delta vs baseline (reported)

| Metric | Delta |
|---|---:|
| exact_matches | -434.0000 |
| mean_bit_accuracy | -0.1709 |
| total_action_cost | -8.1818 |

## Slice summaries

| slice | budget | cycles | mode_used | min_ctx_acc | mean_bit_acc | conflict | ambiguity | uncertainty | cost | exact | partial | hint |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 180 | 180 | `self-selected` | 0.5370 | 0.7250 | 0.4500 | 1.0000 | 0.5899 | 116.6771 | 91.0000 | 79.0000 | `escalate` |
| 2 | 180 | 180 | `visible` | 0.4455 | 0.6056 | 0.5072 | 1.0000 | 0.6078 | 95.4380 | 58.0000 | 102.0000 | `escalate` |
| 3 | 180 | 180 | `visible` | 0.5000 | 0.8139 | 0.4944 | 1.0000 | 0.5460 | 52.5575 | 124.0000 | 45.0000 | `escalate` |
| 4 | 180 | 180 | `growth-visible` | 0.4434 | 0.7222 | 0.3942 | 1.0000 | 0.6871 | 90.6569 | 97.0000 | 66.0000 | `escalate` |
| 5 | 180 | 180 | `growth-visible` | 0.4505 | 0.4861 | 0.2674 | 1.0000 | 0.7407 | 70.2819 | 16.0000 | 108.0000 | `escalate` |
