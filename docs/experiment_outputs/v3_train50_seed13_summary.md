# REAL Occupancy v3 — session carryover experiment

**run_id:** `v3_seed13_20260320T033522`  
**run_at:** `2026-03-20T03:35:22+00:00`  
**git_sha:** `c357957`  

## Config

| Key | Value |
|---|---|
| csv_path | occupancy_baseline/data/occupancy_synth_v1.csv |
| eval_feedback_fraction | 1.0 |
| feedback_amount | 0.18 |
| feedback_drain_cycles | 4 |
| forward_drain_cycles | 16 |
| max_eval_sessions | 27 |
| max_train_sessions | 50 |
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
- train_session_count: **50**
- eval_session_count: **27**
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
| accuracy | 0.9138 |
| precision | 0.8517 |
| recall | 0.8517 |
| f1 | 0.8517 |

| Stat | Value |
|---|---|
| episode_count | 812 |
| mean_delivered_packets | 24.314 |
| mean_dropped_packets | 0.686 |
| mean_feedback_events | 18.1897 |

## Phase 3 — Warm / cold eval & carryover

### Warm eval

| Metric | Value |
|---|---|
| accuracy | 0.9155 |
| precision | 0.8095 |
| recall | 0.7816 |
| f1 | 0.7953 |

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
| mean_efficiency_ratio | 0.9711 |
| warm_sessions_to_80pct | 0 |
| cold_sessions_to_80pct | 0 |

**Delivery checkpoints:**

| checkpoint | warm | cold | ratio |
|---|---:|---:|---:|
| session_1 | 1.0 | 1.0 | 1.0000 |
| session_5 | 0.76 | 0.84 | 0.9048 |
| session_10 | 0.9111 | 0.9911 | 0.9193 |
| session_20 | 0.94 | 0.96 | 0.9792 |

## Phase 4 — Context transfer probe

- **training_context_codes**: [0, 1, 2, 3]
- **warm_seen_mean_delivery**: 0.9342
- **warm_unseen_mean_delivery**: None
- **cold_seen_mean_delivery**: 0.9622
- **cold_unseen_mean_delivery**: None
- **warm_seen_session_count**: 27
- **warm_unseen_session_count**: 0

## System summaries

### Train

```
{
  "cycles": 30113,
  "injected_packets": 20300,
  "delivered_packets": 19743,
  "delivery_ratio": 0.9726,
  "dropped_packets": 557,
  "drop_ratio": 0.0274,
  "mean_latency": 3.3223,
  "mean_route_cost": 0.02757,
  "mean_feedback_award": 0.1347,
  "node_atp_total": 6.1043,
  "exact_matches": 14770,
  "mean_bit_accuracy": 0.7481
}
```

### Warm eval

```
{
  "cycles": 45033,
  "injected_packets": 10350,
  "delivered_packets": 9925,
  "delivery_ratio": 0.9589,
  "dropped_packets": 425,
  "drop_ratio": 0.0411,
  "mean_latency": 3.1572,
  "mean_route_cost": 0.0289,
  "mean_feedback_award": 0.1373,
  "node_atp_total": 6.0352,
  "exact_matches": 7573,
  "mean_bit_accuracy": 0.763
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
