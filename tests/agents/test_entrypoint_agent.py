# ABOUTME: Tests for EntrypointAgent — the universal Harbor agent
# ABOUTME: that dispatches to library adapters via execution_entrypoint.

import ast
import asyncio
import hashlib
import json
import logging
import shutil
import tarfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aec_bench.contracts.stage_execution import KernelInstructionOverride
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    PUMP_STATION_HARBOR_BRIDGE_MODE,
    export_pump_station_harbor_task,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
    PUMP_STATION_MODEL_CONTROLLER_MODE,
    PUMP_STATION_REFERENCE_CONTROLLER_ID,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_verifier import (
    verify_pump_station_harbor_run,
)
from agents.entrypoint_agent import (
    _BUNDLE_REMOTE_PATH,
    _LIBRARY_ARCHIVE_REMOTE_PATH,
    _LIBRARY_SOURCE,
    _RESULT_REMOTE_PATH,
    EntrypointAgent,
    _host_model_provider_environment,
)
from tests.support.output_completion import make_output_commit_attestation

ENTRYPOINT_AGENT_PATH = Path(__file__).resolve().parents[2] / "agents" / "entrypoint_agent.py"

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


def test_entrypoint_result_path_matches_harbor_artifact_contract() -> None:
    assert _RESULT_REMOTE_PATH == "/workspace/agent_result.json"


def test_entrypoint_agent_does_not_import_a_concrete_continual_task() -> None:
    tree = ast.parse(
        ENTRYPOINT_AGENT_PATH.read_text(encoding="utf-8"),
        filename=str(ENTRYPOINT_AGENT_PATH),
    )
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.append(node.module)

    pump_imports = tuple(
        module
        for module in imported_modules
        if module.startswith(
            "aec_bench.task_world_templates.stewardship.wastewater_pump_station",
        )
    )

    assert pump_imports == ()


def test_entrypoint_agent_does_not_branch_on_continual_task_stage_profile_or_controller() -> None:
    tree = ast.parse(
        ENTRYPOINT_AGENT_PATH.read_text(encoding="utf-8"),
        filename=str(ENTRYPOINT_AGENT_PATH),
    )
    forbidden_branch_tokens = {
        "controller",
        "evidence_health",
        "expected_reference_controller",
        "maintenance_review",
        "profile_ref",
        "reference_controller",
        "reference_runner",
        "rich_work_processes",
        "temporal_evidence",
    }
    violations: list[tuple[int, tuple[str, ...]]] = []
    for node in ast.walk(tree):
        branch_expressions: tuple[ast.AST, ...] = ()
        if isinstance(node, ast.If | ast.IfExp):
            branch_expressions = (node.test,)
        elif isinstance(node, ast.Match):
            branch_expressions = (node.subject, *(case.pattern for case in node.cases))
        for expression in branch_expressions:
            tokens = {
                child.id
                if isinstance(child, ast.Name)
                else child.attr
                if isinstance(child, ast.Attribute)
                else child.value
                for child in ast.walk(expression)
                if isinstance(child, ast.Name | ast.Attribute)
                or (isinstance(child, ast.Constant) and isinstance(child.value, str))
            }
            forbidden = tuple(sorted(tokens & forbidden_branch_tokens))
            if forbidden:
                violations.append((node.lineno, forbidden))

    assert violations == []


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
    """setup() should transfer the library as one archive instead of one file at a time."""
    agent = EntrypointAgent(logs_dir=tmp_path, model_name="test")
    env = _make_environment()
    archived_names: list[str] = []
    archived_init: list[bytes] = []
    setup_commands: list[str] = []

    async def exec_side_effect(cmd: str, **kwargs: Any) -> MagicMock:
        setup_commands.append(cmd)
        return _make_exec_result(return_code=0, stdout="Python 3.13")

    async def inspect_upload(local_path: str, remote_path: str) -> None:
        assert "mkdir -p /workspace/.aec-bench" in setup_commands
        assert remote_path == _LIBRARY_ARCHIVE_REMOTE_PATH
        with tarfile.open(local_path, mode="r:gz") as archive:
            archived_names.extend(member.name for member in archive.getmembers())
            init_file = archive.extractfile("./__init__.py")
            assert init_file is not None
            archived_init.append(init_file.read())

    env.exec = AsyncMock(side_effect=exec_side_effect)
    env.upload_file = AsyncMock(side_effect=inspect_upload)

    with patch("agents.entrypoint_agent.inject_trajectory_writer", new_callable=AsyncMock):
        asyncio.run(agent.setup(env))

    env.upload_file.assert_awaited_once()
    env.upload_dir.assert_not_awaited()
    assert _LIBRARY_ARCHIVE_REMOTE_PATH.startswith("/workspace/.aec-bench/")
    assert _LIBRARY_SOURCE.name == "aec_bench"
    assert "./__init__.py" in archived_names
    assert archived_init == [(_LIBRARY_SOURCE / "__init__.py").read_bytes()]
    assert not any("__pycache__" in name for name in archived_names)
    assert not any(name.endswith((".pyc", ".pyo")) for name in archived_names)
    assert any(_LIBRARY_ARCHIVE_REMOTE_PATH in call.args[0] for call in env.exec.await_args_list)


