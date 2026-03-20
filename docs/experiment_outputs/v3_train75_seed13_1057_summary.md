# REAL Occupancy v3 — session carryover experiment

**run_id:** `v3_seed13_20260320T175945`  
**run_at:** `2026-03-20T17:59:45+00:00`  
**git_sha:** `c5a20ac`  
**primary_eval_mode:** `persistent_eval`  

## Config

| Key | Value |
|---|---|
| context_mode | latent_context |
| csv_path | occupancy_baseline/data/occupancy_synth_v1.csv |
| eval_feedback_fraction | 1.0 |
| eval_mode | persistent_eval |
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
| eval_workers_by_protocol | {'persistent_eval': 2} |

## Dataset

- dataset_rows: **1344**
- total_episodes: **1340**
- total_sessions: **89**
- train_session_count: **10**
- eval_session_count: **5**
- co2_training_median: **0.974881**
- light_training_median: **1.045862**
- training_context_codes: []

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
| accuracy | 0.9254 |
| precision | 0.9000 |
| recall | 0.8571 |
| f1 | 0.8780 |

| Stat | Value |
|---|---|
| episode_count | 134 |
| mean_delivered_packets | 17.8358 |
| mean_dropped_packets | 7.1642 |
| mean_feedback_events | 12.6866 |

## Phase 3 — Warm / cold eval & carryover

### Warm eval

| Metric | Value |
|---|---|
| accuracy | 0.9091 |
| precision | 0.3333 |
| recall | 0.2000 |
| f1 | 0.2500 |

### Cold eval

| Metric | Value |
|---|---|
| accuracy | 0.9242 |
| precision | 0.5000 |
| recall | 0.2000 |
| f1 | 0.2857 |

### Carryover efficiency metrics

| Metric | Value |
|---|---|
| mean_efficiency_ratio | 0.9178 |
| warm_sessions_to_80pct | 0 |
| cold_sessions_to_80pct | 0 |

**Delivery checkpoints:**

| checkpoint | warm | cold | ratio |
|---|---:|---:|---:|
| session_1 | 1.0 | 1.0 | 1.0000 |
| session_5 | 0.48 | 0.6 | 0.8000 |
| session_10 | None | None | — |
| session_20 | None | None | — |

## Phase 4 — Context transfer probe

- **context_mode**: latent_context
- **training_context_codes**: []
- **comparison_applicable**: False
- **status**: not_applicable_latent_context
- **warm_seen_mean_delivery**: None
- **warm_unseen_mean_delivery**: None
- **cold_seen_mean_delivery**: None
- **cold_unseen_mean_delivery**: None
- **warm_seen_session_count**: 0
- **warm_unseen_session_count**: 0
- **eval_context_codes**: []

## System summaries

### Train

```
{
  "capability_policy": "fixed-visible",
  "cycles": 5926,
  "injected_packets": 3350,
  "admitted_packets": 3350,
  "delivered_packets": 2390,
  "delivery_ratio": 0.7134,
  "dropped_packets": 960,
  "drop_ratio": 0.2866,
  "source_buffer": 0,
  "mean_latency": 3.41,
  "mean_hops": 4.0,
  "node_atp_total": 8.5685,
  "mean_route_cost": 0.03482,
  "mean_feedback_award": 0.128,
  "mean_source_admission": 0.5653,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 1700,
  "mean_bit_accuracy": 0.7113
}
```

### Warm eval

```
{
  "capability_policy": "fixed-visible",
  "cycles": 8614,
  "injected_packets": 1650,
  "admitted_packets": 1650,
  "delivered_packets": 1452,
  "delivery_ratio": 0.88,
  "dropped_packets": 198,
  "drop_ratio": 0.12,
  "source_buffer": 0,
  "mean_latency": 3.6481,
  "mean_hops": 4.0,
  "node_atp_total": 5.6657,
  "mean_route_cost": 0.03635,
  "mean_feedback_award": 0.1379,
  "mean_source_admission": 0.6138,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 1112,
  "mean_bit_accuracy": 0.7658
}
```

### Cold eval

```
{
  "capability_policy": "fixed-visible",
  "cycles": 3159,
  "injected_packets": 1650,
  "admitted_packets": 1650,
  "delivered_packets": 1432,
  "delivery_ratio": 0.8679,
  "dropped_packets": 218,
  "drop_ratio": 0.1321,
  "source_buffer": 0,
  "mean_latency": 4.5461,
  "mean_hops": 4.0,
  "node_atp_total": 7.3468,
  "mean_route_cost": 0.03453,
  "mean_feedback_award": 0.1241,
  "mean_source_admission": 0.5223,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 987,
  "mean_bit_accuracy": 0.6892
}
```

## Eval protocols

### persistent_eval

- **workers_used**: 2
- **parallelism_status**: process_pool:2
- **warm_reset_count**: 1
- **cold_reset_count**: 1

| Metric | Value |
|---|---|
| mean_efficiency_ratio | 0.9178 |
| session_1_delivery_delta | 0.0 |
| mean_first_episode_delivery_delta | -0.048 |
| mean_first_three_episode_delivery_delta | -0.0853 |
| warm_sessions_to_80pct | 0 |
| cold_sessions_to_80pct | 0 |

**Context transfer probe:**

- **context_mode**: latent_context
- **training_context_codes**: []
- **comparison_applicable**: False
- **status**: not_applicable_latent_context
- **warm_seen_mean_delivery**: None
- **warm_unseen_mean_delivery**: None
- **cold_seen_mean_delivery**: None
- **cold_unseen_mean_delivery**: None
- **warm_seen_session_count**: 0
- **warm_unseen_session_count**: 0
- **eval_context_codes**: []

**Warm system summary:**

```
{
  "capability_policy": "fixed-visible",
  "cycles": 8614,
  "injected_packets": 1650,
  "admitted_packets": 1650,
  "delivered_packets": 1452,
  "delivery_ratio": 0.88,
  "dropped_packets": 198,
  "drop_ratio": 0.12,
  "source_buffer": 0,
  "mean_latency": 3.6481,
  "mean_hops": 4.0,
  "node_atp_total": 5.6657,
  "mean_route_cost": 0.03635,
  "mean_feedback_award": 0.1379,
  "mean_source_admission": 0.6138,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 1112,
  "mean_bit_accuracy": 0.7658
}
```

**Cold system summary:**

```
{
  "capability_policy": "fixed-visible",
  "cycles": 3159,
  "injected_packets": 1650,
  "admitted_packets": 1650,
  "delivered_packets": 1432,
  "delivery_ratio": 0.8679,
  "dropped_packets": 218,
  "drop_ratio": 0.1321,
  "source_buffer": 0,
  "mean_latency": 4.5461,
  "mean_hops": 4.0,
  "node_atp_total": 7.3468,
  "mean_route_cost": 0.03453,
  "mean_feedback_award": 0.1241,
  "mean_source_admission": 0.5223,
  "last_source_admission": 0,
  "source_admission_support": 0.5,
  "source_admission_velocity": 0.0,
  "mean_source_efficiency": 0.0,
  "exact_matches": 987,
  "mean_bit_accuracy": 0.6892
}
```
