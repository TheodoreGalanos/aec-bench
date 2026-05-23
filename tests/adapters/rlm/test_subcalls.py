# ABOUTME: Tests for the RLM typed sub-call framework and extract() default implementation.
# ABOUTME: Covers happy path parsing, malformed responses, and context injection.

"""Tests for the RLM typed sub-call framework and extract() default implementation."""

import pytest

from aec_bench.adapters.rlm.client import (
    ReplayRlmClient,
    RlmCompletionResponse,
    RlmMessage,
    ToolCall,
)
from aec_bench.adapters.rlm.subcalls import (
    CalculateResult,
    ExtractResult,
    ReasoningResult,
    RetrieveResult,
    SectionReviewResult,
    SummariseResult,
    VerificationResult,
    default_calculate,
    default_extract,
    default_reason,
    default_retrieve,
    default_review,
    default_summarise,
    default_verify,
)


def test_extract_returns_parsed_fields() -> None:
    client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text='```json\n{"wind_speed": 45.0, "terrain_cat": "TC2"}\n```',
                input_tokens=200,
                output_tokens=50,
            ),
        ]
    )
    result = default_extract(
        text="The design wind speed is 45 m/s for terrain category 2.",
        fields=["wind_speed", "terrain_cat"],
        client=client,
        model="test-model",
    )
    assert isinstance(result, ExtractResult)
    assert result.values["wind_speed"] == 45.0
    assert result.values["terrain_cat"] == "TC2"
    assert result.input_tokens == 200


def test_extract_handles_malformed_response() -> None:
    client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text="I couldn't find those fields.",
                input_tokens=200,
                output_tokens=50,
            ),
        ]
    )
    result = default_extract(
        text="Some text.",
        fields=["missing_field"],
        client=client,
        model="test-model",
    )
    assert result.error is not None
    assert result.values == {}


def test_extract_passes_context_to_prompt() -> None:
    responses = [
        RlmCompletionResponse(
            output_text='```json\n{"value": 1}\n```',
            input_tokens=100,
            output_tokens=50,
        ),
    ]
    captured_messages: list = []

    class CapturingClient:
        def generate(
            self,
            *,
            model: str,
            messages: list[RlmMessage],
            system_prompt: str | None,
        ) -> RlmCompletionResponse:
            captured_messages.extend(messages)
            return responses.pop(0)

    default_extract(
        text="Some text.",
        fields=["value"],
        client=CapturingClient(),
        model="test-model",
        context="This is a structural report.",
    )
    user_msg = next(m for m in captured_messages if m.role == "user")
    assert "structural report" in user_msg.content.lower()


def test_calculate_returns_result() -> None:
    client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text='```json\n{"moment_capacity": 245.5}\n```',
                input_tokens=150,
                output_tokens=40,
            ),
        ]
    )
    result = default_calculate(
        expression="beam moment capacity",
        parameters={"width": 300, "depth": 500, "fy": 500},
        client=client,
        model="test",
    )
    assert isinstance(result, CalculateResult)
    assert result.values["moment_capacity"] == 245.5


def test_retrieve_returns_results() -> None:
    client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text=('```json\n[{"text": "Clause 5.6.1", "source": "AS4100", "relevance": "high"}]\n```'),
                input_tokens=200,
                output_tokens=60,
            ),
        ]
    )
    result = default_retrieve(
        query="slenderness limits for steel columns",
        client=client,
        model="test",
    )
    assert isinstance(result, RetrieveResult)
    assert len(result.results) == 1
    assert result.results[0]["source"] == "AS4100"


def test_verify_returns_verdict() -> None:
    client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text=(
                    '```json\n{"passed": true, "confidence": 0.95, "explanation": "Value within limits"}\n```'
                ),
                input_tokens=100,
                output_tokens=30,
            ),
        ]
    )
    result = default_verify(
        value=245.5,
        criterion="Moment capacity must exceed demand of 200 kNm",
        client=client,
        model="test",
    )
    assert isinstance(result, VerificationResult)
    assert result.passed is True
    assert result.confidence == 0.95


def test_summarise_returns_text() -> None:
    client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text="The analysis shows compliance across all sections.",
                input_tokens=300,
                output_tokens=20,
            ),
        ]
    )
    result = default_summarise(
        content="Long detailed analysis text...",
        focus="compliance findings",
        client=client,
        model="test",
    )
    assert isinstance(result, SummariseResult)
    assert "compliance" in result.summary.lower()


