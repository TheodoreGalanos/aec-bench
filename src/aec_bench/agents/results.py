# ABOUTME: AgentResult dataclass and pure functions for parsing agent_result.json.
# ABOUTME: Extracted from ToolLoopAgent._parse_result() and ScriptAgent._parse_result().

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentResult:
    """Parsed agent execution result from agent_result.json."""

    status: str  # "completed" | "failed" | "timeout"
    input_tokens: int = 0
    output_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


def parse_agent_result_json(json_str: str, return_code: int) -> AgentResult:
    """Parse agent_result.json content into AgentResult. Pure function."""
    try:
        data: dict[str, Any] = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return AgentResult(status="failed", metadata={"error": "invalid agent_result.json"})

    status = "completed" if data.get("status") == "ok" else "failed"
    if return_code != 0 and status == "completed":
        status = "failed"

    return AgentResult(
        status=status,
        input_tokens=int(data.get("input_tokens", 0)),
        output_tokens=int(data.get("output_tokens", 0)),
        metadata=data,
    )


async def read_agent_result(environment: Any, exec_result: Any) -> AgentResult:
    """Read agent_result.json from environment and parse it. Thin async wrapper."""
    cat_result = await environment.exec("cat /workspace/agent_result.json")
    if cat_result.return_code != 0:
        return AgentResult(
            status="failed",
            metadata={"error": "agent_result.json not found", "stderr": exec_result.stderr},
        )
    return parse_agent_result_json(cat_result.stdout, exec_result.return_code)