def test_setup_reports_archive_extraction_failure(tmp_path: Path) -> None:
    """setup() should preserve remote extraction diagnostics and stop immediately."""
    agent = EntrypointAgent(logs_dir=tmp_path, model_name="test")
    env = _make_environment()

    async def exec_side_effect(cmd: str, **kwargs: Any) -> MagicMock:
        if cmd == "python3 --version":
            return _make_exec_result(return_code=0, stdout="Python 3.13")
        if _LIBRARY_ARCHIVE_REMOTE_PATH in cmd:
            return _make_exec_result(return_code=1, stderr="archive extraction failed")
        return _make_exec_result(return_code=0)

    env.exec = AsyncMock(side_effect=exec_side_effect)

    with (
        patch("agents.entrypoint_agent.inject_trajectory_writer", new_callable=AsyncMock) as inject,
        pytest.raises(RuntimeError, match="archive extraction failed"),
    ):
        asyncio.run(agent.setup(env))

    inject.assert_not_awaited()
    assert not any("pip install" in call.args[0] for call in env.exec.await_args_list)


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
    assert '"pydantic-ai[anthropic,bedrock,openai]==1.60.0"' in pip_calls[0].args[0]


def test_setup_reports_pip_install_failure(tmp_path: Path) -> None:
    """setup() should fail before execution when the pinned runtime cannot be installed."""
    agent = EntrypointAgent(logs_dir=tmp_path, model_name="test")
    env = _make_environment()

    async def exec_side_effect(cmd: str, **kwargs: Any) -> MagicMock:
        if "import pydantic_ai" in cmd:
            return _make_exec_result(return_code=1, stderr="runtime version mismatch")
        if "pip install" in cmd:
            return _make_exec_result(return_code=1, stderr="package resolution failed")
        return _make_exec_result(return_code=0)

    env.exec = AsyncMock(side_effect=exec_side_effect)

    with (
        patch("agents.entrypoint_agent.inject_trajectory_writer", new_callable=AsyncMock) as inject,
        pytest.raises(RuntimeError, match="package resolution failed"),
    ):
        asyncio.run(agent.setup(env))

    inject.assert_not_awaited()


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


