from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from phase8.environment import LATENT_CONTEXT_PROMOTION_THRESHOLD
from scripts.diagnose_benchmark_node_probe import evaluate_benchmark_node_probe

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIGURE_DIR = ROOT / "docs" / "reports" / "paper_figures"
DEFAULT_OCCUPANCY_BRIDGE_JSON = ROOT / "docs" / "experiment_outputs" / "occupancy_bridge_seed13_20260319.json"
DEFAULT_OCCUPANCY_V2_JSON = ROOT / "docs" / "experiment_outputs" / "occupancy_real_v2_seed13_20260319.json"
DEFAULT_OCCUPANCY_V3_SEED_JSON = ROOT / "docs" / "experiment_outputs" / "v3_best_real_seed13.json"
DEFAULT_OCCUPANCY_V3_SWEEP_JSON = ROOT / "docs" / "experiment_outputs" / "v3_best_real_sweep_13_23_37.json"
DEFAULT_C_NODE_BEFORE_JSON = ROOT / "docs" / "experiment_outputs" / "c_node_probe_c3_taskb_taskc_growth_latent_seed13_20260318.json"
DEFAULT_C_NODE_AFTER_JSON = ROOT / "docs" / "experiment_outputs" / "c_node_probe_c3_taskb_taskc_growth_latent_seed13_postroutegate_20260318.json"

TRANSFORM_ORDER = ("identity", "rotate_left_1", "xor_mask_1010", "xor_mask_0101")
TRANSFORM_LABELS = {
    "identity": "identity",
    "rotate_left_1": "rotate_left_1",
    "xor_mask_1010": "xor_1010",
    "xor_mask_0101": "xor_0101",
}
TRANSFORM_COLORS = {
    "identity": "#4C7A5A",
    "rotate_left_1": "#C96B1B",
    "xor_mask_1010": "#C23B22",
    "xor_mask_0101": "#2D6A9F",
}


def _plt():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        return plt
    except ImportError as exc:
        raise RuntimeError(
            "matplotlib is required to render paper figures. "
            "Install it in the current environment first."
        ) from exc


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _best_transform_name(hints: dict[str, Any] | None) -> str | None:
    best_name = None
    best_value = 0.0
    for name, value in dict(hints or {}).items():
        value_f = float(value)
        if value_f > best_value:
            best_name = str(name)
            best_value = value_f
    return best_name


def occupancy_progress_points(
    *,
    bridge_json: Path = DEFAULT_OCCUPANCY_BRIDGE_JSON,
    v2_json: Path = DEFAULT_OCCUPANCY_V2_JSON,
    v3_seed_json: Path = DEFAULT_OCCUPANCY_V3_SEED_JSON,
    v3_sweep_json: Path = DEFAULT_OCCUPANCY_V3_SWEEP_JSON,
) -> dict[str, Any]:
    bridge = _load_json(bridge_json)
    v2 = _load_json(v2_json)
    v3_seed = _load_json(v3_seed_json)
    v3_sweep = _load_json(v3_sweep_json)

    baseline = bridge["result"]["baseline"]["metrics"]
    v1_real = bridge["result"]["runs"][0]["real"]["eval_summary"]["metrics"]
    v2_conditions = {
        str(item["name"]): item["result"]
        for item in v2["conditions"]
    }
    v2_best_name, v2_best_result = max(
        v2_conditions.items(),
        key=lambda item: float(item[1]["eval_summary"]["metrics"]["f1"]),
    )
    v3_protocols = v3_seed["eval_protocols"]
    fresh = v3_protocols["fresh_session_eval"]
    sweep_summary = v3_sweep["aggregate"]

    return {
        "f1_points": [
            {"label": "MLP baseline", "value": float(baseline["f1"])},
            {"label": "REAL V1", "value": float(v1_real["f1"])},
            {
                "label": f"REAL V2 ({v2_best_name})",
                "value": float(v2_best_result["eval_summary"]["metrics"]["f1"]),
            },
            {"label": "REAL V3 cold", "value": float(fresh["cold_summary"]["metrics"]["f1"])},
            {"label": "REAL V3 warm", "value": float(fresh["warm_summary"]["metrics"]["f1"])},
        ],
        "efficiency_points": [
            {
                "label": f"seed {int(item['selector_seed'])}",
                "value": float(item["mean_efficiency_ratio"]),
            }
            for item in v3_sweep["seed_summaries"]
        ],
        "efficiency_mean": float(sweep_summary["mean_efficiency_ratio"]),
        "f1_gap_v3_vs_mlp": round(
            float(baseline["f1"]) - float(fresh["warm_summary"]["metrics"]["f1"]),
            4,
        ),
    }


