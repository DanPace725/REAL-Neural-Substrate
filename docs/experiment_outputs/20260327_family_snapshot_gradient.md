# 2026-03-27 Family Snapshot

Quick summary of the most recent family sweep manifests on `2026-03-27` using the `gradient` regulator.

- Visible families (`A`, `B`, `C`) use the latest `20260327_laminated_*_visible_b6_t08_gradient_seed13.json` family-sweep manifests.
- Hidden family (`HR`) uses the latest `20260327_121210_731243_hidden_regime_*_gradient_seed13.json` family-sweep manifests.
- This snapshot excludes later one-off follow-up runs such as debug-force-growth files and alternate safety-limit reruns like `s50`, `s100`, and `s150`.

## Family Totals

| Family | Settled | Total | Notes |
| --- | ---: | ---: | --- |
| A | 8 | 12 | Strong on `A2-A4`; `A1 task_a` now settles, while `task_b` remains the weakest lane |
| B | 6 | 9 | Mostly healthy, with holdouts on `B2S1 task_c`, `B2S2 task_a`, and `B2S3 task_a` |
| C | 0 | 9 | Latest saved rerun still shows no settled lanes; scores shifted, but the family remains unresolved |
| HR | 5 | 9 | `HR1` and `HR2` are workable; `HR3` remains weak |

## A Family

| Benchmark | Task | Decision | Slices | Final Acc. | Floor Acc. | Manifest |
| --- | --- | --- | ---: | ---: | ---: | --- |
| A1 | task_a | settle | 9 | 0.9615 | 0.9615 | [20260327_laminated_a1_task_a_visible_b6_t08_gradient_seed13.json](./20260327_laminated_a1_task_a_visible_b6_t08_gradient_seed13.json) |
| A1 | task_b | continue | 40 | 0.7200 | 0.4583 | [20260327_laminated_a1_task_b_visible_b6_t08_gradient_seed13.json](./20260327_laminated_a1_task_b_visible_b6_t08_gradient_seed13.json) |
| A1 | task_c | continue | 40 | 0.5521 | 0.0652 | [20260327_laminated_a1_task_c_visible_b6_t08_gradient_seed13.json](./20260327_laminated_a1_task_c_visible_b6_t08_gradient_seed13.json) |
| A2 | task_a | settle | 6 | 1.0000 | 1.0000 | [20260327_laminated_a2_task_a_visible_b6_t08_gradient_seed13.json](./20260327_laminated_a2_task_a_visible_b6_t08_gradient_seed13.json) |
| A2 | task_b | settle | 7 | 1.0000 | 1.0000 | [20260327_laminated_a2_task_b_visible_b6_t08_gradient_seed13.json](./20260327_laminated_a2_task_b_visible_b6_t08_gradient_seed13.json) |
| A2 | task_c | settle | 8 | 0.9310 | 0.9286 | [20260327_laminated_a2_task_c_visible_b6_t08_gradient_seed13.json](./20260327_laminated_a2_task_c_visible_b6_t08_gradient_seed13.json) |
| A3 | task_a | settle | 34 | 0.9200 | 0.8571 | [20260327_laminated_a3_task_a_visible_b6_t08_gradient_seed13.json](./20260327_laminated_a3_task_a_visible_b6_t08_gradient_seed13.json) |
| A3 | task_b | continue | 40 | 0.7656 | 0.5588 | [20260327_laminated_a3_task_b_visible_b6_t08_gradient_seed13.json](./20260327_laminated_a3_task_b_visible_b6_t08_gradient_seed13.json) |
| A3 | task_c | settle | 8 | 0.9375 | 0.9000 | [20260327_laminated_a3_task_c_visible_b6_t08_gradient_seed13.json](./20260327_laminated_a3_task_c_visible_b6_t08_gradient_seed13.json) |
| A4 | task_a | settle | 31 | 0.9808 | 0.9583 | [20260327_laminated_a4_task_a_visible_b6_t08_gradient_seed13.json](./20260327_laminated_a4_task_a_visible_b6_t08_gradient_seed13.json) |
| A4 | task_b | continue | 40 | 0.7419 | 0.5667 | [20260327_laminated_a4_task_b_visible_b6_t08_gradient_seed13.json](./20260327_laminated_a4_task_b_visible_b6_t08_gradient_seed13.json) |
| A4 | task_c | settle | 7 | 0.9545 | 0.9286 | [20260327_laminated_a4_task_c_visible_b6_t08_gradient_seed13.json](./20260327_laminated_a4_task_c_visible_b6_t08_gradient_seed13.json) |

