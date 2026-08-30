# ABOUTME: Tests safe workspace manifests and meaningful delta classification.
# ABOUTME: Proves links and shared file state cannot cross the workspace boundary.

from pathlib import Path

import pytest

from aec_bench.harness.workspace_evidence import (
    WorkspaceSafetyError,
    capture_workspace_manifest,
    compare_workspace_manifests,
)


def test_manifest_and_delta_capture_file_facts_and_changes(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "input.txt").write_text("same", encoding="utf-8")
    (workspace / "changed.txt").write_text("before", encoding="utf-8")
    (workspace / "deleted.txt").write_text("gone", encoding="utf-8")

    base = capture_workspace_manifest(workspace)
    (workspace / "changed.txt").write_text("after", encoding="utf-8")
    (workspace / "deleted.txt").unlink()
    (workspace / "added.txt").write_text("new", encoding="utf-8")
    final = capture_workspace_manifest(workspace, default_source_role="actor_output")
    delta = compare_workspace_manifests(base, final)

    assert [item.relative_path for item in delta.added] == ["added.txt"]
    assert [item.relative_path for item in delta.modified] == ["changed.txt"]
    assert [item.relative_path for item in delta.deleted] == ["deleted.txt"]
    assert [item.relative_path for item in delta.unchanged] == ["input.txt"]
    assert all(item.source_role == "actor_output" for item in final.files)
    assert next(item for item in final.files if item.relative_path == "added.txt").sha256 is not None


def test_manifest_rejects_symbolic_links(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("private", encoding="utf-8")
    (workspace / "escape.txt").symlink_to(outside)

    with pytest.raises(WorkspaceSafetyError, match="symbolic links"):
        capture_workspace_manifest(workspace)


def test_manifest_rejects_shared_file_inodes(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = workspace / "source.txt"
    source.write_text("shared", encoding="utf-8")
    (workspace / "hard-link.txt").hardlink_to(source)

    with pytest.raises(WorkspaceSafetyError, match="shared inode"):
        capture_workspace_manifest(workspace)
