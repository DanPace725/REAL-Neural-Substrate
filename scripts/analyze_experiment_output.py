"""
analyze_experiment_output.py
----------------------------
Quick analysis of occupancy bridge (and similar) experiment JSON outputs.

Usage:
    python -m scripts.analyze_experiment_output <path_to_json>
    python -m scripts.analyze_experiment_output <path_to_json> --rolling 50
    python -m scripts.analyze_experiment_output <path_to_json> --no-plots
    python -m scripts.analyze_experiment_output <path_to_json> --seed 13
    python -m scripts.analyze_experiment_output <path_to_json> --summary
    python -m scripts.analyze_experiment_output <path_to_json> --summary path/to/output.md

Produces:
    - A printed summary of baseline vs REAL metrics per seed
    - Rolling accuracy curves for train and eval phases
    - Packet delivery / drop statistics
    - Feedback dynamics over training
    - Confidence distribution histogram

V3 occupancy (run_occupancy_real_v3 JSON):
    python -m scripts.analyze_experiment_output docs/experiment_outputs/v3_train50_seed13.json
    python -m scripts.analyze_experiment_output path/to/v3.json --no-plots
    python -m scripts.analyze_experiment_output path/to/v3.json --summary
"""

import argparse
import json
import sys
from pathlib import Path

# Windows charmap safety — force UTF-8 output whether or not we're piped
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Optional matplotlib — degrade gracefully if not installed
# ---------------------------------------------------------------------------
try:
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    HAS_PLT = True
except ImportError:
    HAS_PLT = False
    print("[warn] matplotlib not found — text summary only. Install with: pip install matplotlib")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(value, width=8, decimals=4):
    """Format a float for aligned column display."""
    if value is None:
        return "-".rjust(width)
    return f"{value:.{decimals}f}".rjust(width)


def _pct(value):
    if value is None:
        return "   -   "
    sign = "+" if value >= 0 else ""
    return f"{sign}{value * 100:.2f}%"


def print_header(title):
    width = 72
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def print_metrics_table(label, metrics, ref=None):
    """Print a metrics block with an optional delta column against ref."""
    cols = ["accuracy", "precision", "recall", "f1"]
    header = f"  {'metric':<12}" + "".join(f"{c:>10}" for c in cols)
    if ref:
        header += "   (vs baseline)"
    print(header)
    print("  " + "-" * (len(header) - 2))

    row = f"  {label:<12}" + "".join(_fmt(metrics.get(c)) for c in cols)
    if ref:
        deltas = "  " + "  ".join(
            _pct(metrics.get(c, 0) - ref.get(c, 0)) for c in cols
        )
        row += deltas
    print(row)


