# ABOUTME: Defines immutable identities, manifests, and verifier projections for proposal task packages.
# ABOUTME: Keeps package contracts independent from filesystem materialization and build-context inspection.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.evaluation_plane import (
    TaskVerifierFileInventoryEntry,
    TaskVerifierSurface,
    TaskVerifierSurfaceScope,
)
from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    validate_sha256,
)
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.validators import NonEmptyStr


class ProposalTaskPackageError(ValueError):
    """Reject unsafe inputs or an incomplete derived Harbor task package."""


class ProposalTaskPackageIdentity(FrozenStrictModel):
    """Exact governed identities authorized to enter one derived task package."""

    task_id: NonEmptyStr
    task_revision: str
    source_task_package_sha256: str
    sealed_task_package_sha256: str | None = None
    problem_view_sha256: str
    output_contract_sha256: str
    visibility: Visibility

    @field_validator(
        "task_revision",
        "source_task_package_sha256",
        "problem_view_sha256",
        "output_contract_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("sealed_task_package_sha256")
    @classmethod
    def validate_optional_hash(cls, value: str | None) -> str | None:
        return None if value is None else validate_sha256(value)


class ProposalTaskPackageFile(FrozenStrictModel):
    """One regular file deliberately retained in the derived task package."""

    path: NonEmptyStr
    sha256: str
    byte_size: int = Field(ge=0)
    role: Literal[
        "harbor_metadata",
        "agent_build_context",
        "public_output_contract",
        "verifier_only",
        "sealed_verifier_only",
    ]

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError("derived task package file paths must be contained and relative")
        return value

    @field_validator("sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return validate_sha256(value)


class ProposalTaskPackageManifest(LegacyContentAddressedModel):
    """Content-addressed inventory for one source-free Harbor task package."""

    schema_version: Literal[
        "aecbench.proposal-task-package.v1",
        "aecbench.proposal-task-package.v2",
    ] = "aecbench.proposal-task-package.v1"
    task_id: NonEmptyStr
    task_revision: str
    source_task_package_sha256: str
    sealed_task_package_sha256: str | None = None
    problem_view_sha256: str
    output_contract_sha256: str
    visibility: Visibility
    instruction_policy: Literal["generic_proposal_session"] = "generic_proposal_session"
    build_context_policy: Literal["source_free_dockerfile_only"] = "source_free_dockerfile_only"
    verifier_visibility: Literal["harbor_post_agent_only"] = "harbor_post_agent_only"
    files: tuple[ProposalTaskPackageFile, ...] = Field(min_length=1)

    @field_validator(
        "task_revision",
        "source_task_package_sha256",
        "problem_view_sha256",
        "output_contract_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("sealed_task_package_sha256")
    @classmethod
    def validate_optional_hash(cls, value: str | None) -> str | None:
        return None if value is None else validate_sha256(value)

    @field_validator("files")
    @classmethod
    def validate_files(
        cls,
        value: tuple[ProposalTaskPackageFile, ...],
    ) -> tuple[ProposalTaskPackageFile, ...]:
        paths = tuple(item.path for item in value)
        if paths != tuple(sorted(paths)):
            raise ValueError("derived task package files must be sorted by path")
        if len(paths) != len(set(paths)):
            raise ValueError("derived task package file paths must be unique")
        return value

    @model_validator(mode="after")
    def validate_required_surface(self) -> Self:
        by_path = {item.path: item for item in self.files}
        required_roles = {
            "instruction.md": "harbor_metadata",
            "task.toml": "harbor_metadata",
            "environment/.dockerignore": "agent_build_context",
            "environment/Dockerfile": "agent_build_context",
            "environment/output_contract.json": "public_output_contract",
            "tests/test.sh": "verifier_only",
        }
        for path, role in required_roles.items():
            item = by_path.get(path)
            if item is None or item.role != role:
                raise ValueError(f"derived task package requires {path!r} with role {role!r}")
        verifier_roles = {"verifier_only", "sealed_verifier_only"}
        if any(item.path.startswith("tests/") and item.role not in verifier_roles for item in self.files):
            raise ValueError("derived task verifier files must remain verifier-only")
        sealed_files = tuple(item for item in self.files if item.role == "sealed_verifier_only")
        if self.schema_version == "aecbench.proposal-task-package.v1":
            if self.sealed_task_package_sha256 is not None or sealed_files:
                raise ValueError("proposal task package v1 cannot bind sealed verifier assets")
        elif self.sealed_task_package_sha256 is None or not sealed_files:
            raise ValueError("proposal task package v2 requires a sealed package identity and verifier assets")
        return self


@dataclass(frozen=True)
class MaterializedProposalTaskPackage:
    """Published derived task directory and its independently reloadable manifest."""

    path: Path
    manifest: ProposalTaskPackageManifest


@dataclass(frozen=True)
class VerifiedProposalTaskBuildContext:
    """Exact manifest-bound bytes authorized for a proposal image build."""

    manifest: ProposalTaskPackageManifest
    payloads: tuple[tuple[str, bytes], ...]
    content_sha256: str


def project_proposal_task_verifier_surface(
    manifest: ProposalTaskPackageManifest,
) -> TaskVerifierSurface:
    """Project one derived task manifest onto its complete host-only verifier surface."""

    try:
        selected = ProposalTaskPackageManifest.model_validate(
            manifest.model_dump(mode="python"),
        )
    except ValueError as error:
        raise ProposalTaskPackageError(
            f"proposal task package manifest is invalid: {error}",
        ) from error
    verifier_roles = {"verifier_only", "sealed_verifier_only"}
    return TaskVerifierSurface(
        task_id=selected.task_id,
        task_revision=selected.task_revision,
        source_task_package_sha256=selected.source_task_package_sha256,
        sealed_task_package_sha256=selected.sealed_task_package_sha256,
        files=tuple(
            TaskVerifierFileInventoryEntry(
                path=item.path,
                sha256=item.sha256,
                byte_size=item.byte_size,
                role=("sealed_verifier_only" if item.role == "sealed_verifier_only" else "verifier_only"),
            )
            for item in selected.files
            if item.role in verifier_roles
        ),
    )


def assert_proposal_task_verifier_surface(
    *,
    manifest: ProposalTaskPackageManifest,
    expected_surface: TaskVerifierSurface,
) -> TaskVerifierSurface:
    """Fail closed unless one derived manifest matches an exact verifier surface."""

    try:
        expected = TaskVerifierSurface.model_validate(
            expected_surface.model_dump(mode="python"),
        )
    except ValueError as error:
        raise ProposalTaskPackageError(
            f"expected task verifier surface is invalid: {error}",
        ) from error
    observed = project_proposal_task_verifier_surface(manifest)
    if observed != expected:
        raise ProposalTaskPackageError(
            "derived proposal task verifier surface differs from the expected surface",
        )
    return observed


def assert_proposal_task_verifier_scope(
    *,
    manifests: tuple[ProposalTaskPackageManifest, ...],
    expected_scope: TaskVerifierSurfaceScope,
) -> TaskVerifierSurfaceScope:
    """Fail closed unless derived manifests cover one exact multi-task verifier scope."""

    if not manifests:
        raise ProposalTaskPackageError(
            "derived proposal task verifier scope requires at least one manifest",
        )
    try:
        expected = TaskVerifierSurfaceScope.model_validate(
            expected_scope.model_dump(mode="python"),
        )
    except ValueError as error:
        raise ProposalTaskPackageError(
            f"expected task verifier scope is invalid: {error}",
        ) from error

    observed_by_task: dict[tuple[str, str], TaskVerifierSurface] = {}
    for manifest in manifests:
        observed = project_proposal_task_verifier_surface(manifest)
        identity = (observed.task_id, observed.task_revision)
        prior = observed_by_task.get(identity)
        if prior is not None and prior != observed:
            raise ProposalTaskPackageError(
                "derived proposal manifests disagree on one task verifier surface",
            )
        observed_by_task[identity] = observed
    observed_surfaces = tuple(
        sorted(
            observed_by_task.values(),
            key=lambda surface: (surface.task_id, surface.task_revision),
        )
    )
    if observed_surfaces != expected.task_surfaces:
        raise ProposalTaskPackageError(
            "derived proposal task verifier scope differs from the expected scope",
        )
    return expected
