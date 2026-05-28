# ABOUTME: Tests for provider-backed direct client helpers in aec-bench Python.
# ABOUTME: Covers payload reconstruction and required environment resolution.

import pytest

from aec_bench.adapters.base import SerializedClientSpec
from aec_bench.adapters.direct import DirectCompletionRequest
from aec_bench.adapters.direct_providers import (
    anthropic_direct_client_from_payload,
    azure_openai_chat_client_from_payload,
    required_env_values_for_client_spec,
    together_chat_client_from_payload,
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


def test_together_direct_client_rebuilds_from_payload() -> None:
    client = together_chat_client_from_payload(
        {
            "api_key_env": "TOGETHER_API_KEY",
            "max_tokens": 2048,
        }
    )

    assert client.api_key_env == "TOGETHER_API_KEY"
    assert client.base_url == "https://api.together.ai/v1"
    assert client.max_tokens == 2048


def test_together_direct_client_retries_streaming_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import io
    import urllib.error
    import urllib.request

    class _StreamingResponse:
        def __enter__(self) -> "_StreamingResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def __iter__(self):
            yield b'data: {"choices":[{"delta":{"content":"hello "}}]}\n\n'
            yield b'data: {"choices":[{"delta":{"content":"world"}}]}\n\n'
            yield b"data: [DONE]\n\n"

    calls: list[str] = []

    def fake_urlopen(request: urllib.request.Request, timeout: int):
        del timeout
        payload = request.data.decode() if request.data else ""
        calls.append(payload)
        if '"stream": true' not in payload:
            raise urllib.error.HTTPError(
                request.full_url,
                400,
                "Bad Request",
                hdrs=None,
                fp=io.BytesIO(
                    b'{"message":"This model only supports streaming. Set \\"stream\\": true.",'
                    b'"code":"streaming_required"}'
                ),
            )
        return _StreamingResponse()

    monkeypatch.setenv("TOGETHER_API_KEY", "tog-key")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = together_chat_client_from_payload(
        {
            "api_key_env": "TOGETHER_API_KEY",
            "max_tokens": 32,
            "stream_mode": "auto",
        }
    )

    response = client.complete(
        DirectCompletionRequest(
            model="together:Qwen/Qwen3.7-Max",
            instruction="say hello",
        )
    )

    assert response.error_message is None
    assert response.output_text == "hello world"
    assert len(calls) == 2
    assert '"stream": true' not in calls[0]
    assert '"stream": true' in calls[1]


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


def test_required_env_values_for_together_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOGETHER_API_KEY", "tog-key")

    env = required_env_values_for_client_spec(
        SerializedClientSpec(
            client_kind="together_chat",
            payload={"api_key_env": "TOGETHER_API_KEY"},
        )
    )

    assert env == {"TOGETHER_API_KEY": "tog-key"}


def test_required_env_values_raise_when_secret_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(RuntimeError):
        required_env_values_for_client_spec(
            SerializedClientSpec(
                client_kind="anthropic_api",
                payload={"api_key_env": "ANTHROPIC_API_KEY"},
            )
        )
