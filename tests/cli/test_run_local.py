# ABOUTME: Tests for local RLM execution without Docker/Modal/Harbor.
# ABOUTME: Validates workspace setup, instruction reading, verifier, and retry behavior.

from __future__ import annotations

import importlib
import inspect
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
import typer

from aec_bench.cli.commands.run_local import (
    _archive_verifier_retry_attempt,
    _build_verifier_retry_instruction,
    _copy_output_files,
    _prepare_verifier_retry_workspace,
    _require_adapter_runtime,
    _run_adapter,
    _run_verifier,
    _should_run_verifier_feedback_retry,
)
from aec_bench.harness.local_runtime import (
    read_instruction,
    setup_workspace,
)

run_local_module = importlib.import_module("aec_bench.cli.commands.run_local")


def test_run_local_default_adapter_remains_rlm() -> None:
    adapter_option = inspect.signature(run_local_module.run_local).parameters["adapter"].default

    assert adapter_option.default == "rlm"


def test_prime_preflight_checks_only_the_external_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(run_local_module, "resolve_prime_executable", lambda executable: Path(f"/bin/{executable}"))
    monkeypatch.setattr(
        run_local_module,
        "require_optional_extra",
        lambda *_args, **_kwargs: calls.append("pydantic-ai"),
    )

    _require_adapter_runtime("prime-agent")

    assert calls == []


def test_existing_adapter_preflight_still_requires_local_agents_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(run_local_module, "require_optional_extra", lambda *args, **_kwargs: calls.append(args))

    _require_adapter_runtime("direct")

    assert calls == [("Local agent execution support", "local-agents", ("pydantic_ai",))]


def test_deepseek_preflight_requires_only_the_deepseek_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(run_local_module, "require_optional_extra", lambda *args, **_kwargs: calls.append(args))

    _require_adapter_runtime("deepseek_harness")

    assert calls == [("DeepSeek Harness execution support", "deepseek-harness", ("deepseek_harness",))]


