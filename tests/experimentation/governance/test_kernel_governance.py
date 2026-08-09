# ABOUTME: Exercises durable human authority for exact deterministic kernel-change proposals.
# ABOUTME: Proves legacy approval alone, forged decisions, and candidate-origin sign-off grant no authority.

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    BasisKind,
    HumanAuthorityApproval,
    TaintLabel,
)
from aec_bench.contracts.harness_kernel import (
    KernelCapabilityKind,
    KernelCapabilitySpec,
    KernelPortSpec,
)
from aec_bench.experimentation.governance.authority_ledger import (
    AuthorityLedger,
    StoredBasis,
)
from aec_bench.experimentation.governance.kernel_evolution import (
    EvidenceSelectionBasis,
    HumanApprovalArtifact,
    KernelChangeDecision,
    KernelChangeRequest,
    KernelRegressionEvidence,
    KernelVersionBump,
    MissingPrimitiveEvidence,
    MissingPrimitiveEvidenceSet,
    MissingPrimitiveSource,
    PromotionEvidenceSplit,
    RuntimeMissingPrimitiveDiagnostic,
    capture_runtime_missing_primitive,
    decide_kernel_change,
)
from aec_bench.experimentation.governance.kernel_governance import (
    KernelGovernanceError,
    issue_kernel_change_authority,
)
from aec_bench.harness.kernel_catalogue import default_kernel_registry


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _capability() -> KernelCapabilitySpec:
    return KernelCapabilitySpec(
        capability_id="aecbench.operation.distributed-join",
        version="1.0.0",
        kind=KernelCapabilityKind.PROGRAM_OPERATION,
        summary="Join independent branches under an evidence-completeness gate.",
        inputs=(
            KernelPortSpec(
                name="branches",
                schema_ref="aecbench://branch-results/v1",
            ),
        ),
        outputs=(
            KernelPortSpec(
                name="joined",
                schema_ref="aecbench://joined-result/v1",
            ),
        ),
        configuration_schema_ref="aecbench://kernel/program-operation/distributed-join/v1",
    )


def _target_version() -> str:
    source = default_kernel_registry().manifest.version
    major, minor, _patch = (int(part) for part in source.split("."))
    return f"{major}.{minor + 1}.0"


def _missing_primitive(family: str) -> MissingPrimitiveEvidence:
    registry = default_kernel_registry()
    return capture_runtime_missing_primitive(
        evidence_id=f"missing-{family}",
        kernel_ref=registry.manifest.ref,
        requested_capability=_capability(),
        source=MissingPrimitiveSource(
            task_family_id=family,
            task_id=f"{family}/case-01",
            bundle_id=f"bundle-{family}",
            world_id=f"world-{family}",
            split=PromotionEvidenceSplit.OPTIMIZATION,
        ),
        diagnostic=RuntimeMissingPrimitiveDiagnostic(
            code="operation_handler_missing",
            message="No trusted runtime handler implements distributed join.",
            subject_ids=("distributed-join",),
        ),
    )


def _request(
    evidence: tuple[MissingPrimitiveEvidence, ...],
    *,
    approved_by: str = "human.kernel-owner",
) -> KernelChangeRequest:
    registry = default_kernel_registry()
    capability = _capability()
    evidence_set = MissingPrimitiveEvidenceSet(
        evidence_set_id="distributed-join-recurrence",
        source_kernel_ref=registry.manifest.ref,
        requested_capability_sha256=capability.content_sha256,
        selection_basis=EvidenceSelectionBasis.CAPABILITY_RECURRENCE,
        minimum_distinct_task_families=2,
        evidence_refs=tuple(item.ref for item in evidence),
    )
    target_version = _target_version()
    legacy_approval = HumanApprovalArtifact(
        approval_id="legacy-kernel-eligibility-approval",
        approved_by=approved_by,
        approved=True,
        source_kernel_ref=registry.manifest.ref,
        requested_capability_sha256=capability.content_sha256,
        evidence_set_sha256=evidence_set.content_sha256,
        target_kernel_version=target_version,
        artifact_sha256=_sha("legacy-human-approval-artifact"),
    )
    regression = KernelRegressionEvidence(
        regression_id="kernel-regression-suite",
        suite_id="adaptive-kernel-regression",
        source_kernel_ref=registry.manifest.ref,
        requested_capability_sha256=capability.content_sha256,
        evidence_set_sha256=evidence_set.content_sha256,
        target_kernel_version=target_version,
        passed=True,
        artifact_sha256=_sha("regression-results"),
    )
    return KernelChangeRequest(
        request_id="add-distributed-join",
        source_kernel_ref=registry.manifest.ref,
        requested_capability=capability,
        evidence_set=evidence_set,
        target_kernel_version=target_version,
        version_bump=KernelVersionBump.MINOR,
        approval=legacy_approval,
        regression_evidence=(regression,),
    )


