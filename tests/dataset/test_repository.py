# ABOUTME: Tests repository-backed dataset references against exact Git tree material.
# ABOUTME: Ensures clean tracked task bytes replace redundant source-tree hashes.

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aec_bench.contracts.dataset import DatasetManifest, DatasetTaskEntry, RepositoryDatasetRef
from aec_bench.dataset.repository import (
    load_repository_dataset,
    repository_dataset_reference,
    verify_repository_materialization,
)
from aec_bench.ledger.artifact_repository import canonical_model_bytes


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ("git", *args),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _repository(tmp_path: Path) -> tuple[Path, DatasetManifest, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.name", "Dataset Test")
    _git(root, "config", "user.email", "dataset@example.invalid")
    task = root / "tasks" / "civil" / "task-a"
    task.mkdir(parents=True)
    (task / "task.toml").write_text(
        '[identity]\nid = "019c2c7a-5a33-7b8d-a702-8f7f3e8c21aa"\n'
        'key = "civil/task-a"\nversion = 1\n\n'
        '[metadata]\ndifficulty = "medium"\nlifecycle = "active"\nvisibility = "public"\n',
        encoding="utf-8",
    )
    (task / "instruction.md").write_text("Solve it\n", encoding="utf-8")
    manifest = DatasetManifest(
        dataset_id="core",
        description="Core tasks",
        tasks=[DatasetTaskEntry(task_id="civil/task-a", path="tasks/civil/task-a", task_kind="artifact")],
    )
    path = root / "datasets" / "core" / "manifest.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(canonical_model_bytes(manifest))
    _git(root, "add", "datasets/core/manifest.json", "tasks/civil/task-a")
    _git(root, "commit", "-m", "add dataset")
    return root, manifest, path


def test_repository_reference_uses_full_head_and_manifest_path(tmp_path: Path) -> None:
    root, manifest, path = _repository(tmp_path)

    reference = repository_dataset_reference(manifest=manifest, manifest_path=path, project_root=root)

    assert reference.source_revision == _git(root, "rev-parse", "HEAD")
    assert reference.manifest_path == "datasets/core/manifest.json"
    assert load_repository_dataset(reference, project_root=root) == manifest
    assert verify_repository_materialization(reference, project_root=root).is_clean


def test_repository_publication_rejects_dirty_relevant_files(tmp_path: Path) -> None:
    root, manifest, path = _repository(tmp_path)
    (root / "tasks/civil/task-a/instruction.md").write_text("changed\n", encoding="utf-8")

    with pytest.raises(ValueError, match="clean Git materialisation"):
        repository_dataset_reference(manifest=manifest, manifest_path=path, project_root=root)


def test_repository_publication_rejects_untracked_relevant_files(tmp_path: Path) -> None:
    root, manifest, path = _repository(tmp_path)
    (root / "tasks/civil/task-a/extra.txt").write_text("extra\n", encoding="utf-8")

    with pytest.raises(ValueError, match="untracked"):
        repository_dataset_reference(manifest=manifest, manifest_path=path, project_root=root)


def test_repository_reader_uses_committed_manifest_not_dirty_local_bytes(tmp_path: Path) -> None:
    root, manifest, path = _repository(tmp_path)
    reference = repository_dataset_reference(manifest=manifest, manifest_path=path, project_root=root)
    path.write_text("{}\n", encoding="utf-8")

    assert load_repository_dataset(reference, project_root=root) == manifest
    result = verify_repository_materialization(reference, project_root=root)
    assert not result.is_clean
    assert result.modified == ("manifest.json",)


def test_repository_reader_rejects_manifest_with_absent_task_at_revision(tmp_path: Path) -> None:
    root, manifest, path = _repository(tmp_path)
    missing = manifest.model_copy(
        update={"tasks": (DatasetTaskEntry(task_id="civil/missing", path="tasks/civil/missing", task_kind="artifact"),)}
    )
    path.write_bytes(canonical_model_bytes(missing))
    _git(root, "add", "datasets/core/manifest.json")
    _git(root, "commit", "-m", "reference missing task")
    reference = RepositoryDatasetRef(
        dataset_id="core",
        source_revision=_git(root, "rev-parse", "HEAD"),
        manifest_path="datasets/core/manifest.json",
    )

    with pytest.raises(ValueError, match="missing task path"):
        load_repository_dataset(reference, project_root=root)