def test_reason_returns_conclusion() -> None:
    client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text=(
                    "```json\n"
                    '{"conclusion": "Terzaghi", "confidence": 0.85,'
                    ' "rationale": "Shallow foundation on cohesive soil"}'
                    "\n```"
                ),
                input_tokens=200,
                output_tokens=50,
            ),
        ]
    )
    result = default_reason(
        question="Which bearing capacity formula applies?",
        context="Shallow strip footing on clay, c=50kPa",
        client=client,
        model="test",
    )
    assert isinstance(result, ReasoningResult)
    assert result.conclusion == "Terzaghi"
    assert result.confidence == 0.85


def test_calculate_handles_malformed_response() -> None:
    client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(output_text="I can't do that.", input_tokens=100, output_tokens=20),
        ]
    )
    result = default_calculate(
        expression="beam capacity",
        parameters={"width": 300},
        client=client,
        model="test",
    )
    assert result.error is not None
    assert result.values == {}


def test_verify_handles_malformed_response() -> None:
    client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(output_text="Not sure.", input_tokens=100, output_tokens=20),
        ]
    )
    result = default_verify(
        value=100,
        criterion="Must exceed 200",
        client=client,
        model="test",
    )
    assert result.error is not None


def test_reason_handles_malformed_response() -> None:
    client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(output_text="Hmm.", input_tokens=100, output_tokens=10),
        ]
    )
    result = default_reason(
        question="Which method?",
        client=client,
        model="test",
    )
    assert result.error is not None


class TestResultGetattr:
    def test_extract_result_success_hint(self) -> None:
        result = ExtractResult(values={"x": 1})
        with pytest.raises(AttributeError, match="Check .error is None"):
            _ = result.success

    def test_extract_result_data_hint(self) -> None:
        result = ExtractResult(values={"x": 1})
        with pytest.raises(AttributeError, match=r"\.values"):
            _ = result.data

    def test_extract_result_unknown_attr_lists_fields(self) -> None:
        result = ExtractResult(values={})
        with pytest.raises(AttributeError, match="Available"):
            _ = result.nonexistent

    def test_calculate_result_success_hint(self) -> None:
        result = CalculateResult(values={"y": 2})
        with pytest.raises(AttributeError, match="Check .error is None"):
            _ = result.success

    def test_calculate_result_output_hint(self) -> None:
        result = CalculateResult(values={"y": 2})
        with pytest.raises(AttributeError, match=r"\.values"):
            _ = result.output

    def test_retrieve_result_success_hint(self) -> None:
        result = RetrieveResult(results=[])
        with pytest.raises(AttributeError, match="Check .error is None"):
            _ = result.success

    def test_retrieve_result_values_hint(self) -> None:
        result = RetrieveResult(results=[])
        with pytest.raises(AttributeError, match=r"\.results"):
            _ = result.values

    def test_retrieve_result_data_hint(self) -> None:
        result = RetrieveResult(results=[])
        with pytest.raises(AttributeError, match=r"\.results"):
            _ = result.data

    def test_verification_result_success_hint(self) -> None:
        result = VerificationResult(passed=True)
        with pytest.raises(AttributeError, match=r"\.passed"):
            _ = result.success

    def test_verification_result_result_hint(self) -> None:
        result = VerificationResult(passed=False)
        with pytest.raises(AttributeError, match=r"\.passed"):
            _ = result.result

    def test_summarise_result_text_hint(self) -> None:
        result = SummariseResult(summary="hello")
        with pytest.raises(AttributeError, match=r"\.summary"):
            _ = result.text

    def test_summarise_result_success_hint(self) -> None:
        result = SummariseResult(summary="hello")
        with pytest.raises(AttributeError, match="Check .error is None"):
            _ = result.success

    def test_summarise_result_values_hint(self) -> None:
        result = SummariseResult(summary="hello")
        with pytest.raises(AttributeError, match=r"\.summary"):
            _ = result.values

    def test_reasoning_result_success_hint(self) -> None:
        result = ReasoningResult(conclusion="Terzaghi")
        with pytest.raises(AttributeError, match="Check .error is None"):
            _ = result.success

    def test_reasoning_result_text_hint(self) -> None:
        result = ReasoningResult(conclusion="Terzaghi")
        with pytest.raises(AttributeError, match=r"\.conclusion"):
            _ = result.text

    def test_reasoning_result_explanation_hint(self) -> None:
        result = ReasoningResult(conclusion="Terzaghi")
        with pytest.raises(AttributeError, match=r"\.rationale"):
            _ = result.explanation

    def test_reasoning_result_unknown_attr_lists_fields(self) -> None:
        result = ReasoningResult()
        with pytest.raises(AttributeError, match="Available"):
            _ = result.nonexistent

    def test_real_attributes_still_work(self) -> None:
        """Confirm __getattr__ does not interfere with legitimate attribute access."""
        extract = ExtractResult(values={"a": 1}, input_tokens=10, output_tokens=5)
        assert extract.values == {"a": 1}
        assert extract.input_tokens == 10
        assert extract.error is None

        verify = VerificationResult(passed=True, confidence=0.9, explanation="ok")
        assert verify.passed is True
        assert verify.confidence == 0.9
        assert verify.explanation == "ok"


