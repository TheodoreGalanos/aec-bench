# ABOUTME: Defines content-addressed records for governed proposal dispatch authorization.
# ABOUTME: Enforces exact freeze, bundle, host, task, runtime, and Harbor-job identity joins.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

from pydantic import field_validator, model_validator

from aec_bench.contracts.authority import (
    AuthorityEvent,
    BasisReference,
    OriginStamp,
)
from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    canonical_content_sha256,
    validate_sha256,
)
from aec_bench.contracts.program_proposal.candidate import ProgramCandidateRef
from aec_bench.contracts.program_proposal.study import MatchedEvaluationCoordinate
from aec_bench.contracts.task_definition import TaskDefinition
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.harness.proposal_session_config import ProposalSessionHostConfig
from aec_bench.harness.proposal_task_packaging.contracts import (
    ProposalTaskPackageManifest,
)
from aec_bench.meta_harness.program_proposal_compilation import (
    ProposalRunSessionBundle,
)
from aec_bench.meta_harness.proposal_dispatch.binding_validation import (
    candidate_is_exactly_frozen,
    validate_evaluation_coordinate,
)
from aec_bench.meta_harness.proposal_dispatch.errors import (
    ProposalDispatchGovernanceError as ProposalDispatchGovernanceError,
)
from aec_bench.meta_harness.proposal_dispatch.serialization import (
    load_canonical_job_json,
    load_canonical_task_json,
    validate_recorded_job_surface,
)


