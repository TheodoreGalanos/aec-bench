# ABOUTME: Resolves runnable tasks to one exact Git or detached-artifact reference.
# ABOUTME: Keeps derived review data separate and rejects dirty, untracked, unsafe, or drifting task sources.

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from aec_bench.contracts.stage_execution import declared_stage_graph_from_payload
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.contracts.task_review_snapshot import ReviewSnapshot, TaskReviewSnapshot
from aec_bench.contracts.task_snapshot import ArtifactTaskSnapshotRef, RepositoryTaskSnapshotRef, TaskSnapshotRef
from aec_bench.evaluation.task_review import TASK_REVIEW_SIDECARS, load_task_review_profile
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.tasks.loader import load_task_definition
from aec_bench.tasks.registry import TaskRegistry
from aec_bench.tasks.snapshot import TASK_SNAPSHOT_MEDIA_TYPE, build_task_snapshot_archive


class TaskSnapshotError(ValueError):
    """Raised when a task cannot be safely bound to exact runnable bytes."""


@dataclass(frozen=True)
class ResolvedTaskMaterial:
    """Exact task references and their one optional embedded review value."""

    references: tuple[TaskSnapshotRef, ...]
    review: ReviewSnapshot | None


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ("git", *args),
            cwd=root,
            check=check,
            capture_output=True,
            timeout=10,
        )
    except FileNotFoundError as error:
        raise TaskSnapshotError("Git is required for a repository task snapshot") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode("utf-8", errors="replace").strip()
        raise TaskSnapshotError(detail or f"Git command failed: {' '.join(args)}") from error


def _repository_reference(*, task: TaskDefinition, task_dir: Path) -> RepositoryTaskSnapshotRef:
    root_output = _git(task_dir, "rev-parse", "--show-toplevel").stdout.decode().strip()
    repository_root = Path(root_output).resolve()
    try:
        task_path = task_dir.relative_to(repository_root).as_posix()
    except ValueError as error:
        raise TaskSnapshotError(f"task path is outside its Git repository: {task.task_id}") from error

    tracked = _git(repository_root, "ls-files", "--", task_path).stdout.decode().splitlines()
    if not tracked:
        raise TaskSnapshotError(f"repository task path is not tracked: {task_path}")
    untracked = (
        _git(
            repository_root,
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            task_path,
        )
        .stdout.decode()
        .splitlines()
    )
    if any(not _ignored_runtime_path(path) for path in untracked):
        raise TaskSnapshotError(f"repository task has untracked files: {task.task_id}")
    if _git(repository_root, "diff", "--quiet", "HEAD", "--", task_path, check=False).returncode != 0:
        raise TaskSnapshotError(f"repository task requires a clean Git materialisation: {task.task_id}")

    revision = _git(repository_root, "rev-parse", "HEAD").stdout.decode().strip()
    tree = _git(repository_root, "cat-file", "-t", f"{revision}:{task_path}", check=False)
    if tree.returncode != 0 or tree.stdout.strip() != b"tree":
        raise TaskSnapshotError(f"repository task is absent at revision: {task.task_id}")
    return RepositoryTaskSnapshotRef(
        task_id=task.task_id,
        source_revision=revision,
        task_path=task_path,
    )


def _ignored_runtime_path(value: str) -> bool:
    parts = value.split("/")
    return "__pycache__" in parts or ".pytest_cache" in parts or value.endswith(".pyc")


def build_task_snapshot(
    *,
    task: TaskDefinition,
    tasks_root: Path,
    artifact_repository: ArtifactRepository | None = None,
) -> TaskSnapshotRef:
    """Bind one validated task to Git, or publish one detached task archive."""

    root = Path(tasks_root).resolve()
    task_dir = (root / task.task_id).resolve()
    if not task_dir.is_relative_to(root):
        raise TaskSnapshotError(f"task ref escapes the tasks root: {task.task_id}")
    if not task_dir.is_dir():
        raise TaskSnapshotError(f"task package does not exist: {task.task_id}")

    reloaded = load_task_definition(task_dir, root)
    if reloaded != task:
        raise TaskSnapshotError(f"task definition changed before snapshot: {task.task_id}")

    try:
        return _repository_reference(task=task, task_dir=task_dir)
    except TaskSnapshotError:
        repository = artifact_repository or ArtifactRepository(root.parent / "artefacts" / "task-snapshots")
    artifact = repository.publish_bytes(
        data=build_task_snapshot_archive(task_dir),
        media_type=TASK_SNAPSHOT_MEDIA_TYPE,
    )
    return ArtifactTaskSnapshotRef(task_id=task.task_id, artifact=artifact)


