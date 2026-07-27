# ABOUTME: Preserves exact v1 task identities for the retired Phase 9.1a provider calibration.
# ABOUTME: Keeps its two-task cardinality and historical schema bytes available only for replay.

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    canonical_content_sha256,
    validate_sha256,
)
from aec_bench.contracts.run_bundle import TaskSnapshotRef
from aec_bench.contracts.validators import NonEmptyStr


class ProviderCalibrationTask(ContentAddressedModel):
    """One exact graph-hidden public task identity eligible only for provider calibration."""

    schema_version: Literal["aecbench.provider-calibration-task.v1"] = "aecbench.provider-calibration-task.v1"
    task_id: NonEmptyStr
    public_snapshot: TaskSnapshotRef
    public_task_snapshot_sha256: str
    sealed_task_package_sha256: str
    world_lineage_id: str
    world_package_sha256: str
    topology_signature_sha256: str

    @field_validator(
        "public_task_snapshot_sha256",
        "sealed_task_package_sha256",
        "world_lineage_id",
        "world_package_sha256",
        "topology_signature_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_public_identity(self) -> Self:
        if self.public_snapshot.task_id != self.task_id:
            raise ValueError("provider calibration task id must match its public snapshot")
        if self.public_snapshot.world is not None:
            raise ValueError("provider calibration public snapshot cannot contain a task world")
        expected = canonical_content_sha256(
            {
                "task_id": self.public_snapshot.task_id,
                "definition_sha256": self.public_snapshot.definition_sha256,
                "package_sha256": self.public_snapshot.package_sha256,
            }
        )
        if self.public_task_snapshot_sha256 != expected:
            raise ValueError("provider calibration public snapshot identity does not match its exact bytes")
        if self.public_snapshot.package_sha256 == self.sealed_task_package_sha256:
            raise ValueError("provider calibration public and sealed task packages must be distinct")
        if self.world_lineage_id != self.world_package_sha256:
            raise ValueError("provider calibration world lineage must match its exact world package")
        return self


class ProviderCalibrationTaskManifest(ContentAddressedModel):
    """The exact two public tasks and one seed retired after one calibration generation."""

    schema_version: Literal["aecbench.provider-calibration-task-manifest.v1"] = (
        "aecbench.provider-calibration-task-manifest.v1"
    )
    manifest_id: NonEmptyStr
    evaluation_generation: NonEmptyStr
    structural_split_sha256: str
    structural_task_manifest_sha256: str
    evaluation_seed: int = Field(ge=0)
    tasks: tuple[ProviderCalibrationTask, ...]

    @field_validator(
        "structural_split_sha256",
        "structural_task_manifest_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("tasks")
    @classmethod
    def canonicalize_tasks(
        cls,
        value: tuple[ProviderCalibrationTask, ...],
    ) -> tuple[ProviderCalibrationTask, ...]:
        if len(value) != 2:
            raise ValueError("provider calibration manifest requires exactly two public tasks")
        identity_fields = (
            ("task identities", tuple(task.task_id for task in value)),
            (
                "public snapshot identities",
                tuple(task.public_task_snapshot_sha256 for task in value),
            ),
            (
                "public package identities",
                tuple(task.public_snapshot.package_sha256 for task in value),
            ),
            (
                "sealed package identities",
                tuple(task.sealed_task_package_sha256 for task in value),
            ),
            ("world lineage identities", tuple(task.world_lineage_id for task in value)),
        )
        for label, identities in identity_fields:
            if len(identities) != len(set(identities)):
                raise ValueError(f"provider calibration {label} must be unique")
        public_packages = {task.public_snapshot.package_sha256 for task in value}
        sealed_packages = {task.sealed_task_package_sha256 for task in value}
        if public_packages.intersection(sealed_packages):
            raise ValueError("provider calibration public and sealed package identities must be disjoint")
        return tuple(sorted(value, key=lambda task: task.task_id))


class ProviderCalibrationManifestRetirement(ContentAddressedModel):
    """Human-signable retirement of one exact provider-calibration generation."""

    schema_version: Literal["aecbench.provider-calibration-manifest-retirement.v1"] = (
        "aecbench.provider-calibration-manifest-retirement.v1"
    )
    retirement_id: NonEmptyStr
    manifest_id: NonEmptyStr
    evaluation_generation: NonEmptyStr
    manifest_sha256: str
    release_authority_event_sha256: str

    @field_validator(
        "manifest_sha256",
        "release_authority_event_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)
