# REAL Occupancy v3 — session carryover experiment

**run_id:** `v3_seed13_20260320T134353`  
**run_at:** `2026-03-20T13:43:53+00:00`  
**git_sha:** `c357957`  

## Config

| Key | Value |
|---|---|
| csv_path | occupancy_baseline/data/occupancy_synth_v1.csv |
| eval_feedback_fraction | 1.0 |
| feedback_amount | 0.18 |
| feedback_drain_cycles | 4 |
| forward_drain_cycles | 16 |
| max_eval_sessions | 19 |
| max_train_sessions | None |
| normalize | True |
| packet_ttl | 8 |
| selector_seed | 13 |
| summary_only | True |
| train_session_fraction | 0.79 |
| window_size | 5 |

## Dataset

- dataset_rows: **1344**
- total_episodes: **1340**
- total_sessions: **89**
- train_session_count: **70**
- eval_session_count: **19**
- co2_training_median: **0.974881**
- light_training_median: **1.045862**
- training_context_codes: [0, 1, 2, 3]

### Train inventory

```
{
  "session_count": 70,
  "by_label": {
    "0": 35,
    "1": 35
  },
  "by_context_code": {
    "0": 27,
    "1": 8,
    "3": 27,
    "2": 8
  },
  "episode_lengths": {
    "min": 1,
    "mean": 14.66,
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
  "session_count": 19,
  "by_label": {
    "0": 10,
    "1": 9
  },
  "by_context_code": {
    "0": 6,
    "1": 6,
    "3": 7
  },
  "episode_lengths": {
    "min": 1,
    "mean": 16.53,
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
      3
    ]
  }
}
```

## Phase 2 — Training summary

| Metric | Value |
|---|---|
| accuracy | 0.9055 |
| precision | 0.8449 |
| recall | 0.8476 |
| f1 | 0.8463 |

| Stat | Value |
|---|---|
| episode_count | 1026 |
| mean_delivered_packets | 24.2066 |
| mean_dropped_packets | 0.7934 |
| mean_feedback_events | 17.9981 |

## Phase 3 — Warm / cold eval & carryover

### Warm eval

| Metric | Value |
|---|---|
| accuracy | 0.9331 |
| precision | 0.7759 |
| recall | 0.8491 |
| f1 | 0.8108 |

### Cold eval

| Metric | Value |
|---|---|
| accuracy | 0.9299 |
| precision | 0.7818 |
| recall | 0.8113 |
| f1 | 0.7963 |

### Carryover efficiency metrics

| Metric | Value |
|---|---|
| mean_efficiency_ratio | 1.014 |
| warm_sessions_to_80pct | 0 |
| cold_sessions_to_80pct | 0 |

**Delivery checkpoints:**

| checkpoint | warm | cold | ratio |
|---|---:|---:|---:|
| session_1 | 0.9386 | 0.969 | 0.9686 |
| session_5 | 0.9 | 0.95 | 0.9474 |
| session_10 | 0.9771 | 0.9829 | 0.9941 |
| session_20 | None | None | — |

## Phase 4 — Context transfer probe

- **training_context_codes**: [0, 1, 2, 3]
- **warm_seen_mean_delivery**: 0.95
- **warm_unseen_mean_delivery**: None
- **cold_seen_mean_delivery**: 0.9418
- **cold_unseen_mean_delivery**: None
- **warm_seen_session_count**: 19
- **warm_unseen_session_count**: 0

## System summaries

### Train

```
{
  "cycles": 37952,
  "injected_packets": 25650,
  "delivered_packets": 24836,
  "delivery_ratio": 0.9683,
  "dropped_packets": 814,
  "drop_ratio": 0.0317,
  "mean_latency": 3.2907,
  "mean_route_cost": 0.02736,
  "mean_feedback_award": 0.1338,
  "node_atp_total": 6.0389,
  "exact_matches": 18466,
  "mean_bit_accuracy": 0.7435
}
```

### Warm eval

```
{
  "cycles": 49660,
  "injected_packets": 7850,
  "delivered_packets": 7622,
  "delivery_ratio": 0.971,
  "dropped_packets": 228,
  "drop_ratio": 0.029,
  "mean_latency": 3.3355,
  "mean_route_cost": 0.02979,
  "mean_feedback_award": 0.1378,
  "node_atp_total": 6.0156,
  "exact_matches": 5834,
  "mean_bit_accuracy": 0.7654
}
```

### Cold eval

```
{
  "cycles": 12106,
  "injected_packets": 7850,
  "delivered_packets": 7320,
  "delivery_ratio": 0.9325,
  "dropped_packets": 530,
  "drop_ratio": 0.0675,
  "mean_latency": 3.2075,
  "mean_route_cost": 0.0298,
  "mean_feedback_award": 0.1334,
  "node_atp_total": 6.0649,
  "exact_matches": 5425,
  "mean_bit_accuracy": 0.7411
}
```