def rolling_mean(values, window):
    out = []
    for i in range(len(values)):
        chunk = values[max(0, i - window + 1): i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def analyze(data, args):
    title = data.get("title", "Unknown experiment")
    timestamp = data.get("timestamp", "?")
    harness = data.get("harness", "?")
    seeds = data.get("seeds", [])
    scenarios = data.get("scenarios", [])

    result = data.get("result", {})
    baseline = result.get("baseline", {})
    runs = result.get("runs", [])
    aggregate = result.get("aggregate", {})

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    print_header(f"{title}  [{timestamp}]")
    print(f"  harness   : {harness}")
    print(f"  seeds     : {seeds}")
    print(f"  scenarios : {scenarios}")

    # Dataset info from baseline (or first run)
    b_cfg = baseline.get("config", {})
    b_rows = baseline.get("dataset_rows")
    b_train = baseline.get("train_examples")
    b_test = baseline.get("test_examples")
    print(f"\n  Dataset   : {b_rows} rows  ->  train={b_train}  test={b_test}")
    print(f"  window_size={b_cfg.get('window_size')}  "
          f"normalize={b_cfg.get('normalize')}  "
          f"train_fraction={b_cfg.get('train_fraction')}")

    # ------------------------------------------------------------------
    # Baseline metrics
    # ------------------------------------------------------------------
    print_header("Baseline (standard MLP)")
    b_cfg_full = baseline.get("config", {})
    print(f"  hidden={b_cfg_full.get('hidden_size')}  lr={b_cfg_full.get('learning_rate')}  "
          f"epochs={b_cfg_full.get('epochs')}  seed={b_cfg_full.get('seed')}")
    print(f"  final_train_loss : {baseline.get('final_train_loss', '?'):.6f}")
    b_metrics = baseline.get("metrics", {})
    print_metrics_table("baseline", b_metrics)
    cm = f"  TP={b_metrics.get('tp',0):.0f}  TN={b_metrics.get('tn',0):.0f}  " \
         f"FP={b_metrics.get('fp',0):.0f}  FN={b_metrics.get('fn',0):.0f}"
    print(cm)

    # ------------------------------------------------------------------
    # Per-seed REAL runs
    # ------------------------------------------------------------------
    for run in runs:
        if args.seed is not None and run.get("selector_seed") != args.seed:
            continue

        seed = run.get("selector_seed")
        real = run.get("real", {})
        r_cfg = real.get("config", {})
        train_summary = real.get("train_summary", {})
        eval_summary = real.get("eval_summary", {})
        sys_summary = real.get("system_summary", {})
        train_results = real.get("train_results", [])
        eval_results = real.get("eval_results", [])
        baseline_metrics = run.get("baseline_metrics", b_metrics)
        eval_minus = run.get("eval_minus_baseline", {})

        print_header(f"REAL Run  |  selector_seed={seed}")

        # Config
        print(f"  feedback_amount={r_cfg.get('feedback_amount')}  "
              f"packet_ttl={r_cfg.get('packet_ttl')}")
        print(f"  forward_drain={r_cfg.get('forward_drain_cycles')}  "
              f"feedback_drain={r_cfg.get('feedback_drain_cycles')}")
        print(f"  train_episodes={real.get('train_episode_count')}  "
              f"eval_episodes={real.get('eval_episode_count')}")

        # Topology
        topo = real.get("topology", {})
        adj = topo.get("adjacency", {})
        positions = topo.get("positions", {})
        node_count = len(adj)
        print(f"\n  Topology  : {node_count} nodes  "
              f"(source={topo.get('source_id')}  sink={topo.get('sink_id')})")
        for node, nbrs in adj.items():
            if nbrs:
                print(f"    {node} -> {', '.join(nbrs)}")

        # Train metrics
        print(f"\n  --- Training ({train_summary.get('episode_count')} episodes) ---")
        tm = train_summary.get("metrics", {})
        print_metrics_table("REAL train", tm, baseline_metrics)
        print(f"  mean_delivered_packets : {train_summary.get('mean_delivered_packets')}")
        print(f"  mean_dropped_packets   : {train_summary.get('mean_dropped_packets')}")
        print(f"  mean_feedback_events   : {train_summary.get('mean_feedback_events')}")
        print(f"  mean_feedback_total    : {train_summary.get('mean_feedback_total')}")
        print(f"  occupied_prediction_rate : {train_summary.get('occupied_prediction_rate')}")

        # Eval metrics
        print(f"\n  --- Evaluation ({eval_summary.get('episode_count')} episodes) ---")
        em = eval_summary.get("metrics", {})
        print_metrics_table("REAL eval ", em, baseline_metrics)
        print(f"  mean_delivered_packets : {eval_summary.get('mean_delivered_packets')}")
        print(f"  mean_dropped_packets   : {eval_summary.get('mean_dropped_packets')}")
        print(f"  mean_feedback_events   : {eval_summary.get('mean_feedback_events')}")
        print(f"  mean_feedback_total    : {eval_summary.get('mean_feedback_total')}")
        print(f"  occupied_prediction_rate : {eval_summary.get('occupied_prediction_rate')}")
        print(f"\n  eval_minus_baseline:")
        for k, v in eval_minus.items():
            print(f"    {k:<12} : {_pct(v)}")

        # System summary
        print(f"\n  --- System ---")
        print(f"  total_cycles        : {sys_summary.get('cycles')}")
        print(f"  injected_packets    : {sys_summary.get('injected_packets')}")
        print(f"  delivered_packets   : {sys_summary.get('delivered_packets')}")
        print(f"  delivery_ratio      : {sys_summary.get('delivery_ratio'):.4f}")
        print(f"  drop_ratio          : {sys_summary.get('drop_ratio'):.4f}")
        print(f"  mean_latency        : {sys_summary.get('mean_latency'):.4f}")
        print(f"  mean_route_cost     : {sys_summary.get('mean_route_cost'):.4f}")
        print(f"  mean_feedback_award : {sys_summary.get('mean_feedback_award'):.4f}")
        print(f"  node_atp_total      : {sys_summary.get('node_atp_total'):.4f}")
        print(f"  exact_matches       : {sys_summary.get('exact_matches')}")
        print(f"  mean_bit_accuracy   : {sys_summary.get('mean_bit_accuracy'):.4f}")

        # ------------------------------------------------------------------
        # Episode-level analysis
        # ------------------------------------------------------------------
        _print_episode_stats("train", train_results)
        _print_episode_stats("eval ", eval_results)

        # ------------------------------------------------------------------
        # Plots (one figure per seed)
        # ------------------------------------------------------------------
        if HAS_PLT and not args.no_plots:
            _plot_run(seed, train_results, eval_results, baseline_metrics,
                      title, args.rolling)

    # ------------------------------------------------------------------
    # Aggregate summary
    # ------------------------------------------------------------------
    if aggregate:
        print_header("Aggregate (across all seeds)")
        agg_real = aggregate.get("mean_real_eval_metrics", {})
        agg_delta = aggregate.get("mean_eval_minus_baseline", {})
        print(f"  seed_count : {aggregate.get('selector_seed_count')}")
        print_metrics_table("mean eval ", agg_real, b_metrics)
        print(f"\n  mean_eval_minus_baseline:")
        for k, v in agg_delta.items():
            print(f"    {k:<12} : {_pct(v)}")
        print(f"  mean_real_train_accuracy         : {aggregate.get('mean_real_train_accuracy'):.4f}")
        print(f"  mean_real_eval_delivered_packets : {aggregate.get('mean_real_eval_delivered_packets')}")
        print(f"  mean_real_train_feedback_events  : {aggregate.get('mean_real_train_feedback_events')}")

    if HAS_PLT and not args.no_plots:
        print("\n[info] Showing plots — close windows to exit.")
        plt.show()


def _print_episode_stats(phase_label, results):
    if not results:
        return
    n = len(results)
    correct = sum(1 for r in results if r.get("correct"))
    n_occupied = sum(1 for r in results if r.get("label") == 1)
    n_empty = n - n_occupied
    pred_occupied = sum(1 for r in results if r.get("prediction") == 1)

    # Confidence stats
    confidences = [r.get("prediction_confidence", 0) for r in results]
    mean_conf = sum(confidences) / n if n else 0
    high_conf = sum(1 for c in confidences if c > 0.6)

    # Feedback (only training has non-zero feedback in eval)
    feedbacks = [r.get("feedback_total", 0) for r in results]
    mean_fb = sum(feedbacks) / n if n else 0

    delivered = [r.get("delivered_packets", 0) for r in results]
    mean_del = sum(delivered) / n if n else 0

    print(f"\n  --- {phase_label} episode stats ({n} episodes) ---")
    print(f"  accuracy          : {correct/n:.4f}  ({correct}/{n})")
    print(f"  label distribution: occupied={n_occupied}  empty={n_empty}")
    print(f"  predicted occupied: {pred_occupied}  ({pred_occupied/n:.2%})")
    print(f"  mean confidence   : {mean_conf:.4f}  (high-conf >0.6: {high_conf})")
    print(f"  mean delivered    : {mean_del:.2f}")
    print(f"  mean feedback_tot : {mean_fb:.4f}")


def _plot_run(seed, train_results, eval_results, baseline_metrics, title, window):
    fig = plt.figure(figsize=(15, 10))
    fig.suptitle(f"{title}\nseed={seed}", fontsize=11)
    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.45, wspace=0.35)

    # ---- 1. Rolling accuracy — train ----
    ax1 = fig.add_subplot(gs[0, 0])
    if train_results:
        correct = [1 if r["correct"] else 0 for r in train_results]
        rail = rolling_mean(correct, window)
        ax1.plot(rail, label=f"REAL train (roll={window})", color="steelblue")
        ax1.axhline(baseline_metrics.get("accuracy", 0), color="orange",
                    linestyle="--", label="baseline acc")
        ax1.set_title("Train Rolling Accuracy")
        ax1.set_xlabel("Episode")
        ax1.set_ylabel("Accuracy")
        ax1.set_ylim(0, 1.05)
        ax1.legend(fontsize=7)
        ax1.grid(True, alpha=0.3)

    # ---- 2. Rolling accuracy — eval ----
    ax2 = fig.add_subplot(gs[0, 1])
    if eval_results:
        correct = [1 if r["correct"] else 0 for r in eval_results]
        rail = rolling_mean(correct, window)
        ax2.plot(rail, label=f"REAL eval (roll={window})", color="coral")
        ax2.axhline(baseline_metrics.get("accuracy", 0), color="orange",
                    linestyle="--", label="baseline acc")
        ax2.set_title("Eval Rolling Accuracy")
        ax2.set_xlabel("Episode")
        ax2.set_ylabel("Accuracy")
        ax2.set_ylim(0, 1.05)
        ax2.legend(fontsize=7)
        ax2.grid(True, alpha=0.3)

    # ---- 3. Delivered packets over train ----
    ax3 = fig.add_subplot(gs[0, 2])
    if train_results:
        delivered = [r.get("delivered_packets", 0) for r in train_results]
        ax3.plot(rolling_mean(delivered, window), color="mediumseagreen",
                 label=f"delivered (roll={window})")
        dropped = [r.get("dropped_packets", 0) for r in train_results]
        ax3.plot(rolling_mean(dropped, window), color="tomato", alpha=0.7,
                 label=f"dropped (roll={window})")
        ax3.set_title("Train Packet Delivery")
        ax3.set_xlabel("Episode")
        ax3.set_ylabel("Packets")
        ax3.legend(fontsize=7)
        ax3.grid(True, alpha=0.3)

    # ---- 4. Feedback total over training ----
    ax4 = fig.add_subplot(gs[1, 0])
    if train_results:
        fb = [r.get("feedback_total", 0) for r in train_results]
        ax4.plot(rolling_mean(fb, window), color="mediumpurple",
                 label=f"feedback_total (roll={window})")
        ax4.set_title("Train Feedback Total")
        ax4.set_xlabel("Episode")
        ax4.set_ylabel("Feedback")
        ax4.legend(fontsize=7)
        ax4.grid(True, alpha=0.3)

    # ---- 5. Confidence distribution ----
    ax5 = fig.add_subplot(gs[1, 1])
    if train_results or eval_results:
        train_conf = [r.get("prediction_confidence", 0) for r in train_results]
        eval_conf  = [r.get("prediction_confidence", 0) for r in eval_results]
        bins = [i / 20 for i in range(21)]
        if train_conf:
            ax5.hist(train_conf, bins=bins, alpha=0.6, label="train", color="steelblue")
        if eval_conf:
            ax5.hist(eval_conf, bins=bins, alpha=0.6, label="eval", color="coral")
        ax5.set_title("Prediction Confidence Distribution")
        ax5.set_xlabel("Confidence")
        ax5.set_ylabel("Count")
        ax5.legend(fontsize=7)
        ax5.grid(True, alpha=0.3)

    # ---- 6. Bar: metric comparison ----
    ax6 = fig.add_subplot(gs[1, 2])
    metrics_keys = ["accuracy", "precision", "recall", "f1"]
    # Grab from run's eval_summary metrics
    x = range(len(metrics_keys))
    width = 0.35

    # We need eval metrics for this seed — passed in via train/eval results proxy
    eval_correct = [1 if r["correct"] else 0 for r in eval_results] if eval_results else []
    if eval_results:
        # compute simple accuracy from results
        n = len(eval_results)
        tp = sum(1 for r in eval_results if r.get("label") == 1 and r.get("prediction") == 1)
        tn = sum(1 for r in eval_results if r.get("label") == 0 and r.get("prediction") == 0)
        fp = sum(1 for r in eval_results if r.get("label") == 0 and r.get("prediction") == 1)
        fn = sum(1 for r in eval_results if r.get("label") == 1 and r.get("prediction") == 0)
        acc = (tp + tn) / n if n else 0
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec  = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
        real_vals = [acc, prec, rec, f1]
    else:
        real_vals = [0, 0, 0, 0]

    base_vals = [baseline_metrics.get(k, 0) for k in metrics_keys]

    ax6.bar([xi - width/2 for xi in x], base_vals, width, label="Baseline", color="orange", alpha=0.8)
    ax6.bar([xi + width/2 for xi in x], real_vals, width, label="REAL eval", color="steelblue", alpha=0.8)
    ax6.set_xticks(list(x))
    ax6.set_xticklabels(metrics_keys, fontsize=8)
    ax6.set_ylim(0, 1.1)
    ax6.set_title("Baseline vs REAL Eval Metrics")
    ax6.legend(fontsize=7)
    ax6.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()


# ---------------------------------------------------------------------------
# Markdown summary writer
# ---------------------------------------------------------------------------

