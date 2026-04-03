# REAL Occupancy v3 — session carryover experiment

**run_id:** `v3_seed13_20260330T002120`  
**run_at:** `2026-03-30T00:21:20+00:00`  
**git_sha:** `fe61410`  
**primary_eval_mode:** `fresh_session_eval`  

## Config

| Key | Value |
|---|---|
| context_mode | online_running_context |
| csv_path | occupancy_baseline/data/occupancy_synth_v1.csv |
| eval_feedback_fraction | 1.0 |
| eval_mode | both |
| feedback_amount | 0.18 |
| feedback_drain_cycles | 4 |
| forward_drain_cycles | 16 |
| ingress_mode | admission_source |
| max_eval_sessions | None |
| max_train_sessions | None |
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
| requested_workers | 8 |
| auto_cpu_target_fraction | 0.75 |
| eval_workers_by_protocol | {'fresh_session_eval': 8, 'persistent_eval': 2} |

## Dataset

- dataset_rows: **1344**
- total_episodes: **1340**
- total_sessions: **89**
- train_session_count: **62**
- eval_session_count: **27**
- co2_training_median: **0.974881**
- light_training_median: **1.045862**
- training_context_codes: [0, 1, 2, 3]

### Train inventory

```
{
  "session_count": 62,
  "by_label": {
    "0": 31,
    "1": 31
  },
  "by_context_code": {
    "0": 24,
    "1": 7,
    "3": 24,
    "2": 7
  },
  "episode_lengths": {
    "min": 1,
    "mean": 14.94,
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
  "session_count": 27,
  "by_label": {
    "0": 14,
    "1": 13
  },
  "by_context_code": {
    "3": 10,
    "2": 1,
    "0": 9,
    "1": 7
  },
  "episode_lengths": {
    "min": 1,
    "mean": 15.33,
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
| accuracy | 0.9233 |
| precision | 0.8777 |
| recall | 0.8683 |
| f1 | 0.8730 |

| Stat | Value |
|---|---|
| episode_count | 926 |
| mean_delivered_packets | 24.3272 |
| mean_dropped_packets | 0.6728 |
| mean_feedback_events | 21.5551 |

## Phase 3 — Warm / cold eval & carryover

### Warm eval

| Metric | Value |
|---|---|
| accuracy | 0.9662 |
| precision | 0.8842 |
| recall | 0.9655 |
| f1 | 0.9231 |

### Cold eval

| Metric | Value |
|---|---|
| accuracy | 0.9662 |
| precision | 0.8614 |
| recall | 1.0000 |
| f1 | 0.9255 |

### Carryover efficiency metrics

| Metric | Value |
|---|---|
| mean_efficiency_ratio | 0.9921 |
| warm_sessions_to_80pct | 0 |
| cold_sessions_to_80pct | 0 |

**Delivery checkpoints:**

| checkpoint | warm | cold | ratio |
|---|---:|---:|---:|
| session_1 | 1.0 | 1.0 | 1.0000 |
| session_5 | 1.0 | 1.0 | 1.0000 |
| session_10 | 0.9689 | 0.9822 | 0.9865 |
| session_20 | 0.96 | 0.98 | 0.9796 |

## Phase 4 — Context transfer probe

- **context_mode**: online_running_context
- **training_context_codes**: [0, 1, 2, 3]
- **eval_context_codes**: [0, 1, 2, 3]
- **comparison_applicable**: False
- **status**: not_applicable_all_eval_contexts_seen
- **warm_seen_mean_delivery**: 0.9794
- **warm_unseen_mean_delivery**: None
- **cold_seen_mean_delivery**: 0.9872
- **cold_unseen_mean_delivery**: None
- **warm_seen_session_count**: 27
- **warm_unseen_session_count**: 0

## System summaries

### Train

```
{
  "capability_policy": "fixed-visible",
  "cycles": 32321,
  "injected_packets": 23150,
  "admitted_packets": 23150,
  "delivered_packets": 22527,
  "delivery_ratio": 0.9731,
  "dropped_packets": 623,
  "drop_ratio": 0.0269,
  "source_buffer": 0,
  "mean_latency": 3.3924,
  "mean_hops": 4.0,
  "node_atp_total": 11.6549,
  "mean_route_cost": 0.03235,
  "mean_feedback_award": 0.1595,
  "mean_source_admission": 0.7163,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 19960,
  "mean_bit_accuracy": 0.886
}
```

### Warm eval

```
{
  "capability_policy": "fixed-visible",
  "cycles": 886565,
  "injected_packets": 10350,
  "admitted_packets": 10350,
  "delivered_packets": 10073,
  "delivery_ratio": 0.9732,
  "dropped_packets": 277,
  "drop_ratio": 0.0268,
  "source_buffer": 0,
  "mean_latency": 3.2217,
  "mean_hops": 4.0,
  "node_atp_total": 11.2796,
  "mean_route_cost": 0.0342,
  "mean_feedback_award": 0.1667,
  "mean_source_admission": 0.0117,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 9328,
  "mean_bit_accuracy": 0.926
}
```

### Cold eval

```
{
  "capability_policy": "fixed-visible",
  "cycles": 13655,
  "injected_packets": 10350,
  "admitted_packets": 10350,
  "delivered_packets": 10178,
  "delivery_ratio": 0.9834,
  "dropped_packets": 172,
  "drop_ratio": 0.0166,
  "source_buffer": 0,
  "mean_latency": 3.1987,
  "mean_hops": 4.0,
  "node_atp_total": 11.4781,
  "mean_route_cost": 0.0335,
  "mean_feedback_award": 0.1663,
  "mean_source_admission": 0.758,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 9400,
  "mean_bit_accuracy": 0.9236
}
```

## Eval protocols

### fresh_session_eval

- **workers_used**: 8
- **parallelism_status**: process_pool:8
- **warm_reset_count**: 27
- **cold_reset_count**: 27

| Metric | Value |
|---|---|
| mean_efficiency_ratio | 0.9921 |
| session_1_delivery_delta | 0.0 |
| mean_first_episode_delivery_delta | 0.0 |
| mean_first_three_episode_delivery_delta | -0.0141 |
| warm_sessions_to_80pct | 0 |
| cold_sessions_to_80pct | 0 |

**Context transfer probe:**

- **context_mode**: online_running_context
- **training_context_codes**: [0, 1, 2, 3]
- **eval_context_codes**: [0, 1, 2, 3]
- **comparison_applicable**: False
- **status**: not_applicable_all_eval_contexts_seen
- **warm_seen_mean_delivery**: 0.9794
- **warm_unseen_mean_delivery**: None
- **cold_seen_mean_delivery**: 0.9872
- **cold_unseen_mean_delivery**: None
- **warm_seen_session_count**: 27
- **warm_unseen_session_count**: 0

**Warm system summary:**

```
{
  "capability_policy": "fixed-visible",
  "cycles": 886565,
  "injected_packets": 10350,
  "admitted_packets": 10350,
  "delivered_packets": 10073,
  "delivery_ratio": 0.9732,
  "dropped_packets": 277,
  "drop_ratio": 0.0268,
  "source_buffer": 0,
  "mean_latency": 3.2217,
  "mean_hops": 4.0,
  "node_atp_total": 11.2796,
  "mean_route_cost": 0.0342,
  "mean_feedback_award": 0.1667,
  "mean_source_admission": 0.0117,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 9328,
  "mean_bit_accuracy": 0.926
}
```

**Cold system summary:**

```
{
  "capability_policy": "fixed-visible",
  "cycles": 13655,
  "injected_packets": 10350,
  "admitted_packets": 10350,
  "delivered_packets": 10178,
  "delivery_ratio": 0.9834,
  "dropped_packets": 172,
  "drop_ratio": 0.0166,
  "source_buffer": 0,
  "mean_latency": 3.1987,
  "mean_hops": 4.0,
  "node_atp_total": 11.4781,
  "mean_route_cost": 0.0335,
  "mean_feedback_award": 0.1663,
  "mean_source_admission": 0.758,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 9400,
  "mean_bit_accuracy": 0.9236
}
```

### persistent_eval

- **workers_used**: 2
- **parallelism_status**: process_pool:2
- **warm_reset_count**: 1
- **cold_reset_count**: 1

| Metric | Value |
|---|---|
| mean_efficiency_ratio | 0.9991 |
| session_1_delivery_delta | 0.0 |
| mean_first_episode_delivery_delta | 0.0148 |
| mean_first_three_episode_delivery_delta | 0.0025 |
| warm_sessions_to_80pct | 0 |
| cold_sessions_to_80pct | 0 |

**Context transfer probe:**

- **context_mode**: online_running_context
- **training_context_codes**: [0, 1, 2, 3]
- **eval_context_codes**: [0, 1, 2, 3]
- **comparison_applicable**: False
- **status**: not_applicable_all_eval_contexts_seen
- **warm_seen_mean_delivery**: 0.9639
- **warm_unseen_mean_delivery**: None
- **cold_seen_mean_delivery**: 0.9653
- **cold_unseen_mean_delivery**: None
- **warm_seen_session_count**: 27
- **warm_unseen_session_count**: 0

**Warm system summary:**

```
{
  "capability_policy": "fixed-visible",
  "cycles": 46796,
  "injected_packets": 10350,
  "admitted_packets": 10350,
  "delivered_packets": 10103,
  "delivery_ratio": 0.9761,
  "dropped_packets": 247,
  "drop_ratio": 0.0239,
  "source_buffer": 0,
  "mean_latency": 3.4356,
  "mean_hops": 4.0,
  "node_atp_total": 11.6828,
  "mean_route_cost": 0.03258,
  "mean_feedback_award": 0.1584,
  "mean_source_admission": 0.715,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 8889,
  "mean_bit_accuracy": 0.8799
}
```

**Cold system summary:**

```
{
  "capability_policy": "fixed-visible",
  "cycles": 14472,
  "injected_packets": 10350,
  "admitted_packets": 10350,
  "delivered_packets": 10069,
  "delivery_ratio": 0.9729,
  "dropped_packets": 281,
  "drop_ratio": 0.0271,
  "source_buffer": 0,
  "mean_latency": 3.4079,
  "mean_hops": 4.0,
  "node_atp_total": 12.41,
  "mean_route_cost": 0.03199,
  "mean_feedback_award": 0.1612,
  "mean_source_admission": 0.7152,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 9019,
  "mean_bit_accuracy": 0.8957
}
```
