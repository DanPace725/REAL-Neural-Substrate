# REAL Occupancy v3 — session carryover experiment

**run_id:** `v3_seed13_20260320T181522`  
**run_at:** `2026-03-20T18:15:22+00:00`  
**git_sha:** `c5a20ac`  
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
| max_eval_sessions | 5 |
| max_train_sessions | 10 |
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
| eval_workers_by_protocol | {'fresh_session_eval': 10, 'persistent_eval': 2} |

## Dataset

- dataset_rows: **1344**
- total_episodes: **1340**
- total_sessions: **89**
- train_session_count: **10**
- eval_session_count: **5**
- co2_training_median: **0.974881**
- light_training_median: **1.045862**
- training_context_codes: [0, 1, 2, 3]

### Train inventory

```
{
  "session_count": 10,
  "by_label": {
    "0": 5,
    "1": 5
  },
  "by_context_code": {
    "0": 4,
    "1": 1,
    "3": 5
  },
  "episode_lengths": {
    "min": 1,
    "mean": 13.4,
    "max": 58
  },
  "context_codes_by_label": {
    "0": [
      0,
      1,
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
| accuracy | 0.9104 |
| precision | 0.8571 |
| recall | 0.8571 |
| f1 | 0.8571 |

| Stat | Value |
|---|---|
| episode_count | 134 |
| mean_delivered_packets | 23.903 |
| mean_dropped_packets | 1.097 |
| mean_feedback_events | 21.3209 |

## Phase 3 — Warm / cold eval & carryover

### Warm eval

| Metric | Value |
|---|---|
| accuracy | 0.9545 |
| precision | 0.6667 |
| recall | 0.8000 |
| f1 | 0.7273 |

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
| mean_efficiency_ratio | 0.9912 |
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
- **warm_seen_mean_delivery**: 0.9819
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
  "cycles": 4743,
  "injected_packets": 3350,
  "admitted_packets": 3350,
  "delivered_packets": 3203,
  "delivery_ratio": 0.9561,
  "dropped_packets": 147,
  "drop_ratio": 0.0439,
  "source_buffer": 0,
  "mean_latency": 3.4074,
  "mean_hops": 4.0,
  "node_atp_total": 11.9321,
  "mean_route_cost": 0.03259,
  "mean_feedback_award": 0.1606,
  "mean_source_admission": 0.7063,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 2857,
  "mean_bit_accuracy": 0.892
}
```

### Warm eval

```
{
  "capability_policy": "fixed-visible",
  "cycles": 25967,
  "injected_packets": 1650,
  "admitted_packets": 1650,
  "delivered_packets": 1591,
  "delivery_ratio": 0.9642,
  "dropped_packets": 59,
  "drop_ratio": 0.0358,
  "source_buffer": 0,
  "mean_latency": 3.2627,
  "mean_hops": 4.0,
  "node_atp_total": 11.0462,
  "mean_route_cost": 0.0337,
  "mean_feedback_award": 0.1699,
  "mean_source_admission": 0.0635,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 1502,
  "mean_bit_accuracy": 0.9441
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
| mean_efficiency_ratio | 0.9912 |
| session_1_delivery_delta | 0.0 |
| mean_first_episode_delivery_delta | 0.0 |
| mean_first_three_episode_delivery_delta | -0.0133 |
| warm_sessions_to_80pct | 0 |
| cold_sessions_to_80pct | 0 |

**Context transfer probe:**

- **context_mode**: online_running_context
- **training_context_codes**: [0, 1, 2, 3]
- **eval_context_codes**: [0, 2, 3]
- **comparison_applicable**: False
- **status**: not_applicable_all_eval_contexts_seen
- **warm_seen_mean_delivery**: 0.9819
- **warm_unseen_mean_delivery**: None
- **cold_seen_mean_delivery**: 0.9906
- **cold_unseen_mean_delivery**: None
- **warm_seen_session_count**: 5
- **warm_unseen_session_count**: 0

**Warm system summary:**

```
{
  "capability_policy": "fixed-visible",
  "cycles": 25967,
  "injected_packets": 1650,
  "admitted_packets": 1650,
  "delivered_packets": 1591,
  "delivery_ratio": 0.9642,
  "dropped_packets": 59,
  "drop_ratio": 0.0358,
  "source_buffer": 0,
  "mean_latency": 3.2627,
  "mean_hops": 4.0,
  "node_atp_total": 11.0462,
  "mean_route_cost": 0.0337,
  "mean_feedback_award": 0.1699,
  "mean_source_admission": 0.0635,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 1502,
  "mean_bit_accuracy": 0.9441
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

### persistent_eval

- **workers_used**: 2
- **parallelism_status**: process_pool:2
- **warm_reset_count**: 1
- **cold_reset_count**: 1

| Metric | Value |
|---|---|
| mean_efficiency_ratio | 0.9783 |
| session_1_delivery_delta | 0.0 |
| mean_first_episode_delivery_delta | 0.0 |
| mean_first_three_episode_delivery_delta | -0.0387 |
| warm_sessions_to_80pct | 0 |
| cold_sessions_to_80pct | 0 |

**Context transfer probe:**

- **context_mode**: online_running_context
- **training_context_codes**: [0, 1, 2, 3]
- **eval_context_codes**: [0, 2, 3]
- **comparison_applicable**: False
- **status**: not_applicable_all_eval_contexts_seen
- **warm_seen_mean_delivery**: 0.9346
- **warm_unseen_mean_delivery**: None
- **cold_seen_mean_delivery**: 0.955
- **cold_unseen_mean_delivery**: None
- **warm_seen_session_count**: 5
- **warm_unseen_session_count**: 0

**Warm system summary:**

```
{
  "capability_policy": "fixed-visible",
  "cycles": 7104,
  "injected_packets": 1650,
  "admitted_packets": 1650,
  "delivered_packets": 1565,
  "delivery_ratio": 0.9485,
  "dropped_packets": 85,
  "drop_ratio": 0.0515,
  "source_buffer": 0,
  "mean_latency": 3.5419,
  "mean_hops": 4.0,
  "node_atp_total": 2.7147,
  "mean_route_cost": 0.03223,
  "mean_feedback_award": 0.1633,
  "mean_source_admission": 0.6989,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 1420,
  "mean_bit_accuracy": 0.9073
}
```

**Cold system summary:**

```
{
  "capability_policy": "fixed-visible",
  "cycles": 2298,
  "injected_packets": 1650,
  "admitted_packets": 1650,
  "delivered_packets": 1592,
  "delivery_ratio": 0.9648,
  "dropped_packets": 58,
  "drop_ratio": 0.0352,
  "source_buffer": 0,
  "mean_latency": 3.3788,
  "mean_hops": 4.0,
  "node_atp_total": 2.6546,
  "mean_route_cost": 0.03216,
  "mean_feedback_award": 0.1638,
  "mean_source_admission": 0.718,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 1449,
  "mean_bit_accuracy": 0.9102
}
```
