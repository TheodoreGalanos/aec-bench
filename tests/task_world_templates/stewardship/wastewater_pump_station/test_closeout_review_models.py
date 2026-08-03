# ABOUTME: Defines the frozen maintenance closeout-review contracts through tests.
# ABOUTME: Checks exact issue scope, source binding, strict review fields, and public-private separation.

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review import (
    PUMP_STATION_REVIEW_ISSUE_VERSION_V1,
    PUMP_STATION_REVIEW_PACK_POLICY_V1,
    PUMP_STATION_REVIEW_PACK_POLICY_V2,
    PUMP_STATION_REVIEW_VISIBILITY_POLICY_V1,
    PumpStationReviewActionCode,
    PumpStationReviewDisposition,
    PumpStationReviewerRole,
    PumpStationReviewFinding,
    PumpStationReviewIssueClass,
    PumpStationReviewIssueSpecification,
    PumpStationReviewPreparationRequest,
    PumpStationReviewRecordAssessment,
    PumpStationReviewSubmission,
    PumpStationReviewSubmissionV1,
    PumpStationReviewVerifierTarget,
    PumpStationReviewVerifierTargetV1,
    parse_pump_station_review_submission,
    parse_pump_station_review_verifier_target,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PUMP_STATION_SNAPSHOT_VERSION_V3,
    PumpStationStateSnapshotRef,
)


def _snapshot() -> PumpStationStateSnapshotRef:
    return PumpStationStateSnapshotRef(
        snapshot_version=PUMP_STATION_SNAPSHOT_VERSION_V3,
        run_id="run-review-source",
        episode_id="episode-review-source",
        world_branch_id="branch-review-source",
        sequence=24,
        state_id="state-review-source",
        commit_id="commit-review-source",
    )


def _preparation_request(**changes: object) -> PumpStationReviewPreparationRequest:
    values: dict[str, object] = {
        "request_id": "prepare-review-001",
        "source_snapshot": _snapshot(),
        "asset_id": "synthetic-wastewater-pump-station",
        "reviewed_component_id": "pump-a",
        "maintenance_case_id": "work-order-pump-a",
        "pack_policy": PUMP_STATION_REVIEW_PACK_POLICY_V2,
        "issue_class": PumpStationReviewIssueClass.WRONG_COMPONENT_EVIDENCE_CITATION,
        "issue_version": PUMP_STATION_REVIEW_ISSUE_VERSION_V1,
        "target_record_id": "closeout-record-pump-a",
        "cited_component_id": "pump-b",
        "reviewer_role": PumpStationReviewerRole.ASSET_ENGINEER,
        "visibility_policy": PUMP_STATION_REVIEW_VISIBILITY_POLICY_V1,
    }
    values.update(changes)
    return PumpStationReviewPreparationRequest(**values)  # type: ignore[arg-type]


def _review_submission(**changes: object) -> PumpStationReviewSubmission:
    values: dict[str, object] = {
        "review_id": "review-001",
        "case_id": "case-review-001",
        "public_case_content_sha256": "a" * 64,
        "pack_content_sha256": "b" * 64,
        "reviewer_tenure_id": "tenure-review-001",
        "finding": PumpStationReviewFinding.WRONG_COMPONENT_EVIDENCE_CITATION,
        "finding_summary": "The Pump A closeout cites Pump B functional checks.",
        "affected_record_ids": ("closeout-record-pump-a",),
        "unaffected_duty_ids": ("obligation-0000-pump-a-verification",),
        "missing_evidence_ids": ("evidence-0000-functional-checks-pump-a",),
        "disposition": PumpStationReviewDisposition.REJECT_CLOSEOUT,
        "required_follow_up": (
            PumpStationReviewActionCode.CORRECT_FUNCTIONAL_CHECK_CITATION,
            PumpStationReviewActionCode.REISSUE_PUMP_A_CLOSEOUT,
        ),
        "review_rationale": ("Pump A cannot be closed out against functional checks for Pump B."),
        "related_record_assessments": (
            {
                "record_id": "work-order-pump-a",
                "rationale": "The work order is related, but its approved scope is not changed by the citation error.",
            },
        ),
        "additional_recommendations": ("Confirm the corrected closeout during the next assurance review.",),
        "source_record_ids": (
            "closeout-record-pump-a",
            "evidence-0000-functional-checks-pump-a",
            "evidence-functional-checks-pump-b",
        ),
    }
    values.update(changes)
    return PumpStationReviewSubmission(**values)  # type: ignore[arg-type]