class GovernedProposalDispatch(ContentAddressedModel):
    """Exact host-validated proposal dispatch surface authorized for one provider job."""

    schema_version: Literal["aecbench.governed-proposal-dispatch.v1"] = "aecbench.governed-proposal-dispatch.v1"
    dispatch_id: NonEmptyStr
    candidate_ref: ProgramCandidateRef
    evaluation_coordinate: MatchedEvaluationCoordinate
    execution_schedule_sha256: str
    execution_assignment_sha256: str
    freeze_sha256: str
    freeze_authority_event_sha256: str
    bundle: ProposalRunSessionBundle
    bundle_sha256: str
    compilation_sha256: str
    host_config: ProposalSessionHostConfig
    host_config_sha256: str
    runtime_archive_path: NonEmptyStr
    runtime_archive_sha256: str
    runtime_archive_content_sha256: str
    derived_task_path: NonEmptyStr
    task_id: NonEmptyStr
    task_revision: str
    source_task_package_sha256: str
    derived_task_json: NonEmptyStr
    derived_task_sha256: str
    derived_task_manifest: ProposalTaskPackageManifest
    harbor_job_config_json: NonEmptyStr
    harbor_job_config_sha256: str
    compile_authority_event_sha256: str

    @field_validator(
        "freeze_sha256",
        "freeze_authority_event_sha256",
        "execution_schedule_sha256",
        "execution_assignment_sha256",
        "bundle_sha256",
        "compilation_sha256",
        "host_config_sha256",
        "runtime_archive_sha256",
        "runtime_archive_content_sha256",
        "task_revision",
        "source_task_package_sha256",
        "derived_task_sha256",
        "harbor_job_config_sha256",
        "compile_authority_event_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_exact_bindings(self) -> Self:
        _validate_candidate_and_freeze(self)
        _validate_bundle_and_host(self)
        _validate_runtime(self)
        derived_task = _validate_task_identity(self)
        if canonical_content_sha256(derived_task.model_dump(mode="json")) != self.derived_task_sha256:
            raise ValueError("governed dispatch derived task identity differs")
        job = load_canonical_job_json(self.harbor_job_config_json)
        if canonical_content_sha256(job) != self.harbor_job_config_sha256:
            raise ValueError("governed dispatch Harbor job identity differs")
        validate_recorded_job_surface(record=self, job=job)
        return self


@dataclass(frozen=True)
class GovernedProposalDispatchAuthorization:
    """Exact replay handle for one freeze-to-provider-dispatch authority chain."""

    dispatch: GovernedProposalDispatch
    freeze_authority_event: AuthorityEvent
    freeze_authority_basis: BasisReference
    freeze_authority_origin: OriginStamp
    execution_schedule_basis: BasisReference
    execution_schedule_origin: OriginStamp
    execution_assignment_basis: BasisReference
    execution_assignment_origin: OriginStamp
    compilation_basis: BasisReference
    compilation_origin: OriginStamp
    compile_event: AuthorityEvent
    compile_event_basis: BasisReference
    compile_event_origin: OriginStamp
    dispatch_basis: BasisReference
    dispatch_origin: OriginStamp
    provider_dispatch_event: AuthorityEvent

    @property
    def content_sha256(self) -> str:
        """Return the canonical identity of the complete authority chain."""

        return canonical_content_sha256(
            {
                "dispatch_sha256": self.dispatch.content_sha256,
                "freeze_authority_event_sha256": (self.freeze_authority_event.content_sha256),
                "freeze_authority_basis": (self.freeze_authority_basis.model_dump(mode="json")),
                "freeze_authority_origin_sha256": (self.freeze_authority_origin.content_sha256),
                "execution_schedule_basis": (self.execution_schedule_basis.model_dump(mode="json")),
                "execution_schedule_origin_sha256": (self.execution_schedule_origin.content_sha256),
                "execution_assignment_basis": (self.execution_assignment_basis.model_dump(mode="json")),
                "execution_assignment_origin_sha256": (self.execution_assignment_origin.content_sha256),
                "compilation_basis": (self.compilation_basis.model_dump(mode="json")),
                "compilation_origin_sha256": (self.compilation_origin.content_sha256),
                "compile_event_sha256": self.compile_event.content_sha256,
                "compile_event_basis": (self.compile_event_basis.model_dump(mode="json")),
                "compile_event_origin_sha256": (self.compile_event_origin.content_sha256),
                "dispatch_basis": self.dispatch_basis.model_dump(mode="json"),
                "dispatch_origin_sha256": (self.dispatch_origin.content_sha256),
                "provider_dispatch_event_sha256": (self.provider_dispatch_event.content_sha256),
            }
        )


def _validate_candidate_and_freeze(record: GovernedProposalDispatch) -> None:
    compilation = record.bundle.compilation
    if record.candidate_ref != compilation.candidate_ref or not candidate_is_exactly_frozen(
        freeze=compilation.proposal_freeze,
        candidate_ref=record.candidate_ref,
    ):
        raise ValueError(
            "governed dispatch candidate differs from the exact compiled candidate",
        )
    validate_evaluation_coordinate(
        coordinate=record.evaluation_coordinate,
        freeze=compilation.proposal_freeze,
    )
    if (
        record.freeze_sha256 != compilation.proposal_freeze.content_sha256
        or record.freeze_authority_event_sha256 != compilation.freeze_authority_event_sha256
    ):
        raise ValueError(
            "governed dispatch compilation differs from its freeze authority",
        )


def _validate_bundle_and_host(record: GovernedProposalDispatch) -> None:
    compilation = record.bundle.compilation
    if (
        record.bundle_sha256 != record.bundle.content_sha256
        or record.compilation_sha256 != compilation.content_sha256
        or record.host_config.bundle_content_sha256 != record.bundle.content_sha256
    ):
        raise ValueError(
            "governed dispatch host configuration differs from the exact bundle",
        )
    if record.host_config_sha256 != canonical_content_sha256(
        record.host_config.model_dump(mode="json"),
    ):
        raise ValueError("governed dispatch host configuration identity differs")
    if (
        record.host_config.evaluation_coordinate != record.evaluation_coordinate
        or record.host_config.execution_schedule_sha256 != record.execution_schedule_sha256
        or record.host_config.execution_assignment_sha256 != record.execution_assignment_sha256
    ):
        raise ValueError(
            "governed dispatch host configuration evaluation coordinate or assignment differs",
        )


def _validate_runtime(record: GovernedProposalDispatch) -> None:
    if (
        record.runtime_archive_path != record.host_config.runtime_archive_path
        or record.runtime_archive_sha256 != record.host_config.runtime_archive_sha256
        or record.runtime_archive_content_sha256 != record.host_config.runtime_archive_content_sha256
    ):
        raise ValueError(
            "governed dispatch runtime identity differs from the host configuration",
        )
    if not Path(record.derived_task_path).is_absolute():
        raise ValueError("governed dispatch derived task path must be absolute")


def _validate_task_identity(
    record: GovernedProposalDispatch,
) -> TaskDefinition:
    manifest = record.derived_task_manifest
    derived_task = load_canonical_task_json(record.derived_task_json)
    if (
        record.task_id != record.bundle.task_snapshot.task_id
        or record.task_id != manifest.task_id
        or record.task_id != derived_task.task_id
        or record.task_revision != record.bundle.task_snapshot.definition_sha256
        or record.task_revision != manifest.task_revision
        or record.source_task_package_sha256 != record.bundle.task_snapshot.package_sha256
        or record.source_task_package_sha256 != manifest.source_task_package_sha256
        or record.source_task_package_sha256 != record.host_config.source_task_package_sha256
    ):
        raise ValueError(
            "governed dispatch task identity differs from the exact bundle",
        )
    return derived_task
