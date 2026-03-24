# Occupancy v3 sweep comparison: fresh vs persistent eval

Compares:

- `v3_best_real_sweep_summary.md` (`fresh_session_eval`)
- `v3_sweep_13_23_37_persistent_eval_summary.md` (`persistent_eval`)

Delta convention in all tables: **persistent - fresh**.

## Aggregate metrics

| Metric | Fresh | Persistent | Delta |
|---|---:|---:|---:|
| mean_train_accuracy | 0.9125 | 0.9125 | +0.0000 |
| mean_warm_accuracy | 0.9734 | 0.9130 | -0.0604 |
| mean_cold_accuracy | 0.9678 | 0.9219 | -0.0459 |
| mean_warm_delivery_ratio | 0.9687 | 0.9483 | -0.0204 |
| mean_cold_delivery_ratio | 0.9773 | 0.9599 | -0.0174 |
| mean_efficiency_ratio | 0.9915 | 0.9683 | -0.0232 |
| mean_session_1_delivery_delta | 0.0000 | 0.0000 | +0.0000 |
| mean_first_episode_delivery_delta | 0.0000 | -0.0153 | -0.0153 |
| mean_first_three_episode_delivery_delta | -0.0112 | -0.0276 | -0.0164 |

## Per-seed summary

| Seed | Metric | Fresh | Persistent | Delta |
|---:|---|---:|---:|---:|
| 13 | train_accuracy | 0.9147 | 0.9147 | +0.0000 |
| 13 | warm_accuracy | 0.9807 | 0.9034 | -0.0773 |
| 13 | cold_accuracy | 0.9686 | 0.9203 | -0.0483 |
| 13 | warm_delivery | 0.9739 | 0.9367 | -0.0372 |
| 13 | cold_delivery | 0.9711 | 0.9643 | -0.0068 |
| 13 | efficiency_ratio | 0.9977 | 0.9519 | -0.0458 |
| 23 | train_accuracy | 0.9104 | 0.9104 | +0.0000 |
| 23 | warm_accuracy | 0.9710 | 0.9203 | -0.0507 |
| 23 | cold_accuracy | 0.9662 | 0.9203 | -0.0459 |
| 23 | warm_delivery | 0.9614 | 0.9557 | -0.0057 |
| 23 | cold_delivery | 0.9816 | 0.9559 | -0.0257 |
| 23 | efficiency_ratio | 0.9837 | 0.9701 | -0.0136 |
| 37 | train_accuracy | 0.9125 | 0.9125 | +0.0000 |
| 37 | warm_accuracy | 0.9686 | 0.9155 | -0.0531 |
| 37 | cold_accuracy | 0.9686 | 0.9251 | -0.0435 |
| 37 | warm_delivery | 0.9707 | 0.9525 | -0.0182 |
| 37 | cold_delivery | 0.9793 | 0.9596 | -0.0197 |
| 37 | efficiency_ratio | 0.9931 | 0.9828 | -0.0103 |

## Best-seed shift

| Criterion | Fresh winner | Persistent winner |
|---|---|---|
| best_seed_by_efficiency_ratio | seed 13 (0.9977) | seed 37 (0.9828) |
| best_seed_by_session_1_delivery_delta | seed 13 (0.0) | seed 13 (0.0) |

## Worker policy notes

| Item | Fresh | Persistent |
|---|---|---|
| eval_mode | `fresh_session_eval` | `persistent_eval` |
| requested_workers | `None` | `15` |
| worker_budget | `15` | `15` |
| seed_workers | `3` | `3` |
| eval_workers_per_seed | `5` | `5` |
| per-seed protocol workers | `{'fresh_session_eval': 5}` | `{'persistent_eval': 2}` |