class TestExtractStructuredOutput:
    """Tests for extract() using structured output via generate_with_tools."""

    def test_extract_uses_tool_call_when_available(self) -> None:
        """When client supports generate_with_tools, extract uses it."""
        import json as _json

        class ToolCapableClient:
            def generate(self, *, model, messages, system_prompt):
                raise AssertionError("Should use generate_with_tools")

            def generate_with_tools(
                self,
                *,
                model,
                messages,
                system_prompt,
                tool_name,
                tool_description,
                tool_parameters_schema,
            ):
                assert tool_name == "extraction_result"
                return RlmCompletionResponse(
                    output_text="",
                    input_tokens=300,
                    output_tokens=80,
                    tool_call=ToolCall(
                        name="extraction_result",
                        code=_json.dumps({"wind_speed": 45.0, "terrain_cat": "TC2"}),
                        call_id="call_1",
                    ),
                )

        result = default_extract(
            text="Wind speed is 45 m/s for TC2.",
            fields=["wind_speed", "terrain_cat"],
            client=ToolCapableClient(),
            model="test",
        )
        assert result.values["wind_speed"] == 45.0
        assert result.values["terrain_cat"] == "TC2"
        assert result.error is None

    def test_extract_falls_back_to_text_when_no_tool_support(self) -> None:
        """When client lacks generate_with_tools, falls back to text parsing."""
        client = ReplayRlmClient(
            responses=[
                RlmCompletionResponse(
                    output_text='```json\n{"voltage": 415}\n```',
                    input_tokens=200,
                    output_tokens=50,
                ),
            ]
        )
        result = default_extract(
            text="Supply voltage is 415V.",
            fields=["voltage"],
            client=client,
            model="test",
        )
        assert result.values["voltage"] == 415
        assert result.error is None

    def test_descriptive_fields_fall_back_to_text(self) -> None:
        """Fields with spaces/special chars use text path, not structured output."""

        class TextFallbackClient:
            def generate(self, *, model, messages, system_prompt):
                return RlmCompletionResponse(
                    output_text='```json\n{"drawings": ["E-001"]}\n```',
                    input_tokens=300,
                    output_tokens=80,
                )

            def generate_with_tools(self, **kw):
                raise AssertionError("Should NOT use structured output for descriptive fields")

        result = default_extract(
            text="Some document.",
            fields=["all drawing entries with number, title"],
            client=TextFallbackClient(),
            model="test",
        )
        # Should fall back to text path and succeed
        assert result.error is None
        assert "drawings" in result.values

    def test_extract_handles_tool_call_with_no_parseable_json(self) -> None:
        """When tool_call code is not valid JSON, falls back gracefully."""

        class ToolClient:
            def generate(self, **kw):
                raise AssertionError("Should not be called")

            def generate_with_tools(self, **kw):
                return RlmCompletionResponse(
                    output_text="",
                    input_tokens=200,
                    output_tokens=50,
                    tool_call=ToolCall(
                        name="extraction_result",
                        code="not valid json",
                        call_id="call_1",
                    ),
                )

        result = default_extract(
            text="Some text",
            fields=["field1"],
            client=ToolClient(),
            model="test",
        )
        assert result.error is not None


