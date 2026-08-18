# ABOUTME: Validates and persists per-node evidence for one proposal-owned execution session.
# ABOUTME: Separates closed candidate failures from provider, host, identity, and integrity faults.

from __future__ import annotations

import hashlib
import math
import os
import stat
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path, PurePosixPath
from typing import Literal, Protocol

from pydantic import JsonValue, ValidationError, field_validator

from aec_bench.adapters.base import (
    AdapterFailureKind,
    AdapterResult,
    AdapterStopReason,
)
from aec_bench.contracts.adapter_execution import TranscriptEvent
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.harness_kernel import (
    validate_sha256,
)
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.pricing import estimate_cost_usd
from aec_bench.contracts.proposal_execution.graph import ProposalHandoff
from aec_bench.contracts.proposal_execution.session import (
    ProposalContainerTransitionRef,
    ProposalContractCheckResultRef,
    ProposalHandoffArtifactRef,
    ProposalNodeExecutionResultRef,
)
from aec_bench.contracts.proposal_execution_types import ProposalCandidateFailureCode, ProposalContractCheckStatus
from aec_bench.contracts.stage_execution import StageResourceEvidence
from aec_bench.contracts.trajectory import MetaHarnessTrajectoryContext
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.experimentation.proposals.node_context import (
    PersistedProposalHandoffArtifact,
)
from aec_bench.experimentation.proposals.node_contract import CanonicalProposalHandoff
from aec_bench.experimentation.proposals.session_serialization import (
    canonical_json_bytes,
    json_compatible,
)
from aec_bench.harness.execution_payload import (
    ExecutionBundle,
    RuntimeExecutionAttestation,
    execution_request_sha256,
)
from aec_bench.ledger.durability import fsync_directory, mkdir_durable

_FAILURE_KIND_CODES = {
    AdapterFailureKind.TURN_LIMIT_REACHED: ProposalCandidateFailureCode.AGENT_TURN_BUDGET_EXHAUSTED,
    AdapterFailureKind.TOKEN_BUDGET_REACHED: ProposalCandidateFailureCode.TOKEN_BUDGET_EXHAUSTED,
    AdapterFailureKind.BILLABLE_INPUT_BUDGET_REACHED: ProposalCandidateFailureCode.TOKEN_BUDGET_EXHAUSTED,
    AdapterFailureKind.COST_BUDGET_REACHED: ProposalCandidateFailureCode.COST_BUDGET_EXHAUSTED,
    AdapterFailureKind.SUBCALL_LIMIT_REACHED: ProposalCandidateFailureCode.TOOL_CALL_BUDGET_EXHAUSTED,
    AdapterFailureKind.TOOL_CALL_LIMIT_REACHED: ProposalCandidateFailureCode.TOOL_CALL_BUDGET_EXHAUSTED,
    AdapterFailureKind.CONTEXT_LIMIT_REACHED: ProposalCandidateFailureCode.CONTEXT_BUDGET_EXHAUSTED,
    AdapterFailureKind.TIMEOUT: ProposalCandidateFailureCode.RUNTIME_BUDGET_EXHAUSTED,
    AdapterFailureKind.MISSING_OUTPUT: ProposalCandidateFailureCode.OUTPUT_COMMIT_MISSING,
    AdapterFailureKind.UNDECLARED_TOOL_REQUEST: ProposalCandidateFailureCode.CONTRACT_CHECK_FAILED,
}
_STOP_REASON_CODES = {
    AdapterStopReason.ITERATION_CAP: ProposalCandidateFailureCode.AGENT_TURN_BUDGET_EXHAUSTED,
    AdapterStopReason.TOKEN_BUDGET: ProposalCandidateFailureCode.TOKEN_BUDGET_EXHAUSTED,
    AdapterStopReason.BILLABLE_INPUT_BUDGET: ProposalCandidateFailureCode.TOKEN_BUDGET_EXHAUSTED,
    AdapterStopReason.COST_BUDGET: ProposalCandidateFailureCode.COST_BUDGET_EXHAUSTED,
    AdapterStopReason.SUBCALL_LIMIT: ProposalCandidateFailureCode.TOOL_CALL_BUDGET_EXHAUSTED,
    AdapterStopReason.CONTEXT_LIMIT: ProposalCandidateFailureCode.CONTEXT_BUDGET_EXHAUSTED,
}
_MAX_TRANSITION_RECEIPT_BYTES = 64 * 1024


