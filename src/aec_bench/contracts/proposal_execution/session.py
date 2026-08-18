# ABOUTME: Defines proposal-session plans, execution references, and terminal receipts.
# ABOUTME: Keeps node evidence, handoff evidence, and session invariants independent of graph contracts.

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.harness_instance import HarnessInstanceRef
from aec_bench.contracts.harness_kernel import KernelRef, validate_sha256
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.program_proposal.study import MatchedEvaluationCoordinate
from aec_bench.contracts.proposal_execution._canonical import (
    canonical_unique_models,
    canonical_unique_strings,
)
from aec_bench.contracts.proposal_execution.compilation import ProposalCompilationSuccess
from aec_bench.contracts.proposal_execution_types import (
    ProposalCandidateFailureCode,
    ProposalContractCheckStatus,
    ProposalNodeReceiptStatus,
    ProposalNodeSkipCause,
    ProposalSessionStatus,
)
from aec_bench.contracts.stage_execution import StageResourceEvidence
from aec_bench.contracts.validators import NonEmptyStr


class ProposalSessionPlan(LegacyContentAddressedModel):
    """One task-resident dispatch plan over a complete compiled proposal."""

    schema_version: Literal["aecbench.proposal-session-plan.v1"] = "aecbench.proposal-session-plan.v1"
    session_plan_id: NonEmptyStr
    compilation: ProposalCompilationSuccess
    planned_node_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    topological_order: tuple[NonEmptyStr, ...] = Field(min_length=1)

    @field_validator("planned_node_ids")
    @classmethod
    def canonicalize_planned_node_ids(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return canonical_unique_strings(value, label="planned proposal node ids")

    @field_validator("topological_order")
    @classmethod
    def validate_unique_topological_order(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("session topological order must be unique")
        return value

    @model_validator(mode="after")
    def validate_plan(self) -> ProposalSessionPlan:
        if self.planned_node_ids != self.compilation.proposal_graph.node_ids:
            raise ValueError("session plan must contain the exact proposal node set")
        if self.topological_order != self.compilation.proposal_graph.topological_order:
            raise ValueError("session plan must preserve proposal topological order")
        return self


class ProposalSessionExecutionRef(LegacyContentAddressedModel):
    """Runtime-known identity of one task-resident Harbor sandbox execution."""

    schema_version: Literal["aecbench.proposal-session-execution-ref.v1"] = "aecbench.proposal-session-execution-ref.v1"
    session_id: NonEmptyStr
    environment_session_id: NonEmptyStr
    backend: Literal["docker", "modal", "e2b", "daytona", "morph"]
    source_task_package_sha256: str
    runtime_task_package_sha256: str
    runtime_archive_content_sha256: str
    runtime_archive_sha256: str
    evaluation_coordinate: MatchedEvaluationCoordinate
    execution_schedule_sha256: str
    execution_assignment_sha256: str

    @field_validator(
        "source_task_package_sha256",
        "runtime_task_package_sha256",
        "runtime_archive_content_sha256",
        "runtime_archive_sha256",
        "execution_schedule_sha256",
        "execution_assignment_sha256",
    )
    @classmethod
    def validate_execution_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class ProposalNodeExecutionResultRef(LegacyContentAddressedModel):
    """Persisted child AdapterResult identity for one attempted proposal node."""

    schema_version: Literal["aecbench.proposal-node-execution-result-ref.v1"] = (
        "aecbench.proposal-node-execution-result-ref.v1"
    )
    node_id: NonEmptyStr
    session_relative_path: NonEmptyStr
    artifact_sha256: str
    byte_size: int = Field(ge=1)
    media_type: Literal["application/json"]

    @field_validator("artifact_sha256")
    @classmethod
    def validate_artifact_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("session_relative_path")
    @classmethod
    def validate_session_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or path.suffix.casefold() != ".json"
        ):
            raise ValueError("proposal child result requires a contained JSON artifact path")
        return value


class ProposalContractCheckResultRef(LegacyContentAddressedModel):
    """Persisted structural contract-check result for one attempted proposal node."""

    schema_version: Literal["aecbench.proposal-contract-check-result-ref.v1"] = (
        "aecbench.proposal-contract-check-result-ref.v1"
    )
    node_id: NonEmptyStr
    session_relative_path: NonEmptyStr
    artifact_sha256: str
    byte_size: int = Field(ge=1)
    media_type: Literal["application/json"]
    status: ProposalContractCheckStatus
    failure_code: ProposalCandidateFailureCode | None

    @field_validator("artifact_sha256")
    @classmethod
    def validate_artifact_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("session_relative_path")
    @classmethod
    def validate_session_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or path.suffix.casefold() != ".json"
        ):
            raise ValueError("proposal contract check requires a contained JSON artifact path")
        return value

    @model_validator(mode="after")
    def validate_status_shape(self) -> ProposalContractCheckResultRef:
        if self.status is ProposalContractCheckStatus.PASSED:
            if self.failure_code is not None:
                raise ValueError("passed proposal contract check cannot carry a failure code")
        elif self.failure_code is None:
            raise ValueError("failed proposal contract check requires a candidate failure code")
        return self