def test_missing_prime_executable_reports_separate_install(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from aec_bench.prime_agent.batch import PrimeExecutableNotFoundError

    def fail(_executable: str) -> Path:
        raise PrimeExecutableNotFoundError("prime-agent executable was not found")

    monkeypatch.setattr(run_local_module, "resolve_prime_executable", fail)

    with pytest.raises(typer.Exit) as error:
        _require_adapter_runtime("prime-agent")

    stderr = capsys.readouterr().err
    assert error.value.exit_code == 1
    assert "Prime Agent executable was not found" in stderr
    assert "aec-bench[local-agents]" not in stderr


def test_prime_adapter_receives_run_local_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from aec_bench.adapters.base import AdapterResult
    from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus

    (tmp_path / "instruction.md").write_text("Write output.md", encoding="utf-8")
    observed: dict[str, object] = {}

    class FakeAdapter:
        def execute(self, request):  # noqa: ANN001
            observed["configuration"] = request.configuration
            observed["output_path"] = request.output_path
            (tmp_path / "output.md").write_text("Done", encoding="utf-8")
            return AdapterResult(
                adapter_name="prime-agent",
                resolved_model="anthropic/resolved",
                configuration_record={},
                agent_output=AgentOutput(
                    status=AgentOutputStatus.COMPLETED,
                    output_path=request.output_path,
                    output_format=request.output_format,
                ),
                transcript=[],
            )

    monkeypatch.setattr(
        "aec_bench.adapters.local_registry.build_local_adapter",
        lambda **_kwargs: FakeAdapter(),
    )

    result = _run_adapter(
        adapter_kind="prime-agent",
        workspace=str(tmp_path),
        model="anthropic/requested",
        timeout=37,
    )

    assert observed == {"configuration": {"timeout_seconds": 37}, "output_path": "output.md"}
    assert result["status"] == "completed"


def test_deepseek_adapter_receives_run_local_limits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from aec_bench.adapters.base import AdapterResult
    from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus

    (tmp_path / "instruction.md").write_text("Write output.md", encoding="utf-8")
    observed: dict[str, object] = {}

    class FakeAdapter:
        def execute(self, request):  # noqa: ANN001
            observed["configuration"] = request.configuration
            observed["output_path"] = request.output_path
            observed["output_format"] = request.output_format
            return AdapterResult(
                adapter_name="deepseek_harness",
                resolved_model="test-deployment",
                configuration_record={},
                agent_output=AgentOutput(
                    status=AgentOutputStatus.COMPLETED,
                    output_path=request.output_path,
                    output_format=request.output_format,
                ),
                transcript=[],
                raw_output_text="Done",
            )

    monkeypatch.setattr(
        "aec_bench.adapters.local_registry.build_local_adapter",
        lambda **_kwargs: FakeAdapter(),
    )

    result = _run_adapter(
        adapter_kind="deepseek_harness",
        workspace=str(tmp_path),
        model="azure:test-deployment",
        timeout=37,
        max_tokens=128,
    )

    assert observed == {
        "configuration": {"timeout_sec": 37, "max_tokens": 128},
        "output_path": "output.md",
        "output_format": "markdown",
    }
    assert result["status"] == "completed"


def test_existing_direct_adapter_still_reaches_the_same_execution_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from aec_bench.adapters.base import AdapterResult
    from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus

    (tmp_path / "instruction.md").write_text("Answer directly", encoding="utf-8")
    observed: dict[str, object] = {}

    class FakeDirectAdapter:
        def execute(self, request):  # noqa: ANN001
            observed["instruction"] = request.instruction
            observed["configuration"] = request.configuration
            return AdapterResult(
                adapter_name="direct",
                resolved_model="test-model",
                configuration_record={"model": "test-model"},
                agent_output=AgentOutput(
                    status=AgentOutputStatus.COMPLETED,
                    output_path=request.output_path,
                    output_format=request.output_format,
                ),
                transcript=[],
                raw_output_text="Existing result",
            )

    def fake_builder(**kwargs: object) -> FakeDirectAdapter:
        observed["adapter_kind"] = kwargs["adapter_kind"]
        return FakeDirectAdapter()

    monkeypatch.setattr("aec_bench.adapters.local_registry.build_local_adapter", fake_builder)

    result = _run_adapter(
        adapter_kind="direct",
        workspace=str(tmp_path),
        model="test-model",
        timeout=19,
    )

    assert observed == {
        "adapter_kind": "direct",
        "instruction": "Answer directly",
        "configuration": {},
    }
    assert result["status"] == "completed"
    assert (tmp_path / "output.md").read_text(encoding="utf-8") == "Existing result"


def test_copy_output_files_includes_prime_evidence_and_sessions(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for name in ("prime-events.jsonl", "prime-stderr.log", "prime-run.json"):
        (workspace / name).write_text(name, encoding="utf-8")
    session = workspace / "logs" / "prime" / "sessions" / "session.jsonl"
    session.parent.mkdir(parents=True)
    session.write_text("session", encoding="utf-8")
    output = tmp_path / "output"

    copied = _copy_output_files(str(workspace), output)

    assert copied == [
        "prime-events.jsonl",
        "prime-stderr.log",
        "prime-run.json",
        "logs/prime/sessions/session.jsonl",
    ]
    assert (output / "logs" / "prime" / "sessions" / "session.jsonl").exists()


def test_prime_path_stages_runs_verifies_and_imports_with_fake_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aec_bench.contracts.trial_record import TimingRecord
    from aec_bench.harness.local_import import build_trial_record_from_workspace

    executable_dir = tmp_path / "bin"
    executable_dir.mkdir()
    executable = executable_dir / "prime-agent"
    executable.write_text(
        f"""#!{sys.executable}
import json
import os
from pathlib import Path
import sys

if "--version" in sys.argv:
    print("prime-agent 0.7.0")
    raise SystemExit(0)

Path("output.md").write_text("# Prime result\\n", encoding="utf-8")
session_dir = Path(os.environ["PRIME_AGENT_SESSION_DIR"])
session_dir.mkdir(parents=True, exist_ok=True)
(session_dir / "session.jsonl").write_text('{{"type":"session"}}\\n', encoding="utf-8")
message = {{
    "role": "assistant",
    "content": [{{"type": "text", "text": "Completed"}}],
    "provider": "anthropic",
    "model": "anthropic/requested",
    "responseModel": "anthropic/resolved",
    "responseId": "integration-response",
    "usage": {{"input": 10, "output": 4, "cacheRead": 0, "cacheWrite": 0}},
    "stopReason": "stop",
    "timestamp": 1786064524000,
}}
for event in [
    {{"type": "session", "version": 3, "id": "integration-session", "cwd": os.getcwd()}},
    {{"type": "turn_start"}},
    {{"type": "message_end", "message": message}},
    {{"type": "turn_end", "message": message, "toolResults": []}},
    {{"type": "agent_end", "messages": [message]}},
]:
    print(json.dumps(event), flush=True)
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{executable_dir}{os.pathsep}{os.environ['PATH']}")

    task_dir = tmp_path / "tasks" / "public-task"
    task_dir.mkdir(parents=True)
    (task_dir / "instruction.md").write_text("Write output.md", encoding="utf-8")
    verifier = task_dir / "tests" / "verify.py"
    verifier.parent.mkdir()
    verifier.write_text(
        """import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input")
parser.add_argument("--output")
args = parser.parse_args()
Path(args.output).write_text(json.dumps({"reward": 1.0}), encoding="utf-8")
""",
        encoding="utf-8",
    )
    output_dir = tmp_path / "result"
    imported: dict[str, object] = {}

    def fake_auto_import(**kwargs: object) -> None:
        workspace = Path(str(kwargs["workspace"]))
        record = build_trial_record_from_workspace(
            workspace_dir=workspace,
            trial_id="prime-trial",
            experiment_id="local",
            task_id="public-task",
            model=str(kwargs["model"]),
            adapter=str(kwargs["adapter"]),
            instruction="Write output.md",
            timing=TimingRecord(total_seconds=1.0),
        )
        imported["adapter"] = record.agent.adapter
        imported["model"] = record.agent.model
        imported["reward"] = record.evaluation.reward
        imported["tokens_in"] = record.cost.tokens_in if record.cost is not None else None

    monkeypatch.setattr(run_local_module, "_auto_import", fake_auto_import)
    monkeypatch.setattr(run_local_module, "emit", lambda *args, **kwargs: None)

    run_local_module.run_local(
        task_path=str(task_dir),
        model="anthropic/requested",
        adapter="prime-agent",
        output_dir=str(output_dir),
        timeout=5,
        keep_workspace=False,
        no_verify=False,
        no_import=False,
        no_normalise=True,
        constitutional_model=None,
        reviewer=False,
        reviewer_model=None,
        reviewer_models_config=None,
        fail_on_reviewer_error=False,
    )

    assert imported == {
        "adapter": "prime-agent",
        "model": "anthropic/resolved",
        "reward": 1.0,
        "tokens_in": 10,
    }
    assert (output_dir / "output.md").exists()
    assert (output_dir / "prime-events.jsonl").exists()
    assert (output_dir / "prime-stderr.log").exists()
    assert (output_dir / "prime-run.json").exists()
    assert (output_dir / "logs" / "prime" / "sessions" / "session.jsonl").exists()


class TestSetupWorkspace:
    """Validate that workspace setup copies task files correctly."""

    def test_copies_task_files(self) -> None:
        """Workspace setup should copy all task files into a temp directory."""
        with tempfile.TemporaryDirectory() as task_dir:
            Path(task_dir, "instruction.md").write_text("Do the thing")
            Path(task_dir, "rlm.toml").write_text('[template]\ntier = "flat"')
            Path(task_dir, "system_prompt.md").write_text("You are helpful")

            workspace = setup_workspace(task_dir)
            try:
                assert Path(workspace, "instruction.md").exists()
                assert Path(workspace, "rlm.toml").exists()
                assert Path(workspace, "system_prompt.md").exists()
            finally:
                shutil.rmtree(workspace, ignore_errors=True)

    def test_copies_subdirectories(self) -> None:
        """Workspace setup should recursively copy subdirectories."""
        with tempfile.TemporaryDirectory() as task_dir:
            Path(task_dir, "instruction.md").write_text("Do the thing")
            sub = Path(task_dir, "environment")
            sub.mkdir()
            Path(sub, "Dockerfile").write_text("FROM python:3.11")

            workspace = setup_workspace(task_dir)
            try:
                assert Path(workspace, "environment", "Dockerfile").exists()
            finally:
                shutil.rmtree(workspace, ignore_errors=True)

    def test_skips_pycache(self) -> None:
        """Workspace setup should skip __pycache__ directories."""
        with tempfile.TemporaryDirectory() as task_dir:
            Path(task_dir, "instruction.md").write_text("Do the thing")
            cache = Path(task_dir, "__pycache__")
            cache.mkdir()
            Path(cache, "junk.pyc").write_text("bytecode")

            workspace = setup_workspace(task_dir)
            try:
                assert not Path(workspace, "__pycache__").exists()
            finally:
                shutil.rmtree(workspace, ignore_errors=True)

    def test_flattens_environment_files_to_root(self) -> None:
        """Environment files should be copied to workspace root, mirroring Dockerfile COPY."""
        with tempfile.TemporaryDirectory() as task_dir:
            Path(task_dir, "instruction.md").write_text("task")
            env = Path(task_dir, "environment")
            env.mkdir()
            Path(env, "Dockerfile").write_text("FROM python:3.11")
            Path(env, "heat_load_calc.py").write_text("def compute(): pass")
            Path(env, "system_prompt.md").write_text("You are helpful")

            workspace = setup_workspace(task_dir)
            try:
                # Files flattened to root
                assert Path(workspace, "heat_load_calc.py").exists()
                assert Path(workspace, "system_prompt.md").exists()
                assert Path(workspace, "Dockerfile").exists()
                # Original subdir also kept
                assert Path(workspace, "environment", "Dockerfile").exists()
            finally:
                shutil.rmtree(workspace, ignore_errors=True)

    def test_preserves_file_content(self) -> None:
        """Copied files should retain their original content."""
        with tempfile.TemporaryDirectory() as task_dir:
            original = "# Complex instruction\nWith multiple lines\nAnd data: 42"
            Path(task_dir, "instruction.md").write_text(original)

            workspace = setup_workspace(task_dir)
            try:
                assert Path(workspace, "instruction.md").read_text() == original
            finally:
                shutil.rmtree(workspace, ignore_errors=True)


class TestRunLocalWorkspacePrivacy:
    """Validate that verifier assets appear only after the agent turn."""

    def test_stages_tests_after_agent_execution(self, tmp_path: Path, monkeypatch) -> None:
        task_dir = tmp_path / "task"
        task_dir.mkdir()
        (task_dir / "instruction.md").write_text("Read /workspace/sources/input.md and write output.md")
        sources = task_dir / "environment" / "sources"
        sources.mkdir(parents=True)
        (sources / "input.md").write_text("agent-visible source\n")
        tests_dir = task_dir / "tests"
        tests_dir.mkdir()
        (tests_dir / "instance.json").write_text('{"ground_truth": {"answer": 42}}')
        (tests_dir / "verify.py").write_text("# private verifier\n")

        observed: dict[str, bool] = {}

        def fake_run_adapter(**kwargs):
            workspace = Path(kwargs["workspace"])
            observed["agent_source_visible"] = (workspace / "sources" / "input.md").exists()
            observed["agent_tests_visible"] = (workspace / "tests").exists()
            (workspace / "output.md").write_text("completed\n")
            return {"status": "completed"}

        def fake_run_verifier(*, workspace: str, output_file: str) -> float:
            del output_file
            workspace_path = Path(workspace)
            observed["verifier_tests_visible"] = (workspace_path / "tests" / "verify.py").exists()
            reward = workspace_path / "logs" / "verifier" / "reward.json"
            reward.parent.mkdir(parents=True)
            reward.write_text(json.dumps({"reward": 1.0}))
            return 0.01

        monkeypatch.setattr(run_local_module, "_run_adapter", fake_run_adapter)
        monkeypatch.setattr(run_local_module, "_run_verifier", fake_run_verifier)
        monkeypatch.setattr(run_local_module, "_report_results", lambda *args, **kwargs: None)
        monkeypatch.setattr(run_local_module, "emit", lambda *args, **kwargs: None)

        run_local_module.run_local(
            task_path=str(task_dir),
            model="test-model",
            adapter="direct",
            output_dir=str(tmp_path / "results"),
            timeout=30,
            keep_workspace=False,
            no_verify=False,
            no_import=True,
            no_normalise=True,
            constitutional_model=None,
            reviewer=False,
            reviewer_model=None,
            reviewer_models_config=None,
            fail_on_reviewer_error=False,
        )

        assert observed == {
            "agent_source_visible": True,
            "agent_tests_visible": False,
            "verifier_tests_visible": True,
        }

    def test_hides_tests_again_during_verifier_feedback_retry(self, tmp_path: Path, monkeypatch) -> None:
        task_dir = tmp_path / "task"
        task_dir.mkdir()
        (task_dir / "instruction.md").write_text("Write output.md")
        environment = task_dir / "environment"
        environment.mkdir()
        (environment / "verifier_retry_prompt.md").write_text("Repair the response")
        tests_dir = task_dir / "tests"
        tests_dir.mkdir()
        (tests_dir / "verify.py").write_text("# private verifier\n")
        (tests_dir / "instance.json").write_text('{"ground_truth": {"answer": 42}}')

        agent_visibility: list[bool] = []
        verifier_visibility: list[bool] = []

        def fake_run_adapter(**kwargs):
            workspace = Path(kwargs["workspace"])
            agent_visibility.append((workspace / "tests").exists())
            (workspace / "output.md").write_text(f"attempt {len(agent_visibility)}\n")
            return {"status": "completed"}

        def fake_run_verifier(*, workspace: str, output_file: str) -> float:
            del output_file
            workspace_path = Path(workspace)
            verifier_visibility.append((workspace_path / "tests" / "verify.py").exists())
            reward = workspace_path / "logs" / "verifier" / "reward.json"
            reward.parent.mkdir(parents=True, exist_ok=True)
            reward.write_text(json.dumps({"reward": 0.5 if len(verifier_visibility) == 1 else 1.0}))
            return 0.01

        monkeypatch.setattr(run_local_module, "_run_adapter", fake_run_adapter)
        monkeypatch.setattr(run_local_module, "_run_verifier", fake_run_verifier)
        monkeypatch.setattr(run_local_module, "_report_results", lambda *args, **kwargs: None)
        monkeypatch.setattr(run_local_module, "emit", lambda *args, **kwargs: None)

        run_local_module.run_local(
            task_path=str(task_dir),
            model="test-model",
            adapter="direct",
            output_dir=str(tmp_path / "results"),
            timeout=30,
            keep_workspace=False,
            no_verify=False,
            no_import=True,
            no_normalise=True,
            constitutional_model=None,
            reviewer=False,
            reviewer_model=None,
            reviewer_models_config=None,
            fail_on_reviewer_error=False,
        )

        assert agent_visibility == [False, False]
        assert verifier_visibility == [True, True]


class TestReadInstruction:
    """Validate instruction file reading from workspace."""

    def test_reads_instruction_md(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            Path(workspace, "instruction.md").write_text("Calculate voltage drop")
            assert read_instruction(workspace) == "Calculate voltage drop"

    def test_fallback_to_other_md_files(self) -> None:
        """When instruction.md is missing, should try other .md files."""
        with tempfile.TemporaryDirectory() as workspace:
            Path(workspace, "task_brief.md").write_text("Fallback instruction")
            assert read_instruction(workspace) == "Fallback instruction"

    def test_no_instruction_returns_empty(self) -> None:
        """When no instruction files exist, should return empty string."""
        with tempfile.TemporaryDirectory() as workspace:
            assert read_instruction(workspace) == ""

    def test_skips_system_prompt_and_notes(self) -> None:
        """Fallback should not pick up system_prompt.md or notes.md."""
        with tempfile.TemporaryDirectory() as workspace:
            Path(workspace, "system_prompt.md").write_text("System prompt")
            Path(workspace, "notes.md").write_text("Notes")
            Path(workspace, "README.md").write_text("Readme")
            assert read_instruction(workspace) == ""


class TestRunVerifier:
    """Validate verifier execution from a workspace directory."""

    def test_run_verifier_executes_verify_py(self, tmp_path: Path) -> None:
        """Verifier should run tests/verify.py and produce reward.json."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create output file
        output_file = workspace / "output.md"
        output_file.write_text("# My output\nAnswer: 42")

        # Create tests/verify.py that writes reward.json
        tests_dir = workspace / "tests"
        tests_dir.mkdir()
        verify_script = tests_dir / "verify.py"
        verify_script.write_text(
            "import argparse, json, pathlib\n"
            "parser = argparse.ArgumentParser()\n"
            'parser.add_argument("--input")\n'
            'parser.add_argument("--output")\n'
            "args = parser.parse_args()\n"
            "pathlib.Path(args.output).parent.mkdir(parents=True, exist_ok=True)\n"
            'pathlib.Path(args.output).write_text(json.dumps({"reward": 0.85}))\n'
        )

        elapsed = _run_verifier(workspace=str(workspace), output_file=str(output_file))

        assert elapsed is not None
        assert elapsed >= 0.0

        reward_path = workspace / "logs" / "verifier" / "reward.json"
        assert reward_path.exists()
        reward_data = json.loads(reward_path.read_text())
        assert reward_data["reward"] == 0.85

    def test_run_verifier_returns_none_when_no_verifier(self, tmp_path: Path) -> None:
        """Empty workspace with no verifier scripts should return None."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        elapsed = _run_verifier(workspace=str(workspace), output_file=str(workspace / "output.md"))
        assert elapsed is None

    def test_run_verifier_uses_test_sh_fallback(self, tmp_path: Path) -> None:
        """Should fall back to tests/test.sh when verify.py doesn't exist."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        output_file = workspace / "output.md"
        output_file.write_text("output")

        # Create tests/test.sh that writes reward.json
        tests_dir = workspace / "tests"
        tests_dir.mkdir()
        test_sh = tests_dir / "test.sh"
        test_sh.write_text(
            "#!/bin/bash\nmkdir -p logs/verifier\necho '{\"reward\": 0.5}' > logs/verifier/reward.json\n"
        )
        test_sh.chmod(0o755)

        elapsed = _run_verifier(workspace=str(workspace), output_file=str(output_file))

        assert elapsed is not None
        assert elapsed >= 0.0

        reward_path = workspace / "logs" / "verifier" / "reward.json"
        assert reward_path.exists()
        reward_data = json.loads(reward_path.read_text())
        assert reward_data["reward"] == 0.5

    def test_run_verifier_prefers_verify_py_over_test_sh(self, tmp_path: Path) -> None:
        """When both verify.py and test.sh exist, verify.py takes priority."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        output_file = workspace / "output.md"
        output_file.write_text("output")

        tests_dir = workspace / "tests"
        tests_dir.mkdir()

        # verify.py writes reward=0.9
        verify_script = tests_dir / "verify.py"
        verify_script.write_text(
            "import argparse, json, pathlib\n"
            "parser = argparse.ArgumentParser()\n"
            'parser.add_argument("--input")\n'
            'parser.add_argument("--output")\n'
            "args = parser.parse_args()\n"
            "pathlib.Path(args.output).parent.mkdir(parents=True, exist_ok=True)\n"
            'pathlib.Path(args.output).write_text(json.dumps({"reward": 0.9}))\n'
        )

        # test.sh writes reward=0.1 (should NOT be used)
        test_sh = tests_dir / "test.sh"
        test_sh.write_text(
            "#!/bin/bash\nmkdir -p logs/verifier\necho '{\"reward\": 0.1}' > logs/verifier/reward.json\n"
        )
        test_sh.chmod(0o755)

        _run_verifier(workspace=str(workspace), output_file=str(output_file))

        reward_path = workspace / "logs" / "verifier" / "reward.json"
        reward_data = json.loads(reward_path.read_text())
        assert reward_data["reward"] == 0.9

    def test_run_verifier_retries_workspace_style_verify_py(self, tmp_path: Path) -> None:
        """Legacy verifiers accept a workspace path rather than --input/--output."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        output_file = workspace / "output.md"
        output_file.write_text("output")

        tests_dir = workspace / "tests"
        tests_dir.mkdir()
        verify_script = tests_dir / "verify.py"
        verify_script.write_text(
            "import json, pathlib, sys\n"
            "workspace = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 "
            "else pathlib.Path('/workspace')\n"
            "reward = workspace / 'logs' / 'verifier' / 'reward.json'\n"
            "reward.parent.mkdir(parents=True, exist_ok=True)\n"
            "reward.write_text(json.dumps({'reward': 0.75}))\n"
        )

        elapsed = _run_verifier(workspace=str(workspace), output_file=str(output_file))

        assert elapsed is not None
        reward_path = workspace / "logs" / "verifier" / "reward.json"
        reward_data = json.loads(reward_path.read_text())
        assert reward_data["reward"] == 0.75


class TestVerifierFeedbackRetry:
    """Validate opt-in verifier feedback retry helpers."""

    def test_should_run_verifier_feedback_retry_requires_prompt_and_incomplete_reward(
        self,
        tmp_path: Path,
    ) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        assert not _should_run_verifier_feedback_retry(workspace, reward=0.0)

        (workspace / "verifier_retry_prompt.md").write_text("Repair the files.")

        assert _should_run_verifier_feedback_retry(workspace, reward=0.5)
        assert not _should_run_verifier_feedback_retry(workspace, reward=1.0)
        assert not _should_run_verifier_feedback_retry(workspace, reward=None)

    def test_build_verifier_retry_instruction_includes_prior_output_and_feedback(
        self,
        tmp_path: Path,
    ) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "verifier_retry_prompt.md").write_text("Write the missing files.")
        (workspace / "output.md").write_text("First answer without artifacts.")
        verifier_dir = workspace / "logs" / "verifier"
        verifier_dir.mkdir(parents=True)
        (verifier_dir / "feedback.md").write_text("Missing rewrite_integrity_report.json.")
        (verifier_dir / "details.json").write_text(json.dumps({"rewrite_integrity_report_written": 0.0}, indent=2))

        instruction = _build_verifier_retry_instruction(
            workspace=workspace,
            base_instruction="Original task instruction.",
            reward=0.25,
        )

        assert "Original task instruction." in instruction
        assert "Write the missing files." in instruction
        assert "First answer without artifacts." in instruction
        assert "Missing rewrite_integrity_report.json." in instruction
        assert '"rewrite_integrity_report_written": 0.0' in instruction
        assert "0.2500" in instruction

    def test_build_verifier_retry_instruction_prefers_retry_instruction_file(
        self,
        tmp_path: Path,
    ) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "verifier_retry_prompt.md").write_text("Repair the files.")
        (workspace / "verifier_retry_instruction.md").write_text("Clean retry-only instruction.")
        (workspace / "output.md").write_text("First answer.")
        verifier_dir = workspace / "logs" / "verifier"
        verifier_dir.mkdir(parents=True)
        (verifier_dir / "details.json").write_text(json.dumps({"score": 0.0}))

        instruction = _build_verifier_retry_instruction(
            workspace=workspace,
            base_instruction="Original turn 1 instruction with stale no-file constraint.",
            reward=0.0,
        )

        assert "Clean retry-only instruction." in instruction
        assert "Original turn 1 instruction" not in instruction
        assert "Repair the files." in instruction
        assert "First answer." in instruction

    def test_archive_verifier_retry_attempt_preserves_first_attempt_files(
        self,
        tmp_path: Path,
    ) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "output.md").write_text("first output")
        (workspace / "prime-events.jsonl").write_text('{"type":"session"}\n')
        prime_session = workspace / "logs" / "prime" / "sessions" / "session.jsonl"
        prime_session.parent.mkdir(parents=True)
        prime_session.write_text("prime session")
        (workspace / "rewrite_integrity_report.json").write_text(json.dumps({"attempt": 1}))
        verifier_dir = workspace / "logs" / "verifier"
        verifier_dir.mkdir(parents=True)
        (verifier_dir / "reward.json").write_text(json.dumps({"reward": 0.2}))
        (verifier_dir / "details.json").write_text(json.dumps({"field": 0.0}))
        (verifier_dir / "feedback.md").write_text("retry needed")

        archive_dir = _archive_verifier_retry_attempt(workspace, "attempt-01")

        assert (archive_dir / "output.md").read_text() == "first output"
        assert json.loads((archive_dir / "reward.json").read_text()) == {"reward": 0.2}
        assert json.loads((archive_dir / "details.json").read_text()) == {"field": 0.0}
        assert (archive_dir / "feedback.md").read_text() == "retry needed"
        assert (archive_dir / "artifacts" / "rewrite_integrity_report.json").exists()
        assert (archive_dir / "prime-events.jsonl").exists()
        assert (archive_dir / "prime-sessions" / "session.jsonl").read_text() == "prime session"

    def test_prepare_verifier_retry_workspace_archives_and_clears_output(
        self,
        tmp_path: Path,
    ) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "output.md").write_text("first output")
        verifier_dir = workspace / "logs" / "verifier"
        verifier_dir.mkdir(parents=True)
        (verifier_dir / "reward.json").write_text(json.dumps({"reward": 0.2}))

        archive_dir = _prepare_verifier_retry_workspace(workspace, "attempt-01")

        assert (archive_dir / "output.md").read_text() == "first output"
        assert not (workspace / "output.md").exists()


