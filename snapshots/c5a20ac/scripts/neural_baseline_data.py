from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence


CRITERION_WINDOW = 8
EXACT_THRESHOLD = 0.85
BIT_ACCURACY_THRESHOLD = 0.95


def _bits4(value: int) -> List[int]:
    return [(value >> 3) & 1, (value >> 2) & 1, (value >> 1) & 1, value & 1]


def _parity(bits: Sequence[int]) -> int:
    return sum(int(b) for b in bits) % 2


def _apply_transform(bits: List[int], transform: str) -> List[int]:
    if transform == "identity":
        return list(bits)
    if transform == "rotate_left_1":
        return bits[1:] + bits[:1]
    if transform == "xor_mask_1010":
        mask = [1, 0, 1, 0]
        return [bits[i] ^ mask[i] for i in range(4)]
    if transform == "xor_mask_0101":
        mask = [0, 1, 0, 1]
        return [bits[i] ^ mask[i] for i in range(4)]
    raise ValueError(f"Unknown transform: {transform}")


def _target_transform(task_id: str, context_bit: int) -> str:
    if task_id == "task_a":
        return "rotate_left_1" if context_bit == 0 else "xor_mask_1010"
    if task_id == "task_b":
        return "rotate_left_1" if context_bit == 0 else "xor_mask_0101"
    if task_id == "task_c":
        return "xor_mask_1010" if context_bit == 0 else "xor_mask_0101"
    raise ValueError(f"Unknown task: {task_id}")


@dataclass
class SignalExample:
    input_bits: List[int]
    context_bit: int
    target_bits: List[int]
    task_id: str


def cvt1_stage1_examples(task_id: str = "task_a") -> List[SignalExample]:
    values = [
        0b0001,
        0b0110,
        0b1011,
        0b0101,
        0b1110,
        0b0011,
        0b1100,
        0b1001,
        0b0111,
        0b1010,
        0b0100,
        0b1111,
        0b0000,
        0b1101,
        0b0010,
        0b1000,
        0b0110,
        0b1011,
    ]
    prev = [0, 0, 0, 0]
    examples: List[SignalExample] = []
    for value in values:
        bits = _bits4(value)
        ctx = _parity(prev)
        target = _apply_transform(bits, _target_transform(task_id, ctx))
        examples.append(
            SignalExample(
                input_bits=bits,
                context_bit=ctx,
                target_bits=target,
                task_id=task_id,
            )
        )
        prev = bits
    return examples


def cvt1_stage3_examples(task_id: str = "task_a") -> List[SignalExample]:
    base_values = [
        0b0001,
        0b0110,
        0b1011,
        0b0101,
        0b1110,
        0b0011,
        0b1100,
        0b1001,
        0b0111,
        0b1010,
        0b0100,
        0b1111,
        0b0000,
        0b1101,
        0b0010,
        0b1000,
        0b0110,
        0b1011,
    ]
    masks = [0b0000, 0b1111, 0b0101, 0b1010, 0b0011, 0b1100]
    values = [value ^ masks[pass_idx] for pass_idx in range(6) for value in base_values]

    prev = [0, 0, 0, 0]
    examples: List[SignalExample] = []
    for value in values:
        bits = _bits4(value)
        ctx = _parity(prev)
        target = _apply_transform(bits, _target_transform(task_id, ctx))
        examples.append(
            SignalExample(
                input_bits=bits,
                context_bit=ctx,
                target_bits=target,
                task_id=task_id,
            )
        )
        prev = bits
    return examples


def _exact_match(pred_bits: List[int], target_bits: List[int]) -> bool:
    return pred_bits == target_bits


def _bit_accuracy(pred_bits: List[int], target_bits: List[int]) -> float:
    return sum(p == t for p, t in zip(pred_bits, target_bits)) / max(len(target_bits), 1)


def rolling_window_metrics(
    exact_results: Sequence[bool],
    bit_accuracy_results: Optional[Sequence[float]] = None,
    *,
    bit_accuracy_threshold: Optional[float] = None,
) -> Dict[str, Optional[float]]:
    if bit_accuracy_results is not None and len(bit_accuracy_results) != len(exact_results):
        raise ValueError("bit_accuracy_results must align with exact_results")

    best_exact = 0.0
    best_accuracy = 0.0 if bit_accuracy_results is not None else None
    examples_to_hit: Optional[int] = None
    for end in range(CRITERION_WINDOW, len(exact_results) + 1):
        exact_window = exact_results[end - CRITERION_WINDOW : end]
        exact_rate = sum(exact_window) / CRITERION_WINDOW
        best_exact = max(best_exact, exact_rate)

        bit_ok = True
        if bit_accuracy_results is not None:
            bit_window = bit_accuracy_results[end - CRITERION_WINDOW : end]
            bit_rate = sum(bit_window) / CRITERION_WINDOW
            best_accuracy = max(best_accuracy or 0.0, bit_rate)
            if bit_accuracy_threshold is not None:
                bit_ok = bit_rate >= bit_accuracy_threshold

        if examples_to_hit is None and exact_rate >= EXACT_THRESHOLD and bit_ok:
            examples_to_hit = end

    return {
        "criterion_reached": examples_to_hit is not None,
        "examples_to_criterion": examples_to_hit,
        "best_rolling_exact_rate": round(best_exact, 4),
        "best_rolling_bit_accuracy": (
            round(best_accuracy, 4) if best_accuracy is not None else None
        ),
    }


def _criterion_reached(
    exact_results: Sequence[bool],
    bit_accuracy_results: Optional[Sequence[float]] = None,
    *,
    bit_accuracy_threshold: Optional[float] = None,
) -> bool:
    return bool(
        rolling_window_metrics(
            exact_results,
            bit_accuracy_results,
            bit_accuracy_threshold=bit_accuracy_threshold,
        )["criterion_reached"]
    )


def examples_to_criterion(
    exact_results: Sequence[bool],
    bit_accuracy_results: Optional[Sequence[float]] = None,
    *,
    bit_accuracy_threshold: Optional[float] = None,
) -> Optional[int]:
    value = rolling_window_metrics(
        exact_results,
        bit_accuracy_results,
        bit_accuracy_threshold=bit_accuracy_threshold,
    )["examples_to_criterion"]
    return int(value) if value is not None else None


__all__ = [
    "BIT_ACCURACY_THRESHOLD",
    "CRITERION_WINDOW",
    "EXACT_THRESHOLD",
    "SignalExample",
    "_bit_accuracy",
    "_criterion_reached",
    "_exact_match",
    "cvt1_stage1_examples",
    "cvt1_stage3_examples",
    "examples_to_criterion",
    "rolling_window_metrics",
]
