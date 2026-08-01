# ABOUTME: Independently reconstructs and evaluates one pump-station closeout review.
# ABOUTME: Uses host-private targets without trusting reviewer or stored pass claims.

from __future__ import annotations

from pathlib import Path
from typing import Self

from pydantic import model_validator

from aec_bench.contracts.harness_kernel import ContentAddressedModel
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review import (
    derive_pump_station_review_case,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_repository import (
    PumpStationReviewCaseRepository,
)


class PumpStationReviewVerificationReport(ContentAddressedModel):
    """Independent exact-field evaluation of one immutable review."""

    schema_version: str = "pump-station.review-verification-report.v1"
    case_id: NonEmptyStr
    review_id: NonEmptyStr
    source_state_id: NonEmptyStr
    source_valid: bool
    case_reconstructed: bool
    finding_matches: bool
    affected_records_match: bool
    unaffected_duties_match: bool
    missing_evidence_matches: bool
    disposition_matches: bool
    follow_up_matches: bool
    source_references_match: bool
    valid: bool
    issues: tuple[NonEmptyStr, ...]

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        if self.schema_version != "pump-station.review-verification-report.v1":
            raise ValueError("unsupported review verification report version")
        checks = (
            self.source_valid,
            self.case_reconstructed,
            self.finding_matches,
            self.affected_records_match,
            self.unaffected_duties_match,
            self.missing_evidence_matches,
            self.disposition_matches,
            self.follow_up_matches,
            self.source_references_match,
        )
        if self.valid != all(checks):
            raise ValueError("review verification validity differs from checks")
        if self.valid == bool(self.issues):
            raise ValueError("review verification issues differ from validity")
        return self


def verify_pump_station_review(
    *,
    source_run_root: Path,
    review_repository_root: Path,
    case_id: str,
    review_id: str,
    package_root: Path | None = None,
) -> PumpStationReviewVerificationReport:
    """Reload all source and review evidence and evaluate exact required fields."""
    repository = PumpStationReviewCaseRepository(review_repository_root)
    stored = repository.load_case(case_id)
    submission = repository.load_review(review_id)
    receipt = repository.load_review_receipt(review_id)
    reconstructed = derive_pump_station_review_case(
        source_run_root=source_run_root,
        request=stored.request,
        package_root=package_root,
    )
    target = stored.verifier_target
    source_valid = (
        reconstructed.source_verification.valid
        and reconstructed.source_verification.final_state_id == stored.public_case.source_snapshot.state_id
    )
    case_reconstructed = reconstructed == stored
    finding_matches = submission.finding is target.finding
    affected_records_match = submission.affected_record_ids == target.affected_record_ids
    unaffected_duties_match = submission.unaffected_duty_ids == target.unaffected_duty_ids
    missing_evidence_matches = submission.missing_evidence_ids == target.missing_evidence_ids
    disposition_matches = submission.disposition is target.disposition
    follow_up_matches = submission.required_follow_up == target.required_follow_up
    source_references_match = submission.source_record_ids == target.required_source_record_ids
    receipt_matches = (
        receipt.review_content_sha256 == submission.content_sha256
        and receipt.case_id == case_id
        and submission.case_id == case_id
    )
    issues: list[str] = []
    if not source_valid:
        issues.append("source history is not valid")
    if not case_reconstructed:
        issues.append("derived review case differs")
    if not receipt_matches:
        issues.append("review receipt differs")
        case_reconstructed = False
    if not finding_matches:
        issues.append("finding differs")
    if not affected_records_match:
        issues.append("affected records differ")
    if not unaffected_duties_match:
        issues.append("unaffected duties differ")
    if not missing_evidence_matches:
        issues.append("missing evidence differs")
    if not disposition_matches:
        issues.append("disposition differs")
    if not follow_up_matches:
        issues.append("follow-up differs")
    if not source_references_match:
        issues.append("source references differ")
    valid = all(
        (
            source_valid,
            case_reconstructed,
            finding_matches,
            affected_records_match,
            unaffected_duties_match,
            missing_evidence_matches,
            disposition_matches,
            follow_up_matches,
            source_references_match,
        )
    )
    return PumpStationReviewVerificationReport(
        case_id=case_id,
        review_id=review_id,
        source_state_id=stored.public_case.source_snapshot.state_id,
        source_valid=source_valid,
        case_reconstructed=case_reconstructed,
        finding_matches=finding_matches,
        affected_records_match=affected_records_match,
        unaffected_duties_match=unaffected_duties_match,
        missing_evidence_matches=missing_evidence_matches,
        disposition_matches=disposition_matches,
        follow_up_matches=follow_up_matches,
        source_references_match=source_references_match,
        valid=valid,
        issues=tuple(issues),
    )


__all__ = (
    "PumpStationReviewVerificationReport",
    "verify_pump_station_review",
)