class TestCopyOutputFiles:
    """Validate partial output file copying for graceful exit."""

    def test_copies_existing_files(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        Path(workspace, "output.md").write_text("partial output")
        Path(workspace, "trajectory.jsonl").write_text('{"step": 1}\n')

        out_path = tmp_path / "results"
        copied = _copy_output_files(str(workspace), out_path)
        assert "output.md" in copied
        assert "trajectory.jsonl" in copied
        assert (out_path / "output.md").read_text() == "partial output"

    def test_copies_deepseek_harness_evidence(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        evidence = workspace / "logs" / "deepseek-harness" / "run-test"
        evidence.mkdir(parents=True)
        (evidence / "stderr.log").write_text("provider failure", encoding="utf-8")
        out_path = tmp_path / "results"

        copied = _copy_output_files(str(workspace), out_path)

        assert copied == ["logs/deepseek-harness/run-test/stderr.log"]
        assert (out_path / "logs" / "deepseek-harness" / "run-test" / "stderr.log").read_text() == ("provider failure")

    def test_skips_missing_files(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        # Only trajectory exists — output.md and others are missing
        Path(workspace, "trajectory.jsonl").write_text('{"step": 1}\n')

        out_path = tmp_path / "results"
        copied = _copy_output_files(str(workspace), out_path)
        assert "trajectory.jsonl" in copied
        assert "output.md" not in copied

    def test_creates_output_dir(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        Path(workspace, "output.md").write_text("data")

        out_path = tmp_path / "nested" / "results"
        _copy_output_files(str(workspace), out_path)
        assert out_path.is_dir()

    def test_preserves_verifier_side_effect_artifacts(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        Path(workspace, "anomaly_review_record.json").write_text(json.dumps({"issue_id": "ANOM-001"}))
        Path(workspace, "record_readback_check.json").write_text(json.dumps({"matches_record": False}))
        Path(workspace, "rewrite_integrity_report.json").write_text(json.dumps({"material_risk_preserved": True}))
        Path(workspace, "helper_execution_marker.json").write_text(
            json.dumps({"helper_name": "write_integrity_artifacts.py"})
        )
        Path(workspace, "source_pack.json").write_text(json.dumps({"source_id": "SRC-001"}))
        Path(workspace, "prior_record.json").write_text(json.dumps({"issue_id": "OLD-001"}))

        out_path = tmp_path / "results"
        copied = _copy_output_files(str(workspace), out_path)

        artifact_dir = out_path / "logs" / "verifier" / "artifacts"
        assert "logs/verifier/artifacts/anomaly_review_record.json" in copied
        assert "logs/verifier/artifacts/record_readback_check.json" in copied
        assert "logs/verifier/artifacts/rewrite_integrity_report.json" in copied
        assert "logs/verifier/artifacts/helper_execution_marker.json" in copied
        assert (artifact_dir / "anomaly_review_record.json").exists()
        assert (artifact_dir / "record_readback_check.json").exists()
        assert (artifact_dir / "rewrite_integrity_report.json").exists()
        assert (artifact_dir / "helper_execution_marker.json").exists()
        assert not (artifact_dir / "source_pack.json").exists()
        assert not (artifact_dir / "prior_record.json").exists()

    def test_copies_verifier_retry_attempt_archive(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        attempt_dir = workspace / "logs" / "verifier" / "attempts" / "attempt-01"
        attempt_dir.mkdir(parents=True)
        (attempt_dir / "output.md").write_text("first answer")
        (attempt_dir / "feedback.md").write_text("missing file")
        (workspace / "logs" / "verifier" / "retry.json").write_text(json.dumps({"performed": True}))

        out_path = tmp_path / "results"
        copied = _copy_output_files(str(workspace), out_path)

        assert "logs/verifier/retry.json" in copied
        assert "logs/verifier/attempts/attempt-01/output.md" in copied
        assert "logs/verifier/attempts/attempt-01/feedback.md" in copied
        assert (out_path / "logs" / "verifier" / "attempts" / "attempt-01" / "output.md").read_text() == "first answer"

    def test_copies_reviewer_artifacts(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        reviewer_dir = workspace / "logs" / "reviewer" / "openai-main"
        reviewer_dir.mkdir(parents=True)
        (workspace / "logs" / "reviewer" / "request.json").write_text(json.dumps({"payload": "review-request"}))
        (workspace / "logs" / "reviewer" / "summary.json").write_text(json.dumps({"status": "complete"}))
        (reviewer_dir / "review.json").write_text(json.dumps({"status": "complete"}))

        out_path = tmp_path / "results"
        copied = _copy_output_files(str(workspace), out_path)

        assert "logs/reviewer/request.json" in copied
        assert "logs/reviewer/summary.json" in copied
        assert "logs/reviewer/openai-main/review.json" in copied
        assert (out_path / "logs" / "reviewer" / "summary.json").exists()
