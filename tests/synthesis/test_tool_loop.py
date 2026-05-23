# ABOUTME: Tests for the synthesis tool-loop driver (pydantic-ai backed).
# ABOUTME: Uses pydantic-ai TestModel / FunctionModel to avoid real LLM calls.

from __future__ import annotations

import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    ToolCallPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from aec_bench.contracts.synthesis import (
    SynthesisCandidate,
    SynthesisConfig,
    SynthesisCriteria,
    SynthesisInput,
)
from aec_bench.synthesis.tool_loop import FinishResult, synthesise_via_tool_loop


def _input(k: int = 3) -> SynthesisInput:
    return SynthesisInput(
        candidates=tuple(
            SynthesisCandidate(
                candidate_id=f"cand-{i}",
                content=f"Candidate {i}: the kiosk substation is rated 500kVA.",
            )
            for i in range(k)
        ),
        criteria=SynthesisCriteria(
            section_title="Scope of Works",
            writing_rules=("The Contractor shall install per spec.",),
            rubric_criteria=(("essential", "mentions kiosk substation"),),
            expert_personas=("Senior electrical engineer",),
            summary="Electrical scope for substations",
        ),
        references={
            "source_a": "Kiosk substation type 500kVA, 22kV primary.",
            "source_b": "Earthing per AS/NZS 3000.",
        },
        config=SynthesisConfig(
            synthesis_mode="tool_loop",
            synthesiser_model="test",
            tool_loop_max_turns=10,
            max_output_tokens=4000,
        ),
    )


class TestHappyPath:
    def test_returns_synthesis_output_with_finish_payload(self) -> None:
        """TestModel auto-calls every registered tool once then emits the
        structured output. We verify the driver surfaces both the content
        and the tool-call trace on the SynthesisOutput."""
        model = TestModel(
            custom_output_args={
                "synthesised_section": "The Contractor shall install 500kVA kiosks.",
                "reason": "Merged fact from cand-0 with source_a verification.",
            },
        )
        result = synthesise_via_tool_loop(_input(), model=model)
        assert result.fallback_used is False
        assert "500kVA" in result.content
        assert "Merged" in result.reason
        # TestModel walks every @tool_plain once → 5 tool calls before finish.
        tool_names = {call["tool"] for call in result.tool_calls}
        assert tool_names == {
            "get_candidate",
            "get_source",
            "search_source",
            "search_across_candidates",
            "get_criteria_bundle",
        }
        assert result.synthesiser_turns >= 1

    def test_tool_calls_record_args(self) -> None:
        model = TestModel(
            custom_output_args={
                "synthesised_section": "draft",
                "reason": "r",
            },
        )
        result = synthesise_via_tool_loop(_input(), model=model)
        for call in result.tool_calls:
            assert "tool" in call
            assert "args" in call
            assert isinstance(call["args"], dict)


class TestTurnCap:
    def test_request_limit_triggers_fallback(self) -> None:
        """A model that never calls finish should hit the turn cap and the
        driver should return fallback_used=True with a budget reason."""

        def _never_finishes(
            messages: list[ModelMessage],  # noqa: ARG001
            info: AgentInfo,  # noqa: ARG001
        ) -> ModelResponse:
            # Always call get_candidate, never the output tool.
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="get_candidate",
                        args={"i": None},
                        tool_call_id="tc1",
                    ),
                ],
            )

        model = FunctionModel(_never_finishes)
        inp = _input()
        # Clamp turns so the fallback fires quickly.
        inp = SynthesisInput(
            candidates=inp.candidates,
            criteria=inp.criteria,
            references=inp.references,
            config=SynthesisConfig(
                synthesis_mode="tool_loop",
                synthesiser_model="test",
                tool_loop_max_turns=3,
                max_output_tokens=1000,
            ),
        )
        result = synthesise_via_tool_loop(inp, model=model)
        assert result.fallback_used is True
        assert result.fallback_reason is not None
        assert "UsageLimitExceeded" in result.fallback_reason
        # On UsageLimitExceeded we know the turn count — it equals the cap.
        # Reporting 0 would be misleading since the agent genuinely ran the
        # full budget (the B7 bootstrap run hit this path and the original
        # driver reported 0 turns alongside ~40 tool calls, which looked
        # like a serialisation bug until traced).
        assert result.synthesiser_turns == 3
        # The tool-call trace still captures activity up to the exception.
        assert len(result.tool_calls) >= 1


class TestFinishResultContract:
    def test_schema_has_two_fields(self) -> None:
        fields = FinishResult.model_fields
        assert set(fields) == {"synthesised_section", "reason"}

    def test_rejects_missing_fields(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            FinishResult()  # type: ignore[call-arg]
