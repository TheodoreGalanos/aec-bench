# ABOUTME: Tests for the compaction prompt builder and sub-LLM compaction call.
# ABOUTME: Validates prompt structure, variable/scratchpad/template inclusion, and client calls.

from __future__ import annotations

from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse
from aec_bench.adapters.rlm.compaction import build_compaction_prompt, compact
from aec_bench.adapters.rlm.engine import ReplEnvironment
from aec_bench.adapters.rlm.scratchpad import Scratchpad
from aec_bench.adapters.rlm.template import TemplateStatus
from aec_bench.contracts.constitution import StatePersistenceParams


class TestBuildCompactionPrompt:
    """Tests for the structured compaction prompt builder."""

    def test_includes_variables(self) -> None:
        prompt = build_compaction_prompt(
            variables={"x": 42, "name": "Sydney"},
            scratchpad={},
            template_status=None,
            params=StatePersistenceParams(),
        )
        assert "x" in prompt
        assert "42" in prompt
        assert "Sydney" in prompt

    def test_includes_scratchpad(self) -> None:
        prompt = build_compaction_prompt(
            variables={},
            scratchpad={"wind_speed": 45, "region": "NSW"},
            template_status=None,
            params=StatePersistenceParams(),
        )
        assert "wind_speed" in prompt
        assert "45" in prompt

    def test_includes_template_status(self) -> None:
        status = TemplateStatus(
            total_sections=5,
            completed_sections=2,
            unlocked=["analysis"],
            pending=["analysis", "conclusion", "recommendations"],
            completed=["background", "methodology"],
        )
        prompt = build_compaction_prompt(
            variables={},
            scratchpad={},
            template_status=status,
            params=StatePersistenceParams(),
        )
        assert "2" in prompt and "5" in prompt
        assert "background" in prompt or "completed" in prompt.lower()

    def test_handles_empty_state(self) -> None:
        prompt = build_compaction_prompt(
            variables={},
            scratchpad={},
            template_status=None,
            params=StatePersistenceParams(),
        )
        # Should still produce a valid prompt
        assert "summarise" in prompt.lower() or "progress" in prompt.lower()

    def test_prompt_requests_structured_summary(self) -> None:
        prompt = build_compaction_prompt(
            variables={"data": [1, 2, 3]},
            scratchpad={"key": "value"},
            template_status=None,
            params=StatePersistenceParams(),
        )
        # Should ask for structured output
        assert "documents read" in prompt.lower() or "extracted data" in prompt.lower()


class TestCompact:
    """Tests for the compact() function that calls the sub-LLM."""

    def test_returns_summary_text(self, tmp_path) -> None:
        client = ReplayRlmClient(
            responses=[
                RlmCompletionResponse(
                    output_text="Summary: Agent read input docs and extracted wind speed data.",
                    input_tokens=200,
                    output_tokens=50,
                ),
            ]
        )
        repl = ReplEnvironment()
        repl.execute("wind_speed = 45")

        result = compact(
            client=client,
            model="test-model",
            repl=repl,
            scratchpad=None,
            template=None,
        )
        assert "wind speed" in result.summary.lower()
        assert result.input_tokens == 200
        assert result.output_tokens == 50

    def test_includes_scratchpad_in_call(self, tmp_path) -> None:
        """Scratchpad data should be passed to the compaction LLM."""
        responses_received: list[str] = []

        class CapturingClient:
            def generate(self, *, model, messages, system_prompt):
                responses_received.append(messages[0].content)
                return RlmCompletionResponse(
                    output_text="Compacted.",
                    input_tokens=100,
                    output_tokens=20,
                )

        repl = ReplEnvironment()
        pad = Scratchpad(path=str(tmp_path / ".scratchpad.json"))
        pad.note("facts", {"speed": 45})

        compact(
            client=CapturingClient(),
            model="test-model",
            repl=repl,
            scratchpad=pad,
            template=None,
        )
        assert len(responses_received) == 1
        assert "facts" in responses_received[0]

    def test_uses_compaction_system_prompt(self, tmp_path) -> None:
        """The compaction call should use a summarisation system prompt."""
        system_prompts_received: list[str] = []

        class CapturingClient:
            def generate(self, *, model, messages, system_prompt):
                system_prompts_received.append(system_prompt or "")
                return RlmCompletionResponse(
                    output_text="Summary.",
                    input_tokens=100,
                    output_tokens=20,
                )

        repl = ReplEnvironment()
        compact(
            client=CapturingClient(),
            model="test-model",
            repl=repl,
            scratchpad=None,
            template=None,
        )
        assert len(system_prompts_received) == 1
        assert "summarise" in system_prompts_received[0].lower()


class TestCompactionStrategies:
    def test_llm_summary_prompt_includes_all_state(self) -> None:
        params = StatePersistenceParams(compaction_strategy="llm_summary")
        prompt = build_compaction_prompt(
            variables={"x": 1},
            scratchpad={"note": "hello"},
            template_status=None,
            params=params,
        )
        assert "Summarise" in prompt
        assert "Variables" in prompt
        assert "Scratchpad" in prompt
        assert '"x": 1' in prompt

    def test_state_only_prompt_requests_list(self) -> None:
        params = StatePersistenceParams(compaction_strategy="state_only")
        prompt = build_compaction_prompt(
            variables={"x": 1},
            scratchpad={"note": "hello"},
            template_status=None,
            params=params,
        )
        # state_only strategy lists what's in state without asking for
        # a narrative summary.
        assert "Summarise" not in prompt
        assert "state" in prompt.lower()

    def test_full_reset_prompt_is_minimal(self) -> None:
        params = StatePersistenceParams(compaction_strategy="full_reset")
        prompt = build_compaction_prompt(
            variables={"x": 1},
            scratchpad={},
            template_status=None,
            params=params,
        )
        # Full reset keeps only essential orientation
        assert "reset" in prompt.lower() or "restart" in prompt.lower()

    def test_preserve_variables_false_excludes_variables(self) -> None:
        params = StatePersistenceParams(
            compaction_strategy="llm_summary",
            preserve_variables=False,
        )
        prompt = build_compaction_prompt(
            variables={"secret": "value"},
            scratchpad={},
            template_status=None,
            params=params,
        )
        assert "secret" not in prompt

    def test_preserve_scratchpad_false_excludes_scratchpad(self) -> None:
        params = StatePersistenceParams(
            compaction_strategy="llm_summary",
            preserve_scratchpad=False,
        )
        prompt = build_compaction_prompt(
            variables={},
            scratchpad={"note_key": "note_value"},
            template_status=None,
            params=params,
        )
        assert "note_key" not in prompt
        assert "note_value" not in prompt

    def test_default_params_match_legacy_behaviour(self) -> None:
        """Calling without params (using defaults) matches the pre-refactor output."""
        params = StatePersistenceParams()  # defaults: llm_summary, preserve all
        prompt = build_compaction_prompt(
            variables={"x": 1},
            scratchpad={"k": "v"},
            template_status=None,
            params=params,
        )
        assert "Summarise the agent's progress" in prompt
        assert '"x": 1' in prompt
        assert '"k"' in prompt
