from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_SOURCE = (
    Path(__file__).resolve().parents[2] / "model_inputs" / "model_inputs.csv"
)
DEFAULT_OUTPUT_DIR = (
    Path(__file__).resolve().parents[2] / "model_inputs" / "chunks"
)


@dataclass(frozen=True)
class ChunkSummary:
    chunk_index: int
    filename: str
    path: str
    scenario_start: int
    scenario_end: int
    scenario_count: int
    row_count: int
    window_start_min: int
    window_start_max: int


def _chunk_filename(chunk_index: int, scenario_start: int, scenario_end: int) -> str:
    return (
        f"model_inputs_chunk_{chunk_index:03d}"
        f"_scenarios_{scenario_start:04d}_{scenario_end:04d}.csv"
    )


def split_model_inputs(
    source_csv: Path,
    output_dir: Path,
    *,
    scenarios_per_chunk: int,
) -> dict[str, object]:
    if scenarios_per_chunk <= 0:
        raise ValueError("scenarios_per_chunk must be positive")
    if not source_csv.exists():
        raise FileNotFoundError(f"Source CSV not found: {source_csv}")

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"

    total_size = source_csv.stat().st_size
    total_rows = 0
    total_scenarios = 0
    chunk_summaries: list[ChunkSummary] = []

    current_writer: csv.DictWriter[str] | None = None
    current_handle = None
    current_chunk_path: Path | None = None
    current_chunk_rows = 0
    current_chunk_scenarios = 0
    current_chunk_start: int | None = None
    current_chunk_end: int | None = None
    current_window_min: int | None = None
    current_window_max: int | None = None
    previous_scenario: int | None = None
    fieldnames: list[str] | None = None

    def close_chunk() -> None:
        nonlocal current_writer
        nonlocal current_handle
        nonlocal current_chunk_path
        nonlocal current_chunk_rows
        nonlocal current_chunk_scenarios
        nonlocal current_chunk_start
        nonlocal current_chunk_end
        nonlocal current_window_min
        nonlocal current_window_max

        if current_handle is None or current_chunk_path is None:
            return
        current_handle.close()
        final_path = output_dir / _chunk_filename(
            len(chunk_summaries) + 1,
            int(current_chunk_start or 0),
            int(current_chunk_end or 0),
        )
        if current_chunk_path != final_path:
            current_chunk_path.rename(final_path)
            current_chunk_path = final_path
        chunk_summaries.append(
            ChunkSummary(
                chunk_index=len(chunk_summaries) + 1,
                filename=current_chunk_path.name,
                path=str(current_chunk_path),
                scenario_start=int(current_chunk_start or 0),
                scenario_end=int(current_chunk_end or 0),
                scenario_count=int(current_chunk_scenarios),
                row_count=int(current_chunk_rows),
                window_start_min=int(current_window_min or 0),
                window_start_max=int(current_window_max or 0),
            )
        )
        current_writer = None
        current_handle = None
        current_chunk_path = None
        current_chunk_rows = 0
        current_chunk_scenarios = 0
        current_chunk_start = None
        current_chunk_end = None
        current_window_min = None
        current_window_max = None

    with source_csv.open("r", encoding="utf-8", newline="") as source_handle:
        reader = csv.DictReader(source_handle)
        fieldnames = list(reader.fieldnames or [])
        if not fieldnames:
            raise ValueError(f"No CSV headers found in {source_csv}")
        if "scenario_id" not in fieldnames or "window_start_index" not in fieldnames:
            raise ValueError(
                "CSV must include scenario_id and window_start_index columns"
            )

        for row in reader:
            scenario_id = int(row["scenario_id"])
            window_start = int(row["window_start_index"])
            is_new_scenario = scenario_id != previous_scenario

            if is_new_scenario:
                total_scenarios += 1
                should_rotate = (
                    current_handle is not None
                    and current_chunk_scenarios >= scenarios_per_chunk
                )
                if should_rotate:
                    close_chunk()
                if current_handle is None:
                    chunk_index = len(chunk_summaries) + 1
                    current_chunk_start = scenario_id
                    filename = _chunk_filename(
                        chunk_index,
                        scenario_id,
                        scenario_id,
                    )
                    current_chunk_path = output_dir / filename
                    current_handle = current_chunk_path.open(
                        "w",
                        encoding="utf-8",
                        newline="",
                    )
                    current_writer = csv.DictWriter(
                        current_handle,
                        fieldnames=fieldnames,
                        quoting=csv.QUOTE_MINIMAL,
                    )
                    current_writer.writeheader()
                current_chunk_scenarios += 1
                current_chunk_end = scenario_id
                previous_scenario = scenario_id

            if current_writer is None:
                raise RuntimeError("Chunk writer was not initialized")

            current_writer.writerow(row)
            total_rows += 1
            current_chunk_rows += 1
            current_chunk_end = scenario_id
            current_window_min = (
                window_start
                if current_window_min is None
                else min(current_window_min, window_start)
            )
            current_window_max = (
                window_start
                if current_window_max is None
                else max(current_window_max, window_start)
            )

    close_chunk()

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_csv": str(source_csv),
        "source_size_bytes": total_size,
        "total_rows": total_rows,
        "total_scenarios": total_scenarios,
        "scenarios_per_chunk": scenarios_per_chunk,
        "chunk_count": len(chunk_summaries),
        "chunks": [],
    }
    for summary in chunk_summaries:
        payload = asdict(summary)
        payload["source_bytes_estimate"] = round(
            total_size * (summary.row_count / max(total_rows, 1))
        )
        manifest["chunks"].append(payload)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Split the large model_inputs CSV into scenario-aligned chunks without "
            "breaking multiline quoted matrix fields."
        )
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Path to model_inputs.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where chunk CSVs and manifest.json will be written",
    )
    parser.add_argument(
        "--scenarios-per-chunk",
        type=int,
        default=50,
        help="Number of full scenario_id groups to keep in each chunk",
    )
    args = parser.parse_args()

    manifest = split_model_inputs(
        args.source,
        args.output_dir,
        scenarios_per_chunk=args.scenarios_per_chunk,
    )
    print(
        json.dumps(
            {
                "source_csv": manifest["source_csv"],
                "total_rows": manifest["total_rows"],
                "total_scenarios": manifest["total_scenarios"],
                "chunk_count": manifest["chunk_count"],
                "scenarios_per_chunk": manifest["scenarios_per_chunk"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
