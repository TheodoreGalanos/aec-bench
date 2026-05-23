# ABOUTME: Tests for the plain-synthesis engine.
# ABOUTME: Covers happy path, oversized input, model-side failure, and empty-output fallback.

from __future__ import annotations

import pytest

from aec_bench.contracts.synthesis import (
    SynthesisCandidate,
    SynthesisConfig,
    SynthesisCriteria,
    SynthesisInput,
)
from aec_bench.synthesis.engine import SynthesisBudgetError, synthesise


class FakeClient:
    """Minimal BehavioralLLMClient stub for engine tests."""

    def __init__(self, response: str = "synthesised draft text") -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4000,
    ) -> str:
        self.calls.append(
            {
                "prompt": prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return self.response


class RaisingClient:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def complete(self, prompt: str, *, temperature: float = 0.0, max_tokens: int = 4000) -> str:
        del prompt, temperature, max_tokens
        raise self._exc


def _minimal_input(
    *,
    candidates: tuple[SynthesisCandidate, ...] | None = None,
    references: dict[str, str] | None = None,
    config: SynthesisConfig | None = None,
) -> SynthesisInput:
    return SynthesisInput(
        candidates=candidates
        or (
            SynthesisCandidate(candidate_id="cand-0", content="Draft A"),
            SynthesisCandidate(candidate_id="cand-1", content="Draft B"),
        ),
        criteria=SynthesisCriteria(
            section_title="Methodology",
            writing_rules=("must mention X",),
            rubric_criteria=(("essential", "covers X"),),
            expert_personas=("Senior engineer",),
            summary="Outline the approach",
        ),
        references=references or {"source-doc": "source content describing X"},
        config=config or SynthesisConfig(),
    )


class TestHappyPath:
    def test_returns_trimmed_content(self) -> None:
        client = FakeClient(response="  synthesised output  \n")
        out = synthesise(_minimal_input(), client=client)
        assert out.content == "synthesised output"
        assert out.fallback_used is False
        assert out.fallback_reason is None
        assert out.synthesiser_model == "anthropic:claude-sonnet-4-6"

    def test_passes_config_to_client_call(self) -> None:
        client = FakeClient()
        config = SynthesisConfig(
            synthesiser_model="anthropic:claude-opus-4-7",
            max_output_tokens=12_000,
        )
        out = synthesise(_minimal_input(config=config), client=client, temperature=0.3)
        assert len(client.calls) == 1
        assert client.calls[0]["max_tokens"] == 12_000
        assert client.calls[0]["temperature"] == 0.3
        assert out.synthesiser_model == "anthropic:claude-opus-4-7"

    def test_prompt_contains_domain_hint(self) -> None:
        client = FakeClient()
        config = SynthesisConfig(domain_hint="legal contract")
        synthesise(_minimal_input(config=config), client=client)
        prompt = client.calls[0]["prompt"]
        assert isinstance(prompt, str)
        assert "legal contract" in prompt

    def test_prompt_contains_all_candidates(self) -> None:
        client = FakeClient()
        candidates = (
            SynthesisCandidate(candidate_id="cand-0", content="First draft content"),
            SynthesisCandidate(candidate_id="cand-1", content="Second draft content"),
            SynthesisCandidate(candidate_id="cand-2", content="Third draft content"),
        )
        synthesise(_minimal_input(candidates=candidates), client=client)
        prompt = client.calls[0]["prompt"]
        assert isinstance(prompt, str)
        assert "First draft content" in prompt
        assert "Second draft content" in prompt
        assert "Third draft content" in prompt

    def test_prompt_contains_references(self) -> None:
        client = FakeClient()
        synthesise(
            _minimal_input(references={"ref-1": "ground truth material"}),
            client=client,
        )
        prompt = client.calls[0]["prompt"]
        assert isinstance(prompt, str)
        assert "ground truth material" in prompt


class TestBudgetEnforcement:
    def test_oversized_input_raises_budget_error(self) -> None:
        client = FakeClient()
        # 50K chars of a single candidate easily exceeds a 1K token cap
        big = "word " * 50_000
        candidates = (SynthesisCandidate(candidate_id="cand-0", content=big),)
        config = SynthesisConfig(max_input_tokens=1_000)
        with pytest.raises(SynthesisBudgetError) as excinfo:
            synthesise(_minimal_input(candidates=candidates, config=config), client=client)
        assert "exceeds max_input_tokens" in str(excinfo.value)
        # Budget errors fire before the LLM call
        assert client.calls == []

    def test_normal_input_does_not_trip_budget(self) -> None:
        client = FakeClient()
        out = synthesise(_minimal_input(), client=client)
        assert out.content == "synthesised draft text"
        assert len(client.calls) == 1


class TestModelFailures:
    def test_client_exception_returns_fallback(self) -> None:
        client = RaisingClient(RuntimeError("rate limited"))
        out = synthesise(_minimal_input(), client=client)
        assert out.fallback_used is True
        assert out.fallback_reason is not None
        assert "RuntimeError" in out.fallback_reason
        assert "rate limited" in out.fallback_reason
        assert out.content == ""

    def test_empty_response_returns_fallback(self) -> None:
        client = FakeClient(response="")
        out = synthesise(_minimal_input(), client=client)
        assert out.fallback_used is True
        assert out.fallback_reason == "empty_output"
        assert out.content == ""

    def test_whitespace_only_response_returns_fallback(self) -> None:
        client = FakeClient(response="   \n\n   ")
        out = synthesise(_minimal_input(), client=client)
        assert out.fallback_used is True
        assert out.fallback_reason == "empty_output"


class TestTokenAccounting:
    def test_input_tokens_roughly_estimated(self) -> None:
        client = FakeClient()
        out = synthesise(_minimal_input(), client=client)
        # Prompt is ~1.5K chars minimum given our fixtures; expect >300 tokens
        assert out.input_tokens > 300
        # And bounded — the minimal fixture shouldn't run to 10K
        assert out.input_tokens < 10_000

    def test_output_tokens_scale_with_content(self) -> None:
        long = "Synthesised content. " * 500  # ~10K chars
        client = FakeClient(response=long)
        out = synthesise(_minimal_input(), client=client)
        assert out.output_tokens > 1_000
