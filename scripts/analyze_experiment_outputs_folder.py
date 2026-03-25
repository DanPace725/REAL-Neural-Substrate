"""
analyze_experiment_outputs_folder.py
-----------------------------------
Batch analyzer for docs/experiment_outputs JSON artifacts.

It reads each JSON, detects its format (occupancy v2/v3, laminated_phase8, or
legacy baseline-vs-REAL), and writes a Markdown summary next to the JSON as
`<stem>_summary.md`.

Usage:
  python -m scripts.analyze_experiment_outputs_folder
  python -m scripts.analyze_experiment_outputs_folder --dir docs/experiment_outputs
  python -m scripts.analyze_experiment_outputs_folder --pattern "*laminated*.json"
  python -m scripts.analyze_experiment_outputs_folder --skip-existing
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.analyze_experiment_output import (
    is_laminated_phase8_format,
    is_v2_format,
    is_v3_format,
    write_summary,
    write_summary_laminated_phase8,
    write_summary_v2,
    write_summary_v3,
)


def _iter_json_files(root: Path, pattern: str) -> list[Path]:
    # Non-recursive by default (experiment_outputs is flat in this repo).
    return sorted([p for p in root.glob(pattern) if p.is_file() and p.suffix.lower() == ".json"])


def _write_summary_for_file(path: Path, skip_existing: bool) -> tuple[bool, str]:
    out_path = path.with_name(path.stem + "_summary.md")
    if skip_existing and out_path.exists():
        return False, f"[skip] exists: {out_path.name}"

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"[error] read/parse failed: {path.name} ({e})"

    try:
        if is_v3_format(data):
            write_summary_v3(data, out_path)
        elif is_v2_format(data):
            write_summary_v2(data, out_path)
        elif is_laminated_phase8_format(data):
            write_summary_laminated_phase8(data, out_path)
        else:
            write_summary(data, out_path)
    except Exception as e:
        return False, f"[error] summary failed: {path.name} ({e})"

    return True, f"[ok] wrote: {out_path.name}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch write Markdown summaries for experiment JSON outputs.")
    parser.add_argument(
        "--dir",
        default="docs/experiment_outputs",
        help="Directory containing experiment JSON outputs (default: docs/experiment_outputs)",
    )
    parser.add_argument(
        "--pattern",
        default="*.json",
        help="Glob pattern within --dir (default: *.json)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip writing summary if <stem>_summary.md already exists",
    )
    args = parser.parse_args()

    root = Path(args.dir)
    if not root.exists():
        print(f"[error] directory not found: {root}")
        raise SystemExit(2)

    json_files = _iter_json_files(root, args.pattern)
    if not json_files:
        print(f"[info] no matching JSON files in {root} (pattern={args.pattern!r})")
        return

    ok = 0
    for p in json_files:
        wrote, msg = _write_summary_for_file(p, skip_existing=args.skip_existing)
        print(msg)
        if wrote:
            ok += 1

    print(f"[done] {ok}/{len(json_files)} summaries written")


if __name__ == "__main__":
    # Windows charmap safety
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()