## B Family

| Benchmark | Task | Decision | Slices | Final Acc. | Floor Acc. | Manifest |
| --- | --- | --- | ---: | ---: | ---: | --- |
| B2S1 | task_a | settle | 7 | 0.9038 | 0.8333 | [20260327_laminated_b2s1_task_a_visible_b6_t08_gradient_seed13.json](./20260327_laminated_b2s1_task_a_visible_b6_t08_gradient_seed13.json) |
| B2S1 | task_b | settle | 28 | 0.9423 | 0.9211 | [20260327_laminated_b2s1_task_b_visible_b6_t08_gradient_seed13.json](./20260327_laminated_b2s1_task_b_visible_b6_t08_gradient_seed13.json) |
| B2S1 | task_c | continue | 40 | 0.6833 | 0.0000 | [20260327_laminated_b2s1_task_c_visible_b6_t08_gradient_seed13.json](./20260327_laminated_b2s1_task_c_visible_b6_t08_gradient_seed13.json) |
| B2S2 | task_a | continue | 40 | 0.8438 | 0.5500 | [20260327_laminated_b2s2_task_a_visible_b6_t08_gradient_seed13.json](./20260327_laminated_b2s2_task_a_visible_b6_t08_gradient_seed13.json) |
| B2S2 | task_b | settle | 19 | 1.0000 | 1.0000 | [20260327_laminated_b2s2_task_b_visible_b6_t08_gradient_seed13.json](./20260327_laminated_b2s2_task_b_visible_b6_t08_gradient_seed13.json) |
| B2S2 | task_c | settle | 6 | 1.0000 | 1.0000 | [20260327_laminated_b2s2_task_c_visible_b6_t08_gradient_seed13.json](./20260327_laminated_b2s2_task_c_visible_b6_t08_gradient_seed13.json) |
| B2S3 | task_a | continue | 40 | 0.5323 | 0.5000 | [20260327_laminated_b2s3_task_a_visible_b6_t08_gradient_seed13.json](./20260327_laminated_b2s3_task_a_visible_b6_t08_gradient_seed13.json) |
| B2S3 | task_b | settle | 7 | 0.8462 | 0.8000 | [20260327_laminated_b2s3_task_b_visible_b6_t08_gradient_seed13.json](./20260327_laminated_b2s3_task_b_visible_b6_t08_gradient_seed13.json) |
| B2S3 | task_c | settle | 8 | 0.9231 | 0.8750 | [20260327_laminated_b2s3_task_c_visible_b6_t08_gradient_seed13.json](./20260327_laminated_b2s3_task_c_visible_b6_t08_gradient_seed13.json) |

## C Family

| Benchmark | Task | Decision | Slices | Final Acc. | Floor Acc. | Manifest |
| --- | --- | --- | ---: | ---: | ---: | --- |
| C3S1 | task_a | continue | 40 | 0.5714 | 0.2857 | [20260327_laminated_c3s1_task_a_visible_b6_t08_gradient_seed13.json](./20260327_laminated_c3s1_task_a_visible_b6_t08_gradient_seed13.json) |
| C3S1 | task_b | continue | 40 | 0.7344 | 0.7333 | [20260327_laminated_c3s1_task_b_visible_b6_t08_gradient_seed13.json](./20260327_laminated_c3s1_task_b_visible_b6_t08_gradient_seed13.json) |
| C3S1 | task_c | continue | 40 | 0.5469 | 0.3529 | [20260327_laminated_c3s1_task_c_visible_b6_t08_gradient_seed13.json](./20260327_laminated_c3s1_task_c_visible_b6_t08_gradient_seed13.json) |
| C3S2 | task_a | continue | 40 | 0.6970 | 0.6765 | [20260327_laminated_c3s2_task_a_visible_b6_t08_gradient_seed13.json](./20260327_laminated_c3s2_task_a_visible_b6_t08_gradient_seed13.json) |
| C3S2 | task_b | continue | 40 | 0.6167 | 0.5000 | [20260327_laminated_c3s2_task_b_visible_b6_t08_gradient_seed13.json](./20260327_laminated_c3s2_task_b_visible_b6_t08_gradient_seed13.json) |
| C3S2 | task_c | continue | 40 | 0.5667 | 0.4286 | [20260327_laminated_c3s2_task_c_visible_b6_t08_gradient_seed13.json](./20260327_laminated_c3s2_task_c_visible_b6_t08_gradient_seed13.json) |
| C3S3 | task_a | continue | 40 | 0.4787 | 0.3200 | [20260327_laminated_c3s3_task_a_visible_b6_t08_gradient_seed13.json](./20260327_laminated_c3s3_task_a_visible_b6_t08_gradient_seed13.json) |
| C3S3 | task_b | continue | 40 | 0.4839 | 0.4643 | [20260327_laminated_c3s3_task_b_visible_b6_t08_gradient_seed13.json](./20260327_laminated_c3s3_task_b_visible_b6_t08_gradient_seed13.json) |
| C3S3 | task_c | continue | 40 | 0.6053 | 0.5000 | [20260327_laminated_c3s3_task_c_visible_b6_t08_gradient_seed13.json](./20260327_laminated_c3s3_task_c_visible_b6_t08_gradient_seed13.json) |

