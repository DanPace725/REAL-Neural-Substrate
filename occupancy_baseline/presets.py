from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .experiment import ExperimentConfig

_DATASET_ROOT = Path(__file__).resolve().parent / 'data'
_DEFAULT_RESULTS_ROOT = Path(__file__).resolve().parents[1] / 'tests_tmp'


@dataclass(frozen=True)
class BenchmarkPreset:
    name: str
    description: str
    config: ExperimentConfig
    default_output_json: str


SYNTH_V1_DEFAULT = BenchmarkPreset(
    name='synth_v1_default',
    description='Canonical Phase 8 occupancy bridge benchmark on the checked-in synthetic sequence.',
    config=ExperimentConfig(
        csv_path=str(_DATASET_ROOT / 'occupancy_synth_v1.csv'),
        window_size=5,
        hidden_size=12,
        learning_rate=0.05,
        epochs=60,
        seed=0,
        train_fraction=0.8,
        normalize=True,
    ),
    default_output_json=str(_DEFAULT_RESULTS_ROOT / 'occupancy_synth_v1_default.json'),
)

PRESETS = {
    SYNTH_V1_DEFAULT.name: SYNTH_V1_DEFAULT,
}



def get_preset(name: str) -> BenchmarkPreset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        raise KeyError(f'Unknown occupancy preset: {name}') from exc



def list_presets() -> tuple[BenchmarkPreset, ...]:
    return tuple(PRESETS[name] for name in sorted(PRESETS))
