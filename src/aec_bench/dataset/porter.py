# ABOUTME: Builds, validates, publishes, and safely imports deterministic detached dataset bundles.
# ABOUTME: Uses one enclosing ArtifactRef instead of manifest and per-task self-hashes.

from __future__ import annotations

import gzip
import io
import shutil
import tarfile
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType

from aec_bench.contracts.dataset import BundleDatasetRef, DatasetManifest
from aec_bench.dataset.integrity import IntegrityResult
from aec_bench.dataset.storage import manifest_path, write_dataset_reference, write_manifest
from aec_bench.ledger.artifact_repository import ArtifactRepository, canonical_model_bytes

DATASET_BUNDLE_MEDIA_TYPE = "application/vnd.aec-bench.dataset-bundle+tar+gzip"
_EXCLUDED_DIRECTORY_NAMES = {"__pycache__"}
_EXCLUDED_SUFFIXES = {".pyc"}


@dataclass(frozen=True)
class DatasetBundle:
    """Validated bundle content held in memory before any filesystem writes."""

    manifest: DatasetManifest
    manifest_bytes: bytes
    files: Mapping[str, bytes]
    executable_paths: frozenset[str]


@dataclass(frozen=True)
class ImportedDataset:
    """A safely materialised bundle and its retained exact-byte reference."""

    manifest: DatasetManifest
    reference: BundleDatasetRef


def _portable_archive_path(value: str) -> PurePosixPath:
    if "\\" in value:
        raise ValueError(f"archive member is not a portable relative path: {value}")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"archive member is not a portable relative path: {value}")
    if path.as_posix() != value:
        raise ValueError(f"archive member is not a portable relative path: {value}")
    return path


def _include_task_file(path: Path) -> bool:
    return not any(part in _EXCLUDED_DIRECTORY_NAMES for part in path.parts) and path.suffix not in _EXCLUDED_SUFFIXES


def _path_contains_symlink(root: Path, relative: str) -> bool:
    current = root
    for part in PurePosixPath(relative).parts:
        current /= part
        if current.is_symlink():
            return True
    return False


def _collect_task_files(manifest: DatasetManifest, project_root: Path) -> tuple[dict[str, bytes], frozenset[str]]:
    root = project_root.resolve()
    files: dict[str, bytes] = {}
    executables: set[str] = set()
    for task in manifest.tasks:
        declared_task_dir = root / task.path
        if _path_contains_symlink(root, task.path):
            raise ValueError(f"declared task path must not contain a symlink: {task.path}")
        task_dir = declared_task_dir.resolve()
        try:
            task_dir.relative_to(root)
        except ValueError as error:
            raise ValueError(f"declared task escapes the project root: {task.path}") from error
        if not task_dir.is_dir():
            raise FileNotFoundError(f"declared task directory is missing: {task_dir}")
        task_file_count = 0
        for path in sorted(task_dir.rglob("*")):
            if not _include_task_file(path):
                continue
            if path.is_symlink():
                raise ValueError(f"dataset task files must not be symlinks: {path}")
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if relative in files:
                raise ValueError(f"duplicate dataset task file: {relative}")
            files[relative] = path.read_bytes()
            if path.stat().st_mode & 0o111:
                executables.add(relative)
            task_file_count += 1
        if task_file_count == 0:
            raise ValueError(f"declared task directory has no retained files: {task.path}")
    return files, frozenset(executables)


def _tar_info(name: str, payload: bytes, *, executable: bool = False) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name=name)
    info.size = len(payload)
    info.mode = 0o755 if executable else 0o644
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


def _encode_bundle(manifest_bytes: bytes, files: Mapping[str, bytes], executables: frozenset[str]) -> bytes:
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        archive.addfile(_tar_info("manifest.json", manifest_bytes), io.BytesIO(manifest_bytes))
        for path in sorted(files):
            payload = files[path]
            archive.addfile(
                _tar_info(path, payload, executable=path in executables),
                io.BytesIO(payload),
            )

    compressed = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=compressed, mtime=0) as stream:
        stream.write(tar_buffer.getvalue())
    return compressed.getvalue()


def build_dataset_bundle(*, manifest: DatasetManifest, project_root: Path) -> bytes:
    """Build deterministic bundle bytes for one semantic manifest and its declared tasks."""

    files, executables = _collect_task_files(manifest, project_root)
    return _encode_bundle(canonical_model_bytes(manifest), files, executables)


def read_dataset_bundle(data: bytes) -> DatasetBundle:
    """Validate one untrusted bundle without extracting it to the filesystem."""

    if not data:
        raise ValueError("dataset bundle must not be empty")
    members: dict[str, bytes] = {}
    executables: set[str] = set()
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for member in archive.getmembers():
                path = _portable_archive_path(member.name)
                name = path.as_posix()
                if name in members:
                    raise ValueError(f"duplicate archive path: {name}")
                if not member.isfile():
                    raise ValueError(f"dataset bundles may contain regular files only: {name}")
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise ValueError(f"cannot read dataset bundle member: {name}")
                payload = extracted.read()
                if len(payload) != member.size:
                    raise ValueError(f"dataset bundle member size mismatch: {name}")
                members[name] = payload
                if member.mode & 0o111:
                    executables.add(name)
    except tarfile.TarError as error:
        raise ValueError(f"invalid dataset bundle: {error}") from error

    try:
        manifest_bytes = members.pop("manifest.json")
    except KeyError:
        raise ValueError("manifest.json not found in dataset bundle") from None
    manifest = DatasetManifest.model_validate_json(manifest_bytes)

    task_paths = {task.path: task.task_id for task in manifest.tasks}
    files_by_task = {task_id: 0 for task_id in task_paths.values()}
    for name in members:
        member_path = PurePosixPath(name)
        owners = [
            task_id for task_path, task_id in task_paths.items() if member_path.is_relative_to(PurePosixPath(task_path))
        ]
        if len(owners) != 1:
            raise ValueError(f"undeclared task content in dataset bundle: {name}")
        files_by_task[owners[0]] += 1
    absent = sorted(task_id for task_id, count in files_by_task.items() if count == 0)
    if absent:
        raise ValueError(f"declared task is absent from dataset bundle: {', '.join(absent)}")

    return DatasetBundle(
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        files=MappingProxyType(dict(members)),
        executable_paths=frozenset(executables - {"manifest.json"}),
    )


