# REAL Occupancy v3 — session carryover experiment

**run_id:** `v3_seed13_20260320T185629`  
**run_at:** `2026-03-20T18:56:29+00:00`  
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
| max_eval_sessions | None |
| max_train_sessions | None |
| normalize | True |
| packet_ttl | 8 |
| selector_seed | 13 |
| summary_only | True |
| topology_mode | multihop_routing |
| train_session_fraction | 0.7 |
| window_size | 5 |

## Worker policy

| Key | Value |
|---|---|
| requested_workers | None |
| auto_cpu_target_fraction | 0.75 |
| eval_workers_by_protocol | {'fresh_session_eval': 15, 'persistent_eval': 2} |

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
| accuracy | 0.9147 |
| precision | 0.8686 |
| recall | 0.8470 |
| f1 | 0.8577 |

| Stat | Value |
|---|---|
| episode_count | 926 |
| mean_delivered_packets | 23.9773 |
| mean_dropped_packets | 1.0227 |
| mean_feedback_events | 21.4719 |

## Phase 3 — Warm / cold eval & carryover

### Warm eval

| Metric | Value |
|---|---|
| accuracy | 0.9807 |
| precision | 0.9877 |
| recall | 0.9195 |
| f1 | 0.9524 |

### Cold eval

| Metric | Value |
|---|---|
| accuracy | 0.9686 |
| precision | 1.0000 |
| recall | 0.8506 |
| f1 | 0.9193 |

### Carryover efficiency metrics

| Metric | Value |
|---|---|
| mean_efficiency_ratio | 0.9977 |
| warm_sessions_to_80pct | 0 |
| cold_sessions_to_80pct | 0 |

**Delivery checkpoints:**

| checkpoint | warm | cold | ratio |
|---|---:|---:|---:|
| session_1 | 1.0 | 1.0 | 1.0000 |
| session_5 | 1.0 | 1.0 | 1.0000 |
| session_10 | 0.9778 | 0.9822 | 0.9955 |
| session_20 | 0.98 | 0.99 | 0.9899 |

## Phase 4 — Context transfer probe

- **context_mode**: online_running_context
- **training_context_codes**: [0, 1, 2, 3]
- **eval_context_codes**: [0, 1, 2, 3]
- **comparison_applicable**: False
- **status**: not_applicable_all_eval_contexts_seen
- **warm_seen_mean_delivery**: 0.984
- **warm_unseen_mean_delivery**: None
- **cold_seen_mean_delivery**: 0.9863
- **cold_unseen_mean_delivery**: None
- **warm_seen_session_count**: 27
- **warm_unseen_session_count**: 0

## System summaries

### Train

```
{
  "capability_policy": "fixed-visible",
  "cycles": 33012,
  "injected_packets": 23150,
  "admitted_packets": 23150,
  "delivered_packets": 22203,
  "delivery_ratio": 0.9591,
  "dropped_packets": 947,
  "drop_ratio": 0.0409,
  "source_buffer": 0,
  "mean_latency": 3.4671,
  "mean_hops": 4.0,
  "node_atp_total": 6.3198,
  "mean_route_cost": 0.03165,
  "mean_feedback_award": 0.1612,
  "mean_source_admission": 0.7013,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 19883,
  "mean_bit_accuracy": 0.8955
}
```

### Warm eval

```
{
  "capability_policy": "fixed-visible",
  "cycles": 905602,
  "injected_packets": 10350,
  "admitted_packets": 10350,
  "delivered_packets": 10080,
  "delivery_ratio": 0.9739,
  "dropped_packets": 270,
  "drop_ratio": 0.0261,
  "source_buffer": 0,
  "mean_latency": 3.3582,
  "mean_hops": 4.0,
  "node_atp_total": 11.6699,
  "mean_route_cost": 0.0324,
  "mean_feedback_award": 0.1725,
  "mean_source_admission": 0.0114,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 9659,
  "mean_bit_accuracy": 0.9582
}
```

### Cold eval

```
{
  "capability_policy": "fixed-visible",
  "cycles": 14103,
  "injected_packets": 10350,
  "admitted_packets": 10350,
  "delivered_packets": 10051,
  "delivery_ratio": 0.9711,
  "dropped_packets": 299,
  "drop_ratio": 0.0289,
  "source_buffer": 0,
  "mean_latency": 3.3077,
  "mean_hops": 4.0,
  "node_atp_total": 11.8676,
  "mean_route_cost": 0.0331,
  "mean_feedback_award": 0.1723,
  "mean_source_admission": 0.7339,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 9620,
  "mean_bit_accuracy": 0.9571
}
```

## Eval protocols

### fresh_session_eval

- **workers_used**: 15
- **parallelism_status**: process_pool:15
- **warm_reset_count**: 27
- **cold_reset_count**: 27

