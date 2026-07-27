# ABOUTME: Defines deterministic proposal compilation success and rejection contracts.
# ABOUTME: Preserves explicit execution-profile binding and profile-less v1 replay validation.

from __future__ import annotations

from typing import Annotated, Any, Literal, TypeVar

from pydantic import (
    Field,
    SerializerFunctionWrapHandler,
    ValidationInfo,
    field_validator,
    model_serializer,
    model_validator,
)

from aec_bench.contracts.execution_program import (
    CompiledExecutionProgram,
    ExecutionProgram,
)
from aec_bench.contracts.harness_instance import HarnessInstanceRef
from aec_bench.contracts.harness_kernel import ContentAddressedModel, FrozenStrictModel, validate_sha256
from aec_bench.contracts.program_proposal import ProgramCandidateRef, ProposalFreeze
from aec_bench.contracts.proposal_execution._canonical import canonical_unique_strings
from aec_bench.contracts.proposal_execution.graph import ExecutableCandidateGraph
from aec_bench.contracts.proposal_execution_budget import CandidateBudgetPlan
from aec_bench.contracts.proposal_execution_context import ProposalSourceScopeManifest
from aec_bench.contracts.proposal_execution_profile import ProposalExecutionProfile
from aec_bench.contracts.proposal_execution_types import (
    ProposalCompilationStatus,
    ProposalCompileRejectionCode,
    ProposalDiagnosticVisibility,
)
from aec_bench.contracts.validators import NonEmptyStr


class ProposalCompileDiagnostic(FrozenStrictModel):
    """Candidate-owned, host-authored diagnostic for a deterministic rejection."""

    owner: Literal["candidate"]
    code: ProposalCompileRejectionCode
    subject_ids: tuple[NonEmptyStr, ...] = ()
    message: NonEmptyStr
    feedback_visibility: ProposalDiagnosticVisibility

    @field_validator("subject_ids")
    @classmethod
    def canonicalize_subject_ids(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return canonical_unique_strings(value, label="diagnostic subject ids")


_V1_COMPATIBILITY_PROFILE_CONTEXT_KEY = "proposal_execution_v1_compatibility_profile"


class _ProfileBoundProposalCompilation(ContentAddressedModel):
    """Shared profile binding with an explicit profile-less v1 replay path."""

    execution_profile: ProposalExecutionProfile | None = None

    @model_serializer(mode="wrap")
    def serialize_with_profileless_v1_compatibility(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, object]:
        payload = handler(self)
        if not isinstance(payload, dict):
            raise TypeError("proposal compilation serialization must produce an object")
        if self.execution_profile is None:
            payload.pop("execution_profile", None)
        return payload

    def _profile_for_validation(
        self,
        info: ValidationInfo,
    ) -> ProposalExecutionProfile:
        from aec_bench.contracts.proposal_compilation_verifier import (
            resolve_proposal_execution_profile,
        )

        return resolve_proposal_execution_profile(
            self.execution_profile,
            info=info,
        )


class ProposalCompilationSuccess(_ProfileBoundProposalCompilation):
    """Successful deterministic lowering of one exact frozen proposal."""

    schema_version: Literal[
        "aecbench.proposal-compilation-success.v1",
        "aecbench.proposal-compilation-success.v2",
    ] = "aecbench.proposal-compilation-success.v2"
    compilation_id: NonEmptyStr
    status: Literal[ProposalCompilationStatus.COMPILED]
    candidate_ref: ProgramCandidateRef
    raw_proposal_artifact_sha256: str
    proposal_graph: ExecutableCandidateGraph
    proposal_freeze: ProposalFreeze
    freeze_authority_event_sha256: str
    kernel_sha256: str
    fixed_harness_ref: HarnessInstanceRef
    surface_sha256: str
    lowering_policy_sha256: str
    task_snapshot_sha256: str
    source_scope_manifest: ProposalSourceScopeManifest
    budget_plan: CandidateBudgetPlan
    lowered_program: ExecutionProgram
    compiled_program: CompiledExecutionProgram

    @field_validator(
        "freeze_authority_event_sha256",
        "raw_proposal_artifact_sha256",
        "kernel_sha256",
        "surface_sha256",
        "lowering_policy_sha256",
        "task_snapshot_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_compilation(self, info: ValidationInfo) -> ProposalCompilationSuccess:
        from aec_bench.contracts.proposal_compilation_verifier import (
            verify_proposal_compilation_success,
        )

        execution_profile = self._profile_for_validation(info)
        verify_proposal_compilation_success(
            self,
            profile=execution_profile,
        )
        return self


class ProposalCompilationRejection(_ProfileBoundProposalCompilation):
    """Learner-owned compile rejection that cannot authorize execution or a TrialRecord."""

    schema_version: Literal[
        "aecbench.proposal-compilation-rejection.v1",
        "aecbench.proposal-compilation-rejection.v2",
    ] = "aecbench.proposal-compilation-rejection.v2"
    compilation_id: NonEmptyStr
    status: Literal[ProposalCompilationStatus.REJECTED]
    candidate_ref: ProgramCandidateRef
    raw_proposal_artifact_sha256: str
    proposal_freeze: ProposalFreeze
    freeze_authority_event_sha256: str
    kernel_sha256: str
    fixed_harness_ref: HarnessInstanceRef
    surface_sha256: str
    lowering_policy_sha256: str
    task_snapshot_sha256: str
    diagnostic: ProposalCompileDiagnostic
    trial_record_permitted: Literal[False]
    run_bundle_permitted: Literal[False]

    @field_validator(
        "raw_proposal_artifact_sha256",
        "freeze_authority_event_sha256",
        "kernel_sha256",
        "surface_sha256",
        "lowering_policy_sha256",
        "task_snapshot_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_rejection(self, info: ValidationInfo) -> ProposalCompilationRejection:
        from aec_bench.contracts.proposal_compilation_verifier import (
            verify_proposal_compilation_rejection,
        )

        execution_profile = self._profile_for_validation(info)
        verify_proposal_compilation_rejection(
            self,
            profile=execution_profile,
        )
        return self


ProposalCompilationRecord = Annotated[
    ProposalCompilationSuccess | ProposalCompilationRejection,
    Field(discriminator="status"),
]

_ProposalCompilationT = TypeVar(
    "_ProposalCompilationT",
    bound=_ProfileBoundProposalCompilation,
)


def validate_proposal_compilation_v1_compatibility(
    model_type: type[_ProposalCompilationT],
    value: Any,
    *,
    profile: ProposalExecutionProfile,
) -> _ProposalCompilationT:
    """Validate historical profile-less v1 bytes against one explicit profile."""

    return model_type.model_validate(
        value,
        context={_V1_COMPATIBILITY_PROFILE_CONTEXT_KEY: profile},
    )
