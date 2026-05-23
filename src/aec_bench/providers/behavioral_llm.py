# ABOUTME: Provider-backed LLM client implementations for behavioral trace classification.
# ABOUTME: Supports Anthropic direct API and AWS Bedrock Converse API.

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Bedrock model name prefixes (same list used by rlm/providers.py)
_BEDROCK_PREFIXES = (
    "anthropic.claude",
    "au.anthropic.",
    "us.anthropic.",
    "eu.anthropic.",
    "ap.anthropic.",
    "amazon.",
    "us.amazon.",
    "meta.llama",
    "us.meta.",
    "mistral.",
    "us.mistral.",
    "cohere.",
    "us.cohere.",
    "ai21.",
    "us.ai21.",
)


def detect_behavioral_provider(model_name: str) -> str:
    """Detect provider from model name. Returns ``"bedrock"`` or ``"anthropic"``."""
    lower = model_name.lower()
    if any(lower.startswith(p) for p in _BEDROCK_PREFIXES):
        return "bedrock"
    return "anthropic"


def build_behavioral_llm_client(
    model: str,
) -> AnthropicBehavioralLLMClient | BedrockBehavioralLLMClient:
    """Build the right behavioral LLM client based on model name prefix.

    Bedrock models (``us.anthropic.*``, ``anthropic.claude*``, etc.) use
    the boto3 Converse API.  All others use the direct Anthropic HTTP API.
    """
    provider = detect_behavioral_provider(model)
    if provider == "bedrock":
        logger.info("Behavioral LLM: Bedrock provider for %s", model)
        return BedrockBehavioralLLMClient(model=model)
    logger.info("Behavioral LLM: Anthropic provider for %s", model)
    return AnthropicBehavioralLLMClient(model=model)


@dataclass(frozen=True)
class AnthropicBehavioralLLMClient:
    """Behavioral LLM client using the direct Anthropic HTTP API."""

    model: str
    api_key_env: str = "ANTHROPIC_API_KEY"
    anthropic_version: str = "2023-06-01"
    timeout_seconds: float = 90.0
    retry_budget_seconds: float = 120.0
    initial_backoff_seconds: float = 2.0
    max_backoff_seconds: float = 30.0

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4000,
    ) -> str:
        api_key = _required_env(self.api_key_env)
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        deadline = time.monotonic() + self.retry_budget_seconds
        attempt = 0
        last_error = "retry budget exhausted"

        while time.monotonic() < deadline:
            attempt += 1
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": self.anthropic_version,
                            "content-type": "application/json",
                        },
                        json=payload,
                    )
                    response.raise_for_status()
                    return _extract_text(response.json())
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                last_error = f"HTTP {status_code}: {exc.response.text[:200]}"
                if status_code in {400, 401, 403, 404}:
                    raise RuntimeError(last_error) from exc
                if status_code not in {429} and status_code < 500:
                    raise RuntimeError(last_error) from exc
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"

            time.sleep(
                min(
                    self.initial_backoff_seconds * (2 ** (attempt - 1)),
                    self.max_backoff_seconds,
                )
            )

        raise RuntimeError(last_error)


@dataclass(frozen=True)
class BedrockBehavioralLLMClient:
    """Behavioral LLM client using AWS Bedrock Converse API via boto3."""

    model: str
    region_env: str = "AWS_REGION"
    fallback_region_env: str = "AWS_DEFAULT_REGION"
    retry_budget_seconds: float = 120.0
    initial_backoff_seconds: float = 2.0
    max_backoff_seconds: float = 30.0
    # boto3 default read_timeout is 60s — fine for short judge calls, too short
    # for large synthesis prompts (16K+ output on 80K+ input). Callers with
    # heavy-output workloads should pass read_timeout_seconds=600 or similar.
    read_timeout_seconds: int = 60
    connect_timeout_seconds: int = 30

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4000,
    ) -> str:
        import boto3
        from botocore.config import Config

        region = os.environ.get(self.region_env, "") or os.environ.get(self.fallback_region_env, "")
        session_kwargs: dict[str, object] = {}
        if region:
            session_kwargs["region_name"] = region

        timeout_config_kwargs: dict[str, object] = {
            "read_timeout": self.read_timeout_seconds,
            "connect_timeout": self.connect_timeout_seconds,
        }

        client_kwargs: dict[str, object] = {}
        bearer_token = os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "")
        if bearer_token:
            from botocore.session import Session as BotocoreSession
            from botocore.tokens import FrozenAuthToken

            class _BearerSession(BotocoreSession):
                def __init__(self, token: str) -> None:
                    super().__init__()
                    self._token = token

                def get_auth_token(self, **_kwargs: object) -> FrozenAuthToken:
                    return FrozenAuthToken(self._token)

                def get_credentials(self) -> None:  # type: ignore[override]
                    return None

            session = boto3.Session(
                botocore_session=_BearerSession(bearer_token),
                **session_kwargs,
            )
            client_kwargs["config"] = Config(
                signature_version="bearer",
                **timeout_config_kwargs,
            )
            client = session.client("bedrock-runtime", **client_kwargs)
        else:
            client_kwargs["config"] = Config(**timeout_config_kwargs)
            client = boto3.client("bedrock-runtime", **session_kwargs, **client_kwargs)

        deadline = time.monotonic() + self.retry_budget_seconds
        attempt = 0
        last_error = "retry budget exhausted"

        while time.monotonic() < deadline:
            attempt += 1
            try:
                response = client.converse(
                    modelId=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": [{"text": prompt}],
                        }
                    ],
                    inferenceConfig={
                        "maxTokens": max_tokens,
                        "temperature": temperature,
                    },
                )
                return _extract_bedrock_text(response)

            except client.exceptions.ThrottlingException:
                pass  # retry below
            except client.exceptions.ModelTimeoutException:
                pass  # retry below
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                # Non-retryable errors (validation, access denied, etc.)
                error_code = (
                    getattr(
                        getattr(exc, "response", None),
                        "Error",
                        {},
                    ).get("Code", "")
                    if hasattr(exc, "response")
                    else ""
                )
                if error_code in (
                    "ValidationException",
                    "AccessDeniedException",
                    "ResourceNotFoundException",
                ):
                    raise RuntimeError(last_error) from exc

            time.sleep(
                min(
                    self.initial_backoff_seconds * (2 ** (attempt - 1)),
                    self.max_backoff_seconds,
                )
            )

        raise RuntimeError(last_error)


def _extract_text(payload: dict[str, object]) -> str:
    """Extract text from an Anthropic Messages API response."""
    content = payload.get("content", [])
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "\n".join(parts)


def _extract_bedrock_text(response: dict) -> str:
    """Extract text from a Bedrock Converse API response."""
    output = response.get("output", {})
    message = output.get("message", {})
    content = message.get("content", [])
    parts = []
    for block in content:
        if isinstance(block, dict) and "text" in block:
            parts.append(block["text"])
    return "\n".join(parts)


def _required_env(name: str) -> str:
    value = os.environ.get(name, "")
    if value:
        return value
    raise RuntimeError(f"required environment variable is not set: {name}")
