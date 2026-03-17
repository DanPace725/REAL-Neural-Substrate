from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean
from typing import Dict, List, Optional, Tuple

import numpy as np

from scripts.neural_baseline_data import (
    SignalExample,
    _bit_accuracy,
    _exact_match,
    examples_to_criterion,
    rolling_window_metrics,
)


class MLP:
    def __init__(
        self,
        n_in: int,
        hidden: int = 8,
        lr: float = 0.30,
        seed: int = 0,
    ) -> None:
        rng = np.random.RandomState(seed)
        self.W1 = rng.randn(hidden, n_in) * math.sqrt(2.0 / n_in)
        self.b1 = np.zeros(hidden)
        self.W2 = rng.randn(4, hidden) * math.sqrt(2.0 / hidden)
        self.b2 = np.zeros(4)
        self.lr = lr

    @staticmethod
    def _sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))

    def forward(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        h = self._sigmoid(self.W1 @ x + self.b1)
        y = self._sigmoid(self.W2 @ h + self.b2)
        return h, y

    def predict_bits(self, x: np.ndarray) -> List[int]:
        _, y = self.forward(x)
        return [1 if value >= 0.5 else 0 for value in y]

    def train_step(self, x: np.ndarray, target: np.ndarray) -> float:
        h, y = self.forward(x)
        err = y - target
        loss = float(np.mean(err**2))

        dW2 = np.outer(err * y * (1 - y), h)
        db2 = err * y * (1 - y)
        delta_h = (self.W2.T @ (err * y * (1 - y))) * h * (1 - h)
        dW1 = np.outer(delta_h, x)
        db1 = delta_h

        clip = 5.0
        self.W2 -= self.lr * np.clip(dW2, -clip, clip)
        self.b2 -= self.lr * np.clip(db2, -clip, clip)
        self.W1 -= self.lr * np.clip(dW1, -clip, clip)
        self.b1 -= self.lr * np.clip(db1, -clip, clip)
        return loss


class ElmanRNN:
    def __init__(
        self,
        n_in: int = 4,
        hidden: int = 12,
        lr: float = 0.20,
        seed: int = 0,
    ) -> None:
        rng = np.random.RandomState(seed)
        n_combined = n_in + hidden
        self.Wh = rng.randn(hidden, n_combined) * math.sqrt(2.0 / n_combined)
        self.bh = np.zeros(hidden)
        self.Wo = rng.randn(4, hidden) * math.sqrt(2.0 / hidden)
        self.bo = np.zeros(4)
        self.h = np.zeros(hidden)
        self.lr = lr
        self.hidden = hidden

    def forward(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        combined = np.concatenate([x, self.h])
        h_new = np.tanh(self.Wh @ combined + self.bh)
        y = 1.0 / (1.0 + np.exp(-np.clip(self.Wo @ h_new + self.bo, -30, 30)))
        return combined, h_new, y

    def predict_bits(self, x: np.ndarray) -> List[int]:
        _, h_new, y = self.forward(x)
        self.h = h_new
        return [1 if value >= 0.5 else 0 for value in y]

    def train_step(self, x: np.ndarray, target: np.ndarray) -> float:
        combined, h_new, y = self.forward(x)
        err = y - target
        loss = float(np.mean(err**2))

        dy = err * y * (1 - y)
        dWo = np.outer(dy, h_new)
        dbo = dy
        dh = (self.Wo.T @ dy) * (1 - h_new**2)
        dWh = np.outer(dh, combined)
        dbh = dh

        clip = 5.0
        self.Wo -= self.lr * np.clip(dWo, -clip, clip)
        self.bo -= self.lr * np.clip(dbo, -clip, clip)
        self.Wh -= self.lr * np.clip(dWh, -clip, clip)
        self.bh -= self.lr * np.clip(dbh, -clip, clip)
        self.h = h_new
        return loss


@dataclass
class BaselineResult:
    variant: str
    seed: int
    task_id: str
    exact_matches: Optional[int]
    mean_bit_accuracy: Optional[float]
    examples_to_criterion: Optional[int]
    criterion_reached: bool
    per_example_exact: List[bool]
    per_example_accuracy: List[float]
    losses: List[float]


def run_mlp_explicit(
    examples: List[SignalExample],
    *,
    seed: int,
    hidden: int = 8,
    lr: float = 0.30,
    n_epochs: int = 1,
    train_examples: Optional[List[SignalExample]] = None,
) -> BaselineResult:
    net = MLP(n_in=5, hidden=hidden, lr=lr, seed=seed)
    if train_examples:
        for _ in range(n_epochs):
            for ex in train_examples:
                x = np.array(ex.input_bits + [ex.context_bit], dtype=np.float64)
                target = np.array(ex.target_bits, dtype=np.float64)
                net.train_step(x, target)

    exact_results: List[bool] = []
    acc_results: List[float] = []
    losses: List[float] = []
    for _ in range(n_epochs):
        for ex in examples:
            x = np.array(ex.input_bits + [ex.context_bit], dtype=np.float64)
            target = np.array(ex.target_bits, dtype=np.float64)
            pred = net.predict_bits(x)
            exact_results.append(_exact_match(pred, ex.target_bits))
            acc_results.append(_bit_accuracy(pred, ex.target_bits))
            losses.append(net.train_step(x, target))

    criterion_summary = rolling_window_metrics(exact_results, acc_results)
    return BaselineResult(
        variant="mlp-explicit",
        seed=seed,
        task_id=examples[0].task_id if examples else "",
        exact_matches=sum(exact_results),
        mean_bit_accuracy=mean(acc_results) if acc_results else 0.0,
        examples_to_criterion=_coerce_etc(criterion_summary),
        criterion_reached=bool(criterion_summary["criterion_reached"]),
        per_example_exact=exact_results,
        per_example_accuracy=acc_results,
        losses=losses,
    )


def run_mlp_latent(
    examples: List[SignalExample],
    *,
    seed: int,
    hidden: int = 8,
    lr: float = 0.30,
    n_epochs: int = 1,
    train_examples: Optional[List[SignalExample]] = None,
) -> BaselineResult:
    net = MLP(n_in=4, hidden=hidden, lr=lr, seed=seed)
    if train_examples:
        for _ in range(n_epochs):
            for ex in train_examples:
                x = np.array(ex.input_bits, dtype=np.float64)
                target = np.array(ex.target_bits, dtype=np.float64)
                net.train_step(x, target)

    exact_results: List[bool] = []
    acc_results: List[float] = []
    losses: List[float] = []
    for _ in range(n_epochs):
        for ex in examples:
            x = np.array(ex.input_bits, dtype=np.float64)
            target = np.array(ex.target_bits, dtype=np.float64)
            pred = net.predict_bits(x)
            exact_results.append(_exact_match(pred, ex.target_bits))
            acc_results.append(_bit_accuracy(pred, ex.target_bits))
            losses.append(net.train_step(x, target))

    criterion_summary = rolling_window_metrics(exact_results, acc_results)
    return BaselineResult(
        variant="mlp-latent",
        seed=seed,
        task_id=examples[0].task_id if examples else "",
        exact_matches=sum(exact_results),
        mean_bit_accuracy=mean(acc_results) if acc_results else 0.0,
        examples_to_criterion=_coerce_etc(criterion_summary),
        criterion_reached=bool(criterion_summary["criterion_reached"]),
        per_example_exact=exact_results,
        per_example_accuracy=acc_results,
        losses=losses,
    )


def run_rnn_latent(
    examples: List[SignalExample],
    *,
    seed: int,
    hidden: int = 12,
    lr: float = 0.20,
    n_epochs: int = 1,
    train_examples: Optional[List[SignalExample]] = None,
) -> BaselineResult:
    net = ElmanRNN(n_in=4, hidden=hidden, lr=lr, seed=seed)
    if train_examples:
        for _ in range(n_epochs):
            net.h = np.zeros(net.hidden)
            for ex in train_examples:
                x = np.array(ex.input_bits, dtype=np.float64)
                target = np.array(ex.target_bits, dtype=np.float64)
                net.train_step(x, target)

    exact_results: List[bool] = []
    acc_results: List[float] = []
    losses: List[float] = []
    for _ in range(n_epochs):
        net.h = np.zeros(net.hidden)
        for ex in examples:
            x = np.array(ex.input_bits, dtype=np.float64)
            target = np.array(ex.target_bits, dtype=np.float64)
            pred_raw = 1.0 / (
                1.0
                + np.exp(
                    -np.clip(
                        net.Wo @ np.tanh(net.Wh @ np.concatenate([x, net.h]) + net.bh) + net.bo,
                        -30,
                        30,
                    )
                )
            )
            pred = [1 if value >= 0.5 else 0 for value in pred_raw]
            exact_results.append(_exact_match(pred, ex.target_bits))
            acc_results.append(_bit_accuracy(pred, ex.target_bits))
            losses.append(net.train_step(x, target))

    criterion_summary = rolling_window_metrics(exact_results, acc_results)
    return BaselineResult(
        variant="rnn-latent",
        seed=seed,
        task_id=examples[0].task_id if examples else "",
        exact_matches=sum(exact_results),
        mean_bit_accuracy=mean(acc_results) if acc_results else 0.0,
        examples_to_criterion=_coerce_etc(criterion_summary),
        criterion_reached=bool(criterion_summary["criterion_reached"]),
        per_example_exact=exact_results,
        per_example_accuracy=acc_results,
        losses=losses,
    )


def scan_epochs_to_criterion(
    examples: List[SignalExample],
    *,
    seed: int,
    max_epochs: int = 20,
    mlp_hidden: int = 8,
    rnn_hidden: int = 12,
    train_examples: Optional[List[SignalExample]] = None,
) -> Dict[str, Optional[int]]:
    results: Dict[str, Optional[int]] = {}
    for variant in ("mlp-explicit", "mlp-latent", "rnn-latent"):
        all_exact: List[bool] = []
        net_mlp_e = MLP(n_in=5, hidden=mlp_hidden, lr=0.30, seed=seed) if variant == "mlp-explicit" else None
        net_mlp_l = MLP(n_in=4, hidden=mlp_hidden, lr=0.30, seed=seed) if variant == "mlp-latent" else None
        net_rnn = ElmanRNN(n_in=4, hidden=rnn_hidden, lr=0.20, seed=seed) if variant == "rnn-latent" else None

        if train_examples:
            if net_rnn is not None:
                net_rnn.h = np.zeros(net_rnn.hidden)
            for ex in train_examples:
                target = np.array(ex.target_bits, dtype=np.float64)
                if net_mlp_e is not None:
                    x = np.array(ex.input_bits + [ex.context_bit], dtype=np.float64)
                    net_mlp_e.train_step(x, target)
                elif net_mlp_l is not None:
                    x = np.array(ex.input_bits, dtype=np.float64)
                    net_mlp_l.train_step(x, target)
                else:
                    x = np.array(ex.input_bits, dtype=np.float64)
                    net_rnn.train_step(x, target)

        epoch_found: Optional[int] = None
        for epoch in range(1, max_epochs + 1):
            epoch_exact: List[bool] = []
            if net_rnn is not None:
                net_rnn.h = np.zeros(net_rnn.hidden)

            for ex in examples:
                target = np.array(ex.target_bits, dtype=np.float64)
                if net_mlp_e is not None:
                    x = np.array(ex.input_bits + [ex.context_bit], dtype=np.float64)
                    pred = net_mlp_e.predict_bits(x)
                    net_mlp_e.train_step(x, target)
                elif net_mlp_l is not None:
                    x = np.array(ex.input_bits, dtype=np.float64)
                    pred = net_mlp_l.predict_bits(x)
                    net_mlp_l.train_step(x, target)
                else:
                    x = np.array(ex.input_bits, dtype=np.float64)
                    pred_raw = 1.0 / (
                        1.0
                        + np.exp(
                            -np.clip(
                                net_rnn.Wo @ np.tanh(net_rnn.Wh @ np.concatenate([x, net_rnn.h]) + net_rnn.bh)
                                + net_rnn.bo,
                                -30,
                                30,
                            )
                        )
                    )
                    pred = [1 if value >= 0.5 else 0 for value in pred_raw]
                    net_rnn.train_step(x, target)
                epoch_exact.append(_exact_match(pred, ex.target_bits))

            all_exact.extend(epoch_exact)
            if epoch_found is None and examples_to_criterion(all_exact) is not None:
                epoch_found = epoch

        results[variant] = epoch_found
    return results


def aggregate_results(results: List[BaselineResult]) -> Dict[str, object]:
    if not results:
        return {}

    reached = [result for result in results if result.criterion_reached]
    etc_values = [
        result.examples_to_criterion
        for result in reached
        if result.examples_to_criterion is not None
    ]
    exact_values = [result.exact_matches for result in results if result.exact_matches is not None]
    bit_accuracy_values = [
        result.mean_bit_accuracy for result in results if result.mean_bit_accuracy is not None
    ]
    return {
        "variant": results[0].variant,
        "task_id": results[0].task_id,
        "n_seeds": len(results),
        "mean_exact_matches": mean(exact_values) if exact_values else None,
        "mean_bit_accuracy": mean(bit_accuracy_values) if bit_accuracy_values else None,
        "criterion_rate": len(reached) / len(results),
        "mean_examples_to_criterion": mean(etc_values) if etc_values else None,
        "min_examples_to_criterion": min(etc_values) if etc_values else None,
    }


def _coerce_etc(summary: Dict[str, Optional[float]]) -> Optional[int]:
    value = summary["examples_to_criterion"]
    return int(value) if value is not None else None


__all__ = [
    "BaselineResult",
    "ElmanRNN",
    "MLP",
    "aggregate_results",
    "run_mlp_explicit",
    "run_mlp_latent",
    "run_rnn_latent",
    "scan_epochs_to_criterion",
]
