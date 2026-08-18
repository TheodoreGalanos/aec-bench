# ABOUTME: Stores immutable schema-2 dataset manifests and separate publication-label events.
# ABOUTME: Resolves interactive human selectors to exact dataset references before execution.

from __future__ import annotations

import logging
import re
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from aec_bench.contracts.dataset import DatasetManifest, DatasetPublication, DatasetRef
from aec_bench.ledger.artifact_repository import canonical_model_bytes

logger = logging.getLogger(__name__)

_MANIFEST_FILENAME = "manifest.json"
_MANIFESTS_DIRECTORY = "manifests"
_PUBLICATIONS_DIRECTORY = "publications"
_REFERENCES_DIRECTORY = "references"
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_DATASET_REFERENCE_ADAPTER: TypeAdapter[DatasetRef] = TypeAdapter(DatasetRef)


def _validate_segment(value: str, *, name: str) -> str:
    if not _SAFE_SEGMENT.fullmatch(value):
        raise ValueError(f"{name} must use only letters, numbers, dot, underscore, and hyphen")
    return value


def manifest_path(datasets_root: Path, dataset_id: str) -> Path:
    """Return the only mutable-workspace path for one schema-2 manifest."""

    _validate_segment(dataset_id, name="dataset_id")
    return datasets_root / _MANIFESTS_DIRECTORY / dataset_id / _MANIFEST_FILENAME


def publication_path(datasets_root: Path, dataset_id: str, label: str) -> Path:
    """Return the immutable publication-event path for one human label."""

    _validate_segment(dataset_id, name="dataset_id")
    _validate_segment(label, name="label")
    return datasets_root / _PUBLICATIONS_DIRECTORY / dataset_id / f"{label}.json"


def reference_path(datasets_root: Path, reference: DatasetRef) -> Path:
    """Return the retained external-reference path for one exact dataset source."""

    if reference.kind == "repository":
        identity = reference.source_revision
    else:
        identity = reference.artifact.sha256
    return datasets_root / _REFERENCES_DIRECTORY / reference.dataset_id / f"{identity}.json"


def _write_new(path: Path, payload: bytes, *, kind: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
    except FileExistsError:
        raise FileExistsError(f"{kind} already exists: {path}") from None
    return path


def write_manifest(datasets_root: Path, manifest: DatasetManifest) -> Path:
    """Write one new manifest and never replace existing dataset content."""

    path = manifest_path(datasets_root, manifest.dataset_id)
    stored = _write_new(path, canonical_model_bytes(manifest), kind="dataset manifest")
    logger.info("wrote dataset manifest to %s", stored)
    return stored


def read_manifest(path: Path) -> DatasetManifest:
    """Read one schema-2 manifest. Legacy documents require the named migration reader."""

    if not path.is_file():
        raise FileNotFoundError(f"manifest file not found: {path}")
    return DatasetManifest.model_validate_json(path.read_bytes())


def read_manifest_by_id(datasets_root: Path, dataset_id: str) -> DatasetManifest | None:
    """Read one unpublished or published workspace manifest by stable dataset ID."""

    path = manifest_path(datasets_root, dataset_id)
    if not path.is_file():
        return None
    return read_manifest(path)


def list_datasets(datasets_root: Path) -> list[DatasetManifest]:
    """List valid schema-2 manifests without searching historical version directories."""

    root = datasets_root / _MANIFESTS_DIRECTORY
    if not root.is_dir():
        return []
    manifests: list[DatasetManifest] = []
    for path in sorted(root.glob(f"*/{_MANIFEST_FILENAME}")):
        try:
            manifests.append(read_manifest(path))
        except (OSError, ValueError, ValidationError):
            logger.warning("skipping invalid dataset manifest at %s", path)
    return sorted(manifests, key=lambda manifest: manifest.dataset_id)


def write_publication(datasets_root: Path, publication: DatasetPublication) -> Path:
    """Persist one label assignment without permitting implicit reassignment."""

    path = publication_path(datasets_root, publication.dataset_ref.dataset_id, publication.label)
    stored = _write_new(path, canonical_model_bytes(publication), kind="dataset publication")
    logger.info("wrote dataset publication to %s", stored)
    return stored


def read_publication(path: Path) -> DatasetPublication:
    """Read one validated publication event."""

    if not path.is_file():
        raise FileNotFoundError(f"dataset publication not found: {path}")
    return DatasetPublication.model_validate_json(path.read_bytes())


def write_dataset_reference(datasets_root: Path, reference: DatasetRef) -> Path:
    """Persist the exact reference outside any detached bundle it authenticates."""

    path = reference_path(datasets_root, reference)
    if path.is_file():
        existing = _DATASET_REFERENCE_ADAPTER.validate_json(path.read_bytes())
        if existing == reference:
            return path
        raise FileExistsError(f"dataset reference already exists with different content: {path}")
    return _write_new(path, canonical_model_bytes(reference), kind="dataset reference")


def read_dataset_reference(path: Path) -> DatasetRef:
    """Read one retained repository or bundle reference."""

    if not path.is_file():
        raise FileNotFoundError(f"dataset reference not found: {path}")
    return _DATASET_REFERENCE_ADAPTER.validate_json(path.read_bytes())


def list_publications(datasets_root: Path, *, dataset_id: str | None = None) -> list[DatasetPublication]:
    """List publication events, optionally for one stable dataset ID."""

    root = datasets_root / _PUBLICATIONS_DIRECTORY
    if dataset_id is not None:
        _validate_segment(dataset_id, name="dataset_id")
        paths = sorted((root / dataset_id).glob("*.json"))
    else:
        paths = sorted(root.glob("*/*.json"))
    publications: list[DatasetPublication] = []
    for path in paths:
        try:
            publications.append(read_publication(path))
        except (OSError, ValueError, ValidationError):
            logger.warning("skipping invalid dataset publication at %s", path)
    return sorted(publications, key=lambda item: (item.published_at, item.label))


def resolve_dataset_reference(datasets_root: Path, selector: str) -> DatasetRef | None:
    """Resolve an interactive ID or ID@label selector to one immutable reference."""

    if "@" in selector:
        dataset_id, label = selector.split("@", maxsplit=1)
        _validate_segment(dataset_id, name="dataset_id")
        _validate_segment(label, name="label")
        if label.casefold() == "latest":
            raise ValueError("latest is a mutable selector and cannot be persisted")
        path = publication_path(datasets_root, dataset_id, label)
        if not path.is_file():
            return None
        publication = read_publication(path)
        if publication.dataset_ref.dataset_id != dataset_id:
            raise ValueError("dataset publication ID does not match its storage path")
        return publication.dataset_ref

    _validate_segment(selector, name="dataset_id")
    publications = list_publications(datasets_root, dataset_id=selector)
    if not publications:
        return None
    return publications[-1].dataset_ref


__all__ = (
    "list_datasets",
    "list_publications",
    "manifest_path",
    "publication_path",
    "read_dataset_reference",
    "read_manifest",
    "read_manifest_by_id",
    "read_publication",
    "resolve_dataset_reference",
    "reference_path",
    "write_dataset_reference",
    "write_manifest",
    "write_publication",
)