def assert_task_snapshot_matches_directory(*, reference: TaskSnapshotRef, task_dir: Path) -> None:
    """Reject a materialized task directory that differs from its one exact reference."""

    selected_dir = Path(task_dir).resolve()
    if isinstance(reference, ArtifactTaskSnapshotRef):
        archive = build_task_snapshot_archive(selected_dir)
        if (
            reference.artifact.media_type != TASK_SNAPSHOT_MEDIA_TYPE
            or reference.artifact.size_bytes != len(archive)
            or reference.artifact.sha256 != hashlib.sha256(archive).hexdigest()
        ):
            raise TaskSnapshotError("task directory differs from its detached artifact reference")
        return

    tasks_root = selected_dir
    for _part in Path(reference.task_id).parts:
        tasks_root = tasks_root.parent
    task = load_task_definition(selected_dir, tasks_root)
    if _repository_reference(task=task, task_dir=selected_dir) != reference:
        raise TaskSnapshotError("task directory differs from its repository reference")


def resolve_task_material(
    *,
    task_refs: tuple[str, ...],
    tasks_root: Path,
    artifact_repository: ArtifactRepository | None = None,
) -> ResolvedTaskMaterial:
    """Resolve task references in caller order with one separated review value."""

    if not task_refs:
        raise TaskSnapshotError("at least one task ref is required")
    if len(task_refs) != len(set(task_refs)):
        raise TaskSnapshotError("task refs must be unique")

    root = Path(tasks_root).resolve()
    registry = TaskRegistry(tasks_root=root)
    registry.reload()
    by_id = {task.task_id: task for task in registry.all()}
    unknown = tuple(task_ref for task_ref in task_refs if task_ref not in by_id)
    if unknown:
        raise TaskSnapshotError("unknown task refs: " + ", ".join(unknown))

    references: list[TaskSnapshotRef] = []
    reviews: list[TaskReviewSnapshot] = []
    for task_ref in task_refs:
        task = by_id[task_ref]
        task_dir = root / task.task_id
        references.append(
            build_task_snapshot(
                task=task,
                tasks_root=root,
                artifact_repository=artifact_repository,
            )
        )
        review = _task_review_snapshot(task=task, task_dir=task_dir)
        if review is not None:
            reviews.append(review)
    return ResolvedTaskMaterial(
        references=tuple(references),
        review=ReviewSnapshot(tasks=tuple(reviews)) if reviews else None,
    )


def resolve_task_snapshots(
    *,
    task_refs: tuple[str, ...],
    tasks_root: Path,
    artifact_repository: ArtifactRepository | None = None,
) -> tuple[TaskSnapshotRef, ...]:
    """Resolve only the authoritative task references for a caller that does not need review data."""

    return resolve_task_material(
        task_refs=task_refs,
        tasks_root=tasks_root,
        artifact_repository=artifact_repository,
    ).references


def _task_review_snapshot(*, task: TaskDefinition, task_dir: Path) -> TaskReviewSnapshot | None:
    sidecar = next((task_dir / name for name in TASK_REVIEW_SIDECARS if (task_dir / name).is_file()), None)
    if sidecar is None:
        return None
    profile = load_task_review_profile(task_dir)
    if profile is None:
        raise TaskSnapshotError(f"task-review sidecar could not be resolved: {task.task_id}")
    try:
        stage_graph = declared_stage_graph_from_payload(
            task_id=task.task_id,
            review_profile_id=profile.profile_id,
            payload=_read_sidecar_payload(sidecar),
        )
    except ValueError as error:
        raise TaskSnapshotError(f"invalid declared stage graph for {task.task_id}: {error}") from error
    return TaskReviewSnapshot(
        task_id=task.task_id,
        profile_id=profile.profile_id,
        visibility=task.visibility,
        stage_graph=stage_graph,
    )


def _read_sidecar_payload(sidecar: Path) -> dict[str, object]:
    if sidecar.suffix == ".json":
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    else:
        payload = yaml.safe_load(sidecar.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("task-review sidecar must contain a mapping")
    return payload


__all__ = (
    "ResolvedTaskMaterial",
    "TaskSnapshotError",
    "assert_task_snapshot_matches_directory",
    "build_task_snapshot",
    "resolve_task_material",
    "resolve_task_snapshots",
)
