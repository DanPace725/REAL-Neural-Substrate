# REAL Occupancy v3 - multi-seed sweep

**run_id:** `v3_sweep3seeds_20260324T165700`  
**run_at:** `2026-03-24T16:57:00+00:00`  
**git_sha:** `50e5ae0`  
**selector_seeds:** [13, 23, 37]  

## Base config

| Key | Value |
|---|---|
| context_mode | online_running_context |
| csv_path | occupancy_baseline/data/occupancy_synth_v1.csv |
| eval_feedback_fraction | 1.0 |
| eval_mode | persistent_eval |
| feedback_amount | 0.18 |
| feedback_drain_cycles | 4 |
| forward_drain_cycles | 16 |
| ingress_mode | admission_source |
| max_eval_sessions | None |
| max_train_sessions | None |
| normalize | True |
| packet_ttl | 8 |
| selector_seed | None |
| summary_only | True |
| topology_mode | multihop_routing |
| train_session_fraction | 0.7 |
| window_size | 5 |

## Worker policy

| Key | Value |
|---|---|
| requested_workers | 15 |
| auto_cpu_target_fraction | 0.75 |
| worker_budget | 15 |
| seed_workers | 3 |
| eval_workers_per_seed | 5 |
| effective_total_workers | 15 |
| parallelism_status | process_pool:3 |

## Aggregate

| Metric | Value |
|---|---|
| selector_seed_count | 3 |
| primary_eval_mode | persistent_eval |
| mean_train_accuracy | 0.9125 |
| mean_warm_accuracy | 0.913 |
| mean_cold_accuracy | 0.9219 |
| mean_warm_delivery_ratio | 0.9483 |
| mean_cold_delivery_ratio | 0.9599 |
| mean_efficiency_ratio | 0.9683 |
| mean_session_1_delivery_delta | 0.0 |
| mean_first_episode_delivery_delta | -0.0153 |
| mean_first_three_episode_delivery_delta | -0.0276 |
| best_seed_by_efficiency_ratio | {'selector_seed': 37, 'metric': 'mean_efficiency_ratio', 'value': 0.9828} |
| best_seed_by_session_1_delivery_delta | {'selector_seed': 13, 'metric': 'session_1_delivery_delta', 'value': 0.0} |

## Per-seed summary

| selector_seed | train_accuracy | warm_accuracy | cold_accuracy | warm_delivery | cold_delivery | efficiency_ratio | session_1_delta |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 13 | 0.9146868250539957 | 0.9033816425120773 | 0.9202898550724637 | 0.9367 | 0.9643 | 0.9519 | 0.0 |
| protocol_parallelism | {'persistent_eval': 'process_pool:2'} |  |  |  |  |  |  |
| eval_workers_by_protocol | {'persistent_eval': 2} |  |  |  |  |  |  |
| 23 | 0.9103671706263499 | 0.9202898550724637 | 0.9202898550724637 | 0.9557 | 0.9559 | 0.9701 | 0.0 |
| protocol_parallelism | {'persistent_eval': 'process_pool:2'} |  |  |  |  |  |  |
| eval_workers_by_protocol | {'persistent_eval': 2} |  |  |  |  |  |  |
| 37 | 0.9125269978401728 | 0.9154589371980676 | 0.9251207729468599 | 0.9525 | 0.9596 | 0.9828 | 0.0 |
| protocol_parallelism | {'persistent_eval': 'process_pool:2'} |  |  |  |  |  |  |
| eval_workers_by_protocol | {'persistent_eval': 2} |  |  |  |  |  |  |