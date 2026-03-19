"""
analyze_experiment_output.py
----------------------------
Quick analysis of occupancy bridge (and similar) experiment JSON outputs.

Usage:
    python analyze_experiment_output.py <path_to_json>
    python analyze_experiment_output.py <path_to_json> --rolling 50
    python analyze_experiment_output.py <path_to_json> --no-plots
    python analyze_experiment_output.py <path_to_json> --seed 13
    python analyze_experiment_output.py <path_to_json> --summary
    python analyze_experiment_output.py <path_to_json> --summary path/to/output.md

Produces:
    - A printed summary of baseline vs REAL metrics per seed
    - Rolling accuracy curves for train and eval phases
    - Packet delivery / drop statistics
    - Feedback dynamics over training
    - Confidence distribution histogram
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
        description="Analyze occupancy bridge experiment JSON outputs."
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

    if is_v2_format(data):
        analyze_v2(data, args)
    else:
        analyze(data, args)

    if args.summary is not None:
        if args.summary is True:
            out_path = path.with_name(path.stem + "_summary.md")
        else:
            out_path = Path(args.summary)
        if is_v2_format(data):
            write_summary_v2(data, out_path)
        else:
            write_summary(data, out_path)


if __name__ == "__main__":
    main()
