# ABOUTME: Validates lowered runtime limits and exposes exact positive budget values.
# ABOUTME: Rejects declarations the provider-neutral adapter boundary cannot enforce truthfully.

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class AdapterRuntimeLimitError(RuntimeError):
    """Raised before model execution when a declared runtime limit is unsupported."""


_POSITIVE_LIMIT_FIELDS = (
    "max_turns",
    "max_tool_calls",
    "max_context_tokens",
    "timeout_sec",
)
_TASK_TOOL_ADAPTER_KINDS = {"pydantic_ai", "tool_loop"}
_SUPPORTED_TOOL_ACCESS_MODES = {"execute"}


def configured_positive_int(
    configuration: Mapping[str, Any] | None,
    field_name: str,
) -> int | None:
    """Return one configured positive integer while preserving absent legacy fields."""
    if configuration is None or field_name not in configuration:
        return None

    raw_value = configuration[field_name]
    if isinstance(raw_value, bool):
        raise ValueError(f"{field_name} must be a positive integer")
    if isinstance(raw_value, int):
        value = raw_value
    elif isinstance(raw_value, str):
        try:
            value = int(raw_value)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a positive integer") from exc
    else:
        raise ValueError(f"{field_name} must be a positive integer")

    if value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def validate_runtime_limit_contract(
    *,
    adapter_kind: str,
    configuration: Mapping[str, Any],
) -> None:
    """Validate only declarations owned by the supported adapter execution boundary."""
    for field_name in _POSITIVE_LIMIT_FIELDS:
        configured_positive_int(configuration, field_name)

    if "max_context_tokens" in configuration:
        raise AdapterRuntimeLimitError(
            "max_context_tokens cannot be enforced exactly before model execution by the "
            "provider-neutral adapter boundary; refusing to run"
        )

    has_tool_controls = "tool_access_mode" in configuration or "max_tool_calls" in configuration
    if has_tool_controls and adapter_kind not in _TASK_TOOL_ADAPTER_KINDS:
        raise AdapterRuntimeLimitError(f"adapter kind {adapter_kind!r} does not support lowered task-tool controls")

    if "tool_access_mode" not in configuration:
        return
    access_mode = configuration["tool_access_mode"]
    if access_mode not in _SUPPORTED_TOOL_ACCESS_MODES:
        raise AdapterRuntimeLimitError(
            f"tool_access_mode={access_mode!r} is not supported by the current task-tool runtime; "
            "only 'execute' has an enforceable mapping"
        )
