# ABOUTME: Persists immutable production-monitor claims beneath one confined host-owned repository.
# ABOUTME: Keeps exact claim schemas, translated storage failures, enumeration, and deterministic paths.

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal, Protocol

from pydantic import TypeAdapter, field_validator

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    validate_sha256,
)
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.experimentation.governance.standing_monitors import ForbiddenFlowRule
from aec_bench.ledger.immutable_artifact_store import (
    EvidenceRepository,
    ImmutableArtifactCollisionError,
    ImmutableArtifactConfinementError,
    ImmutableArtifactIntegrityError,
)


class MonitorRuntimeError(RuntimeError):
    """Base failure for the host-owned production monitor runtime."""


class MonitorRuntimeConfinementError(MonitorRuntimeError):
    """Raised when monitor state can escape or overlap a protected root."""


class MonitorRuntimeCollisionError(MonitorRuntimeError):
    """Raised when a durable logical identity is rebound to different content."""


class MonitorRuntimeIntegrityError(MonitorRuntimeError):
    """Raised when persisted monitor state cannot be verified exactly."""


class ProductionMonitorCheckpointKind(StrEnum):
    """Mandatory checkpoints around one governed effect-bearing cycle."""

    PRE_EFFECT = "pre_effect"
    TERMINAL = "terminal"


class _CyclePlanIdentity(Protocol):
    @property
    def cycle_id(self) -> str:
        """Return the cycle identity used to derive repository paths."""


class _RuntimeManifestIdentity(Protocol):
    @property
    def cycle_plan(self) -> _CyclePlanIdentity:
        """Return the cycle identity carried by a runtime manifest."""


class _RuntimeManifestClaim(ContentAddressedModel):
    """Exclusive cycle identity binding to one runtime manifest."""

    schema_version: Literal["aecbench.monitor-runtime-manifest-claim.v1"] = "aecbench.monitor-runtime-manifest-claim.v1"
    cycle_id: NonEmptyStr
    runtime_manifest_sha256: str

    @field_validator("runtime_manifest_sha256")
    @classmethod
    def validate_manifest_hash(cls, value: str) -> str:
        return validate_sha256(value)


