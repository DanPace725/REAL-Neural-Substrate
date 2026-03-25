# 2026-03-25 0853 - laminated phase8

**timestamp:** `2026-03-25T15:53:35.648254Z`  
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
| max_slices | 3 |
| initial_cycle_budget | 8 |
| accuracy_threshold | 0.0 |
| regulator_type | heuristic |

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
| final_cycle_budget | 6 |
| final_signal.next_slice_budget | 6 |
| final_signal.carryover_filter_mode | `keep` |
| final_signal.context_pressure | `medium` |
| final_signal.decision_hint | `continue` |
| final_signal.stop_reason | `` |

## Delta vs baseline (reported)

| Metric | Delta |
|---|---:|
| exact_matches | 0.0000 |
| mean_bit_accuracy | 0.0000 |
| total_action_cost | 0.0000 |

## Slice summaries

| slice | budget | cycles | mode_used | min_ctx_acc | mean_bit_acc | conflict | ambiguity | uncertainty | cost | exact | partial | hint |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 8 | 8 | `self-selected` | 0.5000 | 0.5625 | 0.3750 | 1.0000 | 0.7432 | 1.6145 | 2.0000 | 5.0000 | `continue` |
| 2 | 10 | 10 | `self-selected` | 0.2500 | 0.4000 | 0.3300 | 0.9900 | 0.7511 | 2.4162 | 1.0000 | 6.0000 | `escalate` |
| 3 | 8 | 6 | `self-selected` | — | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 1.4856 | 0.0000 | 0.0000 | `settle` |