def test_frozen_review_values_and_preparation_binding_are_exact() -> None:
    request = _preparation_request()

    assert PUMP_STATION_REVIEW_PACK_POLICY_V1 == "pump-a-closeout-pack.v1"
    assert PUMP_STATION_REVIEW_PACK_POLICY_V2 == "pump-a-closeout-pack.v2"
    assert PUMP_STATION_REVIEW_ISSUE_VERSION_V1 == "wrong-component-evidence-citation.v1"
    assert PUMP_STATION_REVIEW_VISIBILITY_POLICY_V1 == "reviewer-pack-only.v1"
    assert tuple(PumpStationReviewIssueClass) == (PumpStationReviewIssueClass.WRONG_COMPONENT_EVIDENCE_CITATION,)
    assert request.source_snapshot == _snapshot()
    assert request.reviewed_component_id == "pump-a"
    assert request.cited_component_id == "pump-b"

    with pytest.raises(ValidationError, match="issue version"):
        _preparation_request(issue_version="wrong-component-evidence-citation.v2")
    with pytest.raises(ValidationError, match="pack policy"):
        _preparation_request(pack_policy="arbitrary-pack")
    with pytest.raises(ValidationError, match="visibility policy"):
        _preparation_request(visibility_policy="show-verifier-target")
    with pytest.raises(ValidationError, match="reviewed component"):
        _preparation_request(reviewed_component_id="pump-b")
    with pytest.raises(ValidationError, match="cited component"):
        _preparation_request(cited_component_id="pump-a")


def test_preparation_rejects_raw_record_replacement_and_physical_mutation() -> None:
    payload = _preparation_request().model_dump(mode="json")

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PumpStationReviewPreparationRequest.model_validate(
            {**payload, "raw_record_replacement": {"status": "complete"}}
        )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PumpStationReviewPreparationRequest.model_validate({**payload, "physical_mutation": {"pump-a": "failed"}})
    with pytest.raises(ValidationError, match="Input should be"):
        PumpStationReviewPreparationRequest.model_validate(
            {**payload, "issue_class": "incomplete_work_recorded_complete"}
        )


def test_review_submission_requires_every_frozen_field_and_distinct_ids() -> None:
    submission = _review_submission()
    payload = submission.model_dump(mode="json")

    assert submission.disposition is PumpStationReviewDisposition.REJECT_CLOSEOUT
    for field_name in (
        "finding",
        "affected_record_ids",
        "unaffected_duty_ids",
        "missing_evidence_ids",
        "disposition",
        "required_follow_up",
        "review_rationale",
        "source_record_ids",
    ):
        incomplete = dict(payload)
        incomplete.pop(field_name)
        with pytest.raises(ValidationError):
            PumpStationReviewSubmission.model_validate(incomplete)

    with pytest.raises(ValidationError, match="affected_record_ids must be distinct"):
        _review_submission(
            affected_record_ids=(
                "closeout-record-pump-a",
                "closeout-record-pump-a",
            )
        )


def test_hybrid_review_uses_public_action_codes_and_keeps_written_assessment() -> None:
    submission = _review_submission()

    assert submission.required_follow_up == (
        PumpStationReviewActionCode.CORRECT_FUNCTIONAL_CHECK_CITATION,
        PumpStationReviewActionCode.REISSUE_PUMP_A_CLOSEOUT,
    )
    assert submission.review_rationale.startswith("Pump A cannot be closed out")
    assert submission.related_record_assessments == (
        PumpStationReviewRecordAssessment(
            record_id="work-order-pump-a",
            rationale=("The work order is related, but its approved scope is not changed by the citation error."),
        ),
    )
    assert submission.additional_recommendations == (
        "Confirm the corrected closeout during the next assurance review.",
    )

    with pytest.raises(ValidationError, match="Input should be"):
        _review_submission(required_follow_up=("write-a-good-report",))
    with pytest.raises(ValidationError, match="related record must not be directly affected"):
        _review_submission(
            related_record_assessments=(
                {
                    "record_id": "closeout-record-pump-a",
                    "rationale": "This record is already in the direct affected set.",
                },
            )
        )


