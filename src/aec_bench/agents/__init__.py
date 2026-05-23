# ABOUTME: Public API for the agents utility library — pure functions for building agents.
# ABOUTME: Re-exports utility functions for convenient access by agent implementations.

from aec_bench.agents.env import build_all_provider_env, build_provider_env
from aec_bench.agents.providers import PROVIDERS, ProviderConfig, get_provider
from aec_bench.agents.results import AgentResult, parse_agent_result_json, read_agent_result
from aec_bench.agents.scripts import (
    build_anthropic_tool_loop_script,
    build_openai_tool_loop_script,
    build_pydantic_ai_script,
)
from aec_bench.agents.tools import discover_tools, inject_trajectory_writer, parse_tools_from_toml

__all__ = [
    "AgentResult",
    "PROVIDERS",
    "ProviderConfig",
    "build_all_provider_env",
    "build_anthropic_tool_loop_script",
    "build_openai_tool_loop_script",
    "build_provider_env",
    "build_pydantic_ai_script",
    "discover_tools",
    "get_provider",
    "inject_trajectory_writer",
    "parse_agent_result_json",
    "parse_tools_from_toml",
    "read_agent_result",
]
