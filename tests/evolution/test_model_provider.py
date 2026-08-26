# ABOUTME: Tests the PydanticAI model construction boundary used by evolution agents.
# ABOUTME: Verifies provider-specific model names and endpoints without calling a provider.

from __future__ import annotations

import pytest

from aec_bench.evolution.model_provider import build_pydantic_model


def test_build_pydantic_model_supports_together_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOGETHER_API_KEY", "tog-key")

    model = build_pydantic_model("together:Qwen/Qwen3.7-Max")

    assert str(model.base_url).rstrip("/") == "https://api.together.ai/v1"
    assert model.model_name == "Qwen/Qwen3.7-Max"