class ProposalSessionEvidenceError(RuntimeError):
    """Host/runtime evidence fault that must never be scored as candidate utility zero."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class PersistedRuntimeExecutionAttestation:
    """Physical canonical JSON artifact for one content-addressed runtime attestation."""

    session_relative_path: str
    artifact_sha256: str
    byte_size: int
    content_sha256: str


@dataclass(frozen=True)
class PersistedProposalNodeEvidence:
    """Receipt-ready evidence derived from one independently attested adapter attempt."""

    session_id: str
    node_id: str
    invocation_id: str
    node_contract_sha256: str
    execution_request_sha256: str
    runtime_attestation: PersistedRuntimeExecutionAttestation
    execution_result: ProposalNodeExecutionResultRef
    contract_check_result: ProposalContractCheckResultRef
    resources: StageResourceEvidence
    output_artifact_sha256: str | None
    failure_code: ProposalCandidateFailureCode | None

    @property
    def runtime_execution_attestation_sha256(self) -> str:
        """Return the content identity consumed by ProposalNodeReceipt."""
        return self.runtime_attestation.content_sha256


@dataclass(frozen=True)
class PersistedProposalHandoffSet:
    """Receipt and downstream-context references for canonical semantic outputs."""

    receipt_refs: tuple[ProposalHandoffArtifactRef, ...]
    context_refs: tuple[PersistedProposalHandoffArtifact, ...]


@dataclass(frozen=True)
class _StoredJsonArtifact:
    relative_path: str
    artifact_sha256: str
    byte_size: int


class ProposalCandidateTransitionEvidence(Protocol):
    """Provider-neutral fields returned by one completed container rotation."""

    invocation_id: str
    previous_container_identity: str
    current_container_identity: str
    runtime_archive_sha256: str
    receipt_path: Path


class _CompletedCandidateTransitionReceipt(LegacyContentAddressedModel):
    """Exact completed host receipt accepted into proposal-session evidence."""

    schema_version: Literal["aecbench.proposal-candidate-transition.v1"]
    status: Literal["completed"]
    invocation_id: NonEmptyStr
    runtime_archive_sha256: str
    previous_container_identity: NonEmptyStr
    current_container_identity: NonEmptyStr
    previous_container_stopped: Literal[True]
    workspace_wiped: Literal[True]
    candidate_logs_wiped: Literal[True]

    @field_validator("runtime_archive_sha256")
    @classmethod
    def validate_runtime_archive_sha256(cls, value: str) -> str:
        return validate_sha256(value)


def persist_proposal_container_transition(
    *,
    session_root: Path,
    invocation_id: str,
    expected_runtime_archive_sha256: str,
    transition: ProposalCandidateTransitionEvidence,
) -> ProposalContainerTransitionRef:
    """Copy and bind one exact completed candidate-container transition receipt."""
    if not isinstance(invocation_id, str) or not invocation_id.strip():
        raise ProposalSessionEvidenceError(
            "container_transition_identity_mismatch",
            "proposal container transition requires a non-empty invocation identity",
        )
    try:
        validate_sha256(expected_runtime_archive_sha256)
        transition_values = (
            transition.invocation_id,
            transition.previous_container_identity,
            transition.current_container_identity,
            transition.runtime_archive_sha256,
            Path(transition.receipt_path),
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise ProposalSessionEvidenceError(
            "container_transition_identity_mismatch",
            f"proposal container transition result is malformed: {error}",
        ) from error
    (
        observed_invocation_id,
        observed_previous_identity,
        observed_current_identity,
        observed_runtime_sha256,
        receipt_path,
    ) = transition_values
    if (
        observed_invocation_id != invocation_id
        or observed_runtime_sha256 != expected_runtime_archive_sha256
        or not observed_previous_identity
        or not observed_current_identity
        or observed_previous_identity == observed_current_identity
    ):
        raise ProposalSessionEvidenceError(
            "container_transition_identity_mismatch",
            "proposal container transition result differs from the expected invocation",
        )

    receipt_bytes = _read_transition_receipt(receipt_path)
    try:
        receipt = _CompletedCandidateTransitionReceipt.model_validate_json(receipt_bytes)
    except (ValidationError, ValueError) as error:
        raise ProposalSessionEvidenceError(
            "container_transition_integrity_failure",
            f"proposal container transition receipt is invalid: {error}",
        ) from error
    if (
        receipt.invocation_id != observed_invocation_id
        or receipt.runtime_archive_sha256 != observed_runtime_sha256
        or receipt.previous_container_identity != observed_previous_identity
        or receipt.current_container_identity != observed_current_identity
    ):
        raise ProposalSessionEvidenceError(
            "container_transition_identity_mismatch",
            "proposal container transition receipt differs from its returned identity",
        )

    artifact_sha256 = hashlib.sha256(receipt_bytes).hexdigest()
    relative_path = PurePosixPath(
        "artifacts",
        "container-transitions",
        _safe_segment(invocation_id),
        f"transition.{artifact_sha256}.json",
    )
    try:
        destination_parent = _ensure_contained_directory(
            Path(session_root),
            relative_path.parent,
        )
        _write_content_addressed_atomic(
            destination_parent / relative_path.name,
            receipt_bytes,
        )
    except ProposalSessionEvidenceError:
        raise
    except OSError as error:
        raise ProposalSessionEvidenceError(
            "artifact_integrity_failure",
            f"proposal container transition could not be persisted: {error}",
        ) from error
    return ProposalContainerTransitionRef(
        invocation_id=receipt.invocation_id,
        session_relative_path=relative_path.as_posix(),
        artifact_sha256=artifact_sha256,
        byte_size=len(receipt_bytes),
        media_type="application/json",
        previous_container_identity=receipt.previous_container_identity,
        current_container_identity=receipt.current_container_identity,
        runtime_archive_sha256=receipt.runtime_archive_sha256,
        previous_container_stopped=receipt.previous_container_stopped,
        workspace_wiped=receipt.workspace_wiped,
        candidate_logs_wiped=receipt.candidate_logs_wiped,
    )


def persist_proposal_handoffs(
    *,
    session_root: Path,
    producer_node_id: str,
    graph_handoffs: tuple[ProposalHandoff, ...],
    canonical_handoffs: tuple[CanonicalProposalHandoff, ...],
) -> PersistedProposalHandoffSet:
    """Persist canonical outputs once and bind each frozen fan-out edge to them."""
    edges = tuple(
        sorted(
            graph_handoffs,
            key=lambda handoff: handoff.handoff_id,
        )
    )
    outputs = tuple(
        sorted(
            canonical_handoffs,
            key=lambda handoff: handoff.output_id,
        )
    )
    if (
        not producer_node_id.strip()
        or any(edge.producer_node_id != producer_node_id for edge in edges)
        or len({edge.handoff_id for edge in edges}) != len(edges)
        or len({output.output_id for output in outputs}) != len(outputs)
        or {edge.producer_output_id for edge in edges} != {output.output_id for output in outputs}
    ):
        raise ProposalSessionEvidenceError(
            "handoff_integrity_failure",
            "proposal handoff evidence does not exactly match the producer graph edges",
        )
    outputs_by_id = {output.output_id: output for output in outputs}
    stored_outputs: dict[str, tuple[PurePosixPath, str, int]] = {}
    root = Path(session_root)
    for output in outputs:
        if (
            not isinstance(output.canonical_bytes, bytes)
            or not output.canonical_bytes
            or hashlib.sha256(output.canonical_bytes).hexdigest() != output.artifact_sha256
        ):
            raise ProposalSessionEvidenceError(
                "handoff_integrity_failure",
                "canonical proposal handoff bytes differ from their declared identity",
            )
        relative_path = PurePosixPath(
            "artifacts",
            "handoffs",
            _safe_segment(producer_node_id),
            _safe_segment(output.output_id),
            f"handoff.{output.artifact_sha256}.json",
        )
        try:
            destination_parent = _ensure_contained_directory(
                root,
                relative_path.parent,
            )
            destination = destination_parent / relative_path.name
            _write_content_addressed_atomic(
                destination,
                output.canonical_bytes,
            )
        except ProposalSessionEvidenceError:
            raise
        except OSError as error:
            raise ProposalSessionEvidenceError(
                "artifact_integrity_failure",
                f"canonical proposal handoff could not be persisted: {error}",
            ) from error
        stored_outputs[output.output_id] = (
            relative_path,
            output.artifact_sha256,
            len(output.canonical_bytes),
        )

    receipt_refs: list[ProposalHandoffArtifactRef] = []
    context_refs: list[PersistedProposalHandoffArtifact] = []
    for edge in edges:
        output = outputs_by_id[edge.producer_output_id]
        relative_path, artifact_sha256, byte_size = stored_outputs[output.output_id]
        receipt_refs.append(
            ProposalHandoffArtifactRef(
                handoff_id=edge.handoff_id,
                producer_node_id=edge.producer_node_id,
                producer_output_id=edge.producer_output_id,
                consumer_node_id=edge.consumer_node_id,
                consumer_input_id=edge.consumer_input_id,
                session_relative_path=relative_path.as_posix(),
                artifact_sha256=artifact_sha256,
                byte_size=byte_size,
                media_type="application/json",
            )
        )
        context_refs.append(
            PersistedProposalHandoffArtifact(
                handoff_id=edge.handoff_id,
                artifact_path=(root / relative_path).resolve(strict=True),
                artifact_sha256=artifact_sha256,
                byte_size=byte_size,
            )
        )
    return PersistedProposalHandoffSet(
        receipt_refs=tuple(receipt_refs),
        context_refs=tuple(context_refs),
    )


def persist_proposal_node_evidence(
    *,
    session_root: Path,
    session_id: str,
    node_id: str,
    invocation_id: str,
    execution_bundle: ExecutionBundle,
    result: AdapterResult,
    runtime_attestation: RuntimeExecutionAttestation,
    output_bytes: bytes | None,
    structural_contract_satisfied: bool,
    contract_check_details: Mapping[str, JsonValue] | None,
    node_contract_sha256: str,
    wall_seconds: float,
    estimated_cost_usd: float | None = None,
) -> PersistedProposalNodeEvidence:
    """Validate one attempt and atomically persist receipt-ready canonical evidence."""
    _require_nonempty_identity(session_id=session_id, node_id=node_id, invocation_id=invocation_id)
    try:
        validate_sha256(node_contract_sha256)
    except ValueError as error:
        raise ProposalSessionEvidenceError(
            "child_evidence_malformed",
            f"proposal node contract identity is invalid: {error}",
        ) from error
    _require_child_evidence(result=result, runtime_attestation=runtime_attestation)
    request_sha256 = _validate_execution_identity(
        session_id=session_id,
        node_id=node_id,
        invocation_id=invocation_id,
        execution_bundle=execution_bundle,
        result=result,
        runtime_attestation=runtime_attestation,
    )
    candidate_failure = _candidate_failure(result)
    resources = _stage_resources(
        result=result,
        wall_seconds=wall_seconds,
        measured_cost_usd=estimated_cost_usd,
    )
    observed_output_sha256 = _output_sha256(output_bytes)
    committed_output_sha256 = _validate_output_evidence(
        result=result,
        execution_bundle=execution_bundle,
        output_bytes=output_bytes,
        observed_output_sha256=observed_output_sha256,
        candidate_failure=candidate_failure,
    )
    if candidate_failure is None:
        if result.agent_output.status is not AgentOutputStatus.COMPLETED:
            raise ProposalSessionEvidenceError(
                "host_execution_error",
                "unclassified non-completed adapter result cannot become candidate utility zero",
            )
        if committed_output_sha256 is None:
            candidate_failure = ProposalCandidateFailureCode.OUTPUT_COMMIT_MISSING
        elif not structural_contract_satisfied:
            candidate_failure = ProposalCandidateFailureCode.CONTRACT_CHECK_FAILED
    elif result.agent_output.status is AgentOutputStatus.COMPLETED and result.completion_commit is not None:
        raise ProposalSessionEvidenceError(
            "child_evidence_malformed",
            "candidate failure cannot also claim a completed committed output",
        )

    status = ProposalContractCheckStatus.PASSED if candidate_failure is None else ProposalContractCheckStatus.FAILED
    output_artifact_sha256 = committed_output_sha256 if status is ProposalContractCheckStatus.PASSED else None
    try:
        details = json_compatible(dict(contract_check_details or {}))
    except (TypeError, ValueError) as error:
        raise ProposalSessionEvidenceError(
            "child_evidence_malformed",
            f"contract-check details are not canonical JSON: {error}",
        ) from error
    relative_root = PurePosixPath(
        "artifacts",
        "proposal-nodes",
        _safe_segment(node_id),
        _safe_segment(invocation_id),
    )
    result_artifact = _persist_json_artifact(
        session_root=Path(session_root),
        relative_root=relative_root,
        label="adapter-result",
        payload=_adapter_result_payload(result),
    )
    attestation_artifact = _persist_json_artifact(
        session_root=Path(session_root),
        relative_root=relative_root,
        label="runtime-attestation",
        payload=runtime_attestation.model_dump(mode="json"),
    )
    contract_payload = {
        "schema_version": "aecbench.proposal-node-contract-check-evidence.v1",
        "session_id": session_id,
        "node_id": node_id,
        "invocation_id": invocation_id,
        "node_contract_sha256": node_contract_sha256,
        "execution_request_sha256": request_sha256,
        "runtime_execution_attestation_sha256": runtime_attestation.content_sha256,
        "adapter_result_artifact_sha256": result_artifact.artifact_sha256,
        "status": status.value,
        "failure_code": candidate_failure.value if candidate_failure is not None else None,
        "structural_contract_satisfied": structural_contract_satisfied,
        "observed_output_sha256": observed_output_sha256,
        "output_commit_attestation_sha256": (
            result.completion_commit.content_sha256 if result.completion_commit is not None else None
        ),
        "details": details,
    }
    check_artifact = _persist_json_artifact(
        session_root=Path(session_root),
        relative_root=relative_root,
        label="contract-check",
        payload=contract_payload,
    )
    try:
        execution_result = ProposalNodeExecutionResultRef(
            node_id=node_id,
            session_relative_path=result_artifact.relative_path,
            artifact_sha256=result_artifact.artifact_sha256,
            byte_size=result_artifact.byte_size,
            media_type="application/json",
        )
        contract_check_result = ProposalContractCheckResultRef(
            node_id=node_id,
            session_relative_path=check_artifact.relative_path,
            artifact_sha256=check_artifact.artifact_sha256,
            byte_size=check_artifact.byte_size,
            media_type="application/json",
            status=status,
            failure_code=candidate_failure,
        )
    except ValidationError as error:
        raise ProposalSessionEvidenceError(
            "child_evidence_malformed",
            f"persisted proposal evidence does not satisfy its receipt contract: {error}",
        ) from error
    return PersistedProposalNodeEvidence(
        session_id=session_id,
        node_id=node_id,
        invocation_id=invocation_id,
        node_contract_sha256=node_contract_sha256,
        execution_request_sha256=request_sha256,
        runtime_attestation=PersistedRuntimeExecutionAttestation(
            session_relative_path=attestation_artifact.relative_path,
            artifact_sha256=attestation_artifact.artifact_sha256,
            byte_size=attestation_artifact.byte_size,
            content_sha256=runtime_attestation.content_sha256,
        ),
        execution_result=execution_result,
        contract_check_result=contract_check_result,
        resources=resources,
        output_artifact_sha256=output_artifact_sha256,
        failure_code=candidate_failure,
    )


def _require_nonempty_identity(
    *,
    session_id: str,
    node_id: str,
    invocation_id: str,
) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in (session_id, node_id, invocation_id)):
        raise ProposalSessionEvidenceError(
            "child_evidence_missing",
            "proposal session, node, and invocation identities must be non-empty",
        )


def _require_child_evidence(
    *,
    result: AdapterResult,
    runtime_attestation: RuntimeExecutionAttestation,
) -> None:
    if not isinstance(result, AdapterResult) or not isinstance(
        runtime_attestation,
        RuntimeExecutionAttestation,
    ):
        raise ProposalSessionEvidenceError(
            "child_evidence_missing",
            "proposal node requires typed AdapterResult and RuntimeExecutionAttestation evidence",
        )


def _validate_execution_identity(
    *,
    session_id: str,
    node_id: str,
    invocation_id: str,
    execution_bundle: ExecutionBundle,
    result: AdapterResult,
    runtime_attestation: RuntimeExecutionAttestation,
) -> str:
    try:
        request_sha256 = execution_request_sha256(execution_bundle)
    except (TypeError, ValueError) as error:
        raise ProposalSessionEvidenceError(
            "child_evidence_malformed",
            f"execution request cannot be canonicalized: {error}",
        ) from error
    context = runtime_attestation.meta_harness_context
    request_context_payload = execution_bundle.request.configuration.get("meta_harness_context")
    try:
        request_context = (
            None
            if request_context_payload is None
            else MetaHarnessTrajectoryContext.model_validate(request_context_payload)
        )
    except ValidationError as error:
        raise ProposalSessionEvidenceError(
            "child_evidence_malformed",
            f"execution request carries malformed meta-harness identity: {error}",
        ) from error
    if context is None or request_context is None:
        raise ProposalSessionEvidenceError(
            "child_evidence_missing",
            "proposal node execution requires request and runtime meta-harness identity",
        )
    if (
        runtime_attestation.execution_request_sha256 != request_sha256
        or runtime_attestation.adapter_kind != execution_bundle.execution.adapter_kind
        or runtime_attestation.requested_model != execution_bundle.execution.resolved_model
        or runtime_attestation.adapter_name != result.adapter_name
        or runtime_attestation.resolved_model != result.resolved_model
        or request_context != context
        or context.proposal_session_id != session_id
        or context.proposal_invocation_id != invocation_id
        or context.program_node_id != node_id
        or result.agent_output.output_path != execution_bundle.request.output_path
        or result.agent_output.output_format != execution_bundle.request.output_format
    ):
        raise ProposalSessionEvidenceError(
            "execution_identity_mismatch",
            "execution request, runtime attestation, adapter result, and proposal node identities differ",
        )
    return request_sha256


def _stage_resources(
    *,
    result: AdapterResult,
    wall_seconds: float,
    measured_cost_usd: float | None,
) -> StageResourceEvidence:
    if (
        not isinstance(wall_seconds, int | float)
        or isinstance(wall_seconds, bool)
        or not math.isfinite(wall_seconds)
        or wall_seconds < 0
    ):
        raise ProposalSessionEvidenceError(
            "child_evidence_malformed",
            "proposal node wall-clock evidence must be finite and non-negative",
        )
    if result.turns_used is None or result.usage_input_tokens is None or result.usage_output_tokens is None:
        raise ProposalSessionEvidenceError(
            "child_evidence_missing",
            "proposal node AdapterResult lacks turns or token evidence",
        )
    advisor_tokens_in, advisor_tokens_out = _advisor_tokens(result)
    tokens_in = result.usage_input_tokens + advisor_tokens_in
    tokens_out = result.usage_output_tokens + advisor_tokens_out
    cost = measured_cost_usd
    if cost is None:
        cost = estimate_cost_usd(
            result.resolved_model,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            cache_read_tokens=result.usage_cache_read_tokens or 0,
            cache_write_tokens=result.usage_cache_write_tokens or 0,
        )
    try:
        return StageResourceEvidence(
            wall_seconds=float(wall_seconds),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cache_read_tokens=result.usage_cache_read_tokens,
            cache_write_tokens=result.usage_cache_write_tokens,
            estimated_cost_usd=cost,
            agent_turns=result.turns_used,
            tool_calls=sum(entry.event is TranscriptEvent.TOOL_CALL for entry in result.transcript),
        )
    except ValidationError as error:
        raise ProposalSessionEvidenceError(
            "child_evidence_malformed",
            f"proposal node resource evidence is invalid: {error}",
        ) from error


def _advisor_tokens(result: AdapterResult) -> tuple[int, int]:
    fields_present = (
        result.usage_advisor_calls is not None,
        result.usage_advisor_input_tokens is not None,
        result.usage_advisor_output_tokens is not None,
    )
    if not any(fields_present):
        return 0, 0
    if not all(fields_present):
        raise ProposalSessionEvidenceError(
            "child_evidence_missing",
            "proposal node AdapterResult carries incomplete advisor usage evidence",
        )
    assert result.usage_advisor_calls is not None
    assert result.usage_advisor_input_tokens is not None
    assert result.usage_advisor_output_tokens is not None
    if (
        result.usage_advisor_calls < 0
        or result.usage_advisor_input_tokens < 0
        or result.usage_advisor_output_tokens < 0
        or (
            result.usage_advisor_calls == 0
            and (result.usage_advisor_input_tokens > 0 or result.usage_advisor_output_tokens > 0)
        )
    ):
        raise ProposalSessionEvidenceError(
            "child_evidence_malformed",
            "proposal node AdapterResult carries inconsistent advisor usage evidence",
        )
    return result.usage_advisor_input_tokens, result.usage_advisor_output_tokens


def _candidate_failure(result: AdapterResult) -> ProposalCandidateFailureCode | None:
    if result.provider_error is not None or result.failure_kind is AdapterFailureKind.PROVIDER_ERROR:
        raise ProposalSessionEvidenceError(
            "provider_execution_error",
            "provider failure is an experiment error, not a candidate-owned outcome",
        )
    if result.failure_kind is AdapterFailureKind.TOOL_EXECUTION_FAILED:
        raise ProposalSessionEvidenceError(
            "host_execution_error",
            "tool execution failure is not safely attributable to the candidate",
        )
    failure_kind_code = None if result.failure_kind is None else _FAILURE_KIND_CODES.get(result.failure_kind)
    stop_reason_code = None if result.stop_reason is None else _STOP_REASON_CODES.get(result.stop_reason)
    codes = {
        code
        for code in (
            failure_kind_code,
            stop_reason_code,
        )
        if code is not None
    }
    if len(codes) > 1:
        raise ProposalSessionEvidenceError(
            "child_evidence_malformed",
            "adapter failure kind and stop reason classify to different candidate failures",
        )
    if result.failure_kind is not None and result.failure_kind not in _FAILURE_KIND_CODES:
        raise ProposalSessionEvidenceError(
            "host_execution_error",
            f"adapter failure {result.failure_kind.value!r} is not a closed candidate-owned outcome",
        )
    return next(iter(codes), None)


def _output_sha256(output_bytes: bytes | None) -> str | None:
    if output_bytes is None:
        return None
    if not isinstance(output_bytes, bytes):
        raise ProposalSessionEvidenceError(
            "child_evidence_malformed",
            "proposal node output evidence must be exact bytes",
        )
    return hashlib.sha256(output_bytes).hexdigest()


def _validate_output_evidence(
    *,
    result: AdapterResult,
    execution_bundle: ExecutionBundle,
    output_bytes: bytes | None,
    observed_output_sha256: str | None,
    candidate_failure: ProposalCandidateFailureCode | None,
) -> str | None:
    commit = result.completion_commit
    if commit is None:
        return None
    if output_bytes is None or observed_output_sha256 is None:
        raise ProposalSessionEvidenceError(
            "output_integrity_failure",
            "adapter claimed an output commit without preserved output bytes",
        )
    if (
        commit.output_path != execution_bundle.request.output_path
        or commit.output_path != result.agent_output.output_path
        or commit.output_sha256 != observed_output_sha256
        or commit.output_size_bytes != len(output_bytes)
    ):
        raise ProposalSessionEvidenceError(
            "output_integrity_failure",
            "preserved output bytes do not match the adapter output commit",
        )
    if candidate_failure is None and result.agent_output.status is AgentOutputStatus.COMPLETED:
        return observed_output_sha256
    return None


def _adapter_result_payload(result: AdapterResult) -> dict[str, JsonValue]:
    try:
        return {field.name: json_compatible(getattr(result, field.name)) for field in fields(result)}
    except (TypeError, ValueError) as error:
        raise ProposalSessionEvidenceError(
            "child_evidence_malformed",
            f"AdapterResult cannot be represented as canonical JSON: {error}",
        ) from error


def _persist_json_artifact(
    *,
    session_root: Path,
    relative_root: PurePosixPath,
    label: str,
    payload: Mapping[str, JsonValue],
) -> _StoredJsonArtifact:
    try:
        encoded = canonical_json_bytes(payload)
    except (TypeError, ValueError) as error:
        raise ProposalSessionEvidenceError(
            "child_evidence_malformed",
            f"{label} evidence cannot be represented as canonical JSON: {error}",
        ) from error
    artifact_sha256 = hashlib.sha256(encoded).hexdigest()
    relative_path = relative_root / f"{label}.{artifact_sha256}.json"
    root = Path(session_root)
    try:
        destination_parent = _ensure_contained_directory(
            root,
            relative_path.parent,
        )
        destination = destination_parent / relative_path.name
        _write_content_addressed_atomic(destination, encoded)
    except ProposalSessionEvidenceError:
        raise
    except OSError as error:
        raise ProposalSessionEvidenceError(
            "artifact_integrity_failure",
            f"proposal evidence artifact could not be persisted: {error}",
        ) from error
    return _StoredJsonArtifact(
        relative_path=relative_path.as_posix(),
        artifact_sha256=artifact_sha256,
        byte_size=len(encoded),
    )


def _ensure_contained_directory(
    root: Path,
    relative_directory: PurePosixPath,
) -> Path:
    if relative_directory.is_absolute() or any(part in {"", ".", ".."} for part in relative_directory.parts):
        raise ProposalSessionEvidenceError(
            "artifact_integrity_failure",
            "proposal evidence path is not session-relative",
        )
    mkdir_durable(root)
    _assert_regular_directory(root)
    cursor = root
    for part in relative_directory.parts:
        child = cursor / part
        if child.exists() or child.is_symlink():
            _assert_regular_directory(child)
        else:
            try:
                child.mkdir(mode=0o700)
            except FileExistsError:
                _assert_regular_directory(child)
            else:
                fsync_directory(cursor)
        cursor = child
    if not cursor.resolve().is_relative_to(root.resolve()):
        raise ProposalSessionEvidenceError(
            "artifact_integrity_failure",
            "proposal evidence path escapes its session root",
        )
    return cursor


def _assert_regular_directory(path: Path) -> None:
    try:
        mode = path.lstat().st_mode
    except OSError as error:
        raise ProposalSessionEvidenceError(
            "artifact_integrity_failure",
            f"proposal evidence directory cannot be inspected: {error}",
        ) from error
    if not stat.S_ISDIR(mode):
        raise ProposalSessionEvidenceError(
            "artifact_integrity_failure",
            "proposal evidence path contains a non-directory component",
        )


def _write_content_addressed_atomic(path: Path, encoded: bytes) -> None:
    if path.exists() or path.is_symlink():
        _assert_regular_exact_file(path, encoded)
        return
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            _assert_regular_exact_file(path, encoded)
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)
    _assert_regular_exact_file(path, encoded)


def _assert_regular_exact_file(path: Path, encoded: bytes) -> None:
    try:
        mode = path.lstat().st_mode
    except OSError as error:
        raise ProposalSessionEvidenceError(
            "artifact_integrity_failure",
            f"proposal evidence artifact cannot be read: {error}",
        ) from error
    if not stat.S_ISREG(mode):
        raise ProposalSessionEvidenceError(
            "artifact_integrity_failure",
            "content-addressed proposal evidence path is not a regular file",
        )
    try:
        existing = path.read_bytes()
    except OSError as error:
        raise ProposalSessionEvidenceError(
            "artifact_integrity_failure",
            f"proposal evidence artifact cannot be read: {error}",
        ) from error
    if existing != encoded:
        raise ProposalSessionEvidenceError(
            "artifact_integrity_failure",
            "content-addressed proposal evidence path contains different bytes",
        )


def _read_transition_receipt(path: Path) -> bytes:
    flags = os.O_RDONLY
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    flags |= nofollow
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ProposalSessionEvidenceError(
            "container_transition_integrity_failure",
            f"proposal container transition receipt cannot be opened safely: {error}",
        ) from error
    try:
        path_stat = os.fstat(descriptor)
        if (
            not stat.S_ISREG(path_stat.st_mode)
            or path_stat.st_size < 1
            or path_stat.st_size > _MAX_TRANSITION_RECEIPT_BYTES
        ):
            raise ProposalSessionEvidenceError(
                "container_transition_integrity_failure",
                "proposal container transition receipt must be a bounded regular file",
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            content = handle.read(_MAX_TRANSITION_RECEIPT_BYTES + 1)
    except OSError as error:
        raise ProposalSessionEvidenceError(
            "container_transition_integrity_failure",
            f"proposal container transition receipt cannot be read safely: {error}",
        ) from error
    finally:
        os.close(descriptor)
    if len(content) != path_stat.st_size:
        raise ProposalSessionEvidenceError(
            "container_transition_integrity_failure",
            "proposal container transition receipt changed while it was read",
        )
    return content


def _safe_segment(value: str) -> str:
    readable = "".join(
        character if character.isascii() and (character.isalnum() or character in "-.") else "-" for character in value
    ).strip(".-")
    if not readable:
        readable = "identity"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{readable[:48]}-{digest}"
