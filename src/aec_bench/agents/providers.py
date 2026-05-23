# ABOUTME: Declarative provider configurations for LLM API endpoints.
# ABOUTME: Maps provider names to URL templates, auth styles, and required env vars.

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProviderConfig:
    """Configuration for a single LLM provider.

    The family field ("anthropic" or "openai") determines the API request/response
    format used by generated sandbox scripts. Anthropic-family providers use the
    Messages API format; OpenAI-family providers use Chat Completions format.
    """

    name: str
    family: str  # "anthropic" | "openai"
    url_template: str
    env_keys: list[str] = field(default_factory=list)
    auth_style: str = "bearer"  # "x-api-key" | "bearer" | "api-key-header"
    api_version_default: str | None = None
    api_version_env: str | None = None


PROVIDERS: dict[str, ProviderConfig] = {
    "anthropic": ProviderConfig(
        name="anthropic",
        family="anthropic",
        url_template="https://api.anthropic.com/v1/messages",
        env_keys=["ANTHROPIC_API_KEY"],
        auth_style="x-api-key",
    ),
    "bedrock": ProviderConfig(
        name="bedrock",
        family="anthropic",
        url_template="{endpoint}/model/{model}/invoke",
        env_keys=[
            "AWS_BEDROCK_ENDPOINT",
            "AWS_BEARER_TOKEN",
            "AWS_BEARER_TOKEN_BEDROCK",
            "AWS_REGION",
            "AWS_DEFAULT_REGION",
        ],
        auth_style="bearer",
    ),
    "azure_openai": ProviderConfig(
        name="azure_openai",
        family="openai",
        url_template=("{endpoint}/openai/deployments/{model}/chat/completions?api-version={api_version}"),
        env_keys=["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY"],
        auth_style="api-key-header",
        api_version_default="2024-10-21",
        api_version_env="AZURE_OPENAI_API_VERSION",
    ),
    "openai": ProviderConfig(
        name="openai",
        family="openai",
        url_template="https://api.openai.com/v1/chat/completions",
        env_keys=["OPENAI_API_KEY"],
        auth_style="bearer",
    ),
}


def get_provider(name: str) -> ProviderConfig:
    """Look up a provider config by name. Raises ValueError for unknown providers."""
    if name not in PROVIDERS:
        valid = ", ".join(sorted(PROVIDERS))
        raise ValueError(f"unknown provider: {name!r}. Valid providers: {valid}")
    return PROVIDERS[name]
