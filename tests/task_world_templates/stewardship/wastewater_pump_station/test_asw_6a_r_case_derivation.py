# ABOUTME: Tests ASW-6A-R case derivation from one real replay-valid rich-work history.
# ABOUTME: Proves the treated closeout changes no source world state and leaks no verifier target.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_asw_5_rich_work_e2e import _execute_direct

from aec_bench.contracts.world_session import (
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review import (
    PUMP_STATION_REVIEW_ISSUE_VERSION_V1,
    PUMP_STATION_REVIEW_PACK_POLICY_V2,
    PUMP_STATION_REVIEW_VISIBILITY_POLICY_V1,
    PumpStationReviewDisposition,
    PumpStationReviewerRole,
    PumpStationReviewIssueClass,
    PumpStationReviewPreparationRequest,
    PumpStationReviewRecordKind,
    derive_pump_station_review_case,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationStateSnapshotRef,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationWorldSessionFactory,
)


def _inventory(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def _request(snapshot: PumpStationStateSnapshotRef) -> PumpStationReviewPreparationRequest:
    return PumpStationReviewPreparationRequest(
        request_id="prepare-review-001",
        source_snapshot=snapshot,
        asset_id="synthetic-wastewater-pump-station",
        reviewed_component_id="pump-a",
        maintenance_case_id="work-order-pump-a",
        pack_policy=PUMP_STATION_REVIEW_PACK_POLICY_V2,
        issue_class=PumpStationReviewIssueClass.WRONG_COMPONENT_EVIDENCE_CITATION,
        issue_version=PUMP_STATION_REVIEW_ISSUE_VERSION_V1,
        target_record_id="closeout-record-pump-a",
        cited_component_id="pump-b",
        reviewer_role=PumpStationReviewerRole.ASSET_ENGINEER,
        visibility_policy=PUMP_STATION_REVIEW_VISIBILITY_POLICY_V1,
    )


def test_case_derivation_plants_only_the_wrong_component_citation(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source-world"
    completed = _execute_direct(
        PumpStationWorldSessionFactory(
            source_root,
            evidence_health=True,
        )
    )
    source_snapshot = completed.run.snapshot()
    source_before = _inventory(source_root)

    prepared = derive_pump_station_review_case(
        source_run_root=source_root,
        request=_request(source_snapshot),
    )

    source_after = _inventory(source_root)
    public_pack = prepared.public_case.pack
    untreated_pack = prepared.untreated_pack
    pump_a_checks = next(
        item
        for item in public_pack.records
        if item.kind is PumpStationReviewRecordKind.FUNCTIONAL_CHECK_EVIDENCE and item.component_id == "pump-a"
    )
    pump_b_checks = next(
        item
        for item in public_pack.records
        if item.kind is PumpStationReviewRecordKind.FUNCTIONAL_CHECK_EVIDENCE and item.component_id == "pump-b"
    )
    treated_closeout = public_pack.record("closeout-record-pump-a")
    untreated_closeout = untreated_pack.record("closeout-record-pump-a")

    assert prepared.source_verification.valid is True
    assert prepared.public_case.source_snapshot == source_snapshot
    assert prepared.preparation_receipt.source_snapshot_before == source_snapshot
    assert prepared.preparation_receipt.source_snapshot_after == source_snapshot
    assert completed.run.snapshot() == source_snapshot
    assert source_after == source_before
    assert untreated_closeout.evidence_ids == pump_a_checks.source_record_ids
    assert treated_closeout.evidence_ids == pump_b_checks.source_record_ids
    assert prepared.issue.original_evidence_id == pump_a_checks.source_record_ids[0]
    assert prepared.issue.planted_evidence_id == pump_b_checks.source_record_ids[0]
    assert prepared.verifier_target.missing_evidence_ids == pump_a_checks.source_record_ids
    assert prepared.verifier_target.disposition is PumpStationReviewDisposition.REJECT_CLOSEOUT
    assert prepared.treatment_receipt.changed_record_ids == ("closeout-record-pump-a",)


def test_closeout_pack_contains_the_frozen_review_sections_without_private_fields(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source-world"
    completed = _execute_direct(
        PumpStationWorldSessionFactory(
            source_root,
            evidence_health=True,
        )
    )

    prepared = derive_pump_station_review_case(
        source_run_root=source_root,
        request=_request(completed.run.snapshot()),
    )
    kinds = {item.kind for item in prepared.public_case.pack.records}
    public_text = json.dumps(
        prepared.public_case.model_dump(mode="json"),
        sort_keys=True,
    )

    assert {
        PumpStationReviewRecordKind.CONDITION_HISTORY,
        PumpStationReviewRecordKind.DEFECT_HISTORY,
        PumpStationReviewRecordKind.WORK_ORDER,
        PumpStationReviewRecordKind.APPROVED_SCOPE,
        PumpStationReviewRecordKind.WORK_PROCESS,
        PumpStationReviewRecordKind.DEPENDENCY,
        PumpStationReviewRecordKind.ACCESS_AND_RESOURCES,
        PumpStationReviewRecordKind.INSPECTION_EVIDENCE,
        PumpStationReviewRecordKind.INTERVENTION_EVIDENCE,
        PumpStationReviewRecordKind.FUNCTIONAL_CHECK_EVIDENCE,
        PumpStationReviewRecordKind.PROVISIONAL_RETURN,
        PumpStationReviewRecordKind.CLOSEOUT,
        PumpStationReviewRecordKind.POST_MAINTENANCE_VERIFICATION,
        PumpStationReviewRecordKind.OPERATING_RESTRICTION,
        PumpStationReviewRecordKind.DUTY_FOLLOW_UP,
        PumpStationReviewRecordKind.DECISION_LINEAGE,
        PumpStationReviewRecordKind.HANDOVER_LINEAGE,
        PumpStationReviewRecordKind.FMECA_BASIS,
        PumpStationReviewRecordKind.MAINTENANCE_SCHEDULE_BASIS,
    }.issubset(kinds)
    assert "wrong_component_evidence_citation" not in public_text
    assert "issue_version" not in public_text
    assert "original_evidence_id" not in public_text
    assert "expected_affected_record_ids" not in public_text
    assert "unaffected_control_ids" not in public_text
    assert "verifier_target" not in public_text
    assert "scheduled_events" not in public_text
    assert "obstruction_severity" not in public_text
    assert "clearance_severity" not in public_text


def test_derivation_rejects_unverified_or_incomplete_source_scope(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source-world"
    incomplete = PumpStationWorldSessionFactory(
        source_root,
        evidence_health=True,
    ).open(
        WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.START,
            session_id="session-incomplete",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            agent_tenure_id="tenure-incomplete",
            run_id="run-incomplete",
            episode_id="episode-incomplete",
            world_branch_id="branch-incomplete",
        )
    )

    with pytest.raises(ValueError, match="review source is incomplete"):
        derive_pump_station_review_case(
            source_run_root=source_root,
            request=_request(incomplete.run.snapshot()),
        )
