# ABOUTME: Tests for the lambda-RLM synthesis bridge.
# ABOUTME: Covers K=1 pass-through, happy path, fallback behaviour, and trajectory event shape.

from __future__ import annotations

from unittest.mock import patch

import pytest

from aec_bench.adapters.lambda_rlm.criteria import CriteriaBundle, RubricCriterion
from aec_bench.adapters.lambda_rlm.synthesis import (
    CandidateGeneration,
    synthesise_section,
)
from aec_bench.contracts.synthesis import (
    SynthesisConfig,
    SynthesisOutput,
)


def _bundle() -> CriteriaBundle:
    return CriteriaBundle(
        section_id="methodology",
        section_title="Methodology",
        summary="Outline the approach",
        writing_rules=("must mention X",),
        rubric_dimensions=("methodology_quality",),
        rubric_criteria=(RubricCriterion(text="covers X", category="essential"),),
        expert_personas=("Senior engineer",),
        eval_references=("doc-1",),
    )


def _candidates(n: int = 3) -> list[CandidateGeneration]:
    return [
        CandidateGeneration(
            candidate_id=f"cand-{i}",
            content=f"Candidate {i} draft content" + (" extra" * i),
            input_tokens=100 * (i + 1),
            output_tokens=50 * (i + 1),
        )
        for i in range(n)
    ]


class TestKEquals1:
    def test_single_candidate_passes_through_without_synthesis(self) -> None:
        only = CandidateGeneration(
            candidate_id="cand-0",
            content="single candidate text",
            input_tokens=500,
            output_tokens=200,
        )
        result = synthesise_section(
            section_id="methodology",
            candidates=[only],
            bundle=_bundle(),
            references={"doc-1": "content"},
            config=SynthesisConfig(),
        )
        assert result.content == "single candidate text"
        assert result.used_synthesiser is False
        assert result.trajectory_event["k"] == 1
        assert result.trajectory_event["reason"] == "single_candidate_pass_through"
        assert result.trajectory_event["fallback_used"] is False


class TestHappyPath:
    def test_returns_synthesised_content(self) -> None:
        candidates = _candidates(3)
        fake_output = SynthesisOutput(
            content="the synthesised draft",
            reason="merged candidate 1 and 2 facts",
            synthesiser_model="anthropic:claude-sonnet-4-6",
            input_tokens=5_000,
            output_tokens=1_200,
            elapsed_s=42.0,
        )
        with patch(
            "aec_bench.adapters.lambda_rlm.synthesis.synthesise",
            return_value=fake_output,
        ):
            result = synthesise_section(
                section_id="methodology",
                candidates=candidates,
                bundle=_bundle(),
                references={"doc-1": "content"},
                config=SynthesisConfig(),
            )
        assert result.content == "the synthesised draft"
        assert result.used_synthesiser is True
        event = result.trajectory_event
        assert event["k"] == 3
        assert len(event["candidates"]) == 3
        assert event["synthesiser_input_tokens"] == 5_000
        assert event["synthesiser_output_tokens"] == 1_200
        assert event["fallback_used"] is False

    def test_trajectory_event_hashes_candidates(self) -> None:
        candidates = _candidates(2)
        fake_output = SynthesisOutput(
            content="x",
            reason="",
            synthesiser_model="m",
            input_tokens=1,
            output_tokens=1,
            elapsed_s=0.1,
        )
        with patch(
            "aec_bench.adapters.lambda_rlm.synthesis.synthesise",
            return_value=fake_output,
        ):
            result = synthesise_section(
                section_id="methodology",
                candidates=candidates,
                bundle=_bundle(),
                references={},
                config=SynthesisConfig(),
            )
        # Same content → same hash; different content → different hash.
        hashes = [c["content_hash"] for c in result.trajectory_event["candidates"]]
        assert len(set(hashes)) == 2

    def test_trajectory_event_includes_candidate_content(self) -> None:
        # Full candidate text must appear in the event so offline reruns
        # (e.g., re-synthesising the same K candidates with different
        # criteria) can reconstruct the synthesis input from the trajectory.
        candidates = _candidates(3)
        fake_output = SynthesisOutput(
            content="y",
            reason="",
            synthesiser_model="m",
            input_tokens=1,
            output_tokens=1,
            elapsed_s=0.1,
        )
        with patch(
            "aec_bench.adapters.lambda_rlm.synthesis.synthesise",
            return_value=fake_output,
        ):
            result = synthesise_section(
                section_id="methodology",
                candidates=candidates,
                bundle=_bundle(),
                references={},
                config=SynthesisConfig(),
            )
        event_cands = result.trajectory_event["candidates"]
        assert [c["content"] for c in event_cands] == [c.content for c in candidates]

    def test_fallback_event_includes_candidate_content(self) -> None:
        candidates = _candidates(3)
        failed = SynthesisOutput(
            content="",
            reason="",
            synthesiser_model="m",
            input_tokens=0,
            output_tokens=0,
            elapsed_s=0.1,
            fallback_used=True,
            fallback_reason="empty_output",
        )
        with patch(
            "aec_bench.adapters.lambda_rlm.synthesis.synthesise",
            return_value=failed,
        ):
            result = synthesise_section(
                section_id="methodology",
                candidates=candidates,
                bundle=_bundle(),
                references={},
                config=SynthesisConfig(),
            )
        event_cands = result.trajectory_event["candidates"]
        assert [c["content"] for c in event_cands] == [c.content for c in candidates]

    def test_k1_passthrough_event_includes_candidate_content(self) -> None:
        only = CandidateGeneration(
            candidate_id="cand-0",
            content="single candidate text",
            input_tokens=500,
            output_tokens=200,
        )
        result = synthesise_section(
            section_id="methodology",
            candidates=[only],
            bundle=_bundle(),
            references={},
            config=SynthesisConfig(),
        )
        event_cands = result.trajectory_event["candidates"]
        assert event_cands[0]["content"] == "single candidate text"


