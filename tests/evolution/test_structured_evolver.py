# ABOUTME: Tests for the structured evolver module.
# ABOUTME: Covers scope action limits and tool-loop evolver function signature.

from __future__ import annotations

import pytest

from aec_bench.evolution.structured_evolver import (
    _SCOPE_ACTION_LIMITS,
    _build_pydantic_model,
    call_structured_evolver_with_tools,
)


class TestScopeActionLimits:
    def test_scope_action_limits_are_defined(self) -> None:
        assert _SCOPE_ACTION_LIMITS["SKIP"] == 0
        assert _SCOPE_ACTION_LIMITS["MINIMAL"] == 1
        assert _SCOPE_ACTION_LIMITS["TARGETED"] == 3
        assert _SCOPE_ACTION_LIMITS["COMPREHENSIVE"] == 5

    def test_scope_action_limits_has_all_four_scopes(self) -> None:
        assert set(_SCOPE_ACTION_LIMITS.keys()) == {
            "SKIP",
            "MINIMAL",
            "TARGETED",
            "COMPREHENSIVE",
        }


class TestBuildPydanticModel:
    def test_build_pydantic_model_supports_together_prefix(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("TOGETHER_API_KEY", "tog-key")

        model = _build_pydantic_model("together:Qwen/Qwen3.7-Max")

        assert str(model.base_url).rstrip("/") == "https://api.together.ai/v1"
        assert model.model_name == "Qwen/Qwen3.7-Max"


class TestCallStructuredEvolverWithTools:
    def test_call_structured_evolver_with_tools_accepts_toolset(self) -> None:
        """Verify function signature accepts toolset parameter.

        Calls with a deliberately bad model name so the error is about the
        model (no API key / unknown model), not about a missing parameter
        or wrong function signature.
        """

        def fake_tool(query: str) -> str:
            return f"result for {query}"

        toolset = {"search_traces": fake_tool}

        with pytest.raises(Exception) as exc_info:
            call_structured_evolver_with_tools(
                model_name="not-a-real-model-xyz",
                system_prompt="You are an evolver.",
                analysis_brief="Analyse this.",
                toolset=toolset,
                scope="MINIMAL",
            )

        # The error must NOT be about the function signature itself —
        # TypeError from a bad call would indicate a signature mismatch.
        assert not isinstance(exc_info.value, TypeError), (
            f"Got TypeError, which suggests a signature problem: {exc_info.value}"
        )