| Metric | Value |
|---|---|
| mean_efficiency_ratio | 0.9977 |
| session_1_delivery_delta | 0.0 |
| mean_first_episode_delivery_delta | 0.0 |
| mean_first_three_episode_delivery_delta | -0.0042 |
| warm_sessions_to_80pct | 0 |
| cold_sessions_to_80pct | 0 |

**Context transfer probe:**

- **context_mode**: online_running_context
- **training_context_codes**: [0, 1, 2, 3]
- **eval_context_codes**: [0, 1, 2, 3]
- **comparison_applicable**: False
- **status**: not_applicable_all_eval_contexts_seen
- **warm_seen_mean_delivery**: 0.984
- **warm_unseen_mean_delivery**: None
- **cold_seen_mean_delivery**: 0.9863
- **cold_unseen_mean_delivery**: None
- **warm_seen_session_count**: 27
- **warm_unseen_session_count**: 0

**Warm system summary:**

```
{
  "capability_policy": "fixed-visible",
  "cycles": 905602,
  "injected_packets": 10350,
  "admitted_packets": 10350,
  "delivered_packets": 10080,
  "delivery_ratio": 0.9739,
  "dropped_packets": 270,
  "drop_ratio": 0.0261,
  "source_buffer": 0,
  "mean_latency": 3.3582,
  "mean_hops": 4.0,
  "node_atp_total": 11.6699,
  "mean_route_cost": 0.0324,
  "mean_feedback_award": 0.1725,
  "mean_source_admission": 0.0114,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 9659,
  "mean_bit_accuracy": 0.9582
}
```

**Cold system summary:**

```
{
  "capability_policy": "fixed-visible",
  "cycles": 14103,
  "injected_packets": 10350,
  "admitted_packets": 10350,
  "delivered_packets": 10051,
  "delivery_ratio": 0.9711,
  "dropped_packets": 299,
  "drop_ratio": 0.0289,
  "source_buffer": 0,
  "mean_latency": 3.3077,
  "mean_hops": 4.0,
  "node_atp_total": 11.8676,
  "mean_route_cost": 0.0331,
  "mean_feedback_award": 0.1723,
  "mean_source_admission": 0.7339,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 9620,
  "mean_bit_accuracy": 0.9571
}
```

### persistent_eval

- **workers_used**: 2
- **parallelism_status**: process_pool:2
- **warm_reset_count**: 1
- **cold_reset_count**: 1

| Metric | Value |
|---|---|
| mean_efficiency_ratio | 0.9519 |
| session_1_delivery_delta | 0.0 |
| mean_first_episode_delivery_delta | -0.0148 |
| mean_first_three_episode_delivery_delta | -0.0558 |
| warm_sessions_to_80pct | 0 |
| cold_sessions_to_80pct | 0 |

**Context transfer probe:**

- **context_mode**: online_running_context
- **training_context_codes**: [0, 1, 2, 3]
- **eval_context_codes**: [0, 1, 2, 3]
- **comparison_applicable**: False
- **status**: not_applicable_all_eval_contexts_seen
- **warm_seen_mean_delivery**: 0.8865
- **warm_unseen_mean_delivery**: None
- **cold_seen_mean_delivery**: 0.9324
- **cold_unseen_mean_delivery**: None
- **warm_seen_session_count**: 27
- **warm_unseen_session_count**: 0

**Warm system summary:**

```
{
  "capability_policy": "fixed-visible",
  "cycles": 48327,
  "injected_packets": 10350,
  "admitted_packets": 10350,
  "delivered_packets": 9695,
  "delivery_ratio": 0.9367,
  "dropped_packets": 655,
  "drop_ratio": 0.0633,
  "source_buffer": 0,
  "mean_latency": 3.5391,
  "mean_hops": 4.0,
  "node_atp_total": 12.7108,
  "mean_route_cost": 0.03255,
  "mean_feedback_award": 0.1617,
  "mean_source_admission": 0.6758,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 8712,
  "mean_bit_accuracy": 0.8986
}
```

**Cold system summary:**

```
{
  "capability_policy": "fixed-visible",
  "cycles": 14744,
  "injected_packets": 10350,
  "admitted_packets": 10350,
  "delivered_packets": 9980,
  "delivery_ratio": 0.9643,
  "dropped_packets": 370,
  "drop_ratio": 0.0357,
  "source_buffer": 0,
  "mean_latency": 3.5063,
  "mean_hops": 4.0,
  "node_atp_total": 12.5212,
  "mean_route_cost": 0.03254,
  "mean_feedback_award": 0.1643,
  "mean_source_admission": 0.702,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 9109,
  "mean_bit_accuracy": 0.9127
}
```