def write_summary(data, out_path):
    """Write a compact markdown summary of the experiment JSON to out_path."""
    title = data.get("title", "Unknown experiment")
    timestamp = data.get("timestamp", "?")
    harness = data.get("harness", "?")
    seeds = data.get("seeds", [])
    scenarios = data.get("scenarios", [])

    result = data.get("result", {})
    baseline = result.get("baseline", {})
    runs = result.get("runs", [])
    aggregate = result.get("aggregate", {})
    meta = data.get("metadata", {})

    b_cfg = baseline.get("config", {})
    b_metrics = baseline.get("metrics", {})

    lines = []
    lines.append(f"# {title}")
    lines.append(f"")
    lines.append(f"**Timestamp:** `{timestamp}`  ")
    lines.append(f"**Harness:** `{harness}`  ")
    lines.append(f"**Seeds:** {seeds}  ")
    lines.append(f"**Scenarios:** {scenarios}")
    lines.append("")

    # Dataset
    lines.append("## Dataset")
    lines.append("")
    lines.append(f"| Property | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Rows | {baseline.get('dataset_rows')} |")
    lines.append(f"| Windowed examples | {baseline.get('windowed_examples')} |")
    lines.append(f"| Train examples | {baseline.get('train_examples')} |")
    lines.append(f"| Test examples | {baseline.get('test_examples')} |")
    lines.append(f"| Input dim | {baseline.get('input_dim')} |")
    lines.append(f"| Window size | {b_cfg.get('window_size')} |")
    lines.append(f"| Train fraction | {b_cfg.get('train_fraction')} |")
    lines.append(f"| Normalize | {b_cfg.get('normalize')} |")
    lines.append("")

    # Baseline
    lines.append("## Baseline (MLP)")
    lines.append("")
    lines.append(f"| Property | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Hidden size | {b_cfg.get('hidden_size')} |")
    lines.append(f"| Learning rate | {b_cfg.get('learning_rate')} |")
    lines.append(f"| Epochs | {b_cfg.get('epochs')} |")
    lines.append(f"| Seed | {b_cfg.get('seed')} |")
    lines.append(f"| Final train loss | {baseline.get('final_train_loss', 0):.6f} |")
    lines.append("")
    lines.append("**Test metrics:**")
    lines.append("")
    lines.append(_md_metrics_table(b_metrics))
    lines.append("")
    lines.append(
        f"Confusion: TP={b_metrics.get('tp',0):.0f}  "
        f"TN={b_metrics.get('tn',0):.0f}  "
        f"FP={b_metrics.get('fp',0):.0f}  "
        f"FN={b_metrics.get('fn',0):.0f}"
    )
    lines.append("")

    # Per-seed runs
    for run in runs:
        seed = run.get("selector_seed")
        real = run.get("real", {})
        r_cfg = real.get("config", {})
        train_summary = real.get("train_summary", {})
        eval_summary = real.get("eval_summary", {})
        sys_summary = real.get("system_summary", {})
        baseline_metrics = run.get("baseline_metrics", b_metrics)
        eval_minus = run.get("eval_minus_baseline", {})

        topo = real.get("topology", {})
        adj = topo.get("adjacency", {})
        node_count = len(adj)

        lines.append(f"## REAL Run — selector_seed={seed}")
        lines.append("")

        # Config
        lines.append("**Config:**")
        lines.append("")
        lines.append(f"| Param | Value |")
        lines.append(f"|---|---|")
        lines.append(f"| feedback_amount | {r_cfg.get('feedback_amount')} |")
        lines.append(f"| packet_ttl | {r_cfg.get('packet_ttl')} |")
        lines.append(f"| forward_drain_cycles | {r_cfg.get('forward_drain_cycles')} |")
        lines.append(f"| feedback_drain_cycles | {r_cfg.get('feedback_drain_cycles')} |")
        lines.append(f"| train_episodes | {real.get('train_episode_count')} |")
        lines.append(f"| eval_episodes | {real.get('eval_episode_count')} |")
        lines.append("")

        # Topology
        lines.append(f"**Topology** ({node_count} nodes, "
                     f"source=`{topo.get('source_id')}`, "
                     f"sink=`{topo.get('sink_id')}`)")
        lines.append("")
        for node, nbrs in adj.items():
            if nbrs:
                lines.append(f"- `{node}` -> {', '.join(f'`{n}`' for n in nbrs)}")
        lines.append("")

        # Train metrics
        tm = train_summary.get("metrics", {})
        lines.append(f"### Training ({train_summary.get('episode_count')} episodes)")
        lines.append("")
        lines.append(_md_metrics_table(tm, baseline_metrics))
        lines.append("")
        lines.append(f"| Stat | Value |")
        lines.append(f"|---|---|")
        lines.append(f"| mean_delivered_packets | {train_summary.get('mean_delivered_packets')} |")
        lines.append(f"| mean_dropped_packets | {train_summary.get('mean_dropped_packets')} |")
        lines.append(f"| mean_feedback_events | {train_summary.get('mean_feedback_events')} |")
        lines.append(f"| mean_feedback_total | {train_summary.get('mean_feedback_total')} |")
        lines.append(f"| occupied_prediction_rate | {train_summary.get('occupied_prediction_rate')} |")
        lines.append("")

        # Eval metrics
        em = eval_summary.get("metrics", {})
        lines.append(f"### Evaluation ({eval_summary.get('episode_count')} episodes)")
        lines.append("")
        lines.append(_md_metrics_table(em, baseline_metrics))
        lines.append("")
        lines.append(f"| Stat | Value |")
        lines.append(f"|---|---|")
        lines.append(f"| mean_delivered_packets | {eval_summary.get('mean_delivered_packets')} |")
        lines.append(f"| mean_dropped_packets | {eval_summary.get('mean_dropped_packets')} |")
        lines.append(f"| mean_feedback_events | {eval_summary.get('mean_feedback_events')} |")
        lines.append(f"| mean_feedback_total | {eval_summary.get('mean_feedback_total')} |")
        lines.append(f"| occupied_prediction_rate | {eval_summary.get('occupied_prediction_rate')} |")
        lines.append("")

        # Delta vs baseline
        lines.append("**Delta vs baseline (eval):**")
        lines.append("")
        lines.append("| Metric | Delta |")
        lines.append("|---|---|")
        for k, v in eval_minus.items():
            lines.append(f"| {k} | {_pct(v)} |")
        lines.append("")

        # System summary
        lines.append("### Substrate System Stats")
        lines.append("")
        lines.append("| Stat | Value |")
        lines.append("|---|---|")
        for k, v in sys_summary.items():
            lines.append(f"| {k} | {v} |")
        lines.append("")

    # Aggregate
    if aggregate:
        agg_real = aggregate.get("mean_real_eval_metrics", {})
        agg_delta = aggregate.get("mean_eval_minus_baseline", {})
        lines.append("## Aggregate (all seeds)")
        lines.append("")
        lines.append(f"Seed count: {aggregate.get('selector_seed_count')}")
        lines.append("")
        lines.append("**Mean REAL eval metrics:**")
        lines.append("")
        lines.append(_md_metrics_table(agg_real, b_metrics))
        lines.append("")
        lines.append("**Mean delta vs baseline:**")
        lines.append("")
        lines.append("| Metric | Delta |")
        lines.append("|---|---|")
        for k, v in agg_delta.items():
            lines.append(f"| {k} | {_pct(v)} |")
        lines.append("")
        lines.append(f"| Stat | Value |")
        lines.append(f"|---|---|")
        lines.append(f"| mean_real_train_accuracy | {aggregate.get('mean_real_train_accuracy')} |")
        lines.append(f"| mean_real_eval_delivered_packets | {aggregate.get('mean_real_eval_delivered_packets')} |")
        lines.append(f"| mean_real_train_feedback_events | {aggregate.get('mean_real_train_feedback_events')} |")
        lines.append("")

    out_path = Path(out_path)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[summary] Written -> {out_path}")


def _md_metrics_table(metrics, ref=None):
    """Return a markdown table string for the given metrics dict."""
    cols = ["accuracy", "precision", "recall", "f1"]
    header = "| Metric | Value |"
    sep    = "|---|---|"
    if ref:
        header = "| Metric | Value | vs Baseline |"
        sep    = "|---|---|---|"
    rows = [header, sep]
    for c in cols:
        v = metrics.get(c)
        val_str = f"{v:.4f}" if v is not None else "-"
        if ref:
            delta = _pct(v - ref.get(c, 0)) if v is not None else "-"
            rows.append(f"| {c} | {val_str} | {delta} |")
        else:
            rows.append(f"| {c} | {val_str} |")
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Laminated Phase 8 format support (laminated_phase8 harness outputs)
# ---------------------------------------------------------------------------

def is_laminated_phase8_format(data: dict) -> bool:
    """Return True if this JSON looks like a laminated Phase 8 experiment output."""
    if data.get("harness") == "laminated_phase8":
        return True
    result = data.get("result")
    if not isinstance(result, dict):
        return False
    # Heuristic signature: baseline_summary + laminated_run are both present.
    return isinstance(result.get("baseline_summary"), dict) and isinstance(result.get("laminated_run"), dict)


def _laminated_get(d: dict, path: tuple[str, ...], default=None):
    cur = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _laminated_fmt_num(v, decimals: int = 4):
    if v is None:
        return "—"
    try:
        return f"{float(v):.{decimals}f}"
    except (TypeError, ValueError):
        return str(v)


