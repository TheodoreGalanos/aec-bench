# ABOUTME: Tests for provider-backed direct client helpers in aec-bench Python.
# ABOUTME: Covers payload reconstruction and required environment resolution.

import pytest

from aec_bench.adapters.base import SerializedClientSpec
from aec_bench.adapters.direct_providers import (
    anthropic_direct_client_from_payload,
    azure_openai_chat_client_from_payload,
    required_env_values_for_client_spec,
)


def test_anthropic_direct_client_rebuilds_from_payload() -> None:
    client = anthropic_direct_client_from_payload({"api_key_env": "ANTHROPIC_API_KEY", "max_tokens": 4096})

    assert client.api_key_env == "ANTHROPIC_API_KEY"
    assert client.max_tokens == 4096


def test_azure_direct_client_rebuilds_from_payload() -> None:
    client = azure_openai_chat_client_from_payload(
        {
            "api_key_env": "AZURE_OPENAI_API_KEY",
            "endpoint_env": "AZURE_OPENAI_ENDPOINT",
            "deployment": "gpt-4.1-mini",
            "api_version": "2024-10-21",
            "max_tokens": 2048,
        }
    )

    assert client.api_key_env == "AZURE_OPENAI_API_KEY"
    assert client.endpoint_env == "AZURE_OPENAI_ENDPOINT"
    assert client.deployment == "gpt-4.1-mini"
    assert client.max_tokens == 2048


def test_required_env_values_for_anthropic_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-key")

    env = required_env_values_for_client_spec(
        SerializedClientSpec(
            client_kind="anthropic_api",
            payload={"api_key_env": "ANTHROPIC_API_KEY"},
        )
    )

    assert env == {"ANTHROPIC_API_KEY": "secret-key"}


def test_required_env_values_for_azure_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")

    env = required_env_values_for_client_spec(
        SerializedClientSpec(
            client_kind="azure_openai_chat",
            payload={
                "api_key_env": "AZURE_OPENAI_API_KEY",
                "endpoint_env": "AZURE_OPENAI_ENDPOINT",
            },
        )
    )

    assert env == {
        "AZURE_OPENAI_API_KEY": "azure-key",
        "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
    }


def test_required_env_values_raise_when_secret_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(RuntimeError):
        required_env_values_for_client_spec(
            SerializedClientSpec(
                client_kind="anthropic_api",
                payload={"api_key_env": "ANTHROPIC_API_KEY"},
            )
        )
