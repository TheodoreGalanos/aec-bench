# ABOUTME: Export and import dataset archives for portable benchmark sharing.
# ABOUTME: Bundles manifest + task directories into tar.gz; unpacks with integrity verification.

from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

from aec_bench.contracts.dataset import DatasetManifest
from aec_bench.dataset.hashing import hash_task_directory
from aec_bench.dataset.storage import write_manifest


def export_dataset(
    *,
    manifest: DatasetManifest,
    project_root: Path,
    output_path: Path,
) -> None:
    """Bundle a dataset manifest and its tasks into a portable tar.gz archive.

    Creates output_path's parent directories as needed. Task directories that
    don't exist on disk are silently skipped.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    readme = _generate_readme(manifest)

    with tarfile.open(output_path, "w:gz") as tar:
        _add_string_to_tar(tar, "manifest.json", manifest.model_dump_json(indent=2))
        _add_string_to_tar(tar, "README.md", readme)

        for task in manifest.tasks:
            task_dir = project_root / task.task_path
            if task_dir.exists():
                tar.add(str(task_dir), arcname=task.task_path)


def import_dataset(
    *,
    archive_path: Path,
    tasks_root: Path,
    datasets_root: Path,
) -> DatasetManifest:
    """Import a dataset archive — unpack tasks and register manifest.

    Extracts task directories relative to tasks_root.parent so that paths
    like ``tasks/electrical/voltage-drop/instance-0`` land at
    ``<tasks_root.parent>/tasks/electrical/…``.

    Raises ValueError if the archive is missing manifest.json or if any
    extracted task directory fails the integrity hash check.
    """
    with tarfile.open(archive_path, "r:gz") as tar:
        manifest_member = tar.getmember("manifest.json")
        manifest_file = tar.extractfile(manifest_member)
        if manifest_file is None:
            raise ValueError("manifest.json not found in archive")
        manifest_data = json.loads(manifest_file.read().decode("utf-8"))
        manifest = DatasetManifest.model_validate(manifest_data)

        for member in tar.getmembers():
            if member.name.startswith("tasks/") and member.name != "tasks/":
                target = tasks_root.parent / member.name
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    extracted = tar.extractfile(member)
                    if extracted:
                        target.write_bytes(extracted.read())

    # Verify integrity of each extracted task
    for task in manifest.tasks:
        task_dir = tasks_root.parent / task.task_path
        if task_dir.exists():
            current_hash = hash_task_directory(task_dir)
            if current_hash != task.content_hash:
                raise ValueError(
                    f"Integrity check failed for {task.task_id}: "
                    f"expected {task.content_hash[:12]}, got {current_hash[:12]}"
                )

    write_manifest(datasets_root, manifest)
    return manifest


def _generate_readme(manifest: DatasetManifest) -> str:
    """Generate a README.md string from the dataset manifest metadata."""
    desc = manifest.description
    lines = [
        f"# {manifest.name} v{manifest.version}",
        "",
        desc.summary,
        "",
    ]
    if desc.purpose:
        lines.extend([f"**Purpose:** {desc.purpose}", ""])
    lines.extend(
        [
            f"**Tasks:** {desc.task_count}",
            f"**Domains:** {', '.join(desc.domains)}",
            f"**Templates:** {desc.template_count}",
        ]
    )
    if desc.standards:
        lines.append(f"**Standards:** {', '.join(desc.standards)}")
    if desc.difficulty_distribution:
        dist = ", ".join(f"{k}: {v}" for k, v in desc.difficulty_distribution.items())
        lines.append(f"**Difficulty distribution:** {dist}")
    lines.extend(
        [
            "",
            f"**Content hash:** `{manifest.content_hash}`",
            f"**Created:** {manifest.created_at.strftime('%Y-%m-%d')}",
        ]
    )
    return "\n".join(lines)


def _add_string_to_tar(tar: tarfile.TarFile, name: str, content: str) -> None:
    """Add a UTF-8 string as a named file entry to a tar archive."""
    data = content.encode("utf-8")
    info = tarfile.TarInfo(name=name)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))
