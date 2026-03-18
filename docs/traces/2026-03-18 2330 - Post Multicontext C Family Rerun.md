# 2026-03-18 2330 - Post Multicontext C Family Rerun

## Scope

This trace records the first benchmark rerun after the latent-context generalization work.

Artifacts produced:

- `docs/experiment_outputs/c_family_real_diagnostic_c3_c4_seed13_postmulticontext_cold_20260318.json`
- `docs/experiment_outputs/c_family_real_diagnostic_c3_seed13_postmulticontext_20260318.json`

The full transfer-inclusive `C3+C4` run was attempted twice and exceeded the session timeout budget, so this trace covers:

- cold-start `C3+C4`, seed `13`
- transfer-inclusive `C3`, seed `13`
- original `task_a` and `task_b` smoke runs

## Backward-Compatibility Check

The original A/B scenarios still ran successfully after the latent generalization:

- `cvt1_task_a_stage1`: cold exact `8`, warm full `10`, warm substrate-only `12`
- `cvt1_task_b_stage1`: cold exact `1`, warm full `9`, warm substrate-only `9`

So the change did not break the original two-context workloads.

## Cold-Start `C3` / `C4` Result

Visible modes were unchanged.

That is important: the rerun confirms the new behavior is isolated to the latent path.

### `C3` cold deltas vs pre-multicontext postfix run

- `fixed-visible`: exact `0.2037 -> 0.2037`, bit `0.5031 -> 0.5031`
- `fixed-latent`: exact `0.2562 -> 0.1945`, bit `0.5293 -> 0.5231`, criterion `0.3333 -> 0.0000`
- `growth-visible`: exact `0.1790 -> 0.1790`, bit `0.4876 -> 0.4876`
- `growth-latent`: exact `0.2346 -> 0.2191`, bit `0.5015 -> 0.5185`

The biggest regression was `fixed-latent`, especially on `task_c`:

- `task_c fixed-latent`: exact `0.3148 -> 0.1852`, bit `0.5787 -> 0.5139`, criterion `1.0 -> 0.0`

### `C4` cold deltas vs pre-multicontext postfix run

- `fixed-visible`: exact `0.1728 -> 0.1728`, bit `0.5116 -> 0.5116`
- `fixed-latent`: exact `0.2099 -> 0.1821`, bit `0.5193 -> 0.4961`
- `growth-visible`: exact `0.1636 -> 0.1636`, bit `0.4954 -> 0.4954`
- `growth-latent`: exact `0.1621 -> 0.1682`, bit `0.4985 -> 0.4923`

So the 4-state latent path did **not** produce a clean cold-start lift on the hard C points.

## `C3` Transfer Result

Transfer was mixed rather than uniformly improved.

### `fixed-latent`

- `task_b`: exact `0.3241 -> 0.1296`, bit `0.6019 -> 0.4630`
- `task_c`: exact `0.2593 -> 0.1574`, bit `0.5093 -> 0.4722`

### `growth-latent`

- `task_b`: exact `0.1759 -> 0.2685`, bit `0.5139 -> 0.5509`
- `task_c`: exact `0.1574 -> 0.1389`, bit `0.4954 -> 0.4630`

So the new latent path helps one slice (`growth-latent -> task_b`) but hurts the strongest previous latent path (`fixed-latent`) on both transfer targets.

## Current Read

The result is now clearer:

1. the old binary context bottleneck was real and needed to be removed
2. but simply exposing 4 latent states is not enough
3. the latent confidence/promotion system is still tuned for binary competition

The most likely issue is that the current confidence metric:

- uses `(top_context - runner_up) / total_evidence`
- still applies the old binary thresholds (`0.55` effective, `0.78` promotion-ready)

Once evidence is distributed across 4 states instead of 2, the dominant context becomes harder to promote under the same thresholds. That would directly hurt:

- `fixed-latent` cold performance
- `fixed-latent` transfer, where strong latent commitment used to be the advantage

This interpretation also matches the rerun pattern:

- visible modes are unchanged
- latent modes move, but not always upward
- the strongest regression is specifically the old latent winner

## Recommended Next Step

Before broader reruns, inspect and retune latent commitment for cardinality-aware contexts.

Concretely:

1. make effective/promotion thresholds depend on the number of candidate latent states
2. log latent estimate availability and promotion-ready frequency on `C3 task_b/task_c`
3. rerun `C3` first after that threshold change before spending another long run on `C4`