## HR Family

| Benchmark | Task | Decision | Slices | Final Acc. | Floor Acc. | Manifest |
| --- | --- | --- | ---: | ---: | ---: | --- |
| HR1 | task_a | settle | 24 | 0.8333 | 0.8333 | [20260327_121210_731243_hidden_regime_hr1_task_a_hidden_self_selected_b6_s40_t08_gradient_seed13.json](./20260327_121210_731243_hidden_regime_hr1_task_a_hidden_self_selected_b6_s40_t08_gradient_seed13.json) |
| HR1 | task_b | settle | 30 | 1.0000 | 1.0000 | [20260327_121210_731243_hidden_regime_hr1_task_b_hidden_self_selected_b6_s40_t08_gradient_seed13.json](./20260327_121210_731243_hidden_regime_hr1_task_b_hidden_self_selected_b6_s40_t08_gradient_seed13.json) |
| HR1 | task_c | continue | 40 | 0.4655 | 0.4655 | [20260327_121210_731243_hidden_regime_hr1_task_c_hidden_self_selected_b6_s40_t08_gradient_seed13.json](./20260327_121210_731243_hidden_regime_hr1_task_c_hidden_self_selected_b6_s40_t08_gradient_seed13.json) |
| HR2 | task_a | settle | 31 | 1.0000 | 1.0000 | [20260327_121210_731243_hidden_regime_hr2_task_a_hidden_self_selected_b6_s40_t08_gradient_seed13.json](./20260327_121210_731243_hidden_regime_hr2_task_a_hidden_self_selected_b6_s40_t08_gradient_seed13.json) |
| HR2 | task_b | settle | 14 | 1.0000 | 1.0000 | [20260327_121210_731243_hidden_regime_hr2_task_b_hidden_self_selected_b6_s40_t08_gradient_seed13.json](./20260327_121210_731243_hidden_regime_hr2_task_b_hidden_self_selected_b6_s40_t08_gradient_seed13.json) |
| HR2 | task_c | settle | 5 | 1.0000 | 1.0000 | [20260327_121210_731243_hidden_regime_hr2_task_c_hidden_self_selected_b6_s40_t08_gradient_seed13.json](./20260327_121210_731243_hidden_regime_hr2_task_c_hidden_self_selected_b6_s40_t08_gradient_seed13.json) |
| HR3 | task_a | continue | 40 | 0.5469 | 0.5469 | [20260327_121210_731243_hidden_regime_hr3_task_a_hidden_self_selected_b6_s40_t08_gradient_seed13.json](./20260327_121210_731243_hidden_regime_hr3_task_a_hidden_self_selected_b6_s40_t08_gradient_seed13.json) |
| HR3 | task_b | continue | 40 | 0.6094 | 0.6094 | [20260327_121210_731243_hidden_regime_hr3_task_b_hidden_self_selected_b6_s40_t08_gradient_seed13.json](./20260327_121210_731243_hidden_regime_hr3_task_b_hidden_self_selected_b6_s40_t08_gradient_seed13.json) |
| HR3 | task_c | continue | 40 | 0.5893 | 0.5893 | [20260327_121210_731243_hidden_regime_hr3_task_c_hidden_self_selected_b6_s40_t08_gradient_seed13.json](./20260327_121210_731243_hidden_regime_hr3_task_c_hidden_self_selected_b6_s40_t08_gradient_seed13.json) |