def test_world_session_entrypoint_normalizes_remote_evidence_permissions(
    tmp_path: Path,
) -> None:
    task_dir = tmp_path / "tasks" / "stewardship" / "wastewater-pump-station"
    exported = export_pump_station_harbor_task(
        task_dir,
        project_root=Path(__file__).resolve().parents[2],
    )
    agent = EntrypointAgent(
        logs_dir=tmp_path / "logs",
        model_name=PUMP_STATION_REFERENCE_CONTROLLER_ID,
        adapter="tool_loop",
        execution_kind="stewardship_world_session",
        extra_env={},
        world_session={"bridge_mode": PUMP_STATION_HARBOR_BRIDGE_MODE},
    )
    environment = _make_environment()
    environment.environment_dir = task_dir / "environment"
    environment.session_id = "harbor-trial-1"
    captured_run = tmp_path / "captured-world-session"
    captured_output: list[str] = []

    async def capture_dir(local_path: str, remote_path: str) -> None:
        assert remote_path == "/workspace/world-session"
        shutil.copytree(local_path, captured_run)

    async def capture_file(local_path: str, remote_path: str) -> None:
        assert remote_path == "/workspace/output.md"
        captured_output.append(Path(local_path).read_text(encoding="utf-8"))

    environment.upload_dir = AsyncMock(side_effect=capture_dir)
    environment.upload_file = AsyncMock(side_effect=capture_file)
    environment.exec.return_value = _make_exec_result(return_code=0)
    context = MagicMock()
    context.n_input_tokens = 99
    context.n_output_tokens = 99
    context.metadata = {}

    asyncio.run(agent.setup(environment))
    asyncio.run(
        agent.run(
            instruction="Complete the exported pump-station stewardship session.",
            environment=environment,
            context=context,
        )
    )
    verified = verify_pump_station_harbor_run(
        run_dir=captured_run,
        export_manifest_path=exported.manifest_path,
        package_dir=exported.package_dir,
        verifier_runtime_path=exported.verifier_runtime_wheel_path,
    )

    environment.exec.assert_awaited_once_with(
        "chmod -R go-rwx /workspace/world-session",
    )
    assert captured_output == ["The deterministic wastewater pump-station session completed.\n"]
    assert verified["valid"] is True
    assert context.n_input_tokens == 0
    assert context.n_output_tokens == 0
    assert context.metadata["execution_kind"] == ("stewardship_world_session")
    assert context.metadata["world_session_status"] == "completed"
    assert context.metadata["reward_owner"] == "harbor_verifier"


def test_world_session_entrypoint_accepts_bedrock_model_controller(
    tmp_path: Path,
) -> None:
    agent = EntrypointAgent(
        logs_dir=tmp_path / "logs",
        model_name="au.anthropic.claude-sonnet-4-6",
        adapter="tool_loop",
        execution_kind="stewardship_world_session",
        extra_env={},
        max_turns=30,
        world_session={
            "bridge_mode": PUMP_STATION_HARBOR_BRIDGE_MODE,
            "controller": PUMP_STATION_MODEL_CONTROLLER_MODE,
        },
    )

    agent._validate_world_session_configuration()


def test_world_session_host_model_preflight_accepts_aws_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
    monkeypatch.setenv("AWS_PROFILE", "pump-station-bedrock")
    monkeypatch.setenv("AWS_REGION", "ap-southeast-2")
    monkeypatch.setenv("TOGETHER_API_KEY", "unrelated-provider-key")

    with patch(
        "agents.entrypoint_agent.preflight_pydantic_model_configuration",
    ) as preflight:
        environment = _host_model_provider_environment(
            "au.anthropic.claude-sonnet-4-6",
        )

    preflight.assert_called_once_with("au.anthropic.claude-sonnet-4-6")
    assert environment == {
        "AWS_PROFILE": "pump-station-bedrock",
        "AWS_REGION": "ap-southeast-2",
    }


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------