def write_summary_laminated_phase8(data: dict, out_path) -> None:
    """Write a compact markdown summary for laminated_phase8 outputs."""
    title = data.get("title", "Laminated Phase 8 experiment")
    timestamp = data.get("timestamp", "?")
    seeds = data.get("seeds", data.get("seed", []))
    scenarios = data.get("scenarios", [])
    meta = data.get("metadata") or {}
    result = data.get("result") or {}

    baseline = result.get("baseline_summary") or {}
    laminated_run = result.get("laminated_run") or {}
    slice_summaries = laminated_run.get("slice_summaries") or []
    delta = result.get("delta_vs_baseline") or {}

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"**timestamp:** `{timestamp}`  ")
    lines.append(f"**harness:** `{data.get('harness', 'laminated_phase8')}`  ")
    lines.append(f"**scenarios:** {scenarios}  ")
    lines.append(f"**seeds:** {seeds}")
    lines.append("")

    lines.append("## Run identity")
    lines.append("")
    lines.append("| Key | Value |")
    lines.append("|---|---|")
    for key in (
        "benchmark_id",
        "task_key",
        "mode",
        "capability_policy",
        "seed",
    ):
        val = result.get(key, meta.get(key))
        if val is not None:
            lines.append(f"| {key} | {val} |")
    for key in ("max_slices", "safety_limit", "initial_cycle_budget", "accuracy_threshold", "regulator_type"):
        if key in meta:
            lines.append(f"| {key} | {meta.get(key)} |")
    lines.append("")

    lines.append("## Baseline summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    for key in (
        "cycles",
        "injected_packets",
        "admitted_packets",
        "delivered_packets",
        "delivery_ratio",
        "dropped_packets",
        "drop_ratio",
        "mean_latency",
        "mean_hops",
        "node_atp_total",
        "node_reward_total",
        "mean_route_cost",
        "total_action_cost",
        "exact_matches",
        "exact_match_rate",
        "partial_matches",
        "mean_bit_accuracy",
        "mean_feedback_award",
        "node_count",
        "edge_count",
        "bud_successes",
        "prune_events",
        "apoptosis_events",
    ):
        if key in baseline:
            lines.append(f"| {key} | {_laminated_fmt_num(baseline.get(key))} |")
    lines.append("")

    ctx_breakdown = baseline.get("context_breakdown") or {}
    if isinstance(ctx_breakdown, dict) and ctx_breakdown:
        lines.append("### Context breakdown (baseline)")
        lines.append("")
        lines.append("| context | count | exact_matches | exact_match_rate | mean_bit_accuracy |")
        lines.append("|---|---:|---:|---:|---:|")
        for ctx, payload in sorted(ctx_breakdown.items()):
            if not isinstance(payload, dict):
                continue
            lines.append(
                f"| {ctx} | {payload.get('count')} | {payload.get('exact_matches')} | {_laminated_fmt_num(payload.get('exact_match_rate'))} | {_laminated_fmt_num(payload.get('mean_bit_accuracy'))} |"
            )
        lines.append("")

    lines.append("## Laminated controller outcome")
    lines.append("")
    lines.append("| Key | Value |")
    lines.append("|---|---|")
    lines.append(f"| final_decision | `{laminated_run.get('final_decision', '—')}` |")
    if laminated_run.get("final_cycle_budget") is not None:
        lines.append(f"| final_cycle_budget | {laminated_run.get('final_cycle_budget')} |")
    final_signal = laminated_run.get("final_signal") or {}
    if isinstance(final_signal, dict) and final_signal:
        for key in ("next_slice_budget", "carryover_filter_mode", "context_pressure", "decision_hint", "stop_reason"):
            if key in final_signal:
                v = final_signal.get(key)
                if isinstance(v, str):
                    lines.append(f"| final_signal.{key} | `{v}` |")
                else:
                    lines.append(f"| final_signal.{key} | {v} |")
    lines.append("")

    if delta:
        lines.append("## Delta vs baseline (reported)")
        lines.append("")
        lines.append("| Metric | Delta |")
        lines.append("|---|---:|")
        for key, value in delta.items():
            lines.append(f"| {key} | {_laminated_fmt_num(value)} |")
        lines.append("")

    if isinstance(slice_summaries, list) and slice_summaries:
        lines.append("## Slice summaries")
        lines.append("")
        lines.append(
            "| slice | budget | cycles | mode_used | min_ctx_exact | final_exact | mean_bit_acc | conflict | ambiguity | uncertainty | cost | exact | partial | hint |"
        )
        lines.append("|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
        for s in slice_summaries:
            if not isinstance(s, dict):
                continue
            ctx_acc = s.get("context_accuracy") or {}
            min_ctx = None
            if isinstance(ctx_acc, dict) and ctx_acc:
                vals = []
                for v in ctx_acc.values():
                    try:
                        vals.append(float(v))
                    except (TypeError, ValueError):
                        pass
                min_ctx = min(vals) if vals else None
            cost = s.get("cost_summary") or {}
            lines.append(
                f"| {s.get('slice_id')} "
                f"| {s.get('slice_budget')} "
                f"| {s.get('cycles_used')} "
                f"| `{s.get('mode_used', '—')}` "
                f"| {_laminated_fmt_num(min_ctx)} "
                f"| {_laminated_fmt_num(_laminated_get(s, ('metadata', 'final_accuracy')))} "
                f"| {_laminated_fmt_num(_laminated_get(s, ('metadata', 'mean_bit_accuracy')))} "
                f"| {_laminated_fmt_num(s.get('conflict_level'))} "
                f"| {_laminated_fmt_num(s.get('ambiguity_level'))} "
                f"| {_laminated_fmt_num(s.get('mean_uncertainty'))} "
                f"| {_laminated_fmt_num(_laminated_get(cost, ('total_action_cost',)))} "
                f"| {_laminated_fmt_num(_laminated_get(cost, ('exact_matches',)))} "
                f"| {_laminated_fmt_num(_laminated_get(cost, ('partial_matches',)))} "
                f"| `{s.get('settlement_hint', '—')}` |"
            )
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[summary] Written to: {out_path}")


# ---------------------------------------------------------------------------
# V3 format support (session carryover output from run_occupancy_real_v3.py)
# ---------------------------------------------------------------------------

def is_v3_format(data: dict) -> bool:
    """Return True if this JSON was produced by the v3 occupancy runner."""
    return (
        (
            isinstance(data.get("v3_config"), dict)
            and (
                "carryover_efficiency" in data
                or isinstance(data.get("eval_protocols"), dict)
            )
        )
        or (
            isinstance(data.get("v3_sweep_config"), dict)
            and isinstance(data.get("aggregate"), dict)
            and isinstance(data.get("seed_summaries"), list)
        )
    )


def is_v3_sweep_format(data: dict) -> bool:
    return (
        isinstance(data.get("v3_sweep_config"), dict)
        and isinstance(data.get("aggregate"), dict)
        and isinstance(data.get("seed_summaries"), list)
    )


def _v3_selector_seeds(data: dict, manifest: dict | None = None) -> list[int]:
    if manifest and isinstance(manifest.get("selector_seeds"), list):
        return [int(seed) for seed in manifest["selector_seeds"]]
    sweep_cfg = data.get("v3_sweep_config") or {}
    if isinstance(sweep_cfg.get("selector_seeds"), list):
        return [int(seed) for seed in sweep_cfg["selector_seeds"]]
    cfg = data.get("v3_config") or {}
    seed = cfg.get("selector_seed")
    return [int(seed)] if seed is not None else []


def _print_v3_manifest(manifest: dict | None) -> None:
    if not manifest:
        return
    sep = "-" * 60
    print(f"\n{sep}")
    print(f"  run_id:   {manifest.get('run_id', '?')}")
    print(f"  run_at:   {manifest.get('run_at', '?')}")
    if manifest.get("git_sha"):
        print(f"  git_sha:  {manifest['git_sha']}")
    print(f"  csv:      {manifest.get('csv', '?')}")
    selector_seeds = manifest.get("selector_seeds")
    if isinstance(selector_seeds, list) and selector_seeds:
        if len(selector_seeds) == 1:
            print(
                f"  seed:     {selector_seeds[0]}  "
                f"window: {manifest.get('window_size', '?')}  "
                f"train_frac: {manifest.get('train_session_fraction', '?')}"
            )
        else:
            print(
                f"  seeds:    {selector_seeds}  "
                f"window: {manifest.get('window_size', '?')}  "
                f"train_frac: {manifest.get('train_session_fraction', '?')}"
            )
    else:
        print(
            f"  seed:     {manifest.get('selector_seed', '?')}  "
            f"window: {manifest.get('window_size', '?')}  "
            f"train_frac: {manifest.get('train_session_fraction', '?')}"
        )
    if manifest.get("eval_mode") is not None:
        print(
            f"  modes:    eval={manifest.get('eval_mode')}  "
            f"topology={manifest.get('topology_mode')}  "
            f"context={manifest.get('context_mode')}  "
            f"ingress={manifest.get('ingress_mode')}"
        )
    caps = []
    if manifest.get("max_train_sessions") is not None:
        caps.append(f"train<={manifest['max_train_sessions']}")
    if manifest.get("max_eval_sessions") is not None:
        caps.append(f"eval<={manifest['max_eval_sessions']}")
    if caps:
        print(f"  caps:     {', '.join(caps)}")
    print(f"  workers:  {manifest.get('workers', '?')}")
    es = manifest.get("elapsed_seconds")
    if es is not None:
        print(f"  elapsed:  {float(es):.1f}s")
    print(sep)


def _print_v3_worker_policy(policy: dict | None) -> None:
    if not policy:
        return
    print("\nWorker policy")
    for key in (
        "requested_workers",
        "auto_cpu_target_fraction",
        "worker_budget",
        "seed_workers",
        "eval_workers_per_seed",
        "effective_total_workers",
        "parallelism_status",
    ):
        if key in policy:
            print(f"  {key:<26} : {policy.get(key)}")
    if isinstance(policy.get("eval_workers_by_protocol"), dict):
        print(f"  {'eval_workers_by_protocol':<26} : {policy.get('eval_workers_by_protocol')}")


def _print_v3_inventory(label: str, inv: dict) -> None:
    print(f"\n{label}")
    print(f"  sessions:       {inv.get('session_count', '?')}")
    print(f"  by label:       {inv.get('by_label', {})}")
    print(f"  by context:     {inv.get('by_context_code', {})}")
    ep = inv.get("episode_lengths") or {}
    if ep:
        print(
            f"  episode length: min={ep.get('min')}  mean={ep.get('mean')}  "
            f"max={ep.get('max')}"
        )


def _print_v3_phase_summary(title: str, summary: dict) -> None:
    print(f"\n{title}")
    m = summary.get("metrics") or {}
    ec = summary.get("episode_count", "?")
    print(f"  episodes:     {ec}")
    for key in ("accuracy", "f1", "precision", "recall"):
        v = m.get(key)
        if v is not None:
            print(f"  {key:<12} : {float(v):.4f}")
    for key in (
        "mean_delivered_packets",
        "mean_dropped_packets",
        "mean_feedback_events",
        "occupied_prediction_rate",
    ):
        if key in summary:
            print(f"  {key:<22} : {summary[key]}")


def _print_v3_efficiency(eff: dict) -> None:
    print("\nCarryover efficiency")
    print(f"  mean efficiency ratio:       {eff.get('mean_efficiency_ratio')}")
    print(f"  session 1 delivery delta:    {eff.get('session_1_delivery_delta')}")
    print(f"  session 1 efficiency ratio:  {eff.get('session_1_efficiency_ratio')}")
    print(f"  mean first-episode delta:    {eff.get('mean_first_episode_delivery_delta')}")
    print(f"  mean first-3-episode delta:  {eff.get('mean_first_three_episode_delivery_delta')}")
    print(f"  warm sessions to 80% deliv:  {eff.get('warm_sessions_to_80pct')}")
    print(f"  cold sessions to 80% deliv:  {eff.get('cold_sessions_to_80pct')}")
    print("\n  Delivery ratio at session N:")
    print(f"  {'Session':>10}  {'Warm':>8}  {'Cold':>8}  {'Ratio':>8}")
    warm_at = eff.get("warm_delivery_at") or {}
    cold_at = eff.get("cold_delivery_at") or {}
    for key in ("session_1", "session_5", "session_10", "session_20"):
        w, c = warm_at.get(key), cold_at.get(key)
        ratio = (
            f"{w / c:.4f}"
            if (w is not None and c is not None and c > 0)
            else "—"
        )
        w_str = f"{float(w):.4f}" if w is not None else "—"
        c_str = f"{float(c):.4f}" if c is not None else "—"
        lab = key.replace("session_", "session ")
        print(f"  {lab:>10}  {w_str:>8}  {c_str:>8}  {ratio:>8}")


def _print_v3_transfer(probe: dict) -> None:
    print("\nContext transfer probe")
    print(f"  status:                      {probe.get('status')}")
    print(f"  training context codes:    {probe.get('training_context_codes')}")
    print(f"  eval context codes:        {probe.get('eval_context_codes')}")
    print(
        f"  seen contexts (warm):        {probe.get('warm_seen_mean_delivery')}  "
        f"({probe.get('warm_seen_session_count')} sessions)"
    )
    print(
        f"  unseen contexts (warm):      {probe.get('warm_unseen_mean_delivery')}  "
        f"({probe.get('warm_unseen_session_count')} sessions)"
    )
    print(f"  seen contexts (cold):        {probe.get('cold_seen_mean_delivery')}")
    print(
        f"  unseen contexts (cold):      {probe.get('cold_unseen_mean_delivery')}"
    )


def _print_v3_system(label: str, sys_s: dict) -> None:
    if not sys_s:
        return
    print(f"\n  --- {label} ---")
    for key in (
        "cycles",
        "injected_packets",
        "delivered_packets",
        "delivery_ratio",
        "drop_ratio",
        "mean_latency",
        "mean_route_cost",
        "mean_feedback_award",
        "node_atp_total",
        "exact_matches",
        "mean_bit_accuracy",
    ):
        val = sys_s.get(key)
        if val is None:
            continue
        try:
            print(f"  {key:<22} : {float(val):.4f}")
        except (TypeError, ValueError):
            print(f"  {key:<22} : {val}")


def _print_v3_protocol(label: str, payload: dict) -> None:
    print_header(label)
    _print_v3_phase_summary("Warm eval (with carryover)", payload.get("warm_summary") or {})
    _print_v3_phase_summary("Cold eval (fresh substrate)", payload.get("cold_summary") or {})
    print(f"\n  warm_reset_count        : {payload.get('warm_reset_count')}")
    print(f"  cold_reset_count        : {payload.get('cold_reset_count')}")
    print(f"  workers_used            : {payload.get('workers_used')}")
    print(f"  parallelism_status      : {payload.get('parallelism_status')}")
    warm_sys = payload.get("warm_system_summary") or {}
    cold_sys = payload.get("cold_system_summary") or {}
    if warm_sys or cold_sys:
        print(f"  warm admitted_packets   : {warm_sys.get('admitted_packets')}")
        print(f"  cold admitted_packets   : {cold_sys.get('admitted_packets')}")
    _print_v3_efficiency(payload.get("efficiency") or {})
    _print_v3_transfer(payload.get("context_transfer_probe") or {})
    print_header(f"{label} substrate system summaries")
    _print_v3_system("Warm eval", warm_sys)
    _print_v3_system("Cold eval", cold_sys)


def _print_v3_seed_summary(summary: dict) -> None:
    print(f"\nSeed {summary.get('selector_seed')}")
    for key in (
        "train_accuracy",
        "warm_accuracy",
        "cold_accuracy",
        "warm_mean_delivery_ratio",
        "cold_mean_delivery_ratio",
        "mean_efficiency_ratio",
        "session_1_delivery_delta",
        "mean_first_episode_delivery_delta",
        "mean_first_three_episode_delivery_delta",
    ):
        if key in summary:
            print(f"  {key:<31} : {summary.get(key)}")
    if "eval_workers_by_protocol" in summary:
        print(f"  {'eval_workers_by_protocol':<31} : {summary.get('eval_workers_by_protocol')}")
    if "protocol_parallelism" in summary:
        print(f"  {'protocol_parallelism':<31} : {summary.get('protocol_parallelism')}")


def analyze_v3(data: dict, args) -> None:
    if is_v3_sweep_format(data):
        manifest = data.get("manifest")
        selector_seeds = _v3_selector_seeds(data, manifest)
        if args.seed is not None and args.seed not in selector_seeds:
            print(
                f"[info] Skipping: sweep selector_seeds={selector_seeds} "
                f"does not include --seed {args.seed}"
            )
            return

        print_header("REAL Occupancy v3 - multi-seed sweep")
        _print_v3_manifest(manifest)
        sweep_cfg = data.get("v3_sweep_config") or {}
        base_cfg = sweep_cfg.get("base_config") or {}
        if base_cfg:
            print("\nBase config")
            for key in sorted(base_cfg.keys()):
                print(f"  {key:<24} : {base_cfg.get(key)}")
        _print_v3_worker_policy(data.get("worker_policy"))

        aggregate = data.get("aggregate") or {}
        print_header("Sweep aggregate")
        for key in (
            "selector_seed_count",
            "primary_eval_mode",
            "mean_train_accuracy",
            "mean_warm_accuracy",
            "mean_cold_accuracy",
            "mean_warm_delivery_ratio",
            "mean_cold_delivery_ratio",
            "mean_efficiency_ratio",
            "mean_session_1_delivery_delta",
            "mean_first_episode_delivery_delta",
            "mean_first_three_episode_delivery_delta",
        ):
            if key in aggregate:
                print(f"  {key:<33} : {aggregate.get(key)}")
        if "best_seed_by_efficiency_ratio" in aggregate:
            print(f"  {'best_seed_by_efficiency_ratio':<33} : {aggregate.get('best_seed_by_efficiency_ratio')}")
        if "best_seed_by_session_1_delivery_delta" in aggregate:
            print(f"  {'best_seed_by_session_1_delivery_delta':<33} : {aggregate.get('best_seed_by_session_1_delivery_delta')}")

        print_header("Per-seed summaries")
        for summary in data.get("seed_summaries") or []:
            if args.seed is not None and summary.get("selector_seed") != args.seed:
                continue
            _print_v3_seed_summary(summary)

        if args.seed is not None:
            detailed = next(
                (
                    item
                    for item in (data.get("seed_results") or [])
                    if (item.get("v3_config") or {}).get("selector_seed") == args.seed
                ),
                None,
            )
            if detailed is not None:
                print_header(f"Detailed seed view - {args.seed}")
                analyze_v3(
                    detailed,
                    argparse.Namespace(
                        seed=args.seed,
                        no_plots=args.no_plots,
                        rolling=args.rolling,
                        summary=None,
                    ),
                )
            return

        if HAS_PLT and not args.no_plots:
            _plot_v3_sweep(data)
            print("\n[info] Showing plots - close windows to exit.")
            plt.show()
        return

    cfg = data.get("v3_config") or {}
    seed = cfg.get("selector_seed")
    if args.seed is not None and seed != args.seed:
        print(
            f"[info] Skipping: file selector_seed={seed} "
            f"does not match --seed {args.seed}"
        )
        return

    print_header("REAL Occupancy v3 — session carryover experiment")
    _print_v3_manifest(data.get("manifest"))
    _print_v3_worker_policy(data.get("worker_policy"))

    print(f"\n  dataset_rows:      {data.get('dataset_rows')}")
    print(f"  total_episodes:   {data.get('total_episodes')}")
    print(f"  total_sessions:   {data.get('total_sessions')}")
    print(f"  train sessions:   {data.get('train_session_count')}")
    print(f"  eval sessions:    {data.get('eval_session_count')}")
    print(f"  CO2 train median:  {data.get('co2_training_median')}")
    print(f"  Light train median: {data.get('light_training_median')}")

    print_header("Session inventory")
    _print_v3_inventory("Training", data.get("train_inventory") or {})
    _print_v3_inventory("Eval", data.get("eval_inventory") or {})
    print(f"\n  Training context codes seen: {data.get('training_context_codes')}")

    print_header("Phase 2 — Training")
    _print_v3_phase_summary("Training (sequential sessions)", data.get("train_summary") or {})
    _print_v3_system("Train", data.get("train_system_summary") or {})

    eval_protocols = data.get("eval_protocols") or {}
    primary_eval_mode = data.get("primary_eval_mode")
    if eval_protocols:
        print(f"\n  primary_eval_mode : {primary_eval_mode}")
        for protocol_name, payload in eval_protocols.items():
            label = (
                f"Phase 3 - Primary protocol ({protocol_name})"
                if protocol_name == primary_eval_mode
                else f"Phase 3 - Secondary protocol ({protocol_name})"
            )
            _print_v3_protocol(label, payload or {})
        if HAS_PLT and not args.no_plots:
            _plot_v3(data, args.rolling)
            print("\n[info] Showing plots - close windows to exit.")
            plt.show()
        return

    print_header("Phase 3 — Carryover efficiency")
    _print_v3_phase_summary("Warm eval (with carryover)", data.get("warm_eval_summary") or {})
    _print_v3_phase_summary("Cold eval (fresh substrate)", data.get("cold_eval_summary") or {})
    _print_v3_efficiency(data.get("carryover_efficiency") or {})

    print_header("Phase 4 — Context transfer")
    _print_v3_transfer(data.get("context_transfer_probe") or {})

    print_header("Substrate system summaries")
    _print_v3_system("Train", data.get("train_system_summary") or {})
    _print_v3_system("Warm eval", data.get("warm_system_summary") or {})
    _print_v3_system("Cold eval", data.get("cold_system_summary") or {})

    if HAS_PLT and not args.no_plots:
        _plot_v3(data, args.rolling)
        print("\n[info] Showing plots — close windows to exit.")
        plt.show()


def _plot_v3(data: dict, window: int) -> None:
    """Session-indexed curves for train delivery and warm/cold eval."""
    fig = plt.figure(figsize=(14, 9))
    fig.suptitle(
        "Occupancy v3 — session delivery & carryover\n"
        f"seed={data.get('v3_config', {}).get('selector_seed', '?')}",
        fontsize=11,
    )
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.3)

    train_sess = data.get("train_session_results") or []
    if train_sess:
        ax0 = fig.add_subplot(gs[0, 0])
        ratios = [float(s.get("delivery_ratio") or 0) for s in train_sess]
        xs = list(range(len(ratios)))
        if window > 1 and len(ratios) >= window:
            smooth = rolling_mean(ratios, window)
            ax0.plot(xs, smooth, color="steelblue", label=f"delivery (roll={window})")
        else:
            ax0.plot(xs, ratios, color="steelblue", label="delivery ratio")
        ax0.set_title("Train — delivery ratio by session")
        ax0.set_xlabel("Train session index")
        ax0.set_ylabel("Delivery ratio")
        ax0.set_ylim(-0.05, 1.05)
        ax0.legend(fontsize=8)
        ax0.grid(True, alpha=0.3)

    eff = data.get("carryover_efficiency") or {}
    warm_c = eff.get("warm_delivery_curve") or []
    cold_c = eff.get("cold_delivery_curve") or []
    if warm_c or cold_c:
        ax1 = fig.add_subplot(gs[0, 1])
        if warm_c:
            ax1.plot(
                range(len(warm_c)),
                warm_c,
                color="darkgreen",
                label="warm eval",
                alpha=0.9,
            )
        if cold_c:
            ax1.plot(
                range(len(cold_c)),
                cold_c,
                color="coral",
                label="cold eval",
                alpha=0.9,
            )
        ax1.set_title("Eval sessions — delivery ratio (warm vs cold)")
        ax1.set_xlabel("Eval session index")
        ax1.set_ylabel("Delivery ratio")
        ax1.set_ylim(-0.05, 1.05)
        ax1.legend(fontsize=8)
        ax1.grid(True, alpha=0.3)

    ratio_curve = eff.get("efficiency_ratio_curve") or []
    if ratio_curve:
        ax2 = fig.add_subplot(gs[1, :])
        rc = ratio_curve
        ys = rolling_mean([float(x) for x in rc], min(window, len(rc))) if window > 1 else [float(x) for x in rc]
        ax2.plot(
            range(len(ys)),
            ys,
            color="mediumpurple",
            label=(
                f"efficiency ratio (warm/cold delivery, roll={min(window, len(rc))})"
                if window > 1
                else "efficiency ratio"
            ),
        )
        ax2.axhline(1.0, color="gray", linestyle="--", linewidth=1, label="1.0 (parity)")
        ax2.set_title("Carryover efficiency ratio across eval sessions")
        ax2.set_xlabel("Eval session index")
        ax2.set_ylabel("Ratio")
        ax2.legend(fontsize=8)
        ax2.grid(True, alpha=0.3)

    plt.tight_layout()


