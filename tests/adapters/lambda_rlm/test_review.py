# ABOUTME: Tests for lambda-rlm contract review phase.
# ABOUTME: Validates review prompt dispatch, response parsing, and retry logic.

import json

from aec_bench.adapters.lambda_rlm.review import parse_review_response, run_review
from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse


def test_parse_review_response_pass():
    raw = json.dumps(
        {
            "status": "pass",
            "gaps": [],
            "risks": [],
            "reextract_sources": [],
            "supplement_guidance": None,
        }
    )
    result = parse_review_response(raw)
    assert result.status == "pass"
    assert result.needs_action is False


def test_parse_review_response_needs_reextract():
    raw = json.dumps(
        {
            "status": "needs_reextract",
            "gaps": ["Missing milestone dates"],
            "risks": ["Ambiguous design speed"],
            "reextract_sources": ["brief:milestones"],
            "supplement_guidance": None,
        }
    )
    result = parse_review_response(raw)
    assert result.status == "needs_reextract"
    assert result.needs_action is True
    assert "brief:milestones" in result.reextract_sources


def test_parse_review_response_malformed_falls_back_to_pass():
    """If the model returns unparseable JSON, default to pass (don't block)."""
    result = parse_review_response("This is not JSON at all.")
    assert result.status == "pass"
    assert result.needs_action is False


def test_run_review_calls_client():
    client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text=json.dumps(
                    {
                        "status": "pass",
                        "gaps": [],
                        "risks": [],
                        "reextract_sources": [],
                        "supplement_guidance": None,
                    }
                ),
                input_tokens=500,
                output_tokens=100,
            ),
        ]
    )
    result, tokens = run_review(
        client=client,
        model="test-model",
        section_title="Background",
        writing_guidance=["Carry language verbatim"],
        input_sources=["brief:Description"],
        extracted_data={"location": "Princes Highway"},
        dependency_summaries={},
    )
    assert result.status == "pass"
    assert tokens == (500, 100)