def verify_bundle_materialization(bundle: DatasetBundle, *, project_root: Path) -> IntegrityResult:
    """Compare current task bytes with the exact files covered by the enclosing bundle digest."""

    root = project_root.resolve()
    missing: list[str] = []
    modified: list[str] = []
    unexpected: list[str] = []
    verified = 0
    for task in bundle.manifest.tasks:
        task_dir = root / task.path
        if not task_dir.is_dir():
            missing.append(task.task_id)
            continue
        if _path_contains_symlink(root, task.path):
            modified.append(task.task_id)
            continue

        expected = {
            name: payload
            for name, payload in bundle.files.items()
            if PurePosixPath(name).is_relative_to(PurePosixPath(task.path))
        }
        actual: dict[str, bytes] = {}
        for path in sorted(task_dir.rglob("*")):
            if not _include_task_file(path):
                continue
            if path.is_symlink():
                unexpected.append(path.relative_to(root).as_posix())
                continue
            if path.is_file():
                name = path.relative_to(root).as_posix()
                actual[name] = path.read_bytes()
                expected_executable = name in bundle.executable_paths
                if bool(path.stat().st_mode & 0o111) != expected_executable and task.task_id not in modified:
                    modified.append(task.task_id)

        extra = sorted(set(actual) - set(expected))
        unexpected.extend(extra)
        if set(expected) - set(actual) or any(actual.get(name) != payload for name, payload in expected.items()):
            if task.task_id not in modified:
                modified.append(task.task_id)
            continue
        if extra:
            continue
        verified += 1

    return IntegrityResult(
        verified=verified,
        missing=tuple(sorted(missing)),
        modified=tuple(sorted(modified)),
        unexpected=tuple(sorted(set(unexpected))),
    )


def publish_dataset_bundle(
    *,
    manifest: DatasetManifest,
    project_root: Path,
    repository: ArtifactRepository,
) -> BundleDatasetRef:
    """Publish one deterministic bundle and return its exact external reference."""

    artifact = repository.publish_bytes(
        data=build_dataset_bundle(manifest=manifest, project_root=project_root),
        media_type=DATASET_BUNDLE_MEDIA_TYPE,
    )
    return BundleDatasetRef(dataset_id=manifest.dataset_id, artifact=artifact)


def export_dataset(*, manifest: DatasetManifest, project_root: Path, output_path: Path) -> None:
    """Write deterministic detached bundle bytes to a caller-selected path."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise FileExistsError(f"dataset export already exists: {output_path}")
    output_path.write_bytes(build_dataset_bundle(manifest=manifest, project_root=project_root))


def import_dataset(*, archive_path: Path, tasks_root: Path, datasets_root: Path) -> ImportedDataset:
    """Validate, retain, and safely materialise a detached schema-2 bundle."""

    payload = archive_path.read_bytes()
    bundle = read_dataset_bundle(payload)
    project_root = tasks_root.parent.resolve()
    project_root.mkdir(parents=True, exist_ok=True)
    configured_tasks_prefix = PurePosixPath(tasks_root.resolve().relative_to(project_root).as_posix())

    targets: list[tuple[str, Path]] = []
    for task in bundle.manifest.tasks:
        relative = PurePosixPath(task.path)
        if not relative.is_relative_to(configured_tasks_prefix):
            raise ValueError(f"dataset task path is outside the configured tasks root: {task.path}")
        target = (project_root / task.path).resolve()
        try:
            target.relative_to(tasks_root.resolve())
        except ValueError as error:
            raise ValueError(f"dataset task path escapes the configured tasks root: {task.path}") from error
        if target.exists():
            raise FileExistsError(f"dataset task already exists: {target}")
        targets.append((task.path, target))

    stored_manifest = manifest_path(datasets_root, bundle.manifest.dataset_id)
    if stored_manifest.exists():
        raise FileExistsError(f"dataset manifest already exists: {stored_manifest}")

    repository = ArtifactRepository(datasets_root / "artifacts")
    artifact = repository.publish_bytes(data=payload, media_type=DATASET_BUNDLE_MEDIA_TYPE)
    reference = BundleDatasetRef(dataset_id=bundle.manifest.dataset_id, artifact=artifact)
    write_dataset_reference(datasets_root, reference)

    with tempfile.TemporaryDirectory(prefix=".dataset-import-", dir=project_root) as temporary:
        staging = Path(temporary)
        for name, content in bundle.files.items():
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            if name in bundle.executable_paths:
                target.chmod(0o755)

        for task_path, target in targets:
            source = staging / task_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))

    write_manifest(datasets_root, bundle.manifest)
    return ImportedDataset(manifest=bundle.manifest, reference=reference)


__all__ = (
    "DATASET_BUNDLE_MEDIA_TYPE",
    "DatasetBundle",
    "ImportedDataset",
    "build_dataset_bundle",
    "export_dataset",
    "import_dataset",
    "publish_dataset_bundle",
    "read_dataset_bundle",
    "verify_bundle_materialization",
)
