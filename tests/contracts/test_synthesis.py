# ABOUTME: Tests for synthesis boundary contracts.
# ABOUTME: Verifies frozen dataclasses, defaults, and config round-trip for TrialRecord capture.

from dataclasses import FrozenInstanceError, asdict

import pytest

from aec_bench.contracts.synthesis import (
    SynthesisCandidate,
    SynthesisConfig,
    SynthesisCriteria,
    SynthesisInput,
    SynthesisOutput,
)


class TestSynthesisConfig:
    def test_defaults_match_amendment_decisions(self) -> None:
        cfg = SynthesisConfig()
        assert cfg.synthesiser_model == "anthropic:claude-sonnet-4-6"
        assert cfg.max_input_tokens == 80_000
        assert cfg.max_output_tokens == 16_000
        assert cfg.verify_sources is True
        assert cfg.fallback_on_failure is True
        assert cfg.domain_hint == "engineering proposal"
        # Plain-synthesis remains the default; tool-loop is opt-in.
        assert cfg.synthesis_mode == "plain"
        assert cfg.tool_loop_max_turns == 20

    def test_tool_loop_mode_accepted(self) -> None:
        cfg = SynthesisConfig(synthesis_mode="tool_loop", tool_loop_max_turns=30)
        assert cfg.synthesis_mode == "tool_loop"
        assert cfg.tool_loop_max_turns == 30

    def test_frozen(self) -> None:
        cfg = SynthesisConfig()
        with pytest.raises(FrozenInstanceError):
            cfg.synthesiser_model = "other"  # type: ignore[misc]

    def test_round_trip_via_dict(self) -> None:
        """SynthesisConfig must round-trip through dict serialisation cleanly.

        The lambda-RLM adapter snapshots its full FillSectionConfig into
        TrialRecord.configuration (a dict[str, Any] slot). If a new field is
        added to SynthesisConfig but not captured, reproducibility breaks
        silently. This test catches that class of regression.
        """
        original = SynthesisConfig(
            synthesiser_model="anthropic:claude-opus-4-7",
            max_input_tokens=120_000,
            max_output_tokens=20_000,
            verify_sources=False,
            fallback_on_failure=False,
            domain_hint="legal contract",
            synthesis_mode="tool_loop",
            tool_loop_max_turns=25,
        )
        dict_form = asdict(original)
        rebuilt = SynthesisConfig(**dict_form)
        assert rebuilt == original

    def test_default_config_round_trips(self) -> None:
        original = SynthesisConfig()
        rebuilt = SynthesisConfig(**asdict(original))
        assert rebuilt == original


class TestSynthesisCandidate:
    def test_basic(self) -> None:
        c = SynthesisCandidate(candidate_id="cand-0", content="draft text")
        assert c.candidate_id == "cand-0"
        assert c.content == "draft text"

    def test_frozen(self) -> None:
        c = SynthesisCandidate(candidate_id="x", content="y")
        with pytest.raises(FrozenInstanceError):
            c.content = "other"  # type: ignore[misc]


class TestSynthesisCriteria:
    def test_required_fields_only(self) -> None:
        crit = SynthesisCriteria(
            section_title="Methodology",
            writing_rules=("rule 1",),
            rubric_criteria=(("essential", "must cover X"),),
            expert_personas=("Persona A",),
        )
        assert crit.summary == ""

    def test_all_fields(self) -> None:
        crit = SynthesisCriteria(
            section_title="Scope of Works",
            writing_rules=("rule 1", "rule 2"),
            rubric_criteria=(
                ("essential", "covers X"),
                ("important", "mentions Y"),
            ),
            expert_personas=("Engineer A", "Engineer B"),
            summary="Defines the work required",
        )
        assert crit.summary == "Defines the work required"
        assert len(crit.rubric_criteria) == 2


class TestSynthesisInput:
    def test_defaults_config(self) -> None:
        inp = SynthesisInput(
            candidates=(),
            criteria=SynthesisCriteria(
                section_title="X",
                writing_rules=(),
                rubric_criteria=(),
                expert_personas=(),
            ),
            references={},
        )
        # Default config field factory produces a SynthesisConfig with defaults
        assert isinstance(inp.config, SynthesisConfig)
        assert inp.config.synthesiser_model == "anthropic:claude-sonnet-4-6"


class TestSynthesisOutput:
    def test_success_shape(self) -> None:
        out = SynthesisOutput(
            content="synthesised draft",
            reason="merged candidates 1 and 3",
            synthesiser_model="anthropic:claude-sonnet-4-6",
            input_tokens=42_000,
            output_tokens=5_100,
            elapsed_s=57.6,
        )
        assert out.fallback_used is False
        assert out.fallback_reason is None
        # Tool-loop fields default to zero / empty for plain-synthesis outputs.
        assert out.synthesiser_turns == 0
        assert out.tool_calls == ()

    def test_tool_loop_shape(self) -> None:
        out = SynthesisOutput(
            content="draft",
            reason="merged",
            synthesiser_model="m",
            input_tokens=10,
            output_tokens=5,
            elapsed_s=1.0,
            synthesiser_turns=7,
            tool_calls=(
                {"tool": "get_candidate", "args": {"i": 0}},
                {"tool": "search_source", "args": {"query": "x"}},
            ),
        )
        assert out.synthesiser_turns == 7
        assert len(out.tool_calls) == 2
        assert out.tool_calls[0]["tool"] == "get_candidate"

    def test_fallback_shape(self) -> None:
        out = SynthesisOutput(
            content="",
            reason="",
            synthesiser_model="anthropic:claude-sonnet-4-6",
            input_tokens=0,
            output_tokens=0,
            elapsed_s=5.0,
            fallback_used=True,
            fallback_reason="budget_exhausted",
        )
        assert out.fallback_used is True
        assert out.fallback_reason == "budget_exhausted"


def test_contracts_exported_from_package() -> None:
    """Ensure the contracts package re-exports the synthesis types."""
    from aec_bench import contracts

    assert contracts.SynthesisCandidate is SynthesisCandidate
    assert contracts.SynthesisConfig is SynthesisConfig
    assert contracts.SynthesisCriteria is SynthesisCriteria
    assert contracts.SynthesisInput is SynthesisInput
    assert contracts.SynthesisOutput is SynthesisOutput
