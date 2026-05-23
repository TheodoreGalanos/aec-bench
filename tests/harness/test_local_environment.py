# ABOUTME: Tests for LocalEnvironment protocol and HostEnvironment implementation.
# ABOUTME: Covers workspace setup, teardown, and keep-workspace behaviour.

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aec_bench.harness.local_environment import HostEnvironment


@pytest.fixture()
def task_dir(tmp_path: Path) -> Path:
    """Minimal task directory with a couple of files."""
    task = tmp_path / "task"
    task.mkdir()
    (task / "task.toml").write_text("[meta]\nname = 'test'\n")
    (task / "instruction.md").write_text("Do the thing.")
    return task


class TestHostEnvironmentSetupWorkspace:
    def test_copies_files_into_workspace(self, task_dir: Path) -> None:
        env = HostEnvironment()
        workspace = env.setup_workspace(task_dir)
        try:
            assert Path(workspace).is_dir()
            assert (Path(workspace) / "task.toml").exists()
            assert (Path(workspace) / "instruction.md").exists()
        finally:
            shutil.rmtree(workspace, ignore_errors=True)


class TestHostEnvironmentTeardown:
    def test_teardown_removes_workspace(self, task_dir: Path) -> None:
        env = HostEnvironment()
        workspace = env.setup_workspace(task_dir)
        assert Path(workspace).is_dir()

        env.teardown()

        assert not Path(workspace).exists()

    def test_teardown_keeps_workspace_when_requested(self, task_dir: Path) -> None:
        env = HostEnvironment()
        workspace = env.setup_workspace(task_dir)
        assert Path(workspace).is_dir()

        env.teardown(keep=True)

        try:
            assert Path(workspace).is_dir()
        finally:
            shutil.rmtree(workspace, ignore_errors=True)
