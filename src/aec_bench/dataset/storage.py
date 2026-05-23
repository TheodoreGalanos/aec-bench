# ABOUTME: Filesystem-backed storage for dataset manifests — write, read, list, resolve.
# ABOUTME: Manifests live at {datasets_root}/{name}/{version}/manifest.json.

from __future__ import annotations

import json
import logging
from pathlib import Path

from aec_bench.contracts.dataset import DatasetManifest

logger = logging.getLogger(__name__)

_MANIFEST_FILENAME = "manifest.json"


def _semver_key(version_dir: Path) -> tuple[int, ...]:
    """Parse a version directory name into a numeric tuple for sorting.

    Falls back to (0,) for non-numeric version strings so they sort first.
    """
    try:
        return tuple(int(x) for x in version_dir.name.split("."))
    except ValueError:
        return (0,)


def write_manifest(
    datasets_root: Path,
    manifest: DatasetManifest,
    *,
    overwrite: bool = False,
) -> Path:
    """Write a manifest to {datasets_root}/{name}/{version}/manifest.json.

    Raises FileExistsError if the manifest already exists and overwrite is False.
    Returns the path to the written manifest file.
    """
    manifest_dir = datasets_root / manifest.name / manifest.version
    manifest_path = manifest_dir / _MANIFEST_FILENAME

    if manifest_path.is_file() and not overwrite:
        msg = f"dataset manifest already exists: {manifest_path}"
        raise FileExistsError(msg)

    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )
    logger.info("wrote manifest to %s", manifest_path)
    return manifest_path


def read_manifest(manifest_path: Path) -> DatasetManifest:
    """Read and validate a dataset manifest from a JSON file.

    Raises FileNotFoundError if the path does not exist.
    """
    if not manifest_path.is_file():
        msg = f"manifest file not found: {manifest_path}"
        raise FileNotFoundError(msg)

    raw = manifest_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    return DatasetManifest.model_validate(data)


def list_datasets(datasets_root: Path) -> list[DatasetManifest]:
    """Find all valid manifests under datasets_root.

    Returns a flat list of manifests across all dataset names and versions.
    Silently skips directories that do not contain valid manifests.
    """
    if not datasets_root.is_dir():
        return []

    manifests: list[DatasetManifest] = []
    for name_dir in sorted(datasets_root.iterdir()):
        if not name_dir.is_dir():
            continue
        for version_dir in sorted(name_dir.iterdir(), key=_semver_key):
            if not version_dir.is_dir():
                continue
            manifest_path = version_dir / _MANIFEST_FILENAME
            if not manifest_path.is_file():
                continue
            try:
                manifests.append(read_manifest(manifest_path))
            except Exception:
                logger.warning("skipping invalid manifest at %s", manifest_path)
    return manifests


def resolve_dataset(
    datasets_root: Path,
    reference: str,
) -> DatasetManifest | None:
    """Resolve a dataset reference to a manifest.

    Accepts "name" (returns latest version) or "name@version" (exact match).
    Returns None if no matching dataset is found.
    """
    if "@" in reference:
        name, version = reference.split("@", maxsplit=1)
    else:
        name = reference
        version = None

    name_dir = datasets_root / name
    if not name_dir.is_dir():
        return None

    if version is not None:
        manifest_path = name_dir / version / _MANIFEST_FILENAME
        if not manifest_path.is_file():
            return None
        return read_manifest(manifest_path)

    # Find latest version using numeric semver sorting
    version_dirs = [d for d in name_dir.iterdir() if d.is_dir()]
    if not version_dirs:
        return None

    version_dirs.sort(key=_semver_key)
    latest_dir = version_dirs[-1]
    manifest_path = latest_dir / _MANIFEST_FILENAME
    if not manifest_path.is_file():
        return None

    return read_manifest(manifest_path)
