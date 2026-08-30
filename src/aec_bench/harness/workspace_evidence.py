# ABOUTME: Captures safe current-format manifests of actor-visible workspaces.
# ABOUTME: Records portable paths and file facts without making workspace contents task semantics.

from __future__ import annotations

import hashlib
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, NonNegativeInt, field_validator

from aec_bench.contracts.identity import PortableRelativePath
from aec_bench.contracts.validators import StrictModel

type WorkspaceFileType = Literal["file", "directory"]
type WorkspaceSourceRole = Literal["task_input", "primary_output", "actor_output"]


class WorkspaceSafetyError(ValueError):
    """Raised when a workspace cannot be captured without unsafe filesystem assumptions."""


class WorkspaceFile(StrictModel):
    """Facts for one actor-visible workspace path."""

    relative_path: PortableRelativePath
    file_type: WorkspaceFileType
    size_bytes: NonNegativeInt
    mode: int = Field(strict=True, ge=0, le=0o777)
    sha256: str | None = None
    source_role: WorkspaceSourceRole

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str | None) -> str | None:
        if value is not None and (len(value) != 64 or any(character not in "0123456789abcdef" for character in value)):
            raise ValueError("workspace sha256 must contain 64 lowercase hexadecimal characters")
        return value


class WorkspaceManifest(StrictModel):
    """One current-format snapshot of an isolated actor workspace."""

    schema_version: Literal[1] = 1
    strategy: Literal["full_copy"]
    captured_at: datetime
    files_traversed: NonNegativeInt
    bytes_copied: NonNegativeInt
    bytes_attached: NonNegativeInt
    files: tuple[WorkspaceFile, ...] = ()

    @field_validator("captured_at")
    @classmethod
    def validate_captured_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("workspace manifest captured_at must include a timezone")
        return value

    @field_validator("files")
    @classmethod
    def validate_unique_files(cls, value: tuple[WorkspaceFile, ...]) -> tuple[WorkspaceFile, ...]:
        paths = [item.relative_path for item in value]
        if paths != sorted(paths):
            raise ValueError("workspace manifest files must be sorted by relative_path")
        if len(paths) != len(set(paths)):
            raise ValueError("workspace manifest files must have unique relative paths")
        return value


def capture_workspace_manifest(
    workspace: Path,
    *,
    source_roles: dict[str, WorkspaceSourceRole] | None = None,
    default_source_role: WorkspaceSourceRole = "task_input",
    include_checksums: bool = True,
    strategy: Literal["full_copy"] = "full_copy",
    bytes_copied: int | None = None,
    bytes_attached: int = 0,
) -> WorkspaceManifest:
    """Capture one safe manifest without following links or shared file inodes."""

    root = Path(workspace)
    if root.is_symlink() or not root.is_dir():
        raise WorkspaceSafetyError("workspace root must be a regular directory")
    resolved_root = root.resolve()
    roles = source_roles or {}
    entries: list[WorkspaceFile] = []
    for candidate in sorted(root.rglob("*")):
        relative = candidate.relative_to(root).as_posix()
        try:
            relative_path = PortableRelativePath(relative)
        except ValueError as error:
            raise WorkspaceSafetyError(f"workspace path is not portable: {relative}") from error
        try:
            information = candidate.lstat()
        except OSError as error:
            raise WorkspaceSafetyError(f"workspace path cannot be inspected: {relative}") from error
        if stat.S_ISLNK(information.st_mode):
            raise WorkspaceSafetyError(f"workspace must not contain symbolic links: {relative}")
        if not candidate.resolve().is_relative_to(resolved_root):
            raise WorkspaceSafetyError(f"workspace path escapes its root: {relative}")
        is_file = stat.S_ISREG(information.st_mode)
        is_directory = stat.S_ISDIR(information.st_mode)
        if not (is_file or is_directory):
            raise WorkspaceSafetyError(f"workspace path has unsupported file type: {relative}")
        if is_file and information.st_nlink != 1:
            raise WorkspaceSafetyError(f"workspace path has shared inode state: {relative}")
        digest = _sha256(candidate) if is_file and include_checksums else None
        entries.append(
            WorkspaceFile(
                relative_path=relative_path,
                file_type="file" if is_file else "directory",
                size_bytes=information.st_size if is_file else 0,
                mode=stat.S_IMODE(information.st_mode),
                sha256=digest,
                source_role=roles.get(relative, default_source_role),
            )
        )
    file_entries = tuple(entries)
    copied_bytes = sum(item.size_bytes for item in file_entries if item.file_type == "file")
    return WorkspaceManifest(
        strategy=strategy,
        captured_at=datetime.now(UTC),
        files_traversed=sum(item.file_type == "file" for item in file_entries),
        bytes_copied=copied_bytes if bytes_copied is None else bytes_copied,
        bytes_attached=bytes_attached,
        files=file_entries,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class WorkspaceDelta(StrictModel):
    """The exact file changes between actor workspace states."""

    schema_version: Literal[1] = 1
    added: tuple[WorkspaceFile, ...] = ()
    modified: tuple[WorkspaceFile, ...] = ()
    deleted: tuple[WorkspaceFile, ...] = ()
    unchanged: tuple[WorkspaceFile, ...] = ()

    @property
    def changed_files(self) -> tuple[WorkspaceFile, ...]:
        return self.added + self.modified

    @property
    def deleted_paths(self) -> tuple[PortableRelativePath, ...]:
        return tuple(item.relative_path for item in self.deleted)


def compare_workspace_manifests(base: WorkspaceManifest, final: WorkspaceManifest) -> WorkspaceDelta:
    """Classify every path without reading files outside either manifest."""

    base_by_path = {item.relative_path: item for item in base.files}
    final_by_path = {item.relative_path: item for item in final.files}
    added: list[WorkspaceFile] = []
    modified: list[WorkspaceFile] = []
    deleted: list[WorkspaceFile] = []
    unchanged: list[WorkspaceFile] = []
    for path in sorted(set(base_by_path) | set(final_by_path)):
        before = base_by_path.get(path)
        after = final_by_path.get(path)
        if before is None:
            assert after is not None
            added.append(after)
        elif after is None:
            deleted.append(before)
        elif _same_file_facts(before, after):
            unchanged.append(after)
        else:
            modified.append(after)
    return WorkspaceDelta(
        added=tuple(added),
        modified=tuple(modified),
        deleted=tuple(deleted),
        unchanged=tuple(unchanged),
    )


def _same_file_facts(before: WorkspaceFile, after: WorkspaceFile) -> bool:
    """Compare filesystem facts while allowing a final source-role label."""

    return before.model_dump(exclude={"source_role"}) == after.model_dump(exclude={"source_role"})


__all__ = (
    "WorkspaceFile",
    "WorkspaceFileType",
    "WorkspaceDelta",
    "WorkspaceManifest",
    "WorkspaceSafetyError",
    "WorkspaceSourceRole",
    "capture_workspace_manifest",
    "compare_workspace_manifests",
)
