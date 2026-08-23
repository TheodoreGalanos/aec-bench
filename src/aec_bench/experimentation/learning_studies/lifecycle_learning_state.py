# ABOUTME: Validates and copies lifecycle Learning Studies learner-state snapshots.
# ABOUTME: Keeps portable memory and feedback separate from lifecycle packages, runs, and verifier evidence.

from __future__ import annotations

import json
import shutil
import stat
from pathlib import Path, PurePosixPath

_STATE_ROOTS = frozenset({"memory", "feedback"})
_MEMORY_SUFFIXES = frozenset({".json", ".md", ".txt"})
_FEEDBACK_SUFFIXES = frozenset({".json"})
_MAX_FILE_BYTES = 1_000_000
_MAX_STATE_BYTES = 4_000_000

type LifecycleLearnerTreeSnapshot = tuple[tuple[str, str, bytes], ...]


def initialise_lifecycle_learner_state(
    root: Path,
    *,
    memory_seed_root: Path | None = None,
) -> None:
    """Create one exact memory/feedback snapshot and copy an optional safe seed."""

    selected = Path(root)
    selected.mkdir(parents=True, exist_ok=False)
    memory = selected / "memory"
    feedback = selected / "feedback"
    memory.mkdir()
    feedback.mkdir()
    try:
        if memory_seed_root is not None:
            seed = Path(memory_seed_root)
            _validate_content_tree(
                seed,
                allowed_suffixes=_MEMORY_SUFFIXES,
                category="learner-state-invalid",
            )
            for source in sorted(seed.iterdir(), key=lambda path: path.name.casefold()):
                destination = memory / source.name
                if source.is_dir():
                    shutil.copytree(source, destination)
                else:
                    shutil.copy2(source, destination)
        validate_lifecycle_learner_state(selected)
    except Exception:
        shutil.rmtree(selected, ignore_errors=True)
        raise


def validate_lifecycle_learner_state(root: Path) -> None:
    """Validate one complete lifecycle learner-state tree without changing it."""

    selected = Path(root)
    _require_directory(selected, category="learner-state-invalid")
    top_level = {path.name: path for path in selected.iterdir()}
    if set(top_level) != _STATE_ROOTS or any(not path.is_dir() for path in top_level.values()):
        raise ValueError("learner-state-invalid: state root must contain only memory/ and feedback/")
    _validate_content_tree(
        selected / "memory",
        allowed_suffixes=_MEMORY_SUFFIXES,
        category="learner-state-invalid",
    )
    _validate_content_tree(
        selected / "feedback",
        allowed_suffixes=_FEEDBACK_SUFFIXES,
        category="learner-state-invalid",
        allow_nested_directories=False,
    )
    total = sum(path.stat().st_size for path in selected.rglob("*") if path.is_file() and not path.is_symlink())
    if total > _MAX_STATE_BYTES:
        raise ValueError(f"learner-state-too-large: state contains {total} bytes")
    _reject_case_collisions(selected)