def render_occupancy_progress_chart(
    output_path: Path,
    *,
    bridge_json: Path = DEFAULT_OCCUPANCY_BRIDGE_JSON,
    v2_json: Path = DEFAULT_OCCUPANCY_V2_JSON,
    v3_seed_json: Path = DEFAULT_OCCUPANCY_V3_SEED_JSON,
    v3_sweep_json: Path = DEFAULT_OCCUPANCY_V3_SWEEP_JSON,
) -> Path:
    plt = _plt()
    payload = occupancy_progress_points(
        bridge_json=bridge_json,
        v2_json=v2_json,
        v3_seed_json=v3_seed_json,
        v3_sweep_json=v3_sweep_json,
    )
    _ensure_parent(output_path)

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.5), constrained_layout=True)

    left = axes[0]
    f1_points = payload["f1_points"]
    x = list(range(len(f1_points)))
    y = [point["value"] for point in f1_points]
    colors = ["#222222", "#8F3B76", "#3B6EA5", "#6C757D", "#1B7F5A"]
    left.bar(x, y, color=colors, width=0.72)
    left.set_ylim(0.0, 1.02)
    left.set_ylabel("Eval F1")
    left.set_title("Occupancy progression")
    left.set_xticks(x)
    left.set_xticklabels([point["label"] for point in f1_points], rotation=20, ha="right")
    for idx, value in enumerate(y):
        left.text(idx, value + 0.015, f"{value:.3f}", ha="center", va="bottom", fontsize=9)
    left.text(
        0.02,
        0.96,
        f"V3 warm vs MLP gap: {payload['f1_gap_v3_vs_mlp']:.3f}",
        transform=left.transAxes,
        fontsize=9,
        va="top",
        bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "#CCCCCC"},
    )

    right = axes[1]
    eff_points = payload["efficiency_points"]
    eff_x = list(range(len(eff_points)))
    eff_y = [point["value"] for point in eff_points]
    right.bar(eff_x, eff_y, color="#4F7CAC", width=0.6)
    right.axhline(1.0, color="#444444", linestyle="--", linewidth=1.0, label="parity")
    right.axhline(
        payload["efficiency_mean"],
        color="#C96B1B",
        linestyle="-",
        linewidth=1.5,
        label="sweep mean",
    )
    low = min(min(eff_y), payload["efficiency_mean"], 1.0)
    high = max(max(eff_y), payload["efficiency_mean"], 1.0)
    pad = max(0.01, (high - low) * 0.45)
    right.set_ylim(low - pad, high + pad)
    right.set_ylabel("Warm/cold efficiency ratio")
    right.set_title("V3 fresh-session transfer efficiency")
    right.set_xticks(eff_x)
    right.set_xticklabels([point["label"] for point in eff_points])
    for idx, value in enumerate(eff_y):
        right.text(idx, value + 0.0015, f"{value:.4f}", ha="center", va="bottom", fontsize=9)
    right.legend(loc="lower right")

    fig.suptitle("REAL occupancy: performance progression and transfer efficiency", fontsize=14)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output_path


