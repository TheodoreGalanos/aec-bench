# ABOUTME: Tests for rubric evaluation contracts.
# ABOUTME: Verifies dimension scoring, rollup strategy, and details serialisation.

"""Tests for rubric evaluation contracts."""

from aec_bench.contracts.rubric import (
    DimensionScore,
    Rubric,
    RubricCriterion,
    RubricDimension,
    RubricResult,
)


def test_rubric_criterion_construction() -> None:
    criterion = RubricCriterion(
        text="Methodology cites specific measurements",
        category="essential",
    )
    assert criterion.text == "Methodology cites specific measurements"
    assert criterion.category == "essential"


def test_rubric_dimension_construction() -> None:
    dim = RubricDimension(
        id="completeness",
        name="Completeness",
        description="All required sections present",
        weight=1.0,
        max_score=10.0,
        eval_method="automated",
        criteria=[
            RubricCriterion(text="All sections filled", category="essential"),
            RubricCriterion(text="No gaps", category="important"),
        ],
    )
    assert dim.id == "completeness"
    assert dim.max_score == 10.0
    assert dim.eval_method == "automated"
    assert len(dim.criteria) == 2


def test_rubric_dimension_with_typed_criteria() -> None:
    dim = RubricDimension(
        id="depth",
        name="Technical Depth",
        description="Specificity of content",
        weight=2.0,
        max_score=10.0,
        eval_method="llm_judge",
        criteria=[
            RubricCriterion(text="Specific measurements", category="essential"),
            RubricCriterion(text="Named techniques", category="important"),
        ],
    )
    assert len(dim.criteria) == 2
    assert dim.criteria[0].category == "essential"


def test_rubric_construction() -> None:
    rubric = Rubric(
        dimensions=[
            RubricDimension(
                id="completeness",
                name="Completeness",
                description="Coverage",
                weight=1.0,
                max_score=10.0,
                eval_method="automated",
                criteria=[RubricCriterion(text="All sections", category="essential")],
            ),
            RubricDimension(
                id="accuracy",
                name="Accuracy",
                description="Correctness",
                weight=2.0,
                max_score=10.0,
                eval_method="llm_judge",
                criteria=[RubricCriterion(text="Values correct", category="essential")],
            ),
        ],
        rollup_strategy="weighted_mean",
    )
    assert len(rubric.dimensions) == 2
    assert rubric.rollup_strategy == "weighted_mean"


def test_dimension_score_construction() -> None:
    score = DimensionScore(
        dimension_id="completeness",
        score=8.0,
        max_score=10.0,
        evidence="3 of 3 sections filled",
        eval_method_used="automated",
    )
    assert score.score == 8.0
    assert score.max_score == 10.0


def test_dimension_score_with_satisfied_unsatisfied() -> None:
    score = DimensionScore(
        dimension_id="depth",
        score=7.0,
        max_score=10.0,
        evidence="Good specificity",
        eval_method_used="llm_judge",
        satisfied=["Specific measurements"],
        unsatisfied=["Named techniques missing"],
    )
    assert len(score.satisfied) == 1
    assert len(score.unsatisfied) == 1


def test_rubric_result_construction() -> None:
    result = RubricResult(
        dimension_scores=[
            DimensionScore(
                dimension_id="completeness",
                score=8.0,
                max_score=10.0,
                evidence="Good",
                eval_method_used="automated",
            ),
            DimensionScore(
                dimension_id="accuracy",
                score=7.0,
                max_score=10.0,
                evidence="Mostly correct",
                eval_method_used="llm_judge",
            ),
        ],
        reward=0.75,
        rollup_strategy="weighted_mean",
    )
    assert result.reward == 0.75
    assert len(result.dimension_scores) == 2


def test_rubric_result_to_details() -> None:
    result = RubricResult(
        dimension_scores=[
            DimensionScore(
                dimension_id="completeness",
                score=8.0,
                max_score=10.0,
                evidence="Good",
                eval_method_used="automated",
            ),
        ],
        reward=0.8,
        rollup_strategy="weighted_mean",
    )
    details = result.to_details()
    assert "completeness" in details
    assert details["completeness"]["score"] == 8.0
    assert details["completeness"]["max_score"] == 10.0
    assert "reward" in details


def test_rubric_result_to_details_includes_satisfied() -> None:
    result = RubricResult(
        dimension_scores=[
            DimensionScore(
                dimension_id="depth",
                score=7.0,
                max_score=10.0,
                evidence="Good",
                eval_method_used="llm_judge",
                satisfied=["Measurements cited"],
                unsatisfied=["Techniques missing"],
            ),
        ],
        reward=0.7,
        rollup_strategy="weighted_mean",
    )
    details = result.to_details()
    assert details["depth"]["satisfied"] == ["Measurements cited"]
    assert details["depth"]["unsatisfied"] == ["Techniques missing"]
