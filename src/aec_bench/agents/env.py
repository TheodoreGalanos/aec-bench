# ABOUTME: Pure functions that build sandbox environment variable dicts for agent execution.
# ABOUTME: Extracted from ToolLoopAgent._build_env() and PydanticAIAgent._build_env().

from __future__ import annotations

import json
import os
from typing import Any

from aec_bench.agents.providers import PROVIDERS, get_provider


def build_provider_env(
    provider: str,
    instruction: str,
    model_name: str,
    *,
    tools: list[dict[str, Any]] | None = None,
    max_tokens: int = 16384,
    max_turns: int = 10,
    command_timeout: int = 120,
    host_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build sandbox env vars for a single provider.

    Tool-loop params (tools, max_turns, command_timeout) are only included
    when *tools* is not None — script agents pass None to omit them.
    """
    source = host_env if host_env is not None else dict(os.environ)
    config = get_provider(provider)

    env: dict[str, str] = {
        "AGENT_INSTRUCTION": instruction,
        "AGENT_MODEL": model_name,
        "AGENT_MAX_TOKENS": str(max_tokens),
    }

    # Only include tool-loop params when tools is explicitly provided
    if tools is not None:
        env["AGENT_TOOLS_JSON"] = json.dumps(tools)
        env["AGENT_MAX_TURNS"] = str(max_turns)
        env["AGENT_COMMAND_TIMEOUT"] = str(command_timeout)

    # Copy provider auth env vars from host
    for key in config.env_keys:
        value = source.get(key, "")
        if value:
            env[key] = value

    # Provider-specific API version
    if config.api_version_env:
        env["AGENT_API_VERSION"] = source.get(config.api_version_env, config.api_version_default or "")

    return env


def build_all_provider_env(
    instruction: str,
    model_name: str,
    *,
    tools: list[dict[str, Any]] | None = None,
    max_tokens: int = 16384,
    max_turns: int = 10,
    command_timeout: int = 120,
    host_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build sandbox env vars injecting ALL provider keys (for PydanticAI).

    PydanticAI handles provider routing from the model string, so we inject
    env vars for every known provider — not just one.
    """
    source = host_env if host_env is not None else dict(os.environ)

    env: dict[str, str] = {
        "AGENT_INSTRUCTION": instruction,
        "AGENT_MODEL": model_name,
        "AGENT_MAX_TOKENS": str(max_tokens),
    }

    if tools is not None:
        env["AGENT_TOOLS_JSON"] = json.dumps(tools)
        env["AGENT_MAX_TURNS"] = str(max_turns)
        env["AGENT_COMMAND_TIMEOUT"] = str(command_timeout)

    # Inject env vars for ALL providers
    for config in PROVIDERS.values():
        for key in config.env_keys:
            value = source.get(key, "")
            if value:
                env[key] = value
        if config.api_version_env:
            value = source.get(config.api_version_env, config.api_version_default or "")
            if value:
                env[config.api_version_env] = value

    return env
