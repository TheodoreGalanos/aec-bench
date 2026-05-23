# ABOUTME: Reusable statistical primitives for the evaluation domain.
# ABOUTME: Keeps agreement, interval, and aggregation math pure and centrally tested.

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from math import sqrt
from statistics import NormalDist


def mean(values: Iterable[float | int | None]) -> float:
    collected = [float(value) for value in values if value is not None]
    if not collected:
        return 0.0
    return sum(collected) / len(collected)


def wilson_confidence_interval(
    *,
    successes: int,
    trials: int,
    confidence_level: float = 0.95,
) -> tuple[float, float]:
    if trials <= 0:
        return (0.0, 0.0)

    bounded_successes = min(max(successes, 0), trials)
    z_score = NormalDist().inv_cdf(0.5 + confidence_level / 2.0)
    observed_rate = bounded_successes / trials
    z_squared = z_score**2
    denominator = 1.0 + z_squared / trials
    center = (observed_rate + z_squared / (2.0 * trials)) / denominator
    margin = z_score * sqrt((observed_rate * (1.0 - observed_rate) + z_squared / (4.0 * trials)) / trials) / denominator
    return (max(0.0, center - margin), min(1.0, center + margin))


def cohen_kappa(left: Sequence[str], right: Sequence[str]) -> float:
    if len(left) != len(right):
        msg = "cohen_kappa requires label sequences of equal length"
        raise ValueError(msg)
    if not left:
        return 0.0

    observed_agreement = sum(1 for lhs, rhs in zip(left, right, strict=True) if lhs == rhs) / len(left)
    left_counts = Counter(left)
    right_counts = Counter(right)
    categories = set(left_counts) | set(right_counts)
    expected_agreement = sum(
        (left_counts[category] / len(left)) * (right_counts[category] / len(right)) for category in categories
    )

    if expected_agreement == 1.0:
        return 1.0
    return (observed_agreement - expected_agreement) / (1.0 - expected_agreement)