def _plot_v3_sweep(data: dict) -> None:
    seed_summaries = data.get("seed_summaries") or []
    if not seed_summaries:
        return

    seeds = [str(summary.get("selector_seed")) for summary in seed_summaries]
    warm_delivery = [float(summary.get("warm_mean_delivery_ratio") or 0.0) for summary in seed_summaries]
    cold_delivery = [float(summary.get("cold_mean_delivery_ratio") or 0.0) for summary in seed_summaries]
    efficiency = [
        float(summary.get("mean_efficiency_ratio"))
        if summary.get("mean_efficiency_ratio") is not None
        else 0.0
        for summary in seed_summaries
    ]

    fig = plt.figure(figsize=(12, 8))
    fig.suptitle("Occupancy v3 sweep - per-seed delivery and efficiency", fontsize=11)
    gs = gridspec.GridSpec(2, 1, figure=fig, hspace=0.35)

    ax0 = fig.add_subplot(gs[0, 0])
    x = list(range(len(seeds)))
    ax0.plot(x, warm_delivery, marker="o", color="darkgreen", label="warm delivery")
    ax0.plot(x, cold_delivery, marker="o", color="coral", label="cold delivery")
    ax0.set_title("Per-seed delivery ratio")
    ax0.set_xticks(x, seeds)
    ax0.set_ylim(-0.05, 1.05)
    ax0.set_ylabel("Delivery ratio")
    ax0.grid(True, alpha=0.3)
    ax0.legend(fontsize=8)

    ax1 = fig.add_subplot(gs[1, 0])
    ax1.bar(seeds, efficiency, color="mediumpurple")
    ax1.axhline(1.0, color="gray", linestyle="--", linewidth=1)
    ax1.set_title("Per-seed mean efficiency ratio")
    ax1.set_ylabel("Warm / cold delivery ratio")
    ax1.grid(True, axis="y", alpha=0.3)

    plt.tight_layout()


