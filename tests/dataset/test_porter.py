# ABOUTME: Tests deterministic detached dataset bundles and safe immutable import.
# ABOUTME: Covers traversal, links, duplicates, missing tasks, unexpected roots, and digest failure.

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from aec_bench.contracts.dataset import DatasetManifest, DatasetTaskEntry
from aec_bench.dataset.porter import (
    build_dataset_bundle,
    import_dataset,
    publish_dataset_bundle,
    read_dataset_bundle,
    verify_bundle_materialization,
)
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.ledger.immutable_byte_store import ImmutableArtifactIntegrityError


def _task(project_root: Path, relative: str, *, instruction: str = "Solve it") -> None:
    root = project_root / relative
    (root / "tests").mkdir(parents=True)
    (root / "task.toml").write_text('[metadata]\ndifficulty = "medium"\n', encoding="utf-8")
    (root / "instruction.md").write_text(instruction, encoding="utf-8")
    script = root / "tests" / "test.sh"
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)


def _manifest(*paths: str, dataset_id: str = "test-suite") -> DatasetManifest:
    return DatasetManifest(
        dataset_id=dataset_id,
        description="Portable test dataset",
        tasks=[
            DatasetTaskEntry(task_id=path.removeprefix("tasks/"), path=path, task_kind="artifact") for path in paths
        ],
    )


