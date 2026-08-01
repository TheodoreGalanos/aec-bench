# ABOUTME: Exposes one derived Pump A closeout case through closed reviewer tools.
# ABOUTME: Supports fresh-tenure handover and immutable typed review submission.

from __future__ import annotations

import json
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

from pydantic import field_validator, model_validator

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    canonical_content_sha256,
    validate_sha256,
)
from aec_bench.contracts.task_definition import ToolSpec
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review import (
    PumpStationReviewDisposition,
    PumpStationReviewFinding,
    PumpStationReviewPublicCase,
    PumpStationReviewRecordKind,
    PumpStationReviewSubmission,
    PumpStationReviewSubmissionReceipt,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_repository import (
    PumpStationReviewCaseRepository,
)

PUMP_STATION_REVIEW_TOOL_NAMES = (
    "observe_closeout_pack",
    "submit_closeout_review",
)


class PumpStationReviewSessionOpenMode(StrEnum):
    """Permitted ways to open one reviewer tenure."""

    OPEN = "open"
    RESUME = "resume"


class PumpStationReviewSessionRequest(ContentAddressedModel):
    """Exact host-owned binding for one reviewer tenure."""

    schema_version: str = "pump-station.review-session-request.v1"
    open_mode: PumpStationReviewSessionOpenMode
    session_id: NonEmptyStr
    case_id: NonEmptyStr
    public_case_content_sha256: str
    reviewer_tenure_id: NonEmptyStr
    handover_content_sha256: str | None = None

    @field_validator("public_case_content_sha256")
    @classmethod
    def validate_case_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("handover_content_sha256")
    @classmethod
    def validate_handover_hash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.schema_version != "pump-station.review-session-request.v1":
            raise ValueError("unsupported review session request version")
        if self.open_mode is PumpStationReviewSessionOpenMode.OPEN:
            if self.handover_content_sha256 is not None:
                raise ValueError("new review session cannot contain a handover")
        elif self.handover_content_sha256 is None:
            raise ValueError("resumed review session requires a handover")
        return self


class PumpStationReviewHandover(ContentAddressedModel):
    """Reviewer-visible case and bounded prior-tenure continuity material."""

    schema_version: str = "pump-station.review-handover.v1"
    handover_id: NonEmptyStr
    case_id: NonEmptyStr
    public_case_content_sha256: str
    from_tenure_id: NonEmptyStr
    to_tenure_id: NonEmptyStr
    public_case: PumpStationReviewPublicCase
    prior_review_ids: tuple[NonEmptyStr, ...]

    @field_validator("public_case_content_sha256")
    @classmethod
    def validate_case_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_handover(self) -> Self:
        if self.schema_version != "pump-station.review-handover.v1":
            raise ValueError("unsupported review handover version")
        if self.from_tenure_id == self.to_tenure_id:
            raise ValueError("review handover requires a fresh tenure")
        if (
            self.case_id != self.public_case.case_id
            or self.public_case_content_sha256 != self.public_case.content_sha256
        ):
            raise ValueError("review handover case binding differs")
        if len(self.prior_review_ids) != len(set(self.prior_review_ids)):
            raise ValueError("prior_review_ids must be distinct")
        return self


class PumpStationReviewObservation(ContentAddressedModel):
    """Complete reviewer-visible state for one case tenure."""

    schema_version: str = "pump-station.review-observation.v1"
    session_id: NonEmptyStr
    reviewer_tenure_id: NonEmptyStr
    public_case: PumpStationReviewPublicCase
    handover: PumpStationReviewHandover | None = None
    submitted_review_ids: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        if self.schema_version != "pump-station.review-observation.v1":
            raise ValueError("unsupported review observation version")
        if self.handover is not None and (
            self.handover.case_id != self.public_case.case_id or self.handover.to_tenure_id != self.reviewer_tenure_id
        ):
            raise ValueError("review observation handover binding differs")
        if len(self.submitted_review_ids) != len(set(self.submitted_review_ids)):
            raise ValueError("submitted_review_ids must be distinct")
        return self


def create_pump_station_review_handover(
    observation: PumpStationReviewObservation,
    *,
    from_tenure_id: str,
    to_tenure_id: str,
) -> PumpStationReviewHandover:
    """Create one content-bound handover from public material only."""
    basis = canonical_content_sha256(
        {
            "observation_content_sha256": observation.content_sha256,
            "from_tenure_id": from_tenure_id,
            "to_tenure_id": to_tenure_id,
        }
    )
    return PumpStationReviewHandover(
        handover_id=f"review-handover-{basis[:24]}",
        case_id=observation.public_case.case_id,
        public_case_content_sha256=(observation.public_case.content_sha256),
        from_tenure_id=from_tenure_id,
        to_tenure_id=to_tenure_id,
        public_case=observation.public_case,
        prior_review_ids=observation.submitted_review_ids,
    )


def build_reference_review_submission(
    public_case: PumpStationReviewPublicCase,
    *,
    review_id: str,
    reviewer_tenure_id: str,
) -> PumpStationReviewSubmission:
    """Derive the deterministic reference answer from visible records only."""
    closeout = next(
        item
        for item in public_case.pack.records
        if item.kind is PumpStationReviewRecordKind.CLOSEOUT and item.component_id == "pump-a"
    )
    if len(closeout.evidence_ids) != 1:
        raise ValueError("visible closeout must cite exactly one functional check")
    cited = public_case.pack.record(closeout.evidence_ids[0])
    if (
        cited.kind is not PumpStationReviewRecordKind.FUNCTIONAL_CHECK_EVIDENCE
        or cited.component_id == closeout.component_id
    ):
        raise ValueError("visible closeout does not contain the reference issue")
    correct = next(
        item
        for item in public_case.pack.records
        if item.kind is PumpStationReviewRecordKind.FUNCTIONAL_CHECK_EVIDENCE
        and item.component_id == closeout.component_id
    )
    duty = next(
        item
        for item in public_case.pack.records
        if item.kind is PumpStationReviewRecordKind.DUTY_FOLLOW_UP and item.component_id == closeout.component_id
    )
    return PumpStationReviewSubmission(
        review_id=review_id,
        case_id=public_case.case_id,
        public_case_content_sha256=public_case.content_sha256,
        pack_content_sha256=public_case.pack.content_sha256,
        reviewer_tenure_id=reviewer_tenure_id,
        finding=PumpStationReviewFinding.WRONG_COMPONENT_EVIDENCE_CITATION,
        finding_summary=("The Pump A closeout cites Pump B functional-check evidence."),
        affected_record_ids=(closeout.record_id,),
        unaffected_duty_ids=(duty.record_id,),
        missing_evidence_ids=correct.source_record_ids,
        disposition=PumpStationReviewDisposition.REJECT_CLOSEOUT,
        required_follow_up=(
            "correct-functional-check-citation",
            "reissue-pump-a-closeout",
        ),
        source_record_ids=(
            closeout.record_id,
            correct.source_record_ids[0],
            cited.source_record_ids[0],
        ),
    )


class PumpStationReviewSession:
    """One reviewer tenure over an immutable derived review case."""

    def __init__(
        self,
        request: PumpStationReviewSessionRequest,
        repository: PumpStationReviewCaseRepository,
        public_case: PumpStationReviewPublicCase,
        *,
        handover: PumpStationReviewHandover | None,
    ) -> None:
        self._request = request
        self._repository = repository
        self._public_case = public_case
        self._handover = handover

    @property
    def tool_names(self) -> tuple[str, ...]:
        """Return the closed reviewer tool catalogue."""
        return PUMP_STATION_REVIEW_TOOL_NAMES

    @property
    def tool_specs(self) -> tuple[ToolSpec, ...]:
        """Return provider-neutral reviewer tool specifications."""
        return tuple(
            ToolSpec(
                name=name,
                source="builtin",
                description=getattr(self, name).__doc__ or name.replace("_", " "),
            )
            for name in self.tool_names
        )

    @property
    def native_tools(self) -> tuple[Callable[..., str], ...]:
        """Return bound native reviewer functions in declared order."""
        return tuple(getattr(self, name) for name in self.tool_names)

    def observe(self) -> PumpStationReviewObservation:
        """Return only the treated pack and public continuity material."""
        return PumpStationReviewObservation(
            session_id=self._request.session_id,
            reviewer_tenure_id=self._request.reviewer_tenure_id,
            public_case=self._public_case,
            handover=self._handover,
            submitted_review_ids=self._repository.list_review_ids(self._public_case.case_id),
        )

    def submit_review(
        self,
        submission: PumpStationReviewSubmission,
    ) -> PumpStationReviewSubmissionReceipt:
        """Publish one case-bound review without exposing its evaluation target."""
        if (
            submission.case_id != self._public_case.case_id
            or submission.public_case_content_sha256 != self._public_case.content_sha256
            or submission.pack_content_sha256 != self._public_case.pack.content_sha256
        ):
            raise ValueError("review submission belongs to another visible case")
        if submission.reviewer_tenure_id != self._request.reviewer_tenure_id:
            raise ValueError("review submission belongs to another tenure")
        return self._repository.publish_review(submission)

    def observe_closeout_pack(self) -> str:
        """Read the complete treated closeout pack without private targets."""
        return json.dumps(
            self.observe().model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )

    def submit_closeout_review(
        self,
        review_id: str,
        finding: PumpStationReviewFinding,
        finding_summary: str,
        affected_record_ids: list[str],
        unaffected_duty_ids: list[str],
        missing_evidence_ids: list[str],
        disposition: PumpStationReviewDisposition,
        required_follow_up: list[str],
        source_record_ids: list[str],
    ) -> str:
        """Submit every required review field against visible source records."""
        receipt = self.submit_review(
            PumpStationReviewSubmission(
                review_id=review_id,
                case_id=self._public_case.case_id,
                public_case_content_sha256=(self._public_case.content_sha256),
                pack_content_sha256=(self._public_case.pack.content_sha256),
                reviewer_tenure_id=self._request.reviewer_tenure_id,
                finding=PumpStationReviewFinding(finding),
                finding_summary=finding_summary,
                affected_record_ids=tuple(affected_record_ids),
                unaffected_duty_ids=tuple(unaffected_duty_ids),
                missing_evidence_ids=tuple(missing_evidence_ids),
                disposition=PumpStationReviewDisposition(disposition),
                required_follow_up=tuple(required_follow_up),
                source_record_ids=tuple(source_record_ids),
            )
        )
        return receipt.model_dump_json()

    def invoke(self, action_name: str, arguments: dict[str, Any]) -> str:
        """Invoke only one declared reviewer action by exact name."""
        if action_name not in self.tool_names:
            raise ValueError(f"reviewer action is unavailable: {action_name}")
        action = getattr(self, action_name)
        result = action(**arguments)
        if not isinstance(result, str):
            raise TypeError("reviewer native action must return text")
        return result


class PumpStationReviewSessionFactory:
    """Open reviewer tenures only for complete published cases."""

    def __init__(self, review_repository_root: Path) -> None:
        self._repository_root = Path(review_repository_root)

    def open(
        self,
        request: PumpStationReviewSessionRequest,
        *,
        handover: PumpStationReviewHandover | None = None,
    ) -> PumpStationReviewSession:
        """Open an exact new or resumed reviewer tenure."""
        repository = PumpStationReviewCaseRepository(self._repository_root)
        prepared = repository.load_case(request.case_id)
        public_case = prepared.public_case
        if public_case.content_sha256 != request.public_case_content_sha256:
            raise ValueError("review session case content differs")
        if request.open_mode is PumpStationReviewSessionOpenMode.OPEN:
            if handover is not None:
                raise ValueError("new review session cannot install a handover")
        else:
            if handover is None:
                raise ValueError("resumed review session requires its handover")
            if (
                handover.content_sha256 != request.handover_content_sha256
                or handover.case_id != request.case_id
                or handover.public_case != public_case
                or handover.to_tenure_id != request.reviewer_tenure_id
            ):
                raise ValueError("review session handover differs")
        return PumpStationReviewSession(
            request,
            repository,
            public_case,
            handover=handover,
        )


__all__ = (
    "PUMP_STATION_REVIEW_TOOL_NAMES",
    "PumpStationReviewHandover",
    "PumpStationReviewObservation",
    "PumpStationReviewSession",
    "PumpStationReviewSessionFactory",
    "PumpStationReviewSessionOpenMode",
    "PumpStationReviewSessionRequest",
    "build_reference_review_submission",
    "create_pump_station_review_handover",
)