def write_summary_v3(data: dict, out_path) -> None:
    cfg = data.get("v3_config") or {}
    manifest = data.get("manifest") or {}
    if is_v3_sweep_format(data):
        sweep_cfg = data.get("v3_sweep_config") or {}
        base_cfg = sweep_cfg.get("base_config") or {}
        worker_policy = data.get("worker_policy") or {}
        aggregate = data.get("aggregate") or {}
        lines = [
            "# REAL Occupancy v3 - multi-seed sweep",
            "",
            f"**run_id:** `{manifest.get('run_id', '?')}`  ",
            f"**run_at:** `{manifest.get('run_at', '?')}`  ",
            f"**git_sha:** `{manifest.get('git_sha', '')}`  ",
            f"**selector_seeds:** {sweep_cfg.get('selector_seeds', _v3_selector_seeds(data, manifest))}  ",
            "",
            "## Base config",
            "",
            "| Key | Value |",
            "|---|---|",
        ]
        for key in sorted(base_cfg.keys()):
            lines.append(f"| {key} | {base_cfg.get(key)} |")
        lines.extend(["", "## Worker policy", "", "| Key | Value |", "|---|---|"])
        for key in (
            "requested_workers",
            "auto_cpu_target_fraction",
            "worker_budget",
            "seed_workers",
            "eval_workers_per_seed",
            "effective_total_workers",
            "parallelism_status",
        ):
            if key in worker_policy:
                lines.append(f"| {key} | {worker_policy.get(key)} |")
        lines.extend(["", "## Aggregate", "", "| Metric | Value |", "|---|---|"])
        for key in (
            "selector_seed_count",
            "primary_eval_mode",
            "mean_train_accuracy",
            "mean_warm_accuracy",
            "mean_cold_accuracy",
            "mean_warm_delivery_ratio",
            "mean_cold_delivery_ratio",
            "mean_efficiency_ratio",
            "mean_session_1_delivery_delta",
            "mean_first_episode_delivery_delta",
            "mean_first_three_episode_delivery_delta",
            "best_seed_by_efficiency_ratio",
            "best_seed_by_session_1_delivery_delta",
        ):
            if key in aggregate:
                lines.append(f"| {key} | {aggregate.get(key)} |")
        lines.extend(
            [
                "",
                "## Per-seed summary",
                "",
                "| selector_seed | train_accuracy | warm_accuracy | cold_accuracy | warm_delivery | cold_delivery | efficiency_ratio | session_1_delta |",
                "|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for summary in data.get("seed_summaries") or []:
            lines.append(
                f"| {summary.get('selector_seed')} "
                f"| {summary.get('train_accuracy')} "
                f"| {summary.get('warm_accuracy')} "
                f"| {summary.get('cold_accuracy')} "
                f"| {summary.get('warm_mean_delivery_ratio')} "
                f"| {summary.get('cold_mean_delivery_ratio')} "
                f"| {summary.get('mean_efficiency_ratio')} "
                f"| {summary.get('session_1_delivery_delta')} |"
            )
            lines.append(f"| protocol_parallelism | {summary.get('protocol_parallelism')} |  |  |  |  |  |  |")
            lines.append(f"| eval_workers_by_protocol | {summary.get('eval_workers_by_protocol')} |  |  |  |  |  |  |")
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"[summary] Written to: {out_path}")
        return

    lines = [
        "# REAL Occupancy v3 — session carryover experiment",
        "",
        f"**run_id:** `{manifest.get('run_id', '?')}`  ",
        f"**run_at:** `{manifest.get('run_at', '?')}`  ",
        f"**git_sha:** `{manifest.get('git_sha', '')}`  ",
        f"**primary_eval_mode:** `{data.get('primary_eval_mode', '?')}`  ",
        "",
        "## Config",
        "",
        "| Key | Value |",
        "|---|---|",
    ]
    for k in sorted(cfg.keys()):
        lines.append(f"| {k} | {cfg[k]} |")
    worker_policy = data.get("worker_policy") or {}
    if worker_policy:
        lines.extend(["", "## Worker policy", "", "| Key | Value |", "|---|---|"])
        for key in ("requested_workers", "auto_cpu_target_fraction", "eval_workers_by_protocol"):
            if key in worker_policy:
                lines.append(f"| {key} | {worker_policy.get(key)} |")
    lines.extend(
        [
            "",
            "## Dataset",
            "",
            f"- dataset_rows: **{data.get('dataset_rows')}**",
            f"- total_episodes: **{data.get('total_episodes')}**",
            f"- total_sessions: **{data.get('total_sessions')}**",
            f"- train_session_count: **{data.get('train_session_count')}**",
            f"- eval_session_count: **{data.get('eval_session_count')}**",
            f"- co2_training_median: **{data.get('co2_training_median')}**",
            f"- light_training_median: **{data.get('light_training_median')}**",
            f"- training_context_codes: {data.get('training_context_codes')}",
            "",
            "### Train inventory",
            "",
            f"```\n{json.dumps(data.get('train_inventory'), indent=2)}\n```",
            "",
            "### Eval inventory",
            "",
            f"```\n{json.dumps(data.get('eval_inventory'), indent=2)}\n```",
            "",
            "## Phase 2 — Training summary",
            "",
        ]
    )
    ts = data.get("train_summary") or {}
    lines.append(_md_metrics_table(ts.get("metrics") or {}))
    lines.extend(
        [
            "",
            "| Stat | Value |",
            "|---|---|",
            f"| episode_count | {ts.get('episode_count')} |",
            f"| mean_delivered_packets | {ts.get('mean_delivered_packets')} |",
            f"| mean_dropped_packets | {ts.get('mean_dropped_packets')} |",
            f"| mean_feedback_events | {ts.get('mean_feedback_events')} |",
            "",
            "## Phase 3 — Warm / cold eval & carryover",
            "",
        ]
    )
    for label, key in (
        ("Warm eval", "warm_eval_summary"),
        ("Cold eval", "cold_eval_summary"),
    ):
        s = data.get(key) or {}
        lines.append(f"### {label}")
        lines.append("")
        lines.append(_md_metrics_table(s.get("metrics") or {}))
        lines.append("")
    eff = data.get("carryover_efficiency") or {}
    lines.extend(
        [
            "### Carryover efficiency metrics",
            "",
            "| Metric | Value |",
            "|---|---|",
            f"| mean_efficiency_ratio | {eff.get('mean_efficiency_ratio')} |",
            f"| warm_sessions_to_80pct | {eff.get('warm_sessions_to_80pct')} |",
            f"| cold_sessions_to_80pct | {eff.get('cold_sessions_to_80pct')} |",
            "",
            "**Delivery checkpoints:**",
            "",
        ]
    )
    warm_at = eff.get("warm_delivery_at") or {}
    cold_at = eff.get("cold_delivery_at") or {}
    lines.append("| checkpoint | warm | cold | ratio |")
    lines.append("|---|---:|---:|---:|")
    for key in ("session_1", "session_5", "session_10", "session_20"):
        w, c = warm_at.get(key), cold_at.get(key)
        ratio = (
            f"{w / c:.4f}"
            if (w is not None and c is not None and c > 0)
            else "—"
        )
        lines.append(f"| {key} | {w} | {c} | {ratio} |")
    lines.extend(["", "## Phase 4 — Context transfer probe", ""])
    probe = data.get("context_transfer_probe") or {}
    for k, v in probe.items():
        lines.append(f"- **{k}**: {v}")
    lines.extend(["", "## System summaries", ""])
    for label, key in (
        ("Train", "train_system_summary"),
        ("Warm eval", "warm_system_summary"),
        ("Cold eval", "cold_system_summary"),
    ):
        lines.append(f"### {label}")
        lines.append("")
        lines.append(f"```\n{json.dumps(data.get(key), indent=2)}\n```")
        lines.append("")
    eval_protocols = data.get("eval_protocols") or {}
    if eval_protocols:
        lines.extend(["## Eval protocols", ""])
        for protocol_name, payload in eval_protocols.items():
            eff = payload.get("efficiency") or {}
            lines.extend(
                [
                    f"### {protocol_name}",
                    "",
                    f"- **workers_used**: {payload.get('workers_used')}",
                    f"- **parallelism_status**: {payload.get('parallelism_status')}",
                    f"- **warm_reset_count**: {payload.get('warm_reset_count')}",
                    f"- **cold_reset_count**: {payload.get('cold_reset_count')}",
                    "",
                    "| Metric | Value |",
                    "|---|---|",
                    f"| mean_efficiency_ratio | {eff.get('mean_efficiency_ratio')} |",
                    f"| session_1_delivery_delta | {eff.get('session_1_delivery_delta')} |",
                    f"| mean_first_episode_delivery_delta | {eff.get('mean_first_episode_delivery_delta')} |",
                    f"| mean_first_three_episode_delivery_delta | {eff.get('mean_first_three_episode_delivery_delta')} |",
                    f"| warm_sessions_to_80pct | {eff.get('warm_sessions_to_80pct')} |",
                    f"| cold_sessions_to_80pct | {eff.get('cold_sessions_to_80pct')} |",
                    "",
                    "**Context transfer probe:**",
                    "",
                ]
            )
            for key, value in (payload.get("context_transfer_probe") or {}).items():
                lines.append(f"- **{key}**: {value}")
            lines.extend(
                [
                    "",
                    "**Warm system summary:**",
                    "",
                    f"```\n{json.dumps(payload.get('warm_system_summary'), indent=2)}\n```",
                    "",
                    "**Cold system summary:**",
                    "",
                    f"```\n{json.dumps(payload.get('cold_system_summary'), indent=2)}\n```",
                    "",
                ]
            )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[summary] Written to: {out_path}")


# ---------------------------------------------------------------------------
# V2 format support (conditions-based output from run_occupancy_real_v2.py)
# ---------------------------------------------------------------------------

def is_v2_format(data: dict) -> bool:
    """Return True if this JSON was produced by the v2 runner."""
    return "conditions" in data and isinstance(data.get("conditions"), list)


def analyze_v2(data: dict, args) -> None:
    title = data.get("title", "Unknown experiment")
    timestamp = data.get("timestamp", "?")
    selector_seed = data.get("selector_seed", "?")
    elapsed = data.get("elapsed_seconds", "?")
    conditions = data.get("conditions", [])
    aggregate = data.get("aggregate", {})

    print_header(f"{title}  [{timestamp}]")
    print(f"  selector_seed : {selector_seed}")
    print(f"  elapsed       : {elapsed}s")
    print(f"  conditions    : {len(conditions)}")

    for cond in conditions:
        name = cond.get("name", "?")
        desc = cond.get("description", "")
        result = cond.get("result", {})
        if not result:
            continue

        v2cfg    = result.get("v2_config", result.get("config", {}))
        train_s  = result.get("train_summary", {})
        eval_s   = result.get("eval_summary", {})
        sys_s    = result.get("system_summary", {})

        print_header(f"Condition: {name}")
        print(f"  {desc}")

        # v2 config
        if v2cfg:
            print(f"  eval_feedback_fraction : {v2cfg.get('eval_feedback_fraction','?')}")
            print(f"  carryover_mode         : {v2cfg.get('carryover_mode','?')}")
            print(f"  context_bit_source     : {v2cfg.get('context_bit_source','?')}")
        print(f"  train_episodes : {result.get('train_episode_count','?')}   "
              f"eval_episodes : {result.get('eval_episode_count','?')}")
        if result.get("co2_training_median") is not None:
            print(f"  co2_training_median    : {result['co2_training_median']}")

        # Topology
        topo = result.get("topology", {})
        adj  = topo.get("adjacency", {})
        if adj:
            print(f"\n  Topology: {len(adj)} nodes  "
                  f"(source={topo.get('source_id')}  sink={topo.get('sink_id')})")
            for node, nbrs in adj.items():
                if nbrs:
                    print(f"    {node} -> {', '.join(nbrs)}")

        # Train
        print(f"\n  --- Training ({train_s.get('episode_count', '?')} episodes) ---")
        tm = train_s.get("metrics", {})
        print_metrics_table("REAL train", tm)
        print(f"  mean_delivered_packets : {train_s.get('mean_delivered_packets')}")
        print(f"  mean_dropped_packets   : {train_s.get('mean_dropped_packets')}")
        print(f"  mean_feedback_events   : {train_s.get('mean_feedback_events')}")
        print(f"  occupied_prediction_rate : {train_s.get('occupied_prediction_rate')}")

        # Eval
        print(f"\n  --- Evaluation ({eval_s.get('episode_count', '?')} episodes) ---")
        em = eval_s.get("metrics", {})
        print_metrics_table("REAL eval ", em)
        print(f"  mean_delivered_packets : {eval_s.get('mean_delivered_packets')}")
        print(f"  mean_dropped_packets   : {eval_s.get('mean_dropped_packets')}")
        print(f"  mean_feedback_events   : {eval_s.get('mean_feedback_events')}")
        print(f"  occupied_prediction_rate : {eval_s.get('occupied_prediction_rate')}")

        # System
        if sys_s:
            print(f"\n  --- System ---")
            for key in ("cycles", "injected_packets", "delivered_packets",
                        "delivery_ratio", "drop_ratio", "mean_latency",
                        "mean_route_cost", "mean_feedback_award", "node_atp_total"):
                val = sys_s.get(key)
                if val is not None:
                    try:
                        print(f"  {key:<22} : {float(val):.4f}")
                    except (ValueError, TypeError):
                        print(f"  {key:<22} : {val}")

    # Aggregate comparison
    if aggregate:
        print_header("Aggregate Comparison")
        cols = ["train_accuracy", "eval_accuracy", "eval_f1",
                "eval_mean_dropped", "eval_mean_feedback_events"]
        header = f"  {'Condition':<35}" + "".join(f"{c:>12}" for c in cols)
        print(header)
        print("  " + "-" * (len(header) - 2))
        for cond_name, agg in aggregate.items():
            row = f"  {cond_name:<35}"
            for c in cols:
                val = agg.get(c)
                row += _fmt(float(val) if val is not None else None, width=12)
            print(row)


def write_summary_v2(data: dict, out_path) -> None:
    title     = data.get("title", "Unknown experiment")
    timestamp = data.get("timestamp", "?")
    seed      = data.get("selector_seed", "?")
    elapsed   = data.get("elapsed_seconds", "?")
    aggregate = data.get("aggregate", {})
    conditions = data.get("conditions", [])

    lines = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"**Timestamp:** `{timestamp}`  ")
    lines.append(f"**Selector seed:** {seed}  ")
    lines.append(f"**Elapsed:** {elapsed}s  ")
    lines.append(f"**Conditions:** {len(conditions)}")
    lines.append("")

    # Aggregate table
    lines.append("## Aggregate Comparison")
    lines.append("")
    lines.append("| Condition | Tr Acc | Ev Acc | Ev F1 | Ev Dropped | Ev Fdbk Events |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for cond_name, agg in aggregate.items():
        def _v(k): return round(float(agg.get(k, 0)), 4)
        lines.append(
            f"| {cond_name} "
            f"| {_v('train_accuracy')} "
            f"| {_v('eval_accuracy')} "
            f"| {_v('eval_f1')} "
            f"| {_v('eval_mean_dropped')} "
            f"| {_v('eval_mean_feedback_events')} |"
        )
    lines.append("")

    # Per-condition sections
    for cond in conditions:
        name   = cond.get("name", "?")
        desc   = cond.get("description", "")
        result = cond.get("result", {})
        if not result:
            continue

        v2cfg   = result.get("v2_config", result.get("config", {}))
        train_s = result.get("train_summary", {})
        eval_s  = result.get("eval_summary", {})
        sys_s   = result.get("system_summary", {})

        lines.append(f"## Condition: {name}")
        lines.append("")
        lines.append(f"*{desc}*")
        lines.append("")

        if v2cfg:
            lines.append("**Config:**")
            lines.append("")
            lines.append("| Param | Value |")
            lines.append("|---|---|")
            for k in ("eval_feedback_fraction", "carryover_mode", "context_bit_source",
                      "feedback_amount", "packet_ttl", "forward_drain_cycles",
                      "feedback_drain_cycles"):
                lines.append(f"| {k} | {v2cfg.get(k, '?')} |")
            lines.append(f"| train_episodes | {result.get('train_episode_count', '?')} |")
            lines.append(f"| eval_episodes  | {result.get('eval_episode_count', '?')} |")
            if result.get("co2_training_median") is not None:
                lines.append(f"| co2_training_median | {result['co2_training_median']} |")
            lines.append("")

        for phase_label, summary in [("Training", train_s), ("Evaluation", eval_s)]:
            m = summary.get("metrics", {})
            lines.append(f"**{phase_label} metrics** ({summary.get('episode_count', '?')} episodes):")
            lines.append("")
            lines.append(_md_metrics_table(m))
            lines.append("")
            for k in ("mean_delivered_packets", "mean_dropped_packets",
                      "mean_feedback_events", "occupied_prediction_rate"):
                lines.append(f"- **{k}**: {summary.get(k)}")
            lines.append("")

        if sys_s:
            lines.append("**System summary:**")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|---|---|")
            for k in ("cycles", "injected_packets", "delivered_packets",
                      "delivery_ratio", "drop_ratio", "mean_latency",
                      "mean_route_cost", "mean_feedback_award", "node_atp_total"):
                val = sys_s.get(k)
                if val is not None:
                    try:
                        lines.append(f"| {k} | {float(val):.4f} |")
                    except (ValueError, TypeError):
                        lines.append(f"| {k} | {val} |")
            lines.append("")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[summary] Written to: {out_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Analyze experiment JSON outputs: occupancy v1 comparison harness, "
            "v2 multi-condition runs, and v3 session carryover JSON."
        )
    )
    parser.add_argument("json_path", help="Path to the experiment JSON file")
    parser.add_argument(
        "--rolling", type=int, default=50,
        help="Rolling-average window for accuracy/packet plots (default: 50)"
    )
    parser.add_argument(
        "--no-plots", action="store_true",
        help="Skip matplotlib plots, print text summary only"
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Only show results for the given selector_seed"
    )
    parser.add_argument(
        "--summary", nargs="?", const=True, default=None, metavar="OUTPUT_PATH",
        help="Write a markdown summary. Omit a path to auto-name it next to the JSON."
    )
    args = parser.parse_args()

    path = Path(args.json_path)
    if not path.exists():
        print(f"[error] File not found: {path}")
        sys.exit(1)

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if is_v3_format(data):
        analyze_v3(data, args)
    elif is_v2_format(data):
        analyze_v2(data, args)
    elif is_laminated_phase8_format(data):
        print_header("Laminated Phase 8 (summary-only view)")
        print(f"  title     : {data.get('title', '?')}")
        print(f"  timestamp : {data.get('timestamp', '?')}")
        result = data.get("result") or {}
        baseline = result.get("baseline_summary") or {}
        lam = result.get("laminated_run") or {}
        print(f"  benchmark : {result.get('benchmark_id', '?')}")
        print(f"  task_key  : {result.get('task_key', '?')}")
        print(f"  mode      : {result.get('mode', '?')}")
        print(f"  seed      : {result.get('seed', '?')}")
        print(f"\n  Baseline:")
        for key in ("cycles", "delivered_packets", "delivery_ratio", "mean_latency", "mean_hops", "exact_matches", "mean_bit_accuracy", "total_action_cost"):
            if key in baseline:
                print(f"    {key:<18} : {baseline.get(key)}")
        print(f"\n  Laminated:")
        print(f"    final_decision      : {lam.get('final_decision')}")
        print(f"    slices_run          : {len(lam.get('slice_summaries') or [])}")
    else:
        analyze(data, args)

    if args.summary is not None:
        if args.summary is True:
            out_path = path.with_name(path.stem + "_summary.md")
        else:
            out_path = Path(args.summary)
        if is_v3_format(data):
            write_summary_v3(data, out_path)
        elif is_v2_format(data):
            write_summary_v2(data, out_path)
        elif is_laminated_phase8_format(data):
            write_summary_laminated_phase8(data, out_path)
        else:
            write_summary(data, out_path)


if __name__ == "__main__":
    main()
