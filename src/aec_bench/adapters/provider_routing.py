# ABOUTME: Resolves the model provider and its approved host environment at the shared adapter entrypoint.
# ABOUTME: Keeps provider credentials out of serialized execution bundles while recording provider identity.

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from aec_bench.adapters.local_registry import detect_direct_provider
from aec_bench.adapters.rlm.providers import detect_provider


@dataclass(frozen=True)
class ProviderEnvironmentCapability:
    required: tuple[str, ...]
    optional: tuple[str, ...] = ()
    required_one_of: tuple[tuple[str, ...], ...] = ()


_PROVIDER_ENVIRONMENT_CAPABILITIES = {
    "anthropic": ProviderEnvironmentCapability(required=("ANTHROPIC_API_KEY",)),
    "azure": ProviderEnvironmentCapability(
        required=("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"),
        optional=("AZURE_OPENAI_API_VERSION",),
    ),
    "bedrock": ProviderEnvironmentCapability(
        required=("AWS_BEARER_TOKEN_BEDROCK",),
        required_one_of=(("AWS_REGION", "AWS_DEFAULT_REGION"),),
    ),
    "deepseek": ProviderEnvironmentCapability(
        required=("DEEPSEEK_API_KEY",),
        optional=("DEEPSEEK_BASE_URL",),
    ),
    "openai": ProviderEnvironmentCapability(required=("OPENAI_API_KEY",)),
    "together": ProviderEnvironmentCapability(required=("TOGETHER_API_KEY",)),
}

_CLIENT_PROVIDER = {
    "anthropic_api": "anthropic",
    "azure_openai_chat": "azure",
    "replay": None,
    "together_chat": "together",
}

_CLIENT_ENVIRONMENT_FIELDS = {
    "anthropic_api": {"api_key_env": "ANTHROPIC_API_KEY"},
    "azure_openai_chat": {
        "api_key_env": "AZURE_OPENAI_API_KEY",
        "endpoint_env": "AZURE_OPENAI_ENDPOINT",
    },
    "together_chat": {"api_key_env": "TOGETHER_API_KEY"},
}

_DEEPSEEK_HARNESS_PROVIDERS = frozenset({"azure", "deepseek"})


def provider_for_execution(
    *,
    adapter_kind: str,
    model_name: str,
    client_payload: Any,
) -> str | None:
    """Resolve one provider from stable execution inputs without reading credentials."""
    if adapter_kind == "deepseek_harness":
        provider, separator, provider_model = model_name.partition(":")
        provider = provider.strip().lower()
        if not separator or provider not in _DEEPSEEK_HARNESS_PROVIDERS or not provider_model.strip():
            supported = ", ".join(f"{name}:<model>" for name in sorted(_DEEPSEEK_HARNESS_PROVIDERS))
            raise ValueError(f"deepseek_harness model must use provider:model; supported routes: {supported}")
        return provider

    if isinstance(client_payload, dict):
        client_kind = client_payload.get("client_kind")
        if not isinstance(client_kind, str):
            return None
        _validate_client_environment_fields(client_kind, client_payload.get("payload", {}))
        return _CLIENT_PROVIDER.get(client_kind)

    if adapter_kind == "direct":
        return detect_direct_provider(model_name)

    detected = detect_provider(model_name)
    if detected != "auto":
        return detected
    provider_prefix = model_name.partition(":")[0].strip().lower()
    return {
        "anthropic": "anthropic",
        "azure": "azure",
        "deepseek": "deepseek",
        "openai": "openai",
    }.get(provider_prefix)


def provider_environment(
    provider: str | None,
    *,
    host_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return only the approved variables for the selected provider."""
    if provider is None:
        return {}
    try:
        capability = _PROVIDER_ENVIRONMENT_CAPABILITIES[provider]
    except KeyError as exc:
        raise ValueError(f"unsupported execution provider: {provider!r}") from exc

    source = os.environ if host_environment is None else host_environment
    missing = [name for name in capability.required if not source.get(name, "").strip()]
    missing_alternatives = [
        names for names in capability.required_one_of if not any(source.get(name, "").strip() for name in names)
    ]
    if missing or missing_alternatives:
        requirements = [*missing, *("one of " + ", ".join(names) for names in missing_alternatives)]
        raise RuntimeError(
            f"required provider environment configuration is not set for {provider}: " + "; ".join(requirements)
        )

    approved_names = (
        *capability.required,
        *capability.optional,
        *(name for names in capability.required_one_of for name in names),
    )
    return {name: source[name] for name in approved_names if source.get(name, "").strip()}


def _validate_client_environment_fields(client_kind: str, payload: Any) -> None:
    approved_fields = _CLIENT_ENVIRONMENT_FIELDS.get(client_kind, {})
    if not isinstance(payload, dict):
        return
    for field_name, approved_name in approved_fields.items():
        requested_name = payload.get(field_name, approved_name)
        if requested_name != approved_name:
            raise ValueError(
                f"host environment name {requested_name!r} is not approved for client kind {client_kind!r}; "
                f"use {approved_name!r}"
            )