def test_run_writes_bundle_and_executes(tmp_path: Path, monkeypatch: Any) -> None:
    """run() should write an execution bundle and invoke the entrypoint."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
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
        "failure_kind": "turn_limit_reached",
        "stop_reason": "iteration_cap",
        "turns_used": 8,
        "max_turns": 8,
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
    assert context.metadata["failure_kind"] == "turn_limit_reached"
    assert context.metadata["stop_reason"] == "iteration_cap"
    assert context.metadata["turns_used"] == 8
    assert context.metadata["max_turns"] == 8


def test_run_surfaces_adapter_completion_reason_in_harbor_metadata(tmp_path: Path) -> None:
    agent = EntrypointAgent(
        logs_dir=tmp_path,
        model_name="replay-rlm",
        adapter="rlm",
        client={"client_kind": "replay", "payload": {"responses": []}},
    )
    env = _make_environment()
    context = MagicMock(metadata={})
    env.exec.return_value = _make_exec_result(return_code=0)

    async def fake_download(source: str, target: Any) -> None:
        Path(target).write_text(
            json.dumps(
                {
                    "adapter_name": "rlm",
                    "resolved_model": "replay-rlm",
                    "completion_reason": "output_contract_satisfied",
                    "completion_assistance": {
                        "contract_satisfied": True,
                        "reminder_sent": True,
                        "reminder_turn": 3,
                        "explicit_final_turn": 4,
                    },
                }
            ),
            encoding="utf-8",
        )

    env.download_file = AsyncMock(side_effect=fake_download)

    asyncio.run(agent.run("Produce the artifact", env, context))

    assert context.metadata["completion_reason"] == "output_contract_satisfied"
    assert context.metadata["completion_assistance"] == {
        "contract_satisfied": True,
        "reminder_sent": True,
        "reminder_turn": 3,
        "explicit_final_turn": 4,
    }


def test_run_surfaces_output_commit_attestation_in_harbor_metadata(tmp_path: Path) -> None:
    attestation = make_output_commit_attestation()
    agent = EntrypointAgent(
        logs_dir=tmp_path,
        model_name="replay-rlm",
        adapter="rlm",
        client={"client_kind": "replay", "payload": {"responses": []}},
    )
    env = _make_environment()
    context = MagicMock(metadata={})
    env.exec.return_value = _make_exec_result(return_code=0)

    async def fake_download(source: str, target: Any) -> None:
        Path(target).write_text(
            json.dumps(
                {
                    "adapter_name": "rlm",
                    "resolved_model": "replay-rlm",
                    "completion_reason": "output_contract_committed",
                    "completion_commit": attestation.model_dump(mode="json"),
                }
            ),
            encoding="utf-8",
        )

    env.download_file = AsyncMock(side_effect=fake_download)

    asyncio.run(agent.run("Produce the artifact", env, context))

    assert context.metadata["completion_reason"] == "output_contract_committed"
    assert context.metadata["completion_commit"] == attestation.model_dump(mode="json")


def test_run_keeps_harbor_runtime_logger_out_of_serialized_configuration(tmp_path: Path) -> None:
    agent = EntrypointAgent(
        logs_dir=tmp_path,
        model_name="replay-direct",
        logger=logging.getLogger("harbor.trial"),
        adapter="direct",
        client={"client_kind": "replay", "payload": {"output_text": "done"}},
    )
    env = _make_environment()
    context = MagicMock(metadata={})
    captured_bundles: list[dict[str, Any]] = []
    env.exec.return_value = _make_exec_result(return_code=0)

    async def capture_upload(local_path: str, remote_path: str) -> None:
        if remote_path == _BUNDLE_REMOTE_PATH:
            captured_bundles.append(json.loads(Path(local_path).read_text()))

    async def fake_download(source: str, target: Any) -> None:
        Path(target).write_text(json.dumps({"adapter_name": "entrypoint"}), encoding="utf-8")

    env.upload_file = AsyncMock(side_effect=capture_upload)
    env.download_file = AsyncMock(side_effect=fake_download)

    asyncio.run(agent.run("Use replay output", env, context))

    assert "logger" not in captured_bundles[0]["request"]["configuration"]


def test_run_preserves_serialization_error_when_bundle_creation_fails(tmp_path: Path) -> None:
    agent = EntrypointAgent(
        logs_dir=tmp_path,
        model_name="replay-direct",
        adapter="direct",
        client={"client_kind": "replay", "payload": {"output_text": "done"}},
        non_serializable=object(),
    )

    with pytest.raises(TypeError, match="not JSON serializable"):
        asyncio.run(agent.run("Reject invalid configuration", _make_environment(), MagicMock()))


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


def test_bundle_contains_instruction_and_config(tmp_path: Path, monkeypatch: Any) -> None:
    """The execution bundle should contain the instruction and agent config."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
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


