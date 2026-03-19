from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Sequence


@dataclass(frozen=True)
class TrainingConfig:
    hidden_size: int = 12
    learning_rate: float = 0.05
    epochs: int = 40
    seed: int = 0


class BinaryMLP:
    """Tiny pure-Python MLP for binary occupancy classification."""

    def __init__(self, input_dim: int, config: TrainingConfig | None = None) -> None:
        self.config = config or TrainingConfig()
        rng = random.Random(self.config.seed)
        hidden = self.config.hidden_size
        scale1 = math.sqrt(2.0 / max(input_dim, 1))
        scale2 = math.sqrt(2.0 / max(hidden, 1))
        self.w1 = [[rng.gauss(0.0, scale1) for _ in range(hidden)] for _ in range(input_dim)]
        self.b1 = [0.0 for _ in range(hidden)]
        self.w2 = [rng.gauss(0.0, scale2) for _ in range(hidden)]
        self.b2 = 0.0

    @staticmethod
    def _sigmoid(value: float) -> float:
        value = max(-30.0, min(30.0, value))
        return 1.0 / (1.0 + math.exp(-value))

    @staticmethod
    def _tanh(value: float) -> float:
        value = max(-20.0, min(20.0, value))
        return math.tanh(value)

    def forward_one(self, inputs: Sequence[float]) -> tuple[List[float], float]:
        hidden: List[float] = []
        for hidden_index, bias in enumerate(self.b1):
            total = bias
            for input_index, input_value in enumerate(inputs):
                total += input_value * self.w1[input_index][hidden_index]
            hidden.append(self._tanh(total))
        logit = self.b2 + sum(hidden[index] * self.w2[index] for index in range(len(hidden)))
        return hidden, self._sigmoid(logit)

    def predict_proba(self, inputs: Sequence[Sequence[float]]) -> List[float]:
        return [self.forward_one(row)[1] for row in inputs]

    def predict(self, inputs: Sequence[Sequence[float]]) -> List[int]:
        return [1 if probability >= 0.5 else 0 for probability in self.predict_proba(inputs)]

    def train(self, inputs: Sequence[Sequence[float]], labels: Sequence[int]) -> List[float]:
        if len(inputs) != len(labels):
            raise ValueError("inputs and labels must have the same length")
        losses: List[float] = []
        lr = self.config.learning_rate

        for _ in range(self.config.epochs):
            loss_sum = 0.0
            for row, label in zip(inputs, labels):
                hidden, prob = self.forward_one(row)
                prob = min(max(prob, 1e-6), 1.0 - 1e-6)
                target = float(label)
                loss_sum += -(target * math.log(prob) + (1.0 - target) * math.log(1.0 - prob))

                dlogit = prob - target
                old_w2 = list(self.w2)
                for hidden_index in range(len(self.w2)):
                    self.w2[hidden_index] -= lr * dlogit * hidden[hidden_index]
                self.b2 -= lr * dlogit

                for hidden_index in range(len(hidden)):
                    dhidden = dlogit * old_w2[hidden_index] * (1.0 - hidden[hidden_index] ** 2)
                    for input_index in range(len(row)):
                        self.w1[input_index][hidden_index] -= lr * dhidden * row[input_index]
                    self.b1[hidden_index] -= lr * dhidden

            losses.append(loss_sum / max(len(inputs), 1))

        return losses



def evaluate_binary_predictions(labels: Sequence[int], predictions: Sequence[int]) -> Dict[str, float]:
    tp = sum(1 for label, prediction in zip(labels, predictions) if label == 1 and prediction == 1)
    tn = sum(1 for label, prediction in zip(labels, predictions) if label == 0 and prediction == 0)
    fp = sum(1 for label, prediction in zip(labels, predictions) if label == 0 and prediction == 1)
    fn = sum(1 for label, prediction in zip(labels, predictions) if label == 1 and prediction == 0)
    total = max(len(list(labels)) if not isinstance(labels, list) else len(labels), 1)
    accuracy = (tp + tn) / total
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 0.0 if precision + recall == 0.0 else (2.0 * precision * recall) / (precision + recall)
    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": float(tp),
        "tn": float(tn),
        "fp": float(fp),
        "fn": float(fn),
    }
