from __future__ import annotations

import argparse
from pathlib import Path

from scripts.paper_interpretability_figures import (
    DEFAULT_C_NODE_AFTER_JSON,
    DEFAULT_C_NODE_BEFORE_JSON,
    DEFAULT_FIGURE_DIR,
    render_c_node_gate_chart,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the C-node latent-route interpretability chart.")
    parser.add_argument("--before-json", type=Path, default=DEFAULT_C_NODE_BEFORE_JSON)
    parser.add_argument("--after-json", type=Path, default=DEFAULT_C_NODE_AFTER_JSON)
    parser.add_argument("--task-key", default="task_c")
    parser.add_argument("--node-id", default="n3")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_FIGURE_DIR / "c_node_latent_gate.png",
    )
    args = parser.parse_args()

    output = render_c_node_gate_chart(
        args.output,
        before_json=args.before_json,
        after_json=args.after_json,
        task_key=str(args.task_key),
        node_id=str(args.node_id),
    )
    print(output)


if __name__ == "__main__":
    main()
