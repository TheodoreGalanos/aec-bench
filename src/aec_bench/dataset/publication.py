# ABOUTME: Publishes semantic datasets through exact repository or detached-bundle references.
# ABOUTME: Resolves interactive labels before execution and verifies materialised bytes fail closed.

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from aec_bench.contracts.dataset import (
    DatasetManifest,
    DatasetPublication,
    DatasetRef,
    RepositoryDatasetRef,
)
from aec_bench.dataset.integrity import IntegrityResult
from aec_bench.dataset.porter import (
    DATASET_BUNDLE_MEDIA_TYPE,
    publish_dataset_bundle,
    read_dataset_bundle,
    verify_bundle_materialization,
)
from aec_bench.dataset.repository import (
    load_repository_dataset,
    repository_dataset_reference,
    verify_repository_materialization,
)
from aec_bench.dataset.storage import (
    manifest_path,
    publication_path,
    resolve_dataset_reference,
    write_dataset_reference,
    write_publication,
)
from aec_bench.ledger.artifact_repository import ArtifactRepository


@dataclass(frozen=True)
class ResolvedDataset:
    """A semantic manifest paired with its one authoritative immutable reference."""

    reference: DatasetRef
    manifest: DatasetManifest


def publish_dataset(
    *,
    manifest: DatasetManifest,
    datasets_root: Path,
    project_root: Path,
    label: str,
    repository: bool = False,
    published_at: datetime | None = None,
) -> DatasetPublication:
    """Publish one exact reference and assign a new human discovery label."""

    target = publication_path(datasets_root, manifest.dataset_id, label)
    if target.exists():
        raise FileExistsError(f"dataset publication already exists: {target}")

    if repository:
        reference: DatasetRef = repository_dataset_reference(
            manifest=manifest,
            manifest_path=manifest_path(datasets_root, manifest.dataset_id),
            project_root=project_root,
        )
    else:
        reference = publish_dataset_bundle(
            manifest=manifest,
            project_root=project_root,
            repository=ArtifactRepository(datasets_root / "artifacts"),
        )
    write_dataset_reference(datasets_root, reference)
    publication = DatasetPublication(
        dataset_ref=reference,
        label=label,
        published_at=published_at or datetime.now(UTC),
    )
    write_publication(datasets_root, publication)
    return publication


def resolve_dataset(
    *,
    datasets_root: Path,
    selector: str | DatasetRef,
    project_root: Path,
) -> ResolvedDataset | None:
    """Resolve an interactive selector or exact reference to its verified semantic manifest."""

    reference = resolve_dataset_reference(datasets_root, selector) if isinstance(selector, str) else selector
    if reference is None:
        return None

    if isinstance(reference, RepositoryDatasetRef):
        manifest = load_repository_dataset(reference, project_root=project_root)
    else:
        if reference.artifact.media_type != DATASET_BUNDLE_MEDIA_TYPE:
            raise ValueError("bundle dataset reference has an unsupported media type")
        payload = ArtifactRepository(datasets_root / "artifacts").read_bytes(reference.artifact)
        manifest = read_dataset_bundle(payload).manifest
    if manifest.dataset_id != reference.dataset_id:
        raise ValueError("dataset reference ID does not match its manifest")
    return ResolvedDataset(reference=reference, manifest=manifest)


def verify_resolved_dataset(
    resolved: ResolvedDataset,
    *,
    datasets_root: Path,
    project_root: Path,
) -> IntegrityResult:
    """Verify exact reference bytes and their current task materialisation."""

    if isinstance(resolved.reference, RepositoryDatasetRef):
        return verify_repository_materialization(resolved.reference, project_root=project_root)

    payload = ArtifactRepository(datasets_root / "artifacts").read_bytes(resolved.reference.artifact)
    bundle = read_dataset_bundle(payload)
    if bundle.manifest != resolved.manifest:
        raise ValueError("resolved dataset manifest does not match its detached bundle")
    return verify_bundle_materialization(bundle, project_root=project_root)


__all__ = (
    "ResolvedDataset",
    "publish_dataset",
    "resolve_dataset",
    "verify_resolved_dataset",
)