def _ledger(tmp_path: Path) -> AuthorityLedger:
    candidate_root = tmp_path / "candidate"
    candidate_root.mkdir()
    return AuthorityLedger(
        tmp_path / "authority",
        candidate_roots=(candidate_root,),
    )


def _observe_implementation_approval(
    ledger: AuthorityLedger,
    *,
    decision: KernelChangeDecision,
    producer: AuthorityPrincipal,
    taint: tuple[TaintLabel, ...],
    approved: bool = True,
    action: AuthorityAction = AuthorityAction.CHANGE_KERNEL_VERSION,
    subject_id: str | None = None,
    subject_sha256: str | None = None,
    principal_id: str = "human.kernel-owner",
) -> StoredBasis:
    proposal = decision.proposal
    assert proposal is not None
    human = AuthorityPrincipal(
        principal_id=principal_id,
        kind=AuthorityPrincipalKind.HUMAN,
    )
    approval = HumanAuthorityApproval(
        approval_id="approval.implement-distributed-join",
        principal=human,
        action=action,
        subject_id=subject_id or proposal.proposal_id,
        subject_sha256=subject_sha256 or proposal.content_sha256,
        approved=approved,
        reason="approved the exact recomputed kernel proposal for implementation",
    )
    return ledger.observe_model_basis(
        kind=BasisKind.HUMAN_APPROVAL,
        artifact_id=approval.approval_id,
        model=approval,
        producer=producer,
        producer_process_id="codex-desktop",
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        channel="human-approval",
        operation_id="approve-kernel-change",
        invocation_id="approval-invocation-001",
        operation_taint=taint,
    )


def _eligible_fixture() -> tuple[
    tuple[MissingPrimitiveEvidence, ...],
    KernelChangeRequest,
    KernelChangeDecision,
]:
    evidence = (
        _missing_primitive("stormwater"),
        _missing_primitive("road-visual"),
    )
    request = _request(evidence)
    decision = decide_kernel_change(
        request,
        evidence_records=evidence,
        installed_registry=default_kernel_registry(),
    )
    assert decision.eligible
    return evidence, request, decision


def test_exact_recomputed_kernel_proposal_receives_durable_human_authority(
    tmp_path: Path,
) -> None:
    evidence, request, decision = _eligible_fixture()
    ledger = _ledger(tmp_path)
    human = AuthorityPrincipal(
        principal_id="human.kernel-owner",
        kind=AuthorityPrincipalKind.HUMAN,
    )
    approval = _observe_implementation_approval(
        ledger,
        decision=decision,
        producer=human,
        taint=(TaintLabel.HUMAN_AUTHORITY,),
    )

    authorized = issue_kernel_change_authority(
        ledger=ledger,
        request=request,
        decision=decision,
        evidence_records=evidence,
        installed_registry=default_kernel_registry(),
        human_approval=approval.reference,
        event_id="authority.kernel-change.add-distributed-join",
    )

    proposal = decision.proposal
    assert proposal is not None
    assert authorized.event.principal == human
    assert authorized.event.action is AuthorityAction.CHANGE_KERNEL_VERSION
    assert authorized.event.subject_id == proposal.proposal_id
    assert authorized.event.subject_sha256 == proposal.content_sha256
    assert {item.kind for item in authorized.event.basis} == {
        BasisKind.EVIDENCE,
        BasisKind.HUMAN_APPROVAL,
        BasisKind.REGRESSION_EVIDENCE,
    }
    decision_reference = next(
        item for item in authorized.event.basis if item.artifact_id == f"kernel-change-decision.{request.request_id}"
    )
    decision_basis = ledger.resolve_basis(decision_reference)
    assert KernelChangeDecision.model_validate_json(decision_basis.content_path.read_bytes()) == decision
    assert (
        ledger.resolve_authority_event(
            event_id=authorized.event.event_id,
            content_sha256=authorized.event.content_sha256,
        )
        == authorized
    )


def test_candidate_origin_cannot_authorize_exact_kernel_change(
    tmp_path: Path,
) -> None:
    evidence, request, decision = _eligible_fixture()
    ledger = _ledger(tmp_path)
    candidate_approval = _observe_implementation_approval(
        ledger,
        decision=decision,
        producer=AuthorityPrincipal(
            principal_id="candidate.optimizer",
            kind=AuthorityPrincipalKind.CANDIDATE,
        ),
        taint=(TaintLabel.CANDIDATE_AUTHORED,),
    )

    with pytest.raises(KernelGovernanceError, match="host-observed human"):
        issue_kernel_change_authority(
            ledger=ledger,
            request=request,
            decision=decision,
            evidence_records=evidence,
            installed_registry=default_kernel_registry(),
            human_approval=candidate_approval.reference,
            event_id="authority.kernel-change.candidate-forgery",
        )


