# REAL Occupancy v3 — session carryover experiment

**run_id:** `v3_seed13_20260320T182333`  
**run_at:** `2026-03-20T18:23:33+00:00`  
**git_sha:** `c5a20ac`  
**primary_eval_mode:** `fresh_session_eval`  

## Config

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
| max_eval_sessions | 5 |
| max_train_sessions | 20 |
| normalize | True |
| packet_ttl | 8 |
| selector_seed | 13 |
| summary_only | False |
| topology_mode | multihop_routing |
| train_session_fraction | 0.7 |
| window_size | 5 |

## Worker policy

| Key | Value |
|---|---|
| requested_workers | 10 |
| auto_cpu_target_fraction | 0.75 |
| eval_workers_by_protocol | {'fresh_session_eval': 10} |

## Dataset

- dataset_rows: **1344**
- total_episodes: **1340**
- total_sessions: **89**
- train_session_count: **20**
- eval_session_count: **5**
- co2_training_median: **0.974881**
- light_training_median: **1.045862**
- training_context_codes: [0, 1, 2, 3]

### Train inventory

```
{
  "session_count": 20,
  "by_label": {
    "0": 10,
    "1": 10
  },
  "by_context_code": {
    "0": 6,
    "1": 2,
    "3": 11,
    "2": 1
  },
  "episode_lengths": {
    "min": 1,
    "mean": 12.8,
    "max": 58
  },
  "context_codes_by_label": {
    "0": [
      0,
      1,
      2,
      3
    ],
    "1": [
      0,
      3
    ]
  }
}
```

### Eval inventory

```
{
  "session_count": 5,
  "by_label": {
    "0": 3,
    "1": 2
  },
  "by_context_code": {
    "3": 1,
    "2": 1,
    "0": 3
  },
  "episode_lengths": {
    "min": 1,
    "mean": 13.2,
    "max": 59
  },
  "context_codes_by_label": {
    "0": [
      0,
      3
    ],
    "1": [
      0,
      2
    ]
  }
}
```

## Phase 2 — Training summary

| Metric | Value |
|---|---|
| accuracy | 0.8945 |
| precision | 0.8454 |
| recall | 0.8723 |
| f1 | 0.8586 |

| Stat | Value |
|---|---|
| episode_count | 256 |
| mean_delivered_packets | 23.8359 |
| mean_dropped_packets | 1.1641 |
| mean_feedback_events | 20.9727 |

## Phase 3 — Warm / cold eval & carryover

### Warm eval

| Metric | Value |
|---|---|
| accuracy | 0.9545 |
| precision | 0.7500 |
| recall | 0.6000 |
| f1 | 0.6667 |

### Cold eval

| Metric | Value |
|---|---|
| accuracy | 0.9697 |
| precision | 1.0000 |
| recall | 0.6000 |
| f1 | 0.7500 |

### Carryover efficiency metrics

| Metric | Value |
|---|---|
| mean_efficiency_ratio | 0.9967 |
| warm_sessions_to_80pct | 0 |
| cold_sessions_to_80pct | 0 |

**Delivery checkpoints:**

| checkpoint | warm | cold | ratio |
|---|---:|---:|---:|
| session_1 | 1.0 | 1.0 | 1.0000 |
| session_5 | 1.0 | 1.0 | 1.0000 |
| session_10 | None | None | — |
| session_20 | None | None | — |

## Phase 4 — Context transfer probe

- **context_mode**: online_running_context
- **training_context_codes**: [0, 1, 2, 3]
- **eval_context_codes**: [0, 2, 3]
- **comparison_applicable**: False
- **status**: not_applicable_all_eval_contexts_seen
- **warm_seen_mean_delivery**: 0.9873
- **warm_unseen_mean_delivery**: None
- **cold_seen_mean_delivery**: 0.9906
- **cold_unseen_mean_delivery**: None
- **warm_seen_session_count**: 5
- **warm_unseen_session_count**: 0

## System summaries

### Train

