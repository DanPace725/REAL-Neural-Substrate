# REAL Occupancy v3 — session carryover experiment

**run_id:** `v3_seed13_20260320T143103`  
**run_at:** `2026-03-20T14:31:03+00:00`  
**git_sha:** `c357957`  

## Config

| Key | Value |
|---|---|
| csv_path | occupancy_baseline/data/occupancy_synth_v1.csv |
| eval_feedback_fraction | 1.0 |
| feedback_amount | 0.18 |
| feedback_drain_cycles | 4 |
| forward_drain_cycles | 16 |
| max_eval_sessions | 30 |
| max_train_sessions | None |
| normalize | True |
| packet_ttl | 8 |
| selector_seed | 13 |
| summary_only | True |
| train_session_fraction | 0.5 |
| window_size | 5 |

## Dataset

- dataset_rows: **1344**
- total_episodes: **1340**
- total_sessions: **89**
- train_session_count: **44**
- eval_session_count: **30**
- co2_training_median: **1.021993**
- light_training_median: **1.003854**
- training_context_codes: [0, 1, 2, 3]

### Train inventory

```
{
  "session_count": 44,
  "by_label": {
    "0": 22,
    "1": 22
  },
  "by_context_code": {
    "0": 17,
    "1": 5,
    "3": 17,
    "2": 5
  },
  "episode_lengths": {
    "min": 1,
    "mean": 16.5,
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
  "session_count": 30,
  "by_label": {
    "0": 15,
    "1": 15
  },
  "by_context_code": {
    "3": 10,
    "0": 11,
    "2": 2,
    "1": 7
  },
  "episode_lengths": {
    "min": 1,
    "mean": 12.47,
    "max": 59
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
| accuracy | 0.9146 |
| precision | 0.8510 |
| recall | 0.8510 |
| f1 | 0.8510 |

| Stat | Value |
|---|---|
| episode_count | 726 |
| mean_delivered_packets | 24.2975 |
| mean_dropped_packets | 0.7025 |
| mean_feedback_events | 18.2328 |

## Phase 3 — Warm / cold eval & carryover

### Warm eval

| Metric | Value |
|---|---|
| accuracy | 0.8984 |
| precision | 0.8500 |
| recall | 0.8361 |
| f1 | 0.8430 |

### Cold eval

| Metric | Value |
|---|---|
| accuracy | 0.8930 |
| precision | 0.8534 |
| recall | 0.8115 |
| f1 | 0.8319 |

### Carryover efficiency metrics

| Metric | Value |
|---|---|
| mean_efficiency_ratio | 0.9976 |
| warm_sessions_to_80pct | 0 |
| cold_sessions_to_80pct | 0 |

**Delivery checkpoints:**

| checkpoint | warm | cold | ratio |
|---|---:|---:|---:|
| session_1 | 1.0 | 1.0 | 1.0000 |
| session_5 | 0.96 | 0.96 | 1.0000 |
| session_10 | 0.936 | 0.88 | 1.0636 |
| session_20 | 0.98 | 1.0 | 0.9800 |

## Phase 4 — Context transfer probe

- **training_context_codes**: [0, 1, 2, 3]
- **warm_seen_mean_delivery**: 0.9478
- **warm_unseen_mean_delivery**: None
- **cold_seen_mean_delivery**: 0.9521
- **cold_unseen_mean_delivery**: None
- **warm_seen_session_count**: 30
- **warm_unseen_session_count**: 0

## System summaries

### Train

```
{
  "cycles": 27263,
  "injected_packets": 18150,
  "delivered_packets": 17640,
  "delivery_ratio": 0.9719,
  "dropped_packets": 510,
  "drop_ratio": 0.0281,
  "mean_latency": 3.3409,
  "mean_route_cost": 0.02826,
  "mean_feedback_award": 0.1351,
  "node_atp_total": 5.8629,
  "exact_matches": 13237,
  "mean_bit_accuracy": 0.7504
}
```

### Warm eval

```
{
  "cycles": 41142,
  "injected_packets": 9350,
  "delivered_packets": 8848,
  "delivery_ratio": 0.9463,
  "dropped_packets": 502,
  "drop_ratio": 0.0537,
  "mean_latency": 3.1834,
  "mean_route_cost": 0.02884,
  "mean_feedback_award": 0.1344,
  "node_atp_total": 5.9265,
  "exact_matches": 6608,
  "mean_bit_accuracy": 0.7468
}
```

### Cold eval

```
{
  "cycles": 14019,
  "injected_packets": 9350,
  "delivered_packets": 9084,
  "delivery_ratio": 0.9716,
  "dropped_packets": 266,
  "drop_ratio": 0.0284,
  "mean_latency": 3.3293,
  "mean_route_cost": 0.02936,
  "mean_feedback_award": 0.1328,
  "node_atp_total": 5.9523,
  "exact_matches": 6700,
  "mean_bit_accuracy": 0.7376
}
```
