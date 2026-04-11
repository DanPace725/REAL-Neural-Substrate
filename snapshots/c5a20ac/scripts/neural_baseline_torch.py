from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import List, Optional, Sequence

from scripts.ceiling_benchmark_metrics import criterion_metrics_from_exact_and_accuracy
from scripts.neural_baseline_data import SignalExample, _bit_accuracy, _exact_match


TORCH_IMPORT_ERROR: Exception | None = None
try:
    import torch
    from torch import nn
except Exception as exc:  # pragma: no cover - exercised by smoke tests when torch is unavailable
    torch = None
    nn = None
    TORCH_IMPORT_ERROR = exc


TBPTT_WINDOW = 8


@dataclass
class TorchBaselineResult:
    variant: str
    seed: int
    task_id: str
    exact_matches: int
    mean_bit_accuracy: float
    examples_to_criterion: Optional[int]
    criterion_reached: bool
    exact_match_rate: float
    per_example_exact: List[bool]
    per_example_accuracy: List[float]
    losses: List[float]


def torch_available() -> bool:
    return torch is not None


def _require_torch() -> None:
    if torch is None or nn is None:
        raise RuntimeError("PyTorch is required for the expanded neural baselines") from TORCH_IMPORT_ERROR


def _seed_torch(seed: int) -> None:
    _require_torch()
    torch.manual_seed(seed)


def _latent_tensor(example: SignalExample) -> "torch.Tensor":
    _require_torch()
    return torch.tensor(example.input_bits, dtype=torch.float32)


def _targets_tensor(examples: Sequence[SignalExample]) -> "torch.Tensor":
    _require_torch()
    return torch.tensor([example.target_bits for example in examples], dtype=torch.float32).unsqueeze(0)


def _sequence_tensor(examples: Sequence[SignalExample]) -> "torch.Tensor":
    _require_torch()
    if not examples:
        return torch.zeros((1, 0, 4), dtype=torch.float32)
    return torch.stack([_latent_tensor(example) for example in examples], dim=0).unsqueeze(0)


class _RecurrentHead(nn.Module):
    def __init__(self, kind: str, *, input_dim: int, hidden_dim: int) -> None:
        super().__init__()
        if kind == "gru":
            self.core = nn.GRU(input_dim, hidden_dim, batch_first=True)
        elif kind == "lstm":
            self.core = nn.LSTM(input_dim, hidden_dim, batch_first=True)
        elif kind == "elman":
            self.core = nn.RNN(input_dim, hidden_dim, nonlinearity="tanh", batch_first=True)
        else:
            raise ValueError(f"Unsupported recurrent kind: {kind}")
        self.output = nn.Linear(hidden_dim, 4)

    def forward(self, sequence: "torch.Tensor") -> "torch.Tensor":
        outputs, _ = self.core(sequence)
        return self.output(outputs)


class _CausalTransformer(nn.Module):
    def __init__(self, *, input_dim: int, d_model: int, n_heads: int = 4, n_layers: int = 2, context_window: int = TBPTT_WINDOW) -> None:
        super().__init__()
        self.input_proj = nn.Linear(input_dim, d_model)
        self.position = nn.Parameter(torch.zeros(context_window, d_model))
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=n_heads,
            dim_feedforward=d_model * 2,
            dropout=0.0,
            batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        self.output = nn.Linear(d_model, 4)

    def forward(self, sequence: "torch.Tensor") -> "torch.Tensor":
        _, seq_len, _ = sequence.shape
        hidden = self.input_proj(sequence) + self.position[:seq_len].unsqueeze(0)
        mask = torch.full((seq_len, seq_len), float("-inf"), device=sequence.device)
        mask = torch.triu(mask, diagonal=1)
        encoded = self.encoder(hidden, mask=mask)
        return self.output(encoded)


def _predict_bits(logits: "torch.Tensor") -> List[int]:
    _require_torch()
    probabilities = torch.sigmoid(logits).detach().cpu().tolist()
    return [1 if value >= 0.5 else 0 for value in probabilities]


