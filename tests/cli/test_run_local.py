# ABOUTME: Tests for local RLM execution without Docker/Modal/Harbor.
# ABOUTME: Validates workspace setup, instruction reading, verifier, and legacy script prep.

from __future__ import annotations

import importlib
import json
import shutil
import tempfile
from pathlib import Path

from aec_bench.cli.commands.run_local import (
    _archive_verifier_retry_attempt,
    _build_verifier_retry_instruction,
    _copy_output_files,
    _prepare_verifier_retry_workspace,
    _run_verifier,
    _should_run_verifier_feedback_retry,
)
from aec_bench.harness.local_runtime import (
    read_instruction,
    setup_workspace,
    setup_workspace_for_script,
)

run_local_module = importlib.import_module("aec_bench.cli.commands.run_local")


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
            legacy_script=False,
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
            legacy_script=False,
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