def c_node_case_points(
    *,
    before_json: Path = DEFAULT_C_NODE_BEFORE_JSON,
    after_json: Path = DEFAULT_C_NODE_AFTER_JSON,
    task_key: str = "task_c",
    node_id: str = "n3",
) -> dict[str, Any]:
    before = _load_json(before_json)
    after = _load_json(after_json)
    before_node = before["result"]["task_runs"][task_key]["nodes"][node_id]
    after_node = after["result"]["task_runs"][task_key]["nodes"][node_id]
    return {
        "task_key": task_key,
        "node_id": node_id,
        "threshold": float(LATENT_CONTEXT_PROMOTION_THRESHOLD),
        "before": before_node,
        "after": after_node,
    }


def _render_node_case_axis(ax, timeline: list[dict[str, Any]], *, title: str, threshold: float) -> None:
    cycles = [int(item["cycle"]) for item in timeline]
    latent_conf = [float(item.get("latent_context_confidence", 0.0)) for item in timeline]
    promotion = [float(item.get("context_promotion_ready", 0.0)) for item in timeline]
    ax.plot(cycles, latent_conf, color="#2D6A9F", linewidth=2.0, label="latent confidence")
    ax.plot(cycles, promotion, color="#888888", linewidth=1.3, linestyle="--", label="promotion ready")
    ax.axhline(threshold, color="#C23B22", linestyle=":", linewidth=1.4, label="promotion threshold")
    ax.set_ylim(-0.02, 1.05)
    ax.set_ylabel("Confidence")
    ax.set_title(title)

    twin = ax.twinx()
    transform_to_y = {name: idx for idx, name in enumerate(TRANSFORM_ORDER)}
    for name in TRANSFORM_ORDER:
        chosen_cycles = [int(item["cycle"]) for item in timeline if item.get("route_transform") == name]
        chosen_y = [transform_to_y[name]] * len(chosen_cycles)
        if chosen_cycles:
            twin.scatter(
                chosen_cycles,
                chosen_y,
                color=TRANSFORM_COLORS[name],
                s=28,
                label=TRANSFORM_LABELS[name],
                zorder=4,
            )
    twin.set_ylim(-0.5, len(TRANSFORM_ORDER) - 0.5)
    twin.set_yticks(list(transform_to_y.values()))
    twin.set_yticklabels([TRANSFORM_LABELS[name] for name in TRANSFORM_ORDER])
    twin.set_ylabel("Chosen transform")
    ax.set_xlabel("Cycle")


def render_c_node_gate_chart(
    output_path: Path,
    *,
    before_json: Path = DEFAULT_C_NODE_BEFORE_JSON,
    after_json: Path = DEFAULT_C_NODE_AFTER_JSON,
    task_key: str = "task_c",
    node_id: str = "n3",
) -> Path:
    plt = _plt()
    payload = c_node_case_points(
        before_json=before_json,
        after_json=after_json,
        task_key=task_key,
        node_id=node_id,
    )
    _ensure_parent(output_path)

    fig, axes = plt.subplots(2, 1, figsize=(12.0, 8.0), sharex=True, constrained_layout=True)
    _render_node_case_axis(
        axes[0],
        payload["before"]["timeline"],
        title=f"{task_key} {node_id} before downstream latent gate",
        threshold=payload["threshold"],
    )
    _render_node_case_axis(
        axes[1],
        payload["after"]["timeline"],
        title=f"{task_key} {node_id} after downstream latent gate",
        threshold=payload["threshold"],
    )

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.99))
    fig.suptitle("C-node interpretability case: latent confidence versus chosen transform", fontsize=14)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output_path


