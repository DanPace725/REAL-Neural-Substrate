"""Traditional occupancy-detection baseline utilities for Phase 8."""

from .dataset import OccupancyDataset, OccupancyExample, build_windowed_dataset, load_csv_dataset
from .experiment import ExperimentConfig, ExperimentResult, run_experiment, save_result
from .mlp import BinaryMLP, TrainingConfig, evaluate_binary_predictions
from .presets import BenchmarkPreset, get_preset, list_presets

__all__ = [
    "BenchmarkPreset",
    "BinaryMLP",
    "ExperimentConfig",
    "ExperimentResult",
    "OccupancyDataset",
    "OccupancyExample",
    "TrainingConfig",
    "build_windowed_dataset",
    "evaluate_binary_predictions",
    "get_preset",
    "list_presets",
    "load_csv_dataset",
    "run_experiment",
    "save_result",
]
