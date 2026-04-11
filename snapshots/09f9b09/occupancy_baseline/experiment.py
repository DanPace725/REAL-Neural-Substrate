from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict

from .dataset import build_windowed_dataset, load_csv_dataset
from .mlp import BinaryMLP, TrainingConfig, evaluate_binary_predictions


@dataclass(frozen=True)
class ExperimentConfig:
    csv_path: str
    window_size: int = 5
    hidden_size: int = 12
    learning_rate: float = 0.05
    epochs: int = 40
    seed: int = 0
    train_fraction: float = 0.8
    normalize: bool = True


@dataclass(frozen=True)
class ExperimentResult:
    config: ExperimentConfig
    dataset_rows: int
    windowed_examples: int
    input_dim: int
    train_examples: int
    test_examples: int
    final_train_loss: float | None
    metrics: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": asdict(self.config),
            "dataset_rows": self.dataset_rows,
            "windowed_examples": self.windowed_examples,
            "input_dim": self.input_dim,
            "train_examples": self.train_examples,
            "test_examples": self.test_examples,
            "final_train_loss": self.final_train_loss,
            "metrics": dict(self.metrics),
        }



def _split_index(example_count: int, train_fraction: float) -> int:
    if example_count < 2:
        raise ValueError("Need at least 2 windowed examples to create a train/test split")
    clamped_fraction = max(0.0, min(1.0, train_fraction))
    proposed = int(example_count * clamped_fraction)
    return max(1, min(example_count - 1, proposed))



def run_experiment(config: ExperimentConfig) -> ExperimentResult:
    dataset = load_csv_dataset(config.csv_path, normalize=config.normalize)
    windowed = build_windowed_dataset(dataset, window_size=config.window_size, flatten=True)
    split_index = _split_index(windowed.size, config.train_fraction)

    train_x = windowed.features[:split_index]
    train_y = windowed.labels[:split_index]
    test_x = windowed.features[split_index:]
    test_y = windowed.labels[split_index:]

    model = BinaryMLP(
        input_dim=windowed.input_dim,
        config=TrainingConfig(
            hidden_size=config.hidden_size,
            learning_rate=config.learning_rate,
            epochs=config.epochs,
            seed=config.seed,
        ),
    )
    losses = model.train(train_x, train_y)
    metrics = evaluate_binary_predictions(test_y, model.predict(test_x))
    return ExperimentResult(
        config=config,
        dataset_rows=dataset.size,
        windowed_examples=windowed.size,
        input_dim=windowed.input_dim,
        train_examples=len(train_y),
        test_examples=len(test_y),
        final_train_loss=losses[-1] if losses else None,
        metrics=metrics,
    )



def save_result(result: ExperimentResult, output_path: str | Path) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True), encoding='utf-8')
    return destination
