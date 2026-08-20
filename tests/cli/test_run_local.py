# ABOUTME: Tests for local RLM execution without Docker/Modal/Harbor.
# ABOUTME: Validates workspace setup, instruction reading, verifier, and retry behavior.

from __future__ import annotations

import importlib
import inspect
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
import typer

from aec_bench.cli.commands.run_local import (
    _require_adapter_runtime,
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


def test_prime_path_stages_runs_verifies_and_imports_with_fake_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    task_dir = tmp_path / "tasks" / "test" / "public-task"
    task_dir.mkdir(parents=True)
    (task_dir / "instruction.md").write_text("Write /workspace/output.md", encoding="utf-8")
    (task_dir / "task.toml").write_text(
        'version = "1.0"\n\n[metadata]\ndifficulty = "easy"\ncategory = "reasoning"\ntags = []\n'
        "\n[agent]\ntimeout_sec = 30.0\n\n[verifier]\ntimeout_sec = 30.0\n"
        "\n[environment]\nextensions = []\nbuild_timeout_sec = 30.0\ncpus = 1\nmemory_mb = 512\n"
        "storage_mb = 512\nallow_internet = false\n",
        encoding="utf-8",
    )
    environment = task_dir / "environment"
    environment.mkdir()
    (environment / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
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
    monkeypatch.setattr(run_local_module, "emit", lambda *args, **kwargs: None)

    run_local_module.run_local(
        task_path=str(task_dir),
        model="anthropic/requested",
        adapter="prime-agent",
        output_dir=str(output_dir),
        timeout=5,
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

    assert (output_dir / "output.md").exists()
    assert (output_dir / "prime-events.jsonl").exists()
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
