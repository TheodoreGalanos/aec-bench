# ABOUTME: Pure tournament scoring functions for the optional best-of-k generation step.
# ABOUTME: Round-robin and weighted round-robin reward functions following the TournO paper.

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

# TournO defaults from haizelabs/tourno tournament.py
_MIN_SIMILARITY_WEIGHT = 0.25
_DISTANCE_WEIGHT_POWER = 1.0


def _should_swap_stable(prompt_seed: str, candidate_a_id: str, candidate_b_id: str) -> bool:
    """Deterministic swap decision via SHA-256 hash (mirrors TournO position-bias mitigation).

    Both candidates produce the same swap decision regardless of the order they
    are passed in, so the LLM judge sees a position-stable layout per pair.
    """
    h_a = hashlib.sha256(f"{prompt_seed}|{candidate_a_id}".encode()).hexdigest()
    h_b = hashlib.sha256(f"{prompt_seed}|{candidate_b_id}".encode()).hexdigest()
    return h_a > h_b


@dataclass(frozen=True)
class PairwiseOutcome:
    """One pairwise comparison result returned by a judge."""

    a_id: str
    b_id: str
    a_won: bool
    reasoning: str = ""


class PairwiseJudgeProtocol(Protocol):
    """Protocol for any judge that can compare two candidates for one section."""

    def compare(
        self,
        *,
        a_id: str,
        b_id: str,
        completion_a: str,
        completion_b: str,
    ) -> PairwiseOutcome: ...


class PointwiseJudgeProtocol(Protocol):
    """Protocol for any judge that can score a single candidate."""

    def score(self, *, candidate_id: str, completion: str) -> float: ...


def _normalise_to_unit(values: Sequence[float]) -> list[float]:
    """Normalise a list of scores to roughly [0, 1] using min/max.

    Returns all-zeros for an empty list and all-1s if every value is identical.
    """
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi <= lo:
        return [1.0 for _ in values]
    span = hi - lo
    return [(v - lo) / span for v in values]


def pointwise_only_scores(
    candidates: Sequence[tuple[str, str]],
    judge: PointwiseJudgeProtocol,
) -> list[float]:
    """Score each candidate independently and return raw scores in input order."""
    return [judge.score(candidate_id=cid, completion=text) for cid, text in candidates]


def round_robin_win_rates(
    candidates: Sequence[tuple[str, str]],
    judge: PairwiseJudgeProtocol,
) -> tuple[list[float], list[PairwiseOutcome]]:
    """Run all unique pairwise comparisons and return per-candidate win-rates.

    Returns:
        (win_rates, outcomes) where ``win_rates[i] = wins_i / (n - 1)`` for n>1.
        ``outcomes`` is the flat list of every pairwise comparison performed.
    """
    n = len(candidates)
    if n < 2:
        return [1.0 for _ in candidates], []

    wins = [0.0 for _ in candidates]
    outcomes: list[PairwiseOutcome] = []

    for i in range(n):
        for j in range(i + 1, n):
            a_id, a_text = candidates[i]
            b_id, b_text = candidates[j]
            outcome = judge.compare(
                a_id=a_id,
                b_id=b_id,
                completion_a=a_text,
                completion_b=b_text,
            )
            outcomes.append(outcome)
            if outcome.a_won:
                wins[i] += 1.0
            else:
                wins[j] += 1.0

    win_rates = [w / (n - 1) for w in wins]
    return win_rates, outcomes


def weighted_round_robin_scores(
    candidates: Sequence[tuple[str, str]],
    judge: PairwiseJudgeProtocol,
    *,
    min_similarity_weight: float = _MIN_SIMILARITY_WEIGHT,
    distance_weight_power: float = _DISTANCE_WEIGHT_POWER,
) -> tuple[list[float], list[PairwiseOutcome]]:
    """Two-pass weighted round-robin (mirrors TournO weighted_round_robin_reward_fn).

    1. Run a regular round-robin to estimate baseline win-rates.
    2. Reweight every pair outcome by the performance distance between the two
       candidates (similar-performance opponents are downweighted; far-apart
       opponents are upweighted).
    """
    n = len(candidates)
    baseline, outcomes = round_robin_win_rates(candidates, judge)
    if n < 2:
        return baseline, outcomes

    # Build a wins matrix from outcomes (we need it for the second pass)
    id_to_idx = {cid: i for i, (cid, _) in enumerate(candidates)}
    wins_matrix = [[0.0] * n for _ in range(n)]
    for o in outcomes:
        i = id_to_idx[o.a_id]
        j = id_to_idx[o.b_id]
        if o.a_won:
            wins_matrix[i][j] += 1.0
        else:
            wins_matrix[j][i] += 1.0

    # Performance distance matrix
    max_distance = 0.0
    distance: list[list[float]] = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            d = abs(baseline[i] - baseline[j])
            distance[i][j] = d
            if d > max_distance:
                max_distance = d

    weights: list[list[float]] = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            normalised = distance[i][j] / max_distance if max_distance > 0 else 0.0
            weights[i][j] = min_similarity_weight + (
                (1.0 - min_similarity_weight) * (normalised**distance_weight_power)
            )

    weighted_scores: list[float] = []
    for i in range(n):
        weighted_wins = sum(wins_matrix[i][j] * weights[i][j] for j in range(n) if j != i)
        total_weight = sum(weights[i][j] for j in range(n) if j != i)
        if total_weight == 0:
            weighted_scores.append(0.0)
        else:
            weighted_scores.append(weighted_wins / total_weight)
    return weighted_scores, outcomes


def mixture_scores(
    pointwise: Sequence[float],
    pairwise: Sequence[float],
    *,
    alpha: float = 0.5,
) -> list[float]:
    """Combine pointwise + pairwise scores via the TournO mixture formula.

    ``mixed = r_point + exp(-alpha * mean(r_point)) * r_pair``

    As pointwise reward quality (mean) increases, the pairwise component is
    weighted less — preventing redundancy between confident pointwise signal
    and pairwise comparisons.
    """
    if len(pointwise) != len(pairwise):
        raise ValueError(f"pointwise and pairwise must be same length, got {len(pointwise)} vs {len(pairwise)}")
    if not pointwise:
        return []
    mean_point = sum(pointwise) / len(pointwise)
    decay = math.exp(-alpha * mean_point)
    return [p + decay * q for p, q in zip(pointwise, pairwise, strict=False)]


def pick_winner(scores: Sequence[float]) -> int:
    """Return the index of the highest score (first tie wins)."""
    if not scores:
        raise ValueError("cannot pick winner from empty scores")
    best_idx = 0
    best_score = scores[0]
    for i in range(1, len(scores)):
        if scores[i] > best_score:
            best_score = scores[i]
            best_idx = i
    return best_idx
