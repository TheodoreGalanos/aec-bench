# ABOUTME: Reads confined Harbor evidence files and constructs portable artifact references.
# ABOUTME: Centralizes symlink, regular-file, tree-coverage, and content-identity checks.

from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path
from typing import Any, cast

from aec_bench.contracts.harness_kernel import canonical_json_sha256
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.harness.harbor_importing.contracts import HarborImportError


def normalize_artifact_path(path: Path | None, repo_root: Path) -> str | None:
    """Normalize an artifact path to a portable repository-relative path."""

    if path is None:
        return None
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def artifact_reference(
    *,
    kind: str,
    path: Path,
    repo_root: Path,
) -> ArtifactReference:
    """Build a hash-bound reference to one non-symlink regular file."""

    if path.is_symlink():
        raise HarborImportError(f"{kind} artifact must not be a symbolic link")
    try:
        mode = path.stat(follow_symlinks=False).st_mode
        content = path.read_bytes()
    except OSError as error:
        raise HarborImportError(f"{kind} artifact cannot be read") from error
    if not stat.S_ISREG(mode):
        raise HarborImportError(f"{kind} artifact must be a regular file")
    return ArtifactReference(
        kind=kind,
        path=normalize_artifact_path(path, repo_root) or path.as_posix(),
        sha256=hashlib.sha256(content).hexdigest(),
        media_type=artifact_media_type(path),
    )


def artifact_media_type(path: Path) -> str:
    """Infer the stable media type used by TrialRecord artifact references."""

    if path.suffix == ".json":
        return "application/json"
    if path.suffix == ".jsonl":
        return "application/x-ndjson"
    if path.suffix in {".md", ".txt"}:
        return "text/plain"
    if path.name.endswith(".tar.gz"):
        return "application/gzip"
    return "application/octet-stream"


def read_content_addressed_trial_json(
    path: Path,
    *,
    trial_dir: Path,
    label: str,
) -> tuple[bytes, dict[str, Any]]:
    """Read one confined canonical JSON object and verify its content identity."""

    raw = read_required_trial_file(
        path,
        trial_dir=trial_dir,
        label=label,
    )
    try:
        parsed = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HarborImportError(f"{label} is not valid JSON") from error
    if not isinstance(parsed, dict) or any(not isinstance(key, str) for key in parsed):
        raise HarborImportError(f"{label} must be a JSON object")
    payload = cast(dict[str, Any], parsed)
    content_sha256 = payload.get("content_sha256")
    without_identity = {key: value for key, value in payload.items() if key != "content_sha256"}
    if not isinstance(content_sha256, str) or canonical_json_sha256(without_identity) != content_sha256:
        raise HarborImportError(f"{label} content identity changed")
    return raw, payload


def required_trial_directory(
    path: Path,
    *,
    trial_dir: Path,
    label: str,
) -> Path:
    """Require one real directory confined beneath the Harbor trial root."""

    require_trial_containment(path, trial_dir=trial_dir, label=label)
    if path.is_symlink():
        raise HarborImportError(f"{label} must not be a symbolic link")
    try:
        mode = path.stat(follow_symlinks=False).st_mode
    except OSError as error:
        raise HarborImportError(
            f"{label} is missing or cannot be inspected",
        ) from error
    if not stat.S_ISDIR(mode):
        raise HarborImportError(f"{label} must be a directory")
    return path


def read_required_trial_file(
    path: Path,
    *,
    trial_dir: Path,
    label: str,
) -> bytes:
    """Read one real regular file confined beneath the Harbor trial root."""

    require_trial_containment(path, trial_dir=trial_dir, label=label)
    if path.is_symlink():
        raise HarborImportError(f"{label} must not be a symbolic link")
    try:
        mode = path.stat(follow_symlinks=False).st_mode
    except OSError as error:
        raise HarborImportError(
            f"{label} is missing or cannot be inspected",
        ) from error
    if not stat.S_ISREG(mode):
        raise HarborImportError(f"{label} must be a regular file")
    try:
        return path.read_bytes()
    except OSError as error:
        raise HarborImportError(f"{label} cannot be read") from error


def read_regular_trial_tree(
    root: Path,
    *,
    trial_dir: Path,
    label: str,
) -> dict[Path, bytes]:
    """Read the exact non-empty regular-file tree below a confined directory."""

    directory = required_trial_directory(
        root,
        trial_dir=trial_dir,
        label=label,
    )
    files: dict[Path, bytes] = {}
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory).as_posix()
        if path.is_symlink():
            raise HarborImportError(
                f"{label} contains a symbolic link: {relative}",
            )
        mode = path.stat(follow_symlinks=False).st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise HarborImportError(
                f"{label} contains a non-regular file: {relative}",
            )
        files[path] = path.read_bytes()
    if not files:
        raise HarborImportError(f"{label} contains no evidence files")
    return files


def require_trial_containment(
    path: Path,
    *,
    trial_dir: Path,
    label: str,
) -> None:
    """Reject paths whose resolved identity escapes the Harbor trial root."""

    try:
        path.resolve(strict=False).relative_to(trial_dir.resolve(strict=True))
    except (OSError, RuntimeError, ValueError) as error:
        raise HarborImportError(
            f"{label} escapes the Harbor trial boundary",
        ) from error


__all__ = (
    "artifact_media_type",
    "artifact_reference",
    "normalize_artifact_path",
    "read_content_addressed_trial_json",
    "read_regular_trial_tree",
    "read_required_trial_file",
    "required_trial_directory",
)