def b2_guidance_points(
    *,
    seed: int = 13,
    benchmark_id: str = "B2",
    task_key: str = "task_a",
    method_id: str = "self-selected",
    cycle_limit: int = 40,
) -> dict[str, Any]:
    result = evaluate_benchmark_node_probe(
        seed=seed,
        benchmark_id=benchmark_id,
        task_keys=(task_key,),
        method_id=method_id,
        cycle_limit=cycle_limit,
    )
    task_run = result["task_runs"][task_key]
    source_id = str(task_run["focus_nodes"][0])
    node_payload = task_run["nodes"][source_id]
    summary = node_payload["summary"]
    timeline = node_payload["timeline"]
    route_records = [item for item in timeline if item.get("route_transform") is not None]

    rendered = []
    for item in route_records:
        strongest = _best_transform_name(item.get("pre_source_sequence_transform_hint"))
        rendered.append(
            {
                "cycle": int(item["cycle"]),
                "hint_rotate_left_1": float(item["pre_source_sequence_transform_hint"].get("rotate_left_1", 0.0)),
                "hint_xor_mask_1010": float(item["pre_source_sequence_transform_hint"].get("xor_mask_1010", 0.0)),
                "hint_xor_mask_0101": float(item["pre_source_sequence_transform_hint"].get("xor_mask_0101", 0.0)),
                "latent_capability_enabled": float(item.get("latent_capability_enabled", 0.0)),
                "route_transform": str(item.get("route_transform")),
                "strongest_hint_transform": strongest,
                "matched_hint": strongest is not None and str(item.get("route_transform")) == strongest,
            }
        )

    return {
        "result": result,
        "source_id": source_id,
        "summary": summary,
        "records": rendered,
    }


def render_b2_guidance_chart(
    output_path: Path,
    *,
    seed: int = 13,
    benchmark_id: str = "B2",
    task_key: str = "task_a",
    method_id: str = "self-selected",
    cycle_limit: int = 40,
) -> Path:
    plt = _plt()
    payload = b2_guidance_points(
        seed=seed,
        benchmark_id=benchmark_id,
        task_key=task_key,
        method_id=method_id,
        cycle_limit=cycle_limit,
    )
    records = payload["records"]
    _ensure_parent(output_path)

    fig, axes = plt.subplots(2, 1, figsize=(12.0, 8.0), sharex=True, constrained_layout=True)

    cycles = [item["cycle"] for item in records]
    axes[0].plot(cycles, [item["hint_rotate_left_1"] for item in records], color=TRANSFORM_COLORS["rotate_left_1"], linewidth=2.0, label="hint rotate_left_1")
    axes[0].plot(cycles, [item["hint_xor_mask_1010"] for item in records], color=TRANSFORM_COLORS["xor_mask_1010"], linewidth=2.0, label="hint xor_1010")
    axes[0].plot(cycles, [item["hint_xor_mask_0101"] for item in records], color=TRANSFORM_COLORS["xor_mask_0101"], linewidth=2.0, label="hint xor_0101")
    axes[0].fill_between(
        cycles,
        0.0,
        1.0,
        where=[item["latent_capability_enabled"] >= 0.5 for item in records],
        color="#D9EBD3",
        alpha=0.35,
        transform=axes[0].get_xaxis_transform(),
        label="latent capability enabled",
    )
    axes[0].set_ylim(0.0, 1.02)
    axes[0].set_ylabel("Hint strength")
    axes[0].set_title("B2 source sequence guidance")
    axes[0].legend(loc="upper right")

    transform_to_y = {name: idx for idx, name in enumerate(TRANSFORM_ORDER)}
    matched_x = [item["cycle"] for item in records if item["matched_hint"]]
    matched_y = [transform_to_y[item["route_transform"]] for item in records if item["matched_hint"]]
    mismatched_x = [item["cycle"] for item in records if not item["matched_hint"]]
    mismatched_y = [transform_to_y[item["route_transform"]] for item in records if not item["matched_hint"]]
    axes[1].scatter(matched_x, matched_y, color="#1B7F5A", s=34, label="matched strongest hint")
    axes[1].scatter(mismatched_x, mismatched_y, color="#C23B22", s=34, label="mismatched strongest hint")
    axes[1].set_yticks(list(transform_to_y.values()))
    axes[1].set_yticklabels([TRANSFORM_LABELS[name] for name in TRANSFORM_ORDER])
    axes[1].set_ylabel("Chosen transform")
    axes[1].set_xlabel("Cycle")
    axes[1].set_title(
        "Source route-transform choices "
        f"(match rate {float(payload['summary']['pre_sequence_guidance_match_rate']):.2f})"
    )
    axes[1].legend(loc="upper right")

    fig.suptitle("B2 interpretability case: source guidance versus chosen action", fontsize=14)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output_path
