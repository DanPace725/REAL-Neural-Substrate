from __future__ import annotations

import argparse
from pathlib import Path

from scripts.paper_interpretability_figures import (
    DEFAULT_FIGURE_DIR,
    render_b2_guidance_chart,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the B2 source-guidance interpretability chart.")
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--benchmark-id", default="B2")
    parser.add_argument("--task-key", default="task_a")
    parser.add_argument("--method-id", default="self-selected")
    parser.add_argument("--cycle-limit", type=int, default=40)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_FIGURE_DIR / "b2_source_guidance.png",
    )
    args = parser.parse_args()

    output = render_b2_guidance_chart(
        args.output,
        seed=int(args.seed),
        benchmark_id=str(args.benchmark_id),
        task_key=str(args.task_key),
        method_id=str(args.method_id),
        cycle_limit=int(args.cycle_limit),
    )
    print(output)


if __name__ == "__main__":
    main()
