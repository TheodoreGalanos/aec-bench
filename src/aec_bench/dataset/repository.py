# ABOUTME: Creates and verifies repository-backed dataset references against exact Git trees.
# ABOUTME: Uses one full commit plus manifest path and rejects dirty relevant materialisation.

from __future__ import annotations

import subprocess
from pathlib import Path, PurePosixPath

from aec_bench.contracts.dataset import DatasetManifest, RepositoryDatasetRef
from aec_bench.dataset.integrity import IntegrityResult
from aec_bench.ledger.artifact_repository import canonical_model_bytes


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
        raise ValueError("Git is required for a repository-backed dataset") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(detail or f"Git command failed: {' '.join(args)}") from error


def _repository_root(project_root: Path) -> Path:
    result = _git(project_root, "rev-parse", "--show-toplevel")
    return Path(result.stdout.decode().strip()).resolve()


def _relative_to_repository(path: Path, root: Path, *, label: str) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError(f"{label} must stay inside the Git repository: {path}") from error


def _relevant_paths(manifest: DatasetManifest, manifest_relative: str) -> tuple[str, ...]:
    return (manifest_relative, *(task.path for task in manifest.tasks))


def _ignored_runtime_file(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return "__pycache__" in parts or path.endswith(".pyc")


def _untracked_relevant_paths(root: Path, paths: tuple[str, ...]) -> tuple[str, ...]:
    discovered: set[str] = set()
    for args in (
        ("ls-files", "--others", "--exclude-standard", "--", *paths),
        ("ls-files", "--others", "--ignored", "--exclude-standard", "--", *paths),
    ):
        output = _git(root, *args).stdout.decode("utf-8", errors="strict")
        discovered.update(line for line in output.splitlines() if line and not _ignored_runtime_file(line))
    return tuple(sorted(discovered))


def _require_tracked(root: Path, paths: tuple[str, ...]) -> None:
    for path in paths:
        output = _git(root, "ls-files", "--", path).stdout.decode().strip()
        if not output:
            raise ValueError(f"repository dataset path is not tracked: {path}")


def _git_object(root: Path, revision: str, path: str) -> bytes:
    result = _git(root, "show", f"{revision}:{path}")
    return result.stdout


def _require_task_trees(root: Path, revision: str, manifest: DatasetManifest) -> None:
    for task in manifest.tasks:
        result = _git(root, "cat-file", "-t", f"{revision}:{task.path}", check=False)
        if result.returncode != 0 or result.stdout.strip() != b"tree":
            raise ValueError(f"repository dataset is missing task path at revision: {task.path}")


def repository_dataset_reference(
    *,
    manifest: DatasetManifest,
    manifest_path: Path,
    project_root: Path,
) -> RepositoryDatasetRef:
    """Create a reference only when all relevant bytes are tracked and clean at HEAD."""

    root = _repository_root(project_root)
    manifest_relative = _relative_to_repository(manifest_path, root, label="dataset manifest")
    paths = _relevant_paths(manifest, manifest_relative)
    _require_tracked(root, paths)
    if _untracked_relevant_paths(root, paths):
        raise ValueError("repository dataset has untracked or ignored relevant files")
    if _git(root, "diff", "--quiet", "HEAD", "--", *paths, check=False).returncode != 0:
        raise ValueError("repository dataset requires a clean Git materialisation")

    revision = _git(root, "rev-parse", "HEAD").stdout.decode().strip()
    committed_manifest = _git_object(root, revision, manifest_relative)
    if committed_manifest != canonical_model_bytes(manifest):
        raise ValueError("repository dataset manifest does not match its committed canonical bytes")
    _require_task_trees(root, revision, manifest)
    return RepositoryDatasetRef(
        dataset_id=manifest.dataset_id,
        source_revision=revision,
        manifest_path=manifest_relative,
    )


def load_repository_dataset(reference: RepositoryDatasetRef, *, project_root: Path) -> DatasetManifest:
    """Load and validate the manifest from the referenced Git object, never from local bytes."""

    root = _repository_root(project_root)
    if _git(root, "cat-file", "-e", f"{reference.source_revision}^{{commit}}", check=False).returncode != 0:
        raise ValueError(f"repository dataset commit is unavailable: {reference.source_revision}")
    manifest = DatasetManifest.model_validate_json(
        _git_object(root, reference.source_revision, reference.manifest_path)
    )
    if manifest.dataset_id != reference.dataset_id:
        raise ValueError("repository dataset ID does not match the referenced manifest")
    _require_task_trees(root, reference.source_revision, manifest)
    return manifest


def verify_repository_materialization(
    reference: RepositoryDatasetRef,
    *,
    project_root: Path,
) -> IntegrityResult:
    """Prove that current relevant paths match the reference without a second tree hash."""

    root = _repository_root(project_root)
    manifest = load_repository_dataset(reference, project_root=root)
    paths = _relevant_paths(manifest, reference.manifest_path)
    changed_output = _git(
        root,
        "diff",
        "--name-only",
        reference.source_revision,
        "--",
        *paths,
    ).stdout.decode()
    changed = {line for line in changed_output.splitlines() if line}
    untracked = set(_untracked_relevant_paths(root, paths))

    missing: list[str] = []
    modified: list[str] = []
    unexpected: list[str] = sorted(untracked)
    if reference.manifest_path in changed:
        modified.append("manifest.json")

    verified = 0
    for task in manifest.tasks:
        task_dir = root / task.path
        if not task_dir.is_dir():
            missing.append(task.task_id)
            continue
        has_changed = any(PurePosixPath(path).is_relative_to(PurePosixPath(task.path)) for path in changed | untracked)
        if has_changed:
            modified.append(task.task_id)
        else:
            verified += 1
    return IntegrityResult(
        verified=verified,
        missing=tuple(sorted(missing)),
        modified=tuple(sorted(modified)),
        unexpected=tuple(unexpected),
    )


__all__ = (
    "load_repository_dataset",
    "repository_dataset_reference",
    "verify_repository_materialization",
)