def test_bundle_uses_only_a_content_bound_kernel_instruction_override(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    original = "Complete the whole drainage review."
    effective = "Execute only the declared source_inventory stage."
    override = KernelInstructionOverride(
        mode="declared_stage",
        task_id="civil/review/drainage",
        original_instruction_sha256=hashlib.sha256(original.encode("utf-8")).hexdigest(),
        effective_instruction=effective,
        stage_id="source_inventory",
        context_manifest_sha256="1" * 64,
    )
    agent = EntrypointAgent(
        logs_dir=tmp_path,
        model_name="claude-sonnet-4-20250514",
        adapter="tool_loop",
        kernel_instruction_override=override.model_dump(mode="json"),
    )
    env = _make_environment()
    context = MagicMock()
    context.metadata = {}
    env.exec.return_value = _make_exec_result(return_code=0)
    captured_bundles: list[dict[str, Any]] = []

    async def capture_upload(local_path: str, remote_path: str) -> None:
        if remote_path == _BUNDLE_REMOTE_PATH:
            captured_bundles.append(json.loads(Path(local_path).read_text()))

    async def fake_download(source: str, target: Any) -> None:
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_text(json.dumps({"adapter_name": "entrypoint"}))

    env.upload_file = AsyncMock(side_effect=capture_upload)
    env.download_file = AsyncMock(side_effect=fake_download)

    asyncio.run(agent.run(original, env, context))

    assert captured_bundles[0]["request"]["instruction"] == effective
    assert captured_bundles[0]["request"]["configuration"]["kernel_instruction_override"] == (
        override.model_dump(mode="json")
    )

    mismatched = EntrypointAgent(
        logs_dir=tmp_path,
        model_name="claude-sonnet-4-20250514",
        adapter="tool_loop",
        kernel_instruction_override=override.model_dump(mode="json"),
    )
    with pytest.raises(ValueError, match="original instruction"):
        asyncio.run(mismatched.run("Different task bytes.", env, context))


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


def test_bundle_materializes_harness_tools_context_and_lineage(tmp_path: Path) -> None:
    """Typed harness settings must reach the adapter request rather than remain metadata."""
    tools = [
        {
            "name": "read-evidence",
            "source": "tools/read_evidence.py",
            "description": "Read one declared evidence packet.",
            "returns_image": False,
        }
    ]
    meta_harness_context = {
        "kernel_sha256": "a" * 64,
        "harness_id": "hx-review",
        "harness_sha256": "b" * 64,
        "program_id": "px-review",
        "program_sha256": "c" * 64,
        "bundle_id": "bundle-review",
        "bundle_sha256": "d" * 64,
        "program_node_id": "review",
        "binding_ids": ["agent", "tools"],
        "repair_iteration": 0,
        "attempt": 1,
        "motif_ids": [],
    }
    agent = EntrypointAgent(
        logs_dir=tmp_path,
        model_name="replay-tool-loop",
        adapter="tool_loop",
        system_prompt="Review evidence conservatively.",
        tools=tools,
        meta_harness_context=meta_harness_context,
    )
    env = _make_environment()
    context = MagicMock()
    context.metadata = {}
    env.exec.return_value = _make_exec_result(return_code=0)
    captured_bundles: list[dict[str, Any]] = []

    async def capture_upload(local_path: str, remote_path: str) -> None:
        if remote_path == _BUNDLE_REMOTE_PATH:
            captured_bundles.append(json.loads(Path(local_path).read_text()))

    async def fake_download(source: str, target: Any) -> None:
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_text(json.dumps({"adapter_name": "entrypoint"}))

    env.upload_file = AsyncMock(side_effect=capture_upload)
    env.download_file = AsyncMock(side_effect=fake_download)

    asyncio.run(agent.run("Review this package", env, context))

    request = captured_bundles[0]["request"]
    assert request["system_prompt"] == "Review evidence conservatively."
    assert request["tools"] == tools
    assert request["configuration"]["meta_harness_context"] == meta_harness_context


def test_anthropic_client_injects_only_approved_host_secret_without_serializing_it(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    secret = "anthropic-secret-marker"
    unselected_secret = "openai-secret-marker"
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
    monkeypatch.setenv("OPENAI_API_KEY", unselected_secret)
    agent = EntrypointAgent(
        logs_dir=tmp_path,
        model_name="claude-sonnet-4-20250514",
        adapter="direct",
        client={
            "client_kind": "anthropic_api",
            "payload": {"api_key_env": "ANTHROPIC_API_KEY", "max_tokens": 4096},
        },
    )
    env = _make_environment()
    context = MagicMock()
    context.metadata = {}
    env.exec.return_value = _make_exec_result(return_code=0)
    captured_bundles: list[dict[str, Any]] = []

    async def capture_upload(local_path: str, remote_path: str) -> None:
        if remote_path == _BUNDLE_REMOTE_PATH:
            captured_bundles.append(json.loads(Path(local_path).read_text()))

    async def fake_download(source: str, target: Any) -> None:
        Path(target).write_text(json.dumps({"adapter_name": "entrypoint"}))

    env.upload_file = AsyncMock(side_effect=capture_upload)
    env.download_file = AsyncMock(side_effect=fake_download)

    asyncio.run(agent.run("Use Anthropic", env, context))

    entrypoint_call = next(call for call in env.exec.call_args_list if "execution_entrypoint" in call.args[0])
    serialized_bundle = json.dumps(captured_bundles[0], sort_keys=True)
    assert entrypoint_call.kwargs["env"] == {"ANTHROPIC_API_KEY": secret}
    assert secret not in entrypoint_call.args[0]
    assert secret not in serialized_bundle
    assert unselected_secret not in serialized_bundle
    assert captured_bundles[0]["execution"]["payload"]["client"]["payload"]["api_key_env"] == ("ANTHROPIC_API_KEY")


def test_model_selected_azure_provider_receives_only_azure_runtime_configuration(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-secret-marker")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://approved-resource.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "unselected-anthropic-secret")
    agent = EntrypointAgent(
        logs_dir=tmp_path,
        model_name="gpt-4.1-mini",
        adapter="rlm",
    )
    env = _make_environment()
    context = MagicMock()
    context.metadata = {}
    env.exec.return_value = _make_exec_result(return_code=0)

    async def fake_download(source: str, target: Any) -> None:
        Path(target).write_text(json.dumps({"adapter_name": "entrypoint"}))

    env.download_file = AsyncMock(side_effect=fake_download)

    asyncio.run(agent.run("Use Azure", env, context))

    entrypoint_call = next(call for call in env.exec.call_args_list if "execution_entrypoint" in call.args[0])
    assert entrypoint_call.kwargs["env"] == {
        "AZURE_OPENAI_API_KEY": "azure-secret-marker",
        "AZURE_OPENAI_API_VERSION": "2025-01-01-preview",
        "AZURE_OPENAI_ENDPOINT": "https://approved-resource.openai.azure.com",
    }


def test_model_selected_bedrock_direct_provider_receives_only_bedrock_runtime_configuration(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "bedrock-secret-marker")
    monkeypatch.setenv("AWS_REGION", "ap-southeast-2")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "unselected-anthropic-secret")
    agent = EntrypointAgent(
        logs_dir=tmp_path,
        model_name="au.anthropic.claude-sonnet-4-6",
        adapter="direct",
    )
    env = _make_environment()
    context = MagicMock()
    context.metadata = {}
    env.exec.return_value = _make_exec_result(return_code=0)

    async def fake_download(source: str, target: Any) -> None:
        Path(target).write_text(json.dumps({"adapter_name": "entrypoint"}))

    env.download_file = AsyncMock(side_effect=fake_download)

    asyncio.run(agent.run("Use Bedrock", env, context))

    entrypoint_call = next(call for call in env.exec.call_args_list if "execution_entrypoint" in call.args[0])
    assert entrypoint_call.kwargs["env"] == {
        "AWS_BEARER_TOKEN_BEDROCK": "bedrock-secret-marker",
        "AWS_REGION": "ap-southeast-2",
    }


def test_missing_required_provider_credential_fails_before_bundle_upload(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
    agent = EntrypointAgent(
        logs_dir=tmp_path,
        model_name="together:meta-llama/Llama-3.3-70B-Instruct-Turbo",
        adapter="direct",
        client={"client_kind": "together_chat", "payload": {}},
    )
    env = _make_environment()

    with pytest.raises(RuntimeError, match="TOGETHER_API_KEY"):
        asyncio.run(agent.run("Use Together", env, MagicMock()))

    env.upload_file.assert_not_awaited()
    env.exec.assert_not_awaited()


def test_replay_client_requires_no_secret_and_receives_no_host_environment(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-cross")
    agent = EntrypointAgent(
        logs_dir=tmp_path,
        model_name="claude-looking-replay-model",
        adapter="direct",
        client={"client_kind": "replay", "payload": {"output_text": "done"}},
    )
    env = _make_environment()
    context = MagicMock()
    context.metadata = {}
    env.exec.return_value = _make_exec_result(return_code=0)

    async def fake_download(source: str, target: Any) -> None:
        Path(target).write_text(json.dumps({"adapter_name": "entrypoint"}))

    env.download_file = AsyncMock(side_effect=fake_download)

    asyncio.run(agent.run("Replay", env, context))

    entrypoint_call = next(call for call in env.exec.call_args_list if "execution_entrypoint" in call.args[0])
    assert "env" not in entrypoint_call.kwargs


def test_client_cannot_request_an_unapproved_host_environment_name(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("UNRELATED_PRIVATE_TOKEN", "must-not-cross")
    agent = EntrypointAgent(
        logs_dir=tmp_path,
        model_name="claude-sonnet-4-20250514",
        adapter="direct",
        client={
            "client_kind": "anthropic_api",
            "payload": {"api_key_env": "UNRELATED_PRIVATE_TOKEN"},
        },
    )

    with pytest.raises(ValueError, match="not approved for client kind 'anthropic_api'"):
        asyncio.run(agent.run("Do not exfiltrate", _make_environment(), MagicMock()))


def test_literal_provider_secret_in_client_payload_is_rejected_before_serialization(
    tmp_path: Path,
) -> None:
    agent = EntrypointAgent(
        logs_dir=tmp_path,
        model_name="replay",
        adapter="direct",
        client={
            "client_kind": "replay",
            "payload": {"api_key": "literal-secret-must-not-serialize"},
        },
    )

    with pytest.raises(ValueError, match="provider secrets must come from the host environment"):
        asyncio.run(agent.run("Reject literals", _make_environment(), MagicMock()))


def test_secret_values_are_redacted_from_failure_metadata(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    secret = "metadata-secret-marker"
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
    agent = EntrypointAgent(
        logs_dir=tmp_path,
        model_name="claude-sonnet-4-20250514",
        adapter="direct",
        client={"client_kind": "anthropic_api", "payload": {}},
    )
    env = _make_environment()
    context = MagicMock()
    context.metadata = {}
    env.exec.return_value = _make_exec_result(return_code=1, stderr=f"provider failed with {secret}")
    env.download_file = AsyncMock(side_effect=RuntimeError(f"download failed near {secret}"))

    asyncio.run(agent.run("Redact failures", env, context))

    serialized_metadata = json.dumps(context.metadata, sort_keys=True)
    assert secret not in serialized_metadata
    assert "<redacted>" in serialized_metadata


@pytest.mark.parametrize("timeout_sec", [0, -1])
def test_non_positive_timeout_fails_before_upload_or_execution(
    tmp_path: Path,
    timeout_sec: int,
) -> None:
    agent = EntrypointAgent(
        logs_dir=tmp_path,
        model_name="replay",
        adapter="direct",
        timeout_sec=timeout_sec,
        client={"client_kind": "replay", "payload": {"output_text": "done"}},
    )
    env = _make_environment()

    with pytest.raises(ValueError, match="timeout_sec must be a positive integer"):
        asyncio.run(agent.run("Reject invalid timeout", env, MagicMock()))

    env.upload_file.assert_not_awaited()
    env.exec.assert_not_awaited()
