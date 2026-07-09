# ABOUTME: Tests for EntrypointAgent — the universal Harbor agent
# ABOUTME: that dispatches to library adapters via execution_entrypoint.

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from agents.entrypoint_agent import (
    _BUNDLE_REMOTE_PATH,
    _LIBRARY_SOURCE,
    EntrypointAgent,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_exec_result(return_code: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    result = MagicMock()
    result.return_code = return_code
    result.stdout = stdout
    result.stderr = stderr
    return result


def _make_environment(**exec_side_effects: Any) -> AsyncMock:
    """Build a mock environment with configurable exec responses."""
    env = AsyncMock()
    env.exec = AsyncMock()
    env.upload_dir = AsyncMock()
    env.upload_file = AsyncMock()
    env.download_file = AsyncMock()
    return env


# ---------------------------------------------------------------------------
# name / version
# ---------------------------------------------------------------------------


def test_entrypoint_agent_name() -> None:
    agent = EntrypointAgent(logs_dir=Path("/tmp/logs"), model_name="claude-sonnet-4-20250514")
    assert agent.name() == "entrypoint"


def test_entrypoint_agent_version() -> None:
    agent = EntrypointAgent(logs_dir=Path("/tmp/logs"))
    assert agent.version() == "1.0.0"


# ---------------------------------------------------------------------------
# setup()
# ---------------------------------------------------------------------------


def test_setup_verifies_python_available(tmp_path: Path) -> None:
    """setup() should call python3 --version and raise if it fails."""
    agent = EntrypointAgent(logs_dir=tmp_path, model_name="test")
    env = _make_environment()
    env.exec.return_value = _make_exec_result(return_code=1, stderr="python3 not found")

    try:
        asyncio.run(agent.setup(env))
        raised = False
    except RuntimeError:
        raised = True

    assert raised, "setup() should raise RuntimeError when python3 is unavailable"


def test_setup_uploads_library_source(tmp_path: Path) -> None:
    """setup() should upload the library source directory."""
    agent = EntrypointAgent(logs_dir=tmp_path, model_name="test")
    env = _make_environment()
    # python3 --version succeeds, pydantic_ai import succeeds
    env.exec.return_value = _make_exec_result(return_code=0, stdout="Python 3.13")

    with patch("agents.entrypoint_agent.inject_trajectory_writer", new_callable=AsyncMock):
        asyncio.run(agent.setup(env))

    env.upload_dir.assert_called_once_with(str(_LIBRARY_SOURCE), "/opt/aec_bench/aec_bench")


def test_setup_installs_pip_deps_when_pydantic_ai_missing(tmp_path: Path) -> None:
    """setup() should pip install when pydantic_ai is not importable."""
    agent = EntrypointAgent(logs_dir=tmp_path, model_name="test")
    env = _make_environment()

    # python3 --version: OK
    # pydantic_ai import: fails (return_code=1)
    # pip install: OK
    # trajectory writer injection: handled by patch

    async def exec_side_effect(cmd: str, **kwargs: Any) -> MagicMock:
        if "python3 --version" in cmd:
            return _make_exec_result(return_code=0, stdout="Python 3.13")
        if "import pydantic_ai" in cmd:
            return _make_exec_result(return_code=1, stderr="ModuleNotFoundError")
        if "pip install" in cmd:
            return _make_exec_result(return_code=0)
        # trajectory_writer injection (cat >)
        return _make_exec_result(return_code=0)

    env.exec = AsyncMock(side_effect=exec_side_effect)

    with patch("agents.entrypoint_agent.inject_trajectory_writer", new_callable=AsyncMock):
        asyncio.run(agent.setup(env))

    # Find the pip install call
    pip_calls = [c for c in env.exec.call_args_list if "pip install" in str(c)]
    assert len(pip_calls) == 1, f"Expected one pip install call, got: {env.exec.call_args_list}"


def test_setup_skips_pip_when_pydantic_ai_available(tmp_path: Path) -> None:
    """setup() should skip pip install when pydantic_ai is already importable."""
    agent = EntrypointAgent(logs_dir=tmp_path, model_name="test")
    env = _make_environment()

    async def exec_side_effect(cmd: str, **kwargs: Any) -> MagicMock:
        # All commands succeed
        return _make_exec_result(return_code=0, stdout="OK")

    env.exec = AsyncMock(side_effect=exec_side_effect)

    with patch("agents.entrypoint_agent.inject_trajectory_writer", new_callable=AsyncMock):
        asyncio.run(agent.setup(env))

    pip_calls = [c for c in env.exec.call_args_list if "pip install" in str(c)]
    assert len(pip_calls) == 0, f"No pip install expected, got: {pip_calls}"


def test_setup_injects_trajectory_writer(tmp_path: Path) -> None:
    """setup() should call inject_trajectory_writer."""
    agent = EntrypointAgent(logs_dir=tmp_path, model_name="test")
    env = _make_environment()
    env.exec.return_value = _make_exec_result(return_code=0)

    mock_inject = AsyncMock()
    with patch("agents.entrypoint_agent.inject_trajectory_writer", mock_inject):
        asyncio.run(agent.setup(env))

    mock_inject.assert_awaited_once_with(env)


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------


def test_run_writes_bundle_and_executes(tmp_path: Path) -> None:
    """run() should write an execution bundle and invoke the entrypoint."""
    agent = EntrypointAgent(
        logs_dir=tmp_path,
        model_name="claude-sonnet-4-20250514",
        adapter="rlm",
        timeout_sec="900",
    )
    env = _make_environment()
    context = MagicMock()
    context.n_input_tokens = 0
    context.n_output_tokens = 0
    context.metadata = {}

    # exec for the entrypoint command: succeed
    env.exec.return_value = _make_exec_result(return_code=0)

    # download_file: write a result JSON to the target path
    result_data = {
        "usage_input_tokens": 1234,
        "usage_output_tokens": 567,
        "adapter_name": "entrypoint",
        "resolved_model": "claude-sonnet-4-20250514",
    }

    async def fake_download(source: str, target: Any) -> None:
        target_path = Path(target)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(json.dumps(result_data))

    env.download_file = AsyncMock(side_effect=fake_download)

    asyncio.run(agent.run("Solve this task", env, context))

    # Should have uploaded a bundle file
    env.upload_file.assert_called_once()
    upload_args = env.upload_file.call_args
    assert upload_args[0][1] == _BUNDLE_REMOTE_PATH

    # Should have executed the entrypoint
    exec_calls = env.exec.call_args_list
    entrypoint_calls = [c for c in exec_calls if "execution_entrypoint" in str(c)]
    assert len(entrypoint_calls) == 1

    # Should have set token counts from result
    assert context.n_input_tokens == 1234
    assert context.n_output_tokens == 567


def test_run_uses_default_adapter_kind(tmp_path: Path) -> None:
    """run() should default to 'rlm' adapter when not specified."""
    agent = EntrypointAgent(logs_dir=tmp_path, model_name="test")
    env = _make_environment()
    context = MagicMock()
    context.metadata = {}

    env.exec.return_value = _make_exec_result(return_code=0)

    # Capture bundle content during upload (file is deleted after upload)
    captured_bundles: list[dict[str, Any]] = []

    async def capture_upload(local_path: str, remote_path: str) -> None:
        if remote_path == _BUNDLE_REMOTE_PATH:
            captured_bundles.append(json.loads(Path(local_path).read_text()))

    env.upload_file = AsyncMock(side_effect=capture_upload)

    # Make download_file write a minimal result
    async def fake_download(source: str, target: Any) -> None:
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_text(json.dumps({"adapter_name": "entrypoint"}))

    env.download_file = AsyncMock(side_effect=fake_download)

    asyncio.run(agent.run("Test instruction", env, context))

    assert len(captured_bundles) == 1
    assert captured_bundles[0]["execution"]["adapter_kind"] == "rlm"


def test_run_handles_exec_failure_gracefully(tmp_path: Path) -> None:
    """run() should not crash when the entrypoint execution fails."""
    agent = EntrypointAgent(logs_dir=tmp_path, model_name="test")
    env = _make_environment()
    context = MagicMock()
    context.metadata = {}

    env.exec.return_value = _make_exec_result(return_code=1, stderr="adapter crashed")
    env.download_file = AsyncMock(side_effect=FileNotFoundError("no result"))

    # Should not raise
    asyncio.run(agent.run("Test instruction", env, context))

    # Should have recorded error in metadata
    assert "error" in context.metadata


def test_run_handles_download_failure_gracefully(tmp_path: Path) -> None:
    """run() should not crash when result download fails."""
    agent = EntrypointAgent(logs_dir=tmp_path, model_name="test")
    env = _make_environment()
    context = MagicMock()
    context.metadata = {}

    env.exec.return_value = _make_exec_result(return_code=0)
    env.download_file = AsyncMock(side_effect=Exception("download failed"))

    # Should not raise
    asyncio.run(agent.run("Test instruction", env, context))

    assert "error" in context.metadata


def test_run_passes_timeout_to_exec(tmp_path: Path) -> None:
    """run() should pass timeout_sec to environment.exec."""
    agent = EntrypointAgent(logs_dir=tmp_path, model_name="test", timeout_sec="1200")
    env = _make_environment()
    context = MagicMock()
    context.metadata = {}

    env.exec.return_value = _make_exec_result(return_code=0)

    async def fake_download(source: str, target: Any) -> None:
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_text(json.dumps({"adapter_name": "entrypoint"}))

    env.download_file = AsyncMock(side_effect=fake_download)

    asyncio.run(agent.run("Test", env, context))

    exec_call = env.exec.call_args
    assert exec_call.kwargs.get("timeout_sec") == 1200


def test_bundle_contains_instruction_and_config(tmp_path: Path) -> None:
    """The execution bundle should contain the instruction and agent config."""
    agent = EntrypointAgent(
        logs_dir=tmp_path,
        model_name="claude-sonnet-4-20250514",
        adapter="tool_loop",
        custom_param="hello",
    )
    env = _make_environment()
    context = MagicMock()
    context.metadata = {}

    env.exec.return_value = _make_exec_result(return_code=0)

    # Capture bundle content during upload
    captured_bundles: list[dict[str, Any]] = []

    async def capture_upload(local_path: str, remote_path: str) -> None:
        if remote_path == _BUNDLE_REMOTE_PATH:
            captured_bundles.append(json.loads(Path(local_path).read_text()))

    env.upload_file = AsyncMock(side_effect=capture_upload)

    async def fake_download(source: str, target: Any) -> None:
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_text(json.dumps({"adapter_name": "entrypoint"}))

    env.download_file = AsyncMock(side_effect=fake_download)

    asyncio.run(agent.run("Calculate voltage drop", env, context))

    assert len(captured_bundles) == 1
    bundle_data = captured_bundles[0]

    assert bundle_data["execution"]["adapter_kind"] == "tool_loop"
    assert bundle_data["execution"]["resolved_model"] == "claude-sonnet-4-20250514"
    assert bundle_data["request"]["instruction"] == "Calculate voltage drop"
    assert bundle_data["request"]["configuration"]["custom_param"] == "hello"


def test_bundle_includes_serialized_client_payload(tmp_path: Path) -> None:
    """EntrypointAgent should forward serialized client settings to execution_entrypoint."""
    agent = EntrypointAgent(
        logs_dir=tmp_path,
        model_name="replay-direct",
        adapter="direct",
        client={"client_kind": "replay", "payload": {"output_text": "done"}},
    )
    env = _make_environment()
    context = MagicMock()
    context.metadata = {}
    env.exec.return_value = _make_exec_result(return_code=0)

    captured_bundles: list[dict[str, Any]] = []

    async def capture_upload(local_path: str, remote_path: str) -> None:
        if remote_path == _BUNDLE_REMOTE_PATH:
            captured_bundles.append(json.loads(Path(local_path).read_text()))

    env.upload_file = AsyncMock(side_effect=capture_upload)

    async def fake_download(source: str, target: Any) -> None:
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_text(json.dumps({"adapter_name": "entrypoint"}))

    env.download_file = AsyncMock(side_effect=fake_download)

    asyncio.run(agent.run("Use replay output", env, context))

    assert captured_bundles[0]["execution"]["payload"] == {
        "client": {"client_kind": "replay", "payload": {"output_text": "done"}}
    }
