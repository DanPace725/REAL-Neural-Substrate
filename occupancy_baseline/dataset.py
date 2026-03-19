from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

FEATURE_COLUMNS = (
    "temperature",
    "humidity",
    "light",
    "co2",
    "humidity_ratio",
)
LABEL_COLUMN = "occupancy"


@dataclass(frozen=True)
class OccupancyExample:
    features: tuple[float, ...]
    label: int


@dataclass(frozen=True)
class OccupancyDataset:
    features: tuple[object, ...]
    labels: tuple[int, ...]
    feature_names: tuple[str, ...]

    @property
    def size(self) -> int:
        return len(self.labels)

    @property
    def input_dim(self) -> int:
        if not self.features:
            return 0
        first = self.features[0]
        if isinstance(first, tuple) and first and isinstance(first[0], tuple):
            return len(first) * len(first[0])
        return len(first)



def _parse_label(value: str) -> int:
    label = int(float(value))
    if label not in (0, 1):
        raise ValueError(f"Expected binary occupancy label, got {value!r}")
    return label



def _zscore_normalize(rows: List[List[float]]) -> List[List[float]]:
    if not rows:
        return []
    column_count = len(rows[0])
    means = [sum(row[index] for row in rows) / len(rows) for index in range(column_count)]
    variances = [
        sum((row[index] - means[index]) ** 2 for row in rows) / len(rows)
        for index in range(column_count)
    ]
    stds = [variance**0.5 if variance > 1e-8 else 1.0 for variance in variances]
    return [
        [
            (row[index] - means[index]) / stds[index]
            for index in range(column_count)
        ]
        for row in rows
    ]



def load_csv_dataset(path: str | Path, *, normalize: bool = True) -> OccupancyDataset:
    csv_path = Path(path)
    rows: List[OccupancyExample] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in FEATURE_COLUMNS + (LABEL_COLUMN,) if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"CSV is missing required columns: {missing}")
        for row in reader:
            features = tuple(float(row[column]) for column in FEATURE_COLUMNS)
            label = _parse_label(row[LABEL_COLUMN])
            rows.append(OccupancyExample(features=features, label=label))

    if not rows:
        raise ValueError(f"No data rows found in {csv_path}")

    feature_rows = [list(example.features) for example in rows]
    if normalize:
        feature_rows = _zscore_normalize(feature_rows)
    labels = [example.label for example in rows]
    return OccupancyDataset(
        features=tuple(tuple(row) for row in feature_rows),
        labels=tuple(labels),
        feature_names=FEATURE_COLUMNS,
    )



def build_windowed_dataset(
    dataset: OccupancyDataset,
    *,
    window_size: int = 5,
    flatten: bool = True,
) -> OccupancyDataset:
    if window_size <= 0:
        raise ValueError("window_size must be positive")
    if dataset.size < window_size:
        raise ValueError(
            f"Need at least {window_size} rows to build windows, found {dataset.size}"
        )

    windows: List[object] = []
    labels: List[int] = []
    for end_index in range(window_size - 1, dataset.size):
        start_index = end_index - window_size + 1
        window = dataset.features[start_index : end_index + 1]
        if flatten:
            flattened = tuple(value for row in window for value in row)
            windows.append(flattened)
        else:
            windows.append(tuple(tuple(row) for row in window))
        labels.append(int(dataset.labels[end_index]))

    if flatten:
        feature_names: Sequence[str] = tuple(
            f"t-{offset}:{name}"
            for offset in reversed(range(window_size))
            for name in dataset.feature_names
        )
    else:
        feature_names = dataset.feature_names

    return OccupancyDataset(
        features=tuple(windows),
        labels=tuple(labels),
        feature_names=tuple(feature_names),
    )
