# ABOUTME: Tests for AgentResult dataclass and result-parsing pure functions.
# ABOUTME: Covers JSON parsing, error handling, and the thin async read_agent_result wrapper.

import asyncio
from dataclasses import FrozenInstanceError

import pytest

from aec_bench.agents.results import AgentResult, parse_agent_result_json, read_agent_result


def test_agent_result_defaults() -> None:
    result = AgentResult(status="completed")
    assert result.status == "completed"
    assert result.input_tokens == 0
    assert result.output_tokens == 0
    assert result.metadata == {}


def test_agent_result_with_metadata() -> None:
    meta = {"model": "claude-sonnet-4", "turns": 3}
    result = AgentResult(status="completed", input_tokens=100, output_tokens=200, metadata=meta)
    assert result.input_tokens == 100
    assert result.metadata["model"] == "claude-sonnet-4"


def test_agent_result_is_frozen() -> None:
    result = AgentResult(status="completed")
    with pytest.raises(FrozenInstanceError):
        result.status = "failed"  # type: ignore[misc]


def test_parse_ok_result() -> None:
    json_str = (
        '{"status": "ok", "input_tokens": 200, "output_tokens": 400, "model": "claude-sonnet-4", "turns_used": 3}'
    )
    result = parse_agent_result_json(json_str, return_code=0)
    assert result.status == "completed"
    assert result.input_tokens == 200
    assert result.output_tokens == 400
    assert result.metadata["model"] == "claude-sonnet-4"


def test_parse_error_result() -> None:
    json_str = '{"status": "error", "error": "API failed", "input_tokens": 0, "output_tokens": 0}'
    result = parse_agent_result_json(json_str, return_code=1)
    assert result.status == "failed"


def test_parse_ok_status_but_nonzero_exit() -> None:
    json_str = '{"status": "ok", "input_tokens": 50, "output_tokens": 100}'
    result = parse_agent_result_json(json_str, return_code=1)
    assert result.status == "failed"


def test_parse_invalid_json() -> None:
    result = parse_agent_result_json("not json at all", return_code=0)
    assert result.status == "failed"
    assert "invalid" in result.metadata.get("error", "")


def test_parse_empty_string() -> None:
    result = parse_agent_result_json("", return_code=0)
    assert result.status == "failed"


class _FakeExecResult:
    def __init__(self, return_code: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr


class _FakeEnvironment:
    def __init__(self, results: dict[str, _FakeExecResult]) -> None:
        self._results = results

    async def exec(self, command: str, **kwargs: object) -> _FakeExecResult:
        for prefix, result in self._results.items():
            if command.startswith(prefix):
                return result
        return _FakeExecResult()


def test_read_agent_result_success() -> None:
    json_str = '{"status": "ok", "input_tokens": 100, "output_tokens": 200}'
    env = _FakeEnvironment({"cat /workspace/agent_result.json": _FakeExecResult(stdout=json_str)})
    exec_result = _FakeExecResult(return_code=0)
    result = asyncio.run(read_agent_result(env, exec_result))
    assert result.status == "completed"
    assert result.input_tokens == 100


def test_read_agent_result_missing_file() -> None:
    env = _FakeEnvironment({"cat /workspace/agent_result.json": _FakeExecResult(return_code=1, stderr="No such file")})
    exec_result = _FakeExecResult(return_code=1, stderr="script crashed")
    result = asyncio.run(read_agent_result(env, exec_result))
    assert result.status == "failed"
    assert "not found" in result.metadata["error"]
    assert result.metadata["stderr"] == "script crashed"
