# ABOUTME: Validates the DeepSeek adapter's fixed treatment and per-trial request limits.
# ABOUTME: Keeps unsupported adapter configuration out of the runtime boundary.

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, cast

from aec_bench.adapters.base import AdapterRequest
from aec_bench.adapters.output_commit import (
    configured_output_completion_commit,
    configured_output_completion_contract,
)
from aec_bench.contracts.output_completion import OutputCompletionContract
from aec_bench.contracts.validators import NonEmptyStr, StrictModel

DeepSeekHarnessProvider = Literal["azure", "deepseek"]
HarnessProviderRoute = Literal["azure", "deepseek-official"]

DEFAULT_TIMEOUT_SECONDS = 1800
DEFAULT_DEEPSEEK_SYSTEM_PROMPT = "You are a software engineering agent."
DEEPSEEK_HARNESS_VERSION = "0.1.0rc6"
OUTPUT_COMMIT_PLUGIN_ID = "@aec-bench/dsh-output-commit"
OUTPUT_COMMIT_PLUGIN_VERSION = "0.1.0"
TOOL_GATEWAY_PLUGIN_ID = "@aec-bench/dsh-tools"
TOOL_GATEWAY_PLUGIN_VERSION = "0.2.0"
_MAX_SAFE_INTEGER = 2**53 - 1
_HARNESS_PROVIDER_ROUTES: dict[str, HarnessProviderRoute] = {
    "azure": "azure",
    "deepseek": "deepseek-official",
}
_CORDIS_PROFILES = {
    "azure": "azure.cordis.yml",
    "deepseek": "deepseek.cordis.yml",
}
_TOOL_GATEWAY_CORDIS_PROFILES = {
    "azure": "azure.tools.cordis.yml",
    "deepseek": "deepseek.tools.cordis.yml",
}


class DeepSeekHarnessConfigurationError(ValueError):
    """Raised before runtime launch when a treatment cannot be enforced."""


class DeepSeekHarnessSettings(StrictModel):
    """The model identity supplied by the execution bundle."""

    provider: DeepSeekHarnessProvider
    model: NonEmptyStr
    requested_model: NonEmptyStr | None = None

    @classmethod
    def from_execution_payload(
        cls,
        *,
        model_name: str,
        payload: dict[str, Any],
    ) -> DeepSeekHarnessSettings:
        """Resolve the bundle-owned model and reject treatment overrides."""
        if "model" in payload:
            raise DeepSeekHarnessConfigurationError("model is owned by the execution bundle, not adapter payload")
        values = dict(payload)
        provider = values.get("provider")
        if provider not in {"azure", "deepseek"}:
            raise DeepSeekHarnessConfigurationError(f"unsupported DeepSeek Harness provider: {provider!r}")
        prefix, separator, provider_model = model_name.partition(":")
        if separator:
            if prefix.strip().lower() != provider:
                raise DeepSeekHarnessConfigurationError("bundle provider does not match the model provider prefix")
            model = provider_model.strip()
        else:
            model = model_name.strip()
        if not model:
            raise DeepSeekHarnessConfigurationError("DeepSeek Harness model must be non-empty")
        values["model"] = model
        values["requested_model"] = model_name
        try:
            return cls.model_validate(values)
        except ValueError as exc:
            raise DeepSeekHarnessConfigurationError(str(exc)) from exc


def validate_deepseek_request(
    request: AdapterRequest,
    *,
    native_tool_names: frozenset[str] = frozenset(),
) -> None:
    """Reject task tools and limits that the qualified runtime cannot enforce."""
    requested_tool_names = frozenset(tool.name for tool in request.tools)
    if requested_tool_names != native_tool_names:
        names = ", ".join(sorted(requested_tool_names)) or "none"
        expected = ", ".join(sorted(native_tool_names)) or "none"
        raise DeepSeekHarnessConfigurationError(
            "deepseek_harness request tools must match its configured native tool gateway; "
            f"requested: {names}; configured: {expected}"
        )

    for field_name in ("max_turns", "max_tool_calls", "max_context_tokens"):
        if field_name in request.configuration:
            raise DeepSeekHarnessConfigurationError(
                f"deepseek_harness cannot enforce {field_name} exactly at the qualified public SDK boundary"
            )

    request_timeout_seconds(request)
    request_max_tokens(request)
    _contract, commit_required = deepseek_output_commit_configuration(request)
    if native_tool_names and commit_required:
        raise DeepSeekHarnessConfigurationError(
            "deepseek_harness native tools cannot be combined with required output commitment"
        )


