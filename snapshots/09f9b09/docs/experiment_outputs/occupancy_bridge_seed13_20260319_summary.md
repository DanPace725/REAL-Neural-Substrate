# 2026-03-19 1324 - occupancy baseline comparison

**Timestamp:** `2026-03-19T20:24:06.647080Z`  
**Harness:** `occupancy_baseline_comparison`  
**Seeds:** [13]  
**Scenarios:** ['synth_v1_default']

## Dataset

| Property | Value |
|---|---|
| Rows | 1344 |
| Windowed examples | 1340 |
| Train examples | 1072 |
| Test examples | 268 |
| Input dim | 25 |
| Window size | 5 |
| Train fraction | 0.8 |
| Normalize | True |

## Baseline (MLP)

| Property | Value |
|---|---|
| Hidden size | 12 |
| Learning rate | 0.05 |
| Epochs | 60 |
| Seed | 0 |
| Final train loss | 0.018626 |

**Test metrics:**

| Metric | Value |
|---|---|
| accuracy | 0.9851 |
| precision | 0.9455 |
| recall | 0.9811 |
| f1 | 0.9630 |

Confusion: TP=52  TN=212  FP=3  FN=1

## REAL Run — selector_seed=13

**Config:**

| Param | Value |
|---|---|
| feedback_amount | 0.18 |
| packet_ttl | 8 |
| forward_drain_cycles | 16 |
| feedback_drain_cycles | 4 |
| train_episodes | 1072 |
| eval_episodes | 268 |

**Topology** (9 nodes, source=`sensor_hub`, sink=`sink`)

- `sensor_temperature` -> `decision_empty`, `decision_occupied`
- `sensor_humidity` -> `decision_empty`, `decision_occupied`
- `sensor_light` -> `decision_empty`, `decision_occupied`
- `sensor_co2` -> `decision_empty`, `decision_occupied`
- `sensor_humidity_ratio` -> `decision_empty`, `decision_occupied`
- `decision_empty` -> `sink`
- `decision_occupied` -> `sink`

### Training (1072 episodes)

| Metric | Value | vs Baseline |
|---|---|---|
| accuracy | 0.9254 | -5.97% |
| precision | 0.8852 | -6.02% |
| recall | 0.8571 | -12.40% |
| f1 | 0.8710 | -9.20% |

| Stat | Value |
|---|---|
| mean_delivered_packets | 24.0382 |
| mean_dropped_packets | 0.9618 |
| mean_feedback_events | 19.9235 |
| mean_feedback_total | 3.5862 |
| occupied_prediction_rate | 0.2845 |

### Evaluation (268 episodes)

| Metric | Value | vs Baseline |
|---|---|---|
| accuracy | 0.7724 | -21.27% |
| precision | 0.1000 | -84.55% |
| recall | 0.0189 | -96.23% |
| f1 | 0.0317 | -93.12% |

| Stat | Value |
|---|---|
| mean_delivered_packets | 7.653 |
| mean_dropped_packets | 17.347 |
| mean_feedback_events | 0.0 |
| mean_feedback_total | 0.0 |
| occupied_prediction_rate | 0.0373 |

**Delta vs baseline (eval):**

| Metric | Delta |
|---|---|
| accuracy | -21.27% |
| precision | -84.55% |
| recall | -96.23% |
| f1 | -93.12% |

### Substrate System Stats

| Stat | Value |
|---|---|
| cycles | 43754 |
| injected_packets | 33500 |
| delivered_packets | 27820 |
| delivery_ratio | 0.8304 |
| dropped_packets | 5680 |
| drop_ratio | 0.1696 |
| mean_latency | 2.2467 |
| mean_route_cost | 0.0378 |
| mean_feedback_award | 0.1382 |
| node_atp_total | 1.3279 |
| exact_matches | 22484 |
| mean_bit_accuracy | 0.8082 |

## Aggregate (all seeds)

Seed count: 1

**Mean REAL eval metrics:**

| Metric | Value | vs Baseline |
|---|---|---|
| accuracy | 0.7724 | -21.27% |
| precision | 0.1000 | -84.55% |
| recall | 0.0189 | -96.22% |
| f1 | 0.0317 | -93.13% |

**Mean delta vs baseline:**

| Metric | Delta |
|---|---|
| accuracy | -21.27% |
| precision | -84.55% |
| recall | -96.23% |
| f1 | -93.12% |

| Stat | Value |
|---|---|
| mean_real_train_accuracy | 0.9254 |
| mean_real_eval_delivered_packets | 7.653 |
| mean_real_train_feedback_events | 19.9235 |
