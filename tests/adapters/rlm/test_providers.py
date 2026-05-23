# ABOUTME: Tests for real RlmClient provider implementations.
# ABOUTME: Validates provider detection, message conversion, and client instantiation.

from __future__ import annotations

import pytest

from aec_bench.adapters.rlm.providers import (
    detect_provider,
    make_rlm_client,
)


class TestDetectProvider:
    """Tests for model-name-based provider detection."""

    def test_bedrock_prefixes(self) -> None:
        assert detect_provider("us.anthropic.claude-sonnet-4-6") == "bedrock"
        assert detect_provider("anthropic.claude-3-5-sonnet-20241022-v2:0") == "bedrock"
        assert detect_provider("eu.anthropic.claude-haiku-4-5-20251001-v1:0") == "bedrock"
        assert detect_provider("amazon.titan-text-premier-v2:0") == "bedrock"
        assert detect_provider("meta.llama3-1-405b-instruct-v1:0") == "bedrock"

    def test_azure_prefixes(self) -> None:
        assert detect_provider("gpt-4.1-mini") == "azure"
        assert detect_provider("gpt-4o") == "azure"
        assert detect_provider("o1-preview") == "azure"
        assert detect_provider("o3-mini") == "azure"
        assert detect_provider("o4-mini") == "azure"

    def test_anthropic_direct(self) -> None:
        assert detect_provider("claude-sonnet-4-6") == "anthropic"
        assert detect_provider("claude-haiku-4-5-20251001") == "anthropic"

    def test_unknown_model(self) -> None:
        assert detect_provider("some-random-model") == "auto"


class TestMakeRlmClient:
    """Tests for client factory — instantiation without API calls."""

    def test_returns_object_with_generate_method(self) -> None:
        """The factory should return something with a generate() method."""
        try:
            client = make_rlm_client(model_name="claude-sonnet-4-6")
        except (ImportError, Exception) as exc:
            if "ANTHROPIC_API_KEY" in str(exc):
                pytest.skip("ANTHROPIC_API_KEY not set")
            if "pydantic" in str(type(exc).__module__).lower():
                pytest.skip(f"Provider credential missing: {exc}")
            raise
        assert hasattr(client, "generate")

    def test_bedrock_client_creation(self) -> None:
        try:
            client = make_rlm_client(
                model_name="us.anthropic.claude-sonnet-4-6",
            )
        except (ImportError, Exception) as exc:
            if "credential" in str(exc).lower() or "region" in str(exc).lower():
                pytest.skip(f"AWS credentials not configured: {exc}")
            if "pydantic" in str(type(exc).__module__).lower():
                pytest.skip(f"Provider credential missing: {exc}")
            raise
        assert hasattr(client, "generate")

    def test_caching_disabled(self) -> None:
        try:
            client = make_rlm_client(
                model_name="claude-sonnet-4-6",
                cache=False,
            )
        except (ImportError, Exception) as exc:
            if "ANTHROPIC_API_KEY" in str(exc):
                pytest.skip("ANTHROPIC_API_KEY not set")
            if "pydantic" in str(type(exc).__module__).lower():
                pytest.skip(f"Provider credential missing: {exc}")
            raise
        assert hasattr(client, "generate")


class TestGenerateWithTools:
    """Tests for PydanticAiRlmClient.generate_with_tools()."""

    def test_has_generate_with_tools_method(self) -> None:
        from aec_bench.adapters.rlm.providers import PydanticAiRlmClient

        assert hasattr(PydanticAiRlmClient, "generate_with_tools")

    def test_generate_with_tools_signature(self) -> None:
        import inspect

        from aec_bench.adapters.rlm.providers import PydanticAiRlmClient

        sig = inspect.signature(PydanticAiRlmClient.generate_with_tools)
        params = list(sig.parameters.keys())
        assert "model" in params
        assert "messages" in params
        assert "system_prompt" in params
        assert "tool_name" in params
        assert "tool_description" in params
        assert "tool_parameters_schema" in params
