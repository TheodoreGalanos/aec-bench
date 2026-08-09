# ABOUTME: Defines phase-neutral evaluation task identities, cohorts, bindings, and retirement.
# ABOUTME: Keeps cohort size and evaluation seeds in content-addressed manifest data.

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    FrozenStrictModel,
    canonical_content_sha256,
    validate_sha256,
)
from aec_bench.contracts.run_bundle import TaskSnapshotRef
from aec_bench.contracts.validators import NonEmptyStr


class EvaluationCohortPurpose(StrEnum):
    """Stable scientific purpose of one released evaluation cohort."""

    CALIBRATION = "calibration"
    DEVELOPMENT = "development"
    ACCEPTANCE = "acceptance"
    STRUCTURAL_HOLDOUT = "structural_holdout"
    TRANSFER = "transfer"


class EvaluationTaskIdentity(ContentAddressedModel):
    """One public task identity paired with its hidden evaluation lineage."""

    schema_version: Literal["aecbench.evaluation-task-identity.v3"] = "aecbench.evaluation-task-identity.v3"
    task_id: NonEmptyStr
    public_snapshot: TaskSnapshotRef
    public_task_snapshot_sha256: str
    sealed_task_package_sha256: str
    review_lineage_id: str
    review_sidecar_sha256: str
    declared_surface_sha256: str

    @field_validator(
        "public_task_snapshot_sha256",
        "sealed_task_package_sha256",
        "review_lineage_id",
        "review_sidecar_sha256",
        "declared_surface_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_public_identity(self) -> Self:
        if self.public_snapshot.task_id != self.task_id:
            raise ValueError("evaluation task id must match its public snapshot")
        if self.public_snapshot.task_review is not None:
            raise ValueError("evaluation public snapshot cannot contain a task review")
        expected = canonical_content_sha256(
            {
                "task_id": self.public_snapshot.task_id,
                "definition_sha256": self.public_snapshot.definition_sha256,
                "package_sha256": self.public_snapshot.package_sha256,
            }
        )
        if self.public_task_snapshot_sha256 != expected:
            raise ValueError(
                "evaluation public snapshot identity does not match its exact bytes",
            )
        if self.public_snapshot.package_sha256 == self.sealed_task_package_sha256:
            raise ValueError("evaluation public and sealed task packages must be distinct")
        if self.review_lineage_id != self.review_sidecar_sha256:
            raise ValueError("evaluation review lineage must match its exact task-review sidecar")
        return self


class EvaluationCohortTask(ContentAddressedModel):
    """One cohort task and its preregistered evaluation seeds."""

    schema_version: Literal["aecbench.evaluation-cohort-task.v2"] = "aecbench.evaluation-cohort-task.v2"
    task: EvaluationTaskIdentity
    evaluation_seeds: tuple[int, ...] = Field(min_length=1)

    @field_validator("evaluation_seeds")
    @classmethod
    def canonicalize_evaluation_seeds(
        cls,
        value: tuple[int, ...],
    ) -> tuple[int, ...]:
        if any(seed < 0 for seed in value):
            raise ValueError("evaluation cohort seeds must be non-negative")
        if len(value) != len(set(value)):
            raise ValueError("evaluation cohort seeds must be unique")
        return tuple(sorted(value))


class EvaluationCohortManifest(ContentAddressedModel):
    """Released task cohort whose size and coordinates are supplied as data."""

    schema_version: Literal["aecbench.evaluation-cohort-manifest.v2"] = "aecbench.evaluation-cohort-manifest.v2"
    cohort_id: NonEmptyStr
    evaluation_generation: NonEmptyStr
    purpose: EvaluationCohortPurpose
    structural_split_sha256: str
    structural_task_manifest_sha256: str
    tasks: tuple[EvaluationCohortTask, ...] = Field(min_length=1)

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
        value: tuple[EvaluationCohortTask, ...],
    ) -> tuple[EvaluationCohortTask, ...]:
        identity_fields = (
            ("task identities", tuple(item.task.task_id for item in value)),
            (
                "public snapshot identities",
                tuple(item.task.public_task_snapshot_sha256 for item in value),
            ),
            (
                "public package identities",
                tuple(item.task.public_snapshot.package_sha256 for item in value),
            ),
            (
                "sealed package identities",
                tuple(item.task.sealed_task_package_sha256 for item in value),
            ),
            (
                "review lineage identities",
                tuple(item.task.review_lineage_id for item in value),
            ),
        )
        for label, identities in identity_fields:
            if len(identities) != len(set(identities)):
                raise ValueError(f"evaluation cohort {label} must be unique")
        public_packages = {item.task.public_snapshot.package_sha256 for item in value}
        sealed_packages = {item.task.sealed_task_package_sha256 for item in value}
        if public_packages.intersection(sealed_packages):
            raise ValueError(
                "evaluation cohort public and sealed package identities must be disjoint",
            )
        return tuple(sorted(value, key=lambda item: item.task.task_id))


class EvaluationCohortBinding(FrozenStrictModel):
    """Exact released cohort identity attached to generated and executed candidates."""

    schema_version: Literal["aecbench.evaluation-cohort-binding.v2"] = "aecbench.evaluation-cohort-binding.v2"
    cohort_id: NonEmptyStr
    evaluation_generation: NonEmptyStr
    cohort_sha256: str
    release_authority_event_sha256: str

    @field_validator(
        "cohort_sha256",
        "release_authority_event_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class EvaluationCohortRetirement(ContentAddressedModel):
    """Human-signable retirement of one exact released evaluation cohort."""

    schema_version: Literal["aecbench.evaluation-cohort-retirement.v2"] = "aecbench.evaluation-cohort-retirement.v2"
    retirement_id: NonEmptyStr
    cohort: EvaluationCohortBinding


def validate_cohort_binding(
    cohort: EvaluationCohortManifest,
    binding: EvaluationCohortBinding,
) -> None:
    """Require a binding to identify one exact cohort manifest."""

    if (
        binding.cohort_id != cohort.cohort_id
        or binding.evaluation_generation != cohort.evaluation_generation
        or binding.cohort_sha256 != cohort.content_sha256
    ):
        raise ValueError("evaluation cohort binding differs from its exact manifest")
