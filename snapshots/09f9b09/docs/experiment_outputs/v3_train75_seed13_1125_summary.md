# REAL Occupancy v3 — session carryover experiment

**run_id:** `v3_seed13_20260320T184058`  
**run_at:** `2026-03-20T18:40:58+00:00`  
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
| max_eval_sessions | 25 |
| max_train_sessions | 50 |
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
- train_session_count: **50**
- eval_session_count: **25**
- co2_training_median: **0.974881**
- light_training_median: **1.045862**
- training_context_codes: [0, 1, 2, 3]

### Train inventory

```
{
  "session_count": 50,
  "by_label": {
    "0": 25,
    "1": 25
  },
  "by_context_code": {
    "0": 19,
    "1": 4,
    "3": 20,
    "2": 7
  },
  "episode_lengths": {
    "min": 1,
    "mean": 16.24,
    "max": 76
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
      1,
      2,
      3
    ]
  }
}
```

### Eval inventory

```
{
  "session_count": 25,
  "by_label": {
    "0": 13,
    "1": 12
  },
  "by_context_code": {
    "3": 10,
    "2": 1,
    "0": 8,
    "1": 6
  },
  "episode_lengths": {
    "min": 1,
    "mean": 14.64,
    "max": 84
  },
  "context_codes_by_label": {
    "0": [
      0,
      1,
      3
    ],
    "1": [
      0,
      1,
      2,
      3
    ]
  }
}
```

## Phase 2 — Training summary

| Metric | Value |
|---|---|
| accuracy | 0.9200 |
| precision | 0.8670 |
| recall | 0.8559 |
| f1 | 0.8614 |

| Stat | Value |
|---|---|
| episode_count | 812 |
| mean_delivered_packets | 23.9138 |
| mean_dropped_packets | 1.0862 |
| mean_feedback_events | 21.5172 |

## Phase 3 — Warm / cold eval & carryover

### Warm eval

| Metric | Value |
|---|---|
| accuracy | 0.9645 |
| precision | 0.9605 |
| recall | 0.8795 |
| f1 | 0.9182 |

### Cold eval

| Metric | Value |
|---|---|
| accuracy | 0.9672 |
| precision | 1.0000 |
| recall | 0.8554 |
| f1 | 0.9221 |

### Carryover efficiency metrics

| Metric | Value |
|---|---|
| mean_efficiency_ratio | 0.9894 |
| warm_sessions_to_80pct | 0 |
| cold_sessions_to_80pct | 0 |

**Delivery checkpoints:**

| checkpoint | warm | cold | ratio |
|---|---:|---:|---:|
| session_1 | 1.0 | 1.0 | 1.0000 |
| session_5 | 1.0 | 1.0 | 1.0000 |
| session_10 | 0.9644 | 0.9822 | 0.9819 |
| session_20 | 0.97 | 0.99 | 0.9798 |

## Phase 4 — Context transfer probe

- **context_mode**: online_running_context
- **training_context_codes**: [0, 1, 2, 3]
- **eval_context_codes**: [0, 1, 2, 3]
- **comparison_applicable**: False
- **status**: not_applicable_all_eval_contexts_seen
- **warm_seen_mean_delivery**: 0.9763
- **warm_unseen_mean_delivery**: None
- **cold_seen_mean_delivery**: 0.9868
- **cold_unseen_mean_delivery**: None
- **warm_seen_session_count**: 25
- **warm_unseen_session_count**: 0

## System summaries

### Train

```
{
  "capability_policy": "fixed-visible",
  "cycles": 28947,
  "injected_packets": 20300,
  "admitted_packets": 20300,
  "delivered_packets": 19418,
  "delivery_ratio": 0.9566,
  "dropped_packets": 882,
  "drop_ratio": 0.0434,
  "source_buffer": 0,
  "mean_latency": 3.4497,
  "mean_hops": 4.0,
  "node_atp_total": 9.827,
  "mean_route_cost": 0.03175,
  "mean_feedback_award": 0.162,
  "mean_source_admission": 0.7013,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 17472,
  "mean_bit_accuracy": 0.8998
}
```

