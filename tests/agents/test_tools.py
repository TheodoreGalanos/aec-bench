# ABOUTME: Tests for agent setup utilities — TOML tool parsing and trajectory writer injection.
# ABOUTME: Pure function tests plus async wrapper tests with fake environments.

import asyncio

from aec_bench.agents.tools import (
    build_trajectory_writer_source,
    discover_tools,
    inject_trajectory_writer,
    parse_tools_from_toml,
)


def test_parse_new_format_basic() -> None:
    toml_content = """
[[environment.tools]]
name = "create_chart"
source = "tools/create_chart.py"
description = "Generate a chart"
returns_image = true
"""
    tools = parse_tools_from_toml(toml_content)
    assert len(tools) == 1
    assert tools[0]["name"] == "create_chart"
    assert tools[0]["source"] == "tools/create_chart.py"
    assert tools[0]["description"] == "Generate a chart"
    assert tools[0]["returns_image"] is True


def test_parse_new_format_multiple_tools() -> None:
    toml_content = """
[[environment.tools]]
name = "chart"
source = "tools/chart.py"
description = "Make chart"

[[environment.tools]]
name = "calc"
source = "tools/calc.py"
description = "Calculator"
"""
    tools = parse_tools_from_toml(toml_content)
    assert len(tools) == 2
    assert tools[0]["name"] == "chart"
    assert tools[1]["name"] == "calc"


def test_parse_new_format_no_returns_image() -> None:
    toml_content = """
[[environment.tools]]
name = "calc"
source = "tools/calc.py"
description = "Calculator"
"""
    tools = parse_tools_from_toml(toml_content)
    assert "returns_image" not in tools[0]


def test_parse_new_format_default_description() -> None:
    toml_content = """
[[environment.tools]]
name = "my_tool"
source = "tools/my_tool.py"
"""
    tools = parse_tools_from_toml(toml_content)
    assert tools[0]["description"] == "Tool: my_tool"


def test_parse_legacy_format() -> None:
    toml_content = '[tools]\nscripts = ["calc.py", "search.py"]\n'
    tools = parse_tools_from_toml(toml_content)
    assert len(tools) == 2
    assert tools[0]["name"] == "calc"
    assert tools[0]["source"] == "calc.py"
    assert tools[1]["name"] == "search"
    assert tools[1]["source"] == "search.py"


def test_parse_legacy_format_underscored_name() -> None:
    toml_content = '[tools]\nscripts = ["my_calc.py"]\n'
    tools = parse_tools_from_toml(toml_content)
    assert tools[0]["name"] == "my-calc"


def test_parse_no_tools_section() -> None:
    toml_content = '[metadata]\ndifficulty = "easy"\n'
    tools = parse_tools_from_toml(toml_content)
    assert tools == []


def test_parse_empty_string() -> None:
    tools = parse_tools_from_toml("")
    assert tools == []


def test_parse_invalid_toml() -> None:
    tools = parse_tools_from_toml("this is not valid toml {{{{")
    assert tools == []


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


def test_discover_tools_reads_and_parses() -> None:
    toml_content = """
[[environment.tools]]
name = "chart"
source = "tools/chart.py"
description = "Make chart"
"""
    env = _FakeEnvironment({"cat /workspace/task.toml": _FakeExecResult(stdout=toml_content)})
    tools = asyncio.run(discover_tools(env))
    assert len(tools) == 1
    assert tools[0]["name"] == "chart"


def test_discover_tools_missing_file() -> None:
    env = _FakeEnvironment({"cat /workspace/task.toml": _FakeExecResult(return_code=1)})
    tools = asyncio.run(discover_tools(env))
    assert tools == []


# -- trajectory writer injection tests ----------------------------------------


def test_build_trajectory_writer_source_returns_valid_python() -> None:
    source = build_trajectory_writer_source()
    assert "class TrajectoryWriter" in source
    assert "def new_step" in source
    assert "def tool_call" in source
    assert "def close" in source


def test_build_trajectory_writer_source_is_stdlib_only() -> None:
    """The writer must have no external dependencies — it runs inside containers."""
    source = build_trajectory_writer_source()
    assert "import json" in source
    assert "from datetime" in source
    # Should NOT import any third-party packages
    assert "import pydantic" not in source
    assert "import httpx" not in source


class _RecordingEnvironment:
    """Records exec commands and their content for verification."""

    def __init__(self) -> None:
        self.exec_calls: list[str] = []

    async def exec(self, command: str, **kwargs: object) -> _FakeExecResult:
        self.exec_calls.append(command)
        return _FakeExecResult(return_code=0)


def test_inject_trajectory_writer_writes_file() -> None:
    env = _RecordingEnvironment()
    asyncio.run(inject_trajectory_writer(env))
    assert len(env.exec_calls) == 1
    cmd = env.exec_calls[0]
    assert "/workspace/trajectory_writer.py" in cmd
    assert "class TrajectoryWriter" in cmd


def test_inject_trajectory_writer_raises_on_failure() -> None:
    import pytest

    env = _FakeEnvironment({"cat >": _FakeExecResult(return_code=1, stderr="permission denied")})
    with pytest.raises(RuntimeError, match="Failed to inject"):
        asyncio.run(inject_trajectory_writer(env))
