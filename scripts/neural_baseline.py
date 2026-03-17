"""
neural_baseline.py - sample-efficiency comparison for Phase 8 CVT-1 tasks.

Implements minimal neural baselines trained online (one example at a time,
matching REAL's learning paradigm) on the CVT-1 workloads.

Usage
-----
    python -m scripts.neural_baseline
    python -m scripts.neural_baseline --seeds 5
    python -m scripts.neural_baseline --task task_b
    python -m scripts.neural_baseline --compare-real
"""

from __future__ import annotations

import argparse
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional

from scripts.experiment_manifest import build_run_manifest, write_run_manifest
from scripts.neural_baseline_data import (
    BIT_ACCURACY_THRESHOLD,
    CRITERION_WINDOW,
    EXACT_THRESHOLD,
    SignalExample,
    _bit_accuracy,
    _criterion_reached,
    _exact_match,
    cvt1_stage1_examples,
    cvt1_stage3_examples,
    examples_to_criterion,
    rolling_window_metrics,
)
from scripts.neural_baseline_models import (
    BaselineResult,
    ElmanRNN,
    MLP,
    aggregate_results,
    run_mlp_explicit,
    run_mlp_latent,
    run_rnn_latent,
    scan_epochs_to_criterion,
)
from scripts.neural_baseline_real import run_real_for_comparison


def _fmt_etc(value: Optional[int]) -> str:
    return str(value) if value is not None else "not reached"


def _print_row(label: str, width: int, *values: object) -> None:
    print(f"  {label:<{width}}", *[f"{value:>14}" for value in values])


def _task_label(task_id: str) -> str:
    suffix = task_id.split("_")[-1].upper()
    return f"Task {suffix}"