class TestExtractGoalDirected:
    """Tests for goal-directed extraction with section context."""

    def test_section_context_triggers_goal_directed_prompt(self) -> None:
        """When section_context is provided, uses writing guidance in prompt."""
        captured: list[str] = []

        class CapturingClient:
            def generate(self, *, model, messages, system_prompt):
                captured.append(messages[0].content)
                return RlmCompletionResponse(
                    output_text='```json\n{"project_id": "EST11221"}\n```',
                    input_tokens=500,
                    output_tokens=80,
                )

        result = default_extract(
            text="Project EST11221 at RAAF Base East Sale.",
            fields=["project_id", "location"],
            client=CapturingClient(),
            model="test",
            section_context={
                "section_title": "Introduction",
                "generation_mode": "transform",
                "writing_guidance": ["Include project ID", "State location clearly"],
                "dependency_context": {},
            },
        )
        assert result.error is None
        assert result.values["project_id"] == "EST11221"
        # Prompt should include writing guidance
        prompt = captured[0]
        assert "Introduction" in prompt
        assert "Include project ID" in prompt
        assert "snake_case" in prompt

    def test_goal_directed_without_fields(self) -> None:
        """Goal-directed extraction works without explicit fields."""
        captured: list[str] = []

        class CapturingClient:
            def generate(self, *, model, messages, system_prompt):
                captured.append(messages[0].content)
                return RlmCompletionResponse(
                    output_text='```json\n{"project_id": "EST11221", "location": "RAAF Base East Sale"}\n```',
                    input_tokens=500,
                    output_tokens=80,
                )

        result = default_extract(
            text="Project EST11221 at RAAF Base East Sale.",
            client=CapturingClient(),
            model="test",
            section_context={
                "section_title": "Introduction",
                "generation_mode": "transform",
                "writing_guidance": ["Include project ID", "State location"],
                "dependency_context": {},
            },
        )
        assert result.error is None
        assert "project_id" in result.values
        # Prompt should NOT have "Also extract these specific fields"
        prompt = captured[0]
        assert "Also extract" not in prompt
        assert "Include project ID" in prompt

    def test_without_section_context_uses_field_directed(self) -> None:
        """Without section_context, extract uses the normal field-directed path."""
        captured: list[str] = []

        class CapturingClient:
            def generate(self, *, model, messages, system_prompt):
                captured.append(messages[0].content)
                return RlmCompletionResponse(
                    output_text='```json\n{"voltage": 415}\n```',
                    input_tokens=300,
                    output_tokens=50,
                )

        result = default_extract(
            text="Supply voltage is 415V.",
            fields=["voltage"],
            client=CapturingClient(),
            model="test",
        )
        assert result.values["voltage"] == 415
        # Should NOT have writing guidance in prompt
        prompt = captured[0]
        assert "Writing guidance" not in prompt


class TestReviewSubcall:
    """Tests for the review() sub-call."""

    def test_review_returns_pass(self) -> None:
        client = ReplayRlmClient(
            responses=[
                RlmCompletionResponse(
                    output_text='```json\n{"status": "pass", "gaps": [], "risks": []}\n```',
                    input_tokens=500,
                    output_tokens=80,
                ),
            ]
        )
        result = default_review(
            section_content="The project is at RAAF Base East Sale.",
            writing_guidance=["Include project location"],
            client=client,
            model="test",
        )
        assert isinstance(result, SectionReviewResult)
        assert result.status == "pass"
        assert result.gaps == []
        assert result.risks == []
        assert result.error is None

    def test_review_returns_gaps_and_risks(self) -> None:
        client = ReplayRlmClient(
            responses=[
                RlmCompletionResponse(
                    output_text=(
                        "```json\n"
                        '{"status": "needs_work", '
                        '"gaps": ["Missing project ID EST11221"], '
                        '"risks": ["Acronym DESN not expanded"]}\n'
                        "```"
                    ),
                    input_tokens=600,
                    output_tokens=100,
                ),
            ]
        )
        result = default_review(
            section_content="The works involve HV upgrades.",
            writing_guidance=["Include project ID", "Expand all acronyms"],
            client=client,
            model="test",
        )
        assert result.status == "needs_work"
        assert len(result.gaps) == 1
        assert "EST11221" in result.gaps[0]
        assert len(result.risks) == 1

    def test_review_handles_malformed_response(self) -> None:
        client = ReplayRlmClient(
            responses=[
                RlmCompletionResponse(
                    output_text="Looks fine to me!",
                    input_tokens=400,
                    output_tokens=30,
                ),
            ]
        )
        result = default_review(
            section_content="Some content.",
            writing_guidance=["Rule 1"],
            client=client,
            model="test",
        )
        assert result.error is not None
