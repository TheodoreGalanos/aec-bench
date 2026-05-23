# ABOUTME: Tests for the shared advisor call utility.
# ABOUTME: Verifies call mechanism, JSON parsing, error handling, and token tracking.

import json

import pytest

from aec_bench.adapters.advisor import AdvisorResult, default_advise
from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse
from aec_bench.contracts.advisor import AdvisorRequest


def _make_advisor_json(
    advice: str = "Do X",
    suggested_action: str = "try Y",
    confidence: float = 0.9,
    reasoning: str = "because Z",
) -> str:
    return json.dumps(
        {
            "advice": advice,
            "suggested_action": suggested_action,
            "confidence": confidence,
            "reasoning": reasoning,
        }
    )


class TestDefaultAdvise:
    def test_successful_call(self) -> None:
        client = ReplayRlmClient(
            [
                RlmCompletionResponse(
                    output_text=_make_advisor_json(),
                    input_tokens=1200,
                    output_tokens=380,
                ),
            ]
        )
        result = default_advise(
            request=AdvisorRequest(goal="write intro", problem="no data"),
            context_messages=[{"role": "user", "content": "template is 50% done"}],
            client=client,
            model="claude-opus-4-6",
            max_response_tokens=500,
        )
        assert result.response is not None
        assert result.response.advice == "Do X"
        assert result.response.confidence == 0.9
        assert result.error is None
        assert result.input_tokens == 1200
        assert result.output_tokens == 380

    def test_json_in_code_block(self) -> None:
        wrapped = f"```json\n{_make_advisor_json(advice='wrapped')}\n```"
        client = ReplayRlmClient(
            [
                RlmCompletionResponse(output_text=wrapped, input_tokens=100, output_tokens=50),
            ]
        )
        result = default_advise(
            request=AdvisorRequest(goal="g", problem="p"),
            context_messages=[],
            client=client,
            model="m",
        )
        assert result.response is not None
        assert result.response.advice == "wrapped"

    def test_unparseable_response(self) -> None:
        client = ReplayRlmClient(
            [
                RlmCompletionResponse(
                    output_text="not json at all",
                    input_tokens=100,
                    output_tokens=50,
                ),
            ]
        )
        result = default_advise(
            request=AdvisorRequest(goal="g", problem="p"),
            context_messages=[],
            client=client,
            model="m",
        )
        assert result.response is not None
        assert result.response.advice == "not json at all"
        assert result.response.confidence == 0.0
        assert result.response.suggested_action == "continue"

    def test_client_error(self) -> None:
        client = ReplayRlmClient(
            [
                RlmCompletionResponse(error_message="timeout", input_tokens=0, output_tokens=0),
            ]
        )
        result = default_advise(
            request=AdvisorRequest(goal="g", problem="p"),
            context_messages=[],
            client=client,
            model="m",
        )
        assert result.error is not None
        assert "timeout" in result.error
        assert result.response is not None
        assert result.response.advice == "Advisor unavailable — proceed on your own judgement"
        assert result.response.confidence == 0.0

    def test_missing_fields_filled_with_defaults(self) -> None:
        partial = json.dumps({"advice": "just this"})
        client = ReplayRlmClient(
            [
                RlmCompletionResponse(output_text=partial, input_tokens=50, output_tokens=20),
            ]
        )
        result = default_advise(
            request=AdvisorRequest(goal="g", problem="p"),
            context_messages=[],
            client=client,
            model="m",
        )
        assert result.response is not None
        assert result.response.advice == "just this"
        assert result.response.suggested_action == "continue"
        assert result.response.confidence == 0.0
        assert result.response.reasoning == ""


class TestAdvisorResultAttributes:
    def test_getattr_hints(self) -> None:
        result = AdvisorResult(
            response=None,
            input_tokens=0,
            output_tokens=0,
            error="failed",
        )
        with pytest.raises(AttributeError, match="Use .response"):
            _ = result.advice  # type: ignore[attr-defined]
