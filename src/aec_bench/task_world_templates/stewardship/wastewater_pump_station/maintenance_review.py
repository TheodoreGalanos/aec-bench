# ABOUTME: Defines the strict ASW-6A-R maintenance closeout review contracts.
# ABOUTME: Keeps review-case treatment and verifier targets separate from reviewer input.

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import field_validator, model_validator

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    validate_sha256,
)
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationVerificationReport,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationStateSnapshotRef,
)

PUMP_STATION_REVIEW_PACK_POLICY_V1 = "pump-a-closeout-pack.v1"
PUMP_STATION_REVIEW_ISSUE_VERSION_V1 = "wrong-component-evidence-citation.v1"
PUMP_STATION_REVIEW_VISIBILITY_POLICY_V1 = "reviewer-pack-only.v1"

_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class PumpStationReviewIssueClass(StrEnum):
    """Closed ASW-6A-R issue catalogue."""

    WRONG_COMPONENT_EVIDENCE_CITATION = "wrong_component_evidence_citation"


class PumpStationReviewerRole(StrEnum):
    """Permitted first-stage reviewer roles."""

    ASSET_ENGINEER = "asset_engineer"
    MAINTENANCE_ASSURANCE_ENGINEER = "maintenance_assurance_engineer"
    INDEPENDENT_VERIFICATION_ENGINEER = "independent_verification_engineer"


class PumpStationReviewFinding(StrEnum):
    """Finding classes that a reviewer can submit."""

    WRONG_COMPONENT_EVIDENCE_CITATION = "wrong_component_evidence_citation"
    NO_MATERIAL_FINDING = "no_material_finding"


class PumpStationReviewDisposition(StrEnum):
    """Available dispositions for the named closeout pack."""

    ACCEPT_CLOSEOUT = "accept_closeout"
    ACCEPT_WITH_FOLLOW_UP = "accept_with_follow_up"
    REJECT_CLOSEOUT = "reject_closeout"


class PumpStationReviewRecordKind(StrEnum):
    """Named record classes in the Pump A closeout pack."""

    CONDITION_HISTORY = "condition_history"
    DEFECT_HISTORY = "defect_history"
    WORK_ORDER = "work_order"
    APPROVED_SCOPE = "approved_scope"
    WORK_PROCESS = "work_process"
    DEPENDENCY = "dependency"
    ACCESS_AND_RESOURCES = "access_and_resources"
    INSPECTION_EVIDENCE = "inspection_evidence"
    INTERVENTION_EVIDENCE = "intervention_evidence"
    FUNCTIONAL_CHECK_EVIDENCE = "functional_check_evidence"
    PROVISIONAL_RETURN = "provisional_return"
    CLOSEOUT = "closeout"
    POST_MAINTENANCE_VERIFICATION = "post_maintenance_verification"
    OPERATING_RESTRICTION = "operating_restriction"
    DUTY_FOLLOW_UP = "duty_follow_up"
    DECISION_LINEAGE = "decision_lineage"
    HANDOVER_LINEAGE = "handover_lineage"
    FMECA_BASIS = "fmeca_basis"
    MAINTENANCE_SCHEDULE_BASIS = "maintenance_schedule_basis"


def _require_safe_id(value: str, field_name: str) -> str:
    if not _SAFE_ID_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be a safe stable identifier")
    return value


