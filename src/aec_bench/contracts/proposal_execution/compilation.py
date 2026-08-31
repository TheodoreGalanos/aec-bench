# ABOUTME: Defines deterministic proposal compilation success and rejection contracts.
# ABOUTME: Requires every current compilation record to bind its execution profile explicitly.

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    Field,
    field_validator,
    model_validator,
)

from aec_bench.contracts.content_address import ContentAddressedModel
from aec_bench.contracts.execution_program import (
    CompiledExecutionProgram,
    ExecutionProgram,
)
from aec_bench.contracts.harness_instance import HarnessInstanceRef
from aec_bench.contracts.harness_kernel import FrozenStrictModel, KernelRef, validate_sha256
from aec_bench.contracts.program_proposal.candidate import ProgramCandidateRef
from aec_bench.contracts.program_proposal.freeze import ProposalFreeze
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


class _ProfileBoundProposalCompilation(ContentAddressedModel):
    """Shared current execution-profile binding."""

    execution_profile: ProposalExecutionProfile


class ProposalCompilationSuccess(_ProfileBoundProposalCompilation):
    """Successful deterministic lowering of one exact frozen proposal."""

    schema_version: Literal["aecbench.proposal-compilation-success.v2"] = "aecbench.proposal-compilation-success.v2"
    compilation_id: NonEmptyStr
    status: Literal[ProposalCompilationStatus.COMPILED]
    candidate_ref: ProgramCandidateRef
    raw_proposal_artifact_sha256: str
    proposal_graph: ExecutableCandidateGraph
    proposal_freeze: ProposalFreeze
    freeze_authority_event_sha256: str
    kernel_ref: KernelRef
    fixed_harness_ref: HarnessInstanceRef
    surface_id: NonEmptyStr
    lowering_policy_sha256: str
    task_snapshot_sha256: str
    source_scope_manifest: ProposalSourceScopeManifest
    budget_plan: CandidateBudgetPlan
    lowered_program: ExecutionProgram
    compiled_program: CompiledExecutionProgram

    @field_validator(
        "freeze_authority_event_sha256",
        "raw_proposal_artifact_sha256",
        "lowering_policy_sha256",
        "task_snapshot_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_compilation(self) -> ProposalCompilationSuccess:
        from aec_bench.contracts.proposal_compilation_verifier import (
            verify_proposal_compilation_success,
        )

        verify_proposal_compilation_success(
            self,
            profile=self.execution_profile,
        )
        return self


class ProposalCompilationRejection(_ProfileBoundProposalCompilation):
    """Learner-owned compile rejection that cannot authorize execution or a TrialRecord."""

    schema_version: Literal["aecbench.proposal-compilation-rejection.v2"] = "aecbench.proposal-compilation-rejection.v2"
    compilation_id: NonEmptyStr
    status: Literal[ProposalCompilationStatus.REJECTED]
    candidate_ref: ProgramCandidateRef
    raw_proposal_artifact_sha256: str
    proposal_freeze: ProposalFreeze
    freeze_authority_event_sha256: str
    kernel_ref: KernelRef
    fixed_harness_ref: HarnessInstanceRef
    surface_id: NonEmptyStr
    lowering_policy_sha256: str
    task_snapshot_sha256: str
    diagnostic: ProposalCompileDiagnostic
    trial_record_permitted: Literal[False]
    run_bundle_permitted: Literal[False]

    @field_validator(
        "raw_proposal_artifact_sha256",
        "freeze_authority_event_sha256",
        "lowering_policy_sha256",
        "task_snapshot_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_rejection(self) -> ProposalCompilationRejection:
        from aec_bench.contracts.proposal_compilation_verifier import (
            verify_proposal_compilation_rejection,
        )

        verify_proposal_compilation_rejection(
            self,
            profile=self.execution_profile,
        )
        return self


ProposalCompilationRecord = Annotated[
    ProposalCompilationSuccess | ProposalCompilationRejection,
    Field(discriminator="status"),
]
