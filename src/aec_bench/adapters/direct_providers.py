# ABOUTME: Provider-backed direct clients for backend-side execution in aec-bench Python.
# ABOUTME: Implements authenticated Anthropic, Azure OpenAI, and Together direct completions.
# ABOUTME: Keeps provider env resolution and OpenAI-compatible response parsing in one place.

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, cast

from aec_bench.adapters.base import SerializedClientSpec
from aec_bench.adapters.direct import (
    DirectClient,
    DirectCompletionRequest,
    DirectCompletionResponse,
)
from aec_bench.adapters.pydantic_ai_runtime import (
    normalise_stream_mode,
    should_retry_with_streaming,
)

ResponseParser = Callable[[dict[str, Any]], DirectCompletionResponse]


@dataclass(frozen=True)
class AnthropicDirectClient(DirectClient):
    api_key_env: str = "ANTHROPIC_API_KEY"
    max_tokens: int = 16384
    anthropic_version: str = "2023-06-01"
    retry_budget_seconds: int = 120
    initial_backoff_seconds: int = 2
    max_backoff_seconds: int = 30

    def complete(self, request: DirectCompletionRequest) -> DirectCompletionResponse:
        api_key = _required_env(self.api_key_env)
        payload: dict[str, Any] = {
            "model": request.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": request.instruction}],
        }
        if request.system_prompt is not None:
            payload["system"] = request.system_prompt
        return _retrying_request(
            url="https://api.anthropic.com/v1/messages",
            payload=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": self.anthropic_version,
                "content-type": "application/json",
            },
            parser=_parse_anthropic_response,
            retry_budget_seconds=self.retry_budget_seconds,
            initial_backoff_seconds=self.initial_backoff_seconds,
            max_backoff_seconds=self.max_backoff_seconds,
        )


