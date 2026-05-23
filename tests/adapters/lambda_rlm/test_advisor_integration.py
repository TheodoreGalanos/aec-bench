# ABOUTME: Integration tests for advisor calls in the lambda-RLM adapter.
# ABOUTME: Verifies programmatic advisor consultation using shared utility.

import json

from aec_bench.adapters.advisor import default_advise
from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse
from aec_bench.contracts.advisor import AdvisorRequest


def _advisor_json(advice: str = "Focus on factual accuracy") -> str:
    return json.dumps(
        {
            "advice": advice,
            "suggested_action": "cross-reference with source doc",
            "confidence": 0.9,
            "reasoning": "source documents contain the required data",
        }
    )


class TestLambdaRlmAdvisorCall:
    def test_phase_aware_context(self) -> None:
        client = ReplayRlmClient(
            [
                RlmCompletionResponse(
                    output_text=_advisor_json(),
                    input_tokens=800,
                    output_tokens=300,
                ),
            ]
        )

        context_msgs = [
            {"role": "system", "content": "Phase: generate, Section: scope_of_works"},
            {"role": "system", "content": "Extraction found 12 fields from brief.md"},
            {"role": "system", "content": "Review flagged: missing road designations"},
        ]

        result = default_advise(
            request=AdvisorRequest(
                goal="Generate scope_of_works section",
                problem="Review flagged missing road designations",
                attempt="Tried extracting from section 3.2",
            ),
            context_messages=context_msgs,
            client=client,
            model="claude-opus-4-6",
            adapter_context=(
                "The executor is running a lambda-RLM pipeline with Plan → Extract → Review → Generate phases."
            ),
        )

        assert result.response is not None
        assert result.response.advice == "Focus on factual accuracy"
        assert result.input_tokens == 800

    def test_advisor_fallback_on_unparseable_response(self) -> None:
        client = ReplayRlmClient(
            [
                RlmCompletionResponse(
                    output_text="I don't know how to help with that.",
                    input_tokens=400,
                    output_tokens=50,
                ),
            ]
        )

        result = default_advise(
            request=AdvisorRequest(
                goal="Generate introduction section",
                problem="Missing context about project location",
            ),
            context_messages=[],
            client=client,
            model="claude-opus-4-6",
        )

        # Unparseable JSON falls back to raw text as advice
        assert result.response is not None
        assert result.response.advice == "I don't know how to help with that."
        assert result.response.confidence == 0.0
        assert result.input_tokens == 400

    def test_advisor_error_returns_safe_fallback(self) -> None:
        client = ReplayRlmClient(
            [
                RlmCompletionResponse(
                    output_text="",
                    input_tokens=100,
                    output_tokens=0,
                    error_message="Rate limited",
                ),
            ]
        )

        result = default_advise(
            request=AdvisorRequest(
                goal="Generate section",
                problem="Need guidance",
            ),
            context_messages=[],
            client=client,
            model="claude-opus-4-6",
        )

        assert result.error == "Rate limited"
        assert result.response is not None
        assert result.response.confidence == 0.0
