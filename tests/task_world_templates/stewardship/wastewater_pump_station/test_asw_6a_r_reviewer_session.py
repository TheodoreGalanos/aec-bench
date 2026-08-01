# ABOUTME: Tests the closed ASW-6A-R reviewer session and independent exact verifier.
# ABOUTME: Covers handover, source binding, idempotent submission, and negative access.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_asw_5_rich_work_e2e import _execute_direct
from test_asw_6a_r_case_derivation import _request

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review import (
    PreparedPumpStationReviewCase,
    PumpStationReviewActionCode,
    PumpStationReviewDisposition,
    PumpStationReviewFinding,
    PumpStationReviewSubmission,
    derive_pump_station_review_case,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_repository import (
    PumpStationReviewCaseRepository,
    PumpStationReviewRepositoryError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_session import (
    PUMP_STATION_REVIEW_TOOL_NAMES,
    PumpStationReviewSessionFactory,
    PumpStationReviewSessionOpenMode,
    PumpStationReviewSessionRequest,
    build_reference_review_submission,
    create_pump_station_review_handover,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_verifier import (
    verify_pump_station_review,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PumpStationWorldSessionFactory,
)


def _published_case(
    tmp_path: Path,
) -> tuple[Path, Path, PreparedPumpStationReviewCase]:
    source_root = tmp_path / "source-world"
    review_root = tmp_path / "review-cases"
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
    PumpStationReviewCaseRepository(review_root).publish_case(prepared)
    return source_root, review_root, prepared


def _session_request(
    prepared: PreparedPumpStationReviewCase,
    *,
    open_mode: PumpStationReviewSessionOpenMode,
    session_id: str,
    tenure_id: str,
    handover_content_sha256: str | None = None,
) -> PumpStationReviewSessionRequest:
    public_case = prepared.public_case
    return PumpStationReviewSessionRequest(
        open_mode=open_mode,
        session_id=session_id,
        case_id=public_case.case_id,
        public_case_content_sha256=public_case.content_sha256,
        reviewer_tenure_id=tenure_id,
        handover_content_sha256=handover_content_sha256,
    )


def test_fresh_tenure_receives_same_redacted_pack_and_submits_exact_review(
    tmp_path: Path,
) -> None:
    source_root, review_root, prepared = _published_case(tmp_path)
    factory = PumpStationReviewSessionFactory(review_root)
    first = factory.open(
        _session_request(
            prepared,
            open_mode=PumpStationReviewSessionOpenMode.OPEN,
            session_id="review-session-001",
            tenure_id="review-tenure-001",
        )
    )
    first_observation = first.observe()
    handover = create_pump_station_review_handover(
        first_observation,
        from_tenure_id="review-tenure-001",
        to_tenure_id="review-tenure-002",
    )
    second = factory.open(
        _session_request(
            prepared,
            open_mode=PumpStationReviewSessionOpenMode.RESUME,
            session_id="review-session-002",
            tenure_id="review-tenure-002",
            handover_content_sha256=handover.content_sha256,
        ),
        handover=handover,
    )
    second_observation = second.observe()
    submission = build_reference_review_submission(
        second_observation.public_case,
        review_id="review-001",
        reviewer_tenure_id="review-tenure-002",
    )
    submission = PumpStationReviewSubmission.model_validate(
        {
            **submission.model_dump(mode="json", exclude={"content_sha256"}),
            "source_record_ids": [
                *submission.source_record_ids,
                "work-order-pump-a",
                "restriction-0000-pump-a-run-in",
            ],
        }
    )

    receipt = second.submit_review(submission)
    repeated = second.submit_review(submission)
    verified = verify_pump_station_review(
        source_run_root=source_root,
        review_repository_root=review_root,
        case_id=prepared.public_case.case_id,
        review_id=submission.review_id,
    )
    public_text = json.dumps(
        second_observation.model_dump(mode="json"),
        sort_keys=True,
    )

    assert first.tool_names == PUMP_STATION_REVIEW_TOOL_NAMES
    assert first_observation.public_case == second_observation.public_case
    assert second_observation.handover == handover
    assert receipt == repeated
    assert receipt.status == "accepted"
    assert verified.valid is True
    assert verified.finding_matches is True
    assert verified.affected_records_match is True
    assert verified.unaffected_duties_match is True
    assert verified.missing_evidence_matches is True
    assert verified.disposition_matches is True
    assert verified.follow_up_matches is True
    assert verified.source_references_match is True
    assert submission.review_rationale
    assert {item.record_id for item in submission.related_record_assessments} == {
        "work-order-pump-a",
        "restriction-0000-pump-a-run-in",
    }
    assert "issue_class" not in public_text
    assert "verifier_target" not in public_text
    assert "unaffected_control_ids" not in public_text
    assert "obstruction_severity" not in public_text
    assert "clearance_severity" not in public_text
    assert "scheduled_events" not in public_text


def test_wrong_review_is_persisted_but_independent_verifier_rejects_it(
    tmp_path: Path,
) -> None:
    source_root, review_root, prepared = _published_case(tmp_path)
    session = PumpStationReviewSessionFactory(review_root).open(
        _session_request(
            prepared,
            open_mode=PumpStationReviewSessionOpenMode.OPEN,
            session_id="review-session-wrong",
            tenure_id="review-tenure-wrong",
        )
    )
    public_case = session.observe().public_case
    wrong = PumpStationReviewSubmission(
        review_id="review-wrong",
        case_id=public_case.case_id,
        public_case_content_sha256=public_case.content_sha256,
        pack_content_sha256=public_case.pack.content_sha256,
        reviewer_tenure_id="review-tenure-wrong",
        finding=PumpStationReviewFinding.NO_MATERIAL_FINDING,
        finding_summary="No material closeout issue was found.",
        affected_record_ids=("work-order-pump-a",),
        unaffected_duty_ids=("obligation-0000-pump-a-verification",),
        missing_evidence_ids=("evidence-0000-functional-checks-pump-a",),
        disposition=PumpStationReviewDisposition.ACCEPT_CLOSEOUT,
        required_follow_up=(PumpStationReviewActionCode.CORRECT_FUNCTIONAL_CHECK_CITATION,),
        review_rationale="The visible records were read, but the closeout decision is wrong.",
        related_record_assessments=(),
        additional_recommendations=("Archive the closeout after correction.",),
        source_record_ids=("work-order-pump-a",),
    )

    session.submit_review(wrong)
    report = verify_pump_station_review(
        source_run_root=source_root,
        review_repository_root=review_root,
        case_id=public_case.case_id,
        review_id=wrong.review_id,
    )

    assert report.valid is False
    assert report.finding_matches is False
    assert report.affected_records_match is False
    assert report.disposition_matches is False
    assert report.follow_up_matches is False
    assert report.source_references_match is False
    assert "finding differs" in report.issues


def test_session_rejects_conflicts_foreign_sources_and_private_actions(
    tmp_path: Path,
) -> None:
    _, review_root, prepared = _published_case(tmp_path)
    session = PumpStationReviewSessionFactory(review_root).open(
        _session_request(
            prepared,
            open_mode=PumpStationReviewSessionOpenMode.OPEN,
            session_id="review-session-negative",
            tenure_id="review-tenure-negative",
        )
    )
    public_case = session.observe().public_case
    correct = build_reference_review_submission(
        public_case,
        review_id="review-negative",
        reviewer_tenure_id="review-tenure-negative",
    )
    session.submit_review(correct)

    conflict = PumpStationReviewSubmission.model_validate(
        {
            **correct.model_dump(mode="json", exclude={"content_sha256"}),
            "finding_summary": "Different content under the same review id.",
        }
    )
    foreign = PumpStationReviewSubmission.model_validate(
        {
            **correct.model_dump(mode="json", exclude={"content_sha256"}),
            "review_id": "review-foreign-source",
            "source_record_ids": ["record-outside-visible-pack"],
        }
    )

    with pytest.raises(
        PumpStationReviewRepositoryError,
        match="review-submission-id-conflict",
    ):
        session.submit_review(conflict)
    with pytest.raises(ValueError, match="source reference is outside the visible pack"):
        session.submit_review(foreign)
    with pytest.raises(ValueError, match="reviewer action is unavailable"):
        session.invoke("prepare_case", {})
