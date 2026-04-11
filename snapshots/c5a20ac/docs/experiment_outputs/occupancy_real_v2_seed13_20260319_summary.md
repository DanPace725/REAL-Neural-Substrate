# REAL Occupancy v2 — seed 13

**Timestamp:** `2026-03-19T23:12:52Z`  
**Selector seed:** 13  
**Elapsed:** 723.8s  
**Conditions:** 4

## Aggregate Comparison

| Condition | Tr Acc | Ev Acc | Ev F1 | Ev Dropped | Ev Fdbk Events |
|---|---:|---:|---:|---:|---:|
| v2_live | 0.874 | 0.892 | 0.7477 | 4.208 | 13.916 |
| v2_carryover | 0.874 | 0.9 | 0.7573 | 4.228 | 14.18 |
| v2_live_ctx_co2_high | 0.89 | 0.9 | 0.7664 | 0.724 | 18.048 |
| v2_carry_ctx_co2_high | 0.89 | 0.896 | 0.7636 | 0.76 | 18.1 |

## Condition: v2_live

*Eval feedback on, continuous, no context*

**Config:**

| Param | Value |
|---|---|
| eval_feedback_fraction | 1.0 |
| carryover_mode | continuous |
| context_bit_source | none |
| feedback_amount | 0.18 |
| packet_ttl | 8 |
| forward_drain_cycles | 16 |
| feedback_drain_cycles | 4 |
| train_episodes | 500 |
| eval_episodes  | 250 |
| co2_training_median | -0.260971 |

**Training metrics** (500 episodes):

| Metric | Value |
|---|---|
| accuracy | 0.8740 |
| precision | 0.8356 |
| recall | 0.7578 |
| f1 | 0.7948 |

- **mean_delivered_packets**: 21.318
- **mean_dropped_packets**: 3.682
- **mean_feedback_events**: 14.66
- **occupied_prediction_rate**: 0.292

**Evaluation metrics** (250 episodes):

| Metric | Value |
|---|---|
| accuracy | 0.8920 |
| precision | 0.7407 |
| recall | 0.7547 |
| f1 | 0.7477 |

- **mean_delivered_packets**: 20.792
- **mean_dropped_packets**: 4.208
- **mean_feedback_events**: 13.916
- **occupied_prediction_rate**: 0.216

**System summary:**

| Metric | Value |
|---|---|
| cycles | 30249.0000 |
| injected_packets | 18750.0000 |
| delivered_packets | 15857.0000 |
| delivery_ratio | 0.8457 |
| drop_ratio | 0.1543 |
| mean_latency | 2.9224 |
| mean_route_cost | 0.0303 |
| mean_feedback_award | 0.1227 |
| node_atp_total | 4.6870 |

## Condition: v2_carryover

*Eval feedback on, fresh substrate carryover, no context*

**Config:**

| Param | Value |
|---|---|
| eval_feedback_fraction | 1.0 |
| carryover_mode | fresh_eval |
| context_bit_source | none |
| feedback_amount | 0.18 |
| packet_ttl | 8 |
| forward_drain_cycles | 16 |
| feedback_drain_cycles | 4 |
| train_episodes | 500 |
| eval_episodes  | 250 |
| co2_training_median | -0.260971 |

**Training metrics** (500 episodes):

| Metric | Value |
|---|---|
| accuracy | 0.8740 |
| precision | 0.8356 |
| recall | 0.7578 |
| f1 | 0.7948 |

- **mean_delivered_packets**: 21.318
- **mean_dropped_packets**: 3.682
- **mean_feedback_events**: 14.66
- **occupied_prediction_rate**: 0.292

**Evaluation metrics** (250 episodes):

| Metric | Value |
|---|---|
| accuracy | 0.9000 |
| precision | 0.7800 |
| recall | 0.7358 |
| f1 | 0.7573 |

- **mean_delivered_packets**: 20.772
- **mean_dropped_packets**: 4.228
- **mean_feedback_events**: 14.18
- **occupied_prediction_rate**: 0.2

