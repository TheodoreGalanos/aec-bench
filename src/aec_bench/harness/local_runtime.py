# ABOUTME: Local workspace setup for running tasks without Docker or Harbor.
# ABOUTME: Handles file copying, path patching, and instruction reading for local execution.

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


def setup_workspace(task_dir: str, *, work_root: str | Path | None = None) -> str:
    """Copy task files into a temp workspace directory.

    Files inside the ``environment/`` subdirectory are copied to the workspace
    root (mirroring the Dockerfile ``COPY`` behaviour) so that tools referenced
    as ``/workspace/<tool>.py`` in the instruction are accessible after
    ``/workspace/`` path patching.

    Returns the workspace path. The caller is responsible for cleanup.
    """
    task_path = Path(task_dir)
    _validate_copy_source(task_path)
    if work_root is not None:
        Path(work_root).mkdir(parents=True, exist_ok=True)
    workspace = tempfile.mkdtemp(prefix="aec-bench-local-", dir=work_root)

    for item in task_path.iterdir():
        if item.is_file():
            _copy_regular_file(item, Path(workspace) / item.name)
        elif item.name == "environment":
            # Flatten environment/workspace/ into workspace root (like Dockerfile COPY workspace/ /workspace/)
            ws_subdir = item / "workspace"
            if ws_subdir.is_dir():
                for ws_item in ws_subdir.rglob("*"):
                    if ws_item.is_file():
                        rel = ws_item.relative_to(ws_subdir)
                        dest = Path(workspace) / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        _copy_regular_file(ws_item, dest)
            # Mirror environment assets at workspace root, matching Docker COPY destinations.
            for env_item in item.iterdir():
                if env_item.name == "workspace":
                    continue
                if env_item.is_file():
                    _copy_regular_file(env_item, Path(workspace) / env_item.name)
                elif env_item.is_dir():
                    shutil.copytree(
                        env_item,
                        Path(workspace) / env_item.name,
                        dirs_exist_ok=True,
                        symlinks=False,
                    )
            # Keep the full directory because task-relative imports can use it.
            shutil.copytree(item, os.path.join(workspace, item.name))
        elif item.is_dir() and item.name not in {"__pycache__", "tests"}:
            shutil.copytree(item, os.path.join(workspace, item.name), dirs_exist_ok=True, symlinks=False)

    return workspace


def stage_verifier_assets(task_dir: str | Path, workspace: str | Path) -> None:
    """Copy private verifier assets into the workspace after agent execution."""
    source = Path(task_dir) / "tests"
    if not source.is_dir():
        return
    workspace_path = Path(workspace)
    if workspace_path.is_symlink() or not workspace_path.is_dir():
        raise ValueError("verifier staging workspace must be a regular directory")
    _validate_copy_source(source)
    destination = workspace_path / "tests"
    if destination.is_symlink():
        raise ValueError("verifier staging destination must not be a symbolic link")
    if destination.exists():
        raise ValueError("verifier staging destination must not already exist")
    shutil.copytree(source, destination, symlinks=False)


def copy_validated_workspace(source: str | Path, destination: str | Path) -> None:
    """Copy a workspace after validating that its tree stays inside its root."""
    source_path = Path(source)
    _validate_copy_source(source_path)
    shutil.copytree(source_path, destination, symlinks=False, dirs_exist_ok=True)


def unstage_verifier_assets(workspace: str | Path) -> None:
    """Remove private verifier assets before another agent turn."""
    destination = Path(workspace) / "tests"
    if destination.is_symlink():
        raise ValueError("verifier staging destination must not be a symbolic link")
    shutil.rmtree(destination, ignore_errors=True)


def cleanup_workspace(workspace: str | Path) -> None:
    """Remove one local workspace created by :func:`setup_workspace`."""

    path = Path(workspace)
    if path.is_symlink():
        raise ValueError("workspace cleanup target must not be a symbolic link")
    if path.exists() and not path.is_dir():
        raise ValueError("workspace cleanup target must be a directory")
    shutil.rmtree(path, ignore_errors=True)


def _validate_copy_source(source: Path) -> None:
    """Reject source links and shared inodes before any full-copy effect."""

    if source.is_symlink() or not source.is_dir():
        raise ValueError("workspace copy source must be a regular directory")
    resolved_source = source.resolve()
    for candidate in sorted(source.rglob("*")):
        information = candidate.lstat()
        if information.st_mode & 0o170000 == 0o120000:
            raise ValueError(f"workspace copy source must not contain a symbolic link: {candidate}")
        if not candidate.resolve().is_relative_to(resolved_source):
            raise ValueError(f"workspace copy source escapes its root: {candidate}")


def _copy_regular_file(source: Path, destination: Path) -> None:
    """Copy one validated regular file without following source links."""

    information = source.lstat()
    if information.st_mode & 0o170000 != 0o100000:
        raise ValueError(f"workspace copy source must be a regular file: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def patch_workspace_paths(workspace: str, *, source_workspace: str | None = None) -> None:
    """Replace /workspace/ references with the actual local temp directory path.

    Generated tasks use /workspace/ as the container mount point. Locally we
    need these to point at the actual temp directory so tools and instructions
    resolve files correctly.
    """
    normalised = workspace.rstrip("/")
    ws_path = Path(workspace)

    replacements = [("/workspace", normalised)]
    if source_workspace is not None:
        replacements.append((source_workspace.rstrip("/"), normalised))

    for py_file in ws_path.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        patched = content
        for source, target in replacements:
            patched = patched.replace(f'"{source}"', f'"{target}"')
            patched = patched.replace(f'"{source}/', f'"{target}/')
        if patched != content:
            py_file.write_text(patched, encoding="utf-8")

    # Patch the instruction so tool paths resolve
    instruction = ws_path / "instruction.md"
    if instruction.exists():
        content = instruction.read_text(encoding="utf-8")
        patched = content
        for source, target in replacements:
            patched = patched.replace(f"{source}/", f"{target}/")
        if patched != content:
            instruction.write_text(
                patched,
                encoding="utf-8",
            )


def read_instruction(workspace: str) -> str:
    """Read the task instruction from the workspace directory."""
    instruction_path = Path(workspace, "instruction.md")
    if instruction_path.exists():
        return instruction_path.read_text()

    skip_names = {"system_prompt.md", "notes.md", "README.md"}
    for md_file in sorted(Path(workspace).glob("*.md")):
        if md_file.name not in skip_names:
            return md_file.read_text()

    return ""
