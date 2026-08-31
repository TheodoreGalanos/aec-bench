# ABOUTME: Owns filesystem operations for isolated artifact-task workspaces.
# ABOUTME: Keeps materialization, forking, snapshots, deltas, export, and disposal in one boundary.

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Literal

from aec_bench.harness.local_runtime import (
    cleanup_workspace,
    copy_validated_workspace,
    patch_workspace_paths,
    setup_workspace,
)
from aec_bench.harness.workspace_evidence import (
    WorkspaceDelta,
    WorkspaceManifest,
    capture_workspace_manifest,
    compare_workspace_manifests,
)
from aec_bench.tasks.instance import ResolvedTaskInstance

WorkspaceSourceRole = Literal["task_input", "primary_output", "actor_output"]


def resolve_workspace_path(workspace: Path, configured_path: str) -> Path:
    """Resolve one configured artifact path below its attempt workspace."""
    path = Path(configured_path)
    if path.parts and path.parts[0] == "workspace":
        path = Path(*path.parts[1:])
    elif path.is_absolute() and path.parts[:2] == ("/", "workspace"):
        path = Path(*path.parts[2:])
    elif path.is_absolute() and path.parts[:2] == ("/", "logs"):
        path = Path(*path.parts[1:])
    elif path.is_absolute():
        raise ValueError("task output path must resolve inside the attempt workspace")
    candidate = (workspace / path).resolve()
    if candidate != workspace.resolve() and workspace.resolve() not in candidate.parents:
        raise ValueError("task output path must resolve inside the attempt workspace")
    return candidate


def materialize_base_workspace(
    task: ResolvedTaskInstance,
    *,
    work_root: Path | None,
    agent_files: dict[str, Path],
) -> tuple[Path, WorkspaceManifest]:
    """Copy one task instance into a fresh actor-visible workspace."""
    if work_root is not None:
        work_root.mkdir(parents=True, exist_ok=True)
    capture_workspace_manifest(task.instance_dir, include_checksums=False)
    workspace = Path(setup_workspace(str(task.instance_dir), work_root=work_root)).resolve()
    for logical_path, source in agent_files.items():
        destination = resolve_workspace_path(workspace, logical_path)
        if source.is_symlink():
            raise ValueError(f"agent configuration file must not be a symbolic link: {source}")
        if not source.is_file():
            raise FileNotFoundError(f"agent configuration file is missing: {source}")
        if source.stat().st_nlink != 1:
            raise ValueError(f"agent configuration file must not have shared inode state: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    patch_workspace_paths(str(workspace))
    return workspace, capture_workspace_manifest(workspace)


def fork_attempt_workspace(
    parent_workspace: Path,
    *,
    base_manifest: WorkspaceManifest,
    inherited_paths: frozenset[str],
    work_root: Path | None,
) -> tuple[Path, WorkspaceManifest, frozenset[str]]:
    """Copy one attempt workspace without sharing mutable task or actor files."""
    parent_snapshot = capture_workspace_manifest(parent_workspace)
    parent_delta = compare_workspace_manifests(base_manifest, parent_snapshot)
    parent_roles: dict[str, WorkspaceSourceRole] = {
        str(item.relative_path): item.source_role for item in base_manifest.files
    }
    parent_roles.update({str(item.relative_path): "actor_output" for item in parent_delta.changed_files})
    parent_manifest = capture_workspace_manifest(
        parent_workspace,
        source_roles=parent_roles,
        default_source_role="actor_output",
    )
    workspace = Path(tempfile.mkdtemp(prefix="aec-bench-local-", dir=work_root)).resolve()
    try:
        copy_validated_workspace(parent_workspace, workspace)
    except Exception:
        cleanup_workspace(workspace)
        raise
    shutil.rmtree(workspace / "tests", ignore_errors=True)
    shutil.rmtree(workspace / "logs" / "verifier", ignore_errors=True)
    patch_workspace_paths(str(workspace), source_workspace=str(parent_workspace))
    child_manifest = capture_workspace_manifest(
        workspace,
        source_roles=parent_roles,
        default_source_role="actor_output",
    )
    retained_paths = inherited_paths | {str(item.relative_path) for item in parent_delta.changed_files}
    child_inherited = frozenset(
        str(item.relative_path)
        for item in child_manifest.files
        if item.source_role in {"actor_output", "primary_output"}
        and any(parent_item.relative_path == item.relative_path for parent_item in parent_manifest.files)
        and str(item.relative_path) in retained_paths
    )
    return workspace, child_manifest, child_inherited


def export_selected_workspace(snapshot: Path, destination: Path) -> None:
    """Atomically export the selected actor snapshot before verification changes it."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if not destination.is_dir() or any(destination.iterdir()):
            raise ValueError(f"selected workspace export destination must be empty: {destination}")
        destination.rmdir()
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        shutil.copytree(snapshot, staging, dirs_exist_ok=True)
        os.replace(staging, destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def capture_final_workspace_manifest(
    workspace: Path,
    base_manifest: WorkspaceManifest,
    primary_output_path: str,
) -> WorkspaceManifest:
    """Capture final workspace facts while preserving task and actor roles."""
    roles: dict[str, WorkspaceSourceRole] = {str(item.relative_path): item.source_role for item in base_manifest.files}
    primary_relative = resolve_workspace_path(workspace, primary_output_path).relative_to(workspace).as_posix()
    roles[primary_relative] = "primary_output"
    return capture_workspace_manifest(
        workspace,
        source_roles=roles,
        default_source_role="actor_output",
        bytes_copied=0,
    )


def workspace_delta(base_manifest: WorkspaceManifest, final_manifest: WorkspaceManifest) -> WorkspaceDelta:
    """Return exact added, modified, deleted, and unchanged workspace paths."""
    return compare_workspace_manifests(base_manifest, final_manifest)


def dispose_workspace(workspace: Path) -> None:
    """Remove one temporary workspace and all of its child state."""
    cleanup_workspace(workspace)


__all__ = (
    "WorkspaceSourceRole",
    "capture_final_workspace_manifest",
    "dispose_workspace",
    "export_selected_workspace",
    "fork_attempt_workspace",
    "materialize_base_workspace",
    "resolve_workspace_path",
    "workspace_delta",
)
