# ABOUTME: Rubric-based scoring with weighted rollup for complex evaluation.
# ABOUTME: Computes dimension-normalised rewards from rubric definitions and scores.

from __future__ import annotations

from collections.abc import Sequence

from aec_bench.contracts.rubric import (
    DimensionScore,
    Rubric,
    RubricResult,
)


def score_rubric(
    *,
    rubric: Rubric,
    scores: Sequence[DimensionScore],
) -> RubricResult:
    """Compute a rolled-up reward from rubric dimensions and scores.

    Missing dimension scores are treated as zero. Normalised scores
    are clamped to [0.0, 1.0]. The rollup strategy determines how
    dimension scores aggregate into a single reward.
    """
    if not rubric.dimensions:
        return RubricResult(
            dimension_scores=list(scores),
            reward=0.0,
            rollup_strategy=rubric.rollup_strategy,
        )

    score_map = {s.dimension_id: s for s in scores}

    complete_scores: list[DimensionScore] = []
    for dim in rubric.dimensions:
        if dim.id in score_map:
            complete_scores.append(score_map[dim.id])
        else:
            complete_scores.append(
                DimensionScore(
                    dimension_id=dim.id,
                    score=0.0,
                    max_score=dim.max_score,
                    evidence="No score provided",
                    eval_method_used=dim.eval_method,
                )
            )

    dim_map = {d.id: d for d in rubric.dimensions}
    normalised: list[tuple[float, float]] = []
    for ds in complete_scores:
        dim = dim_map[ds.dimension_id]
        raw = ds.score / ds.max_score if ds.max_score > 0 else 0.0
        norm = min(max(raw, 0.0), 1.0)  # clamp to [0, 1]
        normalised.append((norm, dim.weight))

    reward = _rollup(normalised, rubric.rollup_strategy)

    return RubricResult(
        dimension_scores=complete_scores,
        reward=round(reward, 4),
        rollup_strategy=rubric.rollup_strategy,
    )


def _rollup(
    normalised: list[tuple[float, float]],
    strategy: str,
) -> float:
    """Apply a rollup strategy to normalised (score, weight) pairs."""
    if not normalised:
        return 0.0

    if strategy == "min":
        return min(score for score, _ in normalised)

    # Default: weighted_mean
    total_weight = sum(w for _, w in normalised)
    if total_weight == 0:
        return 0.0
    return sum(score * weight for score, weight in normalised) / total_weight
