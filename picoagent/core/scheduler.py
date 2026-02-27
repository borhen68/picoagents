from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np


@dataclass(slots=True)
class ToolDecision:
    tool_name: str | None
    entropy_bits: float
    probabilities: dict[str, float]
    should_clarify: bool


class EntropyScheduler:
    """Selects tools from score distributions with Shannon entropy gating."""

    def __init__(self, threshold_bits: float = 1.5) -> None:
        if threshold_bits < 0:
            raise ValueError("threshold_bits must be >= 0")
        self.threshold_bits = float(threshold_bits)

    def select(self, scores: Mapping[str, float], threshold_bits: float | None = None) -> str | None:
        decision = self.decide(scores, threshold_bits=threshold_bits)
        return decision.tool_name

    def decide(self, scores: Mapping[str, float], threshold_bits: float | None = None) -> ToolDecision:
        if not scores:
            return ToolDecision(tool_name=None, entropy_bits=0.0, probabilities={}, should_clarify=True)

        names = list(scores.keys())
        values = np.array([float(scores[name]) for name in names], dtype=np.float64)
        probs = _softmax(values)
        entropy_bits = shannon_entropy(probs)
        threshold = self.threshold_bits if threshold_bits is None else float(threshold_bits)

        best_idx = int(np.argmax(probs))
        should_clarify = entropy_bits > threshold
        return ToolDecision(
            tool_name=None if should_clarify else names[best_idx],
            entropy_bits=float(entropy_bits),
            probabilities={name: float(probs[i]) for i, name in enumerate(names)},
            should_clarify=should_clarify,
        )


def _softmax(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return values
    shifted = values - np.max(values)
    exps = np.exp(shifted)
    denom = np.sum(exps)
    if denom <= 0:
        return np.full_like(values, 1.0 / values.size)
    return exps / denom


def shannon_entropy(probabilities: np.ndarray) -> float:
    if probabilities.size == 0:
        return 0.0
    probs = np.clip(probabilities, 1e-12, 1.0)
    return float(-np.sum(probs * np.log2(probs)))