**System summary:**

| Metric | Value |
|---|---|
| cycles | 30243.0000 |
| injected_packets | 6250.0000 |
| delivered_packets | 5193.0000 |
| delivery_ratio | 0.8309 |
| drop_ratio | 0.1691 |
| mean_latency | 2.8448 |
| mean_route_cost | 0.0296 |
| mean_feedback_award | 0.1229 |
| node_atp_total | 5.3208 |

## Condition: v2_live_ctx_co2_high

*Eval feedback on, continuous, context=co2_high*

**Config:**

| Param | Value |
|---|---|
| eval_feedback_fraction | 1.0 |
| carryover_mode | continuous |
| context_bit_source | co2_high |
| feedback_amount | 0.18 |
| packet_ttl | 8 |
| forward_drain_cycles | 16 |
| feedback_drain_cycles | 4 |
| train_episodes | 500 |
| eval_episodes  | 250 |
| co2_training_median | -0.260971 |

**Training metrics** (500 episodes):

| Metric | Value |
|---|---|
| accuracy | 0.8900 |
| precision | 0.8193 |
| recall | 0.8447 |
| f1 | 0.8318 |

- **mean_delivered_packets**: 24.518
- **mean_dropped_packets**: 0.482
- **mean_feedback_events**: 18.026
- **occupied_prediction_rate**: 0.332

**Evaluation metrics** (250 episodes):

| Metric | Value |
|---|---|
| accuracy | 0.9000 |
| precision | 0.7593 |
| recall | 0.7736 |
| f1 | 0.7664 |

- **mean_delivered_packets**: 24.276
- **mean_dropped_packets**: 0.724
- **mean_feedback_events**: 18.048
- **occupied_prediction_rate**: 0.216

**System summary:**

| Metric | Value |
|---|---|
| cycles | 28064.0000 |
| injected_packets | 18750.0000 |
| delivered_packets | 18328.0000 |
| delivery_ratio | 0.9775 |
| drop_ratio | 0.0225 |
| mean_latency | 3.3774 |
| mean_route_cost | 0.0277 |
| mean_feedback_award | 0.1328 |
| node_atp_total | 6.0647 |

## Condition: v2_carry_ctx_co2_high

*Eval feedback on, fresh carryover, context=co2_high*

**Config:**

| Param | Value |
|---|---|
| eval_feedback_fraction | 1.0 |
| carryover_mode | fresh_eval |
| context_bit_source | co2_high |
| feedback_amount | 0.18 |
| packet_ttl | 8 |
| forward_drain_cycles | 16 |
| feedback_drain_cycles | 4 |
| train_episodes | 500 |
| eval_episodes  | 250 |
| co2_training_median | -0.260971 |

**Training metrics** (500 episodes):

| Metric | Value |
|---|---|
| accuracy | 0.8900 |
| precision | 0.8193 |
| recall | 0.8447 |
| f1 | 0.8318 |

- **mean_delivered_packets**: 24.518
- **mean_dropped_packets**: 0.482
- **mean_feedback_events**: 18.026
- **occupied_prediction_rate**: 0.332

**Evaluation metrics** (250 episodes):

| Metric | Value |
|---|---|
| accuracy | 0.8960 |
| precision | 0.7368 |
| recall | 0.7925 |
| f1 | 0.7636 |

- **mean_delivered_packets**: 24.24
- **mean_dropped_packets**: 0.76
- **mean_feedback_events**: 18.1
- **occupied_prediction_rate**: 0.228

**System summary:**

| Metric | Value |
|---|---|
| cycles | 27970.0000 |
| injected_packets | 6250.0000 |
| delivered_packets | 6060.0000 |
| delivery_ratio | 0.9696 |
| drop_ratio | 0.0304 |
| mean_latency | 3.3012 |
| mean_route_cost | 0.0278 |
| mean_feedback_award | 0.1344 |
| node_atp_total | 6.0422 |
