# ABOUTME: Builds content-addressed snapshots for exact runnable task packages.
# ABOUTME: Rejects drift, traversal, and symlinks before a task can enter a RunBundle.

from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path

import yaml

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.run_bundle import TaskSnapshotRef, WorldSnapshotRef
from aec_bench.contracts.stage_execution import declared_stage_graph_from_payload
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.evaluation.task_world import TASK_WORLD_SIDECARS, load_task_world_profile
from aec_bench.meta_harness.declared_task_surface import project_declared_task_surface
from aec_bench.tasks.loader import load_task_definition
from aec_bench.tasks.registry import TaskRegistry

_IGNORED_NAMES = frozenset({".DS_Store"})
_IGNORED_DIRECTORIES = frozenset({"__pycache__", ".pytest_cache"})


class TaskSnapshotError(ValueError):
    """Raised when a task cannot be safely bound to exact runnable bytes."""


def build_task_snapshot(*, task: TaskDefinition, tasks_root: Path) -> TaskSnapshotRef:
    """Bind one validated task definition to its complete runnable package."""
    root = Path(tasks_root).resolve()
    task_dir = (root / task.task_id).resolve()
    if not task_dir.is_relative_to(root):
        raise TaskSnapshotError(f"task ref escapes the tasks root: {task.task_id}")
    if not task_dir.is_dir():
        raise TaskSnapshotError(f"task package does not exist: {task.task_id}")

    reloaded = load_task_definition(task_dir, root)
    if reloaded != task:
        raise TaskSnapshotError(f"task definition changed before snapshot: {task.task_id}")

    return TaskSnapshotRef(
        task_id=task.task_id,
        definition_sha256=canonical_content_sha256(task.model_dump(mode="json")),
        package_sha256=_task_package_sha256(task_dir),
        world=_task_world_snapshot(task=task, task_dir=task_dir),
    )


def graph_hidden_task_snapshot_sha256(snapshot: TaskSnapshotRef) -> str:
    """Identify an exact public task package only when no task world is present."""
    if snapshot.world is not None:
        raise TaskSnapshotError("graph-hidden task snapshot cannot contain a task world")
    return canonical_content_sha256(
        {
            "task_id": snapshot.task_id,
            "definition_sha256": snapshot.definition_sha256,
            "package_sha256": snapshot.package_sha256,
        }
    )


def resolve_task_snapshots(*, task_refs: tuple[str, ...], tasks_root: Path) -> tuple[TaskSnapshotRef, ...]:
    """Resolve exact task refs in caller order and bind every runnable package."""
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
    return tuple(build_task_snapshot(task=by_id[task_ref], tasks_root=root) for task_ref in task_refs)


def _task_package_sha256(task_dir: Path) -> str:
    digest = hashlib.sha256(b"aec-bench-task-package-v1\0")
    for path in sorted(task_dir.rglob("*"), key=lambda candidate: candidate.relative_to(task_dir).as_posix()):
        relative = path.relative_to(task_dir)
        if _ignored(relative):
            continue
        if path.is_symlink():
            raise TaskSnapshotError(f"task packages cannot contain symbolic links: {relative.as_posix()}")
        if not path.is_file():
            continue
        mode = stat.S_IMODE(path.stat(follow_symlinks=False).st_mode)
        _update_field(digest, relative.as_posix().encode("utf-8"))
        _update_field(digest, f"{mode:o}".encode("ascii"))
        _update_field(digest, path.read_bytes())
    return digest.hexdigest()


def _task_world_snapshot(*, task: TaskDefinition, task_dir: Path) -> WorldSnapshotRef | None:
    sidecar = next((task_dir / name for name in TASK_WORLD_SIDECARS if (task_dir / name).is_file()), None)
    if sidecar is None:
        return None
    profile = load_task_world_profile(task_dir)
    if profile is None:
        raise TaskSnapshotError(f"task-world sidecar could not be resolved: {task.task_id}")
    topology = project_declared_task_surface(task=task, task_dir=task_dir).model_dump(mode="json")
    world_package_sha256 = hashlib.sha256(sidecar.read_bytes()).hexdigest()
    try:
        stage_graph = declared_stage_graph_from_payload(
            task_id=task.task_id,
            world_package_sha256=world_package_sha256,
            payload=_read_sidecar_payload(sidecar),
        )
    except ValueError as error:
        raise TaskSnapshotError(f"invalid declared stage graph for {task.task_id}: {error}") from error
    return WorldSnapshotRef(
        world_id=profile.world_id,
        world_envelope_sha256=canonical_content_sha256(profile.model_dump(mode="json", exclude_none=True)),
        world_package_sha256=world_package_sha256,
        topology_signature_sha256=canonical_content_sha256(topology),
        visibility=task.visibility,
        stage_graph=stage_graph,
    )


def _read_sidecar_payload(sidecar: Path) -> dict[str, object]:
    if sidecar.suffix == ".json":
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    else:
        payload = yaml.safe_load(sidecar.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("task-world sidecar must contain a mapping")
    return payload


def _ignored(relative: Path) -> bool:
    return relative.name in _IGNORED_NAMES or any(part in _IGNORED_DIRECTORIES for part in relative.parts)


def _update_field(digest: hashlib._Hash, value: bytes) -> None:
    digest.update(len(value).to_bytes(8, byteorder="big", signed=False))
    digest.update(value)
