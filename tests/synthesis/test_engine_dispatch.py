# ABOUTME: Tests that synthesise() dispatches to plain or tool-loop based on synthesis_mode.
# ABOUTME: Uses mocks for both paths — no real LLM calls.

from __future__ import annotations

from unittest.mock import patch

import pytest

from aec_bench.contracts.synthesis import (
    SynthesisCandidate,
    SynthesisConfig,
    SynthesisCriteria,
    SynthesisInput,
    SynthesisOutput,
)
from aec_bench.synthesis.engine import synthesise


def _input(mode: str = "plain") -> SynthesisInput:
    return SynthesisInput(
        candidates=(
            SynthesisCandidate(candidate_id="c0", content="draft 0"),
            SynthesisCandidate(candidate_id="c1", content="draft 1"),
        ),
        criteria=SynthesisCriteria(
            section_title="X",
            writing_rules=(),
            rubric_criteria=(),
            expert_personas=(),
        ),
        references={},
        config=SynthesisConfig(
            synthesis_mode=mode,  # type: ignore[arg-type]
            synthesiser_model="m",
        ),
    )


class _StubClient:
    def complete(self, prompt: str, *, temperature: float = 0.0, max_tokens: int = 4000) -> str:  # noqa: ARG002
        return "plain draft"


class TestDispatch:
    def test_plain_mode_uses_client(self) -> None:
        result = synthesise(_input("plain"), client=_StubClient())
        assert result.content == "plain draft"
        assert result.synthesiser_turns == 0  # plain leaves this default

    def test_tool_loop_mode_uses_driver(self) -> None:
        fake_output = SynthesisOutput(
            content="tool-loop draft",
            reason="dispatched",
            synthesiser_model="m",
            input_tokens=10,
            output_tokens=5,
            elapsed_s=0.1,
            synthesiser_turns=3,
            tool_calls=({"tool": "get_candidate", "args": {}},),
        )
        with patch(
            "aec_bench.synthesis.engine.synthesise_via_tool_loop",
            return_value=fake_output,
        ) as mock_driver:
            result = synthesise(_input("tool_loop"), model="test-model")
        assert result.content == "tool-loop draft"
        assert result.synthesiser_turns == 3
        # Plain-synthesis client must NOT be called.
        mock_driver.assert_called_once()

    def test_plain_without_client_raises(self) -> None:
        with pytest.raises(ValueError, match="client"):
            synthesise(_input("plain"))

    def test_tool_loop_without_model_raises(self) -> None:
        with pytest.raises(ValueError, match="model"):
            synthesise(_input("tool_loop"), client=_StubClient())
