# ABOUTME: Configuration helpers for provider-neutral adapter setup in aec-bench Python.
# ABOUTME: Keeps model alias resolution explicit so behavior-affecting defaults stay visible.

from copy import deepcopy
from typing import Any


def reject_unknown(data: dict[str, Any], allowed: set[str], location: str) -> None:
    unknown = sorted(data.keys() - allowed)
    if unknown:
        raise ValueError(f"unknown {location} options: {', '.join(unknown)}")


def merge_configuration(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Apply explicit condition values before validating the adapter configuration."""
    result = deepcopy(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_configuration(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def resolve_model_alias(model: str, *, aliases: dict[str, str]) -> str:
    return aliases.get(model, model)


def record_effective_configuration(
    *,
    resolved_model: str,
    configuration: dict[str, Any],
) -> dict[str, Any]:
    return {"model": resolved_model, **configuration}


def report_configuration(parameters: dict[str, Any]) -> dict[str, Any]:
    """Extract report adapter blocks from the existing execution parameters."""
    keys = {
        "template",
        "inputs",
        "hints",
        "subcalls",
        "guardrails",
        "execution",
        "advisor",
        "constitution",
        "planner",
        "review",
        "extract",
        "fill_section",
        "compose",
        "planning_phase",
        "sandbox",
        "grounding",
        "structure_enforcement",
        "uncertainty",
        "k_candidates",
    }
    return {key: value for key, value in parameters.items() if key in keys}
