from __future__ import annotations

import argparse
import json

from .experiment import ExperimentConfig, run_experiment, save_result
from .presets import get_preset, list_presets



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a small occupancy MLP baseline.")
    parser.add_argument("--csv", help="Path to occupancy CSV file")
    parser.add_argument("--preset", help="Named occupancy benchmark preset")
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--hidden-size", type=int, default=12)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--train-fraction", type=float, default=0.8)
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="Disable z-score normalization before window construction",
    )
    parser.add_argument(
        "--output-json",
        help="Optional path to write the JSON result payload for later comparison",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List available benchmark presets and exit",
    )
    return parser.parse_args()



def _config_from_args(args: argparse.Namespace) -> tuple[ExperimentConfig, str | None]:
    if args.preset:
        preset = get_preset(args.preset)
        return preset.config, args.output_json or preset.default_output_json
    if not args.csv:
        raise ValueError("Either --csv or --preset must be provided")
    return (
        ExperimentConfig(
            csv_path=args.csv,
            window_size=args.window_size,
            hidden_size=args.hidden_size,
            learning_rate=args.learning_rate,
            epochs=args.epochs,
            seed=args.seed,
            train_fraction=args.train_fraction,
            normalize=not args.no_normalize,
        ),
        args.output_json,
    )



def main() -> None:
    args = parse_args()
    if args.list_presets:
        payload = [
            {
                "name": preset.name,
                "description": preset.description,
                "default_output_json": preset.default_output_json,
                "config": preset.config.__dict__,
            }
            for preset in list_presets()
        ]
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    config, output_json = _config_from_args(args)
    result = run_experiment(config)
    payload = result.to_dict()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if output_json:
        save_result(result, output_json)


if __name__ == "__main__":
    main()
