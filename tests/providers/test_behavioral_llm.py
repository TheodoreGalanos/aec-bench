# ABOUTME: Tests provider-backed LLM clients for behavioral classification prompts.
# ABOUTME: Verifies Anthropic and Bedrock request formatting and provider detection.

import httpx
import pytest

from aec_bench.providers.behavioral_llm import (
    AnthropicBehavioralLLMClient,
    BedrockBehavioralLLMClient,
    build_behavioral_llm_client,
    detect_behavioral_provider,
)


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        del exc_type
        del exc
        del tb

    def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]) -> FakeResponse:
        self.calls.append({"url": url, "headers": headers, "json": json})
        return FakeResponse({"content": [{"type": "text", "text": '{"classifications": []}'}]})


def test_anthropic_behavioral_client_posts_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeClient()

    def fake_httpx_client(*, timeout: float) -> FakeClient:
        assert abs(timeout - 90.0) < 1e-9
        return fake_client

    monkeypatch.setattr(httpx, "Client", fake_httpx_client)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    client = AnthropicBehavioralLLMClient(model="claude-sonnet-4")

    response = client.complete("Classify this trace.", temperature=0.1, max_tokens=512)
    recorded_call = fake_client.calls[0]
    headers = recorded_call["headers"]
    payload = recorded_call["json"]

    assert isinstance(headers, dict)
    assert isinstance(payload, dict)

    assert response == '{"classifications": []}'
    assert recorded_call["url"] == "https://api.anthropic.com/v1/messages"
    assert headers["x-api-key"] == "test-key"
    assert payload == {
        "model": "claude-sonnet-4",
        "max_tokens": 512,
        "temperature": 0.1,
        "messages": [{"role": "user", "content": "Classify this trace."}],
    }


class TestDetectBehavioralProvider:
    """Tests for model-name-based provider detection."""

    def test_bedrock_prefixes(self) -> None:
        assert detect_behavioral_provider("us.anthropic.claude-sonnet-4-6") == "bedrock"
        assert detect_behavioral_provider("anthropic.claude-3-5-sonnet") == "bedrock"
        assert detect_behavioral_provider("eu.anthropic.claude-haiku") == "bedrock"

    def test_direct_anthropic(self) -> None:
        assert detect_behavioral_provider("claude-sonnet-4-6") == "anthropic"
        assert detect_behavioral_provider("claude-haiku-4-5-20251001") == "anthropic"

    def test_unknown_defaults_to_anthropic(self) -> None:
        assert detect_behavioral_provider("some-model") == "anthropic"


class TestBuildBehavioralLlmClient:
    """Tests for the factory function."""

    def test_bedrock_model_returns_bedrock_client(self) -> None:
        client = build_behavioral_llm_client("us.anthropic.claude-haiku-4-5-20251001")
        assert isinstance(client, BedrockBehavioralLLMClient)
        assert client.model == "us.anthropic.claude-haiku-4-5-20251001"

    def test_anthropic_model_returns_anthropic_client(self) -> None:
        client = build_behavioral_llm_client("claude-sonnet-4-6")
        assert isinstance(client, AnthropicBehavioralLLMClient)
        assert client.model == "claude-sonnet-4-6"


class TestBedrockBehavioralClient:
    """Tests for Bedrock Converse API client."""

    def test_calls_converse_api(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies the client calls boto3 converse with correct params."""
        captured_calls: list[dict] = []

        class FakeBedrockClient:
            class exceptions:
                class ThrottlingException(Exception):
                    pass

                class ModelTimeoutException(Exception):
                    pass

            def converse(self, **kwargs) -> dict:
                captured_calls.append(kwargs)
                return {
                    "output": {
                        "message": {
                            "content": [{"text": "classified result"}],
                        }
                    }
                }

        def fake_boto3_client(service: str, **kwargs) -> FakeBedrockClient:
            assert service == "bedrock-runtime"
            return FakeBedrockClient()

        import boto3

        monkeypatch.setattr(boto3, "client", fake_boto3_client)
        monkeypatch.setenv("AWS_REGION", "us-east-1")

        client = BedrockBehavioralLLMClient(
            model="us.anthropic.claude-haiku-4-5-20251001",
        )
        result = client.complete("Classify this.", temperature=0.1, max_tokens=2000)

        assert result == "classified result"
        assert len(captured_calls) == 1
        assert captured_calls[0]["modelId"] == "us.anthropic.claude-haiku-4-5-20251001"
        assert captured_calls[0]["inferenceConfig"]["maxTokens"] == 2000
        assert captured_calls[0]["inferenceConfig"]["temperature"] == 0.1


class TestBedrockReadTimeoutField:
    """Field-level tests for the read_timeout_seconds extension.

    Avoids the Converse API roundtrip so we don't get tangled in the
    pre-existing test's monkeypatch issue (it patches boto3.client but the
    code uses session.client()).
    """

    def test_default_preserves_historical_60s_timeout(self) -> None:
        client = BedrockBehavioralLLMClient(model="us.anthropic.claude-sonnet-4-6")
        assert client.read_timeout_seconds == 60
        assert client.connect_timeout_seconds == 30

    def test_override_read_timeout_for_synthesis_use_case(self) -> None:
        client = BedrockBehavioralLLMClient(
            model="us.anthropic.claude-sonnet-4-6",
            read_timeout_seconds=600,
        )
        assert client.read_timeout_seconds == 600

    def test_timeouts_propagate_into_boto3_config(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ensure the configured timeouts land on the boto3 Config object.

        We patch boto3.Session so we can inspect the Config kwargs without
        making a real AWS call.
        """
        captured_config_kwargs: dict[str, object] = {}

        class FakeSession:
            def __init__(self, **kwargs: object) -> None:
                del kwargs

            def client(self, service: str, **kwargs: object) -> object:
                del service
                cfg = kwargs.get("config")
                # botocore Config exposes timeouts via its _user_provided_options
                # dict; read from the attributes the Config accepts at construction.
                captured_config_kwargs["read_timeout"] = getattr(
                    cfg,
                    "read_timeout",
                    None,
                )
                captured_config_kwargs["connect_timeout"] = getattr(
                    cfg,
                    "connect_timeout",
                    None,
                )

                # Return a minimal stub that fails the converse call promptly so we
                # never make a real API call.
                class _Stub:
                    class exceptions:
                        class ThrottlingException(Exception):
                            pass

                        class ModelTimeoutException(Exception):
                            pass

                    def converse(self, **_kw: object) -> dict:
                        raise RuntimeError("stop_here")

                return _Stub()

        import boto3

        monkeypatch.setattr(boto3, "Session", FakeSession)
        monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)

        client = BedrockBehavioralLLMClient(
            model="us.anthropic.claude-sonnet-4-6",
            read_timeout_seconds=600,
            connect_timeout_seconds=45,
            retry_budget_seconds=0.1,  # fail fast instead of retrying
        )
        with pytest.raises(RuntimeError):
            client.complete("x", max_tokens=10)

        assert captured_config_kwargs["read_timeout"] == 600
        assert captured_config_kwargs["connect_timeout"] == 45
