# ABOUTME: Pure helpers for uncertainty scoring in the lambda-rlm adapter.
# ABOUTME: Maintains running token-length statistics and computes joint uncertainty scores.

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class RunningStats:
    """Population running statistics using Welford's online algorithm."""

    n: int = 0
    _mean: float = 0.0
    _m2: float = 0.0

    @property
    def mean(self) -> float:
        return self._mean if self.n else 0.0

    @property
    def stdev(self) -> float:
        if self.n == 0:
            return 0.0
        variance = self._m2 / self.n
        return math.sqrt(variance) if variance > 0.0 else 0.0

    def push(self, value: float) -> None:
        self.n += 1
        delta = value - self._mean
        self._mean += delta / self.n
        delta2 = value - self._mean
        self._m2 += delta * delta2

    def z_score(self, value: float) -> float:
        if self.stdev == 0.0:
            return 0.0
        return (value - self.mean) / self.stdev

    def as_dict(self) -> dict[str, float | int]:
        return {
            "mean": self.mean,
            "stdev": self.stdev,
            "n": self.n,
        }


def compute_joint_score(
    confidence: float,
    z_len: float,
    lambda_: float,
    eps: float,
) -> float:
    """Compute the joint uncertainty score from confidence and normalized length."""
    safe_eps = max(eps, 1e-12)
    safe_confidence = max(confidence, safe_eps)
    return -math.log(safe_confidence) - lambda_ * z_len
