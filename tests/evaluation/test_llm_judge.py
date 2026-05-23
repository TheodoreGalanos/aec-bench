# ABOUTME: Tests for the LLM-as-judge evaluation module.
# ABOUTME: Verifies prompt construction, response parsing, and score computation.

"""Tests for the LLM-as-judge evaluation module."""

import json

from aec_bench.contracts.rubric import (
    RubricCriterion,
    RubricDimension,
)
from aec_bench.evaluation.llm_judge import (
    build_judge_prompt,
    compute_criteria_score,
    parse_judge_response,
)


def test_build_judge_prompt_includes_criteria() -> None:
    dim = RubricDimension(
        id="depth",
        name="Technical Depth",
        description="Specificity",
        weight=2.0,
        max_score=10.0,
        eval_method="llm_judge",
        criteria=[
            RubricCriterion(text="Specific measurements", category="essential"),
            RubricCriterion(text="Named techniques", category="important"),
        ],
    )
    prompt = build_judge_prompt(
        dimension=dim,
        agent_output="The methodology uses TLS and QL-B.",
        reference_materials={"brief": "Project brief content"},
    )
    assert "Specific measurements" in prompt
    assert "Named techniques" in prompt
    assert "essential" in prompt.lower() or "ESSENTIAL" in prompt
    assert "Project brief content" in prompt


def test_build_judge_prompt_includes_reference_materials() -> None:
    dim = RubricDimension(
        id="style",
        name="Style",
        description="Tone",
        weight=1.0,
        max_score=10.0,
        eval_method="llm_judge",
        criteria=[RubricCriterion(text="Professional tone", category="essential")],
    )
    prompt = build_judge_prompt(
        dimension=dim,
        agent_output="Output text",
        reference_materials={"reference_proposal": "Previous proposal text"},
    )
    assert "Previous proposal text" in prompt


def test_parse_judge_response_valid_json() -> None:
    response = json.dumps(
        {
            "criteria_results": [
                {
                    "criterion": "Specific measurements",
                    "passed": True,
                    "evidence": "Cited radius 81m",
                },
                {
                    "criterion": "Named techniques",
                    "passed": False,
                    "evidence": "Generic terms used",
                },
            ]
        }
    )
    results = parse_judge_response(response)
    assert len(results) == 2
    assert results[0]["passed"] is True
    assert results[1]["passed"] is False


def test_parse_judge_response_json_in_code_block() -> None:
    inner = '{"criteria_results": [{"criterion": "A", "passed": true, "evidence": "ok"}]}'
    response = f"```json\n{inner}\n```"
    results = parse_judge_response(response)
    assert len(results) == 1
    assert results[0]["passed"] is True


def test_parse_judge_response_malformed_returns_empty() -> None:
    results = parse_judge_response("This is not JSON at all.")
    assert results == []


def test_compute_criteria_score_all_pass() -> None:
    criteria = [
        RubricCriterion(text="A", category="essential"),
        RubricCriterion(text="B", category="important"),
    ]
    results = [
        {"criterion": "A", "passed": True, "evidence": "ok"},
        {"criterion": "B", "passed": True, "evidence": "ok"},
    ]
    score, max_score, satisfied, unsatisfied = compute_criteria_score(
        criteria=criteria,
        results=results,
        max_score=10.0,
    )
    # All pass: (1.0 + 0.7) / (1.0 + 0.7) * 10 = 10.0
    assert abs(score - 10.0) < 0.01
    assert satisfied == ["A", "B"]
    assert unsatisfied == []


def test_compute_criteria_score_partial_pass() -> None:
    criteria = [
        RubricCriterion(text="A", category="essential"),
        RubricCriterion(text="B", category="important"),
        RubricCriterion(text="C", category="optional"),
    ]
    results = [
        {"criterion": "A", "passed": True, "evidence": "ok"},
        {"criterion": "B", "passed": False, "evidence": "missing"},
        {"criterion": "C", "passed": False, "evidence": "missing"},
    ]
    score, max_score, satisfied, unsatisfied = compute_criteria_score(
        criteria=criteria,
        results=results,
        max_score=10.0,
    )
    # Pass: essential 1.0. Fail: important 0.7 + optional 0.3
    # Score: 1.0 / (1.0 + 0.7 + 0.3) * 10 = 5.0
    assert abs(score - 5.0) < 0.01
    assert satisfied == ["A"]
    assert unsatisfied == ["B", "C"]


def test_compute_criteria_score_none_pass() -> None:
    criteria = [
        RubricCriterion(text="A", category="essential"),
    ]
    results = [
        {"criterion": "A", "passed": False, "evidence": "not found"},
    ]
    score, _, _, _ = compute_criteria_score(
        criteria=criteria,
        results=results,
        max_score=10.0,
    )
    assert score == 0.0


def test_compute_criteria_score_missing_results_treated_as_fail() -> None:
    criteria = [
        RubricCriterion(text="A", category="essential"),
        RubricCriterion(text="B", category="essential"),
    ]
    # Only one result returned by judge
    results = [
        {"criterion": "A", "passed": True, "evidence": "ok"},
    ]
    score, _, satisfied, unsatisfied = compute_criteria_score(
        criteria=criteria,
        results=results,
        max_score=10.0,
    )
    # A passes (1.0), B missing treated as fail (0.0). Score: 1.0/2.0 * 10 = 5.0
    assert abs(score - 5.0) < 0.01
    assert satisfied == ["A"]
    assert unsatisfied == ["B"]
