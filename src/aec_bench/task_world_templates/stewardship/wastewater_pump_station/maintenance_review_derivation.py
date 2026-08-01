# ABOUTME: Derives a treated Pump A closeout pack from one verified world snapshot.
# ABOUTME: Reads source evidence without changing the durable pump-station run.

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review import (
    PUMP_STATION_REVIEW_PACK_POLICY_V1,
    PreparedPumpStationReviewCase,
    PumpStationReviewActionCode,
    PumpStationReviewCaseManifest,
    PumpStationReviewDisposition,
    PumpStationReviewFinding,
    PumpStationReviewIssueSpecification,
    PumpStationReviewPack,
    PumpStationReviewPackRecord,
    PumpStationReviewPreparationReceipt,
    PumpStationReviewPreparationRequest,
    PumpStationReviewPublicCase,
    PumpStationReviewRecordKind,
    PumpStationReviewTreatmentReceipt,
    PumpStationReviewVerifierTarget,
    PumpStationReviewVerifierTargetAny,
    PumpStationReviewVerifierTargetV1,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_kernel import (
    pump_station_model_from_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    load_reference_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationEvidence,
    PumpStationEvidenceKind,
    PumpStationObligationKind,
    PumpStationObligationStatus,
    PumpStationProcessKind,
    PumpStationProcessStatus,
    PumpStationRestrictionKind,
    PumpStationStewardshipState,
    PumpStationWorkOrderStatus,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationRunStep,
    verify_stewardship_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)


def _evidence(
    state: PumpStationStewardshipState,
    kind: PumpStationEvidenceKind,
    pump_id: str,
) -> PumpStationEvidence:
    matches = tuple(item for item in state.evidence if item.kind is kind and item.pump_id == pump_id)
    if not matches:
        raise ValueError(f"review source is incomplete: missing {kind.value} evidence for {pump_id}")
    return matches[-1]


def _record(
    *,
    record_id: str,
    kind: PumpStationReviewRecordKind,
    component_id: str,
    title: str,
    statement: str,
    status: str,
    source_record_ids: tuple[str, ...],
    sequence: int,
    evidence_ids: tuple[str, ...] = (),
) -> PumpStationReviewPackRecord:
    return PumpStationReviewPackRecord(
        record_id=record_id,
        kind=kind,
        component_id=component_id,
        title=title,
        statement=statement,
        status=status,
        source_record_ids=source_record_ids,
        evidence_ids=evidence_ids,
        source_sequence=sequence,
    )


def _source_records(
    *,
    state: PumpStationStewardshipState,
    steps: tuple[PumpStationRunStep, ...],
    package_content_id: str,
    package_manifest_content_id: str,
) -> tuple[PumpStationReviewPackRecord, ...]:
    sequence = state.sequence
    pump_a_checks = _evidence(
        state,
        PumpStationEvidenceKind.FUNCTIONAL_CHECKS,
        "pump-a",
    )
    pump_b_checks = _evidence(
        state,
        PumpStationEvidenceKind.FUNCTIONAL_CHECKS,
        "pump-b",
    )
    pump_a_verification = _evidence(
        state,
        PumpStationEvidenceKind.POST_MAINTENANCE_VERIFICATION,
        "pump-a",
    )
    pump_b_inspection = _evidence(
        state,
        PumpStationEvidenceKind.INSPECTION,
        "pump-b",
    )
    work_order = state.work_order_for("pump-a")
    verification_processes = tuple(
        item
        for item in state.processes
        if item.kind is PumpStationProcessKind.POST_MAINTENANCE_VERIFICATION and item.pump_id == "pump-a"
    )
    if not verification_processes:
        raise ValueError("review source is incomplete: missing Pump A verification process")
    verification_process = verification_processes[-1]
    dependencies = tuple(item for item in state.dependencies if item.process_id == verification_process.process_id)
    if not dependencies:
        raise ValueError("review source is incomplete: missing Pump A process dependencies")
    obligation = state.obligation(
        PumpStationObligationKind.POST_MAINTENANCE_VERIFICATION,
        "pump-a",
    )
    restriction = state.restriction(
        PumpStationRestrictionKind.POST_MAINTENANCE_RUN_IN,
        "pump-a",
    )
    physical_steps = tuple(item for item in steps if item.transition.receipt.physical_change is not None)
    if not physical_steps:
        raise ValueError("review source is incomplete: missing intervention receipt")
    decision_ids = tuple(item.transition.receipt.transition_id for item in steps)
    tenure_ids = tuple(
        dict.fromkeys(
            item.information_set.base_view.agent_tenure_id for item in steps if item.information_set is not None
        )
    )
    if len(tenure_ids) < 2:
        raise ValueError("review source is incomplete: missing handover lineage")
    records = (
        _record(
            record_id="condition-history-pump-a",
            kind=PumpStationReviewRecordKind.CONDITION_HISTORY,
            component_id="pump-a",
            title="Pump A condition history",
            statement=(
                "Pump A has accepted post-maintenance checks and independent verification in the selected history."
            ),
            status="verified",
            source_record_ids=(pump_a_checks.evidence_id, pump_a_verification.evidence_id),
            evidence_ids=(pump_a_checks.evidence_id, pump_a_verification.evidence_id),
            sequence=sequence,
        ),
        _record(
            record_id="defect-history-pump-a",
            kind=PumpStationReviewRecordKind.DEFECT_HISTORY,
            component_id="pump-a",
            title="Pump A defect and return history",
            statement=(
                "The selected history begins after Pump A maintenance scope "
                "completion and retains a run-in restriction."
            ),
            status="scope_completed",
            source_record_ids=(work_order.work_order_id, restriction.restriction_id),
            sequence=sequence,
        ),
        _record(
            record_id=work_order.work_order_id,
            kind=PumpStationReviewRecordKind.WORK_ORDER,
            component_id="pump-a",
            title="Pump A work order",
            statement="The Pump A maintenance work order has completed its approved physical scope.",
            status=work_order.status.value,
            source_record_ids=(work_order.work_order_id,),
            sequence=work_order.created_sequence,
        ),
        _record(
            record_id="approved-scope-pump-a",
            kind=PumpStationReviewRecordKind.APPROVED_SCOPE,
            component_id="pump-a",
            title="Approved Pump A scope",
            statement=(
                "Complete maintenance, functional checks, controlled return, "
                "and post-maintenance verification for Pump A."
            ),
            status="approved",
            source_record_ids=(work_order.work_order_id,),
            sequence=work_order.created_sequence,
        ),
        _record(
            record_id=verification_process.process_id,
            kind=PumpStationReviewRecordKind.WORK_PROCESS,
            component_id="pump-a",
            title="Pump A post-maintenance verification process",
            statement="The timed Pump A verification process completed after its declared interruption and resume.",
            status=verification_process.status.value,
            source_record_ids=(verification_process.process_id,),
            sequence=sequence,
        ),
        _record(
            record_id="dependencies-pump-a-verification",
            kind=PumpStationReviewRecordKind.DEPENDENCY,
            component_id="pump-a",
            title="Pump A verification dependencies",
            statement="The process records physical, safety, resource, and administrative dependencies.",
            status=("satisfied" if all(item.satisfied for item in dependencies) else "not_satisfied"),
            source_record_ids=tuple(item.dependency_id for item in dependencies),
            sequence=sequence,
        ),
        _record(
            record_id="access-and-resources-selected-snapshot",
            kind=PumpStationReviewRecordKind.ACCESS_AND_RESOURCES,
            component_id="site",
            title="Access and resource record",
            statement=(
                "The selected history records access withdrawal, restoration, "
                "and repair-kit use through scheduled work events."
            ),
            status="recorded",
            source_record_ids=decision_ids,
            sequence=sequence,
        ),
        _record(
            record_id=pump_b_inspection.evidence_id,
            kind=PumpStationReviewRecordKind.INSPECTION_EVIDENCE,
            component_id="pump-b",
            title="Pump B inspection evidence",
            statement=(
                "This concurrent Pump B inspection record is included to "
                "preserve component identity across the station pack."
            ),
            status="accepted",
            source_record_ids=(pump_b_inspection.evidence_id,),
            evidence_ids=(pump_b_inspection.evidence_id,),
            sequence=sequence,
        ),
        _record(
            record_id="intervention-record-pump-b",
            kind=PumpStationReviewRecordKind.INTERVENTION_EVIDENCE,
            component_id="pump-b",
            title="Pump B intervention receipt",
            statement="The selected history records the separate Pump B obstruction-clearance intervention.",
            status="completed",
            source_record_ids=tuple(item.transition.receipt.transition_id for item in physical_steps),
            sequence=sequence,
        ),
        _record(
            record_id=pump_a_checks.evidence_id,
            kind=PumpStationReviewRecordKind.FUNCTIONAL_CHECK_EVIDENCE,
            component_id="pump-a",
            title="Pump A functional-check evidence",
            statement="Pump A functional checks passed and were accepted for the Pump A post-maintenance baseline.",
            status="accepted",
            source_record_ids=(pump_a_checks.evidence_id,),
            evidence_ids=(pump_a_checks.evidence_id,),
            sequence=sequence,
        ),
        _record(
            record_id=pump_b_checks.evidence_id,
            kind=PumpStationReviewRecordKind.FUNCTIONAL_CHECK_EVIDENCE,
            component_id="pump-b",
            title="Pump B functional-check evidence",
            statement="Pump B functional checks passed after the separate Pump B intervention.",
            status="accepted",
            source_record_ids=(pump_b_checks.evidence_id,),
            evidence_ids=(pump_b_checks.evidence_id,),
            sequence=sequence,
        ),
        _record(
            record_id="provisional-return-record-pump-a",
            kind=PumpStationReviewRecordKind.PROVISIONAL_RETURN,
            component_id="pump-a",
            title="Pump A provisional return",
            statement="Pump A was returned under the active run-in restriction after accepted functional checks.",
            status="provisional",
            source_record_ids=(work_order.work_order_id, restriction.restriction_id),
            evidence_ids=(pump_a_checks.evidence_id,),
            sequence=sequence,
        ),
        _record(
            record_id="closeout-record-pump-a",
            kind=PumpStationReviewRecordKind.CLOSEOUT,
            component_id="pump-a",
            title="Pump A maintenance closeout",
            statement=(
                "The closeout claims that Pump A scope and functional checks support the return-to-service decision."
            ),
            status="issued_for_review",
            source_record_ids=(work_order.work_order_id, pump_a_verification.evidence_id),
            evidence_ids=(pump_a_checks.evidence_id,),
            sequence=sequence,
        ),
        _record(
            record_id=pump_a_verification.evidence_id,
            kind=PumpStationReviewRecordKind.POST_MAINTENANCE_VERIFICATION,
            component_id="pump-a",
            title="Pump A post-maintenance verification evidence",
            statement="Independent Pump A post-maintenance verification passed.",
            status="accepted",
            source_record_ids=(pump_a_verification.evidence_id,),
            evidence_ids=(pump_a_verification.evidence_id,),
            sequence=sequence,
        ),
        _record(
            record_id=restriction.restriction_id,
            kind=PumpStationReviewRecordKind.OPERATING_RESTRICTION,
            component_id="pump-a",
            title="Pump A run-in restriction",
            statement="The Pump A post-maintenance run-in restriction remains active after verification.",
            status=restriction.status.value,
            source_record_ids=(restriction.restriction_id,),
            sequence=restriction.created_sequence,
        ),
        _record(
            record_id=obligation.obligation_id,
            kind=PumpStationReviewRecordKind.DUTY_FOLLOW_UP,
            component_id="pump-a",
            title="Pump A verification duty",
            statement="The Pump A post-maintenance verification duty was fulfilled by accepted independent evidence.",
            status=obligation.status.value,
            source_record_ids=(obligation.obligation_id,),
            evidence_ids=((obligation.evidence_id,) if obligation.evidence_id else ()),
            sequence=obligation.created_sequence,
        ),
        _record(
            record_id="decision-lineage-selected-history",
            kind=PumpStationReviewRecordKind.DECISION_LINEAGE,
            component_id="site",
            title="Decision lineage",
            statement=(
                "Each selected action has an immutable proposal, authority decision, receipt, and resulting state."
            ),
            status="verified",
            source_record_ids=decision_ids,
            sequence=sequence,
        ),
        _record(
            record_id="handover-lineage-selected-history",
            kind=PumpStationReviewRecordKind.HANDOVER_LINEAGE,
            component_id="site",
            title="Reviewer-relevant handover lineage",
            statement="The selected work history spans two bound actor tenures without changing the world branch.",
            status="verified",
            source_record_ids=tenure_ids,
            sequence=sequence,
        ),
        _record(
            record_id="fmeca-basis-pump-a",
            kind=PumpStationReviewRecordKind.FMECA_BASIS,
            component_id="pump-a",
            title="Pump A FMECA basis",
            statement=(
                "The applicable synthetic failure basis covers obstruction, "
                "clearance loss, capability review, and controlled return."
            ),
            status="applicable",
            source_record_ids=(package_content_id,),
            sequence=sequence,
        ),
        _record(
            record_id="maintenance-schedule-basis-pump-a",
            kind=PumpStationReviewRecordKind.MAINTENANCE_SCHEDULE_BASIS,
            component_id="pump-a",
            title="Pump A maintenance schedule basis",
            statement=(
                "The applicable synthetic schedule uses declared access, "
                "resource, process-duration, and verification timing rules."
            ),
            status="applicable",
            source_record_ids=(package_manifest_content_id,),
            sequence=sequence,
        ),
    )
    return records


def _validate_complete_source(state: PumpStationStewardshipState) -> None:
    checks_a = _evidence(
        state,
        PumpStationEvidenceKind.FUNCTIONAL_CHECKS,
        "pump-a",
    )
    checks_b = _evidence(
        state,
        PumpStationEvidenceKind.FUNCTIONAL_CHECKS,
        "pump-b",
    )
    verification = _evidence(
        state,
        PumpStationEvidenceKind.POST_MAINTENANCE_VERIFICATION,
        "pump-a",
    )
    work_order = state.work_order_for("pump-a")
    obligation = state.obligation(
        PumpStationObligationKind.POST_MAINTENANCE_VERIFICATION,
        "pump-a",
    )
    incomplete_process = any(
        item.status
        in {
            PumpStationProcessStatus.ACTIVE,
            PumpStationProcessStatus.BLOCKED,
            PumpStationProcessStatus.SUSPENDED,
        }
        for item in state.processes
    )
    if (
        state.state_version != "pump-station-stewardship-state.v3"
        or checks_a.passed is not True
        or checks_a.accepted_by is None
        or checks_a.health is None
        or checks_b.passed is not True
        or checks_b.accepted_by is None
        or checks_b.health is None
        or verification.passed is not True
        or verification.accepted_by is None
        or verification.health is None
        or work_order.status
        not in {
            PumpStationWorkOrderStatus.SCOPE_COMPLETED,
            PumpStationWorkOrderStatus.IN_PROGRESS,
        }
        or obligation.status is not PumpStationObligationStatus.FULFILLED
        or incomplete_process
    ):
        raise ValueError("review source is incomplete")


def derive_pump_station_review_case(
    *,
    source_run_root: Path,
    request: PumpStationReviewPreparationRequest,
    package_root: Path | None = None,
) -> PreparedPumpStationReviewCase:
    """Reload, verify, and derive one source-bound review case."""
    repository = PumpStationWorldRunRepository(source_run_root)
    snapshot_before = repository.current_snapshot()
    if snapshot_before != request.source_snapshot:
        raise ValueError("review source binding differs from the selected snapshot")
    source_manifest = repository.load_manifest()
    package = load_reference_package(package_root)
    model = pump_station_model_from_package(package)
    if request.asset_id != model.asset_id:
        raise ValueError("review asset differs from the source package")
    report = verify_stewardship_run(
        model,
        repository.load_state(source_manifest.initial_state_id),
        repository.steps(),
        record_versions=source_manifest.record_versions,
    )
    if not report.valid or report.final_state_id != snapshot_before.state_id:
        raise ValueError("review source is not replay-valid")
    state = repository.load_state(snapshot_before.state_id)
    _validate_complete_source(state)
    steps = repository.steps()
    untreated_pack = PumpStationReviewPack(
        pack_name="Pump A maintenance closeout and return-to-service pack",
        asset_id=request.asset_id,
        reviewed_component_id=request.reviewed_component_id,
        maintenance_case_id=request.maintenance_case_id,
        pack_policy=request.pack_policy,
        source_snapshot=snapshot_before,
        records=_source_records(
            state=state,
            steps=steps,
            package_content_id=package.package_content_id,
            package_manifest_content_id=package.manifest_content_id,
        ),
    )
    original_closeout = untreated_pack.record(request.target_record_id)
    pump_b_checks = next(
        item
        for item in untreated_pack.records
        if item.kind is PumpStationReviewRecordKind.FUNCTIONAL_CHECK_EVIDENCE
        and item.component_id == request.cited_component_id
    )
    treated_closeout = PumpStationReviewPackRecord.model_validate(
        {
            **original_closeout.model_dump(
                mode="json",
                exclude={"content_sha256"},
            ),
            "evidence_ids": list(pump_b_checks.source_record_ids),
        }
    )
    treated_pack = PumpStationReviewPack(
        pack_name=untreated_pack.pack_name,
        asset_id=untreated_pack.asset_id,
        reviewed_component_id=untreated_pack.reviewed_component_id,
        maintenance_case_id=untreated_pack.maintenance_case_id,
        pack_policy=untreated_pack.pack_policy,
        source_snapshot=untreated_pack.source_snapshot,
        records=tuple(
            treated_closeout if item.record_id == request.target_record_id else item for item in untreated_pack.records
        ),
    )
    obligation = state.obligation(
        PumpStationObligationKind.POST_MAINTENANCE_VERIFICATION,
        "pump-a",
    )
    restriction = state.restriction(
        PumpStationRestrictionKind.POST_MAINTENANCE_RUN_IN,
        "pump-a",
    )
    issue = PumpStationReviewIssueSpecification(
        request_content_sha256=request.content_sha256,
        issue_class=request.issue_class,
        issue_version=request.issue_version,
        target_record_id=request.target_record_id,
        original_evidence_id=original_closeout.evidence_ids[0],
        planted_evidence_id=pump_b_checks.source_record_ids[0],
        expected_affected_record_ids=(request.target_record_id,),
        unaffected_control_ids=(
            obligation.obligation_id,
            restriction.restriction_id,
        ),
    )
    verifier_target: PumpStationReviewVerifierTargetAny
    if request.pack_policy == PUMP_STATION_REVIEW_PACK_POLICY_V1:
        verifier_target = PumpStationReviewVerifierTargetV1(
            finding=PumpStationReviewFinding.WRONG_COMPONENT_EVIDENCE_CITATION,
            affected_record_ids=(request.target_record_id,),
            unaffected_duty_ids=(obligation.obligation_id,),
            missing_evidence_ids=original_closeout.evidence_ids,
            disposition=PumpStationReviewDisposition.REJECT_CLOSEOUT,
            required_follow_up=(
                "correct-functional-check-citation",
                "reissue-pump-a-closeout",
            ),
            required_source_record_ids=(
                request.target_record_id,
                original_closeout.evidence_ids[0],
                pump_b_checks.source_record_ids[0],
            ),
        )
    else:
        verifier_target = PumpStationReviewVerifierTarget(
            finding=PumpStationReviewFinding.WRONG_COMPONENT_EVIDENCE_CITATION,
            affected_record_ids=(request.target_record_id,),
            unaffected_duty_ids=(obligation.obligation_id,),
            missing_evidence_ids=original_closeout.evidence_ids,
            disposition=PumpStationReviewDisposition.REJECT_CLOSEOUT,
            required_follow_up=(
                PumpStationReviewActionCode.CORRECT_FUNCTIONAL_CHECK_CITATION,
                PumpStationReviewActionCode.REISSUE_PUMP_A_CLOSEOUT,
            ),
            required_source_record_ids=(
                request.target_record_id,
                original_closeout.evidence_ids[0],
                pump_b_checks.source_record_ids[0],
            ),
        )
    case_id = f"review-case-{request.content_sha256[:24]}"
    public_case = PumpStationReviewPublicCase(
        case_id=case_id,
        case_name="Pump A maintenance closeout review",
        source_snapshot=snapshot_before,
        reviewer_role=request.reviewer_role,
        source_verified=True,
        pack=treated_pack,
    )
    snapshot_after = repository.current_snapshot()
    preparation_receipt = PumpStationReviewPreparationReceipt(
        request_content_sha256=request.content_sha256,
        source_snapshot_before=snapshot_before,
        source_snapshot_after=snapshot_after,
        source_verification_sha256=canonical_content_sha256(asdict(report)),
        untreated_pack_content_sha256=untreated_pack.content_sha256,
    )
    treatment_receipt = PumpStationReviewTreatmentReceipt(
        request_content_sha256=request.content_sha256,
        issue_content_sha256=issue.content_sha256,
        untreated_pack_content_sha256=untreated_pack.content_sha256,
        treated_pack_content_sha256=treated_pack.content_sha256,
        changed_record_ids=(request.target_record_id,),
    )
    case_manifest = PumpStationReviewCaseManifest(
        case_id=case_id,
        request_content_sha256=request.content_sha256,
        public_case_content_sha256=public_case.content_sha256,
        issue_content_sha256=issue.content_sha256,
        verifier_target_content_sha256=verifier_target.content_sha256,
        preparation_receipt_content_sha256=preparation_receipt.content_sha256,
        treatment_receipt_content_sha256=treatment_receipt.content_sha256,
    )
    return PreparedPumpStationReviewCase(
        request=request,
        source_verification=report,
        untreated_pack=untreated_pack,
        public_case=public_case,
        issue=issue,
        verifier_target=verifier_target,
        preparation_receipt=preparation_receipt,
        treatment_receipt=treatment_receipt,
        manifest=case_manifest,
    )


__all__ = ("derive_pump_station_review_case",)