def _require_distinct_non_empty(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if not values:
        raise ValueError(f"{field_name} must not be empty")
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must be distinct")
    return values


class PumpStationReviewPreparationRequest(ContentAddressedModel):
    """Exact host-private request to derive one review case."""

    schema_version: str = "pump-station.review-preparation-request.v1"
    request_id: NonEmptyStr
    source_snapshot: PumpStationStateSnapshotRef
    asset_id: NonEmptyStr
    reviewed_component_id: NonEmptyStr
    maintenance_case_id: NonEmptyStr
    pack_policy: NonEmptyStr
    issue_class: PumpStationReviewIssueClass
    issue_version: NonEmptyStr
    target_record_id: NonEmptyStr
    cited_component_id: NonEmptyStr
    reviewer_role: PumpStationReviewerRole
    visibility_policy: NonEmptyStr

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        return _require_safe_id(value, "request_id")

    @model_validator(mode="after")
    def validate_frozen_scope(self) -> Self:
        if self.schema_version != "pump-station.review-preparation-request.v1":
            raise ValueError("unsupported review preparation schema version")
        if self.pack_policy != PUMP_STATION_REVIEW_PACK_POLICY_V1:
            raise ValueError("unsupported pack policy")
        if self.issue_version != PUMP_STATION_REVIEW_ISSUE_VERSION_V1:
            raise ValueError("unsupported issue version")
        if self.visibility_policy != PUMP_STATION_REVIEW_VISIBILITY_POLICY_V1:
            raise ValueError("unsupported visibility policy")
        if self.reviewed_component_id != "pump-a":
            raise ValueError("reviewed component must be pump-a")
        if self.maintenance_case_id != "work-order-pump-a":
            raise ValueError("maintenance case must be the Pump A work order")
        if self.target_record_id != "closeout-record-pump-a":
            raise ValueError("target record must be the Pump A closeout")
        if self.cited_component_id != "pump-b":
            raise ValueError("cited component must be pump-b")
        if self.cited_component_id == self.reviewed_component_id:
            raise ValueError("cited component must differ from the reviewed component")
        return self


class PumpStationReviewIssueSpecification(ContentAddressedModel):
    """Host-private description of the one planted closeout issue."""

    schema_version: str = "pump-station.review-issue.v1"
    request_content_sha256: str
    issue_class: PumpStationReviewIssueClass
    issue_version: NonEmptyStr
    target_record_id: NonEmptyStr
    original_evidence_id: NonEmptyStr
    planted_evidence_id: NonEmptyStr
    expected_affected_record_ids: tuple[NonEmptyStr, ...]
    unaffected_control_ids: tuple[NonEmptyStr, ...]

    @field_validator("request_content_sha256")
    @classmethod
    def validate_request_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_issue(self) -> Self:
        if self.schema_version != "pump-station.review-issue.v1":
            raise ValueError("unsupported review issue schema version")
        if self.issue_version != PUMP_STATION_REVIEW_ISSUE_VERSION_V1:
            raise ValueError("unsupported issue version")
        _require_distinct_non_empty(
            tuple(self.expected_affected_record_ids),
            "expected_affected_record_ids",
        )
        _require_distinct_non_empty(
            tuple(self.unaffected_control_ids),
            "unaffected_control_ids",
        )
        if self.original_evidence_id == self.planted_evidence_id:
            raise ValueError("planted evidence must differ from original evidence")
        return self


class PumpStationReviewVerifierTarget(ContentAddressedModel):
    """Host-private expected answer used by the independent verifier."""

    schema_version: str = "pump-station.review-verifier-target.v1"
    finding: PumpStationReviewFinding
    affected_record_ids: tuple[NonEmptyStr, ...]
    unaffected_duty_ids: tuple[NonEmptyStr, ...]
    missing_evidence_ids: tuple[NonEmptyStr, ...]
    disposition: PumpStationReviewDisposition
    required_follow_up: tuple[NonEmptyStr, ...]
    required_source_record_ids: tuple[NonEmptyStr, ...]

    @model_validator(mode="after")
    def validate_target(self) -> Self:
        if self.schema_version != "pump-station.review-verifier-target.v1":
            raise ValueError("unsupported review verifier target version")
        for field_name in (
            "affected_record_ids",
            "unaffected_duty_ids",
            "missing_evidence_ids",
            "required_follow_up",
            "required_source_record_ids",
        ):
            _require_distinct_non_empty(tuple(getattr(self, field_name)), field_name)
        return self


class PumpStationReviewSubmission(ContentAddressedModel):
    """One immutable source-bound reviewer response."""

    schema_version: str = "pump-station.review-submission.v1"
    review_id: NonEmptyStr
    case_id: NonEmptyStr
    public_case_content_sha256: str
    pack_content_sha256: str
    reviewer_tenure_id: NonEmptyStr
    finding: PumpStationReviewFinding
    finding_summary: NonEmptyStr
    affected_record_ids: tuple[NonEmptyStr, ...]
    unaffected_duty_ids: tuple[NonEmptyStr, ...]
    missing_evidence_ids: tuple[NonEmptyStr, ...]
    disposition: PumpStationReviewDisposition
    required_follow_up: tuple[NonEmptyStr, ...]
    source_record_ids: tuple[NonEmptyStr, ...]

    @field_validator("review_id", "case_id")
    @classmethod
    def validate_stable_ids(cls, value: str, info: object) -> str:
        field_name = getattr(info, "field_name", "identifier")
        return _require_safe_id(value, str(field_name))

    @field_validator("public_case_content_sha256", "pack_content_sha256")
    @classmethod
    def validate_content_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_submission(self) -> Self:
        if self.schema_version != "pump-station.review-submission.v1":
            raise ValueError("unsupported review submission schema version")
        for field_name in (
            "affected_record_ids",
            "unaffected_duty_ids",
            "missing_evidence_ids",
            "required_follow_up",
            "source_record_ids",
        ):
            _require_distinct_non_empty(tuple(getattr(self, field_name)), field_name)
        return self


class PumpStationReviewSubmissionReceipt(ContentAddressedModel):
    """Immutable acknowledgement of one structurally valid review submission."""

    schema_version: str = "pump-station.review-submission-receipt.v1"
    review_id: NonEmptyStr
    review_content_sha256: str
    case_id: NonEmptyStr
    public_case_content_sha256: str
    reviewer_tenure_id: NonEmptyStr
    status: str = "accepted"

    @field_validator("review_content_sha256", "public_case_content_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        if self.schema_version != "pump-station.review-submission-receipt.v1":
            raise ValueError("unsupported review submission receipt version")
        if self.status != "accepted":
            raise ValueError("review submission receipt must be accepted")
        return self


class PumpStationReviewPackRecord(ContentAddressedModel):
    """One reviewer-visible record with stable source references."""

    schema_version: str = "pump-station.review-pack-record.v1"
    record_id: NonEmptyStr
    kind: PumpStationReviewRecordKind
    component_id: NonEmptyStr
    title: NonEmptyStr
    statement: NonEmptyStr
    status: NonEmptyStr
    source_record_ids: tuple[NonEmptyStr, ...]
    evidence_ids: tuple[NonEmptyStr, ...] = ()
    source_sequence: int

    @field_validator("record_id")
    @classmethod
    def validate_record_id(cls, value: str) -> str:
        return _require_safe_id(value, "record_id")

    @field_validator("source_sequence")
    @classmethod
    def validate_sequence(cls, value: int) -> int:
        if isinstance(value, bool) or value < 0:
            raise ValueError("source_sequence must be a non-negative integer")
        return value

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        if self.schema_version != "pump-station.review-pack-record.v1":
            raise ValueError("unsupported review pack record version")
        _require_distinct_non_empty(
            tuple(self.source_record_ids),
            "source_record_ids",
        )
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("evidence_ids must be distinct")
        return self


class PumpStationReviewPack(ContentAddressedModel):
    """Complete reviewer-visible Pump A closeout pack."""

    schema_version: str = "pump-station.review-pack.v1"
    pack_name: NonEmptyStr
    asset_id: NonEmptyStr
    reviewed_component_id: NonEmptyStr
    maintenance_case_id: NonEmptyStr
    pack_policy: NonEmptyStr
    source_snapshot: PumpStationStateSnapshotRef
    records: tuple[PumpStationReviewPackRecord, ...]

    @model_validator(mode="after")
    def validate_pack(self) -> Self:
        if self.schema_version != "pump-station.review-pack.v1":
            raise ValueError("unsupported review pack version")
        if self.pack_policy != PUMP_STATION_REVIEW_PACK_POLICY_V1:
            raise ValueError("unsupported pack policy")
        if self.reviewed_component_id != "pump-a":
            raise ValueError("review pack must concern pump-a")
        if not self.records:
            raise ValueError("review pack records must not be empty")
        record_ids = tuple(item.record_id for item in self.records)
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("review pack record identities must be distinct")
        return self

    def record(self, record_id: str) -> PumpStationReviewPackRecord:
        """Return one record by its stable visible identity."""
        for item in self.records:
            if item.record_id == record_id:
                return item
        raise LookupError(f"review pack lacks record {record_id}")


class PumpStationReviewPublicCase(ContentAddressedModel):
    """The complete case material visible to one reviewer."""

    schema_version: str = "pump-station.review-public-case.v1"
    case_id: NonEmptyStr
    case_name: NonEmptyStr
    source_snapshot: PumpStationStateSnapshotRef
    reviewer_role: PumpStationReviewerRole
    source_verified: bool
    pack: PumpStationReviewPack

    @field_validator("case_id")
    @classmethod
    def validate_case_id(cls, value: str) -> str:
        return _require_safe_id(value, "case_id")

    @model_validator(mode="after")
    def validate_public_case(self) -> Self:
        if self.schema_version != "pump-station.review-public-case.v1":
            raise ValueError("unsupported public review case version")
        if type(self.source_verified) is not bool or not self.source_verified:
            raise ValueError("public review case requires a verified source")
        if self.source_snapshot != self.pack.source_snapshot:
            raise ValueError("public case and review pack source snapshots differ")
        return self


class PumpStationReviewPreparationReceipt(ContentAddressedModel):
    """Immutable proof that derivation did not move the source world."""

    schema_version: str = "pump-station.review-preparation-receipt.v1"
    request_content_sha256: str
    source_snapshot_before: PumpStationStateSnapshotRef
    source_snapshot_after: PumpStationStateSnapshotRef
    source_verification_sha256: str
    untreated_pack_content_sha256: str
    status: str = "completed"

    @field_validator(
        "request_content_sha256",
        "source_verification_sha256",
        "untreated_pack_content_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        if self.schema_version != "pump-station.review-preparation-receipt.v1":
            raise ValueError("unsupported preparation receipt version")
        if self.source_snapshot_before != self.source_snapshot_after:
            raise ValueError("review preparation changed the source snapshot")
        if self.status != "completed":
            raise ValueError("review preparation receipt must be completed")
        return self


class PumpStationReviewTreatmentReceipt(ContentAddressedModel):
    """Immutable host-private proof of the one record-level treatment."""

    schema_version: str = "pump-station.review-treatment-receipt.v1"
    request_content_sha256: str
    issue_content_sha256: str
    untreated_pack_content_sha256: str
    treated_pack_content_sha256: str
    changed_record_ids: tuple[NonEmptyStr, ...]

    @field_validator(
        "request_content_sha256",
        "issue_content_sha256",
        "untreated_pack_content_sha256",
        "treated_pack_content_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        if self.schema_version != "pump-station.review-treatment-receipt.v1":
            raise ValueError("unsupported treatment receipt version")
        _require_distinct_non_empty(
            tuple(self.changed_record_ids),
            "changed_record_ids",
        )
        if self.untreated_pack_content_sha256 == self.treated_pack_content_sha256:
            raise ValueError("review treatment must change the pack")
        return self


class PumpStationReviewCaseManifest(ContentAddressedModel):
    """Host-private content map for one complete derived review case."""

    schema_version: str = "pump-station.review-case-manifest.v1"
    case_id: NonEmptyStr
    request_content_sha256: str
    public_case_content_sha256: str
    issue_content_sha256: str
    verifier_target_content_sha256: str
    preparation_receipt_content_sha256: str
    treatment_receipt_content_sha256: str

    @field_validator("case_id")
    @classmethod
    def validate_case_id(cls, value: str) -> str:
        return _require_safe_id(value, "case_id")

    @field_validator(
        "request_content_sha256",
        "public_case_content_sha256",
        "issue_content_sha256",
        "verifier_target_content_sha256",
        "preparation_receipt_content_sha256",
        "treatment_receipt_content_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


@dataclass(frozen=True, slots=True)
class PreparedPumpStationReviewCase:
    """Complete public and private result of one deterministic derivation."""

    request: PumpStationReviewPreparationRequest
    source_verification: PumpStationVerificationReport
    untreated_pack: PumpStationReviewPack
    public_case: PumpStationReviewPublicCase
    issue: PumpStationReviewIssueSpecification
    verifier_target: PumpStationReviewVerifierTarget
    preparation_receipt: PumpStationReviewPreparationReceipt
    treatment_receipt: PumpStationReviewTreatmentReceipt
    manifest: PumpStationReviewCaseManifest


def derive_pump_station_review_case(
    *,
    source_run_root: Path,
    request: PumpStationReviewPreparationRequest,
    package_root: Path | None = None,
) -> PreparedPumpStationReviewCase:
    """Derive one case after independent source verification."""
    from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_derivation import (
        derive_pump_station_review_case as derive,
    )

    return derive(
        source_run_root=source_run_root,
        request=request,
        package_root=package_root,
    )


__all__ = (
    "PUMP_STATION_REVIEW_ISSUE_VERSION_V1",
    "PUMP_STATION_REVIEW_PACK_POLICY_V1",
    "PUMP_STATION_REVIEW_VISIBILITY_POLICY_V1",
    "PumpStationReviewDisposition",
    "PumpStationReviewFinding",
    "PumpStationReviewIssueClass",
    "PumpStationReviewIssueSpecification",
    "PumpStationReviewPack",
    "PumpStationReviewPackRecord",
    "PumpStationReviewPreparationReceipt",
    "PumpStationReviewPreparationRequest",
    "PumpStationReviewPublicCase",
    "PumpStationReviewCaseManifest",
    "PumpStationReviewRecordKind",
    "PumpStationReviewerRole",
    "PumpStationReviewSubmission",
    "PumpStationReviewSubmissionReceipt",
    "PumpStationReviewTreatmentReceipt",
    "PumpStationReviewVerifierTarget",
    "PreparedPumpStationReviewCase",
    "derive_pump_station_review_case",
)
