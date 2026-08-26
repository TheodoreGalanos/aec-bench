# ABOUTME: Builds PydanticAI models from the repository model provider route.
# ABOUTME: Keeps optional provider imports and environment configuration at one boundary.

from __future__ import annotations

import os
from typing import TYPE_CHECKING, NotRequired, TypedDict

if TYPE_CHECKING:
    from pydantic_ai.models import KnownModelName, Model


def build_pydantic_model(model_name: str) -> Model | KnownModelName | str:
    """Build a PydanticAI model object from the model name.

    Provider detection is shared with the RLM provider router. Provider
    implementations are imported only when the selected route needs them.
    """
    from aec_bench.adapters.rlm.providers import resolve_pydantic_provider

    provider = resolve_pydantic_provider(model_name)

    if provider == "bedrock":
        from pydantic_ai.models.bedrock import BedrockConverseModel
        from pydantic_ai.providers.bedrock import BedrockProvider

        region = os.environ.get("AWS_REGION", "") or os.environ.get("AWS_DEFAULT_REGION", "")
        return BedrockConverseModel(
            model_name,
            provider=BedrockProvider(region_name=region or None),
        )

    if provider == "azure":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.azure import AzureProvider

        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
        api_version = os.environ.get(
            "AZURE_OPENAI_API_VERSION",
            os.environ.get("AGENT_API_VERSION", "2024-10-21"),
        )
        return OpenAIChatModel(
            model_name,
            provider=AzureProvider(**_azure_provider_kwargs(endpoint, api_key, api_version)),
        )

    if provider == "together":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        api_key = os.environ.get("TOGETHER_API_KEY", "")
        if not api_key:
            msg = "required environment variable is not set: TOGETHER_API_KEY"
            raise RuntimeError(msg)
        return OpenAIChatModel(
            _strip_together_prefix(model_name),
            provider=OpenAIProvider(base_url="https://api.together.ai/v1", api_key=api_key),
        )

    # "anthropic" or "auto" — let PydanticAI infer from model string.
    return model_name


def _strip_together_prefix(model_name: str) -> str:
    prefix = "together:"
    if model_name.lower().startswith(prefix):
        return model_name[len(prefix) :]
    return model_name


class _AzureProviderKwargs(TypedDict):
    azure_endpoint: str
    api_key: str
    api_version: NotRequired[str]


def _azure_provider_kwargs(
    endpoint: str,
    api_key: str,
    api_version: str,
) -> _AzureProviderKwargs:
    kwargs: _AzureProviderKwargs = {
        "azure_endpoint": endpoint,
        "api_key": api_key,
    }
    if api_version and not endpoint.rstrip("/").lower().endswith("/openai/v1"):
        kwargs["api_version"] = api_version
    return kwargs


__all__ = ("build_pydantic_model",)
