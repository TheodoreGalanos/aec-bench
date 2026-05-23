# ABOUTME: Tests for local RLM execution without Docker/Modal/Harbor.
# ABOUTME: Validates workspace setup, instruction reading, verifier, and legacy script prep.

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from aec_bench.cli.commands.run_local import _copy_output_files, _run_verifier
from aec_bench.harness.local_runtime import (
    read_instruction,
    setup_workspace,
    setup_workspace_for_script,
)


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


class TestSetupWorkspaceForScript:
    """Validate legacy script workspace with trajectory_writer and path patching."""

    def test_writes_trajectory_writer(self) -> None:
        """Legacy workspace should inject trajectory_writer.py."""
        with tempfile.TemporaryDirectory() as task_dir:
            Path(task_dir, "instruction.md").write_text("Do the thing")

            workspace = setup_workspace_for_script(task_dir)
            try:
                traj_path = Path(workspace, "trajectory_writer.py")
                assert traj_path.exists()
                content = traj_path.read_text()
                assert "TrajectoryWriter" in content
            finally:
                shutil.rmtree(workspace, ignore_errors=True)

    def test_patches_workspace_paths_in_python_files(self) -> None:
        """Legacy workspace should patch /workspace/ in copied .py files."""
        with tempfile.TemporaryDirectory() as task_dir:
            Path(task_dir, "instruction.md").write_text("Do the thing")
            Path(task_dir, "repl_commands.py").write_text('path = "/workspace/data.json"')

            workspace = setup_workspace_for_script(task_dir)
            try:
                content = Path(workspace, "repl_commands.py").read_text()
                assert "/workspace/" not in content
                assert workspace.rstrip("/") in content
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
