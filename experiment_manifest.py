from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def _default_title(harness: str) -> str:
    timestamp_local = datetime.now().strftime("%Y-%m-%d %H%M")
    title_suffix = harness.replace("_", " ")
    return f"{timestamp_local} - {title_suffix}"


def build_run_manifest(
    *,
    harness: str,
    seeds: Iterable[int],
    scenarios: Iterable[str],
    result: dict[str, object],
    title: str | None = None,
    latent_context: bool | None = None,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    manifest: dict[str, object] = {
        "title": title or _default_title(harness),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "harness": harness,
        "seeds": list(seeds),
        "scenarios": list(scenarios),
        "result": result,
    }
    if latent_context is not None:
        manifest["latent_context"] = latent_context
    if metadata:
        manifest["metadata"] = metadata
    return manifest


def write_run_manifest(
    output_path: Path | str,
    manifest: dict[str, object],
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    return path
