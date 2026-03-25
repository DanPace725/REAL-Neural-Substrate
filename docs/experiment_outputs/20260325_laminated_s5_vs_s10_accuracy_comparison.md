# Laminated Accuracy Comparison: s5 vs s10

Built from existing `20260325_laminated_*_summary.md` files in `docs/experiment_outputs`.

## Slice-Level Accuracy Comparison

| Benchmark | s5 final_decision | s10 final_decision | s5 best `mean_bit_acc` | s10 best `mean_bit_acc` | delta (s10-s5) | s5 last `mean_bit_acc` | s10 last `mean_bit_acc` | delta (s10-s5) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| B2S1 | continue | continue | 0.6250 | 0.7500 | +0.1250 | 0.5000 | 0.5000 | +0.0000 |
| B2S2 | settle | settle | 1.0000 | 0.7500 | -0.2500 | 1.0000 | 0.2500 | -0.7500 |
| B2S3 | continue | settle | 0.7105 | 1.0000 | +0.2895 | 0.6579 | 1.0000 | +0.3421 |
| B2S4 | continue | continue | 0.9259 | 0.8333 | -0.0926 | 0.9259 | 0.7500 | -0.1759 |
| B2S5 | continue | settle | 0.9409 | 0.9857 | +0.0448 | 0.8796 | 0.9857 | +0.1061 |
| B2S6 | continue | continue | 0.8139 | 0.6648 | -0.1491 | 0.4861 | 0.5000 | +0.0139 |

## Context-Balanced Accuracy Signal (`min_ctx_acc`)

| Benchmark | s5 best `min_ctx_acc` | s10 best `min_ctx_acc` | delta (s10-s5) | s5 last `min_ctx_acc` | s10 last `min_ctx_acc` | delta (s10-s5) |
|---|---:|---:|---:|---:|---:|---:|
| B2S1 | 0.5000 | 0.7500 | +0.2500 | 0.5000 | 0.5000 | +0.0000 |
| B2S2 | 1.0000 | 0.7500 | -0.2500 | 1.0000 | 0.2500 | -0.7500 |
| B2S3 | 0.6154 | 1.0000 | +0.3846 | 0.5000 | 1.0000 | +0.5000 |
| B2S4 | 0.9167 | 0.5833 | -0.3334 | 0.9167 | 0.5000 | -0.4167 |
| B2S5 | 0.9127 | 0.9792 | +0.0665 | 0.7667 | 0.9792 | +0.2125 |
| B2S6 | 0.5370 | 0.6000 | +0.0630 | 0.4505 | 0.4833 | +0.0328 |

## Baseline/Delta Fields Present In Summary Files

These values are present in the s5 summaries; current s10 summaries often omit baseline and delta fields.

| Benchmark | s5 baseline `mean_bit_accuracy` | s10 baseline `mean_bit_accuracy` | s5 reported delta `mean_bit_accuracy` | s10 reported delta `mean_bit_accuracy` |
|---|---:|---:|---:|---:|
| B2S1 | 0.4722 | n/a | 0.0635 | n/a |
| B2S2 | 0.5278 | n/a | 0.2315 | n/a |
| B2S3 | 0.6065 | n/a | 0.0426 | n/a |
| B2S4 | 0.5995 | n/a | 0.0059 | n/a |
| B2S5 | 0.5810 | n/a | 0.2825 | n/a |
| B2S6 | 0.7882 | n/a | -0.1709 | n/a |
