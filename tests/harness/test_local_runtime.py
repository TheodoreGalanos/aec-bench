# ABOUTME: Tests for local workspace setup in the harness package.
# ABOUTME: Covers file copying, path patching, and instruction reading.

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aec_bench.harness.local_runtime import (
    patch_workspace_paths,
    read_instruction,
    setup_workspace,
    stage_verifier_assets,
    unstage_verifier_assets,
)


@pytest.fixture()
def task_dir(tmp_path: Path) -> Path:
    """Create a minimal task directory structure for testing."""
    task = tmp_path / "task"
    task.mkdir()
    (task / "task.toml").write_text("[meta]\nname = 'test'\n")
    (task / "instruction.md").write_text("Do the thing with /workspace/tool.py")
    return task


class TestSetupWorkspace:
    """Tests for setup_workspace."""

    def test_copies_task_files_into_temp_dir(self, task_dir: Path) -> None:
        workspace = setup_workspace(str(task_dir))
        try:
            assert Path(workspace).is_dir()
            assert (Path(workspace) / "task.toml").exists()
            assert (Path(workspace) / "instruction.md").exists()
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def test_flattens_environment_workspace_contents(self, task_dir: Path) -> None:
        env_ws = task_dir / "environment" / "workspace"
        env_ws.mkdir(parents=True)
        (env_ws / "helper.py").write_text("print('hello')")
        (env_ws / "data" / "input.csv").parent.mkdir(parents=True, exist_ok=True)
        (env_ws / "data" / "input.csv").write_text("a,b\n1,2\n")

        workspace = setup_workspace(str(task_dir))
        try:
            assert (Path(workspace) / "helper.py").exists()
            assert (Path(workspace) / "data" / "input.csv").exists()
            # Full environment directory is also kept for backwards compat
            assert (Path(workspace) / "environment" / "workspace" / "helper.py").exists()
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def test_mirrors_nested_environment_assets_at_workspace_root(self, task_dir: Path) -> None:
        sources = task_dir / "environment" / "sources"
        sources.mkdir(parents=True)
        (sources / "document-register.md").write_text("# Document Register\n")
        (sources / "support" / "basis.txt").parent.mkdir(parents=True)
        (sources / "support" / "basis.txt").write_text("current basis\n")
        (task_dir / "instruction.md").write_text("Read /workspace/sources/document-register.md")

        workspace = setup_workspace(str(task_dir))
        try:
            patch_workspace_paths(workspace)

            mirrored_register = Path(workspace) / "sources" / "document-register.md"
            mirrored_basis = Path(workspace) / "sources" / "support" / "basis.txt"
            assert mirrored_register.read_text() == "# Document Register\n"
            assert mirrored_basis.read_text() == "current basis\n"

            instruction = (Path(workspace) / "instruction.md").read_text()
            assert str(mirrored_register) in instruction

            # Keep the original environment layout for backwards compatibility.
            assert (Path(workspace) / "environment" / "sources" / "document-register.md").exists()
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def test_skips_pycache_directories(self, task_dir: Path) -> None:
        cache = task_dir / "__pycache__"
        cache.mkdir()
        (cache / "module.cpython-312.pyc").write_bytes(b"\x00")

        workspace = setup_workspace(str(task_dir))
        try:
            assert not (Path(workspace) / "__pycache__").exists()
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def test_keeps_verifier_assets_out_of_agent_workspace(self, task_dir: Path) -> None:
        tests_dir = task_dir / "tests"
        tests_dir.mkdir()
        (tests_dir / "instance.json").write_text('{"ground_truth": {"answer": 42}}')
        (tests_dir / "fixtures").mkdir()
        (tests_dir / "fixtures" / "golden_pass.md").write_text("answer: 42\n")

        workspace = setup_workspace(str(task_dir))
        try:
            assert not (Path(workspace) / "tests").exists()
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def test_stages_verifier_assets_only_for_verification(self, task_dir: Path) -> None:
        tests_dir = task_dir / "tests"
        tests_dir.mkdir()
        (tests_dir / "verify.py").write_text("# verifier\n")
        (tests_dir / "instance.json").write_text('{"ground_truth": {"answer": 42}}')

        workspace = setup_workspace(str(task_dir))
        try:
            stage_verifier_assets(task_dir, workspace)
            assert (Path(workspace) / "tests" / "verify.py").read_text() == "# verifier\n"
            assert (Path(workspace) / "tests" / "instance.json").exists()

            unstage_verifier_assets(workspace)
            assert not (Path(workspace) / "tests").exists()
        finally:
            shutil.rmtree(workspace, ignore_errors=True)


class TestPatchWorkspacePaths:
    """Tests for patch_workspace_paths."""

    def test_patches_py_files(self, tmp_path: Path) -> None:
        workspace = str(tmp_path)
        (tmp_path / "tool.py").write_text('BASE = "/workspace/data"\n')

        patch_workspace_paths(workspace)

        content = (tmp_path / "tool.py").read_text()
        assert "/workspace/" not in content
        assert workspace in content

    def test_patches_instruction_md(self, tmp_path: Path) -> None:
        workspace = str(tmp_path)
        (tmp_path / "instruction.md").write_text("Run /workspace/tool.py")

        patch_workspace_paths(workspace)

        content = (tmp_path / "instruction.md").read_text()
        assert "/workspace/" not in content
        assert workspace in content


class TestReadInstruction:
    """Tests for read_instruction."""

    def test_returns_instruction_md_content(self, tmp_path: Path) -> None:
        (tmp_path / "instruction.md").write_text("Do the task")
        assert read_instruction(str(tmp_path)) == "Do the task"

    def test_falls_back_to_other_md_files(self, tmp_path: Path) -> None:
        # No instruction.md, but another .md file exists (not in skip list)
        (tmp_path / "brief.md").write_text("Alternative instructions")
        (tmp_path / "system_prompt.md").write_text("System prompt (should be skipped)")
        (tmp_path / "notes.md").write_text("Notes (should be skipped)")
        (tmp_path / "README.md").write_text("Readme (should be skipped)")

        assert read_instruction(str(tmp_path)) == "Alternative instructions"

    def test_returns_empty_string_when_no_md_files(self, tmp_path: Path) -> None:
        (tmp_path / "data.txt").write_text("Not a markdown file")
        assert read_instruction(str(tmp_path)) == ""
