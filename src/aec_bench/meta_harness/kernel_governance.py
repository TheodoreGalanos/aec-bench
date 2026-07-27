# ABOUTME: Converts deterministic kernel-change eligibility into exact durable human authority.
# ABOUTME: Recomputes every proposal and records its evidence without mutating the installed kernel.

from __future__ import annotations

from collections.abc import Iterable

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityEvent,
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    BasisKind,
    BasisReference,
    HumanAuthorityApproval,
    TaintLabel,
)
from aec_bench.contracts.harness_kernel import ContentAddressedModel
from aec_bench.meta_harness.authority_ledger import (
    AuthorityLedger,
    StoredAuthorityEvent,
    StoredBasis,
)
from aec_bench.meta_harness.kernel_catalogue import KernelRuntimeRegistry
from aec_bench.meta_harness.kernel_evolution import (
    KernelChangeDecision,
    KernelChangeRequest,
    MissingPrimitiveEvidence,
    decide_kernel_change,
)


class KernelGovernanceError(ValueError):
    """Raised when a kernel transition lacks exact durable human authority."""


def issue_kernel_change_authority(
    *,
    ledger: AuthorityLedger,
    request: KernelChangeRequest,
    decision: KernelChangeDecision,
    evidence_records: Iterable[MissingPrimitiveEvidence],
    installed_registry: KernelRuntimeRegistry,
    human_approval: BasisReference,
    event_id: str,
) -> StoredAuthorityEvent:
    """Authorize one exact recomputed kernel proposal without changing installed K."""
    selected_request = KernelChangeRequest.model_validate(request.model_dump(mode="python"))
    selected_decision = KernelChangeDecision.model_validate(decision.model_dump(mode="python"))
    records = tuple(
        MissingPrimitiveEvidence.model_validate(record.model_dump(mode="python")) for record in evidence_records
    )
    recomputed = decide_kernel_change(
        selected_request,
        evidence_records=records,
        installed_registry=installed_registry,
    )
    if selected_decision != recomputed:
        raise KernelGovernanceError("kernel authority requires the exact recomputed decision")
    if not recomputed.eligible or recomputed.proposal is None:
        raise KernelGovernanceError("kernel change decision is not eligible for implementation authority")

    approval_basis, approval = ledger.resolve_model_basis(
        human_approval,
        HumanAuthorityApproval,
    )
    proposal = recomputed.proposal
    legacy_approval = selected_request.approval
    if legacy_approval is None:
        raise KernelGovernanceError("eligible kernel decision lacks its legacy eligibility approval")
    if (
        not approval.approved
        or approval.action is not AuthorityAction.CHANGE_KERNEL_VERSION
        or approval.subject_id != proposal.proposal_id
        or approval.subject_sha256 != proposal.content_sha256
        or approval.principal.principal_id != legacy_approval.approved_by
    ):
        raise KernelGovernanceError("human approval does not match the exact kernel change proposal")
    if (
        approval_basis.origin.producer != approval.principal
        or approval_basis.origin.producer.kind is not AuthorityPrincipalKind.HUMAN
        or approval_basis.origin.observed_by.kind
        not in {
            AuthorityPrincipalKind.HOST_RUNTIME,
            AuthorityPrincipalKind.HOST_POLICY,
        }
        or TaintLabel.HUMAN_AUTHORITY not in approval_basis.origin.taint_labels
    ):
        raise KernelGovernanceError("kernel change requires matching host-observed human approval")

    host_runtime = AuthorityPrincipal(
        principal_id="host.runtime",
        kind=AuthorityPrincipalKind.HOST_RUNTIME,
    )
    host_policy = AuthorityPrincipal(
        principal_id="host.kernel-governance",
        kind=AuthorityPrincipalKind.HOST_POLICY,
    )
    external_input = AuthorityPrincipal(
        principal_id="external.kernel-governance-input",
        kind=AuthorityPrincipalKind.EXTERNAL,
    )
    evidence_bases = tuple(
        _observe_external_model(
            ledger=ledger,
            kind=BasisKind.EVIDENCE,
            artifact_id=f"missing-primitive.{record.evidence_id}",
            model=record,
            producer=external_input,
            observed_by=host_runtime,
            operation_id="observe-missing-primitive",
            invocation_id=record.content_sha256,
        )
        for record in records
    )
    regression_bases = tuple(
        _observe_external_model(
            ledger=ledger,
            kind=BasisKind.REGRESSION_EVIDENCE,
            artifact_id=f"kernel-regression.{regression.regression_id}",
            model=regression,
            producer=external_input,
            observed_by=host_runtime,
            operation_id="observe-kernel-regression",
            invocation_id=regression.content_sha256,
        )
        for regression in selected_request.regression_evidence
    )
    external_origins = tuple(item.origin.content_sha256 for item in (*evidence_bases, *regression_bases))
    request_basis = _observe_external_model(
        ledger=ledger,
        kind=BasisKind.EVIDENCE,
        artifact_id=f"kernel-change-request.{selected_request.request_id}",
        model=selected_request,
        producer=external_input,
        observed_by=host_runtime,
        operation_id="observe-kernel-change-request",
        invocation_id=selected_request.content_sha256,
        parent_origin_sha256s=external_origins,
    )
    decision_basis = ledger.observe_model_basis(
        kind=BasisKind.EVIDENCE,
        artifact_id=f"kernel-change-decision.{selected_request.request_id}",
        model=recomputed,
        producer=host_policy,
        producer_process_id="aecbench.kernel-governance",
        observed_by=host_runtime,
        channel="kernel-governance",
        operation_id="recompute-kernel-change-decision",
        invocation_id=recomputed.content_sha256,
        parent_origin_sha256s=(
            request_basis.origin.content_sha256,
            *external_origins,
        ),
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )
    proposal_basis = ledger.observe_model_basis(
        kind=BasisKind.EVIDENCE,
        artifact_id=f"kernel-change-proposal.{proposal.proposal_id}",
        model=proposal,
        producer=host_policy,
        producer_process_id="aecbench.kernel-governance",
        observed_by=host_runtime,
        channel="kernel-governance",
        operation_id="persist-kernel-change-proposal",
        invocation_id=proposal.content_sha256,
        parent_origin_sha256s=(decision_basis.origin.content_sha256,),
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )
    event = AuthorityEvent(
        event_id=event_id,
        principal=approval.principal,
        action=AuthorityAction.CHANGE_KERNEL_VERSION,
        decision=AuthorityDecision.GRANTED,
        subject_id=proposal.proposal_id,
        subject_sha256=proposal.content_sha256,
        basis=(
            human_approval,
            *(item.reference for item in evidence_bases),
            *(item.reference for item in regression_bases),
            request_basis.reference,
            decision_basis.reference,
            proposal_basis.reference,
        ),
        kernel_sha256=selected_request.source_kernel_ref.content_sha256,
        reasons=("human approved exact recomputed kernel proposal after recurrence and regression gates",),
        revalidation_triggers=(
            "human_authority_revocation",
            "kernel_regression_change",
            "missing_primitive_evidence_change",
        ),
    )
    return ledger.issue_authority_event(event)


def _observe_external_model(
    *,
    ledger: AuthorityLedger,
    kind: BasisKind,
    artifact_id: str,
    model: ContentAddressedModel,
    producer: AuthorityPrincipal,
    observed_by: AuthorityPrincipal,
    operation_id: str,
    invocation_id: str,
    parent_origin_sha256s: tuple[str, ...] = (),
) -> StoredBasis:
    """Record caller-supplied kernel evidence without overstating its producer."""
    return ledger.observe_model_basis(
        kind=kind,
        artifact_id=artifact_id,
        model=model,
        producer=producer,
        producer_process_id="aecbench.kernel-governance-input",
        observed_by=observed_by,
        channel="kernel-governance",
        operation_id=operation_id,
        invocation_id=invocation_id,
        parent_origin_sha256s=parent_origin_sha256s,
        operation_taint=(
            TaintLabel.EXTERNAL_UNVERIFIED,
            TaintLabel.RUNTIME_OBSERVED,
        ),
    )