def _custom_archive(entries: list[tuple[tarfile.TarInfo, bytes | None]]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for info, payload in entries:
            archive.addfile(info, io.BytesIO(payload) if payload is not None else None)
    return buffer.getvalue()


def _file(name: str, payload: bytes) -> tuple[tarfile.TarInfo, bytes]:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    return info, payload


def test_bundle_bytes_are_deterministic_and_have_only_declared_content(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    paths = ("tasks/civil/task-b", "tasks/electrical/task-a")
    for path in reversed(paths):
        _task(project_root, path)
    manifest = _manifest(*paths)

    first = build_dataset_bundle(manifest=manifest, project_root=project_root)
    second = build_dataset_bundle(manifest=manifest, project_root=project_root)
    bundle = read_dataset_bundle(first)

    assert first == second
    assert bundle.manifest == manifest
    assert set(bundle.files) == {
        "tasks/civil/task-b/instruction.md",
        "tasks/civil/task-b/task.toml",
        "tasks/civil/task-b/tests/test.sh",
        "tasks/electrical/task-a/instruction.md",
        "tasks/electrical/task-a/task.toml",
        "tasks/electrical/task-a/tests/test.sh",
    }


def test_bundle_creation_fails_when_a_declared_task_is_missing(tmp_path: Path) -> None:
    manifest = _manifest("tasks/civil/missing")

    with pytest.raises(FileNotFoundError, match="declared task directory is missing"):
        build_dataset_bundle(manifest=manifest, project_root=tmp_path)


def test_bundle_creation_rejects_a_symlinked_task_path(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    _task(project_root, "retained/civil/task-a")
    linked = project_root / "tasks/civil/task-a"
    linked.parent.mkdir(parents=True)
    linked.symlink_to(project_root / "retained/civil/task-a", target_is_directory=True)

    with pytest.raises(ValueError, match="must not contain a symlink"):
        build_dataset_bundle(manifest=_manifest("tasks/civil/task-a"), project_root=project_root)


@pytest.mark.parametrize("unsafe_name", ["../escape", "/absolute", "tasks/../../escape", "tasks\\escape"])
def test_bundle_reader_rejects_path_traversal(unsafe_name: str) -> None:
    info, payload = _file(unsafe_name, b"bad")

    with pytest.raises(ValueError, match="portable relative path"):
        read_dataset_bundle(_custom_archive([(info, payload)]))


@pytest.mark.parametrize("member_type", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE])
def test_bundle_reader_rejects_links_and_special_files(member_type: bytes) -> None:
    info = tarfile.TarInfo("tasks/civil/task/link")
    info.type = member_type
    info.linkname = "../../outside"

    with pytest.raises(ValueError, match="regular files"):
        read_dataset_bundle(_custom_archive([(info, None)]))


def test_bundle_reader_rejects_duplicate_paths() -> None:
    first = _file("manifest.json", b"{}")
    second = _file("manifest.json", b"{}")

    with pytest.raises(ValueError, match="duplicate archive path"):
        read_dataset_bundle(_custom_archive([first, second]))


def test_bundle_reader_rejects_unexpected_task_roots(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    _task(project_root, "tasks/civil/declared")
    payload = build_dataset_bundle(manifest=_manifest("tasks/civil/declared"), project_root=project_root)
    bundle = read_dataset_bundle(payload)
    entries = [_file("manifest.json", bundle.manifest_bytes)]
    entries.extend(_file(path, content) for path, content in bundle.files.items())
    entries.append(_file("tasks/civil/undeclared/instruction.md", b"unexpected"))

    with pytest.raises(ValueError, match="undeclared task content"):
        read_dataset_bundle(_custom_archive(entries))


def test_bundle_reader_rejects_absent_declared_tasks(tmp_path: Path) -> None:
    manifest = _manifest("tasks/civil/missing")
    entries = [_file("manifest.json", (manifest.model_dump_json() + "\n").encode())]

    with pytest.raises(ValueError, match="declared task is absent"):
        read_dataset_bundle(_custom_archive(entries))


def test_published_bundle_digest_is_verified_before_read(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    _task(project_root, "tasks/civil/task-a")
    manifest = _manifest("tasks/civil/task-a")
    repository = ArtifactRepository(tmp_path / "artifacts")
    reference = publish_dataset_bundle(manifest=manifest, project_root=project_root, repository=repository)
    stored = repository.root / reference.artifact.artifact_id
    stored.write_bytes(stored.read_bytes() + b"tampered")

    with pytest.raises(ImmutableArtifactIntegrityError):
        repository.read_bytes(reference.artifact)


def test_bundle_materialization_detects_modified_and_unexpected_files(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    _task(project_root, "tasks/civil/task-a")
    bundle = read_dataset_bundle(
        build_dataset_bundle(manifest=_manifest("tasks/civil/task-a"), project_root=project_root)
    )
    assert verify_bundle_materialization(bundle, project_root=project_root).is_clean

    (project_root / "tasks/civil/task-a/instruction.md").write_text("changed", encoding="utf-8")
    (project_root / "tasks/civil/task-a/extra.txt").write_text("extra", encoding="utf-8")
    result = verify_bundle_materialization(bundle, project_root=project_root)

    assert not result.is_clean
    assert result.modified == ("civil/task-a",)
    assert result.unexpected == ("tasks/civil/task-a/extra.txt",)


def test_bundle_materialization_detects_executable_mode_changes(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    _task(project_root, "tasks/civil/task-a")
    bundle = read_dataset_bundle(
        build_dataset_bundle(manifest=_manifest("tasks/civil/task-a"), project_root=project_root)
    )

    (project_root / "tasks/civil/task-a/tests/test.sh").chmod(0o644)

    result = verify_bundle_materialization(bundle, project_root=project_root)
    assert not result.is_clean
    assert result.modified == ("civil/task-a",)


def test_import_is_safe_and_cannot_overwrite_existing_tasks_or_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _task(source, "tasks/civil/task-a")
    archive = tmp_path / "dataset.tar.gz"
    archive.write_bytes(build_dataset_bundle(manifest=_manifest("tasks/civil/task-a"), project_root=source))
    destination = tmp_path / "destination"

    imported = import_dataset(
        archive_path=archive,
        tasks_root=destination / "tasks",
        datasets_root=destination / "datasets",
    )

    assert imported.manifest.dataset_id == "test-suite"
    assert imported.reference.artifact.sha256
    assert (destination / "tasks/civil/task-a/instruction.md").is_file()
    with pytest.raises(FileExistsError, match="already exists"):
        import_dataset(
            archive_path=archive,
            tasks_root=destination / "tasks",
            datasets_root=destination / "datasets",
        )
