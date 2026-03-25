# 2026-03-25 1041 - laminated phase8

**timestamp:** `2026-03-25T17:41:47.938269Z`  
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
| max_slices | 5 |
| initial_cycle_budget | 9 |
| accuracy_threshold | 0.8 |
| regulator_type | real |

## Baseline summary

| Metric | Value |
|---|---:|
| cycles | 46.0000 |
| injected_packets | 36.0000 |
| admitted_packets | 36.0000 |
| delivered_packets | 36.0000 |
| delivery_ratio | 1.0000 |
| dropped_packets | 0.0000 |
| drop_ratio | 0.0000 |
| mean_latency | 1.0000 |
| mean_hops | 5.0000 |
| node_atp_total | 5.3883 |
| node_reward_total | 6.2300 |
| mean_route_cost | 0.0409 |
| total_action_cost | 12.2080 |
| exact_matches | 9.0000 |
| partial_matches | 20.0000 |
| mean_bit_accuracy | 0.5278 |
| mean_feedback_award | 0.0950 |
| node_count | 11.0000 |
| edge_count | 16.0000 |
| bud_successes | 0.0000 |
| prune_events | 0.0000 |
| apoptosis_events | 0.0000 |

### Context breakdown (baseline)

| context | count | exact_matches | mean_bit_accuracy |
|---|---:|---:|---:|
| context_0 | 11 | 4 | 0.6818 |
| context_1 | 25 | 5 | 0.4600 |

## Laminated controller outcome

| Key | Value |
|---|---|
| final_decision | `settle` |
| final_cycle_budget | 5 |
| final_signal.next_slice_budget | 5 |
| final_signal.carryover_filter_mode | `keep` |
| final_signal.context_pressure | `high` |
| final_signal.decision_hint | `settle` |
| final_signal.stop_reason | `coherence_flat_and_conflict_low` |

## Delta vs baseline (reported)

| Metric | Delta |
|---|---:|
| exact_matches | 7.0000 |
| mean_bit_accuracy | 0.2315 |
| total_action_cost | -0.0663 |

## Slice summaries

| slice | budget | cycles | mode_used | min_ctx_acc | mean_bit_acc | conflict | ambiguity | uncertainty | cost | exact | partial | hint |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 9 | 9 | `self-selected` | 0.3333 | 0.3889 | 0.5000 | 1.0000 | 0.7510 | 3.5845 | 0.0000 | 7.0000 | `continue` |
| 2 | 9 | 9 | `growth-visible` | 0.5000 | 0.5625 | 0.3438 | 1.0000 | 0.7870 | 3.6888 | 2.0000 | 5.0000 | `continue` |
| 3 | 9 | 9 | `growth-visible` | 0.7500 | 0.8000 | 0.2000 | 1.0000 | 0.7507 | 3.7130 | 6.0000 | 4.0000 | `escalate` |
| 4 | 7 | 7 | `growth-visible` | 0.5000 | 0.8571 | 0.0000 | 0.7714 | 0.6750 | 2.5524 | 6.0000 | 0.0000 | `escalate` |
| 5 | 5 | 5 | `growth-visible` | 1.0000 | 1.0000 | 0.0000 | 0.4500 | 0.6528 | 2.1875 | 2.0000 | 0.0000 | `continue` |