@pytest.mark.parametrize(
    ("case", "approved", "action", "subject_id", "principal_id"),
    [
        (
            "rejected",
            False,
            AuthorityAction.CHANGE_KERNEL_VERSION,
            None,
            "human.kernel-owner",
        ),
        (
            "wrong action",
            True,
            AuthorityAction.POLICY_PROMOTION,
            None,
            "human.kernel-owner",
        ),
        (
            "wrong subject",
            True,
            AuthorityAction.CHANGE_KERNEL_VERSION,
            "proposal.somewhere-else",
            "human.kernel-owner",
        ),
        (
            "wrong principal",
            True,
            AuthorityAction.CHANGE_KERNEL_VERSION,
            None,
            "human.other-owner",
        ),
    ],
)
def test_mismatched_human_signoff_cannot_authorize_kernel_change(
    tmp_path: Path,
    case: str,
    approved: bool,
    action: AuthorityAction,
    subject_id: str | None,
    principal_id: str,
) -> None:
    evidence, request, decision = _eligible_fixture()
    ledger = _ledger(tmp_path)
    human = AuthorityPrincipal(
        principal_id=principal_id,
        kind=AuthorityPrincipalKind.HUMAN,
    )
    approval = _observe_implementation_approval(
        ledger,
        decision=decision,
        producer=human,
        taint=(TaintLabel.HUMAN_AUTHORITY,),
        approved=approved,
        action=action,
        subject_id=subject_id,
        principal_id=principal_id,
    )

    with pytest.raises(
        KernelGovernanceError,
        match="does not match",
    ):
        issue_kernel_change_authority(
            ledger=ledger,
            request=request,
            decision=decision,
            evidence_records=evidence,
            installed_registry=default_kernel_registry(),
            human_approval=approval.reference,
            event_id=f"authority.kernel-change.{case.replace(' ', '-')}",
        )


def test_fabricated_eligible_decision_cannot_receive_kernel_authority(
    tmp_path: Path,
) -> None:
    evidence, request, decision = _eligible_fixture()
    proposal = decision.proposal
    assert proposal is not None
    fabricated = KernelChangeDecision(
        request_sha256=decision.request_sha256,
        eligible=True,
        rejection_codes=(),
        distinct_task_family_ids=(
            *decision.distinct_task_family_ids,
            "unobserved-family",
        ),
        proposal=proposal,
    )
    ledger = _ledger(tmp_path)
    human = AuthorityPrincipal(
        principal_id="human.kernel-owner",
        kind=AuthorityPrincipalKind.HUMAN,
    )
    approval = _observe_implementation_approval(
        ledger,
        decision=fabricated,
        producer=human,
        taint=(TaintLabel.HUMAN_AUTHORITY,),
    )

    with pytest.raises(KernelGovernanceError, match="recomputed decision"):
        issue_kernel_change_authority(
            ledger=ledger,
            request=request,
            decision=fabricated,
            evidence_records=evidence,
            installed_registry=default_kernel_registry(),
            human_approval=approval.reference,
            event_id="authority.kernel-change.fabricated-decision",
        )


def test_ineligible_kernel_decision_cannot_receive_authority(
    tmp_path: Path,
) -> None:
    evidence = (_missing_primitive("stormwater"),)
    request = _request(evidence)
    decision = decide_kernel_change(
        request,
        evidence_records=evidence,
        installed_registry=default_kernel_registry(),
    )
    assert not decision.eligible
    ledger = _ledger(tmp_path)
    unrelated = HumanAuthorityApproval(
        approval_id="approval.ineligible-request",
        principal=AuthorityPrincipal(
            principal_id="human.kernel-owner",
            kind=AuthorityPrincipalKind.HUMAN,
        ),
        action=AuthorityAction.CHANGE_KERNEL_VERSION,
        subject_id=request.request_id,
        subject_sha256=request.content_sha256,
        approved=True,
        reason="this cannot turn an ineligible decision into an eligible one",
    )
    approval = ledger.observe_model_basis(
        kind=BasisKind.HUMAN_APPROVAL,
        artifact_id=unrelated.approval_id,
        model=unrelated,
        producer=unrelated.principal,
        producer_process_id="codex-desktop",
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        channel="human-approval",
        operation_id="approve-ineligible-kernel-change",
        invocation_id="approval-invocation-ineligible",
        operation_taint=(TaintLabel.HUMAN_AUTHORITY,),
    )

    with pytest.raises(KernelGovernanceError, match="not eligible"):
        issue_kernel_change_authority(
            ledger=ledger,
            request=request,
            decision=decision,
            evidence_records=evidence,
            installed_registry=default_kernel_registry(),
            human_approval=approval.reference,
            event_id="authority.kernel-change.ineligible",
        )
