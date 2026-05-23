# ABOUTME: CLI command to generate Dockerfiles from task.toml extension declarations.
# ABOUTME: Scans tasks/ directory and regenerates Dockerfiles for tasks with extensions.

from __future__ import annotations

import tomllib
from pathlib import Path

import typer

from aec_bench.cli.output import console, print_success
from aec_bench.images.extensions import generate_dockerfile

GENERATED_MARKER = "# ABOUTME: Auto-generated container"


def generate_dockerfiles_command(
    tasks_dir: Path = typer.Argument(Path("tasks"), help="Root tasks directory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be generated without writing"),
) -> None:
    """Generate Dockerfiles for tasks that declare extensions in task.toml."""
    task_tomls = sorted(tasks_dir.rglob("task.toml"))
    generated = 0
    skipped = 0

    for task_toml_path in task_tomls:
        instance_dir = task_toml_path.parent
        env_dir = instance_dir / "environment"
        dockerfile_path = env_dir / "Dockerfile"

        try:
            raw = tomllib.loads(task_toml_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        env_section = raw.get("environment", {})
        extensions = env_section.get("extensions", [])

        if not extensions:
            # No extensions declared — skip (keep existing Dockerfile)
            skipped += 1
            continue

        # Check if existing Dockerfile is custom (not auto-generated)
        if dockerfile_path.exists():
            content = dockerfile_path.read_text(encoding="utf-8")
            if GENERATED_MARKER not in content and not dry_run:
                # First migration — backup the original
                backup = dockerfile_path.with_suffix(".bak")
                if not backup.exists():
                    backup.write_text(content, encoding="utf-8")

        # Detect extra files in the environment dir (exclude Dockerfile and backups)
        copy_files: list[str] = []
        if env_dir.is_dir():
            for entry in sorted(env_dir.iterdir()):
                if entry.is_file() and entry.name not in {"Dockerfile", "Dockerfile.bak"}:
                    copy_files.append(entry.name)

        # Derive task description from path
        rel = instance_dir.relative_to(tasks_dir)
        task_desc = str(rel).replace("/", " — ")

        dockerfile_content = generate_dockerfile(extensions, task_description=task_desc, copy_files=copy_files)

        if dry_run:
            console.print(f"Would generate: {dockerfile_path}")
            console.print(f"  Extensions: {extensions}")
            if copy_files:
                console.print(f"  Copy files: {copy_files}")
        else:
            env_dir.mkdir(parents=True, exist_ok=True)
            dockerfile_path.write_text(dockerfile_content, encoding="utf-8")
            generated += 1

    if dry_run:
        total = generated + skipped
        console.print(f"\nDry run: {total} tasks scanned")
    else:
        print_success(f"Generated: {generated}, Skipped (no extensions): {skipped}")
