# ABOUTME: Tests for declarative provider configuration in the agents package.
# ABOUTME: Verifies each provider has correct auth style, env keys, URL template, and family.

import pytest

from aec_bench.agents.providers import PROVIDERS, get_provider


def test_anthropic_provider_config() -> None:
    p = get_provider("anthropic")
    assert p.name == "anthropic"
    assert p.family == "anthropic"
    assert p.auth_style == "x-api-key"
    assert "ANTHROPIC_API_KEY" in p.env_keys
    assert "api.anthropic.com" in p.url_template


def test_bedrock_provider_config() -> None:
    p = get_provider("bedrock")
    assert p.name == "bedrock"
    assert p.family == "anthropic"
    assert p.auth_style == "bearer"
    assert "AWS_BEDROCK_ENDPOINT" in p.env_keys
    assert "AWS_BEARER_TOKEN" in p.env_keys
    assert "{endpoint}" in p.url_template
    assert "{model}" in p.url_template


def test_azure_openai_provider_config() -> None:
    p = get_provider("azure_openai")
    assert p.name == "azure_openai"
    assert p.family == "openai"
    assert p.auth_style == "api-key-header"
    assert "AZURE_OPENAI_ENDPOINT" in p.env_keys
    assert "AZURE_OPENAI_API_KEY" in p.env_keys
    assert p.api_version_default == "2024-10-21"
    assert p.api_version_env == "AZURE_OPENAI_API_VERSION"
    assert "{endpoint}" in p.url_template
    assert "{api_version}" in p.url_template


def test_openai_provider_config() -> None:
    p = get_provider("openai")
    assert p.name == "openai"
    assert p.family == "openai"
    assert p.auth_style == "bearer"
    assert "OPENAI_API_KEY" in p.env_keys
    assert "api.openai.com" in p.url_template


def test_get_provider_unknown_raises_value_error() -> None:
    with pytest.raises(ValueError, match="unknown provider"):
        get_provider("gcp-vertex")


def test_all_providers_have_at_least_one_env_key() -> None:
    for name, config in PROVIDERS.items():
        assert len(config.env_keys) >= 1, f"provider {name} has no env_keys"


def test_provider_config_is_frozen() -> None:
    p = get_provider("anthropic")
    with pytest.raises(AttributeError):
        p.name = "modified"  # type: ignore[misc]


def test_all_providers_have_valid_family() -> None:
    valid_families = {"anthropic", "openai"}
    for name, config in PROVIDERS.items():
        assert config.family in valid_families, f"provider {name} has invalid family: {config.family}"
