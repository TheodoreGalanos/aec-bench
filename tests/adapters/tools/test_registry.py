# ABOUTME: Tests for tool executor resolution in aec-bench Python.
# ABOUTME: Covers mapping declared TaskDefinition tools to concrete executor wrappers.

from pathlib import Path

import pytest

from aec_bench.adapters.tools.bash import BashToolExecutor
from aec_bench.adapters.tools.codes_search import CodesSearchToolExecutor
from aec_bench.adapters.tools.registry import ToolExecutorRegistry
from aec_bench.contracts.task_definition import ToolSpec


def test_registry_resolves_codes_search_using_declared_tool_source(tmp_path: Path) -> None:
    registry = ToolExecutorRegistry(workspace_dir=tmp_path)
    tool = ToolSpec(
        name="codes_search",
        source="environment/codes_search.py",
        description="Search code references.",
    )

    executor = registry.resolve(tool)

    assert isinstance(executor, CodesSearchToolExecutor)
    assert executor.workspace_dir == tmp_path
    assert executor.script_path == Path("environment/codes_search.py")


def test_registry_resolves_bash_without_needing_a_staged_script(tmp_path: Path) -> None:
    registry = ToolExecutorRegistry(workspace_dir=tmp_path)
    tool = ToolSpec(
        name="bash",
        source="environment/bash.sh",
        description="Run shell commands.",
    )

    executor = registry.resolve(tool)

    assert isinstance(executor, BashToolExecutor)
    assert executor.workspace_dir == tmp_path


def test_registry_rejects_unknown_tool_name(tmp_path: Path) -> None:
    registry = ToolExecutorRegistry(workspace_dir=tmp_path)
    tool = ToolSpec(
        name="mystery_tool",
        source="environment/mystery.py",
        description="Unknown tool.",
    )

    with pytest.raises(ValueError, match="unsupported tool"):
        registry.resolve(tool)
