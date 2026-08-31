# ABOUTME: Focused tests for the extracted artifact workspace port.
# ABOUTME: Proves full-copy isolation, exact deltas, confinement, export, and disposal.

from pathlib import Path

import pytest

from aec_bench.contracts.task_definition import EnvironmentSpec, VerifierSpec
from aec_bench.harness.artifact.workspace_port import (
    dispose_workspace,
    export_selected_workspace,
    fork_attempt_workspace,
    materialize_base_workspace,
    resolve_workspace_path,
    workspace_delta,
)
from aec_bench.harness.workspace_evidence import capture_workspace_manifest
from aec_bench.tasks.instance import resolve_instance_paths
from tests.support.task_factories import make_task_definition


def _resolved_task(root: Path):  # noqa: ANN202
    task_dir = root / "task"
    task_dir.mkdir()
    (task_dir / "instruction.md").write_text("Write the result", encoding="utf-8")
    (task_dir / "input.txt").write_text("source", encoding="utf-8")
    environment = task_dir / "environment"
    environment.mkdir()
    (environment / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    tests = task_dir / "tests"
    tests.mkdir()
    (tests / "verify.py").write_text("# private\n", encoding="utf-8")
    definition = make_task_definition(
        task_id="test/artifact/ports",
        environment=EnvironmentSpec(dockerfile="environment/Dockerfile"),
        verifier=VerifierSpec(
            script="tests/verify.py",
            expected_output_path="/workspace/output.md",
            reward_path="logs/verifier/reward.json",
        ),
    )
    return resolve_instance_paths(definition, task_dir)


def test_materialize_and_fork_keep_task_and_attempts_isolated(tmp_path: Path) -> None:
    task = _resolved_task(tmp_path)
    first, base_manifest = materialize_base_workspace(task, work_root=tmp_path / "attempts", agent_files={})
    second = None
    try:
        assert (first / "input.txt").stat().st_ino != (task.instance_dir / "input.txt").stat().st_ino
        (first / "input.txt").write_text("first", encoding="utf-8")
        (first / "output.md").write_text("result", encoding="utf-8")
        second, _child_manifest, inherited = fork_attempt_workspace(
            first,
            base_manifest=base_manifest,
            inherited_paths=frozenset(),
            work_root=tmp_path / "attempts",
        )
        assert (task.instance_dir / "input.txt").read_text(encoding="utf-8") == "source"
        assert (second / "input.txt").read_text(encoding="utf-8") == "first"
        assert "output.md" in inherited
        (second / "input.txt").write_text("second", encoding="utf-8")
        assert (first / "input.txt").read_text(encoding="utf-8") == "first"
    finally:
        dispose_workspace(first)
        if second is not None:
            dispose_workspace(second)


def test_workspace_delta_export_and_dispose_are_exact(tmp_path: Path) -> None:
    task = _resolved_task(tmp_path)
    workspace, base_manifest = materialize_base_workspace(task, work_root=tmp_path / "attempts", agent_files={})
    exported = tmp_path / "selected"
    try:
        (workspace / "input.txt").write_text("changed", encoding="utf-8")
        (workspace / "new.txt").write_text("new", encoding="utf-8")
        final_manifest = capture_workspace_manifest(workspace, default_source_role="actor_output")
        delta = workspace_delta(base_manifest, final_manifest)
        assert [str(item.relative_path) for item in delta.modified] == ["input.txt"]
        assert [str(item.relative_path) for item in delta.added] == ["new.txt"]
        export_selected_workspace(workspace, exported)
        assert (exported / "new.txt").read_text(encoding="utf-8") == "new"
    finally:
        dispose_workspace(workspace)
    assert not workspace.exists()


def test_dispose_rejects_symlink_target_without_removing_destination(tmp_path: Path) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()
    (destination / "keep.txt").write_text("keep", encoding="utf-8")
    link = tmp_path / "workspace-link"
    link.symlink_to(destination, target_is_directory=True)

    with pytest.raises(ValueError, match="symbolic link"):
        dispose_workspace(link)

    assert link.is_symlink()
    assert (destination / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_fork_rejects_actor_symlink_without_copying_external_bytes(tmp_path: Path) -> None:
    task = _resolved_task(tmp_path)
    first, base_manifest = materialize_base_workspace(task, work_root=tmp_path / "attempts", agent_files={})
    outside = tmp_path / "outside.txt"
    outside.write_text("private", encoding="utf-8")
    (first / "actor-link").symlink_to(outside)
    try:
        with pytest.raises(ValueError, match="symbolic link"):
            fork_attempt_workspace(
                first,
                base_manifest=base_manifest,
                inherited_paths=frozenset(),
                work_root=tmp_path / "attempts",
            )
        assert outside.read_text(encoding="utf-8") == "private"
        assert [path for path in (tmp_path / "attempts").iterdir() if path != first] == []
    finally:
        dispose_workspace(first)


def test_workspace_path_rejects_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    assert resolve_workspace_path(workspace, "/workspace/output.md") == workspace / "output.md"
    with pytest.raises(ValueError, match="inside"):
        resolve_workspace_path(workspace, "../outside.txt")
