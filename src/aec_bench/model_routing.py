# ABOUTME: Resolves model-name provider routes without importing provider implementations.
# ABOUTME: Gives runtimes and adapters one dependency-neutral routing rule.

from __future__ import annotations

import os
from collections.abc import Mapping

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
_AZURE_PREFIXES = ("gpt-", "gpt4", "o1-", "o3-", "o4-")
_ANTHROPIC_PREFIXES = ("claude-",)
_TOGETHER_PREFIX = "together:"
_BEDROCK_EXPLICIT_PREFIX = "bedrock:"


def detect_provider(model_name: str) -> str:
    """Detect the provider implied by a model name."""
    lower = model_name.lower()
    if lower.startswith(_BEDROCK_EXPLICIT_PREFIX):
        return "bedrock"
    if lower.startswith(_TOGETHER_PREFIX):
        return "together"
    if any(lower.startswith(prefix) for prefix in _BEDROCK_PREFIXES):
        return "bedrock"
    if any(lower.startswith(prefix) for prefix in _AZURE_PREFIXES):
        return "azure"
    if any(lower.startswith(prefix) for prefix in _ANTHROPIC_PREFIXES):
        return "anthropic"
    return "auto"


def resolve_pydantic_provider(model_name: str, env: Mapping[str, str] | None = None) -> str:
    """Resolve the PydanticAI provider without constructing a provider client."""
    source = env if env is not None else os.environ
    provider = detect_provider(model_name)
    if provider == "auto" and ":" in model_name:
        return "auto"
    if provider == "auto" and source.get("AZURE_OPENAI_ENDPOINT") and source.get("AZURE_OPENAI_API_KEY"):
        return "azure"
    return provider


__all__ = ("detect_provider", "resolve_pydantic_provider")
