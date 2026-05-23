# ABOUTME: Tests for rubric scoring functions.
# ABOUTME: Covers weighted rollup, missing dimensions, min strategy, and clamping.

"""Tests for rubric scoring functions."""

from aec_bench.contracts.rubric import (
    DimensionScore,
    Rubric,
    RubricDimension,
    RubricResult,
)
from aec_bench.evaluation.rubric_scorer import score_rubric


def test_score_rubric_weighted_mean() -> None:
    rubric = Rubric(
        dimensions=[
            RubricDimension(
                id="completeness",
                name="Completeness",
                description="Coverage",
                weight=1.0,
                max_score=10.0,
                eval_method="automated",
                criteria=[],
            ),
            RubricDimension(
                id="accuracy",
                name="Accuracy",
                description="Correctness",
                weight=2.0,
                max_score=10.0,
                eval_method="automated",
                criteria=[],
            ),
        ],
        rollup_strategy="weighted_mean",
    )
    scores = [
        DimensionScore(
            dimension_id="completeness",
            score=8.0,
            max_score=10.0,
            evidence="Good",
            eval_method_used="automated",
        ),
        DimensionScore(
            dimension_id="accuracy",
            score=6.0,
            max_score=10.0,
            evidence="Partial",
            eval_method_used="automated",
        ),
    ]
    result = score_rubric(rubric=rubric, scores=scores)
    assert isinstance(result, RubricResult)
    # weighted: (8/10 * 1.0 + 6/10 * 2.0) / (1.0 + 2.0) = (0.8 + 1.2) / 3 = 0.667
    assert abs(result.reward - 0.667) < 0.01


def test_score_rubric_equal_weights() -> None:
    rubric = Rubric(
        dimensions=[
            RubricDimension(
                id="a",
                name="A",
                description="",
                weight=1.0,
                max_score=10.0,
                eval_method="automated",
                criteria=[],
            ),
            RubricDimension(
                id="b",
                name="B",
                description="",
                weight=1.0,
                max_score=10.0,
                eval_method="automated",
                criteria=[],
            ),
        ],
    )
    scores = [
        DimensionScore(dimension_id="a", score=10.0, max_score=10.0),
        DimensionScore(dimension_id="b", score=5.0, max_score=10.0),
    ]
    result = score_rubric(rubric=rubric, scores=scores)
    assert abs(result.reward - 0.75) < 0.01


def test_score_rubric_missing_dimension_scores_zero() -> None:
    rubric = Rubric(
        dimensions=[
            RubricDimension(
                id="a",
                name="A",
                description="",
                weight=1.0,
                max_score=10.0,
                eval_method="automated",
                criteria=[],
            ),
            RubricDimension(
                id="b",
                name="B",
                description="",
                weight=1.0,
                max_score=10.0,
                eval_method="automated",
                criteria=[],
            ),
        ],
    )
    scores = [
        DimensionScore(dimension_id="a", score=10.0, max_score=10.0),
    ]
    result = score_rubric(rubric=rubric, scores=scores)
    # "b" treated as 0: (1.0 * 1.0 + 0.0 * 1.0) / 2.0 = 0.5
    assert abs(result.reward - 0.5) < 0.01
    assert len(result.dimension_scores) == 2


def test_score_rubric_min_strategy() -> None:
    rubric = Rubric(
        dimensions=[
            RubricDimension(
                id="a",
                name="A",
                description="",
                weight=1.0,
                max_score=10.0,
                eval_method="automated",
                criteria=[],
            ),
            RubricDimension(
                id="b",
                name="B",
                description="",
                weight=1.0,
                max_score=10.0,
                eval_method="automated",
                criteria=[],
            ),
        ],
        rollup_strategy="min",
    )
    scores = [
        DimensionScore(dimension_id="a", score=9.0, max_score=10.0),
        DimensionScore(dimension_id="b", score=3.0, max_score=10.0),
    ]
    result = score_rubric(rubric=rubric, scores=scores)
    assert abs(result.reward - 0.3) < 0.01


def test_score_rubric_zero_max_returns_zero() -> None:
    rubric = Rubric(dimensions=[])
    result = score_rubric(rubric=rubric, scores=[])
    assert result.reward == 0.0


def test_score_rubric_clamps_over_max() -> None:
    """Score exceeding max_score should be clamped to 1.0 normalised."""
    rubric = Rubric(
        dimensions=[
            RubricDimension(
                id="a",
                name="A",
                description="",
                weight=1.0,
                max_score=10.0,
                eval_method="automated",
                criteria=[],
            ),
        ],
    )
    scores = [
        DimensionScore(dimension_id="a", score=15.0, max_score=10.0),
    ]
    result = score_rubric(rubric=rubric, scores=scores)
    assert result.reward <= 1.0
    assert abs(result.reward - 1.0) < 0.01