class ProposalContainerTransitionRef(LegacyContentAddressedModel):
    """Persisted proof that one model invocation received a fresh candidate container."""

    schema_version: Literal["aecbench.proposal-container-transition-ref.v1"] = (
        "aecbench.proposal-container-transition-ref.v1"
    )
    invocation_id: NonEmptyStr
    session_relative_path: NonEmptyStr
    artifact_sha256: str
    byte_size: int = Field(ge=1)
    media_type: Literal["application/json"]
    previous_container_identity: NonEmptyStr
    current_container_identity: NonEmptyStr
    runtime_archive_sha256: str
    previous_container_stopped: Literal[True]
    workspace_wiped: Literal[True]
    candidate_logs_wiped: Literal[True]

    @field_validator("artifact_sha256", "runtime_archive_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("session_relative_path")
    @classmethod
    def validate_session_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or path.suffix.casefold() != ".json"
        ):
            raise ValueError("proposal container transition requires a contained JSON artifact path")
        return value

    @model_validator(mode="after")
    def validate_fresh_container(self) -> ProposalContainerTransitionRef:
        if self.previous_container_identity == self.current_container_identity:
            raise ValueError("proposal container transition must produce a fresh container identity")
        return self


class ProposalHandoffArtifactRef(LegacyContentAddressedModel):
    """One canonical semantic output bound to an exact frozen graph edge."""

    schema_version: Literal["aecbench.proposal-handoff-artifact-ref.v1"] = "aecbench.proposal-handoff-artifact-ref.v1"
    handoff_id: NonEmptyStr
    producer_node_id: NonEmptyStr
    producer_output_id: NonEmptyStr
    consumer_node_id: NonEmptyStr
    consumer_input_id: NonEmptyStr
    session_relative_path: NonEmptyStr
    artifact_sha256: str
    byte_size: int = Field(ge=1)
    media_type: Literal["application/json"]

    @field_validator("artifact_sha256")
    @classmethod
    def validate_artifact_sha256(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("session_relative_path")
    @classmethod
    def validate_session_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or path.suffix.casefold() != ".json"
        ):
            raise ValueError("proposal handoff requires a contained JSON artifact path")
        return value


