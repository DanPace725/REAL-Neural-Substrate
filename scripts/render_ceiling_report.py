from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


SVG_WIDTH = 1100
SVG_HEIGHT = 420


def _load_result(path: Path) -> Dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return dict(payload.get("result", payload))


def _points(result: Dict[str, object]) -> List[Dict[str, object]]:
    return sorted(
        list(result["cold_start"]["points"]),
        key=lambda point: (int(point["family_order"]), int(point["difficulty_index"])),
    )


def _aggregates(result: Dict[str, object]) -> List[Dict[str, object]]:
    return list(result["cold_start"]["aggregates"])


def _aggregate_lookup(result: Dict[str, object]) -> Dict[tuple[str, str], Dict[str, object]]:
    return {
        (aggregate["benchmark_id"], aggregate["method_id"]): aggregate
        for aggregate in _aggregates(result)
    }


def _curve_svg(result: Dict[str, object]) -> str:
    lookup = _aggregate_lookup(result)
    points = _points(result)
    families = sorted({point["family_id"] for point in points})
    panel_width = SVG_WIDTH // max(len(families), 1)
    lines: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}">',
        '<rect width="100%" height="100%" fill="#f7f4eb"/>',
        '<style>text{font-family:Georgia,serif;fill:#1f1d1a}.small{font-size:12px}.label{font-size:15px;font-weight:bold}</style>',
        '<text x="28" y="30" class="label">Ceiling Curves by Family (Mean Bit Accuracy)</text>',
    ]
    colors = {
        "fixed-visible": "#115f5f",
        "fixed-latent": "#c65d2e",
        "growth-visible": "#7c2732",
        "best-nn": "#272343",
    }
    for family_index, family_id in enumerate(families):
        family_points = [point for point in points if point["family_id"] == family_id]
        x0 = family_index * panel_width + 40
        x1 = (family_index + 1) * panel_width - 30
        y0 = 60
        y1 = SVG_HEIGHT - 40
        lines.append(f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" fill="none" stroke="#c9c2b3"/>')
        lines.append(f'<text x="{x0}" y="52" class="label">Family {family_id}</text>')
        for tick in range(6):
            value = tick / 5
            y = y1 - (y1 - y0) * value
            lines.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="#e3ddcf"/>')
            lines.append(f'<text x="{x0 - 26}" y="{y + 4:.1f}" class="small">{value:.1f}</text>')
        for method_id in ("fixed-visible", "fixed-latent", "growth-visible"):
            poly_points: List[str] = []
            for point_index, point in enumerate(family_points):
                x = x0 + (x1 - x0) * (point_index + 0.5) / max(len(family_points), 1)
                y = y1 - (y1 - y0) * float(lookup[(point["benchmark_id"], method_id)]["mean_bit_accuracy"])
                poly_points.append(f"{x:.1f},{y:.1f}")
                lines.append(f'<text x="{x - 10:.1f}" y="{y1 + 18}" class="small">{point["benchmark_id"]}</text>')
            lines.append(f'<polyline fill="none" stroke="{colors[method_id]}" stroke-width="3" points="{" ".join(poly_points)}"/>')
        best_nn_points: List[str] = []
        for point_index, point in enumerate(family_points):
            x = x0 + (x1 - x0) * (point_index + 0.5) / max(len(family_points), 1)
            best = lookup[(point["benchmark_id"], point["best_nn_method_id"])]
            y = y1 - (y1 - y0) * float(best["mean_bit_accuracy"])
            best_nn_points.append(f"{x:.1f},{y:.1f}")
        lines.append(f'<polyline fill="none" stroke="{colors["best-nn"]}" stroke-width="3" stroke-dasharray="6 4" points="{" ".join(best_nn_points)}"/>')
    legend_x = SVG_WIDTH - 260
    legend_y = 34
    for index, (label, color) in enumerate(
        (
            ("fixed-visible", colors["fixed-visible"]),
            ("fixed-latent", colors["fixed-latent"]),
            ("growth-visible", colors["growth-visible"]),
            ("best NN", colors["best-nn"]),
        )
    ):
        y = legend_y + index * 18
        dash = ' stroke-dasharray="6 4"' if label == "best NN" else ""
        lines.append(f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 24}" y2="{y}" stroke="{color}" stroke-width="3"{dash}/>')
        lines.append(f'<text x="{legend_x + 32}" y="{y + 4}" class="small">{label}</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def _heatmap_svg(result: Dict[str, object]) -> str:
    points = _points(result)
    lookup = _aggregate_lookup(result)
    cell_w = 150
    cell_h = 34
    rows = len(points)
    cols = 3
    width = 120 + cols * cell_w
    height = 90 + rows * cell_h
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f4eb"/>',
        '<style>text{font-family:Georgia,serif;fill:#1f1d1a}.small{font-size:12px}.label{font-size:15px;font-weight:bold}</style>',
        '<text x="20" y="28" class="label">REAL vs Best NN Heatmap (Bit-Accuracy Delta)</text>',
    ]
    methods = ("fixed-visible", "fixed-latent", "growth-visible")
    for col_index, method_id in enumerate(methods):
        lines.append(f'<text x="{120 + col_index * cell_w + 8}" y="58" class="small">{method_id}</text>')
    for row_index, point in enumerate(points):
        y = 70 + row_index * cell_h
        lines.append(f'<text x="20" y="{y + 22}" class="small">{point["benchmark_id"]}</text>')
        best = lookup[(point["benchmark_id"], point["best_nn_method_id"])]
        best_value = float(best["mean_bit_accuracy"])
        for col_index, method_id in enumerate(methods):
            value = best_value - float(lookup[(point["benchmark_id"], method_id)]["mean_bit_accuracy"])
            intensity = min(max(value / 0.25, 0.0), 1.0)
            red = int(253 - 78 * intensity)
            green = int(243 - 146 * intensity)
            blue = int(227 - 162 * intensity)
            x = 120 + col_index * cell_w
            lines.append(f'<rect x="{x}" y="{y}" width="{cell_w - 8}" height="{cell_h - 6}" fill="rgb({red},{green},{blue})" stroke="#c9c2b3"/>')
            lines.append(f'<text x="{x + 10}" y="{y + 22}" class="small">+{value:.3f}</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def _frontier_markdown(result: Dict[str, object]) -> str:
    frontier = result["cold_start"]["frontier"]
    lines = ["# Ceiling Frontier Summary", ""]
    lines.append(f"Earliest global ceiling: `{frontier.get('earliest_global_ceiling')}`")
    lines.append("")
    lines.append("| Family | Ceiling Band | Last Pre-Collapse |")
    lines.append("|---|---|---|")
    for family_id, payload in sorted(frontier["families"].items()):
        lines.append(
            f"| {family_id} | {payload.get('ceiling_band') or '-'} | {payload.get('last_pre_collapse') or '-'} |"
        )
    lines.append("")
    lines.append("## Best NN By Band")
    lines.append("")
    for family_id, payload in sorted(frontier["families"].items()):
        lines.append(f"### Family {family_id}")
        lines.append("")
        lines.append("| Benchmark | Best NN |")
        lines.append("|---|---|")
        for benchmark_id, method_id in payload["best_nn_by_band"].items():
            lines.append(f"| {benchmark_id} | {method_id or '-'} |")
        lines.append("")
    return "\n".join(lines)


def _digest_markdown(result: Dict[str, object]) -> str:
    frontier = result["cold_start"]["frontier"]
    transfer_ids = result["cold_start"].get("transfer_point_ids") or []
    lines = [
        "# Ceiling Benchmark Digest",
        "",
        f"Benchmarks run: {', '.join(item['benchmark_id'] for item in result['suite'])}",
        f"Earliest global ceiling: `{frontier.get('earliest_global_ceiling')}`",
        f"Transfer slice: {', '.join(transfer_ids) if transfer_ids else 'not run'}",
        "",
        "Use `ceiling_curves.svg` for family trajectories, `real_vs_best_nn_heatmap.svg` for the REAL-vs-NN gap, and `frontier_summary.md` for the collapse table.",
    ]
    return "\n".join(lines)


def render_ceiling_report(
    manifest_or_result: Path | str | Dict[str, object],
    *,
    output_dir: Path | str,
) -> Dict[str, str]:
    if isinstance(manifest_or_result, (str, Path)):
        result = _load_result(Path(manifest_or_result))
    else:
        result = manifest_or_result
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    curve_path = out_dir / "ceiling_curves.svg"
    heatmap_path = out_dir / "real_vs_best_nn_heatmap.svg"
    frontier_path = out_dir / "frontier_summary.md"
    digest_path = out_dir / "ceiling_results_digest.md"

    curve_path.write_text(_curve_svg(result), encoding="utf-8")
    heatmap_path.write_text(_heatmap_svg(result), encoding="utf-8")
    frontier_path.write_text(_frontier_markdown(result), encoding="utf-8")
    digest_path.write_text(_digest_markdown(result), encoding="utf-8")

    return {
        "ceiling_curves": str(curve_path),
        "heatmap": str(heatmap_path),
        "frontier_summary": str(frontier_path),
        "digest": str(digest_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Render SVG/Markdown report artifacts for a ceiling benchmark manifest")
    parser.add_argument("manifest", type=str, help="path to the benchmark manifest JSON")
    parser.add_argument("--output-dir", type=str, default="docs/experiment_outputs/ceiling_report")
    args = parser.parse_args()

    written = render_ceiling_report(args.manifest, output_dir=args.output_dir)
    print(json.dumps(written, indent=2))


if __name__ == "__main__":
    main()