@dataclass(frozen=True)
class AzureOpenAIChatDirectClient(DirectClient):
    api_key_env: str = "AZURE_OPENAI_API_KEY"
    endpoint_env: str = "AZURE_OPENAI_ENDPOINT"
    deployment: str | None = None
    api_version: str = "2024-10-21"
    max_tokens: int = 16384
    retry_budget_seconds: int = 120
    initial_backoff_seconds: int = 2
    max_backoff_seconds: int = 30

    def complete(self, request: DirectCompletionRequest) -> DirectCompletionResponse:
        api_key = _required_env(self.api_key_env)
        endpoint = _required_env(self.endpoint_env).rstrip("/")
        deployment = self.deployment or request.model
        messages = [{"role": "user", "content": request.instruction}]
        if request.system_prompt is not None:
            messages.insert(0, {"role": "system", "content": request.system_prompt})
        return _retrying_request(
            url=(f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={self.api_version}"),
            payload={"max_tokens": self.max_tokens, "messages": messages},
            headers={"api-key": api_key, "content-type": "application/json"},
            parser=_parse_openai_compatible_response,
            retry_budget_seconds=self.retry_budget_seconds,
            initial_backoff_seconds=self.initial_backoff_seconds,
            max_backoff_seconds=self.max_backoff_seconds,
        )


@dataclass(frozen=True)
class TogetherChatDirectClient(DirectClient):
    api_key_env: str = "TOGETHER_API_KEY"
    base_url: str = "https://api.together.ai/v1"
    max_tokens: int = 16384
    retry_budget_seconds: int = 120
    initial_backoff_seconds: int = 2
    max_backoff_seconds: int = 30
    stream_mode: str = "auto"

    def complete(self, request: DirectCompletionRequest) -> DirectCompletionResponse:
        api_key = _required_env(self.api_key_env)
        messages = [{"role": "user", "content": request.instruction}]
        if request.system_prompt is not None:
            messages.insert(0, {"role": "system", "content": request.system_prompt})
        return _retrying_request(
            url=f"{self.base_url.rstrip('/')}/chat/completions",
            payload={
                "model": _strip_together_prefix(request.model),
                "max_tokens": self.max_tokens,
                "messages": messages,
            },
            headers={"Authorization": f"Bearer {api_key}", "content-type": "application/json"},
            parser=_parse_openai_compatible_response,
            retry_budget_seconds=self.retry_budget_seconds,
            initial_backoff_seconds=self.initial_backoff_seconds,
            max_backoff_seconds=self.max_backoff_seconds,
            stream_mode=self.stream_mode,
        )


def anthropic_direct_client_from_payload(payload: dict[str, Any]) -> AnthropicDirectClient:
    return AnthropicDirectClient(
        api_key_env=cast(str, payload.get("api_key_env", "ANTHROPIC_API_KEY")),
        max_tokens=int(payload.get("max_tokens", 16384)),
        anthropic_version=cast(str, payload.get("anthropic_version", "2023-06-01")),
    )


def azure_openai_chat_client_from_payload(
    payload: dict[str, Any],
) -> AzureOpenAIChatDirectClient:
    return AzureOpenAIChatDirectClient(
        api_key_env=cast(str, payload.get("api_key_env", "AZURE_OPENAI_API_KEY")),
        endpoint_env=cast(str, payload.get("endpoint_env", "AZURE_OPENAI_ENDPOINT")),
        deployment=cast(str | None, payload.get("deployment")),
        api_version=cast(str, payload.get("api_version", "2024-10-21")),
        max_tokens=int(payload.get("max_tokens", 16384)),
    )


def together_chat_client_from_payload(payload: dict[str, Any]) -> TogetherChatDirectClient:
    return TogetherChatDirectClient(
        api_key_env=cast(str, payload.get("api_key_env", "TOGETHER_API_KEY")),
        base_url=cast(str, payload.get("base_url", "https://api.together.ai/v1")),
        max_tokens=int(payload.get("max_tokens", 16384)),
        stream_mode=cast(str, payload.get("stream_mode", "auto")),
    )


def required_env_values_for_client_spec(spec: SerializedClientSpec) -> dict[str, str]:
    if spec.client_kind == "anthropic_api":
        env_name = cast(str, spec.payload.get("api_key_env", "ANTHROPIC_API_KEY"))
        return {env_name: _required_env(env_name)}
    if spec.client_kind == "azure_openai_chat":
        api_key_env = cast(str, spec.payload.get("api_key_env", "AZURE_OPENAI_API_KEY"))
        endpoint_env = cast(str, spec.payload.get("endpoint_env", "AZURE_OPENAI_ENDPOINT"))
        return {
            api_key_env: _required_env(api_key_env),
            endpoint_env: _required_env(endpoint_env),
        }
    if spec.client_kind == "together_chat":
        env_name = cast(str, spec.payload.get("api_key_env", "TOGETHER_API_KEY"))
        return {env_name: _required_env(env_name)}
    return {}


def _retrying_request(
    *,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    parser: ResponseParser,
    retry_budget_seconds: int,
    initial_backoff_seconds: int,
    max_backoff_seconds: int,
    stream_mode: str = "never",
) -> DirectCompletionResponse:
    resolved_stream_mode = normalise_stream_mode(stream_mode)
    if resolved_stream_mode == "always":
        return _streaming_openai_compatible_request(
            url=url,
            payload=payload,
            headers=headers,
            retry_budget_seconds=retry_budget_seconds,
            initial_backoff_seconds=initial_backoff_seconds,
            max_backoff_seconds=max_backoff_seconds,
        )

    deadline = time.time() + retry_budget_seconds
    attempt = 0
    last_error = ""
    encoded_payload = json.dumps(payload).encode()

    while time.time() < deadline:
        attempt += 1
        request = urllib.request.Request(
            url,
            data=encoded_payload,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                body = json.loads(response.read().decode())
                return parser(body)
        except urllib.error.HTTPError as exc:
            body_text = ""
            try:
                body_text = exc.read().decode()
            except Exception:
                body_text = ""
            last_error = f"HTTP {exc.code}: {body_text[:200]}"
            if resolved_stream_mode == "auto" and should_retry_with_streaming(last_error):
                return _streaming_openai_compatible_request(
                    url=url,
                    payload=payload,
                    headers=headers,
                    retry_budget_seconds=retry_budget_seconds,
                    initial_backoff_seconds=initial_backoff_seconds,
                    max_backoff_seconds=max_backoff_seconds,
                )
            if exc.code in (400, 401, 403, 404):
                return DirectCompletionResponse(output_text="", error_message=last_error)
            if exc.code == 429:
                time.sleep(_retry_after(exc, attempt, initial_backoff_seconds, max_backoff_seconds))
                continue
            if exc.code >= 500:
                time.sleep(min(initial_backoff_seconds * (2 ** (attempt - 1)), max_backoff_seconds))
                continue
            return DirectCompletionResponse(output_text="", error_message=last_error)
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(min(initial_backoff_seconds * (2 ** (attempt - 1)), max_backoff_seconds))

    return DirectCompletionResponse(
        output_text="",
        error_message=last_error or "retry budget exhausted",
    )


def _streaming_openai_compatible_request(
    *,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    retry_budget_seconds: int,
    initial_backoff_seconds: int,
    max_backoff_seconds: int,
) -> DirectCompletionResponse:
    streaming_payload = dict(payload)
    streaming_payload["stream"] = True
    deadline = time.time() + retry_budget_seconds
    attempt = 0
    last_error = ""

    while time.time() < deadline:
        attempt += 1
        request = urllib.request.Request(
            url,
            data=json.dumps(streaming_payload).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return _parse_openai_compatible_stream(response)
        except urllib.error.HTTPError as exc:
            body_text = ""
            try:
                body_text = exc.read().decode()
            except Exception:
                body_text = ""
            last_error = f"HTTP {exc.code}: {body_text[:200]}"
            if exc.code in (400, 401, 403, 404):
                return DirectCompletionResponse(output_text="", error_message=last_error)
            if exc.code == 429:
                time.sleep(_retry_after(exc, attempt, initial_backoff_seconds, max_backoff_seconds))
                continue
            if exc.code >= 500:
                time.sleep(min(initial_backoff_seconds * (2 ** (attempt - 1)), max_backoff_seconds))
                continue
            return DirectCompletionResponse(output_text="", error_message=last_error)
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(min(initial_backoff_seconds * (2 ** (attempt - 1)), max_backoff_seconds))

    return DirectCompletionResponse(
        output_text="",
        error_message=last_error or "retry budget exhausted",
    )


def _parse_anthropic_response(body: dict[str, Any]) -> DirectCompletionResponse:
    content_parts = cast(list[dict[str, Any]], body.get("content", []))
    output_text = "\n".join(cast(str, part.get("text", "")) for part in content_parts if part.get("type") == "text")
    usage = cast(dict[str, Any], body.get("usage", {}))
    return DirectCompletionResponse(
        output_text=output_text,
        usage_input_tokens=cast(int | None, usage.get("input_tokens")),
        usage_output_tokens=cast(int | None, usage.get("output_tokens")),
    )


def _parse_openai_compatible_stream(lines: Iterable[bytes | str]) -> DirectCompletionResponse:
    output_parts: list[str] = []
    usage: dict[str, Any] = {}
    for line in lines:
        text = line.decode() if isinstance(line, bytes) else line
        text = text.strip()
        if not text or not text.startswith("data:"):
            continue
        data = text.removeprefix("data:").strip()
        if data == "[DONE]":
            break
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            continue
        if event.get("usage"):
            usage = cast(dict[str, Any], event["usage"])
        for choice in cast(list[dict[str, Any]], event.get("choices", [])):
            delta = cast(dict[str, Any], choice.get("delta", {}))
            content = delta.get("content")
            if isinstance(content, str):
                output_parts.append(content)
            message = cast(dict[str, Any], choice.get("message", {}))
            message_content = message.get("content")
            if isinstance(message_content, str):
                output_parts.append(message_content)
    return DirectCompletionResponse(
        output_text="".join(output_parts),
        usage_input_tokens=cast(int | None, usage.get("prompt_tokens")),
        usage_output_tokens=cast(int | None, usage.get("completion_tokens")),
    )


def _parse_openai_compatible_response(body: dict[str, Any]) -> DirectCompletionResponse:
    choices = cast(list[dict[str, Any]], body.get("choices", []))
    output_text = ""
    if choices:
        message = cast(dict[str, Any], choices[0].get("message", {}))
        output_text = cast(str, message.get("content", ""))
    usage = cast(dict[str, Any], body.get("usage", {}))
    return DirectCompletionResponse(
        output_text=output_text,
        usage_input_tokens=cast(int | None, usage.get("prompt_tokens")),
        usage_output_tokens=cast(int | None, usage.get("completion_tokens")),
    )


def _retry_after(
    error: urllib.error.HTTPError,
    attempt: int,
    initial_backoff_seconds: int,
    max_backoff_seconds: int,
) -> float:
    retry_after_ms = error.headers.get("retry-after-ms")
    retry_after = error.headers.get("retry-after")
    if retry_after_ms is not None:
        retry_after_ms_value: float = float(retry_after_ms)
        return min(retry_after_ms_value / 1000.0, max_backoff_seconds)
    if retry_after is not None:
        retry_after_value: float = float(retry_after)
        return min(retry_after_value, max_backoff_seconds)
    fallback_wait: float = min(
        initial_backoff_seconds * (2 ** (attempt - 1)),
        max_backoff_seconds,
    )
    return fallback_wait


def _strip_together_prefix(model_name: str) -> str:
    prefix = "together:"
    if model_name.lower().startswith(prefix):
        return model_name[len(prefix) :]
    return model_name


def _required_env(name: str) -> str:
    value = os.environ.get(name, "")
    if value:
        return value
    msg = f"required environment variable is not set: {name}"
    raise RuntimeError(msg)