def _serialize_variant(results: List[BaselineResult]) -> List[Dict[str, object]]:
    return [
        {
            "seed": result.seed,
            "exact_matches": result.exact_matches,
            "mean_bit_accuracy": result.mean_bit_accuracy,
            "examples_to_criterion": result.examples_to_criterion,
            "criterion_reached": result.criterion_reached,
        }
        for result in results
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 8 neural baseline comparison")
    parser.add_argument("--seeds", type=int, default=1, help="number of random seeds")
    parser.add_argument("--task", default="task_a", choices=["task_a", "task_b", "task_c"])
    parser.add_argument("--max-epochs", type=int, default=20, help="max epochs for epoch-scan mode")
    parser.add_argument("--compare-real", action="store_true", help="also run the REAL system")
    parser.add_argument(
        "--epoch-scan",
        action="store_true",
        help="scan across epochs to find examples-to-criterion instead of single-pass",
    )
    parser.add_argument(
        "--scale",
        action="store_true",
        help="run with a 30-hidden-unit network on a 108-packet dataset",
    )
    parser.add_argument(
        "--transfer",
        action="store_true",
        help="evaluate Task A -> selected task transfer instead of cold-start",
    )
    parser.add_argument(
        "--morphogenesis",
        action="store_true",
        help="enable dynamic topology for the REAL comparison",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="path to save JSON experiment manifest",
    )
    args = parser.parse_args()

    task_id = args.task
    if args.scale:
        train_examples = cvt1_stage3_examples("task_a")
        examples = cvt1_stage3_examples(task_id)
        mlp_hidden = 30
        rnn_hidden = 30
    else:
        train_examples = cvt1_stage1_examples("task_a")
        examples = cvt1_stage1_examples(task_id)
        mlp_hidden = 8
        rnn_hidden = 12
    signal_length = len(examples)

    print("\nPhase 8 - Neural Baseline Comparison")
    mode_str = (
        f"{_task_label('task_a')} -> {_task_label(task_id)} Transfer"
        if args.transfer
        else "Cold-start"
    )
    morph_str = " (REAL morphogenesis enabled)" if args.compare_real and args.morphogenesis else ""
    print(f"Mode: {mode_str}{morph_str}")
    print(f"Task: {task_id}  |  Signal length: {signal_length} examples  |  Seeds: {args.seeds}")
    print(f"Criterion: >={EXACT_THRESHOLD*100:.0f}% exact in rolling {CRITERION_WINDOW}-window")
    print()

    all_by_variant: Dict[str, List[BaselineResult]] = {
        "mlp-explicit": [],
        "mlp-latent": [],
        "rnn-latent": [],
    }
    real_results: List[Dict[str, object]] = []

    for seed in range(args.seeds):
        train_set = train_examples if args.transfer else None
        if not args.epoch_scan:
            all_by_variant["mlp-explicit"].append(
                run_mlp_explicit(examples, seed=seed, hidden=mlp_hidden, train_examples=train_set)
            )
            all_by_variant["mlp-latent"].append(
                run_mlp_latent(examples, seed=seed, hidden=mlp_hidden, train_examples=train_set)
            )
            all_by_variant["rnn-latent"].append(
                run_rnn_latent(examples, seed=seed, hidden=rnn_hidden, train_examples=train_set)
            )
        else:
            epoch_map = scan_epochs_to_criterion(
                examples,
                seed=seed,
                max_epochs=args.max_epochs,
                mlp_hidden=mlp_hidden,
                rnn_hidden=rnn_hidden,
                train_examples=train_set,
            )
            for variant, epoch_found in epoch_map.items():
                etc = epoch_found * signal_length if epoch_found is not None else None
                all_by_variant[variant].append(
                    BaselineResult(
                        variant=variant,
                        seed=seed,
                        task_id=task_id,
                        exact_matches=None,
                        mean_bit_accuracy=None,
                        examples_to_criterion=etc,
                        criterion_reached=etc is not None,
                        per_example_exact=[],
                        per_example_accuracy=[],
                        losses=[],
                    )
                )

        if args.compare_real:
            real = run_real_for_comparison(
                task_id,
                seed=seed,
                scale_mode=args.scale,
                transfer_mode=args.transfer,
                morphogenesis_enabled=args.morphogenesis,
            )
            if real is not None:
                real_results.append(real)
            elif seed == 0:
                print("  [note] phase8 package not found; REAL comparison skipped")

    col_w = 20
    header_variants = list(all_by_variant.keys())
    real_header_label = "REAL Phase 8"
    if args.compare_real and real_results:
        header_variants.append(real_header_label)

    print("  " + "-" * (col_w + 15 * len(header_variants)))
    _print_row("Variant", col_w, *[variant.upper() for variant in header_variants])
    print("  " + "-" * (col_w + 15 * len(header_variants)))

    aggs = {variant: aggregate_results(results) for variant, results in all_by_variant.items()}
    real_agg: Dict[str, object] = {}
    if args.compare_real and real_results:
        real_etc_vals = [
            result["examples_to_criterion"]
            for result in real_results
            if result.get("examples_to_criterion") is not None
        ]
        real_agg = {
            "mean_exact_matches": mean(float(result["exact_matches"]) for result in real_results),
            "mean_bit_accuracy": mean(float(result["mean_bit_accuracy"]) for result in real_results),
            "criterion_rate": sum(
                1.0 for result in real_results if result.get("criterion_reached", False)
            )
            / max(len(real_results), 1),
            "mean_examples_to_criterion": mean(real_etc_vals) if real_etc_vals else None,
        }

    if not args.epoch_scan:
        def _row(label: str, key: str, fmt=str) -> None:
            values = [fmt(aggs[variant].get(key, "-")) for variant in all_by_variant]
            if args.compare_real and real_results:
                values.append(fmt(real_agg.get(key, "-")))
            _print_row(label, col_w, *values)

        _row(
            "Exact matches (mean)",
            "mean_exact_matches",
            lambda value: f"{value:.1f}" if isinstance(value, float) else str(value),
        )
        _row(
            "Mean bit accuracy",
            "mean_bit_accuracy",
            lambda value: f"{value:.3f}" if isinstance(value, float) else str(value),
        )
        _row(
            "Criterion rate",
            "criterion_rate",
            lambda value: f"{value*100:.0f}%" if isinstance(value, float) else str(value),
        )
        _row(
            "ETC (mean examples)",
            "mean_examples_to_criterion",
            lambda value: _fmt_etc(int(value)) if isinstance(value, float) else _fmt_etc(value),
        )
    else:
        for variant, results in all_by_variant.items():
            etc_vals = [
                result.examples_to_criterion
                for result in results
                if result.criterion_reached and result.examples_to_criterion is not None
            ]
            crit_rate = sum(1 for result in results if result.criterion_reached) / max(len(results), 1)
            print(
                f"  {variant:<{col_w}} criterion_rate={crit_rate*100:.0f}%  "
                f"ETC={_fmt_etc(int(mean(etc_vals))) if etc_vals else 'not reached'}"
            )

        if args.compare_real and real_agg:
            crit_rate = real_agg.get("criterion_rate", 0.0)
            etc_val = real_agg.get("mean_examples_to_criterion")
            print(
                f"  {real_header_label:<{col_w}} criterion_rate={crit_rate*100:.0f}%  "
                f"ETC={_fmt_etc(int(etc_val)) if etc_val is not None else 'not reached'}"
            )

    print("  " + "-" * (col_w + 15 * len(header_variants)))

    if not args.epoch_scan and args.seeds == 1:
        print()
        print("  Per-example detail (seed 0):")
        print(f"  {'#':<4} {'input':>8} {'ctx':>4} {'target':>8}", "  mlp-expl  mlp-lat  rnn-lat")
        for index, example in enumerate(examples):
            input_bits = "".join(str(bit) for bit in example.input_bits)
            target_bits = "".join(str(bit) for bit in example.target_bits)
            row_parts = [f"  {index+1:<4} {input_bits:>8} {example.context_bit:>4} {target_bits:>8}"]
            for variant in all_by_variant:
                result_list = all_by_variant[variant]
                if result_list and index < len(result_list[0].per_example_exact):
                    mark = "Y" if result_list[0].per_example_exact[index] else "."
                    acc = result_list[0].per_example_accuracy[index]
                    row_parts.append(f"  {mark} {acc:.2f}")
            print("".join(row_parts))

    print()
    print("Notes:")
    print("  mlp-explicit : 5 inputs (bits + context), upper-bound Stage 1 baseline")
    print("  mlp-latent   : 4 inputs (bits only), stateless - cannot track sequence context")
    print("  rnn-latent   : 4 inputs, Elman RNN - hidden state implicitly tracks parity context")
    print("  REAL         : Phase 8 native substrate - local metabolic learning, no gradients")
    print()
    print("The key comparison is examples-to-criterion (ETC):")
    print("  - mlp-latent cannot reliably reach criterion on 18 examples (bimodal mapping)")
    print("  - rnn-latent can track context but needs more signal than REAL's substrate memory")
    print("  - REAL warm-full carryover reduces ETC further via substrate transfer")
    print()

    if args.output:
        result_dict = {
            "neural_variants": {
                variant: _serialize_variant(results) for variant, results in all_by_variant.items()
            },
            "neural_aggregates": aggs,
            "real_results": real_results if real_results else None,
            "real_aggregate": real_agg if real_results else None,
        }
        scenarios = [f"cvt1_{task_id}_{'scale' if args.scale else 'stage1'}"]
        if args.transfer:
            scenarios.insert(0, f"cvt1_task_a_{'scale' if args.scale else 'stage1'}")

        manifest = build_run_manifest(
            harness="neural_baseline_extended",
            seeds=list(range(args.seeds)),
            scenarios=scenarios,
            result=result_dict,
            metadata={
                "transfer": args.transfer,
                "morphogenesis": args.morphogenesis,
                "scale": args.scale,
                "epoch_scan": args.epoch_scan,
                "max_epochs": args.max_epochs,
            },
        )
        write_run_manifest(Path(args.output), manifest)
        print(f"Saved run manifest to {args.output}")


__all__ = [
    "BIT_ACCURACY_THRESHOLD",
    "BaselineResult",
    "CRITERION_WINDOW",
    "EXACT_THRESHOLD",
    "ElmanRNN",
    "MLP",
    "SignalExample",
    "_bit_accuracy",
    "_criterion_reached",
    "_exact_match",
    "aggregate_results",
    "cvt1_stage1_examples",
    "cvt1_stage3_examples",
    "examples_to_criterion",
    "main",
    "rolling_window_metrics",
    "run_mlp_explicit",
    "run_mlp_latent",
    "run_real_for_comparison",
    "run_rnn_latent",
    "scan_epochs_to_criterion",
]


if __name__ == "__main__":
    main()