def test_version_1_review_contract_still_reloads_without_migration() -> None:
    submission = PumpStationReviewSubmissionV1(
        review_id="review-v1",
        case_id="case-review-v1",
        public_case_content_sha256="a" * 64,
        pack_content_sha256="b" * 64,
        reviewer_tenure_id="tenure-review-v1",
        finding=PumpStationReviewFinding.WRONG_COMPONENT_EVIDENCE_CITATION,
        finding_summary="The Pump A closeout cites Pump B functional checks.",
        affected_record_ids=("closeout-record-pump-a",),
        unaffected_duty_ids=("obligation-0000-pump-a-verification",),
        missing_evidence_ids=("evidence-0000-functional-checks-pump-a",),
        disposition=PumpStationReviewDisposition.REJECT_CLOSEOUT,
        required_follow_up=(
            "correct-functional-check-citation",
            "reissue-pump-a-closeout",
        ),
        source_record_ids=(
            "closeout-record-pump-a",
            "evidence-0000-functional-checks-pump-a",
            "evidence-functional-checks-pump-b",
        ),
    )
    target = PumpStationReviewVerifierTargetV1(
        finding=PumpStationReviewFinding.WRONG_COMPONENT_EVIDENCE_CITATION,
        affected_record_ids=("closeout-record-pump-a",),
        unaffected_duty_ids=("obligation-0000-pump-a-verification",),
        missing_evidence_ids=("evidence-0000-functional-checks-pump-a",),
        disposition=PumpStationReviewDisposition.REJECT_CLOSEOUT,
        required_follow_up=(
            "correct-functional-check-citation",
            "reissue-pump-a-closeout",
        ),
        required_source_record_ids=(
            "closeout-record-pump-a",
            "evidence-0000-functional-checks-pump-a",
            "evidence-functional-checks-pump-b",
        ),
    )

    assert parse_pump_station_review_submission(submission.model_dump(mode="json")) == submission
    assert parse_pump_station_review_verifier_target(target.model_dump(mode="json")) == target
    with pytest.raises(ValidationError, match="source_record_ids must be distinct"):
        _review_submission(
            source_record_ids=(
                "closeout-record-pump-a",
                "closeout-record-pump-a",
            )
        )


def test_private_issue_and_verifier_target_do_not_fit_the_public_request() -> None:
    request = _preparation_request()
    issue = PumpStationReviewIssueSpecification(
        request_content_sha256=request.content_sha256,
        issue_class=request.issue_class,
        issue_version=request.issue_version,
        target_record_id=request.target_record_id,
        original_evidence_id="evidence-0000-functional-checks-pump-a",
        planted_evidence_id="evidence-functional-checks-pump-b",
        expected_affected_record_ids=("closeout-record-pump-a",),
        unaffected_control_ids=(
            "obligation-0000-pump-a-verification",
            "restriction-0000-pump-a-run-in",
        ),
    )
    target = PumpStationReviewVerifierTarget(
        finding=PumpStationReviewFinding.WRONG_COMPONENT_EVIDENCE_CITATION,
        affected_record_ids=("closeout-record-pump-a",),
        unaffected_duty_ids=("obligation-0000-pump-a-verification",),
        missing_evidence_ids=("evidence-0000-functional-checks-pump-a",),
        disposition=PumpStationReviewDisposition.REJECT_CLOSEOUT,
        required_follow_up=(
            PumpStationReviewActionCode.CORRECT_FUNCTIONAL_CHECK_CITATION,
            PumpStationReviewActionCode.REISSUE_PUMP_A_CLOSEOUT,
        ),
        required_source_record_ids=(
            "closeout-record-pump-a",
            "evidence-0000-functional-checks-pump-a",
            "evidence-functional-checks-pump-b",
        ),
    )
    public_text = json.dumps(request.model_dump(mode="json"), sort_keys=True)

    assert issue.planted_evidence_id == "evidence-functional-checks-pump-b"
    assert target.disposition is PumpStationReviewDisposition.REJECT_CLOSEOUT
    assert "original_evidence_id" not in public_text
    assert "planted_evidence_id" not in public_text
    assert "unaffected_control_ids" not in public_text
    assert "required_source_record_ids" not in public_text