class TestFallback:
    def test_synthesiser_failure_falls_back_to_longest(self) -> None:
        candidates = _candidates(3)
        # candidates[2] has "extra" appended twice → longest
        failed = SynthesisOutput(
            content="",
            reason="",
            synthesiser_model="anthropic:claude-sonnet-4-6",
            input_tokens=0,
            output_tokens=0,
            elapsed_s=5.0,
            fallback_used=True,
            fallback_reason="RuntimeError: rate_limited",
        )
        with patch(
            "aec_bench.adapters.lambda_rlm.synthesis.synthesise",
            return_value=failed,
        ):
            result = synthesise_section(
                section_id="methodology",
                candidates=candidates,
                bundle=_bundle(),
                references={},
                config=SynthesisConfig(),
            )
        assert result.used_synthesiser is False
        assert result.content == candidates[2].content
        assert result.trajectory_event["fallback_used"] is True
        assert "rate_limited" in result.trajectory_event["fallback_reason"]

    def test_budget_error_falls_back(self) -> None:
        from aec_bench.synthesis.engine import SynthesisBudgetError

        candidates = _candidates(3)
        with patch(
            "aec_bench.adapters.lambda_rlm.synthesis.synthesise",
            side_effect=SynthesisBudgetError("exceeds max_input_tokens 80000"),
        ):
            result = synthesise_section(
                section_id="methodology",
                candidates=candidates,
                bundle=_bundle(),
                references={},
                config=SynthesisConfig(),
            )
        assert result.used_synthesiser is False
        assert result.content == candidates[2].content
        assert "budget_exceeded" in result.trajectory_event["fallback_reason"]

    def test_fallback_disabled_raises(self) -> None:
        candidates = _candidates(3)
        failed = SynthesisOutput(
            content="",
            reason="",
            synthesiser_model="m",
            input_tokens=0,
            output_tokens=0,
            elapsed_s=0,
            fallback_used=True,
            fallback_reason="empty_output",
        )
        config = SynthesisConfig(fallback_on_failure=False)
        with patch(
            "aec_bench.adapters.lambda_rlm.synthesis.synthesise",
            return_value=failed,
        ):
            with pytest.raises(RuntimeError) as excinfo:
                synthesise_section(
                    section_id="methodology",
                    candidates=candidates,
                    bundle=_bundle(),
                    references={},
                    config=config,
                )
        assert "synthesis failed" in str(excinfo.value)


class TestInputValidation:
    def test_empty_candidates_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one candidate"):
            synthesise_section(
                section_id="methodology",
                candidates=[],
                bundle=_bundle(),
                references={},
                config=SynthesisConfig(),
            )


class TestToolLoopDispatch:
    def test_tool_loop_config_routes_to_driver(self) -> None:
        """When config.synthesis_mode == 'tool_loop', the bridge should
        invoke synthesise() with a pydantic-ai model (not a plain-synthesis
        client). We mock the engine to verify the dispatch path."""
        from aec_bench.contracts.synthesis import SynthesisConfig, SynthesisOutput

        candidates = _candidates(3)
        cfg = SynthesisConfig(
            synthesis_mode="tool_loop",
            synthesiser_model="anthropic:claude-sonnet-4-6",
        )
        fake_output = SynthesisOutput(
            content="tool-loop draft",
            reason="merged",
            synthesiser_model="anthropic:claude-sonnet-4-6",
            input_tokens=100,
            output_tokens=50,
            elapsed_s=1.0,
            synthesiser_turns=4,
            tool_calls=({"tool": "get_candidate", "args": {}},),
        )
        with patch(
            "aec_bench.adapters.lambda_rlm.synthesis.synthesise",
            return_value=fake_output,
        ) as mock_engine:
            result = synthesise_section(
                section_id="methodology",
                candidates=candidates,
                bundle=_bundle(),
                references={},
                config=cfg,
            )
        # The bridge must pass `model=` (not `client=`) for tool-loop mode.
        call_kwargs = mock_engine.call_args.kwargs
        assert "model" in call_kwargs
        assert call_kwargs.get("client") is None or "client" not in call_kwargs
        assert result.content == "tool-loop draft"
        assert result.used_synthesiser is True


class TestBundleConversion:
    def test_bundle_criteria_reach_synthesiser(self) -> None:
        candidates = _candidates(2)
        captured_input = {}

        def _capture(synthesis_input, *, client):  # noqa: ARG001
            captured_input["input"] = synthesis_input
            return SynthesisOutput(
                content="ok",
                reason="",
                synthesiser_model="m",
                input_tokens=1,
                output_tokens=1,
                elapsed_s=0.1,
            )

        with patch(
            "aec_bench.adapters.lambda_rlm.synthesis.synthesise",
            side_effect=_capture,
        ):
            synthesise_section(
                section_id="methodology",
                candidates=candidates,
                bundle=_bundle(),
                references={"doc-1": "ground truth"},
                config=SynthesisConfig(),
            )

        criteria = captured_input["input"].criteria
        assert criteria.section_title == "Methodology"
        assert criteria.writing_rules == ("must mention X",)
        assert criteria.rubric_criteria == (("essential", "covers X"),)
        assert criteria.expert_personas == ("Senior engineer",)
        assert captured_input["input"].references == {"doc-1": "ground truth"}
