# REAL Occupancy v3 — session carryover experiment

**run_id:** `v3_seed13_20260320T122124`  
**run_at:** `2026-03-20T12:21:24+00:00`  
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
| max_train_sessions | 65 |
| normalize | True |
| packet_ttl | 8 |
| selector_seed | 13 |
| summary_only | False |
| train_session_fraction | 0.7 |
| window_size | 5 |

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
| accuracy | 0.9082 |
| precision | 0.8475 |
| recall | 0.8505 |
| f1 | 0.8490 |

| Stat | Value |
|---|---|
| episode_count | 926 |
| mean_delivered_packets | 24.3132 |
| mean_dropped_packets | 0.6868 |
| mean_feedback_events | 18.108 |

## Phase 3 — Warm / cold eval & carryover

### Warm eval

| Metric | Value |
|---|---|
| accuracy | 0.9155 |
| precision | 0.7889 |
| recall | 0.8161 |
| f1 | 0.8023 |

### Cold eval

| Metric | Value |
|---|---|
| accuracy | 0.9251 |
| precision | 0.8182 |
| recall | 0.8276 |
| f1 | 0.8229 |

### Carryover efficiency metrics

| Metric | Value |
|---|---|
| mean_efficiency_ratio | 0.9947 |
| warm_sessions_to_80pct | 0 |
| cold_sessions_to_80pct | 0 |

**Delivery checkpoints:**

| checkpoint | warm | cold | ratio |
|---|---:|---:|---:|
| session_1 | 1.0 | 1.0 | 1.0000 |
| session_5 | 0.8 | 0.84 | 0.9524 |
| session_10 | 0.9822 | 0.9911 | 0.9910 |
| session_20 | 0.94 | 0.96 | 0.9792 |

## Phase 4 — Context transfer probe

- **training_context_codes**: [0, 1, 2, 3]
- **warm_seen_mean_delivery**: 0.9564
- **warm_unseen_mean_delivery**: None
- **cold_seen_mean_delivery**: 0.9622
- **cold_unseen_mean_delivery**: None
- **warm_seen_session_count**: 27
- **warm_unseen_session_count**: 0

## System summaries

### Train

```
{
  "cycles": 34248,
  "injected_packets": 23150,
  "delivered_packets": 22514,
  "delivery_ratio": 0.9725,
  "dropped_packets": 636,
  "drop_ratio": 0.0275,
  "mean_latency": 3.3156,
  "mean_route_cost": 0.0274,
  "mean_feedback_award": 0.1341,
  "node_atp_total": 6.0485,
  "exact_matches": 16768,
  "mean_bit_accuracy": 0.7448
}
```

### Warm eval

```
{
  "cycles": 49742,
  "injected_packets": 10350,
  "delivered_packets": 10019,
  "delivery_ratio": 0.968,
  "dropped_packets": 331,
  "drop_ratio": 0.032,
  "mean_latency": 3.3577,
  "mean_route_cost": 0.03019,
  "mean_feedback_award": 0.1354,
  "node_atp_total": 5.6444,
  "exact_matches": 7535,
  "mean_bit_accuracy": 0.7521
}
```

### Cold eval

```
{
  "cycles": 15013,
  "injected_packets": 10350,
  "delivered_packets": 9940,
  "delivery_ratio": 0.9604,
  "dropped_packets": 410,
  "drop_ratio": 0.0396,
  "mean_latency": 3.187,
  "mean_route_cost": 0.03027,
  "mean_feedback_award": 0.1365,
  "node_atp_total": 6.0707,
  "exact_matches": 7536,
  "mean_bit_accuracy": 0.7581
}
```
