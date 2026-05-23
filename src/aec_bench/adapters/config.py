# ABOUTME: Configuration helpers for provider-neutral adapter setup in aec-bench Python.
# ABOUTME: Keeps model alias resolution explicit so behavior-affecting defaults stay visible.

from typing import Any


def resolve_model_alias(model: str, *, aliases: dict[str, str]) -> str:
    return aliases.get(model, model)


def record_effective_configuration(
    *,
    resolved_model: str,
    configuration: dict[str, Any],
) -> dict[str, Any]:
    return {"model": resolved_model, **configuration}