### Warm eval

```
{
  "capability_policy": "fixed-visible",
  "cycles": 736315,
  "injected_packets": 9150,
  "admitted_packets": 9150,
  "delivered_packets": 8831,
  "delivery_ratio": 0.9651,
  "dropped_packets": 319,
  "drop_ratio": 0.0349,
  "source_buffer": 0,
  "mean_latency": 3.3134,
  "mean_hops": 4.0,
  "node_atp_total": 11.5607,
  "mean_route_cost": 0.0334,
  "mean_feedback_award": 0.1711,
  "mean_source_admission": 0.0124,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 8394,
  "mean_bit_accuracy": 0.9505
}
```

### Cold eval

```
{
  "capability_policy": "fixed-visible",
  "cycles": 12462,
  "injected_packets": 9150,
  "admitted_packets": 9150,
  "delivered_packets": 8885,
  "delivery_ratio": 0.971,
  "dropped_packets": 265,
  "drop_ratio": 0.029,
  "source_buffer": 0,
  "mean_latency": 3.3073,
  "mean_hops": 4.0,
  "node_atp_total": 11.8233,
  "mean_route_cost": 0.0332,
  "mean_feedback_award": 0.1721,
  "mean_source_admission": 0.7342,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 8493,
  "mean_bit_accuracy": 0.9559
}
```

## Eval protocols

### fresh_session_eval

- **workers_used**: 10
- **parallelism_status**: process_pool:10
- **warm_reset_count**: 25
- **cold_reset_count**: 25

| Metric | Value |
|---|---|
| mean_efficiency_ratio | 0.9894 |
| session_1_delivery_delta | 0.0 |
| mean_first_episode_delivery_delta | 0.0 |
| mean_first_three_episode_delivery_delta | -0.0152 |
| warm_sessions_to_80pct | 0 |
| cold_sessions_to_80pct | 0 |

**Context transfer probe:**

- **context_mode**: online_running_context
- **training_context_codes**: [0, 1, 2, 3]
- **eval_context_codes**: [0, 1, 2, 3]
- **comparison_applicable**: False
- **status**: not_applicable_all_eval_contexts_seen
- **warm_seen_mean_delivery**: 0.9763
- **warm_unseen_mean_delivery**: None
- **cold_seen_mean_delivery**: 0.9868
- **cold_unseen_mean_delivery**: None
- **warm_seen_session_count**: 25
- **warm_unseen_session_count**: 0

**Warm system summary:**

```
{
  "capability_policy": "fixed-visible",
  "cycles": 736315,
  "injected_packets": 9150,
  "admitted_packets": 9150,
  "delivered_packets": 8831,
  "delivery_ratio": 0.9651,
  "dropped_packets": 319,
  "drop_ratio": 0.0349,
  "source_buffer": 0,
  "mean_latency": 3.3134,
  "mean_hops": 4.0,
  "node_atp_total": 11.5607,
  "mean_route_cost": 0.0334,
  "mean_feedback_award": 0.1711,
  "mean_source_admission": 0.0124,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 8394,
  "mean_bit_accuracy": 0.9505
}
```

**Cold system summary:**

```
{
  "capability_policy": "fixed-visible",
  "cycles": 12462,
  "injected_packets": 9150,
  "admitted_packets": 9150,
  "delivered_packets": 8885,
  "delivery_ratio": 0.971,
  "dropped_packets": 265,
  "drop_ratio": 0.029,
  "source_buffer": 0,
  "mean_latency": 3.3073,
  "mean_hops": 4.0,
  "node_atp_total": 11.8233,
  "mean_route_cost": 0.0332,
  "mean_feedback_award": 0.1721,
  "mean_source_admission": 0.7342,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 8493,
  "mean_bit_accuracy": 0.9559
}
```