def copy_lifecycle_learner_state(source: Path, destination: Path) -> None:
    """Copy one validated committed snapshot to a distinct candidate root."""

    validate_lifecycle_learner_state(source)
    target = Path(destination)
    if target.exists() or target.is_symlink():
        raise ValueError(f"arm-isolation-failed: state destination already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(source, target)
        validate_lifecycle_learner_state(target)
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise


def lifecycle_learner_tree_snapshot(root: Path) -> LifecycleLearnerTreeSnapshot:
    """Return an exact directory-and-file snapshot for state-change checks."""

    validate_lifecycle_learner_state(root)
    return _tree_snapshot(Path(root))


def lifecycle_memory_snapshot(root: Path) -> LifecycleLearnerTreeSnapshot:
    """Return the exact memory subtree for consolidation-change checks."""

    validate_lifecycle_learner_state(root)
    return _tree_snapshot(Path(root) / "memory")


def create_read_only_context_projection(
    state_root: Path,
    destination: Path,
) -> LifecycleLearnerTreeSnapshot:
    """Copy only committed memory into one restrictive experience-local context."""

    validate_lifecycle_learner_state(state_root)
    target = Path(destination)
    if target.exists() or target.is_symlink():
        raise ValueError(f"context-projection-failed: context path already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(Path(state_root) / "memory", target)
        _validate_context_tree(target)
        for path in sorted(target.rglob("*"), reverse=True):
            path.chmod(0o500 if path.is_dir() else 0o400)
        target.chmod(0o500)
        return _tree_snapshot(target)
    except Exception as error:
        shutil.rmtree(target, ignore_errors=True)
        if isinstance(error, ValueError) and str(error).startswith("context-"):
            raise
        raise ValueError(f"context-projection-failed: {error}") from error


def validate_read_only_context_projection(
    root: Path,
    expected: LifecycleLearnerTreeSnapshot,
) -> None:
    """Require an experience-local context to retain its exact byte tree."""

    try:
        _validate_context_tree(root)
        actual = _tree_snapshot(Path(root))
    except Exception as error:
        raise ValueError(f"context-readonly-violation: {error}") from error
    if actual != expected:
        raise ValueError("context-readonly-violation: learner_context changed during lifecycle execution")


def _validate_context_tree(root: Path) -> None:
    _validate_content_tree(
        Path(root),
        allowed_suffixes=_MEMORY_SUFFIXES,
        category="context-file-unsupported",
    )
    _reject_case_collisions(Path(root), category="context-path-escape")


def _validate_content_tree(
    root: Path,
    *,
    allowed_suffixes: frozenset[str],
    category: str,
    allow_nested_directories: bool = True,
) -> None:
    selected = Path(root)
    _require_directory(selected, category=category)
    resolved_root = selected.resolve(strict=True)
    seen: set[str] = set()
    total = 0
    for path in sorted(selected.rglob("*"), key=lambda item: item.as_posix().casefold()):
        relative = path.relative_to(selected)
        _validate_relative_path(relative, category=category)
        collision_key = relative.as_posix().casefold()
        if collision_key in seen:
            raise ValueError(f"{category}: case-insensitive path collision: {relative.as_posix()}")
        seen.add(collision_key)
        if path.is_symlink():
            symlink_category = "context-path-escape" if category.startswith("context-") else "learner-symlink-forbidden"
            raise ValueError(f"{symlink_category}: symbolic link: {relative.as_posix()}")
        try:
            metadata = path.stat(follow_symlinks=False)
            resolved = path.resolve(strict=True)
        except OSError as error:
            raise ValueError(f"{category}: unreadable path: {relative.as_posix()}") from error
        if resolved != resolved_root and resolved_root not in resolved.parents:
            escape_category = "context-path-escape" if category.startswith("context-") else "learner-state-invalid"
            raise ValueError(f"{escape_category}: path escapes root: {relative.as_posix()}")
        if stat.S_ISDIR(metadata.st_mode):
            if not allow_nested_directories:
                raise ValueError(f"{category}: nested directory is not allowed: {relative.as_posix()}")
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"{category}: special file: {relative.as_posix()}")
        if metadata.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            raise ValueError(f"learner-file-type-unsupported: executable file: {relative.as_posix()}")
        if path.suffix.lower() not in allowed_suffixes:
            file_category = (
                "context-file-unsupported" if category.startswith("context-") else "learner-file-type-unsupported"
            )
            raise ValueError(f"{file_category}: unsupported file type: {relative.as_posix()}")
        if metadata.st_size > _MAX_FILE_BYTES:
            raise ValueError(f"learner-file-too-large: {relative.as_posix()} contains {metadata.st_size} bytes")
        total += metadata.st_size
        if total > _MAX_STATE_BYTES:
            raise ValueError(f"learner-state-too-large: content root contains {total} bytes")
        _validate_file_content(path, relative, category=category)


def _validate_file_content(path: Path, relative: Path, *, category: str) -> None:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        file_category = (
            "context-file-unsupported" if category.startswith("context-") else "learner-file-type-unsupported"
        )
        raise ValueError(f"{file_category}: file is not readable UTF-8: {relative.as_posix()}") from error
    if path.suffix.lower() != ".json":
        return
    try:
        json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError(f"{category}: invalid JSON file: {relative.as_posix()}") from error


def _require_directory(path: Path, *, category: str) -> None:
    if path.is_symlink():
        symlink_category = "context-path-escape" if category.startswith("context-") else "learner-symlink-forbidden"
        raise ValueError(f"{symlink_category}: root is a symbolic link")
    if not path.is_dir():
        raise ValueError(f"{category}: root is not a directory")
    try:
        path.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"{category}: root is not readable") from error


def _validate_relative_path(path: Path, *, category: str) -> None:
    pure = PurePosixPath(path.as_posix())
    if (
        pure.is_absolute()
        or not pure.parts
        or any(part in {".", ".."} or part.startswith(".") or "\\" in part for part in pure.parts)
    ):
        raise ValueError(f"{category}: unsafe learner path: {pure.as_posix()}")


def _reject_case_collisions(root: Path, *, category: str = "learner-state-invalid") -> None:
    seen: set[str] = set()
    for path in sorted(Path(root).rglob("*"), key=lambda item: item.as_posix().casefold()):
        relative = path.relative_to(root).as_posix()
        key = relative.casefold()
        if key in seen:
            raise ValueError(f"{category}: case-insensitive path collision: {relative}")
        seen.add(key)


def _tree_snapshot(root: Path) -> LifecycleLearnerTreeSnapshot:
    entries: list[tuple[str, str, bytes]] = []
    for path in sorted(Path(root).rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            entries.append((relative, "directory", b""))
        elif path.is_file():
            entries.append((relative, "file", path.read_bytes()))
    return tuple(entries)


__all__ = (
    "LifecycleLearnerTreeSnapshot",
    "copy_lifecycle_learner_state",
    "create_read_only_context_projection",
    "initialise_lifecycle_learner_state",
    "lifecycle_learner_tree_snapshot",
    "lifecycle_memory_snapshot",
    "validate_lifecycle_learner_state",
    "validate_read_only_context_projection",
)