class _RuntimeFlowClaim(ContentAddressedModel):
    """Exclusive flow_id binding to one durable runtime observation."""

    schema_version: Literal["aecbench.monitor-runtime-flow-claim.v1"] = "aecbench.monitor-runtime-flow-claim.v1"
    runtime_manifest_sha256: str
    flow_id: NonEmptyStr
    flow_observation_sha256: str

    @field_validator("runtime_manifest_sha256", "flow_observation_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class _CanaryReferenceClaim(ContentAddressedModel):
    """Exclusive reference_id binding to one canary-reference event."""

    schema_version: Literal["aecbench.monitor-canary-reference-claim.v1"] = "aecbench.monitor-canary-reference-claim.v1"
    runtime_manifest_sha256: str
    reference_id: NonEmptyStr
    reference_event_sha256: str

    @field_validator("runtime_manifest_sha256", "reference_event_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class _CanarySurfaceActivationClaim(ContentAddressedModel):
    """Exclusive canary commitment binding to one verified surface activation."""

    schema_version: Literal["aecbench.canary-surface-activation-claim.v1"] = (
        "aecbench.canary-surface-activation-claim.v1"
    )
    runtime_manifest_sha256: str
    canary_commitment_sha256: str
    activation_sha256: str

    @field_validator(
        "runtime_manifest_sha256",
        "canary_commitment_sha256",
        "activation_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class _FlowCollectorActivationClaim(ContentAddressedModel):
    """Exclusive forbidden-flow rule binding to one verified collector activation."""

    schema_version: Literal["aecbench.flow-collector-activation-claim.v1"] = (
        "aecbench.flow-collector-activation-claim.v1"
    )
    runtime_manifest_sha256: str
    rule: ForbiddenFlowRule
    activation_sha256: str

    @field_validator("runtime_manifest_sha256", "activation_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class _CheckpointClaim(ContentAddressedModel):
    """Exclusive checkpoint-stage binding to one immutable checkpoint."""

    schema_version: Literal["aecbench.monitor-runtime-checkpoint-claim.v1"] = (
        "aecbench.monitor-runtime-checkpoint-claim.v1"
    )
    runtime_manifest_sha256: str
    checkpoint: ProductionMonitorCheckpointKind
    checkpoint_sha256: str

    @field_validator("runtime_manifest_sha256", "checkpoint_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class _EffectPermitClaim(ContentAddressedModel):
    """Exclusive cycle binding to one pre-effect permit."""

    schema_version: Literal["aecbench.monitor-effect-permit-claim.v1"] = "aecbench.monitor-effect-permit-claim.v1"
    runtime_manifest_sha256: str
    effect_permit_sha256: str

    @field_validator("runtime_manifest_sha256", "effect_permit_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class _RuntimeClosureClaim(ContentAddressedModel):
    """Exclusive cycle binding to one incident-preserving closure."""

    schema_version: Literal["aecbench.monitor-runtime-closure-claim.v1"] = "aecbench.monitor-runtime-closure-claim.v1"
    runtime_manifest_sha256: str
    closure_sha256: str

    @field_validator("runtime_manifest_sha256", "closure_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


def _prepare_new_repository(
    *,
    root: Path,
    authority_root: Path,
    candidate_roots: tuple[Path, ...],
) -> tuple[EvidenceRepository, tuple[Path, ...]]:
    normalized_candidates = tuple(Path(candidate).resolve(strict=False) for candidate in candidate_roots)
    with _translate_repository_errors(label="monitor runtime root"):
        repository = EvidenceRepository(
            Path(os.path.abspath(root)),
            disjoint_roots=(
                Path(authority_root).resolve(strict=False),
                *normalized_candidates,
            ),
            host_private=True,
        )
    return repository, normalized_candidates


def _open_existing_repository(
    *,
    root: Path,
    authority_root: Path,
    candidate_roots: tuple[Path, ...],
) -> tuple[EvidenceRepository, tuple[Path, ...]]:
    absolute_root = Path(os.path.abspath(root))
    if not os.path.lexists(absolute_root):
        raise MonitorRuntimeIntegrityError("monitor runtime root is missing")
    return _prepare_new_repository(
        root=root,
        authority_root=authority_root,
        candidate_roots=candidate_roots,
    )


@contextmanager
def _translate_repository_errors(
    *,
    label: str,
) -> Iterator[None]:
    try:
        yield
    except ImmutableArtifactCollisionError as error:
        raise MonitorRuntimeCollisionError(f"{label}: {error}") from error
    except ImmutableArtifactConfinementError as error:
        raise MonitorRuntimeConfinementError(f"{label}: {error}") from error
    except ImmutableArtifactIntegrityError as error:
        raise MonitorRuntimeIntegrityError(f"{label}: {error}") from error


def _store_monitor_model[ModelT: ContentAddressedModel](
    repository: EvidenceRepository,
    path: Path,
    model: ModelT,
    model_type: type[ModelT],
    *,
    label: str,
) -> ModelT:
    with _translate_repository_errors(label=label):
        return repository.publish_canonical_model(
            repository.relative_path(path),
            model,
            TypeAdapter(model_type),
        ).model


def _load_monitor_model[ModelT: ContentAddressedModel](
    repository: EvidenceRepository,
    path: Path,
    model_type: type[ModelT],
    *,
    label: str,
) -> ModelT:
    with _translate_repository_errors(label=label):
        return repository.load_stored_canonical_model(
            repository.relative_path(path),
            TypeAdapter(model_type),
        ).model


def _bind_monitor_claim[ModelT: ContentAddressedModel](
    repository: EvidenceRepository,
    path: Path,
    claim: ModelT,
    model_type: type[ModelT],
    *,
    label: str,
) -> None:
    with _translate_repository_errors(label=f"{label} claim"):
        exists = repository.exists(repository.relative_path(path))
    if exists:
        existing = _load_monitor_model(
            repository,
            path,
            model_type,
            label=f"{label} claim",
        )
        if existing != claim:
            raise MonitorRuntimeCollisionError(f"{label} is already bound to different content")
        return
    try:
        _store_monitor_model(
            repository,
            path,
            claim,
            model_type,
            label=f"{label} claim",
        )
    except MonitorRuntimeCollisionError:
        existing = _load_monitor_model(
            repository,
            path,
            model_type,
            label=f"{label} claim",
        )
        if existing != claim:
            raise MonitorRuntimeCollisionError(f"{label} is already bound to different content") from None


def _monitor_claim_files(
    repository: EvidenceRepository,
    claims_root: Path,
) -> tuple[Path, ...]:
    with _translate_repository_errors(label="monitor runtime claims root"):
        relative_paths = repository.list_child_files(
            repository.relative_path(claims_root),
            filename="claim.json",
        )
    return tuple(repository.root.joinpath(*PurePosixPath(relative_path).parts) for relative_path in relative_paths)


def _manifest_object_path(root: Path, content_sha256: str) -> Path:
    validate_sha256(content_sha256)
    return root / "objects" / "manifests" / content_sha256 / "manifest.json"


def _manifest_claim_path(root: Path, cycle_id: str) -> Path:
    return root / "claims" / "cycles" / _logical_key(cycle_id) / "claim.json"


def _cycle_root(
    root: Path,
    manifest: _RuntimeManifestIdentity,
) -> Path:
    return root / "cycles" / _logical_key(manifest.cycle_plan.cycle_id)


def _flow_object_path(
    root: Path,
    manifest: _RuntimeManifestIdentity,
    content_sha256: str,
) -> Path:
    validate_sha256(content_sha256)
    return _cycle_root(root, manifest) / "flows" / "objects" / content_sha256 / "observation.json"


def _flow_claim_path(
    root: Path,
    manifest: _RuntimeManifestIdentity,
    flow_id: str,
) -> Path:
    return _cycle_root(root, manifest) / "flows" / "claims" / _logical_key(flow_id) / "claim.json"


def _reference_object_path(
    root: Path,
    manifest: _RuntimeManifestIdentity,
    content_sha256: str,
) -> Path:
    validate_sha256(content_sha256)
    return _cycle_root(root, manifest) / "references" / "objects" / content_sha256 / "event.json"


def _reference_claim_path(
    root: Path,
    manifest: _RuntimeManifestIdentity,
    reference_id: str,
) -> Path:
    return _cycle_root(root, manifest) / "references" / "claims" / _logical_key(reference_id) / "claim.json"


def _canary_activation_object_path(
    root: Path,
    manifest: _RuntimeManifestIdentity,
    content_sha256: str,
) -> Path:
    validate_sha256(content_sha256)
    return (
        _cycle_root(root, manifest)
        / "instrumentation"
        / "canary-surfaces"
        / "objects"
        / content_sha256
        / "activation.json"
    )


def _canary_activation_claim_path(
    root: Path,
    manifest: _RuntimeManifestIdentity,
    canary_commitment_sha256: str,
) -> Path:
    validate_sha256(canary_commitment_sha256)
    return (
        _cycle_root(root, manifest)
        / "instrumentation"
        / "canary-surfaces"
        / "claims"
        / canary_commitment_sha256
        / "claim.json"
    )


def _flow_activation_object_path(
    root: Path,
    manifest: _RuntimeManifestIdentity,
    content_sha256: str,
) -> Path:
    validate_sha256(content_sha256)
    return (
        _cycle_root(root, manifest)
        / "instrumentation"
        / "flow-collectors"
        / "objects"
        / content_sha256
        / "activation.json"
    )


def _flow_activation_claim_path(
    root: Path,
    manifest: _RuntimeManifestIdentity,
    rule: ForbiddenFlowRule,
) -> Path:
    return (
        _cycle_root(root, manifest)
        / "instrumentation"
        / "flow-collectors"
        / "claims"
        / _logical_key(json.dumps(_flow_rule_identity(rule)))
        / "claim.json"
    )


def _checkpoint_object_path(
    root: Path,
    manifest: _RuntimeManifestIdentity,
    content_sha256: str,
) -> Path:
    validate_sha256(content_sha256)
    return _cycle_root(root, manifest) / "checkpoints" / "objects" / content_sha256 / "checkpoint.json"


def _checkpoint_claim_path(
    root: Path,
    manifest: _RuntimeManifestIdentity,
    checkpoint: ProductionMonitorCheckpointKind,
) -> Path:
    return _cycle_root(root, manifest) / "checkpoints" / "claims" / checkpoint.value / "claim.json"


def _effect_permit_object_path(
    root: Path,
    manifest: _RuntimeManifestIdentity,
    content_sha256: str,
) -> Path:
    validate_sha256(content_sha256)
    return _cycle_root(root, manifest) / "effect-permit" / "objects" / content_sha256 / "permit.json"


def _effect_permit_claim_path(
    root: Path,
    manifest: _RuntimeManifestIdentity,
) -> Path:
    return _cycle_root(root, manifest) / "effect-permit" / "claim" / "claim.json"


def _closure_object_path(
    root: Path,
    manifest: _RuntimeManifestIdentity,
    content_sha256: str,
) -> Path:
    validate_sha256(content_sha256)
    return _cycle_root(root, manifest) / "closure" / "objects" / content_sha256 / "closure.json"


def _closure_claim_path(
    root: Path,
    manifest: _RuntimeManifestIdentity,
) -> Path:
    return _cycle_root(root, manifest) / "closure" / "claim" / "claim.json"


def _logical_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _flow_rule_identity(rule: ForbiddenFlowRule) -> tuple[str, str, str]:
    return (
        rule.source_principal_kind.value,
        rule.target_surface.value,
        rule.action.value,
    )
