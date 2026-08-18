# ABOUTME: Resolves host-only files needed to execute one governed proposal session.
# ABOUTME: Fails closed before source paths or runtime archives can cross into a sandbox.

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ValidationError, field_validator

from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    canonical_json_sha256,
    validate_sha256,
)
from aec_bench.contracts.program_proposal.study import MatchedEvaluationCoordinate
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.experimentation.proposals.program_compilation import (
    ProposalRunSessionBundle,
)
from aec_bench.experimentation.proposals.runtime_archive import (
    ProposalRuntimeArchive,
    ProposalRuntimeArchiveError,
    verify_proposal_runtime_archive,
)
from aec_bench.experimentation.proposals.task_package import source_task_package_sha256
from aec_bench.experimentation.proposals.task_packaging.contracts import (
    ProposalTaskPackageError,
    ProposalTaskPackageManifest,
)
from aec_bench.tasks.loader import LoadError, load_task_definition

_MAX_SESSION_BUNDLE_BYTES = 64 * 1024 * 1024
_MAX_DERIVED_MANIFEST_BYTES = 1024 * 1024


class ProposalSessionHostConfigError(ValueError):
    """Reject an unpinned or unsafe host input before proposal setup."""


class ProposalSessionHostConfig(FrozenStrictModel):
    """Ephemeral host paths paired with durable identities for one dispatch."""

    schema_version: Literal["aecbench.proposal-session-host-config.v1"] = "aecbench.proposal-session-host-config.v1"
    bundle_path: NonEmptyStr
    bundle_file_sha256: str
    bundle_content_sha256: str
    source_task_dir: NonEmptyStr
    source_task_package_sha256: str
    runtime_archive_path: NonEmptyStr
    runtime_archive_sha256: str
    runtime_archive_content_sha256: str
    evaluation_coordinate: MatchedEvaluationCoordinate
    execution_schedule_sha256: str
    execution_assignment_sha256: str

    @field_validator(
        "bundle_file_sha256",
        "bundle_content_sha256",
        "source_task_package_sha256",
        "runtime_archive_sha256",
        "runtime_archive_content_sha256",
        "execution_schedule_sha256",
        "execution_assignment_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator(
        "bundle_path",
        "source_task_dir",
        "runtime_archive_path",
    )
    @classmethod
    def validate_absolute_host_path(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("proposal session host paths must be absolute")
        return value


@dataclass(frozen=True)
class LoadedProposalSessionHostInputs:
    """Validated host inputs that remain outside child execution bundles."""

    config: ProposalSessionHostConfig
    bundle: ProposalRunSessionBundle
    source_task_dir: Path
    derived_task_manifest: ProposalTaskPackageManifest
    runtime_archive: ProposalRuntimeArchive


@dataclass(frozen=True)
class _LoadedSourceTask:
    """Source task identity and typed definition admitted from one host directory."""

    path: Path
    package_sha256: str
    definition: TaskDefinition


def load_proposal_session_host_inputs(
    payload: object,
    *,
    environment_dir: Path,
) -> LoadedProposalSessionHostInputs:
    """Resolve exact files and cross-check every proposal dispatch identity."""

    config = _load_host_config(payload)
    bundle = _load_session_bundle(config)
    _validate_evaluation_coordinate(
        coordinate=config.evaluation_coordinate,
        bundle=bundle,
    )
    source_task = _load_source_task(
        config=config,
        bundle=bundle,
    )
    derived_manifest = _load_derived_task_manifest(
        environment_dir=environment_dir,
        bundle=bundle,
        source_task=source_task,
    )
    runtime_archive = _load_runtime_archive(config)

    return LoadedProposalSessionHostInputs(
        config=config,
        bundle=bundle,
        source_task_dir=source_task.path.resolve(),
        derived_task_manifest=derived_manifest,
        runtime_archive=runtime_archive,
    )


def _load_host_config(payload: object) -> ProposalSessionHostConfig:
    try:
        return ProposalSessionHostConfig.model_validate(payload)
    except ValidationError as error:
        raise ProposalSessionHostConfigError(f"invalid proposal session host configuration: {error}") from error


def _load_session_bundle(
    config: ProposalSessionHostConfig,
) -> ProposalRunSessionBundle:
    bundle_bytes = _read_regular_file(
        Path(config.bundle_path),
        label="proposal session bundle",
        max_bytes=_MAX_SESSION_BUNDLE_BYTES,
    )
    if hashlib.sha256(bundle_bytes).hexdigest() != config.bundle_file_sha256:
        raise ProposalSessionHostConfigError(
            "proposal session bundle file SHA-256 changed after dispatch configuration"
        )
    try:
        bundle = ProposalRunSessionBundle.model_validate_json(bundle_bytes)
    except (ValidationError, ValueError) as error:
        raise ProposalSessionHostConfigError(f"proposal session bundle is invalid: {error}") from error
    if bundle.content_sha256 != config.bundle_content_sha256:
        raise ProposalSessionHostConfigError(
            "proposal session bundle content identity differs from dispatch configuration"
        )
    return bundle


def _load_source_task(
    *,
    config: ProposalSessionHostConfig,
    bundle: ProposalRunSessionBundle,
) -> _LoadedSourceTask:
    source_task_dir = Path(config.source_task_dir)
    _require_directory(source_task_dir, label="proposal source task")
    try:
        observed_source_sha256 = source_task_package_sha256(source_task_dir)
    except ProposalTaskPackageError as error:
        raise ProposalSessionHostConfigError(f"proposal source task package is unsafe: {error}") from error
    expected_source_identities = (
        config.source_task_package_sha256,
        bundle.task_snapshot.package_sha256,
        bundle.compilation.source_scope_manifest.task_package_sha256,
    )
    if any(identity != observed_source_sha256 for identity in expected_source_identities):
        raise ProposalSessionHostConfigError("proposal source task package identity differs from the compiled session")
    try:
        source_task = load_task_definition(
            source_task_dir,
            _tasks_root_for(
                task_dir=source_task_dir,
                task_id=bundle.task_snapshot.task_id,
            ),
        )
    except (LoadError, OSError, ValueError) as error:
        raise ProposalSessionHostConfigError(f"proposal source task definition is invalid: {error}") from error
    if (
        source_task.task_id != bundle.task_snapshot.task_id
        or canonical_json_sha256(source_task.model_dump(mode="json")) != bundle.task_snapshot.definition_sha256
    ):
        raise ProposalSessionHostConfigError("proposal source task definition differs from the compiled session")
    return _LoadedSourceTask(
        path=source_task_dir,
        package_sha256=observed_source_sha256,
        definition=source_task,
    )


def _load_derived_task_manifest(
    *,
    environment_dir: Path,
    bundle: ProposalRunSessionBundle,
    source_task: _LoadedSourceTask,
) -> ProposalTaskPackageManifest:
    environment = Path(environment_dir)
    _require_directory(environment, label="derived task environment")
    manifest_path = environment.parent / "proposal-task-package.json"
    manifest_bytes = _read_regular_file(
        manifest_path,
        label="derived task package manifest",
        max_bytes=_MAX_DERIVED_MANIFEST_BYTES,
    )
    try:
        manifest = ProposalTaskPackageManifest.model_validate_json(manifest_bytes)
    except (ValidationError, ValueError) as error:
        raise ProposalSessionHostConfigError(f"derived task package manifest is invalid: {error}") from error
    _validate_derived_task_manifest(
        manifest=manifest,
        bundle=bundle,
        source_task_package_sha256=source_task.package_sha256,
        source_task_visibility=source_task.definition.visibility,
    )
    return manifest


def _load_runtime_archive(
    config: ProposalSessionHostConfig,
) -> ProposalRuntimeArchive:
    try:
        return verify_proposal_runtime_archive(
            archive_path=Path(config.runtime_archive_path),
            expected_archive_sha256=config.runtime_archive_sha256,
            expected_content_sha256=config.runtime_archive_content_sha256,
        )
    except ProposalRuntimeArchiveError as error:
        raise ProposalSessionHostConfigError(str(error)) from error


def _validate_evaluation_coordinate(
    *,
    coordinate: MatchedEvaluationCoordinate,
    bundle: ProposalRunSessionBundle,
) -> None:
    freeze = bundle.compilation.proposal_freeze
    if (
        coordinate.task_id != bundle.task_snapshot.task_id
        or coordinate.task_revision != bundle.task_snapshot.definition_sha256
        or coordinate.split is not freeze.split
        or coordinate.review_lineage_id != freeze.selected_review_lineage_id
    ):
        raise ProposalSessionHostConfigError(
            "proposal evaluation coordinate differs from the compiled session",
        )


def _validate_derived_task_manifest(
    *,
    manifest: ProposalTaskPackageManifest,
    bundle: ProposalRunSessionBundle,
    source_task_package_sha256: str,
    source_task_visibility: object,
) -> None:
    problem_view = bundle.compilation.proposal_freeze.problem_view
    finalizer = bundle.compilation.proposal_graph.finalizer
    expected = (
        bundle.task_snapshot.task_id,
        bundle.task_snapshot.definition_sha256,
        source_task_package_sha256,
        problem_view.content_sha256,
        finalizer.output_completion_contract_sha256,
        source_task_visibility,
    )
    actual = (
        manifest.task_id,
        manifest.task_revision,
        manifest.source_task_package_sha256,
        manifest.problem_view_sha256,
        manifest.output_contract_sha256,
        manifest.visibility,
    )
    if actual != expected:
        raise ProposalSessionHostConfigError("derived task package does not bind the exact compiled proposal session")


def _read_regular_file(
    path: Path,
    *,
    label: str,
    max_bytes: int,
) -> bytes:
    try:
        inspected = path.stat(follow_symlinks=False)
    except OSError as error:
        raise ProposalSessionHostConfigError(f"{label} cannot be inspected: {path}") from error
    if stat.S_ISLNK(inspected.st_mode):
        raise ProposalSessionHostConfigError(f"{label} must not be a symbolic link: {path}")
    if not stat.S_ISREG(inspected.st_mode):
        raise ProposalSessionHostConfigError(f"{label} must be a regular file: {path}")
    if inspected.st_size > max_bytes:
        raise ProposalSessionHostConfigError(f"{label} exceeds its byte limit: {path}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ProposalSessionHostConfigError(f"{label} cannot be read: {path}") from error
    try:
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_dev != inspected.st_dev
            or observed.st_ino != inspected.st_ino
        ):
            raise ProposalSessionHostConfigError(f"{label} changed before it was read: {path}")
        content = _read_bounded_descriptor(
            descriptor,
            label=label,
            path=path,
            max_bytes=max_bytes,
        )
        after = os.fstat(descriptor)
        if (
            observed.st_dev != after.st_dev
            or observed.st_ino != after.st_ino
            or observed.st_size != after.st_size
            or observed.st_mtime_ns != after.st_mtime_ns
            or observed.st_ctime_ns != after.st_ctime_ns
        ):
            raise ProposalSessionHostConfigError(f"{label} changed while it was read: {path}")
        return content
    except OSError as error:
        raise ProposalSessionHostConfigError(f"{label} cannot be read: {path}") from error
    finally:
        os.close(descriptor)


def _read_bounded_descriptor(
    descriptor: int,
    *,
    label: str,
    path: Path,
    max_bytes: int,
) -> bytes:
    content = bytearray()
    while len(content) <= max_bytes:
        chunk = os.read(
            descriptor,
            min(1024 * 1024, max_bytes + 1 - len(content)),
        )
        if not chunk:
            break
        content.extend(chunk)
    if len(content) > max_bytes:
        raise ProposalSessionHostConfigError(f"{label} exceeds its byte limit: {path}")
    return bytes(content)


def _require_directory(path: Path, *, label: str) -> None:
    if path.is_symlink():
        raise ProposalSessionHostConfigError(f"{label} must not be a symbolic link: {path}")
    try:
        path_stat = path.stat(follow_symlinks=False)
    except OSError as error:
        raise ProposalSessionHostConfigError(f"{label} cannot be inspected: {path}") from error
    if not stat.S_ISDIR(path_stat.st_mode):
        raise ProposalSessionHostConfigError(f"{label} must be a directory: {path}")


def _tasks_root_for(*, task_dir: Path, task_id: str) -> Path:
    root = task_dir
    for _ in Path(task_id).parts:
        root = root.parent
    return root
