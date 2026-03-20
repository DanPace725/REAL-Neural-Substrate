# REAL Occupancy v3 - multi-seed sweep

**run_id:** `v3_sweep3seeds_20260320T194240`  
**run_at:** `2026-03-20T19:42:40+00:00`  
**git_sha:** `c5a20ac`  
**selector_seeds:** [13, 23, 37]  

## Base config

| Key | Value |
|---|---|
| context_mode | online_running_context |
| csv_path | occupancy_baseline/data/occupancy_synth_v1.csv |
| eval_feedback_fraction | 1.0 |
| eval_mode | fresh_session_eval |
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
| requested_workers | None |
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
| primary_eval_mode | fresh_session_eval |
| mean_train_accuracy | 0.9125 |
| mean_warm_accuracy | 0.9734 |
| mean_cold_accuracy | 0.9678 |
| mean_warm_delivery_ratio | 0.9687 |
| mean_cold_delivery_ratio | 0.9773 |
| mean_efficiency_ratio | 0.9915 |
| mean_session_1_delivery_delta | 0.0 |
| mean_first_episode_delivery_delta | 0.0 |
| mean_first_three_episode_delivery_delta | -0.0112 |
| best_seed_by_efficiency_ratio | {'selector_seed': 13, 'metric': 'mean_efficiency_ratio', 'value': 0.9977} |
| best_seed_by_session_1_delivery_delta | {'selector_seed': 13, 'metric': 'session_1_delivery_delta', 'value': 0.0} |

## Per-seed summary

| selector_seed | train_accuracy | warm_accuracy | cold_accuracy | warm_delivery | cold_delivery | efficiency_ratio | session_1_delta |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 13 | 0.9146868250539957 | 0.9806763285024155 | 0.9685990338164251 | 0.9739 | 0.9711 | 0.9977 | 0.0 |
| protocol_parallelism | {'fresh_session_eval': 'process_pool:5'} |  |  |  |  |  |  |
| eval_workers_by_protocol | {'fresh_session_eval': 5} |  |  |  |  |  |  |
| 23 | 0.9103671706263499 | 0.9710144927536232 | 0.966183574879227 | 0.9614 | 0.9816 | 0.9837 | 0.0 |
| protocol_parallelism | {'fresh_session_eval': 'process_pool:5'} |  |  |  |  |  |  |
| eval_workers_by_protocol | {'fresh_session_eval': 5} |  |  |  |  |  |  |
| 37 | 0.9125269978401728 | 0.9685990338164251 | 0.9685990338164251 | 0.9707 | 0.9793 | 0.9931 | 0.0 |
| protocol_parallelism | {'fresh_session_eval': 'process_pool:5'} |  |  |  |  |  |  |
| eval_workers_by_protocol | {'fresh_session_eval': 5} |  |  |  |  |  |  |