class ProposalNodeReceipt(LegacyContentAddressedModel):
    """Per-node evidence inside one task-resident proposal session."""

    schema_version: Literal["aecbench.proposal-node-receipt.v1"] = "aecbench.proposal-node-receipt.v1"
    receipt_id: NonEmptyStr
    session_id: NonEmptyStr
    session_execution_sha256: str
    session_plan_sha256: str
    compilation_sha256: str
    candidate_id: NonEmptyStr
    proposal_graph_sha256: str
    problem_view_sha256: str
    kernel_ref: KernelRef
    fixed_harness_ref: HarnessInstanceRef
    proposal_policy_sha256: str
    node_id: NonEmptyStr
    attempt: Literal[1] | None
    node_source_scope_sha256: str
    node_budget_reservation_sha256: str
    node_contract_sha256: str
    upstream_receipt_sha256s: tuple[str, ...] = ()
    status: ProposalNodeReceiptStatus
    invocation_id: NonEmptyStr | None
    container_transition: ProposalContainerTransitionRef | None
    node_context_sha256: str | None
    execution_request_sha256: str | None
    runtime_execution_attestation_sha256: str | None
    execution_result: ProposalNodeExecutionResultRef | None
    contract_check_result: ProposalContractCheckResultRef | None
    output_artifact_sha256: str | None
    emitted_handoffs: tuple[ProposalHandoffArtifactRef, ...] = ()
    failure_code: ProposalCandidateFailureCode | None
    resources: StageResourceEvidence | None
    skip_cause: ProposalNodeSkipCause | None
    causal_receipt_sha256s: tuple[str, ...] = ()

    @field_validator(
        "session_execution_sha256",
        "session_plan_sha256",
        "compilation_sha256",
        "proposal_graph_sha256",
        "problem_view_sha256",
        "proposal_policy_sha256",
        "node_source_scope_sha256",
        "node_budget_reservation_sha256",
        "node_contract_sha256",
    )
    @classmethod
    def validate_required_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("output_artifact_sha256")
    @classmethod
    def validate_optional_output_hash(cls, value: str | None) -> str | None:
        return None if value is None else validate_sha256(value)

    @field_validator(
        "node_context_sha256",
        "execution_request_sha256",
        "runtime_execution_attestation_sha256",
    )
    @classmethod
    def validate_optional_execution_hashes(
        cls,
        value: str | None,
    ) -> str | None:
        return None if value is None else validate_sha256(value)

    @field_validator("emitted_handoffs")
    @classmethod
    def canonicalize_emitted_handoffs(
        cls,
        value: tuple[ProposalHandoffArtifactRef, ...],
    ) -> tuple[ProposalHandoffArtifactRef, ...]:
        return canonical_unique_models(
            value,
            identity="handoff_id",
            label="proposal emitted handoffs",
        )

    @field_validator("upstream_receipt_sha256s", "causal_receipt_sha256s")
    @classmethod
    def canonicalize_receipt_hashes(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        return canonical_unique_strings(value, label="receipt identities")

    @model_validator(mode="after")
    def validate_status_shape(self) -> ProposalNodeReceipt:
        if self.execution_result is not None and self.execution_result.node_id != self.node_id:
            raise ValueError("proposal child result node id must match its receipt")
        if self.contract_check_result is not None and self.contract_check_result.node_id != self.node_id:
            raise ValueError("proposal contract check node id must match its receipt")
        if self.container_transition is not None and self.container_transition.invocation_id != self.invocation_id:
            raise ValueError("proposal container transition invocation must match its node receipt")
        if self.status is ProposalNodeReceiptStatus.COMPLETED:
            if (
                self.attempt != 1
                or self.invocation_id is None
                or self.container_transition is None
                or self.node_context_sha256 is None
                or self.execution_request_sha256 is None
                or self.runtime_execution_attestation_sha256 is None
                or self.execution_result is None
                or self.contract_check_result is None
                or self.contract_check_result.status is not ProposalContractCheckStatus.PASSED
                or self.output_artifact_sha256 is None
                or self.failure_code is not None
                or self.resources is None
                or self.skip_cause is not None
                or self.causal_receipt_sha256s
            ):
                raise ValueError(
                    "completed node receipt requires one invocation, fresh-container "
                    "transition, execution attestation, child result, passed contract "
                    "check, resources, output, and no failure"
                )
        elif self.status is ProposalNodeReceiptStatus.CANDIDATE_FAILURE:
            if (
                self.attempt != 1
                or self.invocation_id is None
                or self.container_transition is None
                or self.node_context_sha256 is None
                or self.execution_request_sha256 is None
                or self.runtime_execution_attestation_sha256 is None
                or self.execution_result is None
                or self.contract_check_result is None
                or self.contract_check_result.status is not ProposalContractCheckStatus.FAILED
                or self.output_artifact_sha256 is not None
                or self.emitted_handoffs
                or self.failure_code is None
                or self.contract_check_result.failure_code is not self.failure_code
                or self.resources is None
                or self.skip_cause is not None
                or self.causal_receipt_sha256s
            ):
                raise ValueError(
                    "candidate-failure node receipt requires one invocation, "
                    "fresh-container transition, execution attestation, child result, "
                    "matching failed contract check, resources, failure, and no output"
                )
        elif (
            self.attempt is not None
            or self.invocation_id is not None
            or self.container_transition is not None
            or self.node_context_sha256 is not None
            or self.execution_request_sha256 is not None
            or self.runtime_execution_attestation_sha256 is not None
            or self.execution_result is not None
            or self.contract_check_result is not None
            or self.output_artifact_sha256 is not None
            or self.emitted_handoffs
            or self.failure_code is not None
            or self.resources is not None
            or self.skip_cause is None
            or not self.causal_receipt_sha256s
        ):
            raise ValueError(
                "skipped node receipt requires an explicit causal skip and cannot "
                "claim an invocation, container transition, child result, contract "
                "check, resources, output, or failure"
            )
        return self


class ProposalSessionReceipt(LegacyContentAddressedModel):
    """Complete planned-node evidence for one task-resident candidate execution."""

    schema_version: Literal["aecbench.proposal-session-receipt.v1"] = "aecbench.proposal-session-receipt.v1"
    session_id: NonEmptyStr
    execution: ProposalSessionExecutionRef
    plan: ProposalSessionPlan
    planned_node_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    node_receipts: tuple[ProposalNodeReceipt, ...] = Field(min_length=1)
    status: ProposalSessionStatus
    final_output_artifact_sha256: str | None
    output_commit_attestation_sha256: str | None
    trial_record_permitted: bool
    failure_code: ProposalCandidateFailureCode | None

    @field_validator("planned_node_ids")
    @classmethod
    def canonicalize_planned_node_ids(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return canonical_unique_strings(value, label="session planned node ids")

    @field_validator("node_receipts")
    @classmethod
    def canonicalize_node_receipts(
        cls,
        value: tuple[ProposalNodeReceipt, ...],
    ) -> tuple[ProposalNodeReceipt, ...]:
        return canonical_unique_models(
            value,
            identity="node_id",
            label="proposal node receipts",
        )

    @field_validator(
        "final_output_artifact_sha256",
        "output_commit_attestation_sha256",
    )
    @classmethod
    def validate_optional_output_hash(cls, value: str | None) -> str | None:
        return None if value is None else validate_sha256(value)

    @model_validator(mode="after")
    def validate_complete_receipt(self) -> ProposalSessionReceipt:
        from aec_bench.contracts.proposal_session_verifier import (
            verify_proposal_session_receipt,
        )

        verify_proposal_session_receipt(self)
        return self
