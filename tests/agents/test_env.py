# ABOUTME: Tests for env-var builder pure functions — single-provider and all-provider variants.
# ABOUTME: Pure dict-in/dict-out tests with no sandbox or async code needed.

import json

import pytest

from aec_bench.agents.env import build_all_provider_env, build_provider_env


def test_build_provider_env_anthropic_basic() -> None:
    host = {"ANTHROPIC_API_KEY": "sk-test-123"}
    env = build_provider_env(
        "anthropic",
        "solve this",
        "claude-sonnet-4",
        host_env=host,
    )
    assert env["AGENT_INSTRUCTION"] == "solve this"
    assert env["AGENT_MODEL"] == "claude-sonnet-4"
    assert env["ANTHROPIC_API_KEY"] == "sk-test-123"
    assert env["AGENT_MAX_TOKENS"] == "16384"


def test_build_provider_env_azure_with_api_version() -> None:
    host = {
        "AZURE_OPENAI_API_KEY": "az-key",
        "AZURE_OPENAI_ENDPOINT": "https://my.openai.azure.com",
    }
    env = build_provider_env(
        "azure_openai",
        "solve this",
        "gpt-4o",
        host_env=host,
    )
    assert env["AZURE_OPENAI_API_KEY"] == "az-key"
    assert env["AZURE_OPENAI_ENDPOINT"] == "https://my.openai.azure.com"
    assert env["AGENT_API_VERSION"] == "2024-10-21"


def test_build_provider_env_together() -> None:
    host = {"TOGETHER_API_KEY": "tog-key"}
    env = build_provider_env(
        "together",
        "solve this",
        "together:Qwen/Qwen3.7-Max",
        host_env=host,
    )
    assert env["TOGETHER_API_KEY"] == "tog-key"
    assert env["AGENT_MODEL"] == "together:Qwen/Qwen3.7-Max"


def test_build_provider_env_skips_missing_host_keys() -> None:
    env = build_provider_env("anthropic", "solve", "model", host_env={})
    assert "ANTHROPIC_API_KEY" not in env
    assert env["AGENT_INSTRUCTION"] == "solve"


def test_build_provider_env_with_tools() -> None:
    tools = [{"name": "calc", "source": "calc.py", "description": "Calculator"}]
    env = build_provider_env(
        "anthropic",
        "solve",
        "model",
        tools=tools,
        host_env={},
    )
    assert "AGENT_TOOLS_JSON" in env
    parsed = json.loads(env["AGENT_TOOLS_JSON"])
    assert len(parsed) == 1
    assert parsed[0]["name"] == "calc"


def test_build_provider_env_with_tool_loop_params() -> None:
    env = build_provider_env(
        "anthropic",
        "solve",
        "model",
        tools=[],
        max_turns=5,
        command_timeout=60,
        host_env={},
    )
    assert env["AGENT_MAX_TURNS"] == "5"
    assert env["AGENT_COMMAND_TIMEOUT"] == "60"


def test_build_provider_env_without_tool_params() -> None:
    """Script agents don't pass tools/max_turns/command_timeout."""
    env = build_provider_env("anthropic", "solve", "model", host_env={})
    assert "AGENT_TOOLS_JSON" not in env
    assert "AGENT_MAX_TURNS" not in env
    assert "AGENT_COMMAND_TIMEOUT" not in env


def test_build_provider_env_unknown_provider_raises() -> None:
    with pytest.raises(ValueError, match="unknown provider"):
        build_provider_env("nonexistent", "solve", "model", host_env={})


def test_build_all_provider_env_injects_all_keys() -> None:
    host = {
        "ANTHROPIC_API_KEY": "sk-ant",
        "AZURE_OPENAI_API_KEY": "az-key",
        "AZURE_OPENAI_ENDPOINT": "https://az.com",
        "OPENAI_API_KEY": "sk-oai",
        "TOGETHER_API_KEY": "tog-key",
    }
    env = build_all_provider_env(
        "solve",
        "claude-sonnet-4",
        tools=[],
        host_env=host,
    )
    assert env["ANTHROPIC_API_KEY"] == "sk-ant"
    assert env["AZURE_OPENAI_API_KEY"] == "az-key"
    assert env["OPENAI_API_KEY"] == "sk-oai"
    assert env["TOGETHER_API_KEY"] == "tog-key"
    assert env["AGENT_INSTRUCTION"] == "solve"


def test_build_all_provider_env_includes_api_versions() -> None:
    host = {}
    env = build_all_provider_env("solve", "model", tools=[], host_env=host)
    # Azure OpenAI has a default api_version that gets injected
    assert env["AZURE_OPENAI_API_VERSION"] == "2024-10-21"