```
{
  "capability_policy": "fixed-visible",
  "cycles": 9197,
  "injected_packets": 6400,
  "admitted_packets": 6400,
  "delivered_packets": 6102,
  "delivery_ratio": 0.9534,
  "dropped_packets": 298,
  "drop_ratio": 0.0466,
  "source_buffer": 0,
  "mean_latency": 3.4554,
  "mean_hops": 4.0,
  "node_atp_total": 11.5225,
  "mean_route_cost": 0.03305,
  "mean_feedback_award": 0.1584,
  "mean_source_admission": 0.6959,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 5369,
  "mean_bit_accuracy": 0.8799
}
```

### Warm eval

```
{
  "capability_policy": "fixed-visible",
  "cycles": 48294,
  "injected_packets": 1650,
  "admitted_packets": 1650,
  "delivered_packets": 1612,
  "delivery_ratio": 0.977,
  "dropped_packets": 38,
  "drop_ratio": 0.023,
  "source_buffer": 0,
  "mean_latency": 3.4262,
  "mean_hops": 4.0,
  "node_atp_total": 10.8402,
  "mean_route_cost": 0.0344,
  "mean_feedback_award": 0.1711,
  "mean_source_admission": 0.0342,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 1532,
  "mean_bit_accuracy": 0.9503
}
```

### Cold eval

```
{
  "capability_policy": "fixed-visible",
  "cycles": 2244,
  "injected_packets": 1650,
  "admitted_packets": 1650,
  "delivered_packets": 1599,
  "delivery_ratio": 0.9691,
  "dropped_packets": 51,
  "drop_ratio": 0.0309,
  "source_buffer": 0,
  "mean_latency": 3.2939,
  "mean_hops": 4.0,
  "node_atp_total": 11.4464,
  "mean_route_cost": 0.0333,
  "mean_feedback_award": 0.1723,
  "mean_source_admission": 0.7353,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 1531,
  "mean_bit_accuracy": 0.9575
}
```

## Eval protocols

### fresh_session_eval

- **workers_used**: 10
- **parallelism_status**: process_pool:10
- **warm_reset_count**: 5
- **cold_reset_count**: 5

| Metric | Value |
|---|---|
| mean_efficiency_ratio | 0.9967 |
| session_1_delivery_delta | 0.0 |
| mean_first_episode_delivery_delta | 0.0 |
| mean_first_three_episode_delivery_delta | -0.008 |
| warm_sessions_to_80pct | 0 |
| cold_sessions_to_80pct | 0 |

**Context transfer probe:**

- **context_mode**: online_running_context
- **training_context_codes**: [0, 1, 2, 3]
- **eval_context_codes**: [0, 2, 3]
- **comparison_applicable**: False
- **status**: not_applicable_all_eval_contexts_seen
- **warm_seen_mean_delivery**: 0.9873
- **warm_unseen_mean_delivery**: None
- **cold_seen_mean_delivery**: 0.9906
- **cold_unseen_mean_delivery**: None
- **warm_seen_session_count**: 5
- **warm_unseen_session_count**: 0

**Warm system summary:**

```
{
  "capability_policy": "fixed-visible",
  "cycles": 48294,
  "injected_packets": 1650,
  "admitted_packets": 1650,
  "delivered_packets": 1612,
  "delivery_ratio": 0.977,
  "dropped_packets": 38,
  "drop_ratio": 0.023,
  "source_buffer": 0,
  "mean_latency": 3.4262,
  "mean_hops": 4.0,
  "node_atp_total": 10.8402,
  "mean_route_cost": 0.0344,
  "mean_feedback_award": 0.1711,
  "mean_source_admission": 0.0342,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 1532,
  "mean_bit_accuracy": 0.9503
}
```

**Cold system summary:**

```
{
  "capability_policy": "fixed-visible",
  "cycles": 2244,
  "injected_packets": 1650,
  "admitted_packets": 1650,
  "delivered_packets": 1599,
  "delivery_ratio": 0.9691,
  "dropped_packets": 51,
  "drop_ratio": 0.0309,
  "source_buffer": 0,
  "mean_latency": 3.2939,
  "mean_hops": 4.0,
  "node_atp_total": 11.4464,
  "mean_route_cost": 0.0333,
  "mean_feedback_award": 0.1723,
  "mean_source_admission": 0.7353,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 1531,
  "mean_bit_accuracy": 0.9575
}
```
