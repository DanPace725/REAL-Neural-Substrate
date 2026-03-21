from __future__ import annotations

import argparse
from pathlib import Path

from scripts.paper_interpretability_figures import (
    DEFAULT_FIGURE_DIR,
    DEFAULT_OCCUPANCY_BRIDGE_JSON,
    DEFAULT_OCCUPANCY_V2_JSON,
    DEFAULT_OCCUPANCY_V3_SEED_JSON,
    DEFAULT_OCCUPANCY_V3_SWEEP_JSON,
    render_occupancy_progress_chart,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the occupancy progression chart for the paper draft.")
    parser.add_argument("--bridge-json", type=Path, default=DEFAULT_OCCUPANCY_BRIDGE_JSON)
    parser.add_argument("--v2-json", type=Path, default=DEFAULT_OCCUPANCY_V2_JSON)
    parser.add_argument("--v3-seed-json", type=Path, default=DEFAULT_OCCUPANCY_V3_SEED_JSON)
    parser.add_argument("--v3-sweep-json", type=Path, default=DEFAULT_OCCUPANCY_V3_SWEEP_JSON)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_FIGURE_DIR / "occupancy_progress.png",
    )
    args = parser.parse_args()

    output = render_occupancy_progress_chart(
        args.output,
        bridge_json=args.bridge_json,
        v2_json=args.v2_json,
        v3_seed_json=args.v3_seed_json,
        v3_sweep_json=args.v3_sweep_json,
    )
    print(output)


if __name__ == "__main__":
    main()