def deepseek_output_commit_configuration(
    request: AdapterRequest,
) -> tuple[OutputCompletionContract | None, bool]:
    """Return the supported shared output contract and required-commit mode."""
    try:
        contract = configured_output_completion_contract(request)
        required = configured_output_completion_commit(request, contract=contract)
    except ValueError as exc:
        raise DeepSeekHarnessConfigurationError(str(exc)) from exc
    return contract, required


def request_timeout_seconds(request: AdapterRequest) -> int:
    """Return the exact process-boundary timeout for one trial."""
    value = request.configuration.get("timeout_sec", DEFAULT_TIMEOUT_SECONDS)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise DeepSeekHarnessConfigurationError("timeout_sec must be a positive integer")
    return cast(int, value)


def request_max_tokens(request: AdapterRequest) -> int | None:
    """Return the exact per-model-request output cap, when configured."""
    value = request.configuration.get("max_tokens")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value > _MAX_SAFE_INTEGER:
        raise DeepSeekHarnessConfigurationError("max_tokens must be a positive safe integer")
    return cast(int, value)


def deepseek_system_prompt(request: AdapterRequest) -> str:
    """Return the exact static prompt sent to the DeepSeek composition."""
    return DEFAULT_DEEPSEEK_SYSTEM_PROMPT if request.system_prompt is None else request.system_prompt


def harness_provider_route(provider: str) -> HarnessProviderRoute:
    """Return the Harness LLM route that owns the selected provider protocol."""
    try:
        return _HARNESS_PROVIDER_ROUTES[provider]
    except KeyError as exc:
        raise DeepSeekHarnessConfigurationError(f"unsupported DeepSeek Harness provider: {provider!r}") from exc


def treatment_record(
    settings: DeepSeekHarnessSettings,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_tokens: int | None = None,
    output_commit_required: bool = False,
    native_tools: tuple[str, ...] = (),
) -> dict[str, object]:
    """Describe the fixed treatment applied to every DeepSeek trial."""
    return {
        "provider": settings.provider,
        "harness_route": harness_provider_route(settings.provider),
        "model": settings.model,
        "timeout_sec": timeout_seconds,
        "max_tokens": max_tokens,
        "plugin_free_baseline": not output_commit_required and not native_tools,
        "sandbox_mode": "workspace-write",
        "sandbox_enforcement": "partial",
        "network_isolation": False,
        "subagents_enabled": False,
        "workflows_enabled": False,
        "code_mode_enabled": False,
        "output_commit_mode": "required" if output_commit_required else "disabled",
        "output_commit_tool": "aec_commit_output" if output_commit_required else None,
        "native_tools": list(native_tools),
        "notifications_retained": True,
        "session_jsonl_retained": True,
    }


def baseline_cordis_template(provider: str) -> Path:
    """Return the fixed Cordis treatment for the selected provider protocol."""
    try:
        filename = _CORDIS_PROFILES[provider]
    except KeyError as exc:
        raise DeepSeekHarnessConfigurationError(f"unsupported DeepSeek Harness provider: {provider!r}") from exc
    return Path(__file__).parent / "profiles" / filename


def tool_gateway_cordis_template(provider: str) -> Path:
    """Return the provider profile that exposes only the AEC native tool gateway."""
    try:
        filename = _TOOL_GATEWAY_CORDIS_PROFILES[provider]
    except KeyError as exc:
        raise DeepSeekHarnessConfigurationError(f"unsupported DeepSeek Harness provider: {provider!r}") from exc
    return Path(__file__).parent / "profiles" / filename


def output_commit_plugin_path() -> Path:
    """Return the built internal Cordis plugin loaded only for required commits."""
    return Path(__file__).parent / "plugin" / "dist" / "index.js"


def tool_gateway_plugin_path() -> Path:
    """Return the built internal Cordis plugin for the native tool gateway."""
    return Path(__file__).parent / "plugin" / "dist" / "tools.js"
