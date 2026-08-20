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
    workspace = tempfile.mkdtemp(prefix="aec-bench-local-", dir=work_root)
    task_path = Path(task_dir)

    for item in task_path.iterdir():
        if item.is_file():
            shutil.copy2(item, workspace)
        elif item.name == "environment":
            # Flatten environment/workspace/ into workspace root (like Dockerfile COPY workspace/ /workspace/)
            ws_subdir = item / "workspace"
            if ws_subdir.is_dir():
                for ws_item in ws_subdir.rglob("*"):
                    if ws_item.is_file():
                        rel = ws_item.relative_to(ws_subdir)
                        dest = Path(workspace) / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(ws_item, dest)
            # Mirror environment assets at workspace root, matching Docker COPY destinations.
            for env_item in item.iterdir():
                if env_item.name == "workspace":
                    continue
                if env_item.is_file():
                    shutil.copy2(env_item, workspace)
                elif env_item.is_dir():
                    shutil.copytree(
                        env_item,
                        Path(workspace) / env_item.name,
                        dirs_exist_ok=True,
                    )
            # Keep the full directory because task-relative imports can use it.
            shutil.copytree(item, os.path.join(workspace, item.name))
        elif item.is_dir() and item.name not in {"__pycache__", "tests"}:
            shutil.copytree(item, os.path.join(workspace, item.name), dirs_exist_ok=True)

    return workspace


def stage_verifier_assets(task_dir: str | Path, workspace: str | Path) -> None:
    """Copy private verifier assets into the workspace after agent execution."""
    source = Path(task_dir) / "tests"
    if not source.is_dir():
        return
    shutil.copytree(source, Path(workspace) / "tests", dirs_exist_ok=True)


def unstage_verifier_assets(workspace: str | Path) -> None:
    """Remove private verifier assets before another agent turn."""
    shutil.rmtree(Path(workspace) / "tests", ignore_errors=True)


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