def _run_sequence_model(
    examples: Sequence[SignalExample],
    *,
    seed: int,
    variant: str,
    model: "nn.Module",
    lr: float,
    train_examples: Optional[Sequence[SignalExample]] = None,
) -> TorchBaselineResult:
    _require_torch()
    _seed_torch(seed)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.BCEWithLogitsLoss()

    def update_window(window_examples: Sequence[SignalExample]) -> float:
        sequence = _sequence_tensor(window_examples)
        targets = _targets_tensor(window_examples)
        optimizer.zero_grad()
        logits = model(sequence)
        loss = criterion(logits, targets)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        return float(loss.detach().item())

    if train_examples:
        pretrain_window: List[SignalExample] = []
        for example in train_examples:
            pretrain_window.append(example)
            pretrain_window = pretrain_window[-TBPTT_WINDOW:]
            update_window(pretrain_window)

    exact_results: List[bool] = []
    bit_accuracies: List[float] = []
    losses: List[float] = []
    window: List[SignalExample] = []

    for example in examples:
        window.append(example)
        window = window[-TBPTT_WINDOW:]
        sequence = _sequence_tensor(window)
        with torch.no_grad():
            logits = model(sequence)[0, -1]
        prediction = _predict_bits(logits)
        exact_results.append(_exact_match(prediction, example.target_bits))
        bit_accuracies.append(_bit_accuracy(prediction, example.target_bits))
        losses.append(update_window(window))

    metrics = criterion_metrics_from_exact_and_accuracy(exact_results, bit_accuracies)
    return TorchBaselineResult(
        variant=variant,
        seed=seed,
        task_id=examples[0].task_id if examples else "",
        exact_matches=sum(exact_results),
        mean_bit_accuracy=mean(bit_accuracies) if bit_accuracies else 0.0,
        examples_to_criterion=metrics["examples_to_criterion"],
        criterion_reached=bool(metrics["criterion_reached"]),
        exact_match_rate=(sum(exact_results) / len(exact_results)) if exact_results else 0.0,
        per_example_exact=exact_results,
        per_example_accuracy=bit_accuracies,
        losses=losses,
    )


def run_elman_latent(
    examples: Sequence[SignalExample],
    *,
    seed: int,
    hidden: int,
    lr: float = 0.003,
    train_examples: Optional[Sequence[SignalExample]] = None,
) -> TorchBaselineResult:
    _require_torch()
    model = _RecurrentHead("elman", input_dim=4, hidden_dim=hidden)
    return _run_sequence_model(
        examples,
        seed=seed,
        variant="elman",
        model=model,
        lr=lr,
        train_examples=train_examples,
    )


def run_gru_latent(
    examples: Sequence[SignalExample],
    *,
    seed: int,
    hidden: int,
    lr: float = 0.003,
    train_examples: Optional[Sequence[SignalExample]] = None,
) -> TorchBaselineResult:
    _require_torch()
    model = _RecurrentHead("gru", input_dim=4, hidden_dim=hidden)
    return _run_sequence_model(
        examples,
        seed=seed,
        variant="gru",
        model=model,
        lr=lr,
        train_examples=train_examples,
    )


def run_lstm_latent(
    examples: Sequence[SignalExample],
    *,
    seed: int,
    hidden: int,
    lr: float = 0.003,
    train_examples: Optional[Sequence[SignalExample]] = None,
) -> TorchBaselineResult:
    _require_torch()
    model = _RecurrentHead("lstm", input_dim=4, hidden_dim=hidden)
    return _run_sequence_model(
        examples,
        seed=seed,
        variant="lstm",
        model=model,
        lr=lr,
        train_examples=train_examples,
    )


def run_transformer_latent(
    examples: Sequence[SignalExample],
    *,
    seed: int,
    d_model: int,
    lr: float = 0.002,
    train_examples: Optional[Sequence[SignalExample]] = None,
) -> TorchBaselineResult:
    _require_torch()
    model = _CausalTransformer(input_dim=4, d_model=d_model)
    return _run_sequence_model(
        examples,
        seed=seed,
        variant="causal-transformer",
        model=model,
        lr=lr,
        train_examples=train_examples,
    )


__all__ = [
    "TBPTT_WINDOW",
    "TORCH_IMPORT_ERROR",
    "TorchBaselineResult",
    "run_elman_latent",
    "run_gru_latent",
    "run_lstm_latent",
    "run_transformer_latent",
    "torch_available",
]